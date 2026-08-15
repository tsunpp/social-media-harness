from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.assets import media_type_for, orientation_for, sha256_file, scan_assets
from app.database import connect, initialize


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        for directory in ("incoming", "catalog", "thumbnails", "proxies", "keyframes"):
            (self.root / "asset_library" / directory).mkdir(parents=True)
        self.db_path = self.root / "data" / "test.db"
        initialize(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_asset_tables_exist(self):
        with connect(self.db_path) as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        self.assertIn("assets", tables)
        self.assertIn("campaign_assets", tables)

    def test_media_type_and_orientation(self):
        self.assertEqual(media_type_for(Path("sample.MOV")), "video")
        self.assertEqual(media_type_for(Path("sample.HEIC")), "image")
        self.assertEqual(orientation_for(1080, 1920), "portrait")

    def test_hash_is_stable(self):
        path = self.root / "sample.bin"
        path.write_bytes(b"synthetic-sample")
        self.assertEqual(sha256_file(path), sha256_file(path))

    def test_jpeg_catalog_and_thumbnail(self):
        image_path = self.root / "asset_library" / "incoming" / "sample.jpg"
        Image.new("RGB", (1200, 800), "green").save(image_path)
        assets = scan_assets(
            self.root, self.db_path, Path("unused.exe"), generate=True
        )
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["processing_status"], "ready")
        self.assertTrue((self.root / assets[0]["thumbnail_path"]).is_file())
        self.assertTrue(
            (self.root / "asset_library" / "catalog" / "assets.csv").is_file()
        )


if __name__ == "__main__":
    unittest.main()

