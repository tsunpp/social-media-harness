from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.review_governance_v2_6 import finding_signature, govern_finding


REVIEWER_AUTHORITY = {
    "claude": {
        "visual_hierarchy", "composition", "typography", "color",
        "visible_privacy", "visible_facts", "visual_narrative",
    },
    "minimax": {
        "motion", "pacing", "temporal_continuity", "audio", "bgm",
        "sync", "action_feasibility", "generation_feasibility",
    },
    "kimi": {
        "narrative_logic", "fact_integrity", "copy_consistency",
        "cross_stage_integrity", "workflow_audit", "provenance",
        "chronology", "forbidden_claims",
    },
}

OWNER_ONLY = {
    "publication", "material_product_truth_change", "unresolved_privacy",
    "incompatible_core_direction",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_panel_review(reviewer: str, review: dict[str, Any]) -> None:
    if reviewer not in REVIEWER_AUTHORITY:
        raise ValueError(f"Unknown reviewer: {reviewer}")
    required = {"reviewer", "decision", "findings", "summary", "evidence_complete"}
    missing = required - set(review)
    if missing:
        raise ValueError(f"Review missing fields: {sorted(missing)}")
    if review["reviewer"].lower() != reviewer:
        raise ValueError("Reviewer identity does not match panel slot")
    if review["decision"] not in {"PASS", "REVISE", "HUMAN_REVIEW"}:
        raise ValueError("Invalid review decision")
    if not review["evidence_complete"]:
        raise ValueError(f"{reviewer} review is invalid without complete required evidence")
    if not isinstance(review["findings"], list):
        raise ValueError("findings must be an array")
    for finding in review["findings"]:
        if not {"id", "domain", "severity", "problem", "required_change"} <= set(finding):
            raise ValueError("Finding does not match the panel contract")
        if finding["severity"] not in {"blocking", "ordinary", "optional"}:
            raise ValueError("Invalid finding severity")


def classify_findings(reviewer: str, review: dict[str, Any], stage: str = "stage_4", owner_resolutions: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    authority = REVIEWER_AUTHORITY[reviewer]
    classified = {"binding": [], "advisory": [], "owner_only": []}
    for finding in review["findings"]:
        # Owner-only authority is a hard boundary. Classify it before
        # temporal routing so publication decisions cannot be deferred.
        if finding["domain"] in OWNER_ONLY:
            item = {
                "reviewer": reviewer,
                **finding,
                "signature": finding_signature({"reviewer": reviewer, **finding}),
                "binding": True,
                "classification": "OWNER_ONLY",
            }
            classified["owner_only"].append(item)
            continue
        item = govern_finding(reviewer, finding, stage, authority, owner_resolutions)
        if item["classification"] == "RESOLVED_BY_OWNER":
            classified["advisory"].append(item)
            continue
        if item["classification"] == "DEFERRED_TO_CORRECT_STAGE":
            classified["advisory"].append(item)
            continue
        if finding["domain"] in authority:
            classified["binding"].append(item)
        else:
            item["classification_reason"] = "outside_reviewer_validated_authority"
            classified["advisory"].append(item)
    return classified


def aggregate_panel(
    claude: dict[str, Any],
    minimax: dict[str, Any],
    kimi: dict[str, Any],
    revision_count: int = 0,
    auto_revision_limit: int = 8,
    no_improvement_streak: int = 0,
    stage: str = "stage_4",
    owner_resolutions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not 1 <= auto_revision_limit <= 10:
        raise ValueError("auto_revision_limit must be between 1 and 10")
    reviews = {"claude": claude, "minimax": minimax, "kimi": kimi}
    classified = {}
    for reviewer, review in reviews.items():
        validate_panel_review(reviewer, review)
        classified[reviewer] = classify_findings(reviewer, review, stage, owner_resolutions)

    binding = [item for value in classified.values() for item in value["binding"]]
    advisory = [item for value in classified.values() for item in value["advisory"]]
    owner_only = [item for value in classified.values() for item in value["owner_only"]]
    binding_blockers = [item for item in binding if item["severity"] == "blocking"]
    explicit_human = [name for name, review in reviews.items() if review["decision"] == "HUMAN_REVIEW" and any(item["reviewer"] == name and item["severity"] == "blocking" for item in binding)]

    if owner_only or explicit_human:
        next_action, reason = "HUMAN_DECISION", "owner_only_or_explicit_human_issue"
    elif no_improvement_streak >= 2:
        next_action, reason = "HUMAN_DECISION", "no_improvement_guard"
    elif revision_count >= auto_revision_limit and binding_blockers:
        next_action, reason = "HUMAN_DECISION", "revision_limit_reached"
    elif binding_blockers:
        next_action, reason = "CODEX_ADJUDICATION", "binding_findings_require_repair"
    else:
        next_action, reason = "FINAL_CANDIDATE", "all_authoritative_domains_clear"

    return {
        "schema_version": 1,
        "panel_version": "2.5",
        "generated_at": utc_now(),
        "next_action": next_action,
        "reason": reason,
        "revision_count": revision_count,
        "auto_revision_limit": auto_revision_limit,
        "binding_findings": binding,
        "advisory_findings": advisory,
        "owner_only_findings": owner_only,
        "explicit_human_reviewers": explicit_human,
        "authority": {name: sorted(domains) for name, domains in REVIEWER_AUTHORITY.items()},
        "codex": {
            "role": "orchestrator, evidence adjudicator, repair executor and persistence authority",
            "may_auto_repair": "binding ordinary or blocking findings supported by evidence",
            "must_escalate": sorted(OWNER_ONLY),
        },
        "publication_authorized": False,
        "stage": stage,
    }


def evidence_contract() -> dict[str, Any]:
    return {
        "claude": {
            "required": ["complete_systematic_visual_timeline", "brief", "facts", "effective_contract", "copy", "prior_reviews"],
            "excluded_authority": ["audio", "bgm", "motion_only"],
        },
        "minimax": {
            "required": ["complete_source_proxies", "complete_cumulative_or_final_video_with_audio", "brief", "facts", "effective_contract", "copy", "prior_reviews"],
            "excluded_authority": ["document_provenance", "cross_stage_hash_integrity"],
        },
        "kimi": {
            "required": ["sanitized_campaign_dossier", "complete_multi_image_timeline", "brief", "facts", "effective_contract", "copy", "all_review_records", "provenance_manifests"],
            "excluded_authority": ["motion", "pacing", "audio", "bgm", "visual_aesthetics", "cover_selection"],
        },
    }
