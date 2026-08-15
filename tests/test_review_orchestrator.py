from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.comfyui_adapter import ComfyUIError, apply_bindings, is_api_workflow, prepare_job
from app.review_orchestrator import sample_times
from app.review_policy import aggregate_reviews, validate_review


def review(decision="PASS", risk=2):
    return {
        "reviewer": "test",
        "decision": decision,
        "scores": {
            "visual_quality": 8,
            "authenticity": 9,
            "brand_consistency": 7,
            "platform_fit": 8,
            "risk": risk,
        },
        "blocking_issues": [] if decision == "PASS" else [
            {"id": "test", "location": "test", "problem": "test", "required_change": "test"}
        ],
        "optional_suggestions": [],
        "summary": "test",
    }


class ReviewPolicyTests(unittest.TestCase):
    def test_both_reviewers_pass_without_owner_interruption(self):
        result = aggregate_reviews(review(), review(), revision_count=0)
        self.assertEqual(result["next_action"], "FINAL_CANDIDATE")

    def test_routine_revision_routes_to_codex(self):
        result = aggregate_reviews(review("REVISE"), review(), revision_count=0)
        self.assertEqual(result["next_action"], "CODEX_ADJUDICATION")

    def test_high_risk_routes_to_owner(self):
        result = aggregate_reviews(review("HUMAN_REVIEW", risk=7), review(), revision_count=0)
        self.assertEqual(result["next_action"], "HUMAN_DECISION")

    def test_revision_limit_routes_to_owner(self):
        result = aggregate_reviews(review("REVISE"), review(), revision_count=8)
        self.assertEqual(result["next_action"], "HUMAN_DECISION")

    def test_revision_can_continue_beyond_old_two_cycle_limit(self):
        result = aggregate_reviews(review("REVISE"), review(), revision_count=2)
        self.assertEqual(result["next_action"], "CODEX_ADJUDICATION")
        self.assertEqual(result["auto_revision_limit"], 8)

    def test_no_improvement_loop_guard_routes_to_owner(self):
        history = [
            {"measurable_improvement": False, "blocker_signature": "a"},
            {"measurable_improvement": False, "blocker_signature": "b"},
        ]
        result = aggregate_reviews(review("REVISE"), review(), 2, revision_history=history)
        self.assertEqual(result["next_action"], "HUMAN_DECISION")
        self.assertEqual(result["reason"], "revision_progress_stalled")

    def test_same_blocker_three_times_routes_to_owner(self):
        history = [
            {"measurable_improvement": True, "blocker_signature": "same"},
            {"measurable_improvement": True, "blocker_signature": "same"},
            {"measurable_improvement": True, "blocker_signature": "same"},
        ]
        result = aggregate_reviews(review("REVISE"), review(), 3, revision_history=history)
        self.assertEqual(result["reason"], "revision_progress_stalled")

    def test_revision_limit_cannot_exceed_safety_ceiling(self):
        with self.assertRaises(ValueError):
            aggregate_reviews(review("REVISE"), review(), 0, auto_revision_limit=11)

    def test_invalid_score_is_rejected(self):
        invalid = review()
        invalid["scores"]["risk"] = 11
        with self.assertRaises(ValueError):
            validate_review(invalid)

    def test_pass_with_high_risk_is_rejected_as_self_contradictory(self):
        with self.assertRaises(ValueError):
            validate_review(review(risk=9))

    def test_caption_midpoint_is_sampled(self):
        self.assertIn(12.0, sample_times(20, [{"start": 10, "end": 14}]))

    def test_full_timeline_is_sampled_each_second(self):
        times = sample_times(5.2, [])
        for second in (1.0, 2.0, 3.0, 4.0):
            self.assertIn(second, times)
        self.assertGreaterEqual(len(times), 6)


class ComfyUIAdapterTests(unittest.TestCase):
    def test_api_workflow_detection_and_binding(self):
        workflow = {"1": {"class_type": "TestNode", "inputs": {"prompt": "old"}}}
        self.assertTrue(is_api_workflow(workflow))
        bound = apply_bindings(workflow, {"1.prompt": "new"})
        self.assertEqual(bound["1"]["inputs"]["prompt"], "new")
        self.assertEqual(workflow["1"]["inputs"]["prompt"], "old")

    def test_ui_workflow_is_not_mistaken_for_api_workflow(self):
        self.assertFalse(is_api_workflow({"nodes": [{"id": 1, "type": "LoadImage"}]}))

    def test_disabled_capability_cannot_run(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.json"
            registry.write_text(
                '{"capabilities":{"x":{"enabled":false,"api_workflow":"missing.json"}}}',
                encoding="utf-8",
            )
            with self.assertRaises(ComfyUIError):
                prepare_job(registry, "x", {})


if __name__ == "__main__":
    unittest.main()


