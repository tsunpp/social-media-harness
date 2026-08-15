from __future__ import annotations

import json
from pathlib import Path
from typing import Any


KNOWN_RECIPIENTS = {"claude", "minimax", "kimi-k3", "deepseek"}
FORBIDDEN_MATERIALS = {"credential", "api_key", "identity_document", "privacy_quarantined"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def matrix_path(root: Path, project: str) -> Path:
    return root / "projects" / project / "decisions" / "review-authorization-matrix-v2-6.json"


def resolve_authorization(
    root: Path,
    project: str,
    campaign: str,
    recipient: str,
    materials: list[str],
    *,
    contains_identifiable_people: bool,
    metadata_stripped: bool,
    privacy_preflight: str,
) -> dict[str, Any]:
    path = matrix_path(root, project)
    if not path.is_file():
        raise FileNotFoundError(f"Authorization matrix missing: {path}")
    matrix = read_json(path)
    if matrix.get("status") != "ACTIVE":
        raise ValueError("Authorization matrix is not active")
    name = recipient.strip().lower()
    if name not in KNOWN_RECIPIENTS:
        raise ValueError(f"Unknown review recipient: {name}")
    rule = matrix.get("recipients", {}).get(name)
    if not rule or rule.get("status") != "AUTHORIZED":
        raise ValueError(f"Recipient is not authorized for this project: {name}")
    if privacy_preflight != "PASS":
        raise ValueError("Privacy preflight must pass")
    normalized = {item.strip().lower() for item in materials}
    forbidden = sorted(normalized & FORBIDDEN_MATERIALS)
    if forbidden:
        raise ValueError(f"Forbidden materials requested: {forbidden}")
    allowed = set(rule.get("allowed_materials", []))
    if not normalized <= allowed:
        raise ValueError(f"Materials exceed authorization: {sorted(normalized - allowed)}")
    if rule.get("metadata_stripping_required", True) and not metadata_stripped:
        raise ValueError("Metadata stripping is required")
    if contains_identifiable_people and not rule.get("identifiable_people_allowed", False):
        raise ValueError(f"Identifiable people are not authorized for {name}")
    return {
        "schema_version": 2,
        "status": "AUTHORIZED_FOR_SCOPED_REVIEW_TRANSFER",
        "project": project,
        "campaign": campaign,
        "recipient": name,
        "materials": sorted(normalized),
        "contains_identifiable_people": contains_identifiable_people,
        "metadata_stripped": metadata_stripped,
        "standing_authorization": str(path.relative_to(root)).replace("\\", "/"),
        "per_transfer_owner_confirmation_required": False,
        "publication_authorized": False,
    }

