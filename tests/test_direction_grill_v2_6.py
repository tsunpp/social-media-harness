from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.direction_grill_v2_6 import build_direction_context, direction_questions, draft_contract, record_answers


class DirectionGrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        campaign = self.root / "campaigns" / "demo"
        campaign.mkdir(parents=True)
        (campaign / "brief.yaml").write_text("title: Demo\n", encoding="utf-8")
        (self.root / "projects" / "example").mkdir(parents=True)
        (self.root / "projects" / "example" / "project.yaml").write_text("name: Example\n", encoding="utf-8")
        source = campaign / "source"
        source.mkdir()
        (source / "manifest.json").write_text(json.dumps({"assets": ["AST-DEMO"]}), encoding="utf-8")
        (source / "fact-contract.json").write_text(json.dumps({"confirmed_facts": [{"id": "FACT-1", "statement": "A real process is shown"}], "prohibited_claims": ["unverified efficacy"]}), encoding="utf-8")
        (source / "privacy-review.json").write_text(json.dumps({"status": "PASS", "restrictions": []}), encoding="utf-8")
        catalog = self.root / "asset_library" / "catalog"
        catalog.mkdir(parents=True)
        (catalog / "AST-DEMO.json").write_text(json.dumps({"asset_id": "AST-DEMO", "events": ["process"]}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_questions_are_stable_and_batched_to_three(self):
        build_direction_context(self.root, "example", "demo")
        first = direction_questions(self.root, "demo")
        self.assertEqual(len(first["questions"]), 3)
        self.assertEqual(first["questions"][0]["id"], "core_intent")
        self.assertTrue(first["questions"][0]["recommended_answer"])

    def test_context_requires_complete_evidence_and_extracts_facts(self):
        context = build_direction_context(self.root, "example", "demo")
        self.assertEqual(context["facts"]["confirmed"][0]["id"], "FACT-1")
        self.assertEqual(context["evidence"]["asset_ids"], ["AST-DEMO"])
        (self.root / "campaigns/demo/source/fact-contract.json").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "FACTS_OR_EVIDENCE_REQUIRED"):
            build_direction_context(self.root, "example", "demo")

    def test_contract_requires_all_answers_and_countercase(self):
        build_direction_context(self.root, "example", "demo")
        direction_questions(self.root, "demo")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            draft_contract(self.root, "demo")
        answers = {"answers": {
            "core_intent": "Show authentic process",
            "primary_audience": "Quality-conscious viewers",
            "viewer_shift": "From result to understanding",
            "creative_center": "Process is protagonist",
            "tone_priority": "Authentic first, warm second",
            "anti_direction": "Generic product ad",
            "success_test": "All options preserve the same viewer shift",
        }, "self_adversarial_check": {"strongest_countercase": "A product-led story may convert faster", "disposition": "Reject because evidence supports process-led trust"}}
        result = record_answers(self.root, "demo", answers)
        self.assertEqual(result["status"], "READY_FOR_DIRECTION_DRAFT")
        self.assertEqual(draft_contract(self.root, "demo")["status"], "AWAITING_OWNER_DIRECTION_CONFIRMATION")

    def test_ambiguous_answer_remains_unresolved(self):
        build_direction_context(self.root, "example", "demo")
        direction_questions(self.root, "demo")
        result = record_answers(self.root, "demo", {"answers": {"core_intent": "都可以"}})
        self.assertIn("core_intent", result["remaining_question_ids"])
        session = json.loads((self.root / "campaigns/demo/direction/direction-session.json").read_text(encoding="utf-8"))
        self.assertEqual(session["answer_records"]["core_intent"]["status"], "AMBIGUOUS")


if __name__ == "__main__":
    unittest.main()
