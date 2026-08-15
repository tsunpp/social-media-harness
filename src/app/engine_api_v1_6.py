from __future__ import annotations

from pathlib import Path

from app import planning_orchestrator
from app.engine_api import EngineResult
from app.engine_api_v1_5 import EngineV15
from app.planning_contract_v2 import contract_v2
from app.planning_orchestrator_privacy import prepare_private_context, prepare_private_plan_review
from app.planning_preflight import find_plan_fact_conflicts, load_fact_rules


ENGINE_API_VERSION = "1.6"


class EngineV16(EngineV15):
    """Engine 1.6 separates complete inventory from externally shareable pixels."""

    def _stamp(self, result: EngineResult) -> EngineResult:
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self) -> EngineResult:
        result = super().capabilities()
        result.data["capabilities"]["plan"]["privacy_quarantine"] = True
        return self._stamp(result)

    def planning_prepare(self, project: str, campaign: str) -> EngineResult:
        command = "plan.prepare"
        return self._stamp(self._guard(command, lambda: self._success(
            command,
            {"planning_context": prepare_private_context(self.root, project, campaign)},
            status="READY_FOR_CODEX_PLAN",
            next_action="codex_create_or_update_three_plan_options",
        )))

    def planning_review(self, project: str, campaign: str, plan_path: Path | None = None, run_apis: bool = False, revision_count: int = 0) -> EngineResult:
        planning_orchestrator.contract = contract_v2
        command = "plan.review.run" if run_apis else "plan.review.prepare"
        if plan_path is not None and not plan_path.is_absolute():
            plan_path = self.root / plan_path

        def operation() -> EngineResult:
            request = prepare_private_plan_review(self.root, project, campaign, plan_path)
            rules = load_fact_rules(self.root, request["planning_context"]["active_decisions"])
            fact_conflicts = find_plan_fact_conflicts(request["plan_options"], rules)
            if fact_conflicts:
                return EngineResult(command=command, status="FACT_CONFLICT", ok=False, data={"conflicts": fact_conflicts, "api_calls_performed": False}, errors=[{"code": "FACT_CONFLICT", "message": "Plan conflicts with active facts."}], next_action="codex_correct_plan_facts_without_changing_creative_direction", engine_api_version=ENGINE_API_VERSION)
            if run_apis:
                aggregation = planning_orchestrator.run_plan_review(self.root, request, revision_count)
                return self._success(command, aggregation, status=aggregation["next_action"], next_action=aggregation["next_action"])
            evidence = request["planning_context"]["evidence"]
            return self._success(command, {
                "campaign": campaign,
                "project": project,
                "fact_preflight": "PASS",
                "privacy_preflight": "PASS",
                "asset_count": evidence["asset_count"],
                "image_evidence_count": evidence["image_evidence_count"],
                "video_proxy_count": evidence["video_proxy_count"],
                "quarantined_asset_ids": request["planning_context"]["privacy_quarantine"]["quarantined_asset_ids"],
                "sanitized_request": str(self.root / "campaigns" / campaign / "plans" / "reviews" / "planning-review-request-sanitized.json"),
            }, status="READY_FOR_MODEL_REVIEW", next_action="plan.review.run")

        return self._stamp(self._guard(command, operation))

