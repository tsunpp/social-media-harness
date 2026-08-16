from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.audio_capability_v2_6 import load_registry
from app.platform_profiles_v2_6 import load_profiles


class PackagedDefaultsTests(unittest.TestCase):
    def test_platform_profiles_fall_back_to_packaged_defaults(self):
        with tempfile.TemporaryDirectory() as value:
            profiles = load_profiles(Path(value))
            self.assertIn("wechat_channels", profiles["platforms"])

    def test_audio_registry_falls_back_to_packaged_defaults(self):
        with tempfile.TemporaryDirectory() as value:
            registry = load_registry(Path(value))
            self.assertIn("owner", registry["providers"])


if __name__ == "__main__":
    unittest.main()