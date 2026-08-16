from __future__ import annotations

from pathlib import Path

from app.archive_manifest_v2_6 import validate_archive_manifest
from app.audio_capability_v2_6 import resolve_audio_authority
from app.authorization_matrix_v2_6 import resolve_authorization
from app.contract_consistency_v2_6 import validate_final_contract
from app.engine_api_v2_5 import EngineV25
from app.planning_orchestrator import read_json
from app.platform_profiles_v2_6 import load_profiles, validate_platform_output
from app.final_package_executor_v2_6 import build_final_package_v2_6, prepare_final_package_v2_6, verify_final_package_v2_6
from app.review_pipeline_v2_6 import prepare_complete_evidence, run_resumable_panel
from app.head_discovery import current_head


ENGINE_API_VERSION = "2.6"


class EngineV26(EngineV25):
    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        capabilities = result.data["capabilities"]
        capabilities["persistent_authorization_matrix"] = {
            "implemented": True,
            "per_project": True,
            "recipient_and_material_scoped": True,
            "identifiable_people_explicit": True,
            "publication_authorized": False,
        }
        capabilities["platform_profiles"] = {"implemented": True, "profiles": sorted(load_profiles(self.root)["platforms"])}
        capabilities["archive_manifest_v3"] = {"implemented": True, "immutable": True, "schema": "schemas/archive_manifest_v3.schema.json"}
        capabilities["final_contract_consistency_gate"] = {"implemented": True, "hash_bound": True, "blocks_stale_contracts": True}
        capabilities["audio_authority_registry"] = {"implemented": True, "video_input_is_not_audio_authority": True, "owner_listening_fallback": True}
        capabilities["privacy_adaptive_panel"] = {
            "implemented": True,
            "rule": "Only activated, authorized reviewers may receive evidence; inactive modalities are recorded, never fabricated as PASS.",
        }
        capabilities["resumable_four_agent_review"] = {
            "implemented": True,
            "reviewers": ["claude", "minimax", "kimi"],
            "complete_evidence_assembly": True,
            "hash_bound_panel": True,
            "provider_sized_video_proxy": True,
            "per_reviewer_resume": True,
        }
        capabilities.setdefault("finalize", {}).update({
            "platforms": sorted(load_profiles(self.root)["platforms"]),
            "archive_manifest_schema": 3,
            "final_contract_consistency_required": True,
        })
        capabilities.setdefault("mandatory_completion_gate", {}).update({
            "privacy_adaptive_panel": True,
            "inactive_reviewer_must_have_bounded_reason": True,
            "inactive_reviewer_cannot_be_recorded_as_pass": True,
        })
        if "standing_review_transfer_authorization" in capabilities:
            capabilities["standing_review_transfer_authorization"]["superseded_by"] = "persistent_authorization_matrix"
        result.data["recovery_head_selection"] = "campaign_scoped_freshest_valid_head_with_legacy_chain_compatibility"
        return self._stamp(result)

    def recover(self, head: str | None = None, project: str | None = None, campaign: str | None = None):
        if head is None and (project or campaign):
            selected = current_head(self.root, project=project, campaign=campaign)
            head = str(selected.relative_to(self.root)).replace("\\", "/")
        return self._stamp(super().recover(head))

    def authorization_resolve(self, project, campaign, recipient, materials, identifiable_people, metadata_stripped, privacy_preflight):
        command = "authorization.resolve"
        return self._stamp(self._guard(command, lambda: self._success(
            command,
            resolve_authorization(self.root, project, campaign, recipient, materials,
                                  contains_identifiable_people=identifiable_people,
                                  metadata_stripped=metadata_stripped,
                                  privacy_preflight=privacy_preflight),
            status="AUTHORIZED_FOR_SCOPED_REVIEW_TRANSFER",
            next_action="prepare_sanitized_reviewer_evidence",
        )))

    def platform_validate(self, platform, output, package):
        command = "platform.validate"
        return self._stamp(self._guard(command, lambda: self._success(
            command, validate_platform_output(self.root, platform, output, package),
            status="PLATFORM_OUTPUT_VALIDATED", next_action="contract-consistency.validate"
        )))

    def contract_consistency(self, spec: Path):
        command = "contract-consistency.validate"
        return self._stamp(self._guard(command, lambda: self._success(
            command, validate_final_contract(self.root, read_json(spec if spec.is_absolute() else self.root / spec)),
            status="FINAL_CONTRACT_SYNCHRONIZED", next_action="archive-manifest.validate"
        )))

    def audio_authority(self, provider, capability):
        command = "audio-authority.resolve"
        return self._stamp(self._guard(command, lambda: self._success(
            command, resolve_audio_authority(self.root, provider, capability),
            status="AUDIO_AUTHORITY_RESOLVED", next_action="owner_listening_gate" if provider != "owner" else "persist_owner_decision"
        )))

    def archive_manifest_validate(self, archive: Path):
        command = "archive-manifest.validate"
        def operation():
            folder = archive if archive.is_absolute() else self.root / archive
            return self._success(command, validate_archive_manifest(folder, read_json(folder / "manifest.json")),
                                 status="ARCHIVE_MANIFEST_VERIFIED", next_action="owner_publication_gate")
        return self._stamp(self._guard(command, operation))
    def final_package(self, spec, build=False):
        command = "final-package.build" if build else "final-package.prepare"
        fn = build_final_package_v2_6 if build else prepare_final_package_v2_6
        return self._stamp(self._guard(command, lambda: self._success(
            command, fn(self.root, spec),
            status="APPROVED_NOT_PUBLISHED" if build else "READY_TO_BUILD_FINAL_PACKAGE",
            next_action="owner_publication_gate" if build else "final-package.build",
        )))

    def final_package_verify(self, archive_id):
        command = "final-package.verify"
        return self._stamp(self._guard(command, lambda: self._success(
            command, verify_final_package_v2_6(self.root, archive_id),
            status="VERIFIED_APPROVED_NOT_PUBLISHED", next_action="owner_publication_gate",
        )))

    def four_agent_review(self, spec: Path, run_apis: bool = False):
        command = "four-agent-review.run" if run_apis else "four-agent-review.prepare"
        def operation():
            bundle = prepare_complete_evidence(self.root, spec)
            if not run_apis:
                return self._success(
                    command, bundle, status="READY_FOR_FOUR_AGENT_REVIEW",
                    next_action="four-agent-review.run",
                )
            panel = run_resumable_panel(self.root, bundle)
            return self._success(
                command, panel, status=panel.get("next_action", panel.get("status", "UNDER_REVIEW")),
                next_action=panel.get("next_action", "resume_four_agent_review"),
            )
        return self._stamp(self._guard(command, operation))
