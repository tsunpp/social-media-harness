from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v1_9 import EngineV19
from app.engine_cli_v1_8 import parser as parser_v18


def parser() -> argparse.ArgumentParser:
    root = parser_v18()
    commands = next(x for x in root._actions if isinstance(x, argparse._SubParsersAction))
    p = commands.add_parser("segment-plan-prepare"); p.add_argument("--plan", type=Path, required=True)
    p = commands.add_parser("segment-plan-consensus"); p.add_argument("--plan", type=Path, required=True); p.add_argument("--claude-review", type=Path, required=True); p.add_argument("--minimax-review", type=Path, required=True)
    p = commands.add_parser("segment-accept"); p.add_argument("--plan", type=Path, required=True); p.add_argument("--segment-id", required=True); p.add_argument("--job", type=Path, required=True); p.add_argument("--aggregation", type=Path, required=True)
    p = commands.add_parser("assembly-prepare"); p.add_argument("--plan", type=Path, required=True)
    p = commands.add_parser("final-review-authorize"); p.add_argument("--plan", type=Path, required=True); p.add_argument("--continuity-review", type=Path, required=True); p.add_argument("--final-job", type=Path, required=True)
    return root


def execute(args):
    engine = EngineV19(args.root, args.db)
    if args.command == "recover": return engine.recover()
    if args.command == "capabilities": return engine.capabilities()
    if args.command == "generate-video": return engine.video_generate(args.project, args.campaign, args.spec, args.execute)
    if args.command == "video-pipeline": return engine.video_pipeline(args.project, args.campaign, args.job, args.ffmpeg, args.run_apis, args.revision_count)
    if args.command == "segment-plan-prepare": return engine.segment_plan_prepare(args.plan)
    if args.command == "segment-plan-consensus": return engine.segment_plan_consensus(args.plan, args.claude_review, args.minimax_review)
    if args.command == "segment-accept": return engine.segment_accept(args.plan, args.segment_id, args.job, args.aggregation)
    if args.command == "assembly-prepare": return engine.assembly_prepare(args.plan)
    if args.command == "final-review-authorize": return engine.final_review_authorize(args.plan, args.continuity_review, args.final_job)
    # Preserve all 1.8 commands while stamping results as 1.9.
    from app.engine_cli_v1_8 import execute as execute_v18
    result = execute_v18(args); result.engine_api_version = "1.9"; return result


def main(argv=None) -> int:
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3
