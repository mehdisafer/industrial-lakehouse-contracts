"""Explicit local demo commands. No cloud deployment, push, delete or hidden fallback."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from .canonical import read_json
from .contracts import validate_contract, validate_profile
from .journal import Journal
from .errors import PipelineError
from .fixtures import create_fixture
from .pipeline import Pipeline


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest='command',required=True)
    validate=sub.add_parser('validate')
    validate.add_argument('--contract',type=Path,default=Path('contracts/sales.json'))
    validate.add_argument('--profile',type=Path,default=Path('profiles/reference.json'))
    fixture=sub.add_parser('fixture')
    fixture.add_argument('--output',type=Path,required=True)
    fixture.add_argument('--rows',type=int,default=10000)
    fixture.add_argument('--seed',type=int,default=17)
    fixture.add_argument('--revision',type=int,default=0)
    fixture.add_argument('--anchor',default='2026-11-12T10:00:00Z')
    fixture.add_argument('--fault',choices=['duplicate_key','invalid_amount','schema_drift','orphan','overshipment','incorrect_total'])
    source=sub.add_parser('source-api')
    source.add_argument('--fixture',type=Path,required=True)
    source.add_argument('--port',type=int,default=8765)
    for name in ['run','status','report-api']:
        cmd=sub.add_parser(name)
        cmd.add_argument('--root',type=Path,required=True)
        cmd.add_argument('--contract',type=Path,default=Path('contracts/sales.json'))
        cmd.add_argument('--profile',type=Path,default=Path('profiles/reference.json'))
        if name=='run':
            cmd.add_argument('--fixture',type=Path,required=True)
            cmd.add_argument('--api-url',default=os.environ.get('ILC_API_URL','http://127.0.0.1:8765'))
            cmd.add_argument('--key',required=True)
            cmd.add_argument('--until',required=True)
            cmd.add_argument('--test-failpoint',choices=['after_target_commit','before_accept','after_accept'])
            cmd.add_argument('--test-crash',action='store_true')
        if name=='report-api':
            cmd.add_argument('--access-policy',type=Path,required=True)
            cmd.add_argument('--port',type=int,default=8766)
    args=parser.parse_args(argv)
    try:
        if args.command=='validate':
            contract=validate_contract(read_json(args.repo/args.contract))
            profile=validate_profile(read_json(args.repo/args.profile),contract)
            value={'status':'METADATA_VALID','entities':list(contract['entities']),'profile':profile['profile_id'],'execution_performed':False}
        elif args.command=='fixture':
            value=create_fixture(args.output,validate_contract(read_json(args.repo/'contracts/sales.json')),
                                 args.rows,args.seed,args.revision,args.anchor,args.fault)
        elif args.command=='source-api':
            from .source_api import build_server
            server=build_server(args.fixture,args.port)
            try:server.serve_forever()
            finally:server.server_close()
            return 0
        elif args.command in {'status','report-api'}:
            contract=validate_contract(read_json(args.repo/args.contract))
            profile=validate_profile(read_json(args.repo/args.profile),contract)
            journal=Journal(args.root,profile,read_only=True)
            try:
                if args.command=='status':
                    value=journal.state()
                else:
                    from .report_api import create_app
                    import uvicorn
                    uvicorn.run(create_app(journal,contract,read_json(args.access_policy)),host='127.0.0.1',port=args.port,access_log=False)
                    return 0
            finally:journal.close()
        else:
            pipeline=Pipeline(args.repo,args.root,args.repo/args.contract,args.repo/args.profile)
            try:
                if args.command=='run':
                    value=pipeline.execute(args.key,args.until,args.fixture,args.api_url,args.test_failpoint,args.test_crash)
            finally:pipeline.close()
        print(json.dumps(value,indent=2,allow_nan=False))
        return 2 if value.get('status')=='REJECTED' else 0
    except (PipelineError,ValueError) as exc:
        print(json.dumps({'status':'ERROR','code':getattr(exc,'code','INVALID_ARGUMENT')}),file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())
