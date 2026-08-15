from __future__ import annotations

import unittest
from pathlib import Path

from app.engine_api_v1_4 import EngineV14


class EngineV14Tests(unittest.TestCase):
    def test_relative_plan_path_is_resolved_against_root(self):
        engine = EngineV14(Path.cwd())
        relative = Path("campaigns/example/plans/options.json")
        resolved = engine.root / relative
        self.assertTrue(resolved.is_absolute())
        self.assertEqual(resolved, engine.root / relative)


if __name__ == "__main__":
    unittest.main()

