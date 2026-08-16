from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from app.campaigns import create_campaign
from app.engine_api_v2_6 import EngineV26
from app.states import can_transition
from app.final_package_executor_v2_6 import prepare_final_package_v2_6


class DirectionEngineTests(unittest.TestCase):
    def test_capability_and_legacy_state_compatibility(self):
        with tempfile.TemporaryDirectory() as temp:
            gate = EngineV26(Path(temp)).capabilities().data["capabilities"]["direction_alignment_gate"]
            self.assertTrue(gate["implemented"])
            self.assertFalse(gate["publication_authorized"])
        self.assertTrue(can_transition("INGESTED", "PLANNED"))
        self.assertTrue(can_transition("INGESTED", "DIRECTION_ALIGNMENT_PENDING"))

    def test_new_campaign_has_direction_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_campaign(root, root / "data/harness.db", "demo", "Demo")
            self.assertTrue((root / "campaigns/demo/direction/required.json").is_file())

    def test_unconfirmed_new_campaign_reports_pending_direction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_campaign(root, root / "data/harness.db", "demo", "Demo")
            result = EngineV26(root).direction_status("example", "demo")
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "DIRECTION_ALIGNMENT_PENDING")
            self.assertEqual(result.next_action, "direction.context")

    def test_direction_campaign_final_package_requires_alignment_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "campaigns/demo/direction/required.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")
            spec = {"archive_id": "SM0816202601", "display_name": "Demo", "campaign": "demo", "platform": "youtube_shorts", "master_video": "master.mp4", "render_manifest": "render.json", "publishing_copy": "copy.json", "cover": "cover.jpg", "final_story_contract": "contract.json", "final_review": "review.json", "technical_gate": "technical.json", "owner_approval": "approval.json"}
            path = root / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "direction_alignment_report"):
                prepare_final_package_v2_6(root, path)


if __name__ == "__main__":
    unittest.main()
