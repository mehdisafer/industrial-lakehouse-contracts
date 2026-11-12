"""Execute P01's bounded reference vertical slice; never claim native/cloud tests."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import httpx
from ilc.canonical import canonical,code_manifest,digest,read_json
from ilc.fixtures import create_fixture,make_records,write_fixture
from ilc.pipeline import Pipeline,git_identity
from ilc.journal import Journal
from ilc.reporting import render_snapshot
from ilc.report_api import create_app
from ilc.hosting import serve_report
from ilc.source_api import serving
from ilc.storage import read_silver,read_target


def qualify(output:Path,rows:int=10000):
    if output.exists():raise FileExistsError('Use a new destination; prior evidence is preserved')
    output.mkdir(parents=True);output.chmod(0o700)
    work=output/'work';work.mkdir();evidence=output/'evidence';evidence.mkdir()
    contract=read_json(ROOT/'contracts/sales.json');profile=read_json(ROOT/'profiles/reference.json')
    start=time.perf_counter();baseline=work/'source-baseline'
    manifest=create_fixture(baseline,contract,rows)
    pipe=Pipeline(ROOT,work/'runtime',ROOT/'contracts/sales.json',ROOT/'profiles/reference.json')
    token_admin=secrets.token_urlsafe(32);token_site=secrets.token_urlsafe(32)
    access={'schema_version':'ilc-access/1','principals':[
        {'name':'all-sites-demo','token_sha256':hashlib.sha256(token_admin.encode()).hexdigest(),
         'sites':contract['sites'],'permissions':['report','catalog','evidence']},
        {'name':'site-a-demo','token_sha256':hashlib.sha256(token_site.encode()).hexdigest(),
         'sites':['SITE_A'],'permissions':['report']}]}
    policy=work/'access-policy.json';policy.write_bytes(canonical(access));policy.chmod(0o600)
    consumer=Journal(pipe.root,profile,read_only=True)
    headers_admin={'Authorization':'Bearer '+token_admin};headers_site={'Authorization':'Bearer '+token_site}
    def save(name,value):
        (evidence/name).write_bytes(canonical(value))
    checks={}
    try:
        with serving(baseline) as api:
            accepted=pipe.execute('baseline',manifest['as_of'],baseline,api)
            replay=pipe.execute('baseline',manifest['as_of'],baseline,api)
        assert accepted['status']=='ACCEPTED' and accepted['observed_captured_rows']==rows
        assert replay['batch_id']==accepted['batch_id'] and pipe.journal.state()['generation']==1
        checks['V-P01-01']={'status':'PASS_REFERENCE','same_batch':True,'generation_after_replay':1}
        save('baseline-receipt.json',accepted)
        with serve_report(create_app(consumer,contract,access)) as endpoint,httpx.Client(base_url=endpoint,timeout=15,trust_env=False) as report:
            first=report.get('/api/report',headers=headers_admin);first.raise_for_status();first=first.json()
            site=report.get('/api/report',headers=headers_site);site.raise_for_status();site=site.json()
            assert site['scope']==['SITE_A'] and all(x['site_id']=='SITE_A' for x in site['sites'])
            statuses={
                'unauthenticated':report.get('/api/report').status_code,
                'wrong_token':report.get('/api/report',headers={'Authorization':'Bearer invalid'}).status_code,
                'cross_site':report.get('/api/report?site=SITE_B',headers=headers_site).status_code,
                'global_evidence':report.get('/api/evidence',headers=headers_site).status_code,
                'global_catalog':report.get('/api/catalog',headers=headers_site).status_code,
                'other_site_order':report.get('/api/orders/O000001',headers=headers_site).status_code}
            assert statuses=={'unauthenticated':401,'wrong_token':401,'cross_site':403,'global_evidence':403,'global_catalog':403,'other_site_order':404}
            checks['V-P01-05']={'status':'PASS_REFERENCE_HTTP','outcomes':statuses,'scope':'Application RBAC only; not OS/cloud isolation'}
            save('report-initial.json',first);save('report-site-a.json',site)
            (evidence/'report-initial.html').write_text(render_snapshot(first),encoding='utf-8')
            for fault in ['duplicate_key','invalid_amount','schema_drift']:
                source=work/('source-'+fault);m=create_fixture(source,contract,rows,revision=1,fault=fault)
                with serving(source) as api:rejected=pipe.execute(fault,m['as_of'],source,api)
                assert rejected['status']=='REJECTED'
                current=report.get('/api/report',headers=headers_admin).json()
                assert current['dataset_batch_id']==first['dataset_batch_id'] and current['status']=='DEGRADED'
                assert current['totals']==first['totals']
                save('rejected-'+fault+'.json',rejected)
                save('report-after-'+fault+'.json',current)
            checks['V-P01-03']={'status':'PASS_REFERENCE','faults':['duplicate_key','invalid_amount','schema_drift'],'publication_blocked':True}
            checks['V-P01-06']={'status':'PASS_REFERENCE_HTTP','last_accepted_preserved':True,'degraded_exposed':True}
            (evidence/'report-degraded.html').write_text(render_snapshot(current),encoding='utf-8')
            source=work/'source-recovery';m=create_fixture(source,contract,rows,revision=1)
            before=pipe.journal.state()
            with serving(source) as api:
                cmd=[sys.executable,'-m','ilc.cli','--repo',str(ROOT),'run','--root',str(pipe.root),
                     '--fixture',str(source),'--api-url',api,'--key','hard-exit','--until',m['as_of'],
                     '--test-failpoint','after_target_commit','--test-crash']
                env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'ILC_ENABLE_TEST_FAILPOINTS':'1'}
                killed=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,timeout=60)
            assert killed.returncode==73
            row=pipe.journal.find('hard-exit');target=read_target(pipe.root,row['batch_id'])
            assert target is not None and pipe.journal.state()['accepted_batch']==before['accepted_batch']
            assert pipe.journal.state()['watermarks']==before['watermarks']
            # API is now stopped: successful resume proves no source recapture.
            recovered=pipe.execute('hard-exit',m['as_of'],source,'http://127.0.0.1:1')
            assert recovered['target_reused'] and recovered['target_manifest_sha256']==digest(target)
            assert recovered['generation']==2
            checks['V-P01-02']={'status':'PASS_REFERENCE_REAL_PROCESS_EXIT','child_exit':killed.returncode,
                'target_exists_before_accept':True,'watermark_unchanged_before_resume':True,
                'resume_with_source_offline':True,'candidate_reused':True,'accepted_generation':2}
            save('recovery-receipt.json',recovered);save('recovery-timeline.json',pipe.journal.timeline(row['batch_id']))
            final_report=report.get('/api/report',headers=headers_admin).json()
            assert final_report['dataset_batch_id']==recovered['batch_id']
            save('report-recovered.json',final_report)
            (evidence/'report-recovered.html').write_text(render_snapshot(final_report),encoding='utf-8')
            catalog=report.get('/api/catalog',headers=headers_admin).json();save('local-catalog.json',catalog)
            checks['V-P01-04']={'status':'PASS_REFERENCE','checks':recovered['source_to_target'],
                               'captured_rows':rows,'gold_fact_rows':recovered['gold_fact_rows'],
                               'bronze_bytes':recovered['observed_bronze_bytes']}
        # Sixth entity from metadata only, no copy of an ingestion implementation.
        code_before=code_manifest(ROOT);contract['version']='1.1.0'
        contract['entities']['warehouses']={'owner_role':'synthetic-data-owner','classification':'PUBLIC_SYNTHETIC',
            'primary_key':['warehouse_id'],'watermark':'updated_at','fields':[
                {'name':'warehouse_id','type':'string','nullable':False},
                {'name':'site_id','type':'string','nullable':False,'enum':contract['sites']},
                {'name':'updated_at','type':'timestamp_utc','nullable':False}]}
        profile['entity_sources']['warehouses']={'kind':'csv','location':'warehouses.csv','mode':'FULL'}
        c=work/'extended-contract.json';p=work/'extended-profile.json';c.write_bytes(canonical(contract));p.write_bytes(canonical(profile))
        records=make_records(contract,rows,revision=2)
        records['warehouses']=[{'warehouse_id':'WH-'+site,'site_id':site,'updated_at':'2026-11-12T12:00:00Z'} for site in contract['sites']]
        source=work/'source-extra';m=write_fixture(source,contract,records,as_of='2026-11-12T12:00:00Z')
        next_pipeline=Pipeline(ROOT,pipe.root,c,p)
        try:
            with serving(source) as api:extended=next_pipeline.execute('metadata-extension',m['as_of'],source,api)
            assert extended['status']=='ACCEPTED' and len(read_silver(pipe.root,extended['batch_id'])['warehouses'])==3
            assert code_manifest(ROOT)==code_before and extended['code_sha256']==accepted['code_sha256']
            save('metadata-extension-receipt.json',extended)
            with serve_report(create_app(consumer,contract,access)) as endpoint,httpx.Client(base_url=endpoint,timeout=15,trust_env=False) as report:
                extended_report=report.get('/api/report',headers=headers_admin);extended_report.raise_for_status()
                extended_catalog=report.get('/api/catalog',headers=headers_admin);extended_catalog.raise_for_status()
                extended_report=extended_report.json();extended_catalog=extended_catalog.json()
                assert extended_report['dataset_batch_id']==extended['batch_id'] and extended_report['generation']==3
                assert 'warehouses' in {table['name'] for table in extended_catalog['tables']}
                save('report-extended.json',extended_report);save('local-catalog-extended.json',extended_catalog)
                (evidence/'report-extended.html').write_text(render_snapshot(extended_report),encoding='utf-8')
        finally:next_pipeline.close()
        result={'project':'P01','qualified_profile':'reference_sqlite/reference_json','application_checks':checks,
            'metadata_extension':{'new_entity':'warehouses','new_rows':3,'engine_code_unchanged':True,'consumer_catalog_observed':True,'report_generation':3,'status':'PASS_REFERENCE'},
            'actual_captured_rows_per_clean_base_batch':rows,
            'sources_exercised':['SQLite read-only transaction','real loopback HTTP pagination','CSV file'],
            'consumer_exercised':'real loopback HTTP FastAPI reporting',
            'native_postgresql_spark_delta_dagster':'NOT_RUN','openmetadata':'NOT_RUN',
            'fabric':'NOT_RUN','power_bi':'NOT_RUN','big_data_scale':'NOT_RUN',
            'reference_wall_seconds':round(time.perf_counter()-start,6),'git':git_identity(ROOT),
            'source_code':code_manifest(ROOT),'runtime':accepted['runtime_versions'],
            'secrets_in_evidence':False,'cloud_mutations':0,'github_mutations':0,'personal_pc_access':False}
        save('qualification.json',result)
        return result
    finally:
        consumer.close()
        pipe.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--rows',type=int,default=10000)
    args=parser.parse_args();result=qualify(args.output,args.rows)
    print(json.dumps({k:v for k,v in result.items() if k!='source_code'},indent=2))

if __name__=='__main__':main()
