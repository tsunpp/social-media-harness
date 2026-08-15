from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.engine_api_v1_8 import EngineV18
from app.video_generation_backends import execute_generation


class VideoGenerationBackendTests(unittest.TestCase):
    def test_engine_declares_only_two_generation_routes(self):
        value = EngineV18(Path(".")).capabilities().data["capabilities"]["video_generation"]
        self.assertEqual(value["executable_backends"], ["comfyui_aki:minimax_h3_i2v", "minimax_h3_api"])
        self.assertFalse(value["standard_comfyui_enabled"])

    @patch("app.video_generation_backends.write_json")
    @patch("app.video_generation_backends.run_comfyui_aki")
    def test_aki_dispatch_never_uses_standard(self, run, write):
        run.return_value = {"backend": "comfyui_aki:minimax_h3_i2v"}
        result = execute_generation(Path("."), {"campaign": "c", "job_id": "j", "source_sha256": "h", "source": "s.png", "prompt": "p", "parameters": {"duration": 5}, "backend": "comfyui_aki:minimax_h3_i2v", "output": "out/a.mp4"})
        self.assertEqual(result["backend"], "comfyui_aki:minimax_h3_i2v")
        run.assert_called_once()
        self.assertEqual(result["next_action"], "video.pipeline.prepare")

    @patch("app.video_generation_backends.write_json")
    @patch("app.video_generation_backends.run_minimax_h3_api")
    def test_cloud_dispatch(self, run, write):
        run.return_value = {"backend": "minimax_h3_api"}
        result = execute_generation(Path("."), {"campaign": "c", "job_id": "j", "source_sha256": "h", "source": "s.png", "prompt": "p", "parameters": {"duration": 5}, "backend": "minimax_h3_api", "output": "out/b.mp4"})
        self.assertEqual(result["backend"], "minimax_h3_api")
        run.assert_called_once()
        self.assertEqual(result["next_action"], "video.pipeline.prepare")


if __name__ == "__main__":
    unittest.main()
