from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any


def _read_config(root: Path, name: str) -> dict[str, Any]:
    override = root / "config" / name
    if override.is_file():
        return json.loads(override.read_text(encoding="utf-8-sig"))
    bundled = files("app").joinpath("defaults", name)
    return json.loads(bundled.read_text(encoding="utf-8-sig"))


def load_profiles(root: Path) -> dict[str, Any]:
    return _read_config(root, "platform_profiles_v2_6.json")


def resolve_profile(root: Path, platform: str) -> dict[str, Any]:
    profiles = load_profiles(root).get("platforms", {})
    if platform not in profiles:
        raise ValueError(f"Unknown platform profile: {platform}")
    return profiles[platform]


def validate_platform_output(root: Path, platform: str, output: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    profile = resolve_profile(root, platform)
    if output.get("resolution") not in profile["allowed_resolutions"]:
        raise ValueError(f"{platform} resolution is not allowed")
    duration = float(output.get("duration_seconds", 0))
    if not profile["duration_seconds"]["min"] <= duration <= profile["duration_seconds"]["max"]:
        raise ValueError(f"{platform} duration is outside profile")
    for required in profile["package_requirements"]:
        if not package.get(required):
            raise ValueError(f"{platform} package missing {required}")
    if output.get("color") not in {None, "SDR BT.709"}:
        raise ValueError("Platform output must use SDR BT.709")
    return {"status": "PASS", "platform": platform, "profile_version": "2.6", "publication_authorized": False}