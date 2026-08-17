from __future__ import annotations


INITIAL_STATE = "NEW"

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "NEW": ("INGESTED", "REJECTED"),
    # INGESTED -> PLANNED remains for legacy Campaign recovery. New Campaigns
    # carry a direction/required.json marker and are blocked by planning preflight.
    "INGESTED": ("DIRECTION_ALIGNMENT_PENDING", "PLANNED", "REJECTED"),
    "DIRECTION_ALIGNMENT_PENDING": ("DIRECTION_CONFIRMED", "HUMAN_DECISION", "REJECTED"),
    "DIRECTION_CONFIRMED": ("PLANNED", "DIRECTION_ALIGNMENT_PENDING", "REJECTED"),
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

