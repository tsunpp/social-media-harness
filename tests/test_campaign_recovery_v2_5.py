from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.campaign_recovery_v2_5 import register_existing_campaign


class CampaignRecoveryV25Tests(unittest.TestCase):
    def test_existing_directory_is_registered_at_new_only(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); (root / "campaigns/existing").mkdir(parents=True)
            result = register_existing_campaign(root, root / "data/harness.db", "existing", "Existing")
            self.assertEqual(result["state"], "NEW")

    def test_missing_directory_cannot_be_registered(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            with self.assertRaises(FileNotFoundError):
                register_existing_campaign(root, root / "data/harness.db", "missing", "Missing")


if __name__ == "__main__":
    unittest.main()
