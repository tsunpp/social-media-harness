from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


STAGE_5_TERMS = {"publish", "platform policy", "recommendation", "caption file", "srt", "hashtag", "package", "contact link"}
VISUAL_TERMS = {"palette", "font", "typography", "composition", "color", "hierarchy"}
MOTION_TERMS = {"motion", "pacing", "transition", "continuity", "stable rest", "timestamp"}


def finding_signature(finding: dict[str, Any]) -> str:
    value = {key: finding.get(key) for key in ("reviewer", "domain", "problem", "required_change")}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def infer_scope(finding: dict[str, Any]) -> tuple[str, str | None]:
    text = " ".join(str(finding.get(key, "")).lower() for key in ("problem", "required_change"))
    if any(term in text for term in STAGE_5_TERMS): return "stage_5", "publication_package"
    if any(term in text for term in VISUAL_TERMS): return "stage_4", "visual_hierarchy"
    if any(term in text for term in MOTION_TERMS): return "stage_4", "temporal_continuity"
    return "current", None


def govern_finding(reviewer: str, finding: dict[str, Any], stage: str, authority: set[str], owner_resolutions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    item = {"reviewer": reviewer, **finding, "signature": finding_signature({"reviewer": reviewer, **finding})}
    for resolution in owner_resolutions or []:
        if resolution.get("status") == "RESOLVED" and item["signature"] in resolution.get("finding_signatures", []):
            item.update({"binding": False, "classification": "RESOLVED_BY_OWNER", "resolution_id": resolution.get("resolution_id")})
            return item
    inferred_stage, inferred_domain = infer_scope(item)
    if inferred_stage not in {"current", stage}:
        item.update({"binding": False, "classification": "DEFERRED_TO_CORRECT_STAGE", "target_stage": inferred_stage})
    elif inferred_domain and inferred_domain != item.get("domain"):
        item.update({"binding": inferred_domain in authority, "classification": "DOMAIN_CORRECTED", "declared_domain": item.get("domain"), "domain": inferred_domain})
    else:
        item.update({"binding": item.get("domain") in authority, "classification": "BINDING" if item.get("domain") in authority else "ADVISORY_OUTSIDE_AUTHORITY"})
    return item


def update_loop_state(path: Path, binding_findings: list[dict[str, Any]], evidence_fingerprint: str) -> dict[str, Any]:
    prior = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"cycles": []}
    signatures = sorted(item.get("signature") or finding_signature(item) for item in binding_findings)
    previous = prior["cycles"][-1] if prior["cycles"] else None
    repeated = int(previous.get("repeated_streak", 0)) + 1 if previous and previous.get("signatures") == signatures else 1
    no_improvement = int(previous.get("no_improvement_streak", 0)) + 1 if previous and previous.get("signatures") == signatures and previous.get("evidence_fingerprint") == evidence_fingerprint else 0
    cycle = {"signatures": signatures, "evidence_fingerprint": evidence_fingerprint, "repeated_streak": repeated, "no_improvement_streak": no_improvement}
    prior["cycles"].append(cycle); prior["status"] = "HUMAN_DECISION" if repeated >= 3 or no_improvement >= 2 else "CONTINUE"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(prior, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return prior
