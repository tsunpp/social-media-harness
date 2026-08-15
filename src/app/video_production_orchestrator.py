from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.head_discovery import current_head, head_chain
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.planning_privacy import read_policy
from app.review_orchestrator import duration_from, run_models, sample_times
from app.review_policy import utc_now


PIXEL_ROLES = {"source_image", "source_video", "generated_insert", "rendered_video", "cover"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def inherited_context(root: Path, project: str, campaign: str) -> dict[str, Any]:
    head = current_head(root)
    chain = head_chain(root, head)
    decision_paths: list[str] = []
    for _, record in chain:
        for relative in record.get("active_decisions", []):
            if relative not in decision_paths:
                decision_paths.append(relative)
    return {
        "active_head": str(head.relative_to(root)).replace("\\", "/"),
        "head_chain": [str(path.relative_to(root)).replace("\\", "/") for path, _ in chain],
        "brief": _read_text(root / "campaigns" / campaign / "brief.yaml"),
        "project": _read_text(root / "projects" / project / "project.yaml"),
        "project_decisions": _read_text(root / "projects" / project / "PROJECT_DECISIONS.md"),
        "active_decisions": [
            {"path": relative, "content": read_json(root / relative)}
            for relative in decision_paths if (root / relative).is_file()
        ],
    }


def validate_job(root: Path, campaign: str, job: dict[str, Any]) -> None:
    required = {"schema_version", "campaign", "job_id", "version", "output", "render_manifest", "artifacts", "backends", "revision_policy"}
    missing = required - set(job)
    if missing:
        raise ValueError(f"Video production job missing fields: {sorted(missing)}")
    if job["campaign"] != campaign:
        raise ValueError("Video production job campaign mismatch")
    auto_revision_limit = job["revision_policy"].get("auto_revision_limit")
    if not isinstance(auto_revision_limit, int) or not 1 <= auto_revision_limit <= 10:
        raise ValueError("Video production auto_revision_limit must be between 1 and 10")
    for relative in (job["output"], job["render_manifest"]):
        if not (root / relative).is_file():
            raise FileNotFoundError(root / relative)
    ids = [item.get("artifact_id") for item in job["artifacts"]]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Artifact IDs must be non-empty and unique")
    for item in job["artifacts"]:
        path = root / item["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        for key in ("backend", "role", "included_in_final", "provenance"):
            if key not in item:
                raise ValueError(f"Artifact {item['artifact_id']} missing {key}")


def privacy_conflicts(job: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, str]]:
    blocked = {x["asset_id"] for x in policy.get("rules", []) if not x.get("external_model_pixels_allowed", False)}
    conflicts = []
    for item in job.get("artifacts", []):
        if item.get("role") not in PIXEL_ROLES:
            continue
        blob = json.dumps(item, ensure_ascii=False)
        for asset_id in blocked:
            if asset_id in blob:
                conflicts.append({"artifact_id": item["artifact_id"], "asset_id": asset_id})
    return conflicts


def prompt_fact_conflicts(job: dict[str, Any], context: dict[str, Any]) -> list[dict[str, str]]:
    rules = []
    for item in context["active_decisions"]:
        content = item["content"]
        for phrase in content.get("forbidden_phrases", []):
            rules.append((phrase.lower(), item["path"]))
    conflicts = []
    for artifact in job.get("artifacts", []):
        if not artifact.get("included_in_final") or artifact.get("status") == "historical_capability_evidence_only":
            continue
        prompt = artifact.get("prompt", "").lower()
        for phrase, source in rules:
            if phrase and phrase in prompt:
                conflicts.append({"artifact_id": artifact["artifact_id"], "phrase": phrase, "rule": source})
    return conflicts


def _extract_frames(root: Path, video: Path, review_dir: Path, duration: float, captions: list[dict[str, Any]], ffmpeg: Path) -> list[dict[str, Any]]:
    frame_dir = review_dir / "timeline"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, timestamp in enumerate(sample_times(duration, captions), 1):
        path = frame_dir / f"frame-{index:03d}-{timestamp:06.2f}s.jpg"
        result = subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(timestamp), "-i", str(video), "-frames:v", "1", "-vf", "scale=540:960", "-q:v", "3", str(path)], capture_output=True, text=True, errors="replace")
        if result.returncode != 0 or not path.is_file():
            raise RuntimeError(f"Timeline extraction failed at {timestamp}s: {result.stderr[-500:]}")
        frames.append({"index": index, "time_seconds": timestamp, "path": str(path), "sha256": sha256(path)})
    return frames


