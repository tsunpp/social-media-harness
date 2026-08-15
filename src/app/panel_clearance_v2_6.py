from __future__ import annotations

from typing import Any


VALID_INACTIVE = {"NOT_AUTHORIZED", "PRIVACY_BOUNDARY", "CAPABILITY_UNAVAILABLE", "NOT_REQUIRED_FOR_SCOPE"}


def validate_panel_clearance(panel: dict[str, Any]) -> dict[str, Any]:
    if panel.get("panel_version") != "2.6" or panel.get("next_action") != "FINAL_CANDIDATE":
        raise ValueError("Engine 2.6 panel has not cleared the final candidate")
    reviewers = panel.get("reviewers", {})
    if not reviewers:
        raise ValueError("Panel reviewer activation records are required")
    active = []
    inactive = []
    for name, record in reviewers.items():
        if record.get("active"):
            active.append(name)
            if record.get("decision") != "PASS" or not record.get("evidence_complete"):
                raise ValueError(f"Active reviewer has not passed complete evidence: {name}")
        else:
            inactive.append(name)
            if record.get("reason") not in VALID_INACTIVE:
                raise ValueError(f"Inactive reviewer lacks a valid bounded reason: {name}")
            if record.get("decision") == "PASS":
                raise ValueError(f"Inactive reviewer cannot be represented as PASS: {name}")
    if not {"claude", "minimax"} <= set(active):
        raise ValueError("Visual and complete-video authorities must be active")
    return {"status": "PASS", "active_reviewers": sorted(active), "inactive_reviewers": sorted(inactive), "publication_authorized": False}

