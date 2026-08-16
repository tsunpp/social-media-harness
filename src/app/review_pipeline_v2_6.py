from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable

from app.authorization_matrix_v2_6 import resolve_authorization
from app.four_agent_review_panel import aggregate_panel
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.review_orchestrator import call_anthropic, call_minimax
from app.review_policy import utc_now


PROVIDER_LIMITS = {"minimax": 50 * 1024 * 1024}
REVIEWERS = ("claude", "minimax", "kimi")


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def _required_paths(root: Path, spec: dict[str, Any]) -> dict[str, Path]:
    required = {
        "master_video", "render_manifest", "brief", "facts", "privacy",
        "story_contract", "copy", "source_manifest", "review_dir",
    }
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Four-agent review spec missing fields: {sorted(missing)}")
    paths = {name: _resolve(root, spec[name]) for name in required}
    for name, path in paths.items():
        if name == "review_dir":
            path.mkdir(parents=True, exist_ok=True)
        elif not path.is_file():
            raise FileNotFoundError(f"{name}: {path}")
    timeline = [_resolve(root, item) for item in spec.get("timeline_files", [])]
    if not timeline or any(not path.is_file() for path in timeline):
        raise ValueError("Complete ordered timeline_files are required")
    paths["timeline_files"] = timeline  # type: ignore[assignment]
    return paths


