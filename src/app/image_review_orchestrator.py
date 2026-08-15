from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.head_discovery import current_head, head_chain
from app.planning_orchestrator import read_json, write_json
from app.planning_privacy import read_policy
from app.review_policy import aggregate_reviews, utc_now, validate_review


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type(path: Path) -> str:
    return {".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower(), "image/jpeg")


def data_url(path: Path) -> str:
    return f"data:{media_type(path)};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _project_context(root: Path, project: str, campaign: str) -> dict[str, Any]:
    project_dir = root / "projects" / project
    campaign_dir = root / "campaigns" / campaign
    head_path = current_head(root)
    chain = head_chain(root, head_path)
    decisions = []
    decision_paths = []
    for _, head in chain:
        for relative in head.get("active_decisions", []):
            if relative not in decision_paths:
                decision_paths.append(relative)
    for relative in decision_paths:
        path = root / relative
        if path.is_file():
            decisions.append({"path": relative, "content": read_json(path)})
    return {
        "brief": read_text(campaign_dir / "brief.yaml"),
        "project": read_text(project_dir / "project.yaml"),
        "project_decisions": read_text(project_dir / "PROJECT_DECISIONS.md"),
        "active_head": str(head_path.relative_to(root)).replace("\\", "/"),
        "head_chain": [str(path.relative_to(root)).replace("\\", "/") for path, _ in chain],
        "active_decisions": decisions,
    }


def validate_candidate_set(root: Path, campaign: str, candidate_set: dict[str, Any]) -> None:
    required = {"schema_version", "campaign", "set_id", "purpose", "platforms", "candidates"}
    missing = required - set(candidate_set)
    if missing:
        raise ValueError(f"Candidate set missing fields: {sorted(missing)}")
    if candidate_set["campaign"] != campaign:
        raise ValueError("Candidate set campaign does not match command campaign")
    if len(candidate_set["candidates"]) < 2:
        raise ValueError("Image review requires at least two candidates")
    ids = [item.get("id") for item in candidate_set["candidates"]]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Candidate IDs must be non-empty and unique")
    for item in candidate_set["candidates"]:
        path = root / item["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError(f"Unsupported candidate image: {path}")
        if not item.get("provenance"):
            raise ValueError(f"Candidate {item['id']} has no provenance")


def find_privacy_conflicts(candidate_set: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, str]]:
    quarantined = {
        rule["asset_id"]
        for rule in policy.get("rules", [])
        if not rule.get("external_model_pixels_allowed", False)
    }
    conflicts = []
    for item in candidate_set.get("candidates", []):
        searchable = json.dumps(item, ensure_ascii=False)
        for asset_id in quarantined:
            if item.get("asset_id") == asset_id or asset_id in item.get("path", "") or asset_id in searchable:
                conflicts.append({"candidate_id": item["id"], "asset_id": asset_id})
    return conflicts


def prepare_image_review(root: Path, project: str, campaign: str, candidate_path: Path) -> dict[str, Any]:
    if not candidate_path.is_absolute():
        candidate_path = root / candidate_path
    candidate_set = read_json(candidate_path)
    validate_candidate_set(root, campaign, candidate_set)
    policy_path = root / "policies" / "privacy_quarantine.json"
    conflicts = find_privacy_conflicts(candidate_set, read_policy(policy_path))
    if conflicts:
        raise ValueError(f"Candidate set references quarantined pixels: {conflicts}")
    evidence = []
    for item in candidate_set["candidates"]:
        path = root / item["path"]
        evidence.append({
            "candidate_id": item["id"],
            "path": item["path"],
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "media_type": media_type(path),
            "provenance": item["provenance"],
            "intended_platforms": item.get("intended_platforms", candidate_set["platforms"]),
            "visible_text": item.get("visible_text", []),
        })
    request = {
        "schema_version": 1,
        "created_at": utc_now(),
        "project": project,
        "campaign": campaign,
        "candidate_set_path": str(candidate_path.relative_to(root)).replace("\\", "/"),
        "candidate_set": candidate_set,
        "project_context": _project_context(root, project, campaign),
        "evidence_manifest": {
            "complete_candidate_set": True,
            "candidate_count": len(evidence),
            "candidates": evidence,
        },
        "review_dimensions": [
            "composition", "subject_clarity", "authenticity", "color", "typography",
            "thumbnail_readability", "platform_crop_safety", "brand_consistency",
            "visible_privacy", "factual_and_publication_risk",
        ],
        "privacy_preflight": {
            "status": "PASS",
            "policy": "policies/privacy_quarantine.json",
            "quarantined_candidate_references": [],
        },
        "owner_gate": "Only factual/privacy uncertainty, incompatible direction, or revision limit. Ordinary image choices are handled by Codex.",
    }
    review_dir = candidate_path.parent / "reviews"
    write_json(review_dir / "image-review-request-sanitized.json", request)
    write_json(review_dir / "image-evidence-manifest.json", request["evidence_manifest"])
    write_json(review_dir / "image-cycle-state.json", {
        "campaign": campaign, "set_id": candidate_set["set_id"],
        "status": "READY_FOR_MODEL_REVIEW", "api_calls_performed": False,
        "updated_at": utc_now(),
    })
    return request


def contract(candidate_ids: list[str]) -> str:
    allowed = " | ".join(candidate_ids + ["NONE"])
    return f'''Return strict JSON only:
{{"reviewer":"string","decision":"PASS | REVISE | HUMAN_REVIEW","recommended_candidate":"{allowed}","candidate_findings":[{{"candidate_id":"string","strengths":["string"],"weaknesses":["string"],"platform_crop_notes":["string"]}}],"scores":{{"visual_quality":1-10,"authenticity":1-10,"brand_consistency":1-10,"platform_fit":1-10,"risk":1-10}},"blocking_issues":[{{"id":"string","location":"candidate id","problem":"string","required_change":"string"}}],"optional_suggestions":["string"],"summary":"string"}}
Every candidate must have one candidate_findings entry. Risk means publication risk: 1 is minimal and 10 is highest. PASS requires zero blockers and risk 1-6. Use HUMAN_REVIEW only for genuine factual/privacy uncertainty.'''


def validate_image_review(review: dict[str, Any], candidate_ids: list[str]) -> None:
    validate_review(review)
    if review.get("recommended_candidate") not in set(candidate_ids + ["NONE"]):
        raise ValueError("recommended_candidate is not in the candidate set")
    findings = review.get("candidate_findings")
    if not isinstance(findings, list) or {x.get("candidate_id") for x in findings} != set(candidate_ids):
        raise ValueError("Every candidate must have exactly one findings entry")


def normalize_nonblocking_revision(review: dict[str, Any]) -> dict[str, Any]:
    if (
        review.get("decision") == "REVISE"
        and review.get("blocking_issues") == []
        and review.get("scores", {}).get("risk", 10) <= 6
    ):
        review["contract_normalization"] = {
            "original_decision": "REVISE",
            "normalized_decision": "PASS",
            "reason": "No blocking issue and publication risk is not high; all requested changes are optional suggestions.",
        }
        review["decision"] = "PASS"
    return review


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:3000]}") from exc


