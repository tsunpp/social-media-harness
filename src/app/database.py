from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaigns (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    revision_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_slug TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (campaign_slug) REFERENCES campaigns(slug)
);

CREATE INDEX IF NOT EXISTS idx_state_events_campaign
ON state_events(campaign_slug, id);

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    original_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    width INTEGER,
    height INTEGER,
    duration_seconds REAL,
    captured_at TEXT,
    orientation TEXT,
    thumbnail_path TEXT,
    proxy_path TEXT,
    keyframes_json TEXT NOT NULL DEFAULT '[]',
    processing_status TEXT NOT NULL,
    sensitive_metadata INTEGER NOT NULL DEFAULT 0,
    warning TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_media_type
ON assets(media_type, filename);

CREATE TABLE IF NOT EXISTS campaign_assets (
    campaign_slug TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (campaign_slug, asset_id),
    FOREIGN KEY (campaign_slug) REFERENCES campaigns(slug),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);
"""


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)

