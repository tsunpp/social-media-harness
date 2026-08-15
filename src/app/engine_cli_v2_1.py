from __future__ import annotations
import argparse, json
from pathlib import Path
from app.engine_api_v2_1 import EngineV21
from app.engine_cli_v2_0 import parser as parser_v20

def parser():
    root=parser_v20(); commands=next(x for x in root._actions if isinstance(x,argparse._SubParsersAction))
    p=commands.add_parser("narrative-plan-prepare"); p.add_argument("--project",required=True); p.add_argument("--campaign",required=True); p.add_argument("--plan",type=Path)
    p=commands.add_parser("narrative-plan-review"); p.add_argument("--request",type=Path,required=True); p.add_argument("--revision-count",type=int,default=0)
    return root
def execute(args):
    engine=EngineV21(args.root,args.db)
    if args.command=="narrative-plan-prepare": return engine.narrative_plan_prepare(args.project,args.campaign,args.plan)
    if args.command=="narrative-plan-review": return engine.narrative_plan_review(args.request,args.revision_count)
    from app.engine_cli_v2_0 import execute as old
    result=old(args); result.engine_api_version="2.1"; return result
def main(argv=None):
    result=execute(parser().parse_args(argv)); print(json.dumps(result.to_dict(),ensure_ascii=False,indent=2)); return 0 if result.ok else 3
