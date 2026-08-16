from __future__ import annotations

from typing import Any
from pathlib import Path

from app.image_review_orchestrator import sha256


VALID_INACTIVE = {"NOT_AUTHORIZED", "PRIVACY_BOUNDARY", "CAPABILITY_UNAVAILABLE", "NOT_REQUIRED_FOR_SCOPE"}


def validate_panel_clearance(panel: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    if panel.get("panel_version") != "2.6" or panel.get("next_action") != "FINAL_CANDIDATE":
        raise ValueError("Engine 2.6 panel has not cleared the final candidate")
    reviewers = panel.get("reviewers", {})
    if not reviewers:
        raise ValueError("Panel reviewer activation records are required")
    active = []
    inactive = []
    master_hash = panel.get("master_sha256")
    evidence_hash = panel.get("evidence_bundle_sha256")
    review_dir = Path(panel["review_dir"]) if panel.get("review_dir") else None
    if review_dir is not None and root is not None and not review_dir.is_absolute():
        review_dir = root / review_dir
    for name, record in reviewers.items():
        if record.get("active"):
            active.append(name)
            if record.get("decision") != "PASS" or not record.get("evidence_complete"):
                raise ValueError(f"Active reviewer has not passed complete evidence: {name}")
            if master_hash and record.get("reviewed_master_sha256") != master_hash:
                raise ValueError(f"Reviewer is stale for current master: {name}")
            if evidence_hash and record.get("evidence_bundle_sha256") != evidence_hash:
                raise ValueError(f"Reviewer used stale or incomplete evidence: {name}")
            if review_dir is not None and record.get("review_path") and record.get("review_sha256"):
                review_path = review_dir / record["review_path"]
                if not review_path.is_file() or sha256(review_path).lower() != str(record["review_sha256"]).lower():
                    raise ValueError(f"Reviewer evidence hash mismatch: {name}")
        else:
            inactive.append(name)
            if record.get("reason") not in VALID_INACTIVE:
                raise ValueError(f"Inactive reviewer lacks a valid bounded reason: {name}")
            if record.get("decision") == "PASS":
                raise ValueError(f"Inactive reviewer cannot be represented as PASS: {name}")
    if not {"claude", "minimax"} <= set(active):
        raise ValueError("Visual and complete-video authorities must be active")
    return {"status": "PASS", "active_reviewers": sorted(active), "inactive_reviewers": sorted(inactive), "publication_authorized": False}

