from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.engine_api_v2_0 import EngineV20
from app.final_package_executor import allocate_archive_id, build_final_package, prepare_final_package, verify_final_package


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root: Path, archive_id="SM0811202601") -> Path:
    (root / "master.mp4").write_bytes(b"video")
    (root / "cover.jpg").write_bytes(b"cover")
    dump(root / "render.json", {"output": {"resolution": "1080x1920", "duration_seconds": 21, "color": "SDR BT.709"}})
    dump(root / "review.json", {"next_action": "FINAL_CANDIDATE", "reason": "both_independent_reviewers_passed", "blocking_issues": []})
    dump(root / "technical.json", {"status": "PASS"})
    dump(root / "copy.json", {"publishing_authorized": False, "instagram": {"caption": "caption", "hashtags": ["#one"], "alt_text": "macro"}, "youtube_shorts": {"title": "title", "description": "description", "hashtags": ["#one"]}, "covers": {"recommended": "cover.jpg"}})
    spec = {"schema_version": 1, "archive_id": archive_id, "display_name": "test", "campaign": "c", "source_version": "v1", "language": "en", "master_video": "master.mp4", "render_manifest": "render.json", "publishing_copy": "copy.json", "covers": ["cover.jpg"], "final_review": "review.json", "technical_gate": "technical.json", "publishing_authorized": False}
    dump(root / "spec.json", spec); return root / "spec.json"


class FinalPackageTests(unittest.TestCase):
    def test_capabilities_keep_owner_gate(self):
        with tempfile.TemporaryDirectory() as d:
            result = EngineV20(Path(d)).capabilities()
            self.assertTrue(result.data["capabilities"]["finalize"]["owner_publication_gate"])
            self.assertEqual(result.engine_api_version, "2.0")

    def test_allocate_uses_next_daily_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / "archive" / "SM0811202601").mkdir(parents=True)
            self.assertEqual(allocate_archive_id(root, date(2026, 8, 11)), "SM0811202602")

    def test_build_and_verify_transactional_package(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); spec = fixture(root)
            self.assertEqual(prepare_final_package(root, spec)["status"], "READY_TO_BUILD_FINAL_PACKAGE")
            result = build_final_package(root, spec)
            self.assertFalse(result["publishing_authorized"])
            self.assertEqual(verify_final_package(root, result["archive_id"])["status"], "PASS")
            self.assertFalse((root / "archive" / ".SM0811202601.staging").exists())

    def test_unpassed_master_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); spec = fixture(root); dump(root / "review.json", {"next_action": "CODEX_ADJUDICATION", "blocking_issues": [{"id": "x"}]})
            with self.assertRaisesRegex(ValueError, "has not passed"):
                prepare_final_package(root, spec)


if __name__ == "__main__": unittest.main()
