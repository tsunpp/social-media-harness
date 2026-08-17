from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.review_policy import utc_now
from app.visual_style_profiles import public_style_contract, resolve_visual_style, validate_segment_style_contract
from app.direction_alignment_v2_6 import validate_alignment


PASS_DECISIONS = {"PASS", "APPROVE"}


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_segment_plan(plan: dict[str, Any]) -> None:
    required = {"schema_version", "project", "campaign", "plan_id", "candidate_schemes", "selected_scheme"}
    missing = required - set(plan)
    if missing:
        raise ValueError(f"Segment plan missing fields: {sorted(missing)}")
    if len(plan["candidate_schemes"]) < 2:
        raise ValueError("Codex must propose at least two candidate segmentation schemes")
    selected = next((x for x in plan["candidate_schemes"] if x.get("scheme_id") == plan["selected_scheme"]), None)
    if not selected:
        raise ValueError("selected_scheme must reference a candidate scheme")
    segments = selected.get("segments", [])
    if not segments:
        raise ValueError("Selected scheme must contain one or more segments")
    ids = [x.get("segment_id") for x in segments]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("Segment IDs must be non-empty and unique")
    for segment in segments:
        for key in ("purpose", "duration_seconds", "visual_brief", "production_route", "continuity_in", "continuity_out", "acceptance_criteria"):
            if key not in segment:
                raise ValueError(f"Segment {segment.get('segment_id')} missing {key}")


def prepare_segment_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    path = _resolve(root, plan_path)
    plan = read_json(path)
    validate_segment_plan(plan)
    if (root / "campaigns" / plan["campaign"] / "direction" / "required.json").is_file():
        result = validate_alignment(root, plan["campaign"], "shot-to-function-map", plan)
        if result["status"] != "PASS":
            raise ValueError(f"Shot-to-function mapping diverges from confirmed direction: {result}")
        selected = next(x for x in plan["candidate_schemes"] if x["scheme_id"] == plan["selected_scheme"])
        for segment in selected["segments"]:
            if not segment.get("asset_id") or not segment.get("narrative_function"):
                raise ValueError("Direction-enabled shot mapping requires asset_id and narrative_function for every segment")
    visual_style = resolve_visual_style(root, plan["campaign"])
    validate_segment_style_contract(plan, visual_style)
    work_dir = path.parent / "segmented-workflow"
    request = {
        "schema_version": 1,
        "created_at": utc_now(),
        "review_stage": "SEGMENTATION_CONSENSUS",
        "plan": plan,
        "evidence_contract": {
            "claude": "complete brief, asset inventory, all candidate schemes, every segment brief and continuity contract",
            "minimax": "complete brief, representative motion evidence, all candidate schemes, generation routes and continuity risks",
        },
        "required_reviewers": ["claude", "minimax"],
        "consensus_rule": "both reviewers PASS the same selected scheme before any segment may execute",
        "direction_alignment": result if 'result' in locals() else None,
    }
    if visual_style is not None:
        request["visual_style_profile"] = visual_style["id"]
        request["visual_style_contract"] = public_style_contract(visual_style)
        request["evidence_contract"]["claude"] += "; verify composition, lighting, color, editorial function, continuity and originality against the selected abstract style contract"
        request["typography_gate"] = {
            "required_before_render_when_text_is_present": True,
            "contract_schema": "schemas/typography_contract.schema.json",
            "director": "app.typography_director",
            "shared_targets": ["video", "post", "cover"],
            "claude_checks": ["art direction", "hierarchy", "phone legibility", "shot-specific placement", "palette relationship", "no hollow or generic subtitle treatment"],
        }
    write_json(work_dir / "segmentation-review-request.json", request)
    write_json(work_dir / "workflow-state.json", {
        "plan_id": plan["plan_id"], "status": "AWAITING_SEGMENTATION_REVIEWS",
        "completed_segments": [], "updated_at": utc_now(),
    })
    return request



def authorize_segment_generation(root: Path, generation_spec: Path) -> dict[str, Any]:
    spec_path = _resolve(root, generation_spec)
    spec = read_json(spec_path)
    workflow = spec.get("segmented_workflow")
    if not workflow:
        raise ValueError("New video generation requires segmented_workflow metadata and prior dual-model segmentation consensus")
    plan_path = _resolve(root, workflow.get("plan", ""))
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)
    plan = read_json(plan_path)
    validate_segment_plan(plan)
    state = read_json(plan_path.parent / "segmented-workflow" / "workflow-state.json")
    if state.get("status") not in {"SEGMENTATION_CONSENSUS_REACHED", "SEGMENTS_IN_PROGRESS", "READY_FOR_CONTINUITY_REVIEW"}:
        raise ValueError("Video generation is blocked until Claude and MiniMax approve the segmentation plan")
    scheme = next(x for x in plan["candidate_schemes"] if x["scheme_id"] == plan["selected_scheme"])
    segment_id = workflow.get("segment_id")
    if segment_id not in {x["segment_id"] for x in scheme["segments"]}:
        raise ValueError("Generation spec segment_id is not part of the approved scheme")
    return {"plan": plan, "state": state, "segment_id": segment_id}