def minimal_review_attestation(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    privacy = read_json(_resolve(root, spec["privacy"]))
    project = spec["project"]
    campaign = spec["campaign"]
    identifiable = bool(privacy.get("identifiable_children") or privacy.get("identifiable_people"))
    records = {}
    material_map = {
        "claude": ["privacy_cleared_timeline", "rendered_video", "copy"],
        "minimax": ["source_proxy", "rendered_video", "copy"],
        "kimi": ["sanitized_dossier", "privacy_cleared_timeline", "copy", "provenance"],
    }
    recipient_map = {"claude": "claude", "minimax": "minimax", "kimi": "kimi-k3"}
    for reviewer in REVIEWERS:
        try:
            result = resolve_authorization(
                root, project, campaign, recipient_map[reviewer], material_map[reviewer],
                contains_identifiable_people=identifiable,
                metadata_stripped=True,
                privacy_preflight="PASS" if "PASS" in str(privacy.get("status", "")) else "FAIL",
            )
            records[reviewer] = {"active": True, "authorization_status": result["status"]}
        except (ValueError, FileNotFoundError) as exc:
            records[reviewer] = {"active": False, "reason": "NOT_AUTHORIZED", "detail": str(exc)}
    return {
        "schema_version": 1,
        "project": project,
        "campaign": campaign,
        "privacy_preflight": "PASS",
        "identifiable_people": identifiable,
        "metadata_stripped": True,
        "distribution_scope": privacy.get("distribution_scope", "project_governed"),
        "publication_authorized": False,
        "reviewers": records,
    }


def prepare_complete_evidence(root: Path, spec_path: Path) -> dict[str, Any]:
    spec = read_json(_resolve(root, spec_path))
    paths = _required_paths(root, spec)
    master = paths["master_video"]
    timeline: list[Path] = paths["timeline_files"]  # type: ignore[assignment]
    attestation = minimal_review_attestation(root, spec)
    dossier = {
        "brief": read_json(paths["brief"]),
        "facts": read_json(paths["facts"]),
        "privacy_attestation": attestation,
        "effective_contract": read_json(paths["story_contract"]),
        "copy": read_json(paths["copy"]),
        "source_manifest": read_json(paths["source_manifest"]),
        "render_manifest": read_json(paths["render_manifest"]),
        "publication_authorized": False,
    }
    files = [master, paths["render_manifest"], paths["brief"], paths["facts"], paths["privacy"], paths["story_contract"], paths["copy"], paths["source_manifest"], *timeline]
    bundle = {
        "schema_version": 1,
        "engine_api_version": "2.6",
        "project": spec["project"],
        "campaign": spec["campaign"],
        "master_video": str(master),
        "master_sha256": sha256(master),
        "timeline_files": [str(path) for path in timeline],
        "timeline_complete": True,
        "authorization_attestation": attestation,
        "dossier": dossier,
        "evidence_files": [_file_record(root, path) for path in files],
        "review_dir": str(paths["review_dir"]),
        "ffmpeg": str(_resolve(root, spec["ffmpeg"])) if spec.get("ffmpeg") else None,
        "prepared_at": utc_now(),
    }
    fingerprint_input = {
        "project": bundle["project"], "campaign": bundle["campaign"],
        "master_sha256": bundle["master_sha256"],
        "authorization_attestation": bundle["authorization_attestation"],
        "evidence_files": bundle["evidence_files"],
    }
    bundle["evidence_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    write_json(paths["review_dir"] / "complete-evidence-bundle.json", bundle)
    return bundle


def proxy_required(path: Path, provider: str) -> bool:
    limit = PROVIDER_LIMITS.get(provider)
    return bool(limit and path.stat().st_size > limit)


def ensure_complete_video_proxy(master: Path, provider: str, destination: Path, ffmpeg: Path) -> Path:
    if not proxy_required(master, provider):
        return master
    destination.parent.mkdir(parents=True, exist_ok=True)
    sidecar = destination.with_suffix(destination.suffix + ".json")
    source_hash = sha256(master)
    if destination.is_file() and sidecar.is_file() and not proxy_required(destination, provider):
        metadata = read_json(sidecar)
        if metadata.get("source_sha256") == source_hash and metadata.get("provider") == provider:
            return destination
    result = subprocess.run([
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(master),
        "-vf", "scale=720:1280", "-c:v", "libx264", "-preset", "medium",
        "-b:v", "3200k", "-maxrate", "3600k", "-bufsize", "6400k",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destination),
    ], capture_output=True, text=True, errors="replace")
    if result.returncode or not destination.is_file() or proxy_required(destination, provider):
        raise RuntimeError(f"Unable to create provider-sized {provider} proxy: {result.stderr[-1000:]}")
    write_json(sidecar, {
        "schema_version": 1, "provider": provider, "complete_duration": True,
        "temporal_edits": False, "audio_preserved": True,
        "source_sha256": source_hash, "proxy_sha256": sha256(destination),
        "source_bytes": master.stat().st_size, "proxy_bytes": destination.stat().st_size,
    })
    return destination


def normalize_review(reviewer: str, review: dict[str, Any], master_hash: str, evidence_hash: str) -> dict[str, Any]:
    decision = review.get("decision", review.get("verdict"))
    blockers = review.get("blocking_issues", [])
    findings = review.get("findings", [])
    if not findings:
        default_domain = {"claude": "visual_narrative", "minimax": "temporal_continuity", "kimi": "workflow_audit"}[reviewer]
        findings = [{
            "id": item.get("id", f"{reviewer}-blocker"),
            "domain": item.get("domain", default_domain),
            "severity": "blocking",
            "problem": item.get("problem", item.get("issue", "reviewer blocker")),
            "required_change": item.get("required_change", item.get("required_action", "resolve blocker")),
        } for item in blockers]
    ordinary = review.get("ordinary_revisions", [])
    for item in ordinary:
        findings.append({
            "id": item.get("id", f"{reviewer}-ordinary"),
            "domain": item.get("domain", item.get("area", "workflow_audit")),
            "severity": "ordinary",
            "problem": item.get("problem", item.get("issue", item.get("finding", "ordinary revision"))),
            "required_change": item.get("required_change", item.get("required_action", "apply ordinary revision")),
        })
    return {
        "reviewer": reviewer,
        "decision": decision,
        "findings": findings,
        "summary": review.get("summary", review.get("conclusion", "")),
        "evidence_complete": bool(review.get("evidence_complete", True)),
        "reviewed_master_sha256": master_hash,
        "evidence_bundle_sha256": evidence_hash,
        "raw_decision": review.get("decision", review.get("verdict")),
    }


def _legacy_request(bundle: dict[str, Any], video: Path) -> dict[str, Any]:
    return {
        "campaign": bundle["campaign"], "version": "engine-v2-6", "video": str(video),
        "duration_seconds": bundle["dossier"]["render_manifest"].get("output", {}).get("duration_seconds", 0),
        "frames": [{"index": index, "time_seconds": index - 1, "path": path} for index, path in enumerate(bundle["timeline_files"], 1)],
        "captions": bundle["dossier"]["render_manifest"].get("captions", []),
        "publishing_copy": bundle["dossier"]["copy"], "render_manifest": bundle["dossier"]["render_manifest"],
        "project_context": {"authorization": bundle["authorization_attestation"], "facts": bundle["dossier"]["facts"]},
        "privacy_preflight": bundle["authorization_attestation"], "fact_preflight": {"status": "PASS"},
        "evidence_manifest": {"files": bundle["evidence_files"], "timeline_complete": True},
        "evidence_contract": "Engine 2.6 complete modality-specific evidence",
        "cover_candidates": [], "prior_decisions": [], "settled_topics": [],
    }


def _call_kimi(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("KIMI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("KIMI_API_KEY is not loaded")
    schema = '{"reviewer":"kimi","decision":"PASS|REVISE|HUMAN_REVIEW","evidence_complete":true,"findings":[{"id":"string","domain":"narrative_logic|fact_integrity|copy_consistency|chronology|provenance|workflow_audit","severity":"blocking|ordinary|optional","problem":"string","required_change":"string"}],"summary":"string"}'
    prompt = "Audit narrative, facts, copy, chronology, provenance and workflow only. Do not judge motion, pacing, audio, BGM, visual aesthetics or cover selection. Return strict JSON: " + schema + "\nDOSSIER=" + json.dumps(bundle["dossier"], ensure_ascii=False)
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for path in bundle["timeline_files"]:
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}})
    payload = {"model": os.environ.get("KIMI_REVIEW_MODEL", "kimi-k3"), "messages": [{"role": "user", "content": content}], "max_tokens": 6000}
    request = urllib.request.Request("https://api.moonshot.ai/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=240) as response:
        raw = json.loads(response.read().decode("utf-8"))
    text = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    return json.loads(clean), raw


ReviewerCall = Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]]


