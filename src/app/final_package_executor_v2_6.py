from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.archive_manifest_v2_6 import validate_archive_manifest
from app.contract_consistency_v2_6 import validate_final_contract
from app.final_package_executor import validate_archive_id
from app.image_review_orchestrator import sha256
from app.planning_orchestrator import read_json, write_json
from app.platform_profiles_v2_6 import validate_platform_output
from app.review_policy import utc_now
from app.direction_alignment_v2_6 import validate_alignment


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _paths(root: Path, spec: dict[str, Any]) -> dict[str, Path]:
    required = {"archive_id", "display_name", "campaign", "platform", "master_video", "render_manifest", "publishing_copy", "cover", "final_story_contract", "final_review", "technical_gate", "owner_approval"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Harness 2.6 final package missing fields: {sorted(missing)}")
    validate_archive_id(spec["archive_id"])
    if spec.get("publishing_authorized", False):
        raise ValueError("Final package construction cannot authorize publication")
    paths = {key: _resolve(root, spec[key]) for key in ("master_video", "render_manifest", "publishing_copy", "cover", "final_story_contract", "final_review", "technical_gate", "owner_approval")}
    direction_required = root / "campaigns" / spec["campaign"] / "direction" / "required.json"
    if direction_required.is_file():
        if not spec.get("direction_alignment_report"):
            raise ValueError("Direction-enabled Campaign final package requires direction_alignment_report")
        paths["direction_alignment_report"] = _resolve(root, spec["direction_alignment_report"])
    if spec.get("completion_gate"):
        paths["completion_gate"] = _resolve(root, spec["completion_gate"])
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{name}: {path}")
    return paths


def prepare_final_package_v2_6(root: Path, spec_path: Path) -> dict[str, Any]:
    spec = read_json(_resolve(root, spec_path)); paths = _paths(root, spec)
    render = read_json(paths["render_manifest"]); output = render.get("output", {})
    package = {"master": str(paths["master_video"]), "cover": str(paths["cover"]), **read_json(paths["publishing_copy"])}
    platform_result = validate_platform_output(root, spec["platform"], output, package)
    consistency = validate_final_contract(root, spec)
    direction = None
    if "direction_alignment_report" in paths:
        direction = validate_alignment(root, spec["campaign"], "publication-package", read_json(paths["direction_alignment_report"]))
        if direction["status"] != "PASS":
            raise ValueError(f"Publication package diverges from confirmed direction: {direction}")
    review = read_json(paths["final_review"])
    if review.get("next_action") != "FINAL_CANDIDATE" or review.get("blocking_issues"):
        raise ValueError("Final review has not cleared the candidate")
    technical = read_json(paths["technical_gate"])
    if technical.get("status") != "PASS" and technical.get("passed") is not True:
        raise ValueError("Technical gate has not passed")
    owner = read_json(paths["owner_approval"])
    if owner.get("owner_decision") not in {"APPROVED_FINAL", "APPROVED"} and owner.get("decision") not in {"APPROVED_FINAL", "APPROVED"}:
        raise ValueError("Persisted owner final approval is required")
    destination = root / "archive" / spec["archive_id"]
    if destination.exists():
        raise FileExistsError(f"Archive exists and cannot be overwritten: {destination}")
    return {"status": "READY_TO_BUILD_FINAL_PACKAGE", "archive_id": spec["archive_id"], "platform": platform_result, "consistency": consistency, "direction_alignment": direction, "destination": str(destination), "next_action": "final-package.build"}


def build_final_package_v2_6(root: Path, spec_path: Path) -> dict[str, Any]:
    prepared = prepare_final_package_v2_6(root, spec_path)
    spec = read_json(_resolve(root, spec_path)); paths = _paths(root, spec)
    destination = root / "archive" / spec["archive_id"]
    staging = root / "archive" / f".{spec['archive_id']}.staging"
    if staging.exists():
        raise FileExistsError(staging)
    try:
        mapping = {
            "master_video": Path("deliverables") / paths["master_video"].name,
            "cover": Path("deliverables") / paths["cover"].name,
            "publishing_copy": Path("deliverables") / paths["publishing_copy"].name,
            "render_manifest": Path("provenance/render-manifest.json"),
            "final_story_contract": Path("story-contract-final.json"),
            "final_review": Path("reviews/final-review.json"),
            "technical_gate": Path("reviews/technical-gate.json"),
            "owner_approval": Path("approvals/owner-final-approval.json"),
        }
        if "completion_gate" in paths:
            mapping["completion_gate"] = Path("reviews/completion-gate.json")
        if "direction_alignment_report" in paths:
            mapping["direction_alignment_report"] = Path("reviews/direction-alignment.json")
        for key, relative in mapping.items():
            target = staging / relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(paths[key], target)
        assets = []
        for file in sorted(path for path in staging.rglob("*") if path.is_file()):
            assets.append({"path": file.relative_to(staging).as_posix(), "bytes": file.stat().st_size, "sha256": sha256(file)})
        manifest = {
            "schema_version": 3, "archive_id": spec["archive_id"], "display_name": spec["display_name"],
            "campaign": spec["campaign"], "created_at": utc_now(), "status": "APPROVED_NOT_PUBLISHED",
            "platforms": [spec["platform"]], "master": mapping["master_video"].as_posix(), "assets": assets,
            "story_contract": mapping["final_story_contract"].as_posix(),
            "reviews": [mapping["final_review"].as_posix(), mapping["technical_gate"].as_posix()],
            "owner_approval": mapping["owner_approval"].as_posix(), "publishing_authorized": False,
            "publication_gate": "EXPLICIT_OWNER_PUBLISH_INSTRUCTION_REQUIRED",
        }
        if "direction_alignment_report" in mapping:
            manifest["direction_alignment"] = mapping["direction_alignment_report"].as_posix()
        write_json(staging / "manifest.json", manifest)
        validate_archive_manifest(staging, manifest)
        staging.rename(destination)
        return {"status": "APPROVED_NOT_PUBLISHED", "archive_id": spec["archive_id"], "destination": str(destination), "asset_count": len(assets), "publishing_authorized": False, "next_action": "owner_publication_gate"}
    except Exception:
        if staging.exists(): shutil.rmtree(staging)
        raise


def verify_final_package_v2_6(root: Path, archive_id: str) -> dict[str, Any]:
    validate_archive_id(archive_id)
    archive = root / "archive" / archive_id
    result = validate_archive_manifest(archive, read_json(archive / "manifest.json"))
    result["status"] = "PASS"
    return result

