from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.engine_api import ENGINE_API_VERSION, Engine


class EngineInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "memory").mkdir(parents=True)
        (self.root / "docs").mkdir()
        (self.root / "campaigns").mkdir()
        (self.root / "data").mkdir()
        (self.root / "docs" / "vision.md").write_text("vision", encoding="utf-8")
        (self.root / "memory" / "base.json").write_text('{"stage":"base"}', encoding="utf-8")
        (self.root / "memory" / "overlay.json").write_text('{"stage":"latest"}', encoding="utf-8")
        (self.root / "memory" / "decision.json").write_text('{"status":"ACTIVE"}', encoding="utf-8")
        (self.root / "memory" / "HEAD.json").write_text(
            json.dumps({
                "base_state": "memory/base.json",
                "state_overlays_in_order": ["memory/overlay.json"],
                "active_decisions": ["memory/decision.json"],
                "superseded_records": [],
                "current_stage_summary": "docs/vision.md",
                "current_audit": {},
                "next_stage_after_owner_acceptance": "next-stage",
            }),
            encoding="utf-8",
        )
        self.engine = Engine(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_every_result_has_stable_envelope(self):
        result = self.engine.capabilities().to_dict()
        self.assertTrue(result["ok"])
        self.assertEqual(result["engine_api_version"], ENGINE_API_VERSION)
        self.assertTrue(result["run_id"])
        self.assertIn("status", result)
        self.assertIn("errors", result)

    def test_recovery_loads_head_chain(self):
        result = self.engine.recover()
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "RECOVERED")
        self.assertEqual(result.next_action, "next-stage")
        self.assertEqual(result.data["overlays"][0]["stage"], "latest")

    def test_recovery_fails_on_missing_reference(self):
        head = json.loads((self.root / "memory" / "HEAD.json").read_text(encoding="utf-8"))
        head["active_decisions"].append("memory/missing.json")
        (self.root / "memory" / "HEAD.json").write_text(json.dumps(head), encoding="utf-8")
        result = self.engine.recover()
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "RECOVERY_REFERENCE_MISSING")

    def test_campaign_lifecycle_uses_existing_state_engine(self):
        created = self.engine.start_campaign("second-campaign", "Second Campaign")
        self.assertTrue(created.ok)
        advanced = self.engine.advance("second-campaign", "INGESTED", "test", "assets ready")
        self.assertTrue(advanced.ok)
        status = self.engine.campaign_status("second-campaign")
        self.assertEqual(status.data["campaign"]["state"], "INGESTED")

    def test_unimplemented_executor_is_explicit(self):
        result = self.engine.unavailable("plan")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, "NOT_IMPLEMENTED")
        self.assertEqual(result.errors[0]["code"], "NOT_IMPLEMENTED")


if __name__ == "__main__":
    unittest.main()

