from __future__ import annotations

from app import planning_orchestrator
from app.engine_api import EngineResult
from app.engine_api_v1_4 import EngineV14
from app.planning_contract_v2 import contract_v2


ENGINE_API_VERSION = "1.5"


class EngineV15(EngineV14):
    """Engine 1.5 makes the planning publication-risk scale explicit."""

    def _stamp(self, result: EngineResult) -> EngineResult:
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def planning_review(self, *args, **kwargs) -> EngineResult:
        planning_orchestrator.contract = contract_v2
        return self._stamp(super().planning_review(*args, **kwargs))

    def capabilities(self) -> EngineResult:
        result = super().capabilities()
        result.data["capabilities"]["plan"]["risk_scale"] = "1=minimal publication risk; 10=highest publication risk"
        return self._stamp(result)

