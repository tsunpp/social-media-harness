from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.openclaw_publication_handoff import build_openclaw_handoff, prepare_openclaw_handoff, verify_openclaw_handoff


def write(path: Path, value: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode())


def archive(root: Path, archive_id: str = "SM0813202601") -> None:
    base = root / "archive" / archive_id
    files = {
        "platforms/instagram-reels/reel.mp4": b"ig", "platforms/instagram-reels/cover.jpg": b"c",
        "platforms/instagram-reels/caption.txt": b"caption", "platforms/youtube-shorts/short.mp4": b"yt",
        "platforms/youtube-shorts/thumbnail.jpg": b"t", "platforms/youtube-shorts/title.txt": b"title",
        "platforms/youtube-shorts/description.txt": b"description",
    }
    import hashlib
    for name, body in files.items(): write(base / name, body)
    checksums = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
    write(base / "manifest.json", json.dumps({"schema_version": 2, "archive_id": archive_id, "status": "READY_NOT_PUBLISHED", "publishing_authorized": False, "checksums": checksums}))


class OpenClawHandoffTests(unittest.TestCase):
    def test_build_is_locked_and_verifiable(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); archive(root)
            result = build_openclaw_handoff(root, "SM0813202601")
            self.assertEqual(result["status"], "OPENCLAW_HANDOFF_READY")
            self.assertFalse(result["publishing_authorized"])
            task = json.loads(Path(result["handoff"]).read_text())
            self.assertFalse(task["safety"]["openclaw_execution_permitted"])
            self.assertEqual(verify_openclaw_handoff(root, "SM0813202601")["status"], "PASS")

    def test_build_is_idempotent(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); archive(root)
            build_openclaw_handoff(root, "SM0813202601")
            self.assertTrue(build_openclaw_handoff(root, "SM0813202601")["idempotent"])

    def test_tampered_archive_is_blocked(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); archive(root)
            write(root / "archive/SM0813202601/platforms/instagram-reels/reel.mp4", b"changed")
            with self.assertRaisesRegex(ValueError, "verification failed"):
                prepare_openclaw_handoff(root, "SM0813202601")

    def test_archive_with_publication_lock_removed_is_blocked(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); archive(root)
            path = root / "archive/SM0813202601/manifest.json"
            data = json.loads(path.read_text()); data["publishing_authorized"] = True; write(path, json.dumps(data))
            with self.assertRaisesRegex(ValueError, "verification failed|lock"):
                prepare_openclaw_handoff(root, "SM0813202601")


if __name__ == "__main__": unittest.main()
