from __future__ import annotations

import base64
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

from app.comfyui_adapter import ComfyUIClient, prepare_job
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.planning_privacy import read_policy
from app.video_production_orchestrator import inherited_context
from app.visual_style_profiles import public_style_contract, resolve_visual_style, validate_generation_prompt


CREATE_URL = "https://api.minimax.io/v2/video_generation"
QUERY_BASE = "https://api.minimax.io/v2/query/video_generation"
ALLOWED_BACKENDS = {"comfyui_aki:minimax_h3_i2v", "minimax_h3_api"}


def _post_json(url: str, key: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "social-media-harness/1.8"})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def validate_spec(root: Path, project: str, campaign: str, spec: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "job_id", "campaign", "backend", "source", "prompt", "output", "parameters"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Generation spec missing fields: {sorted(missing)}")
    if spec["campaign"] != campaign or spec["backend"] not in ALLOWED_BACKENDS:
        raise ValueError("Generation campaign/backend invalid; standard ComfyUI is not an executable route")
    source = root / spec["source"]
    if not source.is_file():
        raise FileNotFoundError(source)
    policy = read_policy(root / "policies" / "privacy_quarantine.json")
    for rule in policy.get("rules", []):
        if not rule.get("external_model_pixels_allowed", False) and rule["asset_id"] in json.dumps(spec, ensure_ascii=False):
            raise ValueError(f"Generation source references quarantined asset: {rule['asset_id']}")
    context = inherited_context(root, project, campaign)
    for decision in context["active_decisions"]:
        for phrase in decision["content"].get("forbidden_phrases", []):
            if phrase.lower() in spec["prompt"].lower():
                raise ValueError(f"Generation prompt contains forbidden phrase: {phrase}")
    visual_style = resolve_visual_style(root, campaign)
    validate_generation_prompt(spec["prompt"], visual_style)
    result = {**spec, "source_sha256": sha256(source), "active_head": context["active_head"], "privacy_preflight": "PASS", "fact_preflight": "PASS", "publishing_authorized": False, "api_key_stored": False}
    if visual_style is not None:
        result["visual_style_profile"] = visual_style["id"]
        result["visual_style_contract"] = public_style_contract(visual_style)
        result["originality_preflight"] = "PASS_ABSTRACT_PRINCIPLES_ONLY"
    return result


def prepare_generation(root: Path, project: str, campaign: str, spec_path: Path) -> dict[str, Any]:
    if not spec_path.is_absolute():
        spec_path = root / spec_path
    request = validate_spec(root, project, campaign, read_json(spec_path))
    write_json((root / request["output"]).parent / "generation-request-manifest.json", request)
    return request


def _first_output(history: dict[str, Any]) -> dict[str, str]:
    for node in history.get("outputs", {}).values():
        for kind in ("videos", "gifs", "images"):
            if node.get(kind):
                return node[kind][0]
    raise ValueError("ComfyUI returned no output media")


def run_comfyui_aki(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    instances = read_json(root / "config/comfyui_instances.json")
    instance = instances["instances"]["comfyui_aki"]
    registry_path = root / instance["capability_registry"]
    registry = read_json(registry_path)
    if registry.get("instance_id") != "comfyui_aki" or instances["routing_policy"]["allow_cross_instance_fallback"]:
        raise ValueError("ComfyUI instance isolation contract failed")
    source = root / request["source"]
    input_name = f"harness_{request['job_id']}{source.suffix.lower()}"
    installation = Path(instance["installation"])
    input_path = installation / "input" / input_name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, input_path)
    capability = registry["capabilities"]["minimax_h3_i2v"]
    params = request["parameters"]
    semantic = {"input_image": input_name, "prompt": request["prompt"], "width": params["width"], "height": params["height"], "length": params["length"], "seed": params["seed"], "filename_prefix": params.get("filename_prefix", f"harness/{request['job_id']}")}
    bindings = {capability["bindings"][name]: value for name, value in semantic.items()}
    _, workflow = prepare_job(registry_path, "minimax_h3_i2v", bindings)
    client = ComfyUIClient(instance["base_url"], timeout=120)
    client.health()
    prompt_id = client.queue(workflow)
    media = _first_output(client.wait(prompt_id, int(params.get("timeout_seconds", 3600))))
    generated = installation / "output" / media.get("subfolder", "") / media["filename"]
    output = root / request["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated, output)
    return {"backend": request["backend"], "instance_id": "comfyui_aki", "prompt_id": prompt_id, "source_sha256": request["source_sha256"], "output": request["output"], "output_sha256": sha256(output), "publishing_authorized": False}


def run_minimax_h3_api(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY is not loaded")
    source = root / request["source"]
    mime = "image/png" if source.suffix.lower() == ".png" else "image/jpeg"
    uri = f"data:{mime};base64,{base64.b64encode(source.read_bytes()).decode('ascii')}"
    p = request["parameters"]
    payload = {"model": p.get("model", "MiniMax-H3"), "content": [{"type": "text", "text": request["prompt"]}, {"type": "image_url", "image_url": {"url": uri}, "role": "first_frame"}], "resolution": p.get("resolution", "2K"), "duration": p.get("duration", 5), "ratio": p.get("ratio", "adaptive")}
    created = _post_json(CREATE_URL, key, "POST", payload)
    task_id = str(created.get("task_id") or created.get("task", {}).get("id") or "")
    if not task_id:
        raise ValueError("MiniMax create response contains no task_id")
    deadline = time.monotonic() + int(p.get("timeout_seconds", 2700))
    task = None
    while time.monotonic() < deadline:
        current = _post_json(f"{QUERY_BASE}/{task_id}", key)
        task = current.get("task", current)
        status = str(task.get("status", "unknown"))
        if status == "succeeded":
            break
        if status.lower() in {"failed", "cancelled", "fail"}:
            raise RuntimeError(f"MiniMax generation failed: {status}")
        time.sleep(10)
    if not task or task.get("status") != "succeeded":
        raise TimeoutError(f"MiniMax task {task_id} timed out")
    url = task.get("content", {}).get("url")
    if not url:
        raise ValueError("MiniMax result contains no download URL")
    output = root / request["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as response:
        output.write_bytes(response.read())
    return {"backend": "minimax_h3_api", "task_id": task_id, "source_sha256": request["source_sha256"], "output": request["output"], "output_sha256": sha256(output), "publishing_authorized": False}


def execute_generation(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    result = run_comfyui_aki(root, request) if request["backend"].startswith("comfyui_aki:") else run_minimax_h3_api(root, request)
    output_dir = (root / request["output"]).parent
    write_json(output_dir / "generation-result-manifest.json", result)
    params = request["parameters"]
    duration = float(params.get("duration", params.get("length", 24) / 24))
    render_manifest = {"schema_version": 1, "campaign": request["campaign"], "version": request["job_id"], "purpose": "Generated insert awaiting complete three-agent review", "output": {"path": request["output"], "duration_seconds": duration, "audio": "unknown_until_technical_gate", "publishing_authorized": False}, "captions": [], "content_provenance": {"generated": True, "backend": request["backend"], "source_sha256": request["source_sha256"], "prompt": request["prompt"]}}
    render_path = output_dir / "render-manifest.json"
    write_json(render_path, render_manifest)
    relative_render = str(render_path.relative_to(root)).replace("\\", "/")
    relative_job = str((output_dir / "video-production-job.json").relative_to(root)).replace("\\", "/")
    review_job = {"schema_version": 1, "campaign": request["campaign"], "job_id": request["job_id"] + "-review", "version": request["job_id"], "job_manifest_path": relative_job, "output": request["output"], "render_manifest": relative_render, "backends": {request["backend"]: {"enabled": True}}, "artifacts": [{"artifact_id": request["job_id"], "path": request["output"], "backend": request["backend"], "role": "generated_insert", "included_in_final": True, "provenance": "Generated from the recorded source and prompt; not authentic production footage.", "prompt": request["prompt"]}], "revision_policy": {"auto_revision_limit": 8, "routes": {"local_generated_insert": "comfyui_aki:minimax_h3_i2v", "cloud_generated_insert": "minimax_h3_api", "privacy_or_factual_uncertainty": "human_owner", "final_publish": "human_owner"}}, "publishing_authorized": False}
    write_json(output_dir / "video-production-job.json", review_job)
    result["review_handoff_job"] = relative_job
    result["next_action"] = "video.pipeline.prepare"
    return result
