from __future__ import annotations

from typing import Any


REQUIRED_BEATS = ("hook", "development", "turn", "reveal", "resolution")
REQUIRED_QUESTIONS = (
    "audience_question", "middle_change", "visual_climax", "ending_insight",
    "text_progression", "source_feasibility",
)


def validate_narrative_option(option: dict[str, Any]) -> None:
    narrative = option.get("narrative_contract")
    if not isinstance(narrative, dict):
        raise ValueError(f"Option {option.get('id')} requires narrative_contract before asset selection")
    missing = [key for key in REQUIRED_QUESTIONS if not str(narrative.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Option {option.get('id')} narrative_contract missing: {missing}")
    beats = narrative.get("beats")
    if not isinstance(beats, list) or len(beats) < 5:
        raise ValueError(f"Option {option.get('id')} requires at least five narrative beats")
    functions = [beat.get("function") for beat in beats if isinstance(beat, dict)]
    missing_beats = [beat for beat in REQUIRED_BEATS if beat not in functions]
    if missing_beats:
        raise ValueError(f"Option {option.get('id')} missing narrative beats: {missing_beats}")
    for beat in beats:
        required = ("function", "story_job", "required_evidence", "text_job")
        absent = [key for key in required if not str(beat.get(key, "")).strip()]
        if absent:
            raise ValueError(f"Option {option.get('id')} beat missing: {absent}")
        if beat["text_job"].strip().lower() in {"describe image", "label image", "repeat visual"}:
            raise ValueError(f"Option {option.get('id')} text must advance the story, not repeat the image")
    coverage = option.get("narrative_evidence_coverage")
    if not isinstance(coverage, list) or len(coverage) < len(REQUIRED_BEATS):
        raise ValueError(f"Option {option.get('id')} requires evidence coverage for every narrative beat")
    covered = {item.get("function") for item in coverage if isinstance(item, dict) and item.get("asset_ids")}
    uncovered = [beat for beat in REQUIRED_BEATS if beat not in covered]
    if uncovered:
        raise ValueError(f"Option {option.get('id')} lacks source evidence for beats: {uncovered}")


def narrative_review_contract() -> str:
    return """Also return narrative_assessment with: hook_question, causal_or_discovery_progression, visual_climax, resolution, text_advances_story (boolean), all_beats_evidence_supported (boolean), missing_beats (array), unsupported_claims (array). A plan cannot PASS when it is only attractive shots, text merely labels visible attributes, or any beat lacks authentic evidence. Claude assesses visual causality, discovery, hierarchy, and text progression from the complete systematic visual timeline. MiniMax inspects every complete source proxy required by the plan and assesses action start, change, result, continuity, and feasibility. Never invent missing shots."""


def validate_narrative_review(review: dict[str, Any]) -> None:
    assessment = review.get("narrative_assessment")
    if not isinstance(assessment, dict):
        raise ValueError("Narrative-first review requires narrative_assessment")
    required = ("hook_question", "causal_or_discovery_progression", "visual_climax", "resolution", "text_advances_story", "all_beats_evidence_supported", "missing_beats", "unsupported_claims")
    missing = [key for key in required if key not in assessment]
    if missing:
        raise ValueError(f"Narrative assessment missing fields: {missing}")
    if review.get("decision") == "PASS" and (not assessment["text_advances_story"] or not assessment["all_beats_evidence_supported"] or assessment["missing_beats"] or assessment["unsupported_claims"]):
        raise ValueError("PASS contradicts narrative evidence assessment")