def record_segmentation_consensus(root: Path, plan_path: Path, claude_review: Path, minimax_review: Path) -> dict[str, Any]:
    path = _resolve(root, plan_path)
    plan = read_json(path)
    validate_segment_plan(plan)
    reviews = {"claude": read_json(_resolve(root, claude_review)), "minimax": read_json(_resolve(root, minimax_review))}
    selected = plan["selected_scheme"]
    problems = []
    for reviewer, review in reviews.items():
        if review.get("decision") not in PASS_DECISIONS:
            problems.append(f"{reviewer} did not pass")
        if review.get("approved_scheme_id") != selected:
            problems.append(f"{reviewer} did not approve selected scheme {selected}")
    if problems:
        raise ValueError("Segmentation consensus not reached: " + "; ".join(problems))
    work_dir = path.parent / "segmented-workflow"
    state = read_json(work_dir / "workflow-state.json")
    state.update({"status": "SEGMENTATION_CONSENSUS_REACHED", "approved_scheme_id": selected, "reviews": {
        "claude": str(_resolve(root, claude_review)), "minimax": str(_resolve(root, minimax_review)),
    }, "updated_at": utc_now()})
    write_json(work_dir / "workflow-state.json", state)
    return state


def register_segment_result(root: Path, plan_path: Path, segment_id: str, production_job: Path, review_aggregation: Path) -> dict[str, Any]:
    path = _resolve(root, plan_path)
    plan = read_json(path)
    validate_segment_plan(plan)
    work_dir = path.parent / "segmented-workflow"
    state = read_json(work_dir / "workflow-state.json")
    if state.get("status") not in {"SEGMENTATION_CONSENSUS_REACHED", "SEGMENTS_IN_PROGRESS", "READY_FOR_CONTINUITY_REVIEW"}:
        raise ValueError("Segments cannot execute before Claude and MiniMax reach segmentation consensus")
    scheme = next(x for x in plan["candidate_schemes"] if x["scheme_id"] == plan["selected_scheme"])
    if segment_id not in {x["segment_id"] for x in scheme["segments"]}:
        raise ValueError(f"Unknown segment: {segment_id}")
    job_path = _resolve(root, production_job)
    aggregation_path = _resolve(root, review_aggregation)
    job, aggregation = read_json(job_path), read_json(aggregation_path)
    if aggregation.get("next_action") not in {"PASS", "APPROVED", "READY_FOR_FINAL", "FINAL_CANDIDATE"}:
        raise ValueError(f"Segment {segment_id} has not passed dual-model review")
    reviewer_decisions = aggregation.get("reviewer_decisions", aggregation.get("decisions", {}))
    if reviewer_decisions and not all(value in PASS_DECISIONS for value in reviewer_decisions.values()):
        raise ValueError(f"Segment {segment_id} is missing a reviewer PASS")
    record = {
        "segment_id": segment_id, "production_job": str(job_path), "production_job_sha256": sha256(job_path),
        "review_aggregation": str(aggregation_path), "review_aggregation_sha256": sha256(aggregation_path),
        "output": job.get("output"), "status": "SEGMENT_APPROVED", "updated_at": utc_now(),
    }
    write_json(work_dir / "segments" / segment_id / "approved-result.json", record)
    completed = [x for x in state.get("completed_segments", []) if x != segment_id] + [segment_id]
    state.update({"status": "SEGMENTS_IN_PROGRESS", "completed_segments": completed, "updated_at": utc_now()})
    write_json(work_dir / "workflow-state.json", state)
    return record


def prepare_assembly_gate(root: Path, plan_path: Path) -> dict[str, Any]:
    path = _resolve(root, plan_path)
    plan = read_json(path)
    validate_segment_plan(plan)
    work_dir = path.parent / "segmented-workflow"
    state = read_json(work_dir / "workflow-state.json")
    scheme = next(x for x in plan["candidate_schemes"] if x["scheme_id"] == plan["selected_scheme"])
    expected = [x["segment_id"] for x in scheme["segments"]]
    missing = [x for x in expected if x not in state.get("completed_segments", [])]
    if missing:
        raise ValueError(f"Cannot assemble; segments have not passed review: {missing}")
    continuity = {
        "schema_version": 1, "status": "READY_FOR_CONTINUITY_REVIEW", "ordered_segments": expected,
        "checks": ["narrative handoff", "motion direction", "subject identity", "color and exposure", "audio", "typography", "transition rhythm"],
        "rule": "assemble only after continuity review passes; final master must then pass the existing complete-video Claude and MiniMax review",
        "updated_at": utc_now(),
    }
    write_json(work_dir / "continuity-review-request.json", continuity)
    state.update({"status": "READY_FOR_CONTINUITY_REVIEW", "updated_at": utc_now()})
    write_json(work_dir / "workflow-state.json", state)
    return continuity


def authorize_final_review(root: Path, plan_path: Path, continuity_review: Path, final_job: Path) -> dict[str, Any]:
    path = _resolve(root, plan_path)
    work_dir = path.parent / "segmented-workflow"
    continuity = read_json(_resolve(root, continuity_review))
    if continuity.get("decision") not in PASS_DECISIONS:
        raise ValueError("Final assembly is blocked until continuity review passes")
    job_path = _resolve(root, final_job)
    if not job_path.is_file():
        raise FileNotFoundError(job_path)
    state = read_json(work_dir / "workflow-state.json")
    state.update({"status": "READY_FOR_COMPLETE_VIDEO_DUAL_REVIEW", "final_job": str(job_path), "updated_at": utc_now()})
    write_json(work_dir / "workflow-state.json", state)
    return state
