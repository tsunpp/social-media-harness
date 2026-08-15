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

from app.review_policy import aggregate_reviews, utc_now, validate_review


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def describe(root: Path, path: Path, role: str) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_asset(root: Path, asset_id: str) -> dict[str, Any]:
    path = root / "asset_library" / "catalog" / f"{asset_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Asset catalog record missing: {asset_id}")
    record = read_json(path)
    record["catalog_record"] = str(path.relative_to(root)).replace("\\", "/")
    return record


def manifest_asset_ids(source_manifest: dict[str, Any]) -> list[str]:
    """Accept legacy ID lists and current self-describing ingest records."""
    result: list[str] = []
    for item in source_manifest.get("assets", []):
        asset_id = item.get("asset_id") if isinstance(item, dict) else item
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("Every source manifest asset must be an ID or contain asset_id")
        result.append(asset_id)
    return result


def validate_plan_options(plan: dict[str, Any], campaign: str) -> None:
    if plan.get("schema_version") != 1 or plan.get("campaign") != campaign:
        raise ValueError("Plan schema_version or campaign does not match")
    options = plan.get("options")
    if not isinstance(options, list) or len(options) != 3:
        raise ValueError("Planning review requires exactly three options")
    if {option.get("id") for option in options} != {"A", "B", "C"}:
        raise ValueError("Planning option IDs must be exactly A, B and C")
    required = {"name", "target_duration_seconds", "concept", "opening_hook", "timeline", "strength", "risk"}
    for option in options:
        missing = required - set(option)
        if missing:
            raise ValueError(f"Option {option.get('id')} missing fields: {sorted(missing)}")
        if not isinstance(option["timeline"], list) or len(option["timeline"]) < 4:
            raise ValueError(f"Option {option['id']} requires at least four timeline items")


