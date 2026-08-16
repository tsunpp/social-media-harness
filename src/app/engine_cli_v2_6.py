from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v2_6 import EngineV26
from app.engine_cli_v2_5 import parser as parser_v2_5


def parser():
    root = parser_v2_5()
    commands = next(x for x in root._actions if isinstance(x, argparse._SubParsersAction))
    recover = commands.choices["recover"]
    recover.add_argument("--project")
    recover.add_argument("--campaign")
    auth = commands.add_parser("authorization-resolve")
    auth.add_argument("--project", required=True); auth.add_argument("--campaign", required=True)
    auth.add_argument("--recipient", required=True); auth.add_argument("--material", action="append", dest="materials", required=True)
    auth.add_argument("--identifiable-people", action="store_true"); auth.add_argument("--metadata-stripped", action="store_true")
    auth.add_argument("--privacy-preflight", default="PASS", choices=["PASS", "FAIL", "PENDING"])
    platform = commands.add_parser("platform-validate")
    platform.add_argument("--platform", required=True); platform.add_argument("--output", type=Path, required=True); platform.add_argument("--package", type=Path, required=True)
    consistency = commands.add_parser("contract-consistency")
    consistency.add_argument("--spec", type=Path, required=True)
    audio = commands.add_parser("audio-authority")
    audio.add_argument("--provider", required=True); audio.add_argument("--capability", required=True)
    archive = commands.add_parser("archive-manifest-validate")
    archive.add_argument("--archive", type=Path, required=True)
    for name in ("direction-context", "direction-status", "direction-questions", "direction-draft"):
        item = commands.add_parser(name)
        item.add_argument("--project", required=True); item.add_argument("--campaign", required=True)
    answer = commands.add_parser("direction-answer")
    answer.add_argument("--project", required=True); answer.add_argument("--campaign", required=True); answer.add_argument("--answers", type=Path, required=True)
    confirm = commands.add_parser("direction-confirm")
    confirm.add_argument("--project", required=True); confirm.add_argument("--campaign", required=True); confirm.add_argument("--contract", type=Path, required=True); confirm.add_argument("--actor", default="owner")
    validate = commands.add_parser("direction-validate")
    validate.add_argument("--project", required=True); validate.add_argument("--campaign", required=True); validate.add_argument("--artifact-type", required=True); validate.add_argument("--artifact", type=Path, required=True)
    invalidate = commands.add_parser("direction-invalidate")
    invalidate.add_argument("--project", required=True); invalidate.add_argument("--campaign", required=True); invalidate.add_argument("--reason", required=True); invalidate.add_argument("--actor", required=True)
    panel = commands.add_parser("four-agent-review")
    panel.add_argument("--spec", type=Path, required=True)
    panel.add_argument("--run-apis", action="store_true")
    return root


def execute(args):
    engine = EngineV26(args.root, args.db)
    if args.command == "capabilities": return engine.capabilities()
    if args.command == "recover": return engine.recover(project=args.project, campaign=args.campaign)
    if args.command == "authorization-resolve":
        return engine.authorization_resolve(args.project, args.campaign, args.recipient, args.materials, args.identifiable_people, args.metadata_stripped, args.privacy_preflight)
    if args.command == "platform-validate":
        return engine.platform_validate(args.platform, json.loads(args.output.read_text(encoding="utf-8-sig")), json.loads(args.package.read_text(encoding="utf-8-sig")))
    if args.command == "contract-consistency": return engine.contract_consistency(args.spec)
    if args.command == "audio-authority": return engine.audio_authority(args.provider, args.capability)
    if args.command == "archive-manifest-validate": return engine.archive_manifest_validate(args.archive)
    if args.command == "direction-context": return engine.direction_context(args.project, args.campaign)
    if args.command == "direction-status": return engine.direction_status(args.project, args.campaign)
    if args.command == "direction-questions": return engine.direction_questions(args.project, args.campaign)
    if args.command == "direction-answer": return engine.direction_answer(args.project, args.campaign, args.answers)
    if args.command == "direction-draft": return engine.direction_draft(args.project, args.campaign)
    if args.command == "direction-confirm": return engine.direction_confirm(args.project, args.campaign, args.contract, args.actor)
    if args.command == "direction-validate": return engine.direction_validate(args.project, args.campaign, args.artifact_type, args.artifact)
    if args.command == "direction-invalidate": return engine.direction_invalidate(args.project, args.campaign, args.reason, args.actor)
    if args.command == "four-agent-review": return engine.four_agent_review(args.spec, args.run_apis)
    from app.engine_cli_v2_5 import execute as old_execute
    result = old_execute(args); result.engine_api_version = "2.6"; return result


def main(argv=None):
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3

