from __future__ import annotations


INITIAL_STATE = "NEW"

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "NEW": ("INGESTED", "REJECTED"),
    "INGESTED": ("PLANNED", "REJECTED"),
    "PLANNED": ("PLAN_APPROVED", "HUMAN_DECISION", "REJECTED"),
    "PLAN_APPROVED": ("DRAFT_RENDERED", "HUMAN_DECISION", "REJECTED"),
    "DRAFT_RENDERED": ("UNDER_REVIEW", "HUMAN_DECISION", "REJECTED"),
    "UNDER_REVIEW": ("REVISION_REQUIRED", "HUMAN_DECISION", "APPROVED", "REJECTED"),
    "REVISION_REQUIRED": ("DRAFT_RENDERED", "HUMAN_DECISION", "REJECTED"),
    "HUMAN_DECISION": ("DRAFT_RENDERED", "APPROVED", "REJECTED"),
    "APPROVED": ("EXPORTED",),
    "EXPORTED": (),
    "REJECTED": (),
}

ALL_STATES = tuple(TRANSITIONS)


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, ())

