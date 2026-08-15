from __future__ import annotations

from pathlib import Path

from app.engine_api_v1_8 import EngineV18
from app.segmented_video_orchestrator import (
    authorize_final_review, authorize_segment_generation, prepare_assembly_gate, prepare_segment_plan,
    record_segmentation_consensus, register_segment_result,
)


ENGINE_API_VERSION = "1.9"


class EngineV19(EngineV18):
    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["segmented_video_workflow"] = {
            "implemented": True,
            "mandatory_for_new_video_generation": True,
            "gates": ["codex_candidate_schemes", "claude_minimax_segmentation_consensus", "per_segment_dual_review", "continuity_review", "complete_video_dual_review"],
            "segment_production_uses": "Engine 1.8 video generation and complete-evidence review",
            "whole_video_shortcut": False,
        }
        return self._stamp(result)

    def segment_plan_prepare(self, plan: Path):
        command = "video.segment-plan.prepare"
        return self._stamp(self._guard(command, lambda: self._success(command, prepare_segment_plan(self.root, plan), status="AWAITING_SEGMENTATION_REVIEWS", next_action="video.segment-plan.consensus")))

    def video_generate(self, project: str, campaign: str, spec: Path, execute: bool = False):
        command = "video.generate.run" if execute else "video.generate.prepare"
        def operation():
            authorization = authorize_segment_generation(self.root, spec)
            result = super(EngineV19, self).video_generate(project, campaign, spec, execute)
            if result.ok:
                result.data["segmented_workflow"] = {"plan_id": authorization["plan"]["plan_id"], "approved_scheme_id": authorization["plan"]["selected_scheme"], "segment_id": authorization["segment_id"]}
            return result
        return self._stamp(self._guard(command, operation))
    def segment_plan_consensus(self, plan: Path, claude_review: Path, minimax_review: Path):
        command = "video.segment-plan.consensus"
        return self._stamp(self._guard(command, lambda: self._success(command, record_segmentation_consensus(self.root, plan, claude_review, minimax_review), status="SEGMENTATION_CONSENSUS_REACHED", next_action="video.segment.execute")))

    def segment_accept(self, plan: Path, segment_id: str, job: Path, aggregation: Path):
        command = "video.segment.accept"
        return self._stamp(self._guard(command, lambda: self._success(command, register_segment_result(self.root, plan, segment_id, job, aggregation), status="SEGMENT_APPROVED", next_action="video.segment.next_or_assemble")))

    def assembly_prepare(self, plan: Path):
        command = "video.assembly.prepare"
        return self._stamp(self._guard(command, lambda: self._success(command, prepare_assembly_gate(self.root, plan), status="READY_FOR_CONTINUITY_REVIEW", next_action="video.assembly.continuity-review")))

    def final_review_authorize(self, plan: Path, continuity_review: Path, final_job: Path):
        command = "video.final-review.authorize"
        return self._stamp(self._guard(command, lambda: self._success(command, authorize_final_review(self.root, plan, continuity_review, final_job), status="READY_FOR_COMPLETE_VIDEO_DUAL_REVIEW", next_action="video.pipeline.prepare")))
