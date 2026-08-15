from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.campaigns import advance_campaign, campaign_history, create_campaign, get_campaign
from app.database import initialize
from app.states import can_transition


class StageOneTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "data" / "test.db"
        initialize(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_state_rules(self):
        self.assertTrue(can_transition("NEW", "INGESTED"))
        self.assertFalse(can_transition("NEW", "APPROVED"))

    def test_create_campaign_builds_directories_and_database_record(self):
        path = create_campaign(self.root, self.db_path, "first-short", "First Short")
        self.assertTrue((path / "brief.yaml").is_file())
        self.assertTrue((path / "final" / "instagram").is_dir())
        self.assertEqual(get_campaign(self.db_path, "first-short")["state"], "NEW")

    def test_invalid_transition_is_rejected(self):
        create_campaign(self.root, self.db_path, "first-short", "First Short")
        with self.assertRaises(ValueError):
            advance_campaign(self.db_path, "first-short", "APPROVED", "test", "invalid")

    def test_valid_transition_is_recorded(self):
        create_campaign(self.root, self.db_path, "first-short", "First Short")
        advance_campaign(self.db_path, "first-short", "INGESTED", "tester", "ready")
        campaign = get_campaign(self.db_path, "first-short")
        history = campaign_history(self.db_path, "first-short")
        self.assertEqual(campaign["state"], "INGESTED")
        self.assertEqual(history[-1]["note"], "ready")


if __name__ == "__main__":
    unittest.main()