def prepare_planning_context(root: Path, project: str, campaign: str) -> dict[str, Any]:
    project_dir = root / "projects" / project
    campaign_dir = root / "campaigns" / campaign
    brief_path = campaign_dir / "brief.yaml"
    source_manifest_path = campaign_dir / "source" / "manifest.json"
    source_manifest = read_json(source_manifest_path) if source_manifest_path.is_file() else {}
    blind = source_manifest.get("blind_context", {})
    project_config_path = campaign_dir / blind["project_config_override"] if blind.get("project_config_override") else project_dir / "project.yaml"
    project_decisions_path = campaign_dir / blind["project_decisions_override"] if blind.get("project_decisions_override") else project_dir / "PROJECT_DECISIONS.md"
    head_candidates = sorted((root / "memory").glob("HEAD*.json"))
    if not head_candidates:
        raise FileNotFoundError("No memory/HEAD*.json exists")
    required = [brief_path, source_manifest_path, project_config_path, project_decisions_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing planning inputs: " + ", ".join(missing))

    asset_records = [load_asset(root, asset_id) for asset_id in manifest_asset_ids(source_manifest)]
    image_paths: list[Path] = []
    video_paths: list[Path] = []
    files = [
        describe(root, brief_path, "campaign_brief"),
        describe(root, source_manifest_path, "source_manifest"),
        describe(root, project_config_path, "project_config"),
        describe(root, project_decisions_path, "project_decisions"),
    ]
    campaign_evidence: dict[str, Any] = {}
    for key, relative, role in (
        ("fact_contract", "source/fact-contract.json", "campaign_fact_contract"),
        ("privacy_review", "source/privacy-review.json", "campaign_privacy_review"),
        ("audience_scope", "decisions/audience-scope.json", "campaign_audience_scope"),
        ("format_exception", "decisions/photo-native-format-exception.json", "campaign_format_exception"),
    ):
        evidence_path = campaign_dir / relative
        if evidence_path.is_file():
            campaign_evidence[key] = {
                "path": str(evidence_path.relative_to(root)).replace("\\", "/"),
                "content": read_json(evidence_path),
            }
            files.append(describe(root, evidence_path, role))
    if not blind.get("enabled"):
        files.append(describe(root, head_candidates[-1], "recovery_head"))
    for asset in asset_records:
        catalog = root / asset["catalog_record"]
        files.append(describe(root, catalog, "asset_catalog"))
        thumbnail = root / asset["thumbnail_path"] if asset.get("thumbnail_path") else None
        if thumbnail and thumbnail.is_file():
            image_paths.append(thumbnail)
            files.append(describe(root, thumbnail, "asset_thumbnail"))
        for relative in asset.get("keyframes", []):
            path = root / relative
            if path.is_file():
                image_paths.append(path)
                files.append(describe(root, path, "video_keyframe"))
        proxy = root / asset["proxy_path"] if asset.get("proxy_path") else None
        if proxy and proxy.is_file():
            video_paths.append(proxy)
            files.append(describe(root, proxy, "video_proxy"))

    for relative in source_manifest.get("supplemental_images", []):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        image_paths.append(path)
        files.append(describe(root, path, "supplemental_timeline_evidence"))

    active_decisions = []
    head = read_json(head_candidates[-1])
    allowed_blind_decisions = set(blind.get("allowed_active_decisions", []))
    for relative in head.get("active_decisions", []):
        if blind.get("enabled") and relative not in allowed_blind_decisions:
            continue
        path = root / relative
        if path.is_file() and path.suffix.lower() == ".json":
            active_decisions.append({"path": relative, "content": read_json(path)})

    context = {
        "schema_version": 1,
        "created_at": utc_now(),
        "project": project,
        "campaign": campaign,
        "brief": {"path": str(brief_path.relative_to(root)).replace("\\", "/"), "raw": brief_path.read_text(encoding="utf-8-sig", errors="replace")},
        "project_config": {"path": str(project_config_path.relative_to(root)).replace("\\", "/"), "raw": project_config_path.read_text(encoding="utf-8-sig", errors="replace")},
        "project_decisions": project_decisions_path.read_text(encoding="utf-8-sig", errors="replace"),
        "active_decisions": active_decisions,
        "campaign_evidence": campaign_evidence,
        "source_manifest": source_manifest,
        "asset_records": asset_records,
        "evidence": {
            "asset_count": len(asset_records),
            "image_evidence_count": len(image_paths),
            "video_proxy_count": len(video_paths),
            "images": [str(path.relative_to(root)).replace("\\", "/") for path in image_paths],
            "videos": [str(path.relative_to(root)).replace("\\", "/") for path in video_paths],
            "files": files,
        },
        "evidence_contract": {
            "codex": "complete brief, project rules, active decisions, every asset catalog record, all thumbnails and systematic video keyframes",
            "claude": "complete planning text plus every asset thumbnail and every available systematic video keyframe",
            "minimax": "same complete planning text and image evidence plus every available video proxy for motion context",
        },
        "truth_precedence": "campaign blind snapshots and allowed active decisions override excluded history" if blind.get("enabled") else "active decisions from the latest HEAD override historical plan wording and superseded records",
        "blind_context": {"enabled": bool(blind.get("enabled")), "prior_creative_history_excluded": bool(blind.get("enabled")), "historical_head_content_loaded": not bool(blind.get("enabled")), "project_snapshot": str(project_config_path.relative_to(root)).replace("\\", "/"), "fact_snapshot": str(project_decisions_path.relative_to(root)).replace("\\", "/")},
        "next_action": "CODEX_CREATE_OR_UPDATE_THREE_PLAN_OPTIONS",
    }
    output = campaign_dir / "plans" / "planning-context.json"
    write_json(output, context)
    write_json(campaign_dir / "plans" / "planning-evidence-manifest.json", context["evidence"])
    return context


def prepare_plan_review(root: Path, project: str, campaign: str, plan_path: Path | None = None) -> dict[str, Any]:
    context = prepare_planning_context(root, project, campaign)
    path = plan_path or root / "campaigns" / campaign / "plans" / "plan_options.json"
    if not path.is_file():
        raise FileNotFoundError(f"Plan options not found: {path}")
    plan = read_json(path)
    validate_plan_options(plan, campaign)
    request = {
        "schema_version": 1,
        "created_at": utc_now(),
        "project": project,
        "campaign": campaign,
        "plan_path": str(path.relative_to(root)).replace("\\", "/"),
        "plan_options": plan,
        "planning_context": context,
        "owner_gate": "Both reviewers may assess and recommend, but initial creative direction remains an owner selection gate.",
    }
    review_dir = root / "campaigns" / campaign / "plans" / "reviews"
    write_json(review_dir / "planning-review-request.json", request)
    write_json(review_dir / "planning-cycle-state.json", {
        "campaign": campaign,
        "status": "READY_FOR_MODEL_REVIEW",
        "api_calls_performed": False,
        "updated_at": utc_now(),
    })
    return request


def contract() -> str:
    return """Return strict JSON only:
{"reviewer":"string","decision":"PASS | REVISE | HUMAN_REVIEW","recommended_option":"A | B | C | COMBINE | NONE","scores":{"visual_quality":1-10,"authenticity":1-10,"brand_consistency":1-10,"platform_fit":1-10,"risk":1-10},"blocking_issues":[{"id":"string","location":"string","problem":"string","required_change":"string"}],"optional_suggestions":["string"],"summary":"string"}
RISK SCALE IS DIRECTIONAL: risk=1 means no or minimal publication risk; risk=10 means the highest publication risk. It is not a quality, safety or confidence score. PASS requires zero blocking issues and risk 1-6. Risk 7-10 requires HUMAN_REVIEW with at least one concrete blocking issue. PASS means the option set is sound enough for direction selection; it does not itself authorize production. HUMAN_REVIEW is only for factual/privacy uncertainty or incompatible requirements. Aesthetic preferences are suggestions."""


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:3000]}") from exc


