from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.engine_api_v1_8 import EngineV18
from app.video_production_orchestrator import privacy_conflicts, prompt_fact_conflicts, validate_job


class VideoProductionTests(unittest.TestCase):
    def test_engine_reports_full_video_pipeline(self):
        with tempfile.TemporaryDirectory() as folder:
            result = EngineV18(Path(folder)).capabilities()
            self.assertTrue(result.data["capabilities"]["video_pipeline"]["implemented"])
            self.assertEqual(result.engine_api_version, "1.8")

    def test_quarantined_pixel_artifact_is_blocked(self):
        job = {"artifacts": [{"artifact_id": "x", "role": "source_image", "path": "AST-PII.jpg"}]}
        policy = {"rules": [{"asset_id": "AST-PII", "external_model_pixels_allowed": False}]}
        self.assertEqual(privacy_conflicts(job, policy)[0]["asset_id"], "AST-PII")

    def test_forbidden_prompt_is_blocked_only_when_included(self):
        context = {"active_decisions": [{"path": "rule.json", "content": {"forbidden_phrases": ["tray"]}}]}
        job = {"artifacts": [{"artifact_id": "x", "included_in_final": True, "prompt": "yellow tray"}]}
        self.assertEqual(prompt_fact_conflicts(job, context)[0]["phrase"], "tray")
        job["artifacts"][0]["status"] = "historical_capability_evidence_only"
        self.assertEqual(prompt_fact_conflicts(job, context), [])

    def test_job_accepts_quality_first_revision_limit_and_artifact_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "video.mp4").write_bytes(b"v")
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            job = {"schema_version": 1, "campaign": "c", "job_id": "j", "version": "v", "output": "video.mp4", "render_manifest": "manifest.json", "backends": {}, "revision_policy": {"auto_revision_limit": 8}, "artifacts": [{"artifact_id": "a", "path": "video.mp4", "backend": "ffmpeg", "role": "rendered_video", "included_in_final": True, "provenance": "source"}]}
            validate_job(root, "c", job)


if __name__ == "__main__":
    unittest.main()
