from __future__ import annotations
from pathlib import Path
from typing import Any
from app.narrative_planning import narrative_review_contract
from app.planning_orchestrator import write_json
from app.planning_orchestrator_v2_1 import prepare_narrative_review as prepare_v21, run_narrative_review, validate_narrative_plan

def prepare_narrative_review(root: Path, project: str, campaign: str, plan_path: Path | None = None) -> dict[str, Any]:
    request=prepare_v21(root,project,campaign,plan_path)
    request["mandatory_reviewer_output_contract"]=narrative_review_contract()
    request["pass_conditions"]=[
        "opening creates an explicit audience question",
        "middle contains a visible change, discovery, or causal progression",
        "one evidence-supported visual climax or reveal exists",
        "ending fulfills the opening promise",
        "every text beat advances understanding instead of labeling the image",
        "every narrative beat maps to authentic source asset IDs",
    ]
    target=root/"campaigns"/campaign/"plans"/"narrative-reviews"/"narrative-review-request.json"
    write_json(target,request)
    return request
