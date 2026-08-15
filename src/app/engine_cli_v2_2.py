from __future__ import annotations
import json
from app.engine_api_v2_2 import EngineV22
from app.engine_cli_v2_1 import parser
def execute(args):
    engine=EngineV22(args.root,args.db)
    if args.command=="narrative-plan-prepare": return engine.narrative_plan_prepare(args.project,args.campaign,args.plan)
    if args.command=="narrative-plan-review": return engine.narrative_plan_review(args.request,args.revision_count)
    from app.engine_cli_v2_1 import execute as old
    result=old(args); result.engine_api_version="2.2"; return result
def main(argv=None):
    result=execute(parser().parse_args(argv)); print(json.dumps(result.to_dict(),ensure_ascii=False,indent=2)); return 0 if result.ok else 3
