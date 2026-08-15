from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.engine_api_v2_5 import EngineV25
from app.four_agent_review_panel import aggregate_panel


def review(name, decision="PASS", findings=None, evidence_complete=True):
    return {
        "reviewer": name,
        "decision": decision,
        "findings": findings or [],
        "summary": "test",
        "evidence_complete": evidence_complete,
    }


class FourAgentPanelTests(unittest.TestCase):
    def test_all_clear_is_final_candidate(self):
        result = aggregate_panel(review("claude"), review("minimax"), review("kimi"))
        self.assertEqual(result["next_action"], "FINAL_CANDIDATE")
        self.assertFalse(result["publication_authorized"])

    def test_kimi_fact_blocker_routes_to_codex(self):
        finding = {"id":"k1","domain":"fact_integrity","severity":"blocking","problem":"unsupported","required_change":"remove"}
        result = aggregate_panel(review("claude"), review("minimax"), review("kimi", "REVISE", [finding]))
        self.assertEqual(result["next_action"], "CODEX_ADJUDICATION")
        self.assertEqual(result["binding_findings"][0]["reviewer"], "kimi")

    def test_kimi_motion_opinion_is_advisory(self):
        finding = {"id":"k1","domain":"motion","severity":"blocking","problem":"fast","required_change":"slow"}
        result = aggregate_panel(review("claude"), review("minimax"), review("kimi", "REVISE", [finding]))
        self.assertEqual(result["next_action"], "FINAL_CANDIDATE")
        self.assertEqual(result["advisory_findings"][0]["reviewer"], "kimi")

    def test_minimax_bgm_blocker_is_binding(self):
        finding = {"id":"m1","domain":"bgm","severity":"blocking","problem":"clipping","required_change":"normalize"}
        result = aggregate_panel(review("claude"), review("minimax", "REVISE", [finding]), review("kimi"))
        self.assertEqual(result["next_action"], "CODEX_ADJUDICATION")

    def test_owner_publication_request_stops(self):
        finding = {"id":"c1","domain":"publication","severity":"blocking","problem":"publish","required_change":"owner decides"}
        result = aggregate_panel(review("claude", "HUMAN_REVIEW", [finding]), review("minimax"), review("kimi"))
        self.assertEqual(result["next_action"], "HUMAN_DECISION")

    def test_incomplete_evidence_invalidates_review(self):
        with self.assertRaisesRegex(ValueError, "complete required evidence"):
            aggregate_panel(review("claude"), review("minimax"), review("kimi", evidence_complete=False))

    def test_no_improvement_guard(self):
        finding = {"id":"v1","domain":"typography","severity":"blocking","problem":"small","required_change":"larger"}
        result = aggregate_panel(review("claude", "REVISE", [finding]), review("minimax"), review("kimi"), no_improvement_streak=2)
        self.assertEqual(result["next_action"], "HUMAN_DECISION")

    def test_engine_declares_bounded_panel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            panel = EngineV25(root).capabilities().data["capabilities"]["four_agent_review_panel"]
            self.assertEqual(panel["decision_method"], "modality_authority_not_majority_vote")
            self.assertTrue(panel["owner_publication_gate"])


if __name__ == "__main__":
    unittest.main()
