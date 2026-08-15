from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_policy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sanitize_planning_context(context: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(context))
    rules = {rule["asset_id"]: rule for rule in policy.get("rules", [])}
    removed_images = []
    removed_videos = []
    removed_files = []

    def quarantined_path(relative: str) -> str | None:
        normalized = relative.replace("\\", "/")
        return next((asset_id for asset_id in rules if asset_id in normalized), None)

    clean_images = []
    for relative in result["evidence"]["images"]:
        asset_id = quarantined_path(relative)
        if asset_id:
            removed_images.append({"asset_id": asset_id, "kind": "image"})
        else:
            clean_images.append(relative)
    clean_videos = []
    for relative in result["evidence"]["videos"]:
        asset_id = quarantined_path(relative)
        if asset_id:
            removed_videos.append({"asset_id": asset_id, "kind": "video"})
        else:
            clean_videos.append(relative)
    clean_files = []
    pixel_roles = {"asset_thumbnail", "video_keyframe", "video_proxy"}
    for item in result["evidence"]["files"]:
        asset_id = quarantined_path(item["path"])
        if asset_id and item.get("role") in pixel_roles:
            removed_files.append({"asset_id": asset_id, "role": item["role"]})
        else:
            clean_files.append(item)

    for asset in result.get("asset_records", []):
        rule = rules.get(asset.get("asset_id"))
        if rule:
            asset["privacy_quarantine"] = {
                "classification": rule["classification"],
                "external_model_pixels_allowed": False,
                "automated_selection_allowed": False,
                "human_override_required": True,
            }
            asset["thumbnail_path"] = None
            asset["proxy_path"] = None
            asset["keyframes"] = []

    result["evidence"]["images"] = clean_images
    result["evidence"]["videos"] = clean_videos
    result["evidence"]["files"] = clean_files
    result["evidence"]["image_evidence_count"] = len(clean_images)
    result["evidence"]["video_proxy_count"] = len(clean_videos)
    result["privacy_quarantine"] = {
        "policy": "policies/privacy_quarantine.json",
        "quarantined_asset_ids": sorted(rules),
        "removed_pixel_evidence": {
            "images": removed_images,
            "videos": removed_videos,
            "manifest_entries": removed_files,
        },
        "complete_inventory_preserved_as_metadata": True,
    }
    return result


def find_quarantined_plan_references(plan: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    quarantined = {rule["asset_id"] for rule in policy.get("rules", []) if not rule.get("automated_selection_allowed", False)}
    conflicts = []
    for option in plan.get("options", []):
        hook_id = option.get("opening_hook", {}).get("asset_id")
        if hook_id in quarantined:
            conflicts.append({"option": option.get("id"), "location": "opening_hook", "asset_id": hook_id})
        for index, shot in enumerate(option.get("timeline", []), 1):
            if shot.get("asset_id") in quarantined:
                conflicts.append({"option": option.get("id"), "location": f"timeline[{index}]", "asset_id": shot["asset_id"]})
    return conflicts

