from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.direction_alignment_v2_6 import validate_narrative_options_alignment
from app.direction_contract_v2_6 import confirm_contract, validate_confirmation
from app.direction_grill_v2_6 import build_direction_context, direction_questions, draft_contract, record_answers
from app.engine_api_v2_6 import EngineV26


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


class DirectionEndToEndTests(unittest.TestCase):
    def test_evidence_grill_confirm_align_stale_and_recover(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = root / "campaigns/synthetic"
            dump(campaign / "brief.yaml", {"title": "Synthetic"})
            dump(campaign / "source/manifest.json", {"assets": ["AST-SYNTH"]})
            fact = dump(campaign / "source/fact-contract.json", {"confirmed_facts": [{"id": "FACT-1", "statement": "real process"}], "prohibited_claims": ["instant result"]})
            dump(campaign / "source/privacy-review.json", {"status": "PASS", "restrictions": []})
            dump(root / "projects/example/project.yaml", {"name": "Example"})
            dump(root / "asset_library/catalog/AST-SYNTH.json", {"asset_id": "AST-SYNTH", "events": ["process"]})

            context = build_direction_context(root, "example", "synthetic")
            self.assertEqual(context["facts"]["confirmed"][0]["id"], "FACT-1")
            self.assertLessEqual(len(direction_questions(root, "synthetic")["questions"]), 3)
            ambiguous = record_answers(root, "synthetic", {"answers": {"core_intent": "都可以"}})
            self.assertIn("core_intent", ambiguous["remaining_question_ids"])
            answers = {"answers": {"core_intent": "process", "primary_audience": "viewer", "viewer_shift": "understand",
                       "creative_center": "process", "tone_priority": "authentic", "anti_direction": "generic ad",
                       "success_test": "same shift"},
                       "self_adversarial_check": {"strongest_countercase": "product-led", "disposition": "reject"}}
            self.assertEqual(record_answers(root, "synthetic", answers)["status"], "READY_FOR_DIRECTION_DRAFT")
            draft_result = draft_contract(root, "synthetic")
            confirmed = confirm_contract(root, "synthetic", root / draft_result["contract"], "owner")
            trace = {"direction_contract_hash": confirmed["contract_hash"], "core_intent": "process", "audience": "viewer",
                     "viewer_shift": "understand", "creative_center": "process", "tone": "authentic",
                     "promises": ["real process"], "anti_direction_hits": []}
            self.assertEqual(validate_narrative_options_alignment(root, "synthetic", {"options": [{"id": x, "direction_trace": trace} for x in "ABC"]})["status"], "PASS")

            dump(fact, {"confirmed_facts": [{"id": "FACT-2", "statement": "changed"}]})
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_confirmation(root, "synthetic")
            status = EngineV26(root).direction_status("example", "synthetic")
            self.assertEqual(status.status, "DIRECTION_ALIGNMENT_PENDING")
            recovered = EngineV26(root).recover(project="example", campaign="synthetic")
            self.assertTrue(recovered.ok)
            self.assertEqual(recovered.data["campaign"], "synthetic")


if __name__ == "__main__":
    unittest.main()
