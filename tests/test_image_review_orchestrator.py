from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.engine_api_v1_7 import EngineV17
from app.image_review_orchestrator import find_privacy_conflicts, normalize_nonblocking_revision, prepare_image_review, run_image_review


def review(reviewer: str, choice: str):
    return {
        "reviewer": reviewer, "decision": "PASS", "recommended_candidate": choice,
        "candidate_findings": [
            {"candidate_id": key, "strengths": ["clear"], "weaknesses": [], "platform_crop_notes": ["safe"]}
            for key in ("ONE", "TWO")
        ],
        "scores": {"visual_quality": 8, "authenticity": 9, "brand_consistency": 8, "platform_fit": 8, "risk": 2},
        "blocking_issues": [], "optional_suggestions": [], "summary": "complete review",
    }


class ImageReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("projects/test", "campaigns/camp/drafts/v1", "campaigns/camp", "memory", "policies"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / "projects/test/project.yaml").write_text("project", encoding="utf-8")
        (self.root / "projects/test/PROJECT_DECISIONS.md").write_text("decisions", encoding="utf-8")
        (self.root / "campaigns/camp/brief.yaml").write_text("brief", encoding="utf-8")
        (self.root / "memory/decision.json").write_text("{}", encoding="utf-8")
        (self.root / "memory/base.json").write_text("{}", encoding="utf-8")
        (self.root / "memory/stage.md").write_text("stage", encoding="utf-8")
        (self.root / "memory/HEAD_9998.json").write_text(json.dumps({"base_state": "memory/base.json", "current_stage_summary": "memory/stage.md", "active_decisions": ["memory/decision.json"]}), encoding="utf-8")
        (self.root / "memory/HEAD_9999.json").write_text(json.dumps({"previous_head": "memory/HEAD_9998.json"}), encoding="utf-8")
        (self.root / "policies/privacy_quarantine.json").write_text(json.dumps({"rules": [{"asset_id": "PII", "external_model_pixels_allowed": False}]}), encoding="utf-8")
        for name in ("one.jpg", "two.jpg"):
            (self.root / f"campaigns/camp/drafts/v1/{name}").write_bytes(b"image")
        self.manifest = self.root / "campaigns/camp/drafts/v1/image-candidates.json"
        self.manifest.write_text(json.dumps({
            "schema_version": 1, "campaign": "camp", "set_id": "set", "purpose": "test", "platforms": ["instagram"],
            "candidates": [
                {"id": "ONE", "path": "campaigns/camp/drafts/v1/one.jpg", "provenance": {"type": "source"}},
                {"id": "TWO", "path": "campaigns/camp/drafts/v1/two.jpg", "provenance": {"type": "source"}},
            ],
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_candidate_set_and_hashes(self):
        request = prepare_image_review(self.root, "test", "camp", self.manifest)
        self.assertTrue(request["evidence_manifest"]["complete_candidate_set"])
        self.assertEqual(request["evidence_manifest"]["candidate_count"], 2)
        self.assertTrue(all(x["sha256"] for x in request["evidence_manifest"]["candidates"]))
        self.assertEqual(len(request["project_context"]["active_decisions"]), 1)

    def test_quarantined_candidate_is_blocked(self):
        candidate_set = {"candidates": [{"id": "X", "path": "thumbs/PII.jpg", "provenance": {"asset_id": "PII"}}]}
        conflicts = find_privacy_conflicts(candidate_set, {"rules": [{"asset_id": "PII", "external_model_pixels_allowed": False}]})
        self.assertEqual(conflicts[0]["asset_id"], "PII")

    @patch("app.image_review_orchestrator.call_minimax")
    @patch("app.image_review_orchestrator.call_claude")
    def test_agreement_routes_to_codex_not_owner(self, claude, minimax):
        claude.return_value = (review("claude", "TWO"), {"raw": True})
        minimax.return_value = (review("minimax", "TWO"), {"raw": True})
        result = run_image_review(self.root, prepare_image_review(self.root, "test", "camp", self.manifest))
        self.assertEqual(result["next_action"], "CODEX_FINALIZE_IMAGE_CANDIDATE")
        self.assertEqual(result["recommended_candidate"], "TWO")

    def test_nonblocking_low_risk_revision_is_normalized(self):
        value = review("claude", "ONE")
        value["decision"] = "REVISE"
        normalized = normalize_nonblocking_revision(value)
        self.assertEqual(normalized["decision"], "PASS")
        self.assertEqual(normalized["contract_normalization"]["original_decision"], "REVISE")

    def test_engine_v17_recovery_follows_head_chain(self):
        result = EngineV17(self.root).recover()
        self.assertTrue(result.ok)
        self.assertEqual(result.data["head"], "memory/HEAD_9999.json")
        self.assertEqual(result.engine_api_version, "1.7")

    def test_engine_reports_image_capability(self):
        result = EngineV17(self.root).capabilities()
        self.assertTrue(result.data["capabilities"]["image"]["implemented"])
        self.assertEqual(result.engine_api_version, "1.7")


if __name__ == "__main__":
    unittest.main()
