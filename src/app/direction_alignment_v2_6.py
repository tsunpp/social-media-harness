from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.direction_contract_v2_6 import read_json, utc_now, validate_confirmation, write_json


CORE_FIELDS = ("core_intent", "audience", "viewer_shift", "creative_center", "tone")


def _norm(value: Any) -> str:
    return " ".join(str(value).strip().casefold().split())


def _expected(contract: dict[str, Any]) -> dict[str, str]:
    return {
        "core_intent": _norm(contract["core_intent"].get("statement")),
        "audience": _norm(contract["audience"].get("primary")),
        "viewer_shift": _norm(contract["desired_viewer_shift"].get("statement")),
        "creative_center": _norm(contract["creative_center"].get("statement")),
        "tone": _norm(contract["tone"].get("priority")),
    }


def _artifact_hash(artifact: dict[str, Any]) -> str:
    payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_alignment(root: Path, campaign: str, artifact_type: str, artifact: dict[str, Any], persist: bool = True) -> dict[str, Any]:
    confirmation = validate_confirmation(root, campaign)
    contract = read_json(root / "campaigns" / campaign / "direction" / "direction-contract.json")
    trace = artifact.get("direction_trace")
    if not isinstance(trace, dict):
        raise ValueError(f"{artifact_type} requires engine-verifiable direction_trace")
    if trace.get("direction_contract_hash") != confirmation["contract_hash"]:
        raise ValueError("Artifact is not bound to the active Direction Contract hash")
    expected = _expected(contract)
    checks = []
    failed = []
    for field in CORE_FIELDS:
        actual = _norm(trace.get(field, ""))
        passed = bool(actual) and actual == expected[field]
        checks.append({"check_id": f"DG-{field.upper().replace('_', '-')}", "status": "PASS" if passed else "FAIL", "expected": expected[field], "actual": actual})
        if not passed:
            failed.append(field)
    allowed_promises = {_norm(item.get("statement")) for item in contract.get("must_communicate", [])}
    promises = {_norm(item) for item in trace.get("promises", []) if _norm(item)}
    unsupported = sorted(promises - allowed_promises)
    anti_hits = [str(item) for item in trace.get("anti_direction_hits", []) if str(item).strip()]
    checks.append({"check_id": "DG-PROMISES", "status": "PASS" if not unsupported else "FAIL", "unsupported": unsupported})
    checks.append({"check_id": "DG-ANTI-DIRECTION", "status": "PASS" if not anti_hits else "FAIL", "hits": anti_hits})
    core_change = any(field in failed for field in CORE_FIELDS)
    status = "OWNER_RECONFIRMATION_REQUIRED" if core_change else ("REVISION_REQUIRED" if unsupported or anti_hits else "PASS")
    report = {
        "schema_version": 2, "generated_at": utc_now(), "artifact_type": artifact_type,
        "artifact_hash": _artifact_hash(artifact), "direction_contract_hash": confirmation["contract_hash"],
        "checks": checks, "failed_fields": failed, "unsupported_promises": unsupported,
        "anti_direction_hits": anti_hits, "status": status, "publication_authorized": False,
    }
    if persist:
        safe_type = artifact_type.replace("/", "-").replace(" ", "-")
        path = root / "campaigns" / campaign / "direction" / f"direction-alignment-{safe_type}.json"
        write_json(path, report)
        report["report_path"] = str(path.relative_to(root)).replace("\\", "/")
    return report


def validate_narrative_options_alignment(root: Path, campaign: str, plan: dict[str, Any]) -> dict[str, Any]:
    options = plan.get("options", [])
    if len(options) != 3:
        raise ValueError("Direction alignment requires exactly three narrative options")
    reports = [validate_alignment(root, campaign, f"narrative-option-{option.get('id', 'unknown')}", option) for option in options]
    failures = [report for report in reports if report["status"] != "PASS"]
    if failures:
        raise ValueError("One or more narrative options diverge from the confirmed creative direction")
    return {"status": "PASS", "option_count": 3, "direction_contract_hash": reports[0]["direction_contract_hash"], "reports": reports}
