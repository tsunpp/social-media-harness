from __future__ import annotations

import re
from pathlib import Path


CONTENT_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){1,4}$")


def validate_content_slug(slug: str) -> str:
    if not CONTENT_SLUG.fullmatch(slug):
        raise ValueError("content_slug must contain 2-5 lowercase English/alphanumeric keywords separated by hyphens")
    forbidden = {"ready", "approved", "published", "unpublished", "pending"}
    if forbidden.intersection(slug.split("-")):
        raise ValueError("content_slug cannot contain mutable workflow status words")
    return slug


def archive_name(archive_id: str, content_slug: str) -> str:
    return f"{archive_id}--{validate_content_slug(content_slug)}"


def locate_archive(root: Path, archive_id: str) -> Path:
    exact = root / "archive" / archive_id
    if exact.is_dir():
        return exact
    matches = sorted(path for path in (root / "archive").glob(f"{archive_id}--*") if path.is_dir())
    if len(matches) != 1:
        reason = "not found" if not matches else "ambiguous"
        raise FileNotFoundError(f"Archive {archive_id} {reason}")
    return matches[0]
