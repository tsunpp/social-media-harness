from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v1_8 import EngineV18
from app.engine_cli_v1_7 import parser as parser_v17
from app.review_orchestrator import DEFAULT_FFMPEG


def parser() -> argparse.ArgumentParser:
    root = parser_v17()
    commands = next(action for action in root._actions if isinstance(action, argparse._SubParsersAction))
    pipeline = commands.add_parser("video-pipeline")
    pipeline.add_argument("--project", required=True)
    pipeline.add_argument("--campaign", required=True)
    pipeline.add_argument("--job", type=Path, required=True)
    pipeline.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    pipeline.add_argument("--run-apis", action="store_true")
    pipeline.add_argument("--revision-count", type=int, default=0)
    generation = commands.add_parser("generate-video")
    generation.add_argument("--project", required=True)
    generation.add_argument("--campaign", required=True)
    generation.add_argument("--spec", type=Path, required=True)
    generation.add_argument("--execute", action="store_true")
    return root


def execute(args):
    engine = EngineV18(args.root, args.db)
    if args.command == "recover": return engine.recover()
    if args.command == "capabilities": return engine.capabilities()
    if args.command == "campaign":
        if args.campaign_command == "start": return engine.start_campaign(args.slug, args.title)
        if args.campaign_command == "list": return engine.campaigns()
        if args.campaign_command == "status": return engine.campaign_status(args.slug)
        if args.campaign_command == "history": return engine.campaign_history(args.slug)
        return engine.advance(args.slug, args.to, args.actor, args.note)
    if args.command == "plan-prepare": return engine.planning_prepare(args.project, args.campaign)
    if args.command == "plan-review": return engine.planning_review(args.project, args.campaign, args.plan, args.run_apis, args.revision_count)
    if args.command == "review-video": return engine.video_review(args.campaign, args.version, args.run_apis, args.ffmpeg, args.revision_count)
    if args.command == "review-image": return engine.image_review(args.project, args.campaign, args.candidates, args.run_apis, args.revision_count)
    if args.command == "video-pipeline": return engine.video_pipeline(args.project, args.campaign, args.job, args.ffmpeg, args.run_apis, args.revision_count)
    if args.command == "generate-video": return engine.video_generate(args.project, args.campaign, args.spec, args.execute)
    return engine.unavailable(args.command)

def main(argv=None) -> int:
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3
