from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from app.image_review_orchestrator import sha256
from app.archive_naming import archive_name, locate_archive, validate_content_slug
from app.planning_orchestrator import read_json, write_json
from app.review_policy import utc_now


ARCHIVE_ID = re.compile(r"^SM(?P<month>\d{2})(?P<day>\d{2})(?P<year>\d{4})(?P<sequence>\d{2})$")
FINAL_PASS = {"FINAL_CANDIDATE", "PASS", "APPROVED", "READY_FOR_PUBLICATION_PACKAGE"}


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def allocate_archive_id(root: Path, local_date: date) -> str:
    prefix = f"SM{local_date:%m%d%Y}"
    sequences = []
    for path in (root / "archive").glob(prefix + "[0-9][0-9]*"):
        match = ARCHIVE_ID.fullmatch(path.name.split("--", 1)[0])
        if match:
            sequences.append(int(match.group("sequence")))
    sequence = max(sequences, default=0) + 1
    if sequence > 99:
        raise ValueError(f"Daily archive sequence exhausted for {local_date.isoformat()}")
    return f"{prefix}{sequence:02d}"


def validate_archive_id(archive_id: str) -> None:
    match = ARCHIVE_ID.fullmatch(archive_id)
    if not match:
        raise ValueError("Archive ID must match SMmmddyyyyNN")
    try:
        date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError as exc:
        raise ValueError("Archive ID contains an invalid calendar date") from exc


def validate_package_spec(root: Path, spec: dict[str, Any]) -> dict[str, Path]:
    required = {"schema_version", "archive_id", "display_name", "campaign", "source_version", "language", "master_video", "render_manifest", "publishing_copy", "covers", "final_review", "technical_gate"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Final package spec missing fields: {sorted(missing)}")
    validate_archive_id(spec["archive_id"])
    if spec.get("publishing_authorized", False):
        raise ValueError("Package construction cannot authorize publication")
    paths = {key: _resolve(root, spec[key]) for key in ("master_video", "render_manifest", "publishing_copy", "final_review", "technical_gate")}
    for key, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{key}: {path}")
    covers = [_resolve(root, value) for value in spec["covers"]]
    if not covers:
        raise ValueError("At least one reviewed cover is required")
    for path in covers:
        if not path.is_file():
            raise FileNotFoundError(path)
    paths["covers"] = covers  # type: ignore[assignment]
    final_review = read_json(paths["final_review"])
    if final_review.get("next_action") not in FINAL_PASS or final_review.get("blocking_issues"):
        raise ValueError("Complete-master dual review has not passed")
    dual_pass = final_review.get("reason") == "both_independent_reviewers_passed"
    decisions = final_review.get("reviewer_decisions", final_review.get("decisions", {}))
    dual_pass = dual_pass or (isinstance(decisions, dict) and {"claude", "minimax"}.issubset(decisions) and all(decisions[x] in {"PASS", "APPROVE"} for x in ("claude", "minimax")))
    if not dual_pass:
        raise ValueError("Final review does not prove independent Claude and MiniMax approval")
    technical = read_json(paths["technical_gate"])
    passed = technical.get("status") == "PASS" or technical.get("passed") is True
    if not passed:
        raise ValueError("Technical gate has not passed")
    copy = read_json(paths["publishing_copy"])
    if copy.get("publishing_authorized", False):
        raise ValueError("Publishing copy must remain unauthorized during package construction")
    for platform in ("instagram", "youtube_shorts"):
        if platform not in copy:
            raise ValueError(f"Publishing copy missing {platform}")
    render = read_json(paths["render_manifest"])
    output = render.get("output", {})
    if output.get("resolution") != "1080x1920":
        raise ValueError("Platform master must be 1080x1920 (9:16)")
    duration = float(output.get("duration_seconds", 0))
    if not 3 <= duration <= 60:
        raise ValueError("Vertical short-form master duration must be between 3 and 60 seconds")
    if output.get("color") not in {None, "SDR BT.709"}:
        raise ValueError("Platform master must use SDR BT.709")
    return paths


def prepare_final_package(root: Path, spec_path: Path) -> dict[str, Any]:
    path = _resolve(root, spec_path)
    spec = read_json(path)
    paths = validate_package_spec(root, spec)
    destination_name = archive_name(spec["archive_id"], spec["content_slug"]) if spec.get("content_slug") else spec["archive_id"]
    destination = root / "archive" / destination_name
    if destination.exists():
        raise FileExistsError(f"Archive already exists and will not be overwritten: {destination}")
    manifest = read_json(paths["render_manifest"])
    copy = read_json(paths["publishing_copy"])
    return {
        "schema_version": 1,
        "status": "READY_TO_BUILD_FINAL_PACKAGE",
        "archive_id": spec["archive_id"],
        "destination": str(destination),
        "master_sha256": sha256(paths["master_video"]),
        "cover_count": len(paths["covers"]),
        "selected_cover": copy.get("covers", {}).get("recommended", spec["covers"][0]),
        "platforms": ["instagram_reels", "youtube_shorts"],
        "render_summary": {"output": manifest.get("output"), "duration_seconds": manifest.get("duration_seconds")},
        "gates": {"complete_master_review": "PASS", "technical": "PASS", "publishing_authorized": False},
        "next_action": "final-package.build",
    }


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + "\n", encoding="utf-8")


