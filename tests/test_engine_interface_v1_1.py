from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.engine_api_v1_1 import EngineV11


class EngineV11Tests(unittest.TestCase):
    def test_latest_versioned_head_is_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "memory").mkdir()
            (root / "docs").mkdir()
            (root / "data").mkdir()
            (root / "memory/base.json").write_text("{}", encoding="utf-8")
            (root / "docs/stage.md").write_text("stage", encoding="utf-8")
            base = {
                "base_state": "memory/base.json",
                "state_overlays_in_order": [],
                "active_decisions": [],
                "current_stage_summary": "docs/stage.md",
                "current_audit": {},
                "next_stage_after_owner_acceptance": "old"
            }
            (root / "memory/HEAD.json").write_text(json.dumps(base), encoding="utf-8")
            base["next_stage_after_owner_acceptance"] = "new"
            (root / "memory/HEAD_9999.json").write_text(json.dumps(base), encoding="utf-8")
            result = EngineV11(root).recover()
            self.assertTrue(result.ok)
            self.assertEqual(result.engine_api_version, "1.1")
            self.assertEqual(result.next_action, "new")
            self.assertEqual(result.data["head"], "memory/HEAD_9999.json")


if __name__ == "__main__":
    unittest.main()

