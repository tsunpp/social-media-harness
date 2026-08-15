from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database import connect, initialize
from app.states import INITIAL_STATE, can_transition


CAMPAIGN_DIRECTORIES = (
    "source",
    "selected",
    "plans",
    "drafts",
    "reviews",
    "decisions",
    "final/instagram",
    "final/youtube",
)

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_slug(slug: str) -> None:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("slug 只能使用小写字母、数字和单个连字符")


def create_campaign(root: Path, db_path: Path, slug: str, title: str) -> Path:
    validate_slug(slug)
    if not title.strip():
        raise ValueError("title 不能为空")

    initialize(db_path)
    campaign_path = root / "campaigns" / slug
    if campaign_path.exists():
        raise FileExistsError(f"项目目录已存在: {campaign_path}")

    for relative in CAMPAIGN_DIRECTORIES:
        (campaign_path / relative).mkdir(parents=True, exist_ok=True)

    now = utc_now()
    brief = {
        "schema_version": 1,
        "slug": slug,
        "title": title.strip(),
        "content_type": "vertical_documentary_short",
        "objective": "用真实现场素材制作品牌纪实内容",
        "platforms": ["instagram", "youtube_shorts"],
        "target_duration_seconds": {"min": 15, "max": 30},
        "aspect_ratio": "9:16",
        "language": "待填写",
        "topic": "待填写",
        "human_notes": "",
        "visual_style_profile": "vogue-derived-editorial",
        "created_at": now,
    }
    (campaign_path / "brief.yaml").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with connect(db_path) as connection:
        try:
            connection.execute(
                "INSERT INTO campaigns(slug, title, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (slug, title.strip(), INITIAL_STATE, now, now),
            )
            connection.execute(
                "INSERT INTO state_events(campaign_slug, from_state, to_state, actor, note, created_at) "
                "VALUES (?, NULL, ?, ?, ?, ?)",
                (slug, INITIAL_STATE, "system", "创建内容项目", now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"项目已存在于数据库: {slug}") from exc

    return campaign_path


def get_campaign(db_path: Path, slug: str):
    initialize(db_path)
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM campaigns WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise KeyError(f"未找到项目: {slug}")
    return dict(row)


def list_campaigns(db_path: Path) -> list[dict]:
    initialize(db_path)
    with connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def advance_campaign(db_path: Path, slug: str, target: str, actor: str, note: str) -> dict:
    campaign = get_campaign(db_path, slug)
    current = campaign["state"]
    if not can_transition(current, target):
        raise ValueError(f"不允许的状态变化: {current} -> {target}")

    revision_count = campaign["revision_count"]
    if current == "REVISION_REQUIRED" and target == "DRAFT_RENDERED":
        revision_count += 1
        if revision_count > 2:
            raise ValueError("自动返工已超过两轮，必须进入 HUMAN_DECISION")

    now = utc_now()
    with connect(db_path) as connection:
        connection.execute(
            "UPDATE campaigns SET state = ?, revision_count = ?, updated_at = ? WHERE slug = ?",
            (target, revision_count, now, slug),
        )
        connection.execute(
            "INSERT INTO state_events(campaign_slug, from_state, to_state, actor, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (slug, current, target, actor, note, now),
        )
    return get_campaign(db_path, slug)


def campaign_history(db_path: Path, slug: str) -> list[dict]:
    get_campaign(db_path, slug)
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT from_state, to_state, actor, note, created_at "
            "FROM state_events WHERE campaign_slug = ? ORDER BY id",
            (slug,),
        ).fetchall()
    return [dict(row) for row in rows]
