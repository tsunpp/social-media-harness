from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v2_6 import EngineV26
from app.engine_cli_v2_5 import parser as parser_v2_5


def parser():
    root = parser_v2_5()
    commands = next(x for x in root._actions if isinstance(x, argparse._SubParsersAction))
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
    return root


def execute(args):
    engine = EngineV26(args.root, args.db)
    if args.command == "capabilities": return engine.capabilities()
    if args.command == "authorization-resolve":
        return engine.authorization_resolve(args.project, args.campaign, args.recipient, args.materials, args.identifiable_people, args.metadata_stripped, args.privacy_preflight)
    if args.command == "platform-validate":
        return engine.platform_validate(args.platform, json.loads(args.output.read_text(encoding="utf-8-sig")), json.loads(args.package.read_text(encoding="utf-8-sig")))
    if args.command == "contract-consistency": return engine.contract_consistency(args.spec)
    if args.command == "audio-authority": return engine.audio_authority(args.provider, args.capability)
    if args.command == "archive-manifest-validate": return engine.archive_manifest_validate(args.archive)
    from app.engine_cli_v2_5 import execute as old_execute
    result = old_execute(args); result.engine_api_version = "2.6"; return result


def main(argv=None):
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3

