from __future__ import annotations

import json

from pathlib import Path

from app.engine_api_v1_6 import EngineV16
from app.head_discovery import current_head, head_chain
from app.image_review_orchestrator import prepare_image_review, run_image_review


ENGINE_API_VERSION = "1.7"


class EngineV17(EngineV16):
    """Engine 1.7 adds complete-set image and cover review."""

    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["image"] = {
            "implemented": True,
            "complete_candidate_set": True,
            "privacy_preflight": True,
            "dual_multimodal_review": ["claude", "minimax"],
            "paid_api_only_for": "image.review.run",
        }
        result.data["capabilities"]["review.image"] = result.data["capabilities"]["image"]
        result.data["recovery_head_selection"] = "append_only_previous_head_chain"
        return self._stamp(result)

    def recover(self, head: str | None = None):
        command = "recover"

        def operation():
            head_path = current_head(self.root) if head is None else self.root / head
            chain = head_chain(self.root, head_path)
            base_state = None
            stage_summary = None
            overlays = []
            decisions = []
            superseded = []
            next_action = None
            for _, record in chain:
                base_state = record.get("base_state", base_state)
                stage_summary = record.get("current_stage_summary", stage_summary)
                for relative in record.get("state_overlays_in_order", []):
                    if relative not in overlays: overlays.append(relative)
                latest_overlay = record.get("latest_state_overlay")
                if latest_overlay and latest_overlay not in overlays: overlays.append(latest_overlay)
                for relative in record.get("active_decisions", []):
                    if relative not in decisions: decisions.append(relative)
                for item in record.get("superseded_records", []):
                    if item not in superseded: superseded.append(item)
                next_action = record.get("next_action", record.get("next_stage_after_owner_acceptance", next_action))
            if not base_state or not stage_summary:
                raise KeyError("HEAD chain must resolve base_state and current_stage_summary")
            references = [base_state, stage_summary, *overlays, *decisions]
            missing = sorted({relative for relative in references if not (self.root / relative).is_file()})
            if missing:
                return self._failure(command, "RECOVERY_REFERENCE_MISSING", "Missing recovery references: " + ", ".join(missing), next_action="repair_recovery_chain")
            relative_head = str(head_path.relative_to(self.root)).replace("\\", "/")
            return self._success(command, {
                "head": relative_head,
                "head_chain": [str(path.relative_to(self.root)).replace("\\", "/") for path, _ in chain],
                "base_state": json.loads((self.root / base_state).read_text(encoding="utf-8-sig")),
                "overlays": [json.loads((self.root / relative).read_text(encoding="utf-8-sig")) for relative in overlays],
                "active_decisions": [json.loads((self.root / relative).read_text(encoding="utf-8-sig")) for relative in decisions],
                "superseded_records": superseded,
                "reference_count": len(set(references)),
            }, status="RECOVERED", next_action=next_action)

        return self._stamp(self._guard(command, operation))

    def image_review(self, project: str, campaign: str, candidates: Path, run_apis: bool = False, revision_count: int = 0):
        command = "image.review.run" if run_apis else "image.review.prepare"

        def operation():
            request = prepare_image_review(self.root, project, campaign, candidates)
            if run_apis:
                aggregation = run_image_review(self.root, request, revision_count)
                return self._success(command, aggregation, status=aggregation["next_action"], next_action=aggregation["next_action"])
            return self._success(command, {
                "project": project,
                "campaign": campaign,
                "set_id": request["candidate_set"]["set_id"],
                "candidate_count": request["evidence_manifest"]["candidate_count"],
                "complete_candidate_set": True,
                "privacy_preflight": "PASS",
                "review_request": str((self.root / request["candidate_set_path"]).parent / "reviews" / "image-review-request-sanitized.json"),
            }, status="READY_FOR_MODEL_REVIEW", next_action="image.review.run")

        return self._stamp(self._guard(command, operation))
