from __future__ import annotations

import json
import unittest
from pathlib import Path


class ComfyUIInstanceTests(unittest.TestCase):
    def test_two_instances_are_explicit_and_never_fallback(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / "config/comfyui_instances.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(set(data["instances"]), {"comfyui_aki", "comfyui_standard"})
        self.assertFalse(data["routing_policy"]["allow_cross_instance_fallback"])
        self.assertEqual(data["capability_routes"]["minimax_h3_i2v"], "comfyui_aki")
        self.assertEqual(data["instances"]["comfyui_aki"]["base_url"], "http://127.0.0.1:8189")
        self.assertEqual(data["instances"]["comfyui_standard"]["base_url"], "http://127.0.0.1:8188")


if __name__ == "__main__":
    unittest.main()
