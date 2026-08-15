from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_sound_strategy(strategy: dict[str, Any]) -> None:
    required = {"mode", "story_job", "beat_map", "vocals_allowed", "preserve_silent_master", "candidate_count"}
    missing = required - set(strategy)
    if missing:
        raise ValueError(f"Sound strategy missing fields: {sorted(missing)}")
    if strategy["mode"] not in {"original_bgm", "licensed_bgm", "no_bgm"}:
        raise ValueError("Unsupported sound strategy mode")
    if strategy["candidate_count"] != 3 and strategy["mode"] != "no_bgm":
        raise ValueError("BGM comparison requires exactly three candidates")
    if not strategy["preserve_silent_master"]:
        raise ValueError("Silent master preservation is mandatory")
    if not isinstance(strategy["beat_map"], list) or not strategy["beat_map"]:
        raise ValueError("BGM must be designed against an explicit story beat map")
    for beat in strategy["beat_map"]:
        if not {"id", "start", "end", "music_job"} <= set(beat):
            raise ValueError("Each beat needs id, start, end and music_job")
        if float(beat["end"]) <= float(beat["start"]):
            raise ValueError("Story beat end must be after start")


def prepare_bgm_contract(root: Path, campaign: str, silent_master: Path, final_story_contract: Path, strategy: dict[str, Any], directions: list[dict[str, Any]]) -> dict[str, Any]:
    validate_sound_strategy(strategy)
    if not silent_master.is_file() or not final_story_contract.is_file():
        raise FileNotFoundError("Silent master and final story contract must exist")
    if strategy["mode"] != "no_bgm":
        if len(directions) != 3:
            raise ValueError("Exactly three BGM directions are required")
        ids = [item.get("id") for item in directions]
        if len(set(ids)) != 3 or any(not value for value in ids):
            raise ValueError("BGM direction IDs must be unique and non-empty")
        for direction in directions:
            if not direction.get("prompt") or not direction.get("story_rationale"):
                raise ValueError("Each BGM direction needs a prompt and story rationale")
    output_dir = root / "campaigns" / campaign / "production" / "bgm-v2-5"
    contract = {
        "schema_version": 1, "engine_api_version": "2.5", "campaign": campaign,
        "stage": "BGM_STRATEGY_AND_CANDIDATE_CONTRACT",
        "status": "READY_FOR_CANDIDATE_GENERATION" if strategy["mode"] != "no_bgm" else "BGM_DECLINED_PRESERVE_SILENT_MASTER",
        "silent_master": str(silent_master), "silent_master_sha256": sha256(silent_master),
        "final_story_contract": str(final_story_contract), "final_story_contract_sha256": sha256(final_story_contract),
        "sound_strategy": strategy, "directions": directions,
        "generation_requirements": {
            "original_music_only": strategy["mode"] == "original_bgm",
            "record_provider_model_prompt_task_id_and_hashes": True,
            "deterministic_mix_with_ffmpeg": True,
            "default_loudness_target": "-16 LUFS", "default_true_peak_limit": "-1.5 dBTP",
            "visual_pixels_must_remain_unchanged": True,
        },
        "publication_authorized": False, "created_at": utc_now(),
    }
    write_json(output_dir / "bgm-stage-contract.json", contract)
    return contract


def review_contract(candidate_ids: list[str]) -> dict[str, Any]:
    if len(candidate_ids) != 3 or len(set(candidate_ids)) != 3:
        raise ValueError("Review contract requires three unique candidate IDs")
    return {
        "schema_version": 1, "candidate_ids": candidate_ids,
        "common_evidence": ["sound_strategy", "story_contract", "beat_map", "candidate_manifest", "prior_reviews"],
        "claude": {"required_evidence": ["complete_visual_timeline_for_each_mix", "spectrogram", "loudness_report"], "authority": ["visual_competition", "subtitle_readability", "structural_compatibility"], "must_not_claim": ["heard_audio_quality", "mix_balance", "musical_pacing"]},
        "minimax": {"required_evidence": ["all_three_complete_audio_video_candidates"], "authority": ["heard_music_quality", "story_sync", "pacing", "mix_balance", "fatigue", "ending_resolution"], "must_select_one_candidate": True},
        "kimi": {"required_evidence": ["sanitized_dossier", "beat_map", "prompts", "candidate_and_mix_hashes", "claude_and_minimax_reviews"], "authority": ["story_contract_alignment", "provenance", "cross_stage_integrity", "rights_record_completeness"], "must_not_claim": ["heard_audio_quality", "mix_balance", "visual_aesthetics"]},
        "codex": {"authority": ["evidence_validation", "technical_qc", "selection_adjudication", "rerender", "persistence"], "selection_rule": "MiniMax selects heard performance; Claude can block visual interference; Kimi can block contract or provenance failure."},
        "publication_authorized": False,
    }