def prepare_video_pipeline(root: Path, project: str, campaign: str, job_path: Path, ffmpeg: Path) -> dict[str, Any]:
    if not job_path.is_absolute():
        job_path = root / job_path
    job = read_json(job_path)
    validate_job(root, campaign, job)
    context = inherited_context(root, project, campaign)
    privacy = privacy_conflicts(job, read_policy(root / "policies" / "privacy_quarantine.json"))
    if privacy:
        raise ValueError(f"Video job references quarantined pixels: {privacy}")
    fact_conflicts = prompt_fact_conflicts(job, context)
    if fact_conflicts:
        raise ValueError(f"Production prompt conflicts with active facts: {fact_conflicts}")

    video = root / job["output"]
    manifest_path = root / job["render_manifest"]
    manifest = read_json(manifest_path)
    decode = subprocess.run([str(ffmpeg), "-hide_banner", "-v", "error", "-i", str(video), "-f", "null", "NUL"], capture_output=True, text=True, errors="replace")
    if decode.returncode != 0:
        raise ValueError(f"Technical decode gate failed: {decode.stderr[-1000:]}")
    duration = duration_from(manifest)
    captions = manifest.get("captions", [])
    review_dir = job_path.parent / "reviews" / "video-pipeline"
    frames = _extract_frames(root, video, review_dir, duration, captions, ffmpeg)
    artifacts = []
    for item in job["artifacts"]:
        path = root / item["path"]
        artifacts.append({**item, "bytes": path.stat().st_size, "sha256": sha256(path)})
    request = {
        "schema_version": 3,
        "created_at": utc_now(),
        "project": project,
        "campaign": campaign,
        "version": job["version"],
        "video": str(video),
        "manifest": str(manifest_path),
        "duration_seconds": duration,
        "captions": captions,
        "frames": frames,
        "render_manifest": manifest,
        "production_job": job,
        "artifact_registry": artifacts,
        "project_context": context,
        "prior_decisions": context["active_decisions"],
        "settled_topics": [],
        "publishing_copy": read_json(root / job["publishing_copy"]) if job.get("publishing_copy") else None,
        "cover_candidates": [str(root / path) for path in job.get("cover_candidates", [])],
        "privacy_preflight": {"status": "PASS", "conflicts": [], "policy": "policies/privacy_quarantine.json"},
        "fact_preflight": {"status": "PASS", "prompt_conflicts": []},
        "technical_gate": {"status": "PASS", "decode_return_code": 0},
        "evidence_contract": {
            "claude": "complete one-second image timeline plus every caption start/mid/end boundary and complete project/production context",
            "minimax": "complete rendered video with audio plus complete project/production context",
            "frame_count": len(frames),
        },
        "owner_gate": "Only privacy/factual uncertainty, incompatible reviewer requirements, revision limit, or final publish.",
    }
    evidence = {
        "schema_version": 1,
        "video": {"path": job["output"], "bytes": video.stat().st_size, "sha256": sha256(video)},
        "timeline_frames": [{"time_seconds": x["time_seconds"], "path": str(Path(x["path"]).relative_to(root)).replace("\\", "/"), "sha256": x["sha256"]} for x in frames],
        "artifacts": artifacts,
        "complete_timeline": True,
    }
    request["evidence_manifest"] = evidence
    write_json(review_dir / "video-review-request-sanitized.json", request)
    write_json(review_dir / "video-evidence-manifest.json", evidence)
    write_json(review_dir / "video-cycle-state.json", {"status": "READY_FOR_MODEL_REVIEW", "api_calls_performed": False, "revision_count": 0, "updated_at": utc_now()})
    return request


def run_video_pipeline_review(root: Path, request: dict[str, Any], revision_count: int) -> dict[str, Any]:
    source_dir = Path(request["video"]).parent / "reviews"
    target_dir = (root / request["production_job"]["job_manifest_path"]).parent / "reviews" / "video-pipeline" if request["production_job"].get("job_manifest_path") else source_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    state = run_models(request, revision_count, target_dir)
    state["revision_routes"] = request["production_job"]["revision_policy"]["routes"]
    state["complete_video_reviewed_by_minimax"] = True
    state["complete_timeline_reviewed_by_claude"] = True
    write_json(target_dir / "video-pipeline-state.json", state)
    return state
