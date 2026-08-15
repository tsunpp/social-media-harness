from __future__ import annotations

import json

from app.engine_api_v1_6 import EngineV16
from app.engine_cli_v1_2 import parser


def execute(args):
    engine = EngineV16(args.root, args.db)
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
    return engine.unavailable(args.command)


def main(argv=None) -> int:
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3


if __name__ == "__main__":
    raise SystemExit(main())

