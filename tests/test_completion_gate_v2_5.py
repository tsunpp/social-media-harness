from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.campaigns import advance_campaign, create_campaign
from app.completion_gate_v2_5 import REQUIRED_STAGES, validate_completion_gate
from app.image_review_orchestrator import sha256
from app.engine_api_v2_5 import EngineV25


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def receipt(root: Path, name: str, value=None):
    path = dump(root / "evidence" / f"{name}.json", value or {"stage": name})
    return {"status": "PASS", "path": str(path.relative_to(root)), "sha256": sha256(path)}


def fixture(root: Path, mode="no_bgm"):
    db = root / "data/harness.db"
    create_campaign(root, db, "campaign", "Campaign")
    for state in ("INGESTED", "PLANNED", "PLAN_APPROVED", "DRAFT_RENDERED", "UNDER_REVIEW"):
        advance_campaign(db, "campaign", state, "test", state)
    semantic = {
        "facts_locked": {"status": "FACTS_LOCKED"},
        "narrative_panel_cleared": {"status": "NARRATIVE_PANEL_CLEARED", "story_skeleton_count": 3, "reviewer_decisions": {"claude": "PASS", "minimax": "PASS"}},
        "segment_plan_cleared": {"status": "SEGMENTATION_CONSENSUS_REACHED", "reviewer_decisions": {"claude": "PASS", "minimax": "PASS"}},
        "segments_cleared": {"status": "READY_FOR_COMPLETE_VIDEO_DUAL_REVIEW", "all_segments_complete": True, "cumulative_reviews_complete": True},
        "silent_master_cleared": {"status": "SILENT_MASTER_CLEARED", "audio": False, "master_sha256": "A"},
        "cover_set_cleared": {"status": "COVER_SET_CLEARED", "candidate_count": 2, "reviewer_decisions": {"claude": "PASS", "minimax": "PASS"}},
        "platform_variants_cleared": {"status": "PLATFORM_VARIANTS_CLEARED", "platforms": {"instagram_reels": {"path": "ig.mp4", "sha256": "I"}, "youtube_shorts": {"path": "yt.mp4", "sha256": "Y"}}},
    }
    stages = {name: receipt(root, name, semantic.get(name)) for name in REQUIRED_STAGES}
    sound_path = Path(stages["sound_strategy_locked"]["path"])
    dump(root / sound_path, {"mode": mode})
    stages["sound_strategy_locked"]["sha256"] = sha256(root / sound_path)
    panel_path = Path(stages["four_agent_panel_cleared"]["path"])
    dump(root / panel_path, {"panel_version": "2.5", "next_action": "FINAL_CANDIDATE", "reviewer_decisions": {"claude": "PASS", "minimax": "PASS", "kimi": "PASS"}})
    stages["four_agent_panel_cleared"]["sha256"] = sha256(root / panel_path)
    if mode == "no_bgm":
        stages["owner_no_bgm_decision"] = receipt(root, "owner-no-bgm", {"decision": "OWNER_CONFIRMED_NO_BGM", "actor": "owner"})
    else:
        stages["bgm_candidates_cleared"] = receipt(root, "bgm-candidates")
        stages["final_audio_master_cleared"] = receipt(root, "audio-master")
        stages["owner_listening_cleared"] = receipt(root, "owner-listening", {"decision": "OWNER_LISTENING_CLEARED", "actor": "owner"})
    gate = dump(root / "gate.json", {"schema_version": 1, "engine_api_version": "2.5", "campaign": "campaign", "status": "READY_FOR_FINAL_PACKAGE", "stages": stages})
    render = dump(root / "render.json", {"output": {"audio": mode != "no_bgm"}})
    return db, {"campaign": "campaign", "completion_gate": "gate.json", "render_manifest": "render.json"}, gate


