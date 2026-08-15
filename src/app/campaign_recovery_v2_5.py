from __future__ import annotations

from pathlib import Path

from app.campaigns import get_campaign, utc_now, validate_slug
from app.database import connect, initialize


def register_existing_campaign(root: Path, db_path: Path, slug: str, title: str) -> dict:
    validate_slug(slug)
    campaign = root / "campaigns" / slug
    if not campaign.is_dir():
        raise FileNotFoundError(campaign)
    if not title.strip():
        raise ValueError("Campaign title cannot be empty")
    initialize(db_path)
    try:
        return get_campaign(db_path, slug)
    except KeyError:
        pass
    now = utc_now()
    with connect(db_path) as connection:
        connection.execute(
            "INSERT INTO campaigns(slug, title, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (slug, title.strip(), "NEW", now, now),
        )
        connection.execute(
            "INSERT INTO state_events(campaign_slug, from_state, to_state, actor, note, created_at) VALUES (?, NULL, ?, ?, ?, ?)",
            (slug, "NEW", "engine_v2_5_recovery", "Registered an existing Campaign at NEW; no prior stage was trusted or skipped.", now),
        )
    return get_campaign(db_path, slug)
