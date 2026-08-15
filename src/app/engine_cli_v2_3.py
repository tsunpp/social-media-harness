from __future__ import annotations
import json
from app.engine_api_v2_3 import EngineV23
from app.engine_cli_v2_2 import parser
def execute(args):
    engine=EngineV23(args.root,args.db)
    if args.command=="capabilities":return engine.capabilities()
    from app.engine_cli_v2_2 import execute as old
    result=old(args);result.engine_api_version="2.3";return result
def main(argv=None):
    result=execute(parser().parse_args(argv));print(json.dumps(result.to_dict(),ensure_ascii=False,indent=2));return 0 if result.ok else 3

