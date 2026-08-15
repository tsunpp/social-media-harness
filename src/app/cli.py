from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.assets import attach_assets_to_campaign, scan_assets
from app.campaigns import (
    advance_campaign,
    campaign_history,
    create_campaign,
    get_campaign,
    list_campaigns,
)
from app.database import initialize
from app.states import ALL_STATES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "harness.db"


def print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def self_check(root: Path, db_path: Path) -> dict:
    required = [
        "app", "config/platforms", "policies", "schemas", "templates",
        "asset_library/incoming", "asset_library/catalog",
        "asset_library/proxies", "asset_library/thumbnails",
        "asset_library/keyframes", "campaigns", "data", "logs", "tests",
    ]
    missing = [item for item in required if not (root / item).exists()]
    initialize(db_path)
    return {
        "ok": not missing,
        "root": str(root),
        "database": str(db_path),
        "missing_paths": missing,
        "campaign_count": len(list_campaigns(db_path)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Social Media Content Harness")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite数据库路径")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="初始化数据库")

    new = subparsers.add_parser("new", help="创建内容项目")
    new.add_argument("--slug", required=True)
    new.add_argument("--title", required=True)

    status = subparsers.add_parser("status", help="查看项目状态")
    status.add_argument("--slug", required=True)

    subparsers.add_parser("list", help="列出所有内容项目")

    advance = subparsers.add_parser("advance", help="推进项目状态")
    advance.add_argument("--slug", required=True)
    advance.add_argument("--to", required=True, choices=ALL_STATES)
    advance.add_argument("--actor", default="human")
    advance.add_argument("--note", default="")

    history = subparsers.add_parser("history", help="查看状态历史")
    history.add_argument("--slug", required=True)

    scan = subparsers.add_parser(
        "scan-assets", help="扫描素材并生成目录、缩略图、关键帧和代理文件"
    )
    scan.add_argument("--ffmpeg", type=Path, required=True)
    scan.add_argument("--campaign", help="把本批素材挂接到指定内容项目")
    scan.add_argument("--catalog-only", action="store_true", help="只建档，不生成衍生文件")

    subparsers.add_parser("self-check", help="检查项目骨架")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.db)
            print_json({"ok": True, "database": str(args.db)})
        elif args.command == "new":
            path = create_campaign(ROOT, args.db, args.slug, args.title)
            print_json({"ok": True, "campaign": args.slug, "path": str(path)})
        elif args.command == "status":
            print_json(get_campaign(args.db, args.slug))
        elif args.command == "list":
            print_json(list_campaigns(args.db))
        elif args.command == "advance":
            print_json(
                advance_campaign(args.db, args.slug, args.to, args.actor, args.note)
            )
        elif args.command == "history":
            print_json(campaign_history(args.db, args.slug))
        elif args.command == "scan-assets":
            if not args.ffmpeg.is_file():
                raise ValueError(f"FFmpeg不存在: {args.ffmpeg}")
            assets = scan_assets(
                ROOT, args.db, args.ffmpeg, generate=not args.catalog_only
            )
            manifest = None
            if args.campaign:
                manifest = attach_assets_to_campaign(
                    ROOT, args.db, args.campaign, assets
                )
            print_json(
                {
                    "ok": True,
                    "asset_count": len(assets),
                    "ready": sum(
                        asset["processing_status"] == "ready" for asset in assets
                    ),
                    "partial": sum(
                        asset["processing_status"] == "partial" for asset in assets
                    ),
                    "sensitive_metadata": sum(
                        asset["sensitive_metadata"] for asset in assets
                    ),
                    "manifest": str(manifest) if manifest else None,
                }
            )
        elif args.command == "self-check":
            result = self_check(ROOT, args.db)
            print_json(result)
            return 0 if result["ok"] else 1
    except (ValueError, KeyError, FileExistsError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    return 0

