from __future__ import annotations

import json
from pathlib import Path


def current_head(root: Path) -> Path:
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
    winner = max(candidates, key=lambda name: (depth(name), records[name].get("updated_at", ""), name))
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