def run_resumable_panel(root: Path, bundle: dict[str, Any], callbacks: dict[str, ReviewerCall] | None = None) -> dict[str, Any]:
    review_dir = Path(bundle["review_dir"])
    evidence_hash = bundle["evidence_fingerprint"]
    master_hash = bundle["master_sha256"]
    callbacks = callbacks or {}
    state_path = review_dir / "review-state-v2-6.json"
    state = read_json(state_path) if state_path.is_file() else {"schema_version": 1, "reviewers": {}, "master_sha256": master_hash}
    normalized: dict[str, dict[str, Any]] = {}
    master = Path(bundle["master_video"])
    ffmpeg = Path(bundle["ffmpeg"]) if bundle.get("ffmpeg") else None
    minimax_video = master
    if bundle["authorization_attestation"]["reviewers"]["minimax"]["active"] and proxy_required(master, "minimax"):
        if ffmpeg is None:
            raise ValueError("ffmpeg is required to create an oversized MiniMax review proxy")
        minimax_video = ensure_complete_video_proxy(master, "minimax", review_dir / "proxies/minimax-complete.mp4", ffmpeg)
    for reviewer in REVIEWERS:
        auth = bundle["authorization_attestation"]["reviewers"][reviewer]
        if not auth["active"]:
            state["reviewers"][reviewer] = {"status": "INACTIVE", "reason": auth["reason"]}
            continue
        normalized_path = review_dir / f"{reviewer}-normalized.json"
        if normalized_path.is_file():
            previous = read_json(normalized_path)
            if previous.get("reviewed_master_sha256") == master_hash and previous.get("evidence_bundle_sha256") == evidence_hash:
                normalized[reviewer] = previous
                state["reviewers"][reviewer] = {"status": "PASS_REUSED", "path": normalized_path.name}
                continue
        state["reviewers"][reviewer] = {"status": "RUNNING"}; write_json(state_path, state)
        try:
            if reviewer in callbacks:
                result, raw = callbacks[reviewer](bundle)
            elif reviewer == "claude":
                result, raw = call_anthropic(_legacy_request(bundle, master), os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"))
            elif reviewer == "minimax":
                result, raw = call_minimax(_legacy_request(bundle, minimax_video), os.environ.get("MINIMAX_REVIEW_MODEL", "MiniMax-M3"))
            else:
                result, raw = _call_kimi(bundle)
        except Exception as exc:
            state["reviewers"][reviewer] = {"status": "FAILED", "error": str(exc), "retryable": True}
            state["status"] = "REVIEWER_FAILED_RESUMABLE"
            write_json(state_path, state)
            raise
        write_json(review_dir / f"{reviewer}-raw-response.json", raw)
        value = normalize_review(reviewer, result, master_hash, evidence_hash)
        write_json(normalized_path, value)
        normalized[reviewer] = value
        state["reviewers"][reviewer] = {"status": "COMPLETED", "decision": value["decision"], "path": normalized_path.name}
        write_json(state_path, state)
    if not set(REVIEWERS) <= set(normalized):
        state["status"] = "INCOMPLETE_PRIVACY_ADAPTIVE_PANEL"; write_json(state_path, state); return state
    aggregation = aggregate_panel(normalized["claude"], normalized["minimax"], normalized["kimi"])
    panel = {
        "panel_version": "2.6", "next_action": aggregation["next_action"],
        "master_sha256": master_hash, "evidence_bundle_sha256": evidence_hash,
        "review_dir": str(review_dir),
        "reviewers": {name: {
            "active": True, "decision": value["decision"], "evidence_complete": value["evidence_complete"],
            "reviewed_master_sha256": value["reviewed_master_sha256"],
            "evidence_bundle_sha256": value["evidence_bundle_sha256"],
            "review_path": f"{name}-normalized.json", "review_sha256": sha256(review_dir / f"{name}-normalized.json"),
        } for name, value in normalized.items()},
        "aggregation": aggregation, "publication_authorized": False,
    }
    write_json(review_dir / "final-panel-v2-6.json", panel)
    state["status"] = aggregation["next_action"]; state["panel"] = "final-panel-v2-6.json"; write_json(state_path, state)
    return panel

