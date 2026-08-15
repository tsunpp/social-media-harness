from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v1_2 import EngineV12
from app.review_orchestrator import DEFAULT_FFMPEG
from app.states import ALL_STATES


ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Social Media Harness engine 1.2")
    root.add_argument("--root", type=Path, default=ROOT)
    root.add_argument("--db", type=Path)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("recover")
    commands.add_parser("capabilities")

    campaign = commands.add_parser("campaign")
    campaign_commands = campaign.add_subparsers(dest="campaign_command", required=True)
    start = campaign_commands.add_parser("start")
    start.add_argument("--slug", required=True)
    start.add_argument("--title", required=True)
    campaign_commands.add_parser("list")
    status = campaign_commands.add_parser("status")
    status.add_argument("--slug", required=True)
    history = campaign_commands.add_parser("history")
    history.add_argument("--slug", required=True)
    advance = campaign_commands.add_parser("advance")
    advance.add_argument("--slug", required=True)
    advance.add_argument("--to", required=True, choices=ALL_STATES)
    advance.add_argument("--actor", default="codex")
    advance.add_argument("--note", default="")

    plan_prepare = commands.add_parser("plan-prepare")
    plan_prepare.add_argument("--project", required=True)
    plan_prepare.add_argument("--campaign", required=True)
    plan_review = commands.add_parser("plan-review")
    plan_review.add_argument("--project", required=True)
    plan_review.add_argument("--campaign", required=True)
    plan_review.add_argument("--plan", type=Path)
    plan_review.add_argument("--run-apis", action="store_true")
    plan_review.add_argument("--revision-count", type=int, default=0)

    video = commands.add_parser("review-video")
    video.add_argument("--campaign", required=True)
    video.add_argument("--version", required=True)
    video.add_argument("--run-apis", action="store_true")
    video.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    video.add_argument("--revision-count", type=int, default=0)
    for name in ("review-image", "finalize", "archive"):
        commands.add_parser(name)
    return root


def execute(args):
    engine = EngineV12(args.root, args.db)
    if args.command == "recover":
        return engine.recover()
    if args.command == "capabilities":
        return engine.capabilities()
    if args.command == "campaign":
        if args.campaign_command == "start":
            return engine.start_campaign(args.slug, args.title)
        if args.campaign_command == "list":
            return engine.campaigns()
        if args.campaign_command == "status":
            return engine.campaign_status(args.slug)
        if args.campaign_command == "history":
            return engine.campaign_history(args.slug)
        return engine.advance(args.slug, args.to, args.actor, args.note)
    if args.command == "plan-prepare":
        return engine.planning_prepare(args.project, args.campaign)
    if args.command == "plan-review":
        return engine.planning_review(args.project, args.campaign, args.plan, args.run_apis, args.revision_count)
    if args.command == "review-video":
        return engine.video_review(args.campaign, args.version, args.run_apis, args.ffmpeg, args.revision_count)
    return engine.unavailable(args.command)


def main(argv=None) -> int:
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3


if __name__ == "__main__":
    raise SystemExit(main())

