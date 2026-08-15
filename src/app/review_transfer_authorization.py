from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DECISION_NAME = "standing-review-transfer-authorization-v2-5.json"
ALLOWED_RECIPIENTS = {"claude", "minimax", "kimi-k3"}
FORBIDDEN_MATERIAL_MARKERS = {
    "privacy_quarantined",
    "credential",
    "api_key",
    "identity_document",
    "unrelated_personal_data",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_review_transfer_authorization(
    root: Path,
    project: str,
    campaign: str,
    recipients: list[str],
    materials: list[str],
    privacy_preflight: str,
    fact_preflight: str,
) -> dict[str, Any]:
    decision = Path("projects") / project / "decisions" / DECISION_NAME
    path = root / decision
    if not path.is_file():
        raise FileNotFoundError(f"Standing review-transfer decision missing: {path}")
    record = _read(path)
    if record.get("status") != "ACTIVE":
        raise ValueError("Standing review-transfer authorization is not active")
    if project != record.get("scope", {}).get("project"):
        raise ValueError(f"Project is outside standing authorization scope: {project}")
    requested = {value.strip().lower() for value in recipients}
    authorized = {value.lower() for value in record.get("authorized_recipients", [])}
    if not requested or not requested.issubset(ALLOWED_RECIPIENTS & authorized):
        raise ValueError(f"Unauthorized review recipient requested: {sorted(requested - authorized)}")
    if privacy_preflight != "PASS":
        raise ValueError("Review transfer requires privacy preflight PASS")
    if fact_preflight != "PASS":
        raise ValueError("Review transfer requires fact preflight PASS")
    normalized_materials = {value.strip().lower() for value in materials}
    forbidden = sorted(marker for marker in FORBIDDEN_MATERIAL_MARKERS if marker in normalized_materials)
    if forbidden:
        raise ValueError(f"Forbidden review material requested: {forbidden}")
    if not campaign or "/" in campaign or "\\" in campaign:
        raise ValueError("Campaign must be a single governed Campaign slug")
    return {
        "schema_version": 1,
        "status": "AUTHORIZED_FOR_SCOPED_REVIEW_TRANSFER",
        "project": project,
        "campaign": campaign,
        "recipients": sorted(requested),
        "materials": sorted(normalized_materials),
        "privacy_preflight": "PASS",
        "fact_preflight": "PASS",
        "standing_authorization": str(decision).replace("\\", "/"),
        "per_transfer_owner_confirmation_required": False,
        "paid_review_calls_allowed": True,
        "publication_authorized": False,
        "next_action": "prepare_sanitized_reviewer_evidence",
    }