def parse(text: str) -> dict[str, Any]:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        value = json.loads(clean)
        if not isinstance(value, dict):
            raise ValueError("Review JSON must be an object")
        return value
    except json.JSONDecodeError as original:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"{", clean):
            try:
                value, _ = decoder.raw_decode(clean[match.start():])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
        raise original


def data_url(path: Path, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def call_claude(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not loaded")
    context = request["planning_context"]
    prompt = (
        "You are Claude, the independent visual planning reviewer. Review all three candidate plans against the complete brief, project decisions, every asset catalog entry, all thumbnails and systematic keyframes. Check whether proposed shots actually exist, visual variety, composition, narrative, typography opportunities, privacy and authenticity. Active decisions override historical wording: the yellow material is DIAMOND mother liquor, not a yellow tray. Do not select direction for the owner; recommend an option and distinguish blockers from preferences.\n\n"
        + contract() + "\n\n" + request.get("mandatory_reviewer_output_contract", "") + "\n\nREQUEST:\n" + json.dumps(request, ensure_ascii=False)
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for relative in context["evidence"]["images"]:
        path = root / relative
        content.extend([
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(path.read_bytes()).decode("ascii")}},
            {"type": "text", "text": f"Planning evidence: {relative}"},
        ])
    review_dir = root / "campaigns" / request["campaign"] / "plans" / "reviews"
    last_error: Exception | None = None
    for attempt in range(1, 4):
        raw = post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            {"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"), "max_tokens": 5000, "thinking": {"type": "disabled"}, "output_config": {"effort": "low"}, "messages": [{"role": "user", "content": content}]},
        )
        write_json(review_dir / f"claude-format-attempt-{attempt}-raw.json", raw)
        text = "\n".join(item.get("text", "") for item in raw.get("content", []) if item.get("type") == "text")
        try:
            review = parse(text)
            validate_review(review)
            if request.get("planning_mode") == "NARRATIVE_FIRST":
                from app.narrative_planning import validate_narrative_review
                validate_narrative_review(review)
            if attempt > 1:
                review["format_retry_count"] = attempt - 1
            return review, raw
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if request.get("planning_mode") == "NARRATIVE_FIRST":
                content = [{"type": "text", "text": (
                    "FORMAT-ONLY REPAIR. The prior review below was produced after inspecting the complete supplied visual evidence. "
                    "Preserve its substantive findings, but return exactly one logically consistent JSON object with the top-level narrative_assessment. "
                    "Required shape: {\"reviewer\":\"Claude\",\"decision\":\"PASS|REVISE|HUMAN_REVIEW\",\"recommended_option\":\"A|B|C|COMBINE|NONE\",\"scores\":{\"visual_quality\":1,\"authenticity\":1,\"brand_consistency\":1,\"platform_fit\":1,\"risk\":1},\"blocking_issues\":[],\"optional_suggestions\":[],\"summary\":\"\",\"narrative_assessment\":{\"hook_question\":\"\",\"causal_or_discovery_progression\":\"\",\"visual_climax\":\"\",\"resolution\":\"\",\"text_advances_story\":false,\"all_beats_evidence_supported\":false,\"missing_beats\":[],\"unsupported_claims\":[]}}. "
                    "PASS is allowed only when both booleans are true and both arrays are empty. Do not erase a substantive finding merely to preserve PASS; use REVISE when the findings identify a missing or unsupported beat. No prose or markdown.\n\nPRIOR REVIEW:\n" + text
                )}]
            else:
                content[0]["text"] = prompt + f"\n\nFORMAT RETRY {attempt}: Your prior response violated the exact JSON contract ({type(exc).__name__}). Return exactly one complete JSON object with every required score field and no prose or markdown."
    raise ValueError(f"Claude planning review failed the JSON contract after 3 format attempts: {last_error}")


