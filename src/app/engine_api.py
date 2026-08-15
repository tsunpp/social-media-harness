from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.campaigns import (
    advance_campaign,
    campaign_history,
    create_campaign,
    get_campaign,
    list_campaigns,
)
from app.database import initialize
from app.review_orchestrator import DEFAULT_FFMPEG, prepare_review, run_models


ENGINE_API_VERSION = "1.0"


@dataclass
class EngineResult:
    command: str
    status: str
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    next_action: str | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    engine_api_version: str = ENGINE_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Engine:
    """Stable project-neutral interface used by the future Codex Skill."""

    def __init__(self, root: Path, db_path: Path | None = None):
        self.root = root.resolve()
        self.db_path = (db_path or self.root / "data" / "harness.db").resolve()

    def _success(
        self,
        command: str,
        data: dict[str, Any],
        status: str = "COMPLETED",
        next_action: str | None = None,
    ) -> EngineResult:
        return EngineResult(command=command, status=status, ok=True, data=data, next_action=next_action)

    def _failure(
        self,
        command: str,
        code: str,
        message: str,
        status: str = "FAILED",
        next_action: str | None = None,
    ) -> EngineResult:
        return EngineResult(
            command=command,
            status=status,
            ok=False,
            errors=[{"code": code, "message": message}],
            next_action=next_action,
        )

    def _guard(self, command: str, operation: Callable[[], EngineResult]) -> EngineResult:
        try:
            return operation()
        except (ValueError, KeyError, FileExistsError, FileNotFoundError) as exc:
            return self._failure(command, type(exc).__name__.upper(), str(exc))

    def capabilities(self) -> EngineResult:
        capabilities = {
            "recover": {"implemented": True, "mutates": False},
            "campaign.start": {"implemented": True, "mutates": True},
            "campaign.list": {"implemented": True, "mutates": False},
            "campaign.status": {"implemented": True, "mutates": False},
            "campaign.history": {"implemented": True, "mutates": False},
            "campaign.advance": {"implemented": True, "mutates": True},
            "review.video.prepare": {"implemented": True, "mutates": True, "paid_api": False},
            "review.video.run": {"implemented": True, "mutates": True, "paid_api": True},
            "plan": {"implemented": False, "reason": "planning executor not built"},
            "review.image": {"implemented": False, "reason": "image evidence executor not built"},
            "finalize": {"implemented": False, "reason": "final-package executor not built"},
            "archive": {"implemented": False, "reason": "stable archive executor not built"},
        }
        return self._success("capabilities", {"capabilities": capabilities})

    def recover(self, head: str = "memory/HEAD.json") -> EngineResult:
        command = "recover"

        def operation() -> EngineResult:
            head_path = self.root / head
            payload = json.loads(head_path.read_text(encoding="utf-8-sig"))
            references: list[str] = [payload["base_state"]]
            references.extend(payload.get("state_overlays_in_order", []))
            references.extend(payload.get("active_decisions", []))
            references.append(payload["current_stage_summary"])
            audit = payload.get("current_audit", {})
            references.extend(value for value in audit.values() if isinstance(value, str))
            missing = sorted({relative for relative in references if not (self.root / relative).is_file()})
            if missing:
                return self._failure(
                    command,
                    "RECOVERY_REFERENCE_MISSING",
                    "Missing recovery references: " + ", ".join(missing),
                    next_action="repair_recovery_chain",
                )
            base_state = json.loads((self.root / payload["base_state"]).read_text(encoding="utf-8-sig"))
            overlays = [
                json.loads((self.root / relative).read_text(encoding="utf-8-sig"))
                for relative in payload.get("state_overlays_in_order", [])
            ]
            decisions = [
                json.loads((self.root / relative).read_text(encoding="utf-8-sig"))
                for relative in payload.get("active_decisions", [])
            ]
            return self._success(
                command,
                {
                    "head": head,
                    "base_state": base_state,
                    "overlays": overlays,
                    "active_decisions": decisions,
                    "superseded_records": payload.get("superseded_records", []),
                    "reference_count": len(set(references)),
                },
                status="RECOVERED",
                next_action=payload.get("next_stage_after_owner_acceptance"),
            )

        return self._guard(command, operation)

    def start_campaign(self, slug: str, title: str) -> EngineResult:
        command = "campaign.start"

        def operation() -> EngineResult:
            path = create_campaign(self.root, self.db_path, slug, title)
            return self._success(command, {"campaign": get_campaign(self.db_path, slug), "path": str(path)}, status="CREATED")

        return self._guard(command, operation)

    def campaigns(self) -> EngineResult:
        initialize(self.db_path)
        return self._success("campaign.list", {"campaigns": list_campaigns(self.db_path)})

    def campaign_status(self, slug: str) -> EngineResult:
        return self._guard("campaign.status", lambda: self._success("campaign.status", {"campaign": get_campaign(self.db_path, slug)}))

    def campaign_history(self, slug: str) -> EngineResult:
        return self._guard("campaign.history", lambda: self._success("campaign.history", {"events": campaign_history(self.db_path, slug)}))

    def advance(self, slug: str, target: str, actor: str, note: str) -> EngineResult:
        command = "campaign.advance"
        return self._guard(
            command,
            lambda: self._success(
                command,
                {"campaign": advance_campaign(self.db_path, slug, target, actor, note)},
                status="ADVANCED",
            ),
        )

    def video_review(
        self,
        campaign: str,
        version: str,
        run_apis: bool = False,
        ffmpeg: Path = DEFAULT_FFMPEG,
        revision_count: int = 0,
    ) -> EngineResult:
        command = "review.video.run" if run_apis else "review.video.prepare"

        def operation() -> EngineResult:
            request = prepare_review(campaign, version, ffmpeg)
            if run_apis:
                result = run_models(request, revision_count)
                return self._success(command, result, status=result["status"], next_action=result["status"])
            return self._success(
                command,
                {
                    "campaign": campaign,
                    "version": version,
                    "evidence_manifest": request["evidence_manifest"],
                },
                status="READY_FOR_MODEL_REVIEW",
                next_action="review.video.run",
            )

        return self._guard(command, operation)

    def unavailable(self, command: str) -> EngineResult:
        return self._failure(
            command,
            "NOT_IMPLEMENTED",
            f"{command} is declared but its executor is not implemented.",
            status="NOT_IMPLEMENTED",
            next_action="implement_and_test_executor",
        )

