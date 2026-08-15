from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_registry(root: Path) -> dict[str, Any]:
    return json.loads((root / "config" / "audio_capabilities_v2_6.json").read_text(encoding="utf-8-sig"))


def resolve_audio_authority(root: Path, provider: str, capability: str) -> dict[str, Any]:
    record = load_registry(root).get("providers", {}).get(provider)
    if not record:
        raise ValueError(f"Unknown audio provider: {provider}")
    supported = capability in record.get("validated_authorities", [])
    return {
        "provider": provider,
        "capability": capability,
        "validated": supported,
        "evidence": record.get("evidence", []),
        "owner_listening_required": capability in {"bgm_quality", "mix_balance", "musical_pacing"} and not supported,
        "publication_authorized": False,
    }

