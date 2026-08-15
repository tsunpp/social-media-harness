from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.typography_director import build_ffmpeg_filters, create_contract, derive_palette, render_static, validate_contract


ROOT = Path(__file__).resolve().parents[1]


class TypographyDirectorV25Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.image = Path(self.temp.name) / "blue-white.jpg"
        canvas = Image.new("RGB", (240, 240), "#F1F2EE")
        for x in range(80, 220):
            for y in range(45, 205):
                canvas.putpixel((x, y), (25, 112, 154))
        canvas.save(self.image)
        functions = ["hook", "development", "turn", "reveal", "resolution"]
        self.segments = [
            {"segment_id": f"S{index + 1}", "function": function, "index_copy": f"0{index + 1} / STUDY", "display_lines": [function, "FORM"]}
            for index, function in enumerate(functions)
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_palette_is_derived_from_campaign_pixels(self):
        palette = derive_palette([self.image])
        self.assertEqual(palette["source"], "campaign_evidence_pixels")
        self.assertNotEqual(palette["dominant_ink"], "#000000")
        self.assertEqual(palette["accent_limit"], 1)

    def test_contract_varies_axes_and_reserves_one_accent(self):
        contract = create_contract(ROOT, "campaign", self.segments, [self.image])
        self.assertEqual(contract["validation"]["status"], "PASS")
        self.assertEqual(contract["shared_targets"], ["video", "post", "cover"])
        self.assertGreater(len({item["layout"]["axis"] for item in contract["segments"]}), 1)
        self.assertEqual(sum(item["uses_accent"] for item in contract["segments"]), 1)

    def test_hollow_or_outline_type_is_blocked(self):
        contract = create_contract(ROOT, "campaign", self.segments, [self.image])
        contract["segments"][0]["outline_width"] = 2
        with self.assertRaisesRegex(ValueError, "outlined"):
            validate_contract(contract)

    def test_ffmpeg_filters_are_solid_and_contract_driven(self):
        contract = create_contract(ROOT, "campaign", self.segments, [self.image])
        filters = build_ffmpeg_filters(contract, "S1", 3.6)
        combined = ",".join(filters)
        self.assertIn("fontcolor=0x", combined)
        self.assertIn("borderw=0", combined)
        self.assertNotIn("shadowcolor", combined)

    def test_same_contract_renders_post_and_cover(self):
        contract = create_contract(ROOT, "campaign", self.segments, [self.image])
        post = Path(self.temp.name) / "post.jpg"
        cover = Path(self.temp.name) / "cover.jpg"
        render_static(self.image, post, contract, "S1", target="post", size=(1080, 1350))
        render_static(self.image, cover, contract, "S5", target="cover", size=(1080, 1920))
        with Image.open(post) as post_image, Image.open(cover) as cover_image:
            self.assertEqual(post_image.size, (1080, 1350))
            self.assertEqual(cover_image.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
