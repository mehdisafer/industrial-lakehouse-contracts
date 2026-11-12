"""Execute only on a disposable, explicitly authorized native demo database."""
import argparse
import json
from pathlib import Path
from ilc.canonical import read_json
from ilc.fixtures import create_fixture
from ilc.native import require_native, seed_postgres
from ilc.source_api import serving


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    args=parser.parse_args()
    require_native()
    if args.output.exists():raise FileExistsError('Use a new native work directory')
    contract=read_json(args.repo/'contracts/sales.json')
    profile=read_json(args.repo/'profiles/native.json')
    manifest=create_fixture(args.output/'fixture',contract,rows=10000)
    seeded=seed_postgres(args.output/'fixture',contract,profile)
    from ilc.orchestration import accepted_sales_job
    with serving(args.output/'fixture') as url:
        config={'repo':str(args.repo.resolve()),'root':str((args.output/'runtime').resolve()),
                'contract':'contracts/sales.json','profile':'profiles/native.json',
                'fixture':str((args.output/'fixture').resolve()),'api_url':url,'key':'native-first',
                'until':manifest['as_of']}
        result=accepted_sales_job.execute_in_process(run_config={'ops':{'execute_accepted_batch':{'config':config}}})
        if not result.success:raise RuntimeError('Native Dagster run failed')
        receipt=result.output_for_node('execute_accepted_batch')
    (args.output/'native-result.json').write_text(json.dumps({'seed':seeded,'dagster_run_id':result.run_id,'receipt':receipt},indent=2)+'\n')

if __name__=='__main__':main()
