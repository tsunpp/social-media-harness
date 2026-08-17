from __future__ import annotations

from pathlib import Path
from typing import Any

from app.narrative_planning import validate_narrative_option, validate_narrative_review
from app.planning_orchestrator import (
    prepare_planning_context,
    read_json,
    run_plan_review as run_legacy_plan_review,
    write_json,
)
from app.review_policy import utc_now
from app.visual_style_profiles import (
    public_style_contract,
    resolve_visual_style,
    validate_narrative_style_contract,
)
from app.direction_alignment_v2_6 import validate_narrative_options_alignment


def validate_narrative_plan(plan: dict[str, Any], campaign: str) -> None:
    if plan.get("schema_version") != 2 or plan.get("campaign") != campaign:
        raise ValueError("Narrative-first planning requires schema_version 2 and matching campaign")
    options = plan.get("options")
    if not isinstance(options, list) or len(options) != 3 or {x.get("id") for x in options} != {"A", "B", "C"}:
        raise ValueError("Narrative-first planning requires exactly options A, B and C")
    base = {"name", "target_duration_seconds", "concept", "opening_hook", "timeline", "strength", "risk"}
    for option in options:
        missing = base - set(option)
        if missing:
            raise ValueError(f"Option {option.get('id')} missing fields: {sorted(missing)}")
        validate_narrative_option(option)


def prepare_narrative_review(root: Path, project: str, campaign: str, plan_path: Path | None = None) -> dict[str, Any]:
    context = prepare_planning_context(root, project, campaign)
    visual_style = resolve_visual_style(root, campaign)
    path = plan_path or root / "campaigns" / campaign / "plans" / "narrative_plan_options.json"
    if not path.is_file():
        raise FileNotFoundError(f"Narrative plan options not found: {path}")
    plan = read_json(path)
    validate_narrative_plan(plan, campaign)
    if (root / "campaigns" / campaign / "direction" / "required.json").is_file():
        validate_narrative_options_alignment(root, campaign, plan)
    validate_narrative_style_contract(plan, visual_style)
    if visual_style is not None:
        context["visual_style_contract"] = public_style_contract(visual_style)
    context["evidence_contract"].update({
        "claude_narrative": "complete systematic visual timeline for every proposed beat; assess hook, discovery/causality, climax, resolution and whether text advances the story",
        "minimax_narrative": "every complete source proxy used by any beat; assess action start, change, result, continuity and feasibility",
        "codex_narrative": "three story skeletons before shot ranking; every selected shot has one explicit narrative function and verified source evidence",
    })
    request = {
        "schema_version": 2,
        "created_at": utc_now(),
        "project": project,
        "campaign": campaign,
        "planning_mode": "NARRATIVE_FIRST",
        "plan_path": str(path.relative_to(root)).replace("\\", "/"),
        "plan_options": plan,
        "planning_context": context,
        "stage_order": ["facts", "owner_confirmed_direction", "three_story_skeletons", "direction_alignment", "dual_narrative_review", "codex_adjudication", "evidence_based_asset_selection", "beat_coverage_gate", "segmented_production"],
        "owner_gate": "Owner is interrupted only for factual uncertainty, incompatible creative directions, or final direction review; ordinary narrative repairs route to Codex.",
    }
    if visual_style is not None:
        request["visual_style_profile"] = visual_style["id"]
        request["visual_style_contract"] = public_style_contract(visual_style)
    review_dir = root / "campaigns" / campaign / "plans" / "narrative-reviews"
    write_json(review_dir / "narrative-review-request.json", request)
    write_json(review_dir / "narrative-cycle-state.json", {"campaign": campaign, "status": "READY_FOR_DUAL_NARRATIVE_REVIEW", "api_calls_performed": False, "updated_at": utc_now()})
    return request


def run_narrative_review(root: Path, request: dict[str, Any], revision_count: int = 0) -> dict[str, Any]:
    if request.get("planning_mode") != "NARRATIVE_FIRST":
        raise ValueError("Narrative executor refuses a legacy visual-sequence request")
    # The established dual-model transport remains authoritative. The request embeds
    # the narrative contract, and results are checked again here before acceptance.
    result = run_legacy_plan_review(root, request, revision_count)
    review_dir = root / "campaigns" / request["campaign"] / "plans" / "reviews"
    for filename in ("claude-planning-review.json", "minimax-planning-review.json"):
        validate_narrative_review(read_json(review_dir / filename))
    result["narrative_gate"] = "PASS"
    result["production_allowed"] = False
    result["next_action"] = "CODEX_NARRATIVE_ADJUDICATION" if result["next_action"] != "HUMAN_REVIEW" else result["next_action"]
    target = root / "campaigns" / request["campaign"] / "plans" / "narrative-reviews"
    write_json(target / "narrative-review-aggregation.json", result)
    return result
