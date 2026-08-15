from __future__ import annotations

from pathlib import Path
from typing import Any

from app.planning_orchestrator import prepare_plan_review, prepare_planning_context, write_json
from app.planning_privacy import find_quarantined_plan_references, read_policy, sanitize_planning_context


def prepare_private_context(root: Path, project: str, campaign: str) -> dict[str, Any]:
    context = prepare_planning_context(root, project, campaign)
    policy = read_policy(root / "policies" / "privacy_quarantine.json")
    clean = sanitize_planning_context(context, policy)
    write_json(root / "campaigns" / campaign / "plans" / "planning-context-sanitized.json", clean)
    write_json(root / "campaigns" / campaign / "plans" / "planning-evidence-manifest-sanitized.json", clean["evidence"])
    return clean


def prepare_private_plan_review(root: Path, project: str, campaign: str, plan_path: Path | None = None) -> dict[str, Any]:
    request = prepare_plan_review(root, project, campaign, plan_path)
    policy = read_policy(root / "policies" / "privacy_quarantine.json")
    references = find_quarantined_plan_references(request["plan_options"], policy)
    if references:
        raise ValueError(f"Plan references quarantined assets: {references}")
    request["planning_context"] = sanitize_planning_context(request["planning_context"], policy)
    request["privacy_preflight"] = {
        "status": "PASS",
        "quarantined_plan_references": [],
        "policy": "policies/privacy_quarantine.json",
    }
    output = root / "campaigns" / campaign / "plans" / "reviews" / "planning-review-request-sanitized.json"
    write_json(output, request)
    return request

