from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


DECISIONS = {"PASS", "REVISE", "HUMAN_REVIEW"}
SCORE_NAMES = {
    "visual_quality",
    "authenticity",
    "brand_consistency",
    "platform_fit",
    "risk",
}

DEFAULT_AUTO_REVISION_LIMIT = 8
MAX_AUTO_REVISION_LIMIT = 10


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_review(review: dict[str, Any]) -> None:
    required = {
        "reviewer",
        "decision",
        "scores",
        "blocking_issues",
        "optional_suggestions",
        "summary",
    }
    missing = required - set(review)
    if missing:
        raise ValueError(f"Review missing fields: {sorted(missing)}")
    if review["decision"] not in DECISIONS:
        raise ValueError(f"Invalid review decision: {review['decision']}")
    if set(review["scores"]) != SCORE_NAMES:
        raise ValueError("Review score fields do not match the contract")
    if any(
        not isinstance(value, int) or not 1 <= value <= 10
        for value in review["scores"].values()
    ):
        raise ValueError("Review scores must be integers from 1 to 10")
    if not isinstance(review["blocking_issues"], list):
        raise ValueError("blocking_issues must be an array")
    if not isinstance(review["optional_suggestions"], list):
        raise ValueError("optional_suggestions must be an array")
    decision = review["decision"]
    risk = review["scores"]["risk"]
    blockers = review["blocking_issues"]
    if decision == "PASS" and blockers:
        raise ValueError("PASS cannot contain blocking issues")
    if decision == "PASS" and risk >= 7:
        raise ValueError("PASS conflicts with a high risk score")
    if decision in {"REVISE", "HUMAN_REVIEW"} and not blockers:
        raise ValueError(f"{decision} requires at least one blocking issue")


def aggregate_reviews(
    claude: dict[str, Any],
    minimax: dict[str, Any],
    revision_count: int,
    auto_revision_limit: int = DEFAULT_AUTO_REVISION_LIMIT,
    high_risk_threshold: int = 7,
    revision_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not 1 <= auto_revision_limit <= MAX_AUTO_REVISION_LIMIT:
        raise ValueError(
            f"auto_revision_limit must be between 1 and {MAX_AUTO_REVISION_LIMIT}"
        )
    validate_review(claude)
    validate_review(minimax)
    reviews = {"claude": claude, "minimax": minimax}
    high_risk = [
        name
        for name, review in reviews.items()
        if review["scores"]["risk"] >= high_risk_threshold
    ]
    human_requests = [
        name
        for name, review in reviews.items()
        if review["decision"] == "HUMAN_REVIEW"
    ]
    blockers = [
        {"reviewer": name, **issue}
        for name, review in reviews.items()
        for issue in review["blocking_issues"]
    ]

    history = revision_history or []
    no_improvement_streak = 0
    repeated_blocker_streak = 0
    for cycle in reversed(history):
        if cycle.get("measurable_improvement", True):
            break
        no_improvement_streak += 1
    if history:
        latest_signature = history[-1].get("blocker_signature")
        if latest_signature:
            for cycle in reversed(history):
                if cycle.get("blocker_signature") != latest_signature:
                    break
                repeated_blocker_streak += 1
    loop_guard_triggered = no_improvement_streak >= 2 or repeated_blocker_streak >= 3

    if high_risk or human_requests:
        next_action = "HUMAN_DECISION"
        reason = "high_risk_or_explicit_human_review"
    elif all(review["decision"] == "PASS" for review in reviews.values()):
        next_action = "FINAL_CANDIDATE"
        reason = "both_independent_reviewers_passed"
    elif loop_guard_triggered:
        next_action = "HUMAN_DECISION"
        reason = "revision_progress_stalled"
    elif revision_count >= auto_revision_limit:
        next_action = "HUMAN_DECISION"
        reason = "auto_revision_limit_reached"
    else:
        next_action = "CODEX_ADJUDICATION"
        reason = "one_or_more_reviewers_requested_revision"

    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "next_action": next_action,
        "reason": reason,
        "revision_count": revision_count,
        "auto_revision_limit": auto_revision_limit,
        "revision_loop_guard": {
            "triggered": loop_guard_triggered,
            "no_improvement_streak": no_improvement_streak,
            "repeated_blocker_streak": repeated_blocker_streak,
            "rules": {
                "no_measurable_improvement_cycles": 2,
                "same_blocker_cycles": 3,
            },
        },
        "high_risk_reviewers": high_risk,
        "human_review_requests": human_requests,
        "blocking_issues": blockers,
        "optional_suggestions": [
            {"reviewer": name, "suggestion": suggestion}
            for name, review in reviews.items()
            for suggestion in review["optional_suggestions"]
        ],
        "codex_policy": {
            "auto_accept": "evidence-supported, in-scope, non-conflicting changes",
            "reject_with_reason": "unsupported or source-contradicted reviewer claims",
            "escalate": "factual/privacy uncertainty, incompatible requirements, stalled progress, or revision limit",
        },
    }

