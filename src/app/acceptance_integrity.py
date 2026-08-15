from __future__ import annotations
from typing import Any

MOTION_AXES={"motion","pacing","action_start","action_change","action_result","continuity_motion","stable_rest"}
VISUAL_AXES={"composition","typography","color","visual_hierarchy","pixel_fact","privacy"}

def require_documentary_evidence(beat: dict[str,Any]) -> None:
    if not beat.get("asset_id") or not beat.get("required_evidence"):
        raise ValueError("Every documentary beat requires an authentic asset_id and required_evidence")
    if beat.get("evidence_status") in {"MISSING","UNSUPPORTED"}:
        raise ValueError("Missing documentary evidence must revise the story or request new capture; generation cannot silently fill it")
    if beat.get("generated_to_fill_missing_evidence"):
        raise ValueError("Generated media cannot substitute for a missing factual documentary beat")

def validate_contract_render_sync(contract: dict[str,Any], render: dict[str,Any]) -> None:
    narrative=contract.get("narrative",{})
    segments=render.get("segments",[])
    if len(narrative)!=len(segments): raise ValueError("Final story contract and render segment count differ")
    expected=list(narrative.values())
    for index,(beat,segment) in enumerate(zip(expected,segments),1):
        if beat.get("asset_id")!=segment.get("asset_id"): raise ValueError(f"Segment {index} asset differs from final story contract")
        if beat.get("text")!=segment.get("text"): raise ValueError(f"Segment {index} text differs from final story contract")
        output=beat.get("output","")
        if not output: raise ValueError(f"Segment {index} lacks output timeline mapping")

def validate_resolution_semantics(contract: dict[str,Any]) -> None:
    resolution=contract.get("narrative",{}).get("resolution",{})
    continuity=contract.get("continuity_contract",{})
    if not resolution.get("job") or not continuity.get("resolution"):
        raise ValueError("Resolution and stable-ending semantics must be explicit before final review")

def adjudicate_modality_conflict(claude: dict[str,Any], minimax: dict[str,Any], issue_axis: str, pixel_contradiction: bool=False) -> dict[str,str]:
    if issue_axis in MOTION_AXES:
        if pixel_contradiction: return {"authority":"CODEX","route":"RECONCILE_PIXEL_AND_MOTION_EVIDENCE"}
        return {"authority":"MINIMAX","route":"USE_COMPLETE_VIDEO_EVIDENCE"}
    if issue_axis in VISUAL_AXES: return {"authority":"CLAUDE","route":"USE_SYSTEMATIC_VISUAL_EVIDENCE"}
    return {"authority":"CODEX","route":"FACT_AND_CONTRACT_ADJUDICATION"}

def validate_final_dual_pass(claude: dict[str,Any], minimax: dict[str,Any], contract_sync: bool) -> None:
    if not contract_sync: raise ValueError("Final review cannot pass against a stale or unsynchronized contract")
    if claude.get("decision")!="PASS" or minimax.get("decision")!="PASS": raise ValueError("Final master requires Claude and MiniMax PASS after valid adjudication")
    if claude.get("blocking_issues") or minimax.get("blocking_issues"): raise ValueError("PASS cannot contain blocking issues")

def validate_version_attribution(review: dict[str,Any], allowed_text_by_version: dict[str,set[str]]) -> None:
    attributions=review.get("text_attributions",{})
    for version,phrases in attributions.items():
        if version not in allowed_text_by_version: raise ValueError(f"Unknown version attribution: {version}")
        invalid=set(phrases)-allowed_text_by_version[version]
        if invalid: raise ValueError(f"Review attributed text to wrong version: {version}: {sorted(invalid)}")

def validate_blind_isolation(context: dict[str,Any]) -> None:
    blind=context.get("blind_context",{})
    if not blind.get("enabled") or not blind.get("prior_creative_history_excluded"):
        raise ValueError("Blind validation requires explicit prior-creative-history exclusion")
    forbidden=("prior_master","prior_caption","prior_shot_order","prior_review_conclusion")
    leaked=[key for key in forbidden if context.get(key)]
    if leaked: raise ValueError(f"Blind context leaked prior creative fields: {leaked}")

