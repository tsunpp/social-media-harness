from __future__ import annotations

import hashlib
import json
from typing import Any


INTENTS = {"CLIENT_PREVIEW", "INTERNAL_ARCHIVE", "PUBLICATION_CANDIDATE"}
MESSAGE_MODES = {"PROCESS_DOCUMENTARY", "SERVICE_EDITORIAL", "PRODUCT_EDITORIAL"}
VFX_ROUTES = {"NO_REPLACEMENT", "PLANAR_TRACK", "SURFACE_TRACK", "MASK_AND_TRACK", "GENERATIVE_REPAIR", "NEW_CAPTURE_REQUIRED"}


def canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_campaign_governance(contract: dict[str, Any]) -> dict[str, Any]:
    intent = contract.get("delivery_intent")
    if intent not in INTENTS:
        raise ValueError(f"delivery_intent must be one of {sorted(INTENTS)}")
    messaging = contract.get("messaging", {})
    if messaging.get("mode") not in MESSAGE_MODES:
        raise ValueError(f"messaging.mode must be one of {sorted(MESSAGE_MODES)}")
    if messaging.get("mode") == "PROCESS_DOCUMENTARY":
        required = {"commercial_solicitation": False, "cta": "NONE", "contact_information": False, "sales_language": False}
        for key, expected in required.items():
            if messaging.get(key) != expected:
                raise ValueError(f"PROCESS_DOCUMENTARY requires messaging.{key}={expected!r}")

    marks = contract.get("brand_marks")
    if not isinstance(marks, list) or not marks:
        raise ValueError("At least one brand_marks record is required")
    replacements = []
    for mark in marks:
        for key in ("mark_id", "owner", "internal_display_allowed", "public_display_allowed", "alteration_allowed"):
            if key not in mark:
                raise ValueError(f"Brand mark record missing {key}")
        if intent == "PUBLICATION_CANDIDATE" and not mark["public_display_allowed"] and not mark.get("replacement_requested"):
            raise ValueError(f"Public candidate cannot retain non-public mark: {mark['mark_id']}")
        if mark.get("replacement_requested"):
            replacements.append(mark["mark_id"])
            if not mark["alteration_allowed"]:
                raise ValueError(f"Replacement requested without alteration permission: {mark['mark_id']}")
            asset = mark.get("replacement_asset", {})
            if asset.get("format") not in {"SVG", "PNG"} or not asset.get("transparent_background") or not asset.get("sha256"):
                raise ValueError(f"Replacement asset must be hash-bound transparent SVG/PNG: {mark['mark_id']}")

    vfx = contract.get("logo_replacement_preflight", {})
    if replacements:
        shots = vfx.get("shots")
        if vfx.get("status") != "PASS" or not isinstance(shots, list) or not shots:
            raise ValueError("Logo replacement requires a passing shot-level VFX preflight")
        for shot in shots:
            required = {"shot_id", "mark_id", "surface", "camera_motion", "occlusion", "reflection", "uv_light", "route"}
            if required - set(shot):
                raise ValueError(f"VFX shot record is incomplete: {shot.get('shot_id')}")
            if shot["route"] not in VFX_ROUTES - {"NO_REPLACEMENT"}:
                raise ValueError(f"Invalid replacement route: {shot['route']}")

    direction = contract.get("direction_contract", {})
    if direction.get("status") != "OWNER_CONFIRMED" or direction.get("unresolved_owner_decisions") not in ([], None):
        raise ValueError("Direction Contract must be OWNER_CONFIRMED with no unresolved owner decisions")
    if not direction.get("contract_sha256"):
        raise ValueError("Direction Contract must be hash-bound")

    allowed_stages = {
        "CLIENT_PREVIEW": ["stage_1", "stage_2", "stage_3", "stage_4", "archive_preview"],
        "INTERNAL_ARCHIVE": ["stage_1", "stage_2", "stage_3", "stage_4", "archive"],
        "PUBLICATION_CANDIDATE": ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5"],
    }[intent]
    return {
        "status": "PASS", "delivery_intent": intent, "messaging_mode": messaging["mode"],
        "replacement_marks": replacements, "allowed_stages": allowed_stages,
        "governance_sha256": canonical_hash(contract), "publication_authorized": False,
    }


def validate_direction_binding(direction_contract: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    expected = direction_contract.get("contract_sha256")
    if direction_contract.get("status") != "OWNER_CONFIRMED" or not expected:
        raise ValueError("Active Direction Contract is not owner-confirmed and hash-bound")
    if artifact.get("direction_contract_sha256") != expected:
        raise ValueError("Artifact is stale or unbound to the active Direction Contract")
    return {"status": "PASS", "direction_contract_sha256": expected}
