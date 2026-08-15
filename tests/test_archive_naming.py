import tempfile
import unittest
from pathlib import Path

from app.archive_naming import archive_name, locate_archive, validate_content_slug


class ArchiveNamingTests(unittest.TestCase):
    def test_readable_name_preserves_canonical_id(self):
        self.assertEqual(archive_name("SM0813202601", "sample-product-process-b"), "SM0813202601--sample-product-process-b")

    def test_mutable_status_word_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "status"):
            validate_content_slug("sample-ready")

    def test_locator_supports_legacy_and_readable_directories(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); (root / "archive/SM0812202601").mkdir(parents=True)
            (root / "archive/SM0813202601--sample-product-process-b").mkdir()
            self.assertEqual(locate_archive(root, "SM0812202601").name, "SM0812202601")
            self.assertEqual(locate_archive(root, "SM0813202601").name, "SM0813202601--sample-product-process-b")