def validate_candidate_manifest(contract: dict[str, Any], manifest: dict[str, Any]) -> None:
    candidates = manifest.get("candidates", [])
    expected = {item["id"] for item in contract["directions"]}
    actual = {item.get("id") for item in candidates}
    if actual != expected or len(candidates) != 3:
        raise ValueError("Candidate manifest does not match the three approved directions")
    if manifest.get("source_silent_master_sha256") != contract["silent_master_sha256"]:
        raise ValueError("Candidate generation used the wrong silent master")
    required = {"id", "provider", "model", "prompt", "task_id", "audio", "audio_sha256", "mix", "mix_sha256", "technical_qc"}
    for candidate in candidates:
        if required - set(candidate):
            raise ValueError("Candidate provenance record is incomplete")
        if candidate["technical_qc"] != "PASS":
            raise ValueError("Candidate failed technical QC")


def adjudicate_bgm_reviews(candidate_ids: list[str], claude: dict[str, Any], minimax: dict[str, Any], kimi: dict[str, Any]) -> dict[str, Any]:
    for name, review in (("claude", claude), ("minimax", minimax), ("kimi", kimi)):
        if not review.get("evidence_complete"):
            raise ValueError(f"{name} BGM review lacks complete required evidence")
    selected = minimax.get("selected")
    if selected not in candidate_ids:
        raise ValueError("MiniMax must select one valid candidate from complete audio-video evidence")
    claude_domains = {"visual_competition", "subtitle_readability", "structural_compatibility"}
    kimi_domains = {"story_contract_alignment", "provenance", "cross_stage_integrity", "rights_record_completeness"}
    claude_blockers = [item for item in claude.get("findings", []) if item.get("severity") == "blocking" and item.get("domain") in claude_domains]
    kimi_blockers = [item for item in kimi.get("findings", []) if item.get("severity") == "blocking" and item.get("domain") in kimi_domains]
    if claude_blockers or kimi_blockers:
        return {"status": "CODEX_ADJUDICATION", "selected_by_minimax": selected, "binding_blockers": claude_blockers + kimi_blockers, "publication_authorized": False}
    return {"status": "BGM_SELECTED_PENDING_FINAL_MIX_QC", "selected": selected, "selection_authority": "minimax_complete_audio_video", "claude_clearance": "PASS", "kimi_integrity_clearance": "PASS", "publication_authorized": False}


def finalize_dual_master(silent_master: Path, selected_mix: Path, destination: Path, expected_silent_sha256: str, expected_mix_sha256: str) -> dict[str, Any]:
    if sha256(silent_master) != expected_silent_sha256:
        raise ValueError("Silent master changed before BGM finalization")
    if sha256(selected_mix) != expected_mix_sha256:
        raise ValueError("Selected BGM mix hash mismatch")
    if destination.resolve() == silent_master.resolve():
        raise ValueError("BGM master must never overwrite the silent master")
    if destination.exists():
        raise FileExistsError("BGM master destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected_mix, destination)
    if sha256(silent_master) != expected_silent_sha256:
        raise RuntimeError("Silent master changed during finalization")
    return {"status": "BGM_MASTER_CREATED_NOT_PUBLISHED", "silent_master": str(silent_master), "silent_master_sha256": expected_silent_sha256, "bgm_master": str(destination), "bgm_master_sha256": sha256(destination), "silent_master_preserved": True, "publication_authorized": False}
