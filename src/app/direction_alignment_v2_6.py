from __future__ import annotations

from pathlib import Path
from typing import Any

from app.direction_contract_v2_6 import validate_confirmation


CORE_FIELDS = ("core_intent_supported", "audience_fit", "viewer_shift_supported", "creative_center_preserved", "tone_fit")


def validate_alignment(root: Path, campaign: str, artifact_type: str, artifact: dict[str, Any]) -> dict[str, Any]:
    confirmation = validate_confirmation(root, campaign)
    alignment = artifact.get("direction_alignment")
    if not isinstance(alignment, dict):
        raise ValueError(f"{artifact_type} requires direction_alignment")
    if alignment.get("direction_contract_hash") != confirmation["contract_hash"]:
        raise ValueError("Artifact is not bound to the active Direction Contract hash")
    failed = [field for field in CORE_FIELDS if alignment.get(field) is not True]
    if failed or alignment.get("anti_direction_triggered") is True or alignment.get("unsupported_promises"):
        core_change = any(field in failed for field in ("audience_fit", "viewer_shift_supported", "creative_center_preserved"))
        return {
            "status": "OWNER_RECONFIRMATION_REQUIRED" if core_change else "REVISION_REQUIRED",
            "failed_fields": failed,
            "anti_direction_triggered": bool(alignment.get("anti_direction_triggered")),
            "unsupported_promises": alignment.get("unsupported_promises", []),
        }
    return {"status": "PASS", "direction_contract_hash": confirmation["contract_hash"], "artifact_type": artifact_type}


def validate_narrative_options_alignment(root: Path, campaign: str, plan: dict[str, Any]) -> dict[str, Any]:
    options = plan.get("options", [])
    if len(options) != 3:
        raise ValueError("Direction alignment requires exactly three narrative options")
    reports = [validate_alignment(root, campaign, "narrative-option", option) for option in options]
    failures = [report for report in reports if report["status"] != "PASS"]
    if failures:
        raise ValueError("One or more narrative options diverge from the confirmed creative direction")
    return {"status": "PASS", "option_count": 3, "direction_contract_hash": reports[0]["direction_contract_hash"]}
