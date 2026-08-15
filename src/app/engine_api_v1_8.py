from __future__ import annotations

from pathlib import Path

from app.engine_api_v1_7 import EngineV17
from app.video_generation_backends import execute_generation, prepare_generation
from app.video_production_orchestrator import prepare_video_pipeline, run_video_pipeline_review


ENGINE_API_VERSION = "1.8"


class EngineV18(EngineV17):
    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["video_pipeline"] = {
            "implemented": True,
            "backends": ["authentic_media", "comfyui_aki", "comfyui_standard", "minimax_h3_api", "ffmpeg"],
            "comfyui_cross_instance_fallback": False,
            "claude_evidence": "complete sampled timeline and caption boundaries",
            "minimax_evidence": "complete video with audio",
            "auto_revision_limit": 8,
        }
        result.data["capabilities"]["video_generation"] = {"implemented": True, "executable_backends": ["comfyui_aki:minimax_h3_i2v", "minimax_h3_api"], "standard_comfyui_enabled": False, "prepare_without_execution": True}
        return self._stamp(result)

    def video_pipeline(self, project: str, campaign: str, job: Path, ffmpeg: Path, run_apis: bool = False, revision_count: int = 0):
        command = "video.pipeline.review.run" if run_apis else "video.pipeline.prepare"

        def operation():
            request = prepare_video_pipeline(self.root, project, campaign, job, ffmpeg)
            if run_apis:
                state = run_video_pipeline_review(self.root, request, revision_count)
                return self._success(command, state, status=state["status"], next_action=state["status"])
            return self._success(command, {
                "project": project, "campaign": campaign, "job_id": request["production_job"]["job_id"],
                "video_sha256": request["evidence_manifest"]["video"]["sha256"],
                "timeline_frame_count": request["evidence_contract"]["frame_count"],
                "artifact_count": len(request["artifact_registry"]),
                "privacy_preflight": "PASS", "fact_preflight": "PASS", "technical_gate": "PASS",
                "review_request": str((self.root / request["production_job"]["job_manifest_path"]).parent / "reviews" / "video-pipeline" / "video-review-request-sanitized.json"),
            }, status="READY_FOR_MODEL_REVIEW", next_action="video.pipeline.review.run")

        return self._stamp(self._guard(command, operation))

    def video_generate(self, project: str, campaign: str, spec: Path, execute: bool = False):
        command = "video.generate.run" if execute else "video.generate.prepare"
        def operation():
            request = prepare_generation(self.root, project, campaign, spec)
            if execute:
                result = execute_generation(self.root, request)
                return self._success(command, result, status="GENERATED_AWAITING_REVIEW", next_action="video.pipeline.prepare")
            return self._success(command, {"job_id": request["job_id"], "backend": request["backend"], "source_sha256": request["source_sha256"], "output": request["output"], "privacy_preflight": "PASS", "fact_preflight": "PASS"}, status="READY_FOR_GENERATION", next_action="video.generate.run")
        return self._stamp(self._guard(command, operation))
