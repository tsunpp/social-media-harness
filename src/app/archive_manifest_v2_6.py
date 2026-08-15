from __future__ import annotations

from pathlib import Path
from typing import Any

from app.image_review_orchestrator import sha256


REQUIRED = {
    "schema_version", "archive_id", "display_name", "campaign", "created_at", "status",
    "platforms", "master", "assets", "story_contract", "reviews", "owner_approval",
    "publishing_authorized", "publication_gate",
}


def validate_archive_manifest(archive: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED - set(manifest)
    if missing:
        raise ValueError(f"Archive manifest missing fields: {sorted(missing)}")
    if manifest["schema_version"] != 3:
        raise ValueError("Harness 2.6 requires archive manifest schema_version 3")
    if manifest["status"] not in {"APPROVED_NOT_PUBLISHED", "READY_NOT_PUBLISHED"}:
        raise ValueError("Invalid archive status")
    if manifest["publishing_authorized"] is not False:
        raise ValueError("Archive construction cannot authorize publication")
    failures = []
    for asset in manifest["assets"]:
        path = archive / asset["path"]
        if not path.is_file() or sha256(path).upper() != str(asset["sha256"]).upper():
            failures.append(asset["path"])
    if failures:
        raise ValueError(f"Archive asset verification failed: {failures}")
    if not (archive / manifest["master"]).is_file():
        raise ValueError("Archive master is missing")
    return {"status": "PASS", "archive_id": manifest["archive_id"], "asset_count": len(manifest["assets"]), "publication_authorized": False}

