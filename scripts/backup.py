"""Explicit reference snapshot or same-path restore; never overwrite a runtime."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ilc.backup import backup_reference, restore_reference
from ilc.canonical import read_json, canonical, immutable_write
from ilc.journal import Journal
from ilc.errors import PipelineError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for name in ('create','restore'):
        p=sub.add_parser(name);p.add_argument('--root',type=Path,required=True)
        p.add_argument('--archive',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
        if name=='restore':p.add_argument('--expected-sha256',required=True)
    args=parser.parse_args()
    try:
        if args.receipt.exists():
            parser.error('Receipt already exists; no overwrite')
        if args.action=='create':
            if not (args.root/'.ilc-sandbox.json').is_file():
                parser.error('Backup requires an existing runtime')
            journal=Journal(args.root,read_json(ROOT/'profiles/reference.json'))
            try:result=backup_reference(journal,args.archive)
            finally:journal.close()
        else:result=restore_reference(args.archive,args.root,args.expected_sha256)
        immutable_write(args.receipt,canonical(result));print(json.dumps(result,indent=2));return 0
    except PipelineError as exc:
        print(json.dumps({'status':'ERROR','code':exc.code}),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
