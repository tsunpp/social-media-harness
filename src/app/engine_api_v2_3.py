from __future__ import annotations
from app.engine_api_v2_2 import EngineV22
ENGINE_API_VERSION="2.3"
class EngineV23(EngineV22):
    def _stamp(self,result):result.engine_api_version=ENGINE_API_VERSION;return result
    def capabilities(self):
        result=super().capabilities(); result.data["capabilities"]["acceptance_integrity"]={
            "implemented":True,"documentary_missing_evidence_generation":False,"contract_render_sync_required":True,
            "explicit_resolution_semantics":True,"modality_arbitration":{"motion":"minimax_complete_video","visual":"claude_systematic_timeline","facts_and_contract":"codex"},
            "dual_pass_after_sync":True,"cross_version_attribution_validation":True,"blind_leakage_validation":True}
        return self._stamp(result)

