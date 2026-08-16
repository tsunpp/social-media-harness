from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "core_intent",
    "audience",
    "desired_viewer_shift",
    "creative_center",
    "tone",
    "anti_direction",
    "success_tests",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def persist_direction_head(root: Path, project: str, campaign: str, status: str, next_action: str, **fields: Any) -> Path:
    memory = root / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    previous = None
    try:
        from app.head_discovery import current_head
        candidate = current_head(root, project=project, campaign=campaign)
        record = read_json(candidate)
        if record.get("project") == project and record.get("campaign") == campaign:
            previous = str(candidate.relative_to(root)).replace("\\", "/")
    except (FileNotFoundError, ValueError):
        pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    record = {
        "schema_version": 1,
        "project": project,
        "campaign": campaign,
        "state": status,
        "direction_status": status,
        "next_action": next_action,
        "updated_at": utc_now(),
        **fields,
    }
    if previous:
        record["previous_head"] = previous
    path = memory / f"HEAD_{campaign}_direction_{stamp}.json"
    write_json(path, record)
    return path


def canonical_payload(contract: dict[str, Any]) -> bytes:
    payload = dict(contract)
    payload.pop("contract_hash", None)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def contract_hash(contract: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_payload(contract)).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validate_direction_contract(contract: dict[str, Any], campaign: str | None = None) -> dict[str, Any]:
    if contract.get("schema_version") != 1:
        raise ValueError("Direction Contract schema_version must be 1")
    if campaign is not None and contract.get("campaign") != campaign:
        raise ValueError("Direction Contract campaign does not match")
    missing = [name for name in REQUIRED_FIELDS if not contract.get(name)]
    if missing:
        raise ValueError(f"Direction Contract missing required fields: {missing}")
    if contract.get("status") == "OWNER_CONFIRMED" and contract.get("unresolved_owner_decisions"):
        raise ValueError("OWNER_CONFIRMED Direction Contract cannot contain unresolved owner decisions")
    if not isinstance(contract.get("anti_direction"), list) or not contract["anti_direction"]:
        raise ValueError("Direction Contract requires at least one anti_direction")
    if not isinstance(contract.get("success_tests"), list) or not contract["success_tests"]:
        raise ValueError("Direction Contract requires at least one success test")
    supplied = contract.get("contract_hash")
    calculated = contract_hash(contract)
    if supplied and supplied != calculated:
        raise ValueError("Direction Contract hash does not match canonical content")
    return {"status": "PASS", "contract_hash": calculated}


def source_staleness(root: Path, contract: dict[str, Any]) -> list[dict[str, str]]:
    stale: list[dict[str, str]] = []
    for relative, expected in contract.get("source_hashes", {}).items():
        path = root / relative
        if not path.is_file():
            stale.append({"path": relative, "reason": "MISSING"})
            continue
        actual = file_hash(path)
        if actual != expected:
            stale.append({"path": relative, "reason": "HASH_CHANGED", "expected": expected, "actual": actual})
    return stale


def validate_confirmation(root: Path, campaign: str) -> dict[str, Any]:
    direction = root / "campaigns" / campaign / "direction"
    active = direction / "direction-contract.json"
    confirmation = direction / "direction-confirmation.json"
    if not active.is_file() or not confirmation.is_file():
        raise FileNotFoundError("Owner-confirmed Direction Contract is required")
    contract = read_json(active)
    result = validate_direction_contract(contract, campaign)
    record = read_json(confirmation)
    if record.get("decision") != "CONFIRMED" or record.get("actor") != "owner":
        raise ValueError("Direction confirmation must be an explicit owner CONFIRMED decision")
    if record.get("contract_hash") != result["contract_hash"]:
        raise ValueError("Direction confirmation is not bound to the active contract hash")
    stale = source_staleness(root, contract)
    if stale:
        raise ValueError("Direction Contract is stale because source evidence changed")
    return {"status": "PASS", "contract_hash": result["contract_hash"], "stale_sources": []}


def confirm_contract(root: Path, campaign: str, contract_path: Path, actor: str) -> dict[str, Any]:
    if actor != "owner":
        raise ValueError("Only owner may confirm creative direction")
    contract = read_json(contract_path)
    contract["campaign"] = campaign
    contract["status"] = "OWNER_CONFIRMED"
    contract["confirmed_by"] = actor
    contract["confirmed_at"] = utc_now()
    contract["contract_hash"] = contract_hash(contract)
    validate_direction_contract(contract, campaign)
    direction = root / "campaigns" / campaign / "direction"
    direction.mkdir(parents=True, exist_ok=True)
    active = direction / "direction-contract.json"
    if active.is_file():
        old = read_json(active)
        old_hash = old.get("contract_hash") or contract_hash(old)
        write_json(direction / "history" / f"direction-contract-{old_hash.split(':')[-1][:12]}.json", old)
    write_json(active, contract)
    confirmation = {
        "schema_version": 1,
        "campaign": campaign,
        "decision": "CONFIRMED",
        "actor": actor,
        "contract_hash": contract["contract_hash"],
        "confirmed_at": contract["confirmed_at"],
        "publication_authorized": False,
    }
    write_json(direction / "direction-confirmation.json", confirmation)
    context_path = direction / "direction-context.json"
    project = read_json(context_path).get("project", "unknown") if context_path.is_file() else "unknown"
    head = persist_direction_head(
        root, project, campaign, "DIRECTION_CONFIRMED", "narrative.prepare",
        active_direction_contract=str(active.relative_to(root)).replace("\\", "/"),
        active_direction_contract_hash=contract["contract_hash"],
        direction_confirmation=str((direction / "direction-confirmation.json").relative_to(root)).replace("\\", "/"),
        direction_open_questions=[],
    )
    return {"status": "DIRECTION_CONFIRMED", "contract": str(active.relative_to(root)).replace("\\", "/"), "contract_hash": contract["contract_hash"], "memory_head": str(head.relative_to(root)).replace("\\", "/"), "publication_authorized": False}


def invalidate_contract(root: Path, campaign: str, reason: str, actor: str) -> dict[str, Any]:
    direction = root / "campaigns" / campaign / "direction"
    active = direction / "direction-contract.json"
    if not active.is_file():
        raise FileNotFoundError("No active Direction Contract exists")
    contract = read_json(active)
    digest = contract.get("contract_hash") or contract_hash(contract)
    write_json(direction / "history" / f"direction-contract-{digest.split(':')[-1][:12]}.json", contract)
    record = {"schema_version": 1, "campaign": campaign, "status": "INVALIDATED", "contract_hash": digest, "reason": reason.strip(), "actor": actor, "invalidated_at": utc_now()}
    if not record["reason"]:
        raise ValueError("Direction invalidation requires a bounded reason")
    write_json(direction / "direction-invalidation.json", record)
    active.unlink()
    confirmation = direction / "direction-confirmation.json"
    if confirmation.exists():
        confirmation.unlink()
    context_path = direction / "direction-context.json"
    project = read_json(context_path).get("project", "unknown") if context_path.is_file() else "unknown"
    head = persist_direction_head(root, project, campaign, "DIRECTION_ALIGNMENT_PENDING", "direction.context", invalidated_direction_contract_hash=digest, direction_invalidation=str((direction / "direction-invalidation.json").relative_to(root)).replace("\\", "/"))
    return {"status": "DIRECTION_ALIGNMENT_PENDING", "invalidated_contract_hash": digest, "reason": record["reason"], "memory_head": str(head.relative_to(root)).replace("\\", "/")}
