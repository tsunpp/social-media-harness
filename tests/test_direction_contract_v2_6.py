from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.direction_contract_v2_6 import confirm_contract, contract_hash, file_hash, invalidate_contract, validate_confirmation, validate_direction_contract


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def contract(campaign="demo", source_hashes=None):
    return {
        "schema_version": 1,
        "campaign": campaign,
        "status": "DRAFT_AWAITING_OWNER",
        "core_intent": {"statement": "Show authentic process"},
        "audience": {"primary": "quality-conscious viewers"},
        "desired_viewer_shift": {"statement": "from result to credible process"},
        "creative_center": {"statement": "process is protagonist"},
        "tone": {"priority": "restrained authenticity"},
        "must_communicate": [{"statement": "Real process", "evidence_refs": ["FACT-1"]}],
        "must_not_imply": ["unverified efficacy"],
        "anti_direction": ["generic product advertisement"],
        "success_tests": ["all options create the same viewer shift"],
        "open_freedoms": ["shot rhythm"],
        "unresolved_owner_decisions": [],
        "self_adversarial_check": {"strongest_countercase": "Product-led may convert faster", "disposition": "Reject"},
        "source_hashes": source_hashes or {"source.json": "sha256:" + "0" * 64},
    }


class DirectionContractTests(unittest.TestCase):
    def test_hash_is_canonical_and_ignores_hash_field(self):
        value = contract()
        digest = contract_hash(value)
        value["contract_hash"] = digest
        self.assertEqual(contract_hash(value), digest)
        self.assertEqual(validate_direction_contract(value)["status"], "PASS")

    def test_confirm_is_owner_only_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = dump(root / "source.json", {"fact": True})
            path = dump(root / "draft.json", contract(source_hashes={"source.json": file_hash(source)}))
            with self.assertRaisesRegex(ValueError, "Only owner"):
                confirm_contract(root, "demo", path, "codex")
            result = confirm_contract(root, "demo", path, "owner")
            self.assertEqual(result["status"], "DIRECTION_CONFIRMED")
            self.assertFalse(result["publication_authorized"])
            self.assertEqual(validate_confirmation(root, "demo")["status"], "PASS")
            self.assertTrue((root / result["memory_head"]).is_file())

    def test_confirmed_contract_cannot_have_open_decisions(self):
        value = contract()
        value["status"] = "OWNER_CONFIRMED"
        value["unresolved_owner_decisions"] = ["tone"]
        with self.assertRaisesRegex(ValueError, "unresolved"):
            validate_direction_contract(value)

    def test_invalidation_preserves_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = dump(root / "source.json", {"fact": True})
            confirm_contract(root, "demo", dump(root / "draft.json", contract(source_hashes={"source.json": file_hash(source)})), "owner")
            result = invalidate_contract(root, "demo", "Audience changed", "owner")
            self.assertEqual(result["status"], "DIRECTION_ALIGNMENT_PENDING")
            self.assertTrue(any((root / "campaigns/demo/direction/history").iterdir()))
            self.assertFalse((root / "campaigns/demo/direction/direction-contract.json").exists())


if __name__ == "__main__":
    unittest.main()
