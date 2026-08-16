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

    def tearDown(self):
        self.temp.cleanup()

    def test_questions_are_stable_and_batched_to_three(self):
        build_direction_context(self.root, "example", "demo")
        first = direction_questions(self.root, "demo")
        self.assertEqual(len(first["questions"]), 3)
        self.assertEqual(first["questions"][0]["id"], "core_intent")
        self.assertTrue(first["questions"][0]["recommended_answer"])

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


if __name__ == "__main__":
    unittest.main()
