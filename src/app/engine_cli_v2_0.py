from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.engine_api_v2_0 import EngineV20
from app.engine_cli_v1_9 import parser as parser_v19


def parser() -> argparse.ArgumentParser:
    root = parser_v19()
    commands = next(x for x in root._actions if isinstance(x, argparse._SubParsersAction))
    p = commands.add_parser("final-package"); p.add_argument("--spec", type=Path, required=True); p.add_argument("--build", action="store_true")
    p = commands.add_parser("verify-package"); p.add_argument("--archive-id", required=True)
    return root


def execute(args):
    engine = EngineV20(args.root, args.db)
    if args.command == "recover": return engine.recover()
    if args.command == "capabilities": return engine.capabilities()
    if args.command == "final-package": return engine.final_package(args.spec, args.build)
    if args.command == "verify-package": return engine.final_package_verify(args.archive_id)
    from app.engine_cli_v1_9 import execute as execute_v19
    result = execute_v19(args); result.engine_api_version = "2.0"; return result


def main(argv=None) -> int:
    result = execute(parser().parse_args(argv))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 3