def build_final_package(root: Path, spec_path: Path) -> dict[str, Any]:
    path = _resolve(root, spec_path)
    spec = read_json(path)
    paths = validate_package_spec(root, spec)
    archive_id = spec["archive_id"]
    content_slug = validate_content_slug(spec["content_slug"]) if spec.get("content_slug") else None
    archive_dir_name = archive_name(archive_id, content_slug) if content_slug else archive_id
    destination = root / "archive" / archive_dir_name
    staging = root / "archive" / f".{archive_dir_name}.staging"
    if destination.exists() or staging.exists():
        raise FileExistsError(f"Archive or staging path already exists: {destination}")
    copy = read_json(paths["publishing_copy"])
    try:
        instagram = staging / "platforms" / "instagram-reels"
        youtube = staging / "platforms" / "youtube-shorts"
        media = staging / "media"
        covers_dir = staging / "covers"
        reviews_dir = staging / "reviews"
        for folder in (instagram, youtube, media, covers_dir, reviews_dir):
            folder.mkdir(parents=True, exist_ok=True)
        master_name = f"{archive_id}-master.mp4"
        shutil.copy2(paths["master_video"], media / master_name)
        shutil.copy2(paths["master_video"], instagram / "reel.mp4")
        shutil.copy2(paths["master_video"], youtube / "short.mp4")
        archived_covers = []
        for index, cover in enumerate(paths["covers"], 1):
            target = covers_dir / f"{archive_id}-cover-{index:02d}{cover.suffix.lower()}"
            shutil.copy2(cover, target); archived_covers.append(target)
        selected = archived_covers[0]
        recommended = copy.get("covers", {}).get("recommended")
        if recommended:
            recommended_name = Path(recommended).name
            for source, archived in zip(paths["covers"], archived_covers):
                if source.name == recommended_name:
                    selected = archived; break
        shutil.copy2(selected, instagram / "cover.jpg")
        shutil.copy2(selected, youtube / "thumbnail.jpg")
        ig = copy["instagram"]; yt = copy["youtube_shorts"]
        _write_text(instagram / "caption.txt", ig["caption"])
        _write_text(instagram / "hashtags.txt", " ".join(ig.get("hashtags", [])))
        _write_text(instagram / "alt_text.txt", ig.get("alt_text", spec.get("default_alt_text", spec["display_name"])))
        _write_text(instagram / "publishing_notes.md", "Owner approval required. Documentary display; verify platform status immediately before posting.")
        _write_text(youtube / "title.txt", yt["title"])
        _write_text(youtube / "description.txt", yt["description"])
        _write_text(youtube / "tags.txt", ", ".join(x.lstrip("#") for x in yt.get("hashtags", [])))
        _write_text(youtube / "publishing_notes.md", "Owner approval required. Verify title, audience settings and platform status immediately before posting.")
        shutil.copy2(paths["publishing_copy"], staging / "publishing-copy.json")
        shutil.copy2(paths["final_review"], reviews_dir / "complete-master-review.json")
        shutil.copy2(paths["technical_gate"], reviews_dir / "technical-gate.json")
        files = sorted(x for x in staging.rglob("*") if x.is_file())
        checksums = {str(x.relative_to(staging)).replace("\\", "/"): sha256(x) for x in files}
        manifest = {
            "schema_version": 2, "archive_id": archive_id, "archive_name": archive_dir_name,
            "content_slug": content_slug, "display_name": spec["display_name"],
            "created_at": utc_now(), "campaign": spec["campaign"], "source_version": spec["source_version"],
            "language": spec["language"], "status": "READY_NOT_PUBLISHED",
            "platforms": ["instagram_reels", "youtube_shorts"],
            "default_cover": str(selected.relative_to(staging)).replace("\\", "/"),
            "publishing_authorized": False, "publication_gate": "OWNER_APPROVAL_REQUIRED",
            "checksums": checksums,
            "lookup_instruction": f"Load archive/{archive_id}/manifest.json when the owner references {archive_id}.",
        }
        write_json(staging / "manifest.json", manifest)
        # Verify every recorded checksum immediately before the atomic directory move.
        for relative, digest in checksums.items():
            if sha256(staging / relative) != digest:
                raise ValueError(f"Checksum verification failed: {relative}")
        staging.rename(destination)
        return {"archive_id": archive_id, "status": "READY_NOT_PUBLISHED", "destination": str(destination), "file_count": len(checksums) + 1, "publishing_authorized": False, "next_action": "owner_review_publication_package"}
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def verify_final_package(root: Path, archive_id: str) -> dict[str, Any]:
    validate_archive_id(archive_id)
    folder = locate_archive(root, archive_id)
    manifest = read_json(folder / "manifest.json")
    failures = []
    for relative, expected in manifest.get("checksums", {}).items():
        target = folder / relative
        if not target.is_file() or sha256(target) != expected:
            failures.append(relative)
    required = [
        "platforms/instagram-reels/reel.mp4", "platforms/instagram-reels/cover.jpg", "platforms/instagram-reels/caption.txt",
        "platforms/youtube-shorts/short.mp4", "platforms/youtube-shorts/thumbnail.jpg", "platforms/youtube-shorts/title.txt",
    ]
    missing = [x for x in required if not (folder / x).is_file()]
    if manifest.get("publishing_authorized") is not False:
        failures.append("publishing_authorized")
    return {"archive_id": archive_id, "status": "PASS" if not failures and not missing else "FAIL", "checksum_failures": failures, "missing": missing, "publishing_authorized": manifest.get("publishing_authorized")}
