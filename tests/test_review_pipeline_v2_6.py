from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.panel_clearance_v2_6 import validate_panel_clearance
from app.review_pipeline_v2_6 import prepare_complete_evidence, proxy_required, run_resumable_panel


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def passed(name: str):
    return ({"reviewer":name,"decision":"PASS","evidence_complete":True,"findings":[],"summary":"pass"}, {"raw":name})


class ReviewPipelineV26Tests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        matrix = {"status":"ACTIVE","recipients":{}}
        materials = ["privacy_cleared_timeline","rendered_video","copy","source_proxy","sanitized_dossier","provenance"]
        for name in ("claude","minimax","kimi-k3"):
            matrix["recipients"][name] = {"status":"AUTHORIZED","allowed_materials":materials,"identifiable_people_allowed":True,"metadata_stripping_required":True}
        dump(root / "projects/p/decisions/review-authorization-matrix-v2-6.json", matrix)
        master = root / "master.mp4"; master.write_bytes(b"video")
        frame = root / "frame.jpg"; frame.write_bytes(b"image")
        for name, value in {
            "render.json":{"output":{"duration_seconds":1}}, "brief.json":{}, "facts.json":{},
            "privacy.json":{"status":"PASS","identifiable_people":True}, "contract.json":{},
            "copy.json":{"publishing_authorized":False}, "source.json":{"assets":[]},
        }.items(): dump(root / name, value)
        return dump(root / "spec.json", {
            "project":"p","campaign":"c","master_video":"master.mp4","render_manifest":"render.json",
            "brief":"brief.json","facts":"facts.json","privacy":"privacy.json","story_contract":"contract.json",
            "copy":"copy.json","source_manifest":"source.json","timeline_files":["frame.jpg"],"review_dir":"reviews"
        })

    def test_complete_evidence_and_three_reviewer_panel(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); spec = self.fixture(root)
            bundle = prepare_complete_evidence(root, spec)
            calls = {name:0 for name in ("claude","minimax","kimi")}
            def callback(name):
                def run(_): calls[name] += 1; return passed(name)
                return run
            panel = run_resumable_panel(root, bundle, {name:callback(name) for name in calls})
            self.assertEqual(panel["next_action"], "FINAL_CANDIDATE")
            self.assertEqual(validate_panel_clearance(panel, root)["active_reviewers"], ["claude","kimi","minimax"])
            self.assertEqual(calls, {"claude":1,"minimax":1,"kimi":1})

    def test_resume_reuses_hash_matching_reviews(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); spec = self.fixture(root)
            bundle = prepare_complete_evidence(root, spec)
            calls = {name:0 for name in ("claude","minimax","kimi")}
            callbacks = {}
            for name in calls:
                def run(_, name=name): calls[name] += 1; return passed(name)
                callbacks[name] = run
            run_resumable_panel(root, bundle, callbacks)
            bundle = prepare_complete_evidence(root, spec)
            run_resumable_panel(root, bundle, callbacks)
            self.assertEqual(calls, {"claude":1,"minimax":1,"kimi":1})

    def test_panel_rejects_stale_master_hash(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); spec = self.fixture(root); bundle = prepare_complete_evidence(root, spec)
            panel = run_resumable_panel(root, bundle, {name:(lambda _, name=name: passed(name)) for name in ("claude","minimax","kimi")})
            panel["reviewers"]["kimi"]["reviewed_master_sha256"] = "stale"
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_panel_clearance(panel, root)

    def test_failed_reviewer_resumes_without_repeating_completed_reviewer(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); spec = self.fixture(root); bundle = prepare_complete_evidence(root, spec)
            calls = {"claude":0,"minimax":0,"kimi":0}
            def claude(_): calls["claude"] += 1; return passed("claude")
            def broken(_): calls["minimax"] += 1; raise RuntimeError("temporary")
            with self.assertRaisesRegex(RuntimeError, "temporary"):
                run_resumable_panel(root, bundle, {"claude":claude,"minimax":broken,"kimi":lambda _:passed("kimi")})
            state = json.loads((root / "reviews/review-state-v2-6.json").read_text())
            self.assertEqual(state["reviewers"]["minimax"]["status"], "FAILED")
            def minimax(_): calls["minimax"] += 1; return passed("minimax")
            def kimi(_): calls["kimi"] += 1; return passed("kimi")
            panel = run_resumable_panel(root, bundle, {"claude":claude,"minimax":minimax,"kimi":kimi})
            self.assertEqual(panel["next_action"], "FINAL_CANDIDATE")
            self.assertEqual(calls, {"claude":1,"minimax":2,"kimi":1})

    def test_minimax_proxy_preflight_uses_provider_limit(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "large.mp4"
            with path.open("wb") as handle: handle.truncate(50 * 1024 * 1024 + 1)
            self.assertTrue(proxy_required(path, "minimax"))
            self.assertFalse(proxy_required(path, "claude"))


if __name__ == "__main__":
    unittest.main()

