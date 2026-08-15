from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.review_policy import aggregate_reviews, utc_now, validate_review
from app.visual_style_profiles import public_style_contract, resolve_visual_style


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FFMPEG = Path(os.environ.get("SMH_FFMPEG", shutil.which("ffmpeg") or "ffmpeg"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resolve_draft(campaign: str, version: str) -> tuple[Path, Path, Path, dict[str, Any]]:
    draft = ROOT / "campaigns" / campaign / "drafts" / version
    manifest_path = draft / "render-manifest.json"
    if not manifest_path.is_file():
        manifest_path = draft / "production_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No render manifest in {draft}")
    manifest = read_json(manifest_path)
    output = manifest.get("output", {})
    video_value = output.get("path") if isinstance(output, dict) else None
    if video_value:
        video = ROOT / video_value
    else:
        videos = sorted(draft.glob("*.mp4"))
        if len(videos) != 1:
            raise ValueError(f"Cannot determine one review video in {draft}")
        video = videos[0]
    if not video.is_file():
        raise FileNotFoundError(video)
    return draft, manifest_path, video, manifest


def duration_from(manifest: dict[str, Any]) -> float:
    output = manifest.get("output", {})
    for key in ("duration_seconds", "target_duration_seconds"):
        if isinstance(output, dict) and output.get(key) is not None:
            return float(output[key])
    shots = manifest.get("shots", [])
    if shots:
        return sum(float(shot["duration"]) for shot in shots)
    raise ValueError("Manifest has no duration")


def sample_times(duration: float, captions: list[dict[str, Any]]) -> list[float]:
    if duration <= 0:
        return []
    values = {round(min(0.25, duration / 2), 2)}
    second = 1.0
    while second <= max(0.0, duration - 0.75):
        values.add(round(second, 2))
        second += 1.0
    values.add(round(max(0.0, duration - 0.75), 2))
    for caption in captions:
        start = float(caption.get("start", 0))
        end = float(caption.get("end", start))
        if end > start:
            values.add(round(max(0.0, min(start, duration - 0.75)), 2))
            values.add(round((start + end) / 2, 2))
            values.add(round(max(0.0, min(end - 0.01, duration - 0.75)), 2))
    return sorted(value for value in values if 0 <= value < duration)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_url(path: Path, media_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def load_prior_decisions(campaign: str) -> list[dict[str, Any]]:
    decision_dir = ROOT / "campaigns" / campaign / "decisions"
    return [
        {"file": str(path.relative_to(ROOT)), "content": read_json(path)}
        for path in sorted(decision_dir.glob("*.json"))
        if path.name != "settled-topics.json"
    ]


def load_settled_topics(campaign: str) -> list[dict[str, Any]]:
    path = ROOT / "campaigns" / campaign / "decisions" / "settled-topics.json"
    if not path.is_file():
        return []
    return read_json(path).get("topics", [])


def prepare_review(campaign: str, version: str, ffmpeg: Path) -> dict[str, Any]:
    draft, manifest_path, video, manifest = resolve_draft(campaign, version)
    review_dir = draft / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    decode = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-v", "error", "-i", str(video), "-f", "null", "NUL"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    technical = {
        "performed_at": utc_now(),
        "passed": decode.returncode == 0,
        "return_code": decode.returncode,
        "stderr_tail": decode.stderr[-2000:],
    }
    write_json(review_dir / "technical-gate.json", technical)
    if not technical["passed"]:
        raise RuntimeError("Technical gate failed; model review was not prepared")

    duration = duration_from(manifest)
    captions = manifest.get("captions", [])
    frame_dir = review_dir / "keyframes"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, timestamp in enumerate(sample_times(duration, captions), start=1):
        name = f"frame-{index:02d}-{timestamp:05.2f}s.jpg"
        path = frame_dir / name
        result = subprocess.run(
            [
                str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(timestamp), "-i", str(video), "-frames:v", "1",
                "-vf", "scale=540:960", "-q:v", "3", str(path),
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode != 0 or not path.is_file():
            raise RuntimeError(f"Frame extraction failed at {timestamp}s")
        frames.append(
            {"index": index, "time_seconds": timestamp, "file": name, "path": str(path)}
        )

    request = {
        "schema_version": 2,
        "campaign": campaign,
        "version": version,
        "created_at": utc_now(),
        "video": str(video),
        "manifest": str(manifest_path),
        "duration_seconds": duration,
        "captions": captions,
        "frames": frames,
        "render_manifest": manifest,
        "prior_decisions": load_prior_decisions(campaign),
        "settled_topics": load_settled_topics(campaign),
        "publishing_copy": read_json(draft / "publishing-copy.json")
        if (draft / "publishing-copy.json").is_file()
        else None,
        "cover_candidates": [
            str(path)
            for path in sorted((draft / "publish-assets").glob("cover-*.jpg"))
        ],
        "roles": {
            "codex": "producer, evidence-based adjudicator and revision executor",
            "claude": "visual direction, narrative, color, typography and visible privacy reviewer",
            "minimax": "full-video continuity, motion, audio, copy, factual clarity and publication-risk reviewer",
        },
        "evidence_contract": {
            "claude": "all one-second timeline samples, caption boundaries, covers, copy, manifest and prior decisions",
            "minimax": "complete video plus covers, copy, manifest and prior decisions",
            "sampling": "one frame per second plus first/last and every caption start/mid/end boundary",
        },
        "owner_gate": "Only genuine conflict, factual/privacy uncertainty, revision limit, or final publish",
    }
    visual_style = resolve_visual_style(ROOT, campaign)
    if visual_style is not None:
        request["visual_style_profile"] = visual_style["id"]
        request["visual_style_contract"] = public_style_contract(visual_style)
        request["evidence_contract"]["claude"] += "; enforce the selected composition, lighting, color and originality checks"
    evidence_paths = [video, manifest_path, *[Path(frame["path"]) for frame in frames]]
    evidence_paths.extend(Path(path) for path in request["cover_candidates"])
    evidence_manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "campaign": campaign,
        "version": version,
        "frame_count": len(frames),
        "sampling": request["evidence_contract"]["sampling"],
        "reviewer_modalities": {
            "claude": ["text", "complete_image_timeline"],
            "minimax": ["text", "complete_video", "cover_images"],
        },
        "files": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in evidence_paths
        ],
    }
    request["evidence_manifest"] = evidence_manifest
    write_json(review_dir / "evidence-manifest.json", evidence_manifest)
    write_json(review_dir / "review-request.json", request)
    write_json(
        review_dir / "cycle-state.json",
        {
            "campaign": campaign,
            "version": version,
            "status": "READY_FOR_MODEL_REVIEW",
            "api_calls_performed": False,
            "updated_at": utc_now(),
        },
    )
    return request


def contract() -> str:
    return """Return only one JSON object:
{"reviewer":"string","decision":"PASS | REVISE | HUMAN_REVIEW","scores":{"visual_quality":1-10,"authenticity":1-10,"brand_consistency":1-10,"platform_fit":1-10,"risk":1-10},"blocking_issues":[{"id":"string","location":"string","problem":"string","required_change":"string"}],"optional_suggestions":["string"],"summary":"string"}
Use HUMAN_REVIEW only for genuine factual/privacy uncertainty. Ordinary aesthetic preferences are not blockers. PASS requires zero blocking issues and a risk score from 1 to 6; risk 7 to 10 requires HUMAN_REVIEW plus a concrete blocking issue."""


def normalize_nonblocking_review(review: dict[str, Any]) -> dict[str, Any]:
    if review.get("decision") == "REVISE" and review.get("blocking_issues") == [] and review.get("scores", {}).get("risk", 10) <= 6:
        review["contract_normalization"] = {
            "original_decision": "REVISE",
            "normalized_decision": "PASS",
            "reason": "No blocking issue and publication risk is not high; requested changes are optional.",
        }
        review["decision"] = "PASS"
    return review

def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:2000]}") from exc


