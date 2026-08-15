from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.head_discovery import current_head, head_chain


class HeadDiscoveryTests(unittest.TestCase):
    def test_chain_leaf_beats_lexicographically_later_old_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "memory").mkdir()
            gate = "memory/HEAD_2026-08-11_planning-privacy-gate.json"
            complete = "memory/HEAD_2026-08-11_planning-complete.json"
            (root / gate).write_text(json.dumps({"updated_at": "2026-08-11"}), encoding="utf-8")
            (root / complete).write_text(json.dumps({"updated_at": "2026-08-11", "previous_head": gate}), encoding="utf-8")
            self.assertEqual(current_head(root), root / complete)
            self.assertEqual([path for path, _ in head_chain(root)], [root / gate, root / complete])


if __name__ == "__main__":
    unittest.main()
