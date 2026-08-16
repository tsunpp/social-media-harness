from __future__ import annotations

from pathlib import Path
from typing import Any

from app.direction_contract_v2_6 import file_hash, persist_direction_head, read_json, utc_now, write_json


QUESTIONS = (
    ("core_intent", "What single idea should the audience retain?", "Make authentic process evidence the primary trust-building idea."),
    ("primary_audience", "Who must understand or trust this story first?", "Prioritize the highest-value audience supported by the Campaign brief."),
    ("viewer_shift", "What should change in the viewer between opening and ending?", "Move from surface-level product awareness to evidence-backed understanding."),
    ("creative_center", "Who or what is the protagonist?", "Use the authentic process as protagonist and the product as outcome evidence."),
    ("tone_priority", "Which tone leads, and which tone is secondary?", "Lead with restrained authenticity; use warmth as a secondary quality."),
    ("anti_direction", "What attractive but wrong direction must be rejected?", "Reject a generic product advertisement without causal progression."),
    ("success_test", "What observable test proves the direction stayed aligned?", "All three story options may differ structurally but must produce the same viewer shift."),
)


def _campaign_dir(root: Path, campaign: str) -> Path:
    path = root / "campaigns" / campaign
    if not path.is_dir():
        raise FileNotFoundError(f"Campaign not found: {campaign}")
    return path


def build_direction_context(root: Path, project: str, campaign: str) -> dict[str, Any]:
    campaign_dir = _campaign_dir(root, campaign)
    candidates = (
        root / "projects" / project / "project.yaml",
        root / "projects" / project / "PROJECT_DECISIONS.md",
        campaign_dir / "brief.yaml",
        campaign_dir / "source" / "manifest.json",
        campaign_dir / "source" / "fact-contract.json",
    )
    sources = {}
    for path in candidates:
        if path.is_file():
            relative = str(path.relative_to(root)).replace("\\", "/")
            sources[relative] = file_hash(path)
    if not (campaign_dir / "brief.yaml").is_file():
        raise FileNotFoundError("Campaign brief is required before Direction Grill")
    context = {
        "schema_version": 1,
        "project": project,
        "campaign": campaign,
        "created_at": utc_now(),
        "source_hashes": sources,
        "question_policy": {"discoverable_facts": "INVESTIGATE_DO_NOT_ASK_OWNER", "owner_judgments": "ASK_1_TO_3_BLOCKING_QUESTIONS", "recommendation_required": True, "self_adversarial_check_required": True},
        "next_action": "direction.questions",
    }
    write_json(campaign_dir / "direction" / "direction-context.json", context)
    marker = campaign_dir / "direction" / "required.json"
    if not marker.exists():
        write_json(marker, {"schema_version": 1, "required": True, "campaign": campaign})
    persist_direction_head(root, project, campaign, "DIRECTION_ALIGNMENT_PENDING", "direction.questions", direction_context=str((campaign_dir / "direction" / "direction-context.json").relative_to(root)).replace("\\", "/"))
    return context


def direction_questions(root: Path, campaign: str) -> dict[str, Any]:
    direction = _campaign_dir(root, campaign) / "direction"
    context_path = direction / "direction-context.json"
    if not context_path.is_file():
        raise FileNotFoundError("Direction context must be built first")
    session_path = direction / "direction-session.json"
    session = read_json(session_path) if session_path.is_file() else {"schema_version": 1, "campaign": campaign, "answers": {}, "round": 0, "self_adversarial_check": None}
    unanswered = [item for item in QUESTIONS if item[0] not in session["answers"]]
    batch = [{"id": qid, "question": prompt, "recommended_answer": recommendation, "impact": "Blocks creative direction confirmation"} for qid, prompt, recommendation in unanswered[:3]]
    session["round"] += 1
    session["updated_at"] = utc_now()
    session["open_question_ids"] = [item[0] for item in unanswered]
    write_json(session_path, session)
    project = read_json(context_path).get("project", "unknown")
    persist_direction_head(root, project, campaign, "DIRECTION_ALIGNMENT_PENDING", "direction.answer" if batch else "direction.draft", direction_session=str(session_path.relative_to(root)).replace("\\", "/"), direction_open_questions=session["open_question_ids"])
    return {"status": "AWAITING_OWNER_DIRECTION", "round": session["round"], "questions": batch, "remaining": len(unanswered), "next_action": "direction.answer" if batch else "direction.draft"}


