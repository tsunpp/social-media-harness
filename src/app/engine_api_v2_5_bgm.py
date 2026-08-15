from __future__ import annotations

from app.bgm_orchestrator_v2_5 import prepare_bgm_contract, review_contract
from app.engine_api_v2_5 import EngineV25


class EngineV25BGM(EngineV25):
    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["bgm_stage"] = {
            "implemented": True,
            "candidate_count": 3,
            "story_beat_contract_required": True,
            "silent_master_immutable": True,
            "selection_authority": "minimax_complete_audio_video",
            "claude_authority": ["visual_competition", "subtitle_readability", "structural_compatibility"],
            "kimi_authority": ["story_contract_alignment", "provenance", "cross_stage_integrity", "rights_record_completeness"],
            "original_generation_provenance_required": True,
            "owner_publication_gate": True,
        }
        return result

    def bgm_prepare(self, campaign, silent_master, final_story_contract, strategy, directions):
        return prepare_bgm_contract(self.root, campaign, silent_master, final_story_contract, strategy, directions)

    def bgm_review_contract(self, candidate_ids):
        return review_contract(candidate_ids)
