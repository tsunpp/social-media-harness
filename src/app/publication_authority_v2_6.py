from __future__ import annotations

from typing import Any


DECISIONS = {"APPROVE_PACKAGE_ONLY", "ARCHIVE_NO_PUBLISH", "AUTHORIZE_PUBLICATION"}


def resolve_stage5_owner_decision(decision: dict[str, Any], current_receipt_sha256: str) -> dict[str, Any]:
    if decision.get("actor") != "owner" or decision.get("decision") not in DECISIONS:
        raise ValueError(f"Stage 5 owner decision must be one of {sorted(DECISIONS)}")
    if str(decision.get("stage_receipt_sha256", "")).lower() != current_receipt_sha256.lower():
        raise ValueError("Stage 5 owner decision is not bound to the current receipt")
    choice = decision["decision"]
    publication = choice == "AUTHORIZE_PUBLICATION"
    if publication and not decision.get("target_platforms"):
        raise ValueError("Publication authorization requires explicit target platforms")
    status = {
        "APPROVE_PACKAGE_ONLY": "PACKAGE_APPROVED_NOT_PUBLISHED",
        "ARCHIVE_NO_PUBLISH": "ARCHIVED_NOT_PUBLISHED",
        "AUTHORIZE_PUBLICATION": "PUBLICATION_AUTHORIZED",
    }[choice]
    return {
        "status": status,
        "package_approved": True,
        "archive_authorized": choice in {"ARCHIVE_NO_PUBLISH", "AUTHORIZE_PUBLICATION"},
        "publication_authorized": publication,
        "target_platforms": decision.get("target_platforms", []) if publication else [],
        "next_action": "publish" if publication else ("archive" if choice == "ARCHIVE_NO_PUBLISH" else "await_archive_or_publish_decision"),
    }