def record_answers(root: Path, campaign: str, answers: dict[str, Any]) -> dict[str, Any]:
    direction = _campaign_dir(root, campaign) / "direction"
    session_path = direction / "direction-session.json"
    if not session_path.is_file():
        raise FileNotFoundError("Direction session must be started first")
    session = read_json(session_path)
    valid_ids = {item[0] for item in QUESTIONS}
    for qid, answer in answers.get("answers", answers).items():
        if qid not in valid_ids:
            raise ValueError(f"Unknown Direction Grill question id: {qid}")
        if not str(answer).strip():
            raise ValueError(f"Direction answer cannot be blank: {qid}")
        session["answers"][qid] = str(answer).strip()
    if "self_adversarial_check" in answers:
        check = answers["self_adversarial_check"]
        if not isinstance(check, dict) or not str(check.get("strongest_countercase", "")).strip() or not str(check.get("disposition", "")).strip():
            raise ValueError("Self-adversarial check requires strongest_countercase and disposition")
        session["self_adversarial_check"] = check
    session["updated_at"] = utc_now()
    write_json(session_path, session)
    remaining = [item[0] for item in QUESTIONS if item[0] not in session["answers"]]
    context = read_json(direction / "direction-context.json")
    persist_direction_head(root, context.get("project", "unknown"), campaign, "DIRECTION_ALIGNMENT_PENDING", "direction.questions" if remaining else ("direction.answer" if not session.get("self_adversarial_check") else "direction.draft"), direction_session=str(session_path.relative_to(root)).replace("\\", "/"), direction_open_questions=remaining)
    return {"status": "DIRECTION_ALIGNMENT_PENDING" if remaining or not session.get("self_adversarial_check") else "READY_FOR_DIRECTION_DRAFT", "remaining_question_ids": remaining, "self_adversarial_check_complete": bool(session.get("self_adversarial_check")), "next_action": "direction.questions" if remaining else ("direction.answer" if not session.get("self_adversarial_check") else "direction.draft")}


def draft_contract(root: Path, campaign: str) -> dict[str, Any]:
    direction = _campaign_dir(root, campaign) / "direction"
    session = read_json(direction / "direction-session.json")
    context = read_json(direction / "direction-context.json")
    missing = [item[0] for item in QUESTIONS if item[0] not in session.get("answers", {})]
    if missing or not session.get("self_adversarial_check"):
        raise ValueError("Direction Grill is incomplete; resolve all owner judgments and self-adversarial check")
    a = session["answers"]
    contract = {
        "schema_version": 1,
        "campaign": campaign,
        "status": "DRAFT_AWAITING_OWNER",
        "core_intent": {"statement": a["core_intent"]},
        "audience": {"primary": a["primary_audience"]},
        "desired_viewer_shift": {"statement": a["viewer_shift"]},
        "creative_center": {"statement": a["creative_center"]},
        "tone": {"priority": a["tone_priority"]},
        "must_communicate": [],
        "must_not_imply": [],
        "anti_direction": [a["anti_direction"]],
        "success_tests": [a["success_test"]],
        "open_freedoms": ["opening form", "shot rhythm", "title wording"],
        "unresolved_owner_decisions": [],
        "self_adversarial_check": session["self_adversarial_check"],
        "source_hashes": context["source_hashes"],
        "created_at": utc_now(),
    }
    path = direction / "direction-contract.draft.json"
    write_json(path, contract)
    persist_direction_head(root, context.get("project", "unknown"), campaign, "DIRECTION_ALIGNMENT_PENDING", "direction.confirm", direction_contract_draft=str(path.relative_to(root)).replace("\\", "/"), direction_open_questions=[])
    return {"status": "AWAITING_OWNER_DIRECTION_CONFIRMATION", "contract": str(path.relative_to(root)).replace("\\", "/"), "publication_authorized": False, "next_action": "direction.confirm"}