def parse(text: str) -> dict[str, Any]:
    return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I))


def _text_context(request: dict[str, Any]) -> dict[str, Any]:
    return {key: request[key] for key in (
        "project", "campaign", "candidate_set", "project_context", "evidence_manifest",
        "review_dimensions", "privacy_preflight", "owner_gate",
    )}


def call_claude(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not loaded")
    ids = [x["id"] for x in request["candidate_set"]["candidates"]]
    prompt = "You are Claude, the independent visual image and cover reviewer. Compare the complete candidate set, not isolated selections. Inspect visual hierarchy, subject clarity, authenticity, typography, mobile thumbnail readability, Instagram/Reels and YouTube Shorts crop safety, visible privacy, and consistency with the complete brief and active decisions. Do not infer purity, potency, efficacy, consumption, or manufacturing claims.\n\n" + contract(ids) + "\n\nREQUEST:\n" + json.dumps(_text_context(request), ensure_ascii=False)
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for item in request["evidence_manifest"]["candidates"]:
        path = root / item["path"]
        content.extend([
            {"type": "image", "source": {"type": "base64", "media_type": item["media_type"], "data": base64.b64encode(path.read_bytes()).decode("ascii")}},
            {"type": "text", "text": f"Candidate {item['candidate_id']} 閳?{item['path']}"},
        ])
    raw = post_json("https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, {"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"), "max_tokens": 5000, "thinking": {"type": "disabled"}, "output_config": {"effort": "low"}, "messages": [{"role": "user", "content": content}]})
    text = "\n".join(x.get("text", "") for x in raw.get("content", []) if x.get("type") == "text")
    review = normalize_nonblocking_revision(parse(text))
    validate_image_review(review, ids)
    return review, raw


def call_minimax(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY is not loaded")
    ids = [x["id"] for x in request["candidate_set"]["candidates"]]
    prompt = "You are MiniMax M3, the second independent multimodal image and cover reviewer. Compare every candidate against the complete brief, active facts, provenance and platform use. Evaluate artifacts, authenticity, text readability, crop safety, visual variety, publication risk and whether ComfyUI or generated-media provenance is accurately declared. Do not invent product claims.\n\n" + contract(ids) + "\n\nREQUEST:\n" + json.dumps(_text_context(request), ensure_ascii=False)
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for item in request["evidence_manifest"]["candidates"]:
        content.extend([
            {"type": "input_image", "image_url": {"url": data_url(root / item["path"]), "detail": "high"}},
            {"type": "input_text", "text": f"Candidate {item['candidate_id']} 閳?{item['path']}"},
        ])
    raw = post_json("https://api.minimax.io/v1/responses", {"Authorization": f"Bearer {key}", "content-type": "application/json"}, {"model": os.environ.get("MINIMAX_REVIEW_MODEL", "MiniMax-M3"), "instructions": "Return strict JSON only.", "input": [{"type": "message", "role": "user", "content": content}], "reasoning": {"effort": "none"}, "max_output_tokens": 5000, "stream": False})
    if raw.get("status") != "completed":
        raise RuntimeError(f"MiniMax incomplete: {raw.get('status')}: {raw.get('error')}")
    review = normalize_nonblocking_revision(parse(raw.get("output_text", "")))
    validate_image_review(review, ids)
    return review, raw


def run_image_review(root: Path, request: dict[str, Any], revision_count: int = 0) -> dict[str, Any]:
    candidate_path = root / request["candidate_set_path"]
    review_dir = candidate_path.parent / "reviews"
    claude, claude_raw = call_claude(root, request)
    minimax, minimax_raw = call_minimax(root, request)
    write_json(review_dir / "claude-image-review.json", claude)
    write_json(review_dir / "claude-image-raw-response.json", claude_raw)
    write_json(review_dir / "minimax-image-review.json", minimax)
    write_json(review_dir / "minimax-image-raw-response.json", minimax_raw)
    aggregation = aggregate_reviews(claude, minimax, revision_count)
    if aggregation["next_action"] == "FINAL_CANDIDATE":
        choices = {claude["recommended_candidate"], minimax["recommended_candidate"]}
        if len(choices) == 1 and "NONE" not in choices:
            aggregation["next_action"] = "CODEX_FINALIZE_IMAGE_CANDIDATE"
            aggregation["recommended_candidate"] = next(iter(choices))
            aggregation["reason"] = "both_reviewers_passed_and_agreed"
        else:
            aggregation["next_action"] = "CODEX_ADJUDICATION"
            aggregation["reason"] = "reviewers_passed_but_candidate_recommendations_differ"
    write_json(review_dir / "image-review-aggregation.json", aggregation)
    write_json(review_dir / "image-cycle-state.json", {
        "campaign": request["campaign"], "set_id": request["candidate_set"]["set_id"],
        "status": aggregation["next_action"], "api_calls_performed": True,
        "models": {"claude": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"), "minimax": os.environ.get("MINIMAX_REVIEW_MODEL", "MiniMax-M3")},
        "updated_at": utc_now(),
    })
    return aggregation
