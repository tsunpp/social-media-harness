from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


STYLE_FIELD = "visual_style_profile"
DEFAULTS_PATH = Path("config") / "visual_style_defaults.json"


def _read_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def load_campaign_brief(root: Path, campaign: str) -> dict[str, Any]:
    path = root / "campaigns" / campaign / "brief.yaml"
    text = path.read_text(encoding="utf-8-sig")
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError(f"Expected an object in {path}")
        return value
    except json.JSONDecodeError:
        # The engine historically stores both JSON-compatible and ordinary YAML
        # briefs. Style resolution needs only one top-level scalar, so keep this
        # dependency-free and avoid interpreting unrelated Campaign content.
        match = re.search(rf"(?m)^\s*{re.escape(STYLE_FIELD)}\s*:\s*([^#\r\n]*)", text)
        if not match:
            return {}
        scalar = match.group(1).strip().strip("'\"")
        return {STYLE_FIELD: None if scalar.casefold() in {"", "null", "~"} else scalar}


def resolve_visual_style(root: Path, campaign: str) -> dict[str, Any] | None:
    brief_path = root / "campaigns" / campaign / "brief.yaml"
    # Legacy/test plans may predate Campaign briefs. Absence means the historical
    # unstyled behavior; an explicitly selected profile is still validated strictly.
    if not brief_path.is_file():
        return None
    brief = load_campaign_brief(root, campaign)
    defaults = _read_object(root / DEFAULTS_PATH)
    raw_style_id = brief.get(STYLE_FIELD)
    disabled = {str(value).casefold() for value in defaults.get("explicit_disable_values", [])}
    if isinstance(raw_style_id, str) and raw_style_id.casefold() in disabled:
        return None
    style_id = raw_style_id
    if style_id in (None, "", "default") and defaults.get("apply_when_brief_field_missing_or_null", False):
        style_id = defaults.get("default_profile")
    if style_id in (None, ""):
        return None
    if not isinstance(style_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", style_id):
        raise ValueError(f"Invalid {STYLE_FIELD}: {style_id!r}")
    profile = _read_object(root / "config" / "visual_styles" / f"{style_id}.json")
    if profile.get("id") != style_id:
        raise ValueError(f"Visual style profile contract invalid: {style_id}")
    return profile


def public_style_contract(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        key: profile[key]
        for key in (
            "id", "display_name", "abstract_principles", "story_skeleton_contract",
            "shot_selection_contract", "segment_contract", "claude_review_contract",
            "originality_policy", "typography_policy", "research_provenance",
        )
    }


def validate_generation_prompt(prompt: str, profile: dict[str, Any] | None) -> None:
    if profile is None:
        return
    policy = profile["originality_policy"]
    lowered = prompt.casefold()
    matches = [term for term in policy.get("prohibited_prompt_terms", []) if term.casefold() in lowered]
    for pattern in policy.get("prohibited_prompt_patterns", []):
        if re.search(pattern, prompt, flags=re.IGNORECASE):
            matches.append(pattern)
    if matches:
        raise ValueError(
            "Generation prompt violates the selected style originality policy; "
            f"use abstract visual principles only (matched: {sorted(set(matches))})"
        )


def validate_narrative_style_contract(plan: dict[str, Any], profile: dict[str, Any] | None) -> None:
    if profile is None:
        return
    required = set(profile["story_skeleton_contract"]["required_fields"])
    for option in plan.get("options", []):
        contract = option.get("visual_style_contract", {})
        missing = required - set(contract)
        if missing:
            raise ValueError(f"Option {option.get('id')} missing visual style fields: {sorted(missing)}")


def validate_segment_style_contract(plan: dict[str, Any], profile: dict[str, Any] | None) -> None:
    if profile is None:
        return
    selected = next(x for x in plan["candidate_schemes"] if x.get("scheme_id") == plan["selected_scheme"])
    required = set(profile["segment_contract"]["required_fields"])
    for segment in selected["segments"]:
        contract = segment.get("visual_style_contract", {})
        missing = required - set(contract)
        if missing:
            raise ValueError(f"Segment {segment.get('segment_id')} missing visual style fields: {sorted(missing)}")
