from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ALLOWED_STAGES = {"narrative_selection", "final_master", "publication_package"}
DECISIONS = {"UPHOLD", "CHALLENGE", "HUMAN_REVIEW"}
CODEX_DISPOSITIONS = {"ACCEPT", "PARTIAL_ACCEPT", "REJECT", "HUMAN_REVIEW"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def adversarial_review_contract() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "deepseek_text_critic",
        "purpose": "Attempt to falsify Codex conclusions using supplied textual evidence.",
        "trigger_stages": sorted(ALLOWED_STAGES),
        "required_evidence": ["codex_conclusions", "campaign_facts", "effective_story_contract", "review_summaries", "copy_or_publication_package_when_applicable", "evidence_index"],
        "authority": ["argument_validity", "copy_clarity", "unsupported_inference", "internal_contradiction", "conclusion_evidence_mismatch"],
        "excluded_authority": ["pixel_visible_fact", "visual_aesthetics", "motion", "pacing", "audio", "bgm", "mix_balance", "publication_authorization"],
        "not_a_vote": True,
        "codex_dispositions": sorted(CODEX_DISPOSITIONS),
        "loop_guard": {"max_rounds": 3, "stop_when": "Repeated challenge adds no new evidence or falsifiable reasoning."},
        "owner_gate": ["unresolved_fact_uncertainty", "incompatible_core_direction", "material_product_truth_change", "publication"],
    }


def validate_adversarial_review(review: dict[str, Any], evidence_ids: set[str]) -> None:
    required = {"reviewer", "decision", "challenges", "summary", "evidence_complete"}
    missing = required - set(review)
    if missing:
        raise ValueError(f"Adversarial review missing fields: {sorted(missing)}")
    if review["reviewer"] != "deepseek_text_critic" or review["decision"] not in DECISIONS:
        raise ValueError("Invalid adversarial reviewer or decision")
    if not review["evidence_complete"] or not isinstance(review["challenges"], list):
        raise ValueError("Complete textual evidence and a challenges array are required")
    for challenge in review["challenges"]:
        fields = {"id", "codex_conclusion", "argument", "evidence_ids", "proposed_action"}
        if not fields <= set(challenge) or not challenge["evidence_ids"]:
            raise ValueError("Challenge does not match the evidence contract")
        unknown = set(challenge["evidence_ids"]) - evidence_ids
        if unknown:
            raise ValueError(f"Challenge cites unknown evidence: {sorted(unknown)}")
        forbidden = set(challenge.get("claimed_modalities", [])) & {"visual", "motion", "audio", "bgm", "mix_balance"}
        if forbidden:
            raise ValueError(f"DeepSeek claimed excluded modalities: {sorted(forbidden)}")


def adjudicate_challenges(review: dict[str, Any], dispositions: list[dict[str, Any]]) -> dict[str, Any]:
    if {x["id"] for x in review["challenges"]} != {x.get("challenge_id") for x in dispositions}:
        raise ValueError("Codex must adjudicate every challenge exactly once")
    for item in dispositions:
        if item.get("disposition") not in CODEX_DISPOSITIONS or not item.get("reason") or not item.get("evidence_ids"):
            raise ValueError("Every Codex disposition requires a valid disposition, reason and evidence_ids")
    owner = [x for x in dispositions if x["disposition"] == "HUMAN_REVIEW"]
    accepted = [x for x in dispositions if x["disposition"] in {"ACCEPT", "PARTIAL_ACCEPT"}]
    return {"schema_version": 1, "generated_at": utc_now(), "next_action": "HUMAN_DECISION" if owner else ("CODEX_REPAIR" if accepted else "NO_CHANGE"), "dispositions": dispositions, "publication_authorized": False}
