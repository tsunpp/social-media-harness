from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.direction_contract_v2_6 import confirm_contract, file_hash
from app.segmented_video_orchestrator import prepare_segment_plan


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class DirectionDownstreamGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        dump(self.root / "campaigns/c/direction/required.json", {"required": True})
        source = dump(self.root / "source.json", {"fact": True})
        draft = {
            "schema_version": 1, "campaign": "c", "status": "DRAFT_AWAITING_OWNER",
            "core_intent": {"statement": "process"}, "audience": {"primary": "viewer"},
            "desired_viewer_shift": {"statement": "understand"}, "creative_center": {"statement": "process"},
            "tone": {"priority": "authentic"}, "must_communicate": [{"statement": "real process", "evidence_refs": ["FACT-1"]}],
            "must_not_imply": [], "anti_direction": ["generic ad"], "success_tests": ["same shift"],
            "open_freedoms": ["rhythm"], "unresolved_owner_decisions": [],
            "self_adversarial_check": {"strongest_countercase": "product", "disposition": "reject"},
            "source_hashes": {"source.json": file_hash(source)},
        }
        self.confirmed = confirm_contract(self.root, "c", dump(self.root / "draft.json", draft), "owner")

    def tearDown(self):
        self.temp.cleanup()

    def alignment(self, **changes):
        value = {"direction_contract_hash": self.confirmed["contract_hash"], "core_intent": "process",
                 "audience": "viewer", "viewer_shift": "understand", "creative_center": "process",
                 "tone": "authentic", "promises": ["real process"], "anti_direction_hits": []}
        value.update(changes)
        return value

    def plan(self, alignment):
        segment = {"segment_id": "s1", "purpose": "show change", "duration_seconds": 2,
                   "visual_brief": "process", "production_route": "ffmpeg", "continuity_in": "start",
                   "continuity_out": "result", "acceptance_criteria": ["visible"],
                   "asset_id": "AST-1", "narrative_function": "middle change"}
        return {"schema_version": 1, "project": "p", "campaign": "c", "plan_id": "p1",
                "candidate_schemes": [{"scheme_id": "a", "segments": [segment]}, {"scheme_id": "b", "segments": [{**segment, "segment_id": "s2"}]}],
                "selected_scheme": "a", "direction_trace": alignment}

    def test_shot_mapping_gate_passes_and_blocks_core_drift(self):
        prepare_segment_plan(self.root, dump(self.root / "plan.json", self.plan(self.alignment())))
        with self.assertRaisesRegex(ValueError, "diverges"):
            prepare_segment_plan(self.root, dump(self.root / "bad.json", self.plan(self.alignment(creative_center="product"))))


if __name__ == "__main__":
    unittest.main()
