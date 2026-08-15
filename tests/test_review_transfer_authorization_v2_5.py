from __future__ import annotations

import unittest
from pathlib import Path

from app.review_transfer_authorization import resolve_review_transfer_authorization


ROOT = Path(__file__).resolve().parents[1]


class ReviewTransferAuthorizationV25Tests(unittest.TestCase):
    def test_all_three_reviewers_are_authorized_without_per_transfer_confirmation(self):
        result = resolve_review_transfer_authorization(
            ROOT,
            "example-project",
            "campaign-slug",
            ["claude", "minimax", "kimi-k3"],
            ["privacy_cleared_timeline", "rendered_video", "sanitized_dossier"],
            "PASS",
            "PASS",
        )
        self.assertEqual(result["status"], "AUTHORIZED_FOR_SCOPED_REVIEW_TRANSFER")
        self.assertFalse(result["per_transfer_owner_confirmation_required"])
        self.assertFalse(result["publication_authorized"])

    def test_privacy_failure_blocks_transfer(self):
        with self.assertRaisesRegex(ValueError, "privacy preflight PASS"):
            resolve_review_transfer_authorization(
                ROOT, "example-project", "campaign-slug", ["claude"], ["timeline"], "FAIL", "PASS"
            )

    def test_unknown_recipient_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Unauthorized review recipient"):
            resolve_review_transfer_authorization(
                ROOT, "example-project", "campaign-slug", ["other-model"], ["timeline"], "PASS", "PASS"
            )

    def test_sensitive_material_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Forbidden review material"):
            resolve_review_transfer_authorization(
                ROOT, "example-project", "campaign-slug", ["kimi-k3"], ["identity_document"], "PASS", "PASS"
            )


if __name__ == "__main__":
    unittest.main()