def call_minimax(root: Path, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY is not loaded")
    context = request["planning_context"]
    prompt = (
        "You are MiniMax M3, the independent multimodal planning reviewer. Review all three plans against the complete brief, project decisions, every asset record, all image evidence and every available proxy video. Evaluate whether planned moments exist in motion, pacing feasibility, audio opportunities, factual clarity, platform fit, privacy and generation risk. Active decisions override historical wording: the yellow material is DIAMOND mother liquor, not a yellow tray. Do not select direction for the owner.\n\n"
        + contract() + "\n\n" + request.get("mandatory_reviewer_output_contract", "") + "\n\nREQUEST:\n" + json.dumps(request, ensure_ascii=False)
    )
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for relative in context["evidence"]["images"]:
        content.extend([
            {"type": "input_image", "image_url": {"url": data_url(root / relative, "image/jpeg"), "detail": "high"}},
            {"type": "input_text", "text": f"Planning image evidence: {relative}"},
        ])
    for relative in context["evidence"]["videos"]:
        content.extend([
            {"type": "input_video", "video_url": {"url": data_url(root / relative, "video/mp4"), "fps": 2, "detail": "high", "max_long_side_pixel": 720}},
            {"type": "input_text", "text": f"Complete planning proxy: {relative}"},
        ])
    raw = post_json(
        "https://api.minimax.io/v1/responses",
        {"Authorization": f"Bearer {key}", "content-type": "application/json"},
        {"model": os.environ.get("MINIMAX_REVIEW_MODEL", "MiniMax-M3"), "instructions": "Return strict JSON only.", "input": [{"type": "message", "role": "user", "content": content}], "reasoning": {"effort": "none"}, "max_output_tokens": 5000, "stream": False},
    )
    if raw.get("status") != "completed":
        raise RuntimeError(f"MiniMax incomplete: {raw.get('status')}: {raw.get('error')}")
    review = parse(raw.get("output_text", ""))
    validate_review(review)
    if request.get("planning_mode") == "NARRATIVE_FIRST":
        from app.narrative_planning import validate_narrative_review
        validate_narrative_review(review)
    return review, raw


def run_plan_review(root: Path, request: dict[str, Any], revision_count: int = 0) -> dict[str, Any]:
    review_dir = root / "campaigns" / request["campaign"] / "plans" / "reviews"
    claude, claude_raw = call_claude(root, request)
    minimax, minimax_raw = call_minimax(root, request)
    write_json(review_dir / "claude-planning-review.json", claude)
    write_json(review_dir / "claude-raw-response.json", claude_raw)
    write_json(review_dir / "minimax-planning-review.json", minimax)
    write_json(review_dir / "minimax-raw-response.json", minimax_raw)
    aggregation = aggregate_reviews(claude, minimax, revision_count)
    if aggregation["next_action"] == "FINAL_CANDIDATE":
        aggregation["next_action"] = "AWAITING_OWNER_PLAN_SELECTION"
        aggregation["reason"] = "both_reviewers_passed_owner_direction_gate_remains"
    write_json(review_dir / "planning-review-aggregation.json", aggregation)
    write_json(review_dir / "planning-cycle-state.json", {
        "campaign": request["campaign"],
        "status": aggregation["next_action"],
        "api_calls_performed": True,
        "updated_at": utc_now(),
    })
    return aggregation
