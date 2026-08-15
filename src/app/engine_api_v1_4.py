from __future__ import annotations

from pathlib import Path

from app.engine_api import EngineResult
from app.engine_api_v1_3 import EngineV13


ENGINE_API_VERSION = "1.4"


class EngineV14(EngineV13):
    """Engine 1.4 resolves explicit relative plan paths against the project root."""

    def _stamp(self, result: EngineResult) -> EngineResult:
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def planning_review(
        self,
        project: str,
        campaign: str,
        plan_path: Path | None = None,
        run_apis: bool = False,
        revision_count: int = 0,
    ) -> EngineResult:
        if plan_path is not None and not plan_path.is_absolute():
            plan_path = self.root / plan_path
        return self._stamp(super().planning_review(project, campaign, plan_path, run_apis, revision_count))