class CompletionGateV25Tests(unittest.TestCase):
    def test_no_bgm_requires_explicit_owner_decision(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, gate = fixture(root)
            data = json.loads(gate.read_text()); del data["stages"]["owner_no_bgm_decision"]; dump(gate, data)
            with self.assertRaisesRegex(ValueError, "OWNER_CONFIRMED_NO_BGM"):
                validate_completion_gate(root, db, spec)

    def test_bgm_requires_candidates_audio_master_and_listening(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, gate = fixture(root, "original_bgm")
            data = json.loads(gate.read_text()); del data["stages"]["owner_listening_cleared"]; dump(gate, data)
            with self.assertRaisesRegex(ValueError, "owner_listening_cleared"):
                validate_completion_gate(root, db, spec)

    def test_silent_master_cannot_pass_bgm_strategy(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, _ = fixture(root, "original_bgm"); dump(root / "render.json", {"output": {"audio": False}})
            with self.assertRaisesRegex(ValueError, "silent platform master"):
                validate_completion_gate(root, db, spec)

    def test_three_agent_panel_is_mandatory(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, gate = fixture(root); data = json.loads(gate.read_text())
            panel = root / data["stages"]["four_agent_panel_cleared"]["path"]
            dump(panel, {"panel_version": "2.5", "next_action": "FINAL_CANDIDATE", "reviewer_decisions": {"claude": "PASS", "minimax": "PASS"}})
            data["stages"]["four_agent_panel_cleared"]["sha256"] = sha256(panel); dump(gate, data)
            with self.assertRaisesRegex(ValueError, "Claude, MiniMax, and Kimi"):
                validate_completion_gate(root, db, spec)

    def test_unreviewed_segments_cannot_be_replaced_by_a_pass_label(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, gate = fixture(root); data = json.loads(gate.read_text())
            segment = root / data["stages"]["segments_cleared"]["path"]
            dump(segment, {"status": "READY_FOR_COMPLETE_VIDEO_DUAL_REVIEW", "all_segments_complete": True, "cumulative_reviews_complete": False})
            data["stages"]["segments_cleared"]["sha256"] = sha256(segment); dump(gate, data)
            with self.assertRaisesRegex(ValueError, "cumulative reviews"):
                validate_completion_gate(root, db, spec)

    def test_single_auto_cover_cannot_pass_cover_gate(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, gate = fixture(root); data = json.loads(gate.read_text())
            cover = root / data["stages"]["cover_set_cleared"]["path"]
            dump(cover, {"status": "COVER_SET_CLEARED", "candidate_count": 1, "reviewer_decisions": {"claude": "PASS", "minimax": "PASS"}})
            data["stages"]["cover_set_cleared"]["sha256"] = sha256(cover); dump(gate, data)
            with self.assertRaisesRegex(ValueError, "at least two candidates"):
                validate_completion_gate(root, db, spec)

    def test_registered_campaign_and_all_hashed_stages_pass(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db, spec, _ = fixture(root)
            result = validate_completion_gate(root, db, spec)
            self.assertEqual(result["sound_mode"], "no_bgm")

    def test_missing_completion_gate_is_blocked(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); db = root / "data/harness.db"
            with self.assertRaisesRegex(ValueError, "requires completion_gate"):
                validate_completion_gate(root, db, {"campaign": "campaign", "render_manifest": "render.json"})

    def test_engine_final_package_cannot_use_legacy_bypass(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); spec = dump(root / "spec.json", {"campaign": "campaign"})
            result = EngineV25(root, root / "data/harness.db").final_package(spec)
            self.assertFalse(result.ok)
            self.assertIn("completion_gate", result.errors[0]["message"])

    def test_default_engine_exposes_mandatory_bgm_and_completion_gate(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); (root / "data").mkdir()
            capabilities = EngineV25(root).capabilities().data["capabilities"]
            self.assertTrue(capabilities["bgm_stage"]["mandatory_sound_strategy"])
            self.assertTrue(capabilities["mandatory_completion_gate"]["segmented_workflow_evidence_required"])


if __name__ == "__main__":
    unittest.main()
