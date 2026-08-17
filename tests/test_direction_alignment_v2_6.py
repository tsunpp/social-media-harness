from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.direction_alignment_v2_6 import validate_alignment, validate_narrative_options_alignment
from app.direction_contract_v2_6 import confirm_contract, file_hash
from app.engine_api_v2_6 import EngineV26


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class DirectionAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = dump(self.root / "source.json", {"fact": True})
        draft = {"schema_version": 1, "campaign": "demo", "status": "DRAFT_AWAITING_OWNER", "core_intent": {"statement": "process"}, "audience": {"primary": "viewer"}, "desired_viewer_shift": {"statement": "understand"}, "creative_center": {"statement": "process"}, "tone": {"priority": "authentic"}, "must_communicate": [{"statement": "process", "evidence_refs": ["FACT-1"]}], "must_not_imply": [], "anti_direction": ["generic ad"], "success_tests": ["same shift"], "open_freedoms": ["rhythm"], "unresolved_owner_decisions": [], "self_adversarial_check": {"strongest_countercase": "product-led", "disposition": "reject"}, "source_hashes": {"source.json": file_hash(source)}}
        self.confirmed = confirm_contract(self.root, "demo", dump(self.root / "draft.json", draft), "owner")

    def tearDown(self):
        self.temp.cleanup()

    def alignment(self, **overrides):
        value = {"direction_contract_hash": self.confirmed["contract_hash"], "core_intent": "process", "audience": "viewer", "viewer_shift": "understand", "creative_center": "process", "tone": "authentic", "promises": ["process"], "anti_direction_hits": []}
        value.update(overrides)
        return {"direction_trace": value}

    def test_pass_is_bound_to_active_hash(self):
        self.assertEqual(validate_alignment(self.root, "demo", "cover", self.alignment())["status"], "PASS")

    def test_core_drift_requires_owner_reconfirmation(self):
        result = validate_alignment(self.root, "demo", "master", self.alignment(creative_center="product"))
        self.assertEqual(result["status"], "OWNER_RECONFIRMATION_REQUIRED")
        self.assertTrue((self.root / result["report_path"]).is_file())

    def test_engine_api_surfaces_alignment_failure(self):
        artifact = dump(self.root / "artifact.json", self.alignment(creative_center="product"))
        result = EngineV26(self.root).direction_validate("p", "demo", "master", artifact)
        self.assertFalse(result.ok)
        self.assertEqual(result.status, "OWNER_RECONFIRMATION_REQUIRED")
        self.assertEqual(result.data["status"], "OWNER_RECONFIRMATION_REQUIRED")

    def test_all_three_options_must_align(self):
        plan = {"options": [self.alignment() for _ in range(3)]}
        self.assertEqual(validate_narrative_options_alignment(self.root, "demo", plan)["option_count"], 3)
        plan["options"][2] = self.alignment(anti_direction_hits=["generic ad"])
        with self.assertRaisesRegex(ValueError, "diverge"):
            validate_narrative_options_alignment(self.root, "demo", plan)


if __name__ == "__main__":
    unittest.main()
