from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.archive_manifest_v2_6 import validate_archive_manifest
from app.audio_capability_v2_6 import resolve_audio_authority
from app.authorization_matrix_v2_6 import resolve_authorization
from app.contract_consistency_v2_6 import validate_final_contract
from app.engine_api_v2_6 import EngineV26
from app.image_review_orchestrator import sha256
from app.panel_clearance_v2_6 import validate_panel_clearance
from app.platform_profiles_v2_6 import validate_platform_output
from app.final_package_executor_v2_6 import build_final_package_v2_6, verify_final_package_v2_6


ROOT = Path(__file__).resolve().parents[1]


def dump(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


class EngineV26Tests(unittest.TestCase):
    def test_capabilities_expose_all_five_upgrades(self):
        capabilities = EngineV26(ROOT).capabilities().data["capabilities"]
        for name in ("persistent_authorization_matrix", "platform_profiles", "archive_manifest_v3", "final_contract_consistency_gate", "audio_authority_registry", "resumable_four_agent_review"):
            self.assertTrue(capabilities[name]["implemented"])

    def test_family_matrix_remembers_all_three_reviewers_for_identifiable_family_media(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            matrix = {
                "status": "ACTIVE",
                "recipients": {
                    name: {
                        "status": "AUTHORIZED",
                        "allowed_materials": ["rendered_video"],
                        "identifiable_people_allowed": True,
                        "metadata_stripping_required": True,
                    }
                    for name in ("claude", "minimax", "kimi-k3")
                },
            }
            dump(root / "projects" / "family-social" / "decisions" / "review-authorization-matrix-v2-6.json", matrix)
            result = resolve_authorization(root, "family-social", "campaign", "claude", ["rendered_video"], contains_identifiable_people=True, metadata_stripped=True, privacy_preflight="PASS")
            self.assertFalse(result["per_transfer_owner_confirmation_required"])
            kimi = resolve_authorization(root, "family-social", "campaign", "kimi-k3", ["rendered_video"], contains_identifiable_people=True, metadata_stripped=True, privacy_preflight="PASS")
            self.assertFalse(kimi["per_transfer_owner_confirmation_required"])

    def test_wechat_accepts_adam_delivery_shape(self):
        result = validate_platform_output(ROOT, "wechat_channels", {"resolution": "720x1280", "duration_seconds": 37.65, "color": "SDR BT.709"}, {"master": "x", "cover": "x", "caption": "x"})
        self.assertEqual(result["status"], "PASS")

    def test_audio_input_does_not_imply_listening_authority(self):
        minimax = resolve_audio_authority(ROOT, "minimax", "bgm_quality")
        owner = resolve_audio_authority(ROOT, "owner", "bgm_quality")
        self.assertFalse(minimax["validated"]); self.assertTrue(minimax["owner_listening_required"])
        self.assertTrue(owner["validated"])

    def test_privacy_adaptive_panel_records_kimi_skip_without_fake_pass(self):
        result = validate_panel_clearance({"panel_version": "2.6", "next_action": "FINAL_CANDIDATE", "reviewers": {
            "claude": {"active": True, "decision": "PASS", "evidence_complete": True},
            "minimax": {"active": True, "decision": "PASS", "evidence_complete": True},
            "kimi": {"active": False, "decision": "SKIPPED", "reason": "PRIVACY_BOUNDARY"},
        }})
        self.assertEqual(result["inactive_reviewers"], ["kimi"])

    def test_contract_consistency_is_hash_bound(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            master = root / "master.mp4"; master.write_bytes(b"video")
            dump(root / "contract.json", {"final_duration_seconds": 37.65, "audio": {"bgm_primary": True}, "publication_authorized": False})
            dump(root / "render.json", {"output": {"duration_seconds": 37.65, "audio": True}, "master_sha256": sha256(master)})
            dump(root / "copy.json", {"platform": "wechat_channels", "publishing_authorized": False})
            result = validate_final_contract(root, {"final_story_contract": "contract.json", "render_manifest": "render.json", "master_video": "master.mp4", "publishing_copy": "copy.json", "platform": "wechat_channels"})
            self.assertEqual(result["status"], "PASS")
            dump(root / "render.json", {"output": {"duration_seconds": 30, "audio": True}, "master_sha256": sha256(master)})
            with self.assertRaisesRegex(ValueError, "duration"):
                validate_final_contract(root, {"final_story_contract": "contract.json", "render_manifest": "render.json", "master_video": "master.mp4", "publishing_copy": "copy.json", "platform": "wechat_channels"})

    def test_archive_manifest_v3_verifies_assets(self):
        with tempfile.TemporaryDirectory() as value:
            archive = Path(value); master = archive / "media" / "master.mp4"; master.parent.mkdir(); master.write_bytes(b"video")
            contract = archive / "contract.json"; contract.write_bytes(b"{}")
            assets = [{"path": str(p.relative_to(archive)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in (master, contract)]
            manifest = {"schema_version": 3, "archive_id": "SM0814202601", "display_name": "test", "campaign": "c", "created_at": "2026-08-14T00:00:00-07:00", "status": "APPROVED_NOT_PUBLISHED", "platforms": ["wechat_channels"], "master": "media/master.mp4", "assets": assets, "story_contract": "contract.json", "reviews": [], "owner_approval": "approval.json", "publishing_authorized": False, "publication_gate": "OWNER_APPROVAL_REQUIRED"}
            self.assertEqual(validate_archive_manifest(archive, manifest)["status"], "PASS")

    def test_wechat_final_package_builds_transactionally_with_schema_v3(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "config").mkdir(); (root / "archive").mkdir()
            (root / "config/platform_profiles_v2_6.json").write_bytes((ROOT / "config/platform_profiles_v2_6.json").read_bytes())
            master = root / "master.mp4"; master.write_bytes(b"video")
            dump(root / "contract.json", {"final_duration_seconds": 37.65, "audio": {"bgm_primary": True}, "publication_authorized": False})
            dump(root / "render.json", {"output": {"resolution": "720x1280", "duration_seconds": 37.65, "audio": True, "color": "SDR BT.709"}, "master_sha256": sha256(master)})
            dump(root / "copy.json", {"platform": "wechat_channels", "caption": "caption", "publishing_authorized": False})
            (root / "cover.jpg").write_bytes(b"cover")
            dump(root / "review.json", {"next_action": "FINAL_CANDIDATE", "blocking_issues": []})
            dump(root / "technical.json", {"status": "PASS"})
            dump(root / "approval.json", {"owner_decision": "APPROVED_FINAL"})
            spec = {"archive_id": "SM0814202601", "display_name": "Adam", "campaign": "adam", "platform": "wechat_channels", "master_video": "master.mp4", "render_manifest": "render.json", "publishing_copy": "copy.json", "cover": "cover.jpg", "final_story_contract": "contract.json", "final_review": "review.json", "technical_gate": "technical.json", "owner_approval": "approval.json", "publishing_authorized": False}
            spec_path = dump(root / "spec.json", spec)
            built = build_final_package_v2_6(root, spec_path)
            self.assertEqual(built["status"], "APPROVED_NOT_PUBLISHED")
            self.assertEqual(verify_final_package_v2_6(root, built["archive_id"])["status"], "PASS")
            self.assertFalse((root / "archive/.SM0814202601.staging").exists())


if __name__ == "__main__":
    unittest.main()
