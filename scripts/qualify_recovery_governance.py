"""Executed reference recovery plus catalog protocol tests, NOT real OpenMetadata.

The catalog peer is explicitly imported from tests/support. Do not count it as a
provider deployment. SQLite/HTTP/reporting/backup/restore use the real code paths.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
import httpx
from support.openmetadata_emulator import CatalogEmulator
from ilc.backup import backup_reference,restore_reference
from ilc.canonical import canonical,code_manifest,read_json,immutable_write,digest
from ilc.fixtures import create_fixture
from ilc.governance import build_export,Publisher,RemoteOutcomeUnknown
from ilc.hosting import serve_report
from ilc.journal import Journal
from ilc.pipeline import Pipeline,git_identity
from ilc.report_api import create_app
from ilc.reporting import render_snapshot
from ilc.source_api import serving


def qualify(output:Path,rows:int=10000)->dict:
    if output.exists():raise FileExistsError('Use a new output directory; no overwrite')
    output=output.resolve();output.mkdir(parents=True);output.chmod(0o700)
    work=output/'work';evidence=output/'evidence';work.mkdir();evidence.mkdir()
    start=time.perf_counter()
    contract=read_json(ROOT/'contracts/sales.json');profile=read_json(ROOT/'profiles/reference.json')
    settings=read_json(ROOT/'governance/openmetadata.example.json')
    def save(name,value):immutable_write(evidence/name,canonical(value))
    src=work/'source';manifest=create_fixture(src,contract,rows)
    root=work/'runtime'
    pipe=Pipeline(ROOT,root,ROOT/'contracts/sales.json',ROOT/'profiles/reference.json')
    token=secrets.token_urlsafe(32)
    access={'schema_version':'ilc-access/1','principals':[{
        'name':'qualification-reader','token_sha256':hashlib.sha256(token.encode()).hexdigest(),
        'sites':contract['sites'],'permissions':['report','catalog','evidence']}]}
    headers={'Authorization':'Bearer '+token}
    restored_pipeline=None
    try:
        with serving(src) as url:accepted=pipe.execute('backup-baseline',manifest['as_of'],src,url)
        assert accepted['status']=='ACCEPTED' and accepted['observed_captured_rows']==rows
        state=pipe.journal.state()
        consumer=Journal(root,profile,read_only=True)
        try:
            with serve_report(create_app(consumer,contract,access)) as url,httpx.Client(base_url=url,trust_env=False,timeout=15) as client:
                r=client.get('/api/report',headers=headers);r.raise_for_status();before=r.json()
        finally:consumer.close()
        save('acceptance.json',accepted);save('report-before-restore.json',before)
        server=CatalogEmulator()
        with server.serving() as url:
            settings['api_url']=url;plan=build_export(pipe.journal,settings)
            publisher=Publisher(settings,'ephemeral-emulator-token',root/'governance-outbox')
            try:
                governance=publisher.publish(plan,allow_writes=True)
                writes_before=sum(m in ('PUT','POST') for m,_,_ in server.calls)
                assert publisher.publish(plan,allow_writes=True)==governance
                assert writes_before==sum(m in ('PUT','POST') for m,_,_ in server.calls)
            finally:publisher.close()
            backup=backup_reference(pipe.journal,work/'reference-snapshot.zip')
            pipe.close()
            original=root.with_name('runtime-original-retained')
            root.rename(original) # Original is retained, never removed or overwritten.
            restored=restore_reference(work/'reference-snapshot.zip',root,backup['archive_sha256'])
            assert original.is_dir()
            restored_pipeline=Pipeline(ROOT,root,ROOT/'contracts/sales.json',ROOT/'profiles/reference.json')
            replay=restored_pipeline.execute('backup-baseline',manifest['as_of'],src,'http://127.0.0.1:1')
            assert replay['invocation']=='REPLAY_OF_ACCEPTED_BATCH'
            assert restored_pipeline.journal.state()==state
            publisher=Publisher(settings,'ephemeral-emulator-token',root/'governance-outbox')
            try:
                restored_governance=publisher.publish(plan,allow_writes=True)
                assert restored_governance==governance
                assert writes_before==sum(m in ('PUT','POST') for m,_,_ in server.calls)
            finally:publisher.close()
            consumer=Journal(root,profile,read_only=True)
            try:
                with serve_report(create_app(consumer,contract,access)) as url,httpx.Client(base_url=url,trust_env=False,timeout=15) as client:
                    r=client.get('/api/report',headers=headers);r.raise_for_status();after=r.json()
                    assert after['dataset_batch_id']==before['dataset_batch_id']
                    assert after['generation']==before['generation'] and after['totals']==before['totals']
                    assert client.get('/api/report').status_code==401
            finally:consumer.close()
        # Separate failure experiment: exact HTTP semantics modelled with MockTransport.
        lost=CatalogEmulator();lost.fail_after_write=True
        p=Publisher(settings,'ephemeral-model-token',work/'lost-response-ledger',transport=httpx.MockTransport(lost.handler))
        try:
            try:p.publish(plan,allow_writes=True)
            except RemoteOutcomeUnknown:pass
            else:raise AssertionError('Expected lost-response branch was not exercised')
        finally:p.close()
        p=Publisher(settings,'ephemeral-model-token',work/'lost-response-ledger',transport=httpx.MockTransport(lost.handler))
        try:
            recovered_catalog=p.publish(plan,allow_writes=True)
            assert len([c for c in lost.calls if c[0]=='PUT' and c[1].endswith('/databases')])==1
        finally:p.close()
        save('governance-plan.json',plan);save('governance-readback.json',governance)
        save('backup-receipt.json',backup);save('restore-receipt.json',restored)
        save('report-after-restore.json',after);save('replay-after-restore.json',replay)
        (evidence/'restored-report.html').write_text(render_snapshot(after),encoding='utf-8')
        summary={'schema_version':'p01-recovery-governance-qualification/1','project':'P01',
            'status':'REFERENCE_RECOVERY_AND_PROTOCOL_CHECKS_EXECUTED',
            'reference_restore':{'sqlite_backup_api_used':True,'original_runtime_retained':True,
                'same_path_identity':True,'generation':after['generation'],'totals_equal':True,
                'report_reread_over_real_http':True,'unauthenticated_refused':True,
                'accepted_replay_http_source_offline':True,'publication_state_equal':True,
                'governance_outbox_restored':True,'catalog_replay_additional_writes':0,
                'archive_sha256':backup['archive_sha256'],'restored_files':backup['files']},
            'openmetadata':{'scope':'PROTOCOL_EMULATOR_NOT_OPENMETADATA_PRODUCT',
                'loopback_http_executed':True,'tables':governance['tables_read_back'],
                'lineage_edges':governance['lineage_edges_read_back'],
                'quality_results':governance['quality_results_read_back'],
                'lost_response_test':'HTTPX_MOCK_TRANSPORT',
                'database_create_requests_after_lost_response':1,
                'server_product_qualified':False,'server_rbac_qualified':False},
            'native_profile':'NOT_RUN','fabric':'NOT_RUN','power_bi':'NOT_RUN',
            'source_rows':rows,'gold_rows':accepted['gold_fact_rows'],
            'git':git_identity(ROOT),'source_code':code_manifest(ROOT),
            'elapsed_seconds':round(time.perf_counter()-start,6),
            'external_system_mutations':0,'personal_pc_access':False,
            'limits':['Same-path single-host SQLite recovery; not PostgreSQL DR or power-loss qualification',
                      'Governance HTTP peer is a named test emulator; no claim of provider compatibility or RBAC',
                      'Reference archive excludes credentials/access policies; reauthorization is external']}
        save('qualification.json',summary)
        return summary
    finally:
        pipe.close()
        if restored_pipeline:restored_pipeline.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--rows',type=int,default=10000)
    args=parser.parse_args();print(json.dumps(qualify(args.output,args.rows),indent=2))
if __name__=='__main__':main()
