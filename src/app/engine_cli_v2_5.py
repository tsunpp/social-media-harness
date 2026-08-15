from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v2_5 import EngineV25
from app.engine_cli_v2_2 import parser as parser_v2_2


def parser():
    root = parser_v2_2()
    commands = next(x for x in root._actions if isinstance(x, argparse._SubParsersAction))
    handoff = commands.add_parser("openclaw-handoff")
    handoff.add_argument("--archive-id", required=True)
    handoff.add_argument("--platform", action="append", dest="platforms", choices=["instagram_reels", "youtube_shorts"])
    handoff.add_argument("--build", action="store_true")
    verify = commands.add_parser("verify-openclaw-handoff")
    verify.add_argument("--archive-id", required=True)
    bgm = commands.add_parser("bgm-prepare")
    bgm.add_argument("--campaign", required=True)
    bgm.add_argument("--silent-master", type=Path, required=True)
    bgm.add_argument("--story-contract", type=Path, required=True)
    bgm.add_argument("--strategy", type=Path, required=True)
    bgm.add_argument("--directions", type=Path, required=True)
    bgm_review = commands.add_parser("bgm-review-contract")
    bgm_review.add_argument("--candidate-id", action="append", required=True)
    register = commands.add_parser("register-existing-campaign")
    register.add_argument("--campaign", required=True)
    register.add_argument("--title", required=True)
    typography = commands.add_parser("typography-prepare")
    typography.add_argument("--campaign", required=True)
    typography.add_argument("--segments", type=Path, required=True)
    typography.add_argument("--evidence-image", action="append", type=Path, required=True)
    typography.add_argument("--output", type=Path)
    transfer = commands.add_parser("review-transfer-authorize")
    transfer.add_argument("--project", default="cannabis-social-media")
    transfer.add_argument("--campaign", required=True)
    transfer.add_argument("--recipient", action="append", dest="recipients", required=True, choices=["claude", "minimax", "kimi-k3"])
    transfer.add_argument("--material", action="append", dest="materials", required=True)
    transfer.add_argument("--privacy-preflight", default="PASS", choices=["PASS", "FAIL", "PENDING"])
    transfer.add_argument("--fact-preflight", default="PASS", choices=["PASS", "FAIL", "PENDING"])
    return root


def execute(args):
    engine = EngineV25(args.root, args.db)
    if args.command == "capabilities":
        return engine.capabilities()
    if args.command == "openclaw-handoff":
        return engine.openclaw_handoff(args.archive_id, args.platforms, args.build)
    if args.command == "verify-openclaw-handoff":
        return engine.openclaw_handoff_verify(args.archive_id)
    if args.command == "final-package":
        return engine.final_package(args.spec, args.build)
    if args.command == "verify-package":
        return engine.final_package_verify(args.archive_id)
    if args.command == "bgm-prepare":
        strategy = json.loads(args.strategy.read_text(encoding="utf-8-sig"))
        directions = json.loads(args.directions.read_text(encoding="utf-8-sig"))
        data = engine.bgm_prepare(args.campaign, args.silent_master, args.story_contract, strategy, directions)
        return engine._success("bgm.prepare", data, status=data["status"], next_action="generate_bgm_candidates")
    if args.command == "bgm-review-contract":
        data = engine.bgm_review_contract(args.candidate_id)
        return engine._success("bgm.review-contract", data, status="READY_FOR_BGM_REVIEW")
    if args.command == "register-existing-campaign":
        return engine.register_existing_campaign(args.campaign, args.title)
    if args.command == "typography-prepare":
        return engine.typography_prepare(args.campaign, args.segments, args.evidence_image, args.output)
    if args.command == "review-transfer-authorize":
        return engine.review_transfer_authorize(
            args.project, args.campaign, args.recipients, args.materials, args.privacy_preflight, args.fact_preflight
        )
    from app.engine_cli_v2_3 import execute as old_execute
    result = old_execute(args)
    result.engine_api_version = "2.5"
    return result


def main(argv=None):
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3
