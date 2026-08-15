from __future__ import annotations

from pathlib import Path
from typing import Any

from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_final_contract(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    required = {"final_story_contract", "render_manifest", "master_video", "publishing_copy", "platform"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Consistency spec missing fields: {sorted(missing)}")
    contract_path = _resolve(root, spec["final_story_contract"])
    render_path = _resolve(root, spec["render_manifest"])
    master_path = _resolve(root, spec["master_video"])
    copy_path = _resolve(root, spec["publishing_copy"])
    for path in (contract_path, render_path, master_path, copy_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    contract = read_json(contract_path)
    render = read_json(render_path)
    publishing = read_json(copy_path)
    output = render.get("output", {})
    mismatches: list[str] = []
    expected_duration = float(contract.get("final_duration_seconds", contract.get("target_duration_seconds", 0)))
    actual_duration = float(output.get("duration_seconds", render.get("duration_seconds", 0)))
    if abs(expected_duration - actual_duration) > float(spec.get("duration_tolerance_seconds", 0.25)):
        mismatches.append("duration")
    expected_audio = contract.get("audio", {})
    actual_audio = output.get("audio") not in {False, None, "none", "silent"}
    if bool(expected_audio.get("bgm_primary") or expected_audio.get("bgm_present")) != actual_audio:
        mismatches.append("audio_strategy")
    if contract.get("publication_authorized", False) or publishing.get("publishing_authorized", False):
        mismatches.append("publication_authority")
    if publishing.get("platform") not in {None, spec["platform"]}:
        mismatches.append("platform")
    expected_hash = render.get("master_sha256") or output.get("sha256")
    actual_hash = sha256(master_path)
    if expected_hash and str(expected_hash).upper() != actual_hash.upper():
        mismatches.append("master_sha256")
    if mismatches:
        raise ValueError(f"Final contract/render mismatch: {sorted(mismatches)}")
    return {
        "schema_version": 1,
        "engine_api_version": "2.6",
        "status": "PASS",
        "platform": spec["platform"],
        "contract_sha256": sha256(contract_path),
        "render_manifest_sha256": sha256(render_path),
        "master_sha256": actual_hash,
        "publishing_copy_sha256": sha256(copy_path),
        "publication_authorized": False,
    }

