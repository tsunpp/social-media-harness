from __future__ import annotations

from pathlib import Path

from app.engine_api_v2_0 import EngineV20
from app.planning_orchestrator_v2_1 import prepare_narrative_review, run_narrative_review


ENGINE_API_VERSION = "2.1"


class EngineV21(EngineV20):
    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["narrative_plan"] = {
            "implemented": True,
            "required_for_new_campaigns": True,
            "story_skeletons": 3,
            "required_beats": ["hook", "development", "turn", "reveal", "resolution"],
            "requires_claude_complete_visual_timeline": True,
            "requires_minimax_complete_source_proxies": True,
            "requires_evidence_for_every_beat": True,
            "production_before_gate": False,
        }
        return self._stamp(result)

    def narrative_plan_prepare(self, project: str, campaign: str, plan_path: Path | None = None):
        command = "narrative-plan.prepare"
        return self._stamp(self._guard(command, lambda: self._success(command, prepare_narrative_review(self.root, project, campaign, plan_path), status="READY_FOR_DUAL_NARRATIVE_REVIEW", next_action="run_narrative_review")))

    def narrative_plan_review(self, request_path: Path, revision_count: int = 0):
        command = "narrative-plan.review"
        from app.planning_orchestrator import read_json
        return self._stamp(self._guard(command, lambda: self._success(command, run_narrative_review(self.root, read_json(request_path), revision_count), status="NARRATIVE_REVIEW_COMPLETE", next_action="codex_narrative_adjudication")))

