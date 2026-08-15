from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.engine_api_v1_9 import EngineV19
from app.segmented_video_orchestrator import authorize_segment_generation, prepare_assembly_gate, prepare_segment_plan, record_segmentation_consensus, register_segment_result


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def plan():
    segment = {"segment_id": "s1", "purpose": "open", "duration_seconds": 3, "visual_brief": "macro", "production_route": "comfyui_aki:minimax_h3_i2v", "continuity_in": "start", "continuity_out": "hold", "acceptance_criteria": ["stable"]}
    return {"schema_version": 1, "project": "p", "campaign": "c", "plan_id": "p1", "candidate_schemes": [{"scheme_id": "a", "segments": [segment]}, {"scheme_id": "b", "segments": [{**segment, "segment_id": "b1"}]}], "selected_scheme": "a"}


class SegmentedVideoTests(unittest.TestCase):
    def test_capability_is_mandatory(self):
        with tempfile.TemporaryDirectory() as d:
            result = EngineV19(Path(d)).capabilities()
            self.assertTrue(result.data["capabilities"]["segmented_video_workflow"]["mandatory_for_new_video_generation"])
            self.assertEqual(result.engine_api_version, "1.9")

    def test_consensus_is_required_before_segment(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); plan_path = root / "plan.json"; dump(plan_path, plan()); prepare_segment_plan(root, plan_path)
            job = root / "job.json"; agg = root / "agg.json"; dump(job, {"output": "x.mp4"}); dump(agg, {"next_action": "PASS"})
            with self.assertRaisesRegex(ValueError, "before Claude and MiniMax"):
                register_segment_result(root, plan_path, "s1", job, agg)

    def test_direct_generation_without_segment_metadata_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); spec = root / "spec.json"; dump(spec, {"backend": "minimax_h3_api"})
            with self.assertRaisesRegex(ValueError, "requires segmented_workflow"):
                authorize_segment_generation(root, spec)
    def test_complete_flow_reaches_continuity_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); plan_path = root / "plan.json"; dump(plan_path, plan()); prepare_segment_plan(root, plan_path)
            c = root / "c.json"; m = root / "m.json"; review = {"decision": "PASS", "approved_scheme_id": "a"}; dump(c, review); dump(m, review)
            record_segmentation_consensus(root, plan_path, c, m)
            job = root / "job.json"; agg = root / "agg.json"; dump(job, {"output": "x.mp4"}); dump(agg, {"next_action": "PASS", "reviewer_decisions": {"claude": "PASS", "minimax": "PASS"}})
            register_segment_result(root, plan_path, "s1", job, agg)
            self.assertEqual(prepare_assembly_gate(root, plan_path)["status"], "READY_FOR_CONTINUITY_REVIEW")


    def test_video_pipeline_final_candidate_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); plan_path = root / "plan.json"; dump(plan_path, plan()); prepare_segment_plan(root, plan_path)
            c = root / "c.json"; m = root / "m.json"; review = {"decision": "PASS", "approved_scheme_id": "a"}; dump(c, review); dump(m, review)
            record_segmentation_consensus(root, plan_path, c, m)
            job = root / "job.json"; agg = root / "agg.json"; dump(job, {"output": "x.mp4"}); dump(agg, {"next_action": "FINAL_CANDIDATE"})
            self.assertEqual(register_segment_result(root, plan_path, "s1", job, agg)["status"], "SEGMENT_APPROVED")

if __name__ == "__main__": unittest.main()
