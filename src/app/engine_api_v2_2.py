from __future__ import annotations
from pathlib import Path
from app.engine_api_v2_1 import EngineV21
from app.planning_orchestrator_v2_2 import prepare_narrative_review

ENGINE_API_VERSION="2.2"
class EngineV22(EngineV21):
    def _stamp(self,result): result.engine_api_version=ENGINE_API_VERSION; return result
    def narrative_plan_prepare(self,project:str,campaign:str,plan_path:Path|None=None):
        command="narrative-plan.prepare"
        return self._stamp(self._guard(command,lambda:self._success(command,prepare_narrative_review(self.root,project,campaign,plan_path),status="READY_FOR_DUAL_NARRATIVE_REVIEW",next_action="run_narrative_review")))
