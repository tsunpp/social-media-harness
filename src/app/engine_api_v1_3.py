from __future__ import annotations

from pathlib import Path

from app.engine_api import EngineResult
from app.engine_api_v1_2 import EngineV12
from app.planning_orchestrator import prepare_plan_review, run_plan_review
from app.planning_preflight import find_plan_fact_conflicts, load_fact_rules


ENGINE_API_VERSION = "1.3"


class EngineV13(EngineV12):
    """Engine 1.3 blocks external planning review on superseded factual wording."""

    def _stamp(self, result: EngineResult) -> EngineResult:
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self) -> EngineResult:
        result = super().capabilities()
        result.data["capabilities"]["plan"]["fact_preflight"] = True
        return self._stamp(result)

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
            rules = load_fact_rules(self.root, request["planning_context"]["active_decisions"])
            conflicts = find_plan_fact_conflicts(request["plan_options"], rules)
            if conflicts:
                return self._failure(
                    command,
                    "FACT_CONFLICT",
                    "Planning options contain wording superseded by active owner-confirmed facts.",
                    status="FACT_CONFLICT",
                    next_action="codex_correct_plan_facts_without_changing_creative_direction",
                ).__class__(
                    command=command,
                    status="FACT_CONFLICT",
                    ok=False,
                    data={"conflicts": conflicts, "api_calls_performed": False},
                    errors=[{"code": "FACT_CONFLICT", "message": "Planning options contain wording superseded by active owner-confirmed facts."}],
                    next_action="codex_correct_plan_facts_without_changing_creative_direction",
                    engine_api_version=ENGINE_API_VERSION,
                )
            if run_apis:
                aggregation = run_plan_review(self.root, request, revision_count)
                return self._success(command, aggregation, status=aggregation["next_action"], next_action=aggregation["next_action"])
            return self._success(
                command,
                {
                    "campaign": campaign,
                    "project": project,
                    "fact_preflight": "PASS",
                    "asset_count": request["planning_context"]["evidence"]["asset_count"],
                    "image_evidence_count": request["planning_context"]["evidence"]["image_evidence_count"],
                    "video_proxy_count": request["planning_context"]["evidence"]["video_proxy_count"],
                },
                status="READY_FOR_MODEL_REVIEW",
                next_action="plan.review.run",
            )

        return self._stamp(self._guard(command, operation))

