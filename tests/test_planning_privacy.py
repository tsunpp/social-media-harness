from __future__ import annotations

import unittest

from app.planning_privacy import find_quarantined_plan_references, sanitize_planning_context


class PlanningPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"rules": [{"asset_id": "AST-PII", "classification": "PII", "automated_selection_allowed": False}]}

    def test_pixels_are_removed_but_inventory_remains(self):
        context = {
            "asset_records": [{"asset_id": "AST-PII", "thumbnail_path": "thumb.jpg", "proxy_path": None, "keyframes": []}],
            "evidence": {
                "images": ["asset_library/thumbnails/AST-PII.jpg"], "videos": [],
                "files": [{"path": "asset_library/catalog/AST-PII.json", "role": "asset_catalog"}, {"path": "asset_library/thumbnails/AST-PII.jpg", "role": "asset_thumbnail"}],
                "image_evidence_count": 1, "video_proxy_count": 0
            }
        }
        result = sanitize_planning_context(context, self.policy)
        self.assertEqual(result["evidence"]["images"], [])
        self.assertEqual(len(result["asset_records"]), 1)
        self.assertIsNone(result["asset_records"][0]["thumbnail_path"])
        self.assertEqual(result["evidence"]["files"][0]["role"], "asset_catalog")
        report = result["privacy_quarantine"]["removed_pixel_evidence"]
        self.assertNotIn("path", report["images"][0])
        self.assertNotIn("path", report["manifest_entries"][0])

    def test_quarantined_asset_cannot_be_selected(self):
        plan = {"options": [{"id": "A", "opening_hook": {"asset_id": "AST-PII"}, "timeline": []}]}
        self.assertEqual(find_quarantined_plan_references(plan, self.policy)[0]["location"], "opening_hook")


if __name__ == "__main__":
    unittest.main()

