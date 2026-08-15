from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_fact_rules(root: Path, active_decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = []
    for item in active_decisions:
        content = item.get("content", {})
        if content.get("status") == "ACTIVE_CONFIRMED" and content.get("forbidden_phrases"):
            rules.append(content)
    return rules


def find_plan_fact_conflicts(plan_options: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized = json.dumps(plan_options, ensure_ascii=False)
    conflicts = []
    for rule in rules:
        for phrase in rule.get("forbidden_phrases", []):
            count = serialized.lower().count(str(phrase).lower())
            if count:
                conflicts.append({
                    "decision_id": rule.get("decision_id", "unknown"),
                    "phrase": phrase,
                    "occurrences": count,
                    "required_fact": rule.get("required_fact", ""),
                    "preferred_terms": rule.get("preferred_terms", []),
                })
    return conflicts

