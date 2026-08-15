from __future__ import annotations

import shutil

from app.engine_api_v2_3 import EngineV23
from app.four_agent_review_panel import aggregate_panel, evidence_contract
from app.adversarial_review import adversarial_review_contract, adjudicate_challenges, validate_adversarial_review
from app.openclaw_publication_handoff import build_openclaw_handoff, prepare_openclaw_handoff, verify_openclaw_handoff
from app.completion_gate_v2_5 import validate_completion_gate
from app.bgm_orchestrator_v2_5 import adjudicate_bgm_reviews, finalize_dual_master, prepare_bgm_contract, review_contract
from app.final_package_executor import build_final_package, prepare_final_package, verify_final_package
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.campaign_recovery_v2_5 import register_existing_campaign
from app.visual_style_profiles import public_style_contract, resolve_visual_style
from app.typography_director import create_contract as create_typography_contract, write_contract as write_typography_contract
from app.review_transfer_authorization import resolve_review_transfer_authorization

ENGINE_API_VERSION = "2.5"


class EngineV25(EngineV23):
    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["four_agent_review_panel"] = {
            "implemented": True,
            "reviewers": ["claude", "minimax", "kimi"],
            "producer_and_adjudicator": "codex",
            "decision_method": "modality_authority_not_majority_vote",
            "evidence_contract": evidence_contract(),
            "owner_publication_gate": True,
            "frozen_predecessor": "2.3",
        }
        result.data["capabilities"]["deepseek_adversarial_review"] = {
            "implemented": True,
            "optional": True,
            "reviewer": "deepseek_text_critic",
            "not_a_panel_vote": True,
            "contract": adversarial_review_contract(),
            "frozen_predecessor": "2.3",
        }
        result.data["capabilities"]["openclaw_publication_handoff"] = {
            "implemented": True,
            "transactional": True,
            "idempotent": True,
            "dispatches_openclaw": False,
            "publishes": False,
            "owner_publication_gate": True,
            "requires_verified_archive": True,
            "platforms": ["instagram_reels", "youtube_shorts"],
        }
        result.data["capabilities"]["mandatory_completion_gate"] = {
            "implemented": True,
            "cannot_finalize_without_registered_campaign": True,
            "sound_strategy_required": True,
            "silent_requires_explicit_owner_no_bgm": True,
            "bgm_requires_three_candidate_stage_and_owner_listening": True,
            "segmented_workflow_evidence_required": True,
            "four_agent_panel_required": True,
        }
        result.data["capabilities"]["bgm_stage"] = {
            "implemented": True,
            "mandatory_sound_strategy": True,
            "candidate_count": 3,
            "silent_master_immutable": True,
            "silent_requires_owner_decision": True,
            "owner_listening_gate": True,
        }
        result.data["capabilities"]["opt_in_visual_style_profiles"] = {
            "implemented": True,
            "available": ["vogue-derived-editorial"],
            "brief_field": "visual_style_profile",
            "default": "vogue-derived-editorial",
            "automatic_on_every_campaign": True,
            "explicit_opt_out": "none",
            "originality_safe_abstract_principles_only": True,
        }
        result.data["capabilities"]["typography_director"] = {
            "implemented": True,
            "automatic_palette_from_campaign_pixels": True,
            "shared_targets": ["video", "post", "cover"],
            "structured_contract": "schemas/typography_contract.schema.json",
            "blocks": ["hollow_type", "outlined_display_type", "generic_subtitles", "uniform_catalog_titles", "unbounded_accent_colors"],
            "owner_feedback_persisted": True,
        }
        result.data["capabilities"]["standing_review_transfer_authorization"] = {
            "implemented": True,
            "scope": "cannabis-social-media Campaign review only",
            "recipients": ["claude", "minimax", "kimi-k3"],
            "privacy_and_fact_preflight_required": True,
            "per_transfer_owner_confirmation_required": False,
            "publication_authorized": False,
        }
        return self._stamp(result)

    def review_transfer_authorize(self, project, campaign, recipients, materials, privacy_preflight, fact_preflight):
        command = "review-transfer.authorize"
        return self._stamp(self._guard(command, lambda: self._success(
            command,
            resolve_review_transfer_authorization(
                self.root, project, campaign, recipients, materials, privacy_preflight, fact_preflight
            ),
            status="AUTHORIZED_FOR_SCOPED_REVIEW_TRANSFER",
            next_action="prepare_sanitized_reviewer_evidence",
        )))

    def campaign_visual_style(self, campaign):
        command = "campaign.visual-style"
        return self._stamp(self._guard(command, lambda: self._success(
            command,
            {"campaign": campaign, "visual_style_contract": public_style_contract(resolve_visual_style(self.root, campaign))},
            status="STYLE_RESOLVED",
            next_action="narrative.prepare",
        )))

    def typography_prepare(self, campaign, segments, evidence_images, output=None):
        command = "typography.prepare"
        def operation():
            spec_path = segments if segments.is_absolute() else self.root / segments
            spec = read_json(spec_path)
            items = spec.get("segments", spec.get("typography_segments"))
            if not isinstance(items, list):
                raise ValueError("Typography segment spec requires segments array")
            images = [path if path.is_absolute() else self.root / path for path in evidence_images]
            contract = create_typography_contract(self.root, campaign, items, images)
            target = output or self.root / "campaigns" / campaign / "plans" / "typography-contract.json"
            if not target.is_absolute():
                target = self.root / target
            write_typography_contract(target, contract)
            data = {"campaign": campaign, "contract": str(target.relative_to(self.root)).replace("\\", "/"), "typography": contract}
            return self._success(command, data, status="TYPOGRAPHY_CONTRACT_READY", next_action="render_video_post_or_cover")
        return self._stamp(self._guard(command, operation))

    def register_existing_campaign(self, campaign, title):
        command = "campaign.register-existing"
        return self._stamp(self._guard(command, lambda: self._success(command, register_existing_campaign(self.root, self.db_path, campaign, title), status="REGISTERED_AT_NEW", next_action="campaign.advance")))

    def bgm_prepare(self, campaign, silent_master, final_story_contract, strategy, directions):
        return prepare_bgm_contract(self.root, campaign, silent_master, final_story_contract, strategy, directions)

    def bgm_review_contract(self, candidate_ids):
        return review_contract(candidate_ids)

    def bgm_adjudicate(self, candidate_ids, claude, minimax, kimi):
        return adjudicate_bgm_reviews(candidate_ids, claude, minimax, kimi)

    def bgm_finalize(self, silent_master, selected_mix, destination, expected_silent_sha256, expected_mix_sha256):
        return finalize_dual_master(silent_master, selected_mix, destination, expected_silent_sha256, expected_mix_sha256)

    def final_package(self, spec, build=False):
        command = "final-package.build" if build else "final-package.prepare"
        def operation():
            value = read_json(self.root / spec if not spec.is_absolute() else spec)
            clearance = validate_completion_gate(self.root, self.db_path, value)
            data = build_final_package(self.root, spec) if build else prepare_final_package(self.root, spec)
            if build:
                destination = self.root / "archive" / value["archive_id"]
                credential = destination / "reviews" / "completion-gate-v2-5.json"
                shutil.copy2(clearance["path"], credential)
                manifest_path = destination / "manifest.json"
                manifest = read_json(manifest_path)
                relative = str(credential.relative_to(destination)).replace("\\", "/")
                digest = sha256(credential)
                manifest["checksums"][relative] = digest
                manifest["completion_gate_sha256"] = digest
                manifest["completion_gate"] = relative
                write_json(manifest_path, manifest)
            data["completion_gate"] = clearance
            return self._success(command, data, status=data["status"], next_action=data["next_action"])
        return self._stamp(self._guard(command, operation))

    def final_package_verify(self, archive_id):
        command = "final-package.verify"
        def operation():
            data = verify_final_package(self.root, archive_id)
            if data["status"] != "PASS":
                raise ValueError(f"Final package verification failed: {data}")
            manifest = read_json(self.root / "archive" / archive_id / "manifest.json")
            if not manifest.get("completion_gate_sha256"):
                raise ValueError("Archive lacks Engine 2.5 completion-gate provenance")
            return self._success(command, data, status="VERIFIED_READY_NOT_PUBLISHED", next_action="owner_review_publication_package")
        return self._stamp(self._guard(command, operation))

    def review_panel_aggregate(self, claude, minimax, kimi, **kwargs):
        return aggregate_panel(claude, minimax, kimi, **kwargs)

    def validate_adversarial_review(self, review, evidence_ids):
        validate_adversarial_review(review, set(evidence_ids))
        return True

    def adversarial_adjudicate(self, review, dispositions):
        return adjudicate_challenges(review, dispositions)

    def openclaw_handoff(self, archive_id, platforms=None, build=False):
        command = "openclaw-handoff.build" if build else "openclaw-handoff.prepare"
        def operation():
            from app.archive_naming import locate_archive
            manifest = read_json(locate_archive(self.root, archive_id) / "manifest.json")
            if not manifest.get("completion_gate_sha256"):
                raise ValueError("OpenClaw handoff requires Engine 2.5 completion-gate provenance")
            data = build_openclaw_handoff(self.root, archive_id, platforms) if build else prepare_openclaw_handoff(self.root, archive_id, platforms)
            return self._success(command, data, status=data["status"] if build else "OPENCLAW_HANDOFF_VALIDATED", next_action=data["next_action"])
        return self._stamp(self._guard(command, operation))

    def openclaw_handoff_verify(self, archive_id):
        command = "openclaw-handoff.verify"
        def operation():
            data = verify_openclaw_handoff(self.root, archive_id)
            if data["status"] != "PASS":
                raise ValueError(f"OpenClaw handoff verification failed: {data}")
            next_action = "openclaw_publish_exact_payloads" if data.get("publishing_authorized") else "owner_authorize_openclaw_publication"
            return self._success(command, data, status="OPENCLAW_HANDOFF_VERIFIED", next_action=next_action)
        return self._stamp(self._guard(command, operation))
