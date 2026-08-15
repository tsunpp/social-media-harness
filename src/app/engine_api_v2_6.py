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
        return self._stamp(result)

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
