from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.engine_api_v1_2 import EngineV12
from app.planning_orchestrator import manifest_asset_ids, prepare_plan_review, prepare_planning_context, run_plan_review


def valid_review(reviewer: str):
    return {
        "reviewer": reviewer,
        "decision": "PASS",
        "recommended_option": "A",
        "scores": {"visual_quality": 8, "authenticity": 9, "brand_consistency": 8, "platform_fit": 8, "risk": 2},
        "blocking_issues": [],
        "optional_suggestions": [],
        "summary": "ready for owner selection",
    }


class PlanningOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for path in [
            "projects/test-project", "campaigns/test-campaign/source", "campaigns/test-campaign/plans",
            "asset_library/catalog", "asset_library/thumbnails", "asset_library/keyframes",
            "asset_library/proxies", "memory", "data"
        ]:
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "projects/test-project/project.yaml").write_text("project: test", encoding="utf-8")
        (self.root / "projects/test-project/PROJECT_DECISIONS.md").write_text("decisions", encoding="utf-8")
        (self.root / "campaigns/test-campaign/brief.yaml").write_text('{"topic":"test"}', encoding="utf-8")
        (self.root / "campaigns/test-campaign/source/manifest.json").write_text('{"assets":["AST-1"]}', encoding="utf-8")
        (self.root / "asset_library/thumbnails/AST-1.jpg").write_bytes(b"jpeg")
        asset = {
            "asset_id": "AST-1", "filename": "one.jpg", "media_type": "image",
            "thumbnail_path": "asset_library/thumbnails/AST-1.jpg", "proxy_path": None,
            "keyframes": [], "processing_status": "ready"
        }
        (self.root / "asset_library/catalog/AST-1.json").write_text(json.dumps(asset), encoding="utf-8")
        decision = {"decision_id": "truth", "status": "ACTIVE_CONFIRMED"}
        (self.root / "memory/decision.json").write_text(json.dumps(decision), encoding="utf-8")
        (self.root / "memory/base.json").write_text("{}", encoding="utf-8")
        (self.root / "memory/stage.md").write_text("stage", encoding="utf-8")
        head = {
            "base_state": "memory/base.json", "state_overlays_in_order": [],
            "active_decisions": ["memory/decision.json"], "current_stage_summary": "memory/stage.md",
            "current_audit": {}, "next_stage_after_owner_acceptance": "plan"
        }
        (self.root / "memory/HEAD_9999.json").write_text(json.dumps(head), encoding="utf-8")
        option = {"name": "name", "target_duration_seconds": 20, "concept": "concept", "opening_hook": {}, "timeline": [{}, {}, {}, {}], "strength": "s", "risk": "r"}
        plan = {"schema_version": 1, "campaign": "test-campaign", "status": "awaiting_human_selection", "shared_output": {}, "options": [{"id": key, **option} for key in "ABC"], "selection_required": {}}
        (self.root / "campaigns/test-campaign/plans/plan_options.json").write_text(json.dumps(plan), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_context_contains_every_asset_and_active_decision(self):
        context = prepare_planning_context(self.root, "test-project", "test-campaign")
        self.assertEqual(context["evidence"]["asset_count"], 1)
        self.assertEqual(context["evidence"]["image_evidence_count"], 1)
        self.assertEqual(context["active_decisions"][0]["content"]["decision_id"], "truth")

    def test_current_manifest_object_records_are_normalized_to_asset_ids(self):
        manifest = {"assets": [{"asset_id": "AST-1", "decoded_path": "x.jpg"}]}
        self.assertEqual(manifest_asset_ids(manifest), ["AST-1"])
        (self.root / "campaigns/test-campaign/source/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        context = prepare_planning_context(self.root, "test-project", "test-campaign")
        self.assertEqual(context["asset_records"][0]["asset_id"], "AST-1")

    def test_campaign_fact_privacy_and_scope_evidence_are_included(self):
        campaign = self.root / "campaigns/test-campaign"
        (campaign / "decisions").mkdir()
        for relative in ("source/fact-contract.json", "source/privacy-review.json", "decisions/audience-scope.json", "decisions/photo-native-format-exception.json"):
            (campaign / relative).write_text('{"status":"PASS"}', encoding="utf-8")
        context = prepare_planning_context(self.root, "test-project", "test-campaign")
        self.assertEqual(set(context["campaign_evidence"]), {"fact_contract", "privacy_review", "audience_scope", "format_exception"})
        roles = {item["role"] for item in context["evidence"]["files"]}
        self.assertIn("campaign_fact_contract", roles)
        self.assertIn("campaign_format_exception", roles)

    def test_prepare_review_validates_three_options(self):
        request = prepare_plan_review(self.root, "test-project", "test-campaign")
        self.assertEqual([item["id"] for item in request["plan_options"]["options"]], ["A", "B", "C"])
        self.assertTrue((self.root / "campaigns/test-campaign/plans/reviews/planning-review-request.json").is_file())

    @patch("app.planning_orchestrator.call_minimax")
    @patch("app.planning_orchestrator.call_claude")
    def test_both_pass_still_waits_for_owner_direction(self, claude, minimax):
        claude.return_value = (valid_review("claude"), {"raw": True})
        minimax.return_value = (valid_review("minimax"), {"raw": True})
        request = prepare_plan_review(self.root, "test-project", "test-campaign")
        result = run_plan_review(self.root, request)
        self.assertEqual(result["next_action"], "AWAITING_OWNER_PLAN_SELECTION")

    def test_engine_reports_planning_implemented(self):
        result = EngineV12(self.root).capabilities()
        self.assertTrue(result.data["capabilities"]["plan"]["implemented"])
        self.assertEqual(result.engine_api_version, "1.2")


if __name__ == "__main__":
    unittest.main()