def parse_object(text: str) -> dict[str, Any]:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    return json.loads(clean)


def call_anthropic(request: dict[str, Any], model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not loaded")
    context = {
        key: request.get(key)
        for key in (
            "campaign", "version", "duration_seconds", "captions",
            "publishing_copy", "render_manifest", "prior_decisions", "settled_topics",
            "evidence_manifest", "production_job", "artifact_registry", "project_context",
            "privacy_preflight", "fact_preflight", "technical_gate", "evidence_contract",
            "visual_style_profile", "visual_style_contract",
        )
    }
    prompt = (
        "You are Claude, the independent visual reviewer in a three-agent content harness. "
        "Review only visible evidence in the chronological frames. Assess composition, progression, color, typography, "
        "subject clarity, authenticity, vertical-platform fit and visible privacy. Do not infer liquids, manufacturing, "
        "purity, potency or efficacy unless directly visible. Active decisions in project_context override historical wording. "
        "When visual_style_contract is present, explicitly check composition, lighting, color, pose or motion, environmental storytelling, continuity and originality. For typography, reject hollow/outlined display type, generic subtitle treatment, catalog-like uniform placement, unjustified pure-black defaults, low mobile legibility, arbitrary per-shot colors, or type that does not participate in shot hierarchy. Treat identifiable imitation of a reference image, publication layout, photographer signature or campaign execution as a blocking revision; judge only abstract principles and visible evidence. The intent is documentary display, not sales.\n\n"
        + json.dumps(context, ensure_ascii=False)
        + "\n\n"
        + contract()
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for frame in request["frames"]:
        encoded = base64.b64encode(Path(frame["path"]).read_bytes()).decode("ascii")
        content.extend(
            [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}},
                {"type": "text", "text": f"Frame {frame['index']} at {frame['time_seconds']} seconds"},
            ]
        )
    for index, cover_path in enumerate(request.get("cover_candidates", []), start=1):
        encoded = base64.b64encode(Path(cover_path).read_bytes()).decode("ascii")
        content.extend(
            [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}},
                {"type": "text", "text": f"Publication cover candidate {index}"},
            ]
        )
    raw = post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        {"model": model, "max_tokens": 4000, "messages": [{"role": "user", "content": content}]},
    )
    text = "\n".join(item.get("text", "") for item in raw.get("content", []) if item.get("type") == "text")
    review = normalize_nonblocking_review(parse_object(text))
    validate_review(review)
    return review, raw


