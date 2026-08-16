from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.head_discovery import current_head
from app.engine_api_v2_6 import EngineV26


class HeadDiscoveryV26Tests(unittest.TestCase):
    def write(self, root: Path, name: str, value: dict, mtime: float) -> Path:
        path = root / "memory" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path

    def test_new_independent_campaign_beats_deep_old_chain(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            old = self.write(root, "HEAD_old.json", {"project":"p","campaign":"old"}, 100)
            self.write(root, "HEAD_old_2.json", {"project":"p","campaign":"old","previous_head":"memory/HEAD_old.json"}, 200)
            newest = self.write(root, "HEAD_new.json", {"project":"p","campaign":"new"}, 300)
            self.assertEqual(current_head(root), newest)
            self.assertNotEqual(current_head(root), old)

    def test_project_and_campaign_scope(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            wanted = self.write(root, "HEAD_a.json", {"project":"family","campaign":"adam"}, 100)
            self.write(root, "HEAD_b.json", {"project":"business","campaign":"newer"}, 300)
            self.assertEqual(current_head(root, project="family", campaign="adam"), wanted)

    def test_engine_recovers_self_contained_campaign_snapshot(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "data").mkdir()
            self.write(root, "HEAD_snapshot.json", {"project":"family","campaign":"adam","state":"APPROVED","next_action":"archive"}, 300)
            result = EngineV26(root).recover()
            self.assertTrue(result.ok)
            self.assertEqual(result.data["recovery_mode"], "CAMPAIGN_STATE_SNAPSHOT")
            self.assertEqual(result.data["campaign"], "adam")


if __name__ == "__main__":
    unittest.main()

