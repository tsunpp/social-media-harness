from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _record_time(path: Path, record: dict) -> float:
    for key in ("updated_at", "created_at", "date"):
        value = record.get(key)
        if not value:
            continue
        try:
            normalized = str(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            pass
    return path.stat().st_mtime


def current_head(root: Path, project: str | None = None, campaign: str | None = None) -> Path:
    paths = sorted((root / "memory").glob("HEAD*.json"))
    if not paths:
        raise FileNotFoundError("No memory/HEAD*.json exists")
    records = {}
    for path in paths:
        try:
            records[str(path.relative_to(root)).replace("\\", "/")] = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
    if not records:
        raise ValueError("No readable HEAD record exists")

    def depth(name: str, seen: set[str] | None = None) -> int:
        seen = set() if seen is None else seen
        if name in seen:
            raise ValueError(f"HEAD cycle detected at {name}")
        previous = records.get(name, {}).get("previous_head")
        if not previous or previous not in records:
            return 0
        return 1 + depth(previous, seen | {name})

    referenced = {record.get("previous_head") for record in records.values() if record.get("previous_head")}
    leaves = [name for name in records if name not in referenced]
    candidates = leaves or list(records)
    if project:
        scoped = [name for name in candidates if records[name].get("project") == project]
        candidates = scoped or candidates
    if campaign:
        scoped = [name for name in candidates if records[name].get("campaign") == campaign]
        candidates = scoped or candidates
    # Independent Campaign HEAD chains are normal. Freshness must outrank the
    # depth of an unrelated historical chain; depth only breaks equal times.
    winner = max(
        candidates,
        key=lambda name: (_record_time(root / name, records[name]), depth(name), name),
    )
    return root / winner


def head_chain(root: Path, head: Path | None = None) -> list[tuple[Path, dict]]:
    head = current_head(root) if head is None else head
    chain = []
    seen = set()
    while head.is_file():
        relative = str(head.relative_to(root)).replace("\\", "/")
        if relative in seen:
            raise ValueError(f"HEAD cycle detected at {relative}")
        seen.add(relative)
        record = json.loads(head.read_text(encoding="utf-8-sig"))
        chain.append((head, record))
        previous = record.get("previous_head")
        if not previous:
            break
        head = root / previous
    return list(reversed(chain))
