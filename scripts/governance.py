"""Plan or deliver accepted-generation metadata; no default outbound mutation."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ilc.canonical import canonical, immutable_write, read_json
from ilc.errors import PipelineError
from ilc.governance import build_export, Publisher
from ilc.journal import Journal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--profile',type=Path,default=ROOT/'profiles/reference.json')
    parser.add_argument('--settings',type=Path,default=ROOT/'governance/openmetadata.example.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--allow-catalog-writes',action='store_true')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists; choose a new receipt path')
    journal=None;publisher=None
    try:
        journal=Journal(args.root,read_json(args.profile),read_only=True)
        plan=build_export(journal,read_json(args.settings))
        if not args.publish:
            immutable_write(args.output,canonical(plan))
            print(json.dumps({'status':'PLAN_ONLY','batch_id':plan['batch_id'],'writes':0}))
            return 0
        if not args.allow_catalog_writes:parser.error('Explicit --allow-catalog-writes is required')
        token=os.environ.get('ILC_OPENMETADATA_TOKEN')
        if not token:parser.error('Set ILC_OPENMETADATA_TOKEN outside Git')
        publisher=Publisher(plan['settings'],token,args.root/'governance-outbox')
        result=publisher.publish(plan,allow_writes=True)
        immutable_write(args.output,canonical(result))
        print(json.dumps(result,indent=2))
        return 0
    except PipelineError as exc:
        print(json.dumps({'status':'ERROR','code':exc.code}),file=sys.stderr)
        return 1
    finally:
        if publisher:publisher.close()
        if journal:journal.close()

if __name__=='__main__':sys.exit(main())
