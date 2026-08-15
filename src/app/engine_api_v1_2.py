from __future__ import annotations

from pathlib import Path

from app.engine_api import EngineResult
from app.engine_api_v1_1 import EngineV11
from app.planning_orchestrator import prepare_plan_review, prepare_planning_context, run_plan_review


ENGINE_API_VERSION = "1.2"


class EngineV12(EngineV11):
    """Engine 1.2 adds the planning evidence and dual-review executor."""

    def _stamp(self, result: EngineResult) -> EngineResult:
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self) -> EngineResult:
        result = super().capabilities()
        result.data["capabilities"]["plan"] = {
            "implemented": True,
            "mutates": True,
            "steps": ["prepare_context", "prepare_review", "run_review"],
            "paid_api_only_for": "run_review",
        }
        return self._stamp(result)

    def planning_prepare(self, project: str, campaign: str) -> EngineResult:
        command = "plan.prepare"
        return self._stamp(self._guard(
            command,
            lambda: self._success(
                command,
                {"planning_context": prepare_planning_context(self.root, project, campaign)},
                status="READY_FOR_CODEX_PLAN",
                next_action="codex_create_or_update_three_plan_options",
            ),
        ))

    def planning_review(
        self,
        project: str,
        campaign: str,
        plan_path: Path | None = None,
        run_apis: bool = False,
        revision_count: int = 0,
    ) -> EngineResult:
        command = "plan.review.run" if run_apis else "plan.review.prepare"

        def operation() -> EngineResult:
            request = prepare_plan_review(self.root, project, campaign, plan_path)
            if run_apis:
                aggregation = run_plan_review(self.root, request, revision_count)
                return self._success(command, aggregation, status=aggregation["next_action"], next_action=aggregation["next_action"])
            return self._success(
                command,
                {
                    "campaign": campaign,
                    "project": project,
                    "review_request": str((self.root / "campaigns" / campaign / "plans" / "reviews" / "planning-review-request.json")),
                    "asset_count": request["planning_context"]["evidence"]["asset_count"],
                    "image_evidence_count": request["planning_context"]["evidence"]["image_evidence_count"],
                    "video_proxy_count": request["planning_context"]["evidence"]["video_proxy_count"],
                },
                status="READY_FOR_MODEL_REVIEW",
                next_action="plan.review.run",
            )

        return self._stamp(self._guard(command, operation))

