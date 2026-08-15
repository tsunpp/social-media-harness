from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.final_package_executor import validate_archive_id, verify_final_package
from app.archive_naming import locate_archive
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.review_policy import utc_now


SUPPORTED_PLATFORMS = {
    "instagram_reels": "platforms/instagram-reels",
    "youtube_shorts": "platforms/youtube-shorts",
}


def _archive(root: Path, archive_id: str) -> tuple[Path, dict[str, Any]]:
    validate_archive_id(archive_id)
    folder = locate_archive(root, archive_id)
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = read_json(manifest_path)
    if manifest.get("archive_id") != archive_id:
        raise ValueError("Archive manifest identity does not match archive ID")
    verification = verify_final_package(root, archive_id)
    if verification["status"] != "PASS":
        raise ValueError(f"Archive verification failed: {verification}")
    if manifest.get("status") != "READY_NOT_PUBLISHED":
        raise ValueError("Archive must be READY_NOT_PUBLISHED")
    if manifest.get("publishing_authorized") is not False:
        raise ValueError("Archive publication lock is not intact")
    return folder, manifest


def _platform_payload(folder: Path, platform: str) -> dict[str, Any]:
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported publication platform: {platform}")
    base = folder / SUPPORTED_PLATFORMS[platform]
    names = (
        ("media", "reel.mp4"), ("cover", "cover.jpg"), ("caption", "caption.txt")
    ) if platform == "instagram_reels" else (
        ("media", "short.mp4"), ("cover", "thumbnail.jpg"),
        ("title", "title.txt"), ("description", "description.txt"),
    )
    files: dict[str, dict[str, Any]] = {}
    for role, name in names:
        path = base / name
        if not path.is_file():
            raise FileNotFoundError(path)
        files[role] = {"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size}
    return {"platform": platform, "files": files}


def prepare_openclaw_handoff(root: Path, archive_id: str, platforms: list[str] | None = None) -> dict[str, Any]:
    folder, manifest = _archive(root, archive_id)
    selected = platforms or list(SUPPORTED_PLATFORMS)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Platforms must be a non-empty unique list")
    payloads = [_platform_payload(folder, platform) for platform in selected]
    manifest_path = folder / "manifest.json"
    authorization_path = folder / "handoffs" / "openclaw" / "owner-publication-authorization.json"
    authorization = None
    execution_permitted = False
    if authorization_path.is_file():
        candidate = read_json(authorization_path)
        expected_platforms = sorted(x["platform"] for x in payloads)
        current_media = {x["platform"]: x["files"]["media"]["sha256"].upper() for x in payloads}
        authorized_media = {k: str(v).upper() for k, v in candidate.get("media_sha256", {}).items()}
        execution_permitted = (
            candidate.get("archive_id") == archive_id
            and candidate.get("owner_authorized") is True
            and sorted(candidate.get("platforms", [])) == expected_platforms
            and authorized_media == current_media
        )
        if execution_permitted:
            authorization = {"path": str(authorization_path.resolve()), "sha256": sha256(authorization_path)}
    return {
        "schema_version": 1,
        "handoff_type": "openclaw_publication",
        "archive_id": archive_id,
        "archive_manifest": {"path": str(manifest_path.resolve()), "sha256": sha256(manifest_path)},
        "archive_status": manifest["status"],
        "platform_payloads": payloads,
        "safety": {
            "publication_authorized": execution_permitted,
            "owner_authorization_required": not execution_permitted,
            "openclaw_execution_permitted": execution_permitted,
            "instruction": "Execute only the exact authorized archive/platform payloads and write the publication receipt." if execution_permitted else "Verify fresh owner authorization for the exact archive and platforms before any external upload or publication.",
        },
        "owner_authorization": authorization,
        "next_action": "openclaw_publish_exact_payloads" if execution_permitted else "owner_authorize_openclaw_publication",
    }


def build_openclaw_handoff(root: Path, archive_id: str, platforms: list[str] | None = None) -> dict[str, Any]:
    payload = prepare_openclaw_handoff(root, archive_id, platforms)
    folder = locate_archive(root, archive_id) / "handoffs" / "openclaw"
    task_path = folder / "publication-handoff.json"
    receipt_path = folder / "publication-receipt.json"
    if task_path.exists():
        existing = read_json(task_path)
        comparable = {k: v for k, v in existing.items() if k not in {"created_at", "task_sha256"}}
        if comparable != payload:
            raise FileExistsError("A different OpenClaw handoff already exists for this archive")
        return {"archive_id": archive_id, "status": "OPENCLAW_HANDOFF_READY", "handoff": str(task_path), "task_sha256": sha256(task_path), "idempotent": True, "publishing_authorized": payload["safety"]["publication_authorized"], "next_action": payload["next_action"]}
    folder.mkdir(parents=True, exist_ok=True)
    payload["created_at"] = utc_now()
    write_json(task_path, payload)
    digest = sha256(task_path)
    write_json(receipt_path, {
        "schema_version": 1, "archive_id": archive_id, "handoff_sha256": digest,
        "status": "READY_FOR_OPENCLAW_DISPATCH" if payload["safety"]["openclaw_execution_permitted"] else "PREPARED_NOT_DISPATCHED", "openclaw_dispatched": False,
        "published": False, "publication_authorized": payload["safety"]["publication_authorized"],
    })
    return {"archive_id": archive_id, "status": "OPENCLAW_HANDOFF_READY", "handoff": str(task_path), "receipt": str(receipt_path), "task_sha256": digest, "idempotent": False, "publishing_authorized": payload["safety"]["publication_authorized"], "next_action": payload["next_action"]}


def verify_openclaw_handoff(root: Path, archive_id: str) -> dict[str, Any]:
    task = locate_archive(root, archive_id) / "handoffs" / "openclaw" / "publication-handoff.json"
    receipt = task.with_name("publication-receipt.json")
    failures: list[str] = []
    try:
        expected = prepare_openclaw_handoff(root, archive_id)
        actual = read_json(task)
        for key, value in expected.items():
            if actual.get(key) != value:
                failures.append(key)
        recorded = read_json(receipt)
        if recorded.get("handoff_sha256") != sha256(task): failures.append("receipt.handoff_sha256")
        if recorded.get("published") is not False: failures.append("receipt.published")
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        failures.append(str(exc))
    return {"archive_id": archive_id, "status": "PASS" if not failures else "FAIL", "failures": failures, "publishing_authorized": actual.get("safety", {}).get("publication_authorized", False) if 'actual' in locals() else False}
