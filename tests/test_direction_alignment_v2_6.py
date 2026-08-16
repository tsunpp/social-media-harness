from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.direction_alignment_v2_6 import validate_alignment, validate_narrative_options_alignment
from app.direction_contract_v2_6 import confirm_contract


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class DirectionAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        draft = {"schema_version": 1, "campaign": "demo", "status": "DRAFT_AWAITING_OWNER", "core_intent": {"statement": "process"}, "audience": {"primary": "viewer"}, "desired_viewer_shift": {"statement": "understand"}, "creative_center": {"statement": "process"}, "tone": {"priority": "authentic"}, "anti_direction": ["generic ad"], "success_tests": ["same shift"], "unresolved_owner_decisions": [], "source_hashes": {}}
        self.confirmed = confirm_contract(self.root, "demo", dump(self.root / "draft.json", draft), "owner")

    def tearDown(self):
        self.temp.cleanup()

    def alignment(self, **overrides):
        value = {"direction_contract_hash": self.confirmed["contract_hash"], "core_intent_supported": True, "audience_fit": True, "viewer_shift_supported": True, "creative_center_preserved": True, "tone_fit": True, "anti_direction_triggered": False, "unsupported_promises": []}
        value.update(overrides)
        return {"direction_alignment": value}

    def test_pass_is_bound_to_active_hash(self):
        self.assertEqual(validate_alignment(self.root, "demo", "cover", self.alignment())["status"], "PASS")

    def test_core_drift_requires_owner_reconfirmation(self):
        result = validate_alignment(self.root, "demo", "master", self.alignment(creative_center_preserved=False))
        self.assertEqual(result["status"], "OWNER_RECONFIRMATION_REQUIRED")

    def test_all_three_options_must_align(self):
        plan = {"options": [self.alignment() for _ in range(3)]}
        self.assertEqual(validate_narrative_options_alignment(self.root, "demo", plan)["option_count"], 3)
        plan["options"][2] = self.alignment(anti_direction_triggered=True)
        with self.assertRaisesRegex(ValueError, "diverge"):
            validate_narrative_options_alignment(self.root, "demo", plan)


if __name__ == "__main__":
    unittest.main()
