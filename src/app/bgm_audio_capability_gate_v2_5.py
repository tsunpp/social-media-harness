from __future__ import annotations
from typing import Any


def require_validated_audio_authority(capability: dict[str, Any]) -> dict[str, Any]:
    required = {"reviewer", "complete_duration_audio", "semantic_consistency", "validated"}
    missing = required - set(capability)
    if missing:
        raise ValueError(f"Audio capability record missing fields: {sorted(missing)}")
    if not capability["complete_duration_audio"] or not capability["semantic_consistency"] or not capability["validated"]:
        return {
            "status": "HUMAN_AUDIO_REVIEW",
            "reason": "No configured reviewer has passed complete-audio semantic capability validation",
            "model_selection_is_provisional": True,
            "publication_authorized": False,
        }
    return {"status":"AUDIO_MODEL_AUTHORITY_VALIDATED","reviewer":capability["reviewer"],"publication_authorized":False}
