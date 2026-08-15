from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.visual_style_profiles import (
    resolve_visual_style,
    validate_generation_prompt,
    validate_narrative_style_contract,
    validate_segment_style_contract,
)


PROFILE_SOURCE = Path(__file__).resolve().parents[1] / "config" / "visual_styles" / "vogue-derived-editorial.json"


class VisualStyleProfilesV25Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "campaigns" / "styled").mkdir(parents=True)
        (self.root / "campaigns" / "default").mkdir(parents=True)
        (self.root / "config" / "visual_styles").mkdir(parents=True)
        (self.root / "config" / "visual_styles" / PROFILE_SOURCE.name).write_bytes(PROFILE_SOURCE.read_bytes())
        defaults = Path(__file__).resolve().parents[1] / "config" / "visual_style_defaults.json"
        (self.root / "config" / "visual_style_defaults.json").write_bytes(defaults.read_bytes())
        self._write_brief("styled", {"visual_style_profile": "vogue-derived-editorial"})
        self._write_brief("default", {"title": "Default behavior"})
        (self.root / "campaigns" / "disabled").mkdir(parents=True)
        self._write_brief("disabled", {"visual_style_profile": "none"})
        (self.root / "campaigns" / "legacy-yaml").mkdir(parents=True)
        (self.root / "campaigns" / "legacy-yaml" / "brief.yaml").write_text(
            "schema_version: 1\ntitle: Legacy YAML\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write_brief(self, campaign, value):
        (self.root / "campaigns" / campaign / "brief.yaml").write_text(json.dumps(value), encoding="utf-8")

    def test_profile_is_automatic_with_explicit_opt_out(self):
        self.assertEqual(resolve_visual_style(self.root, "default")["id"], "vogue-derived-editorial")
        self.assertEqual(resolve_visual_style(self.root, "styled")["id"], "vogue-derived-editorial")
        self.assertEqual(resolve_visual_style(self.root, "legacy-yaml")["id"], "vogue-derived-editorial")
        self.assertIsNone(resolve_visual_style(self.root, "disabled"))

    def test_explicitly_disabled_campaign_prompt_behavior_is_unchanged(self):
        validate_generation_prompt("Vogue style portrait photographed by Tim Walker", None)

    def test_selected_profile_rejects_identifiable_imitation_language(self):
        profile = resolve_visual_style(self.root, "styled")
        with self.assertRaisesRegex(ValueError, "abstract visual principles only"):
            validate_generation_prompt("Make this Vogue style, photographed by Tim Walker", profile)
        validate_generation_prompt(
            "Decisive subject hierarchy, sculptural silhouette, restrained palette, shaped falloff",
            profile,
        )

    def test_typography_policy_prohibits_hollow_display_type(self):
        profile = resolve_visual_style(self.root, "styled")
        policy = profile["typography_policy"]
        self.assertTrue(policy["solid_fill_required"])
        self.assertTrue(policy["outline_or_hollow_display_type_prohibited"])
        self.assertGreaterEqual(policy["minimum_vertical_1080p_display_size_px"], 64)

    def test_all_three_story_skeletons_require_style_contract(self):
        profile = resolve_visual_style(self.root, "styled")
        required = profile["story_skeleton_contract"]["required_fields"]
        plan = {"options": [{"id": option, "visual_style_contract": {key: "intent" for key in required}} for option in "ABC"]}
        validate_narrative_style_contract(plan, profile)
        del plan["options"][1]["visual_style_contract"][required[0]]
        with self.assertRaisesRegex(ValueError, "Option B"):
            validate_narrative_style_contract(plan, profile)

    def test_selected_segments_require_editorial_contract(self):
        profile = resolve_visual_style(self.root, "styled")
        required = profile["segment_contract"]["required_fields"]
        plan = {
            "selected_scheme": "S1",
            "candidate_schemes": [{"scheme_id": "S1", "segments": [
                {"segment_id": "01", "visual_style_contract": {key: "intent" for key in required}}
            ]}],
        }
        validate_segment_style_contract(plan, profile)
        del plan["candidate_schemes"][0]["segments"][0]["visual_style_contract"][required[0]]
        with self.assertRaisesRegex(ValueError, "Segment 01"):
            validate_segment_style_contract(plan, profile)


if __name__ == "__main__":
    unittest.main()