def call_minimax(request: dict[str, Any], model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY is not loaded")
    context = {
        name: request.get(name)
        for name in (
            "campaign", "version", "duration_seconds", "captions",
            "publishing_copy", "render_manifest", "prior_decisions", "settled_topics",
            "evidence_manifest", "production_job", "artifact_registry", "project_context",
            "privacy_preflight", "fact_preflight", "technical_gate", "evidence_contract",
        )
    }
    prompt = (
        "You are MiniMax M3, the second independent multimodal reviewer in a three-agent social-content harness. "
        "You receive the complete rendered video, evidence inventory, captions, publishing copy, manifest, covers and "
        "settled prior decisions. Review the entire timeline, not isolated frames. Focus on motion continuity, temporal "
        "artifacts, audio, visual authenticity, on-screen copy, factual clarity, narrative consistency and publication "
        "risk. The content is documentary display, not direct marketing. Do not invent purity, potency, medical, purchase, "
        "manufacturing or efficacy claims. Cite timestamps for video findings. Do not reopen settled decisions without new "
        "evidence. Active decisions in project_context override historical wording. Ordinary aesthetic preferences are optional suggestions, not blockers.\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n\n"
        + contract()
    )
    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": prompt},
        {
            "type": "input_video",
            "video_url": {
                "url": data_url(Path(request["video"]), "video/mp4"),
                "fps": 2,
                "detail": "high",
                "max_long_side_pixel": 1080,
            },
        },
    ]
    for index, cover_path in enumerate(request.get("cover_candidates", []), start=1):
        content.extend([
            {
                "type": "input_image",
                "image_url": {
                    "url": data_url(Path(cover_path), "image/jpeg"),
                    "detail": "high",
                },
            },
            {"type": "input_text", "text": f"Publication cover candidate {index}"},
        ])
    raw = post_json(
        "https://api.minimax.io/v1/responses",
        {"Authorization": f"Bearer {key}", "content-type": "application/json"},
        {
            "model": model,
            "instructions": "Return strict JSON only. Do not use markdown fences.",
            "input": [{"type": "message", "role": "user", "content": content}],
            "reasoning": {"effort": "none"},
            "max_output_tokens": 4000,
            "stream": False,
        },
    )
    if raw.get("status") != "completed":
        raise RuntimeError(
            f"MiniMax response did not complete: {raw.get('status')}: {raw.get('error')}"
        )
    review = normalize_nonblocking_review(parse_object(raw.get("output_text", "")))
    validate_review(review)
    return review, raw


def run_models(request: dict[str, Any], revision_count: int, review_dir_override: Path | None = None) -> dict[str, Any]:
    review_dir = review_dir_override or Path(request["video"]).parent / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    minimax_model = os.environ.get("MINIMAX_REVIEW_MODEL", "MiniMax-M3")
    claude, claude_raw = call_anthropic(request, anthropic_model)
    write_json(review_dir / "claude-raw-response.json", claude_raw)
    write_json(review_dir / "claude-multimodal-review.json", claude)
    minimax, minimax_raw = call_minimax(request, minimax_model)
    write_json(review_dir / "minimax-raw-response.json", minimax_raw)
    write_json(review_dir / "minimax-multimodal-review.json", minimax)
    aggregation = aggregate_reviews(claude, minimax, revision_count)
    write_json(review_dir / "review-aggregation.json", aggregation)
    state = {
        "campaign": request["campaign"],
        "version": request["version"],
        "status": aggregation["next_action"],
        "api_calls_performed": True,
        "models": {"claude": anthropic_model, "minimax": minimax_model},
        "updated_at": utc_now(),
    }
    write_json(review_dir / "cycle-state.json", state)
    if aggregation["next_action"] == "CODEX_ADJUDICATION":
        write_json(
            review_dir / "codex-adjudication-task.json",
            {
                "instruction": "Verify every blocker against source evidence. Accept or reject with reasons; implement accepted changes and start the next review without asking the owner unless escalation policy applies.",
                "aggregation": aggregation,
            },
        )
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Three-agent content review orchestrator")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument("--revision-count", type=int, default=0)
    parser.add_argument("--run-apis", action="store_true")
    args = parser.parse_args(argv)
    request = prepare_review(args.campaign, args.version, args.ffmpeg)
    result = run_models(request, args.revision_count) if args.run_apis else {
        "campaign": args.campaign,
        "version": args.version,
        "status": "READY_FOR_MODEL_REVIEW",
        "api_calls_performed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


