from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.campaigns import get_campaign
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json


REQUIRED_STAGES = (
    "facts_locked",
    "narrative_panel_cleared",
    "segment_plan_cleared",
    "segments_cleared",
    "silent_master_cleared",
    "sound_strategy_locked",
    "cover_set_cleared",
    "platform_variants_cleared",
    "four_agent_panel_cleared",
)


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _evidence(root: Path, stage: str, record: dict[str, Any]) -> Path:
    if record.get("status") != "PASS":
        raise ValueError(f"Completion stage has not passed: {stage}")
    if not record.get("path") or not record.get("sha256"):
        raise ValueError(f"Completion stage lacks hashed evidence: {stage}")
    path = _resolve(root, record["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Completion evidence missing for {stage}: {path}")
    if sha256(path).upper() != str(record["sha256"]).upper():
        raise ValueError(f"Completion evidence hash mismatch: {stage}")
    return path


def _decision(root: Path, record: dict[str, Any], expected: str) -> dict[str, Any]:
    if not record:
        raise ValueError(f"{expected} requires an explicit persisted owner decision")
    path = _evidence(root, expected.lower(), record)
    value = read_json(path)
    if value.get("decision") != expected or value.get("actor") != "owner":
        raise ValueError(f"{expected} requires an explicit persisted owner decision")
    return value


def _validate_stage_semantics(stage: str, path: Path) -> None:
    value = read_json(path)
    expected_status = {
        "facts_locked": "FACTS_LOCKED",
        "narrative_panel_cleared": "NARRATIVE_PANEL_CLEARED",
        "segment_plan_cleared": "SEGMENTATION_CONSENSUS_REACHED",
        "segments_cleared": "READY_FOR_COMPLETE_VIDEO_DUAL_REVIEW",
        "silent_master_cleared": "SILENT_MASTER_CLEARED",
        "cover_set_cleared": "COVER_SET_CLEARED",
        "platform_variants_cleared": "PLATFORM_VARIANTS_CLEARED",
    }.get(stage)
    if expected_status and value.get("status") != expected_status:
        raise ValueError(f"Completion evidence has invalid semantic status for {stage}")
    if stage == "narrative_panel_cleared":
        if value.get("story_skeleton_count") != 3 or any(value.get("reviewer_decisions", {}).get(x) != "PASS" for x in ("claude", "minimax")):
            raise ValueError("Narrative clearance must prove exactly three skeletons and Claude/MiniMax PASS")
    elif stage == "segment_plan_cleared":
        if any(value.get("reviewer_decisions", {}).get(x) != "PASS" for x in ("claude", "minimax")):
            raise ValueError("Segment plan requires Claude and MiniMax consensus")
    elif stage == "segments_cleared":
        if not value.get("all_segments_complete") or not value.get("cumulative_reviews_complete"):
            raise ValueError("All segments and cumulative reviews must be complete")
    elif stage == "silent_master_cleared":
        if value.get("audio") is not False or not value.get("master_sha256"):
            raise ValueError("Silent-master clearance must prove a hashed silent master")
    elif stage == "cover_set_cleared":
        if int(value.get("candidate_count", 0)) < 2 or any(value.get("reviewer_decisions", {}).get(x) != "PASS" for x in ("claude", "minimax")):
            raise ValueError("Cover clearance requires at least two candidates and dual review")
    elif stage == "platform_variants_cleared":
        platforms = value.get("platforms", {})
        if not {"instagram_reels", "youtube_shorts"} <= set(platforms):
            raise ValueError("Platform clearance requires Instagram Reels and YouTube Shorts variants")
        for name in ("instagram_reels", "youtube_shorts"):
            if not platforms[name].get("path") or not platforms[name].get("sha256"):
                raise ValueError(f"Platform variant lacks hashed output: {name}")


def validate_completion_gate(root: Path, db_path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    gate_value = spec.get("completion_gate")
    if not gate_value:
        raise ValueError("Engine 2.5 finalization requires completion_gate")
    gate_path = _resolve(root, gate_value)
    gate = read_json(gate_path)
    if gate.get("schema_version") != 1 or gate.get("engine_api_version") != "2.5":
        raise ValueError("Completion gate must use the Engine 2.5 contract")
    if gate.get("campaign") != spec.get("campaign"):
        raise ValueError("Completion gate campaign does not match package spec")
    campaign = get_campaign(db_path, gate["campaign"])
    if campaign.get("state") not in {"UNDER_REVIEW", "APPROVED"}:
        raise ValueError("Campaign database state is not eligible for finalization")
    stages = gate.get("stages", {})
    missing = [name for name in REQUIRED_STAGES if name not in stages]
    if missing:
        raise ValueError(f"Completion gate missing mandatory stages: {missing}")
    evidence = {name: _evidence(root, name, stages[name]) for name in REQUIRED_STAGES}
    for name, path in evidence.items():
        if name not in {"sound_strategy_locked", "four_agent_panel_cleared"}:
            _validate_stage_semantics(name, path)

    sound = read_json(evidence["sound_strategy_locked"])
    mode = sound.get("mode")
    if mode not in {"original_bgm", "licensed_bgm", "no_bgm"}:
        raise ValueError("Sound strategy must explicitly select original_bgm, licensed_bgm, or no_bgm")
    if mode == "no_bgm":
        _decision(root, stages.get("owner_no_bgm_decision", {}), "OWNER_CONFIRMED_NO_BGM")
    else:
        for name in ("bgm_candidates_cleared", "final_audio_master_cleared", "owner_listening_cleared"):
            if name not in stages:
                raise ValueError(f"BGM finalization missing mandatory stage: {name}")
            _evidence(root, name, stages[name])
        _decision(root, stages["owner_listening_cleared"], "OWNER_LISTENING_CLEARED")

    panel = read_json(evidence["four_agent_panel_cleared"])
    if panel.get("panel_version") != "2.5" or panel.get("next_action") != "FINAL_CANDIDATE":
        raise ValueError("Authoritative Engine 2.5 panel has not cleared the final candidate")
    decisions = panel.get("reviewer_decisions", {})
    if any(decisions.get(name) != "PASS" for name in ("claude", "minimax", "kimi")):
        raise ValueError("Final panel must prove Claude, MiniMax, and Kimi PASS")

    render = read_json(_resolve(root, spec["render_manifest"]))
    output = render.get("output", {})
    audio_present = output.get("audio") not in {False, None, "none", "silent"}
    if mode == "no_bgm" and audio_present:
        raise ValueError("Render audio conflicts with owner-confirmed no-BGM strategy")
    if mode != "no_bgm" and not audio_present:
        raise ValueError("BGM strategy cannot finalize a silent platform master")
    if gate.get("status") != "READY_FOR_FINAL_PACKAGE":
        raise ValueError("Completion gate is not ready for final package")
    return {
        "path": gate_path,
        "sha256": sha256(gate_path),
        "campaign_state": campaign["state"],
        "sound_mode": mode,
        "stages": sorted(stages),
    }
