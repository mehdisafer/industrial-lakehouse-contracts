"""Real SQLite, disk artifacts and loopback HTTP; native platforms are separate."""
import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
from ilc.canonical import canonical, code_manifest, digest, read_json
from ilc.contracts import validate_contract
from ilc.errors import CaptureError, ConflictError, ContractError, InjectedFailure, IntegrityError, StaleBaseError
from ilc.fixtures import create_fixture, make_records, write_fixture
from ilc.pipeline import Pipeline
from ilc.reporting import NoAcceptedData, ReportReader
from ilc.source_api import serving
from ilc.storage import batch_path, read_silver, read_target


def settings(tmp_path, contract, profile):
    c=tmp_path/'contract.json';p=tmp_path/'profile.json'
    c.write_bytes(canonical(contract));p.write_bytes(canonical(profile))
    return c,p


def test_nominal_and_replay(pipeline,source):
    root,m,url=source
    result=pipeline.execute('one',m['as_of'],root,url)
    state=pipeline.journal.state()
    assert result['status']=='ACCEPTED' and result['observed_captured_rows']==1000
    assert result['gold_fact_rows']==380
    assert result['source_to_target']['source_amount']=='827125.38'
    assert result['source_to_target']['gold_amount']=='827125.38'
    assert result['provider_integration']==result['catalog_provider']=='NOT_RUN'
    replay=pipeline.execute('one',m['as_of'],root,'http://127.0.0.1:1')
    assert replay['batch_id']==result['batch_id'] and replay['invocation']=='REPLAY_OF_ACCEPTED_BATCH'
    assert pipeline.journal.state()==state
    assert pipeline.journal.get(result['batch_id'])['attempts']==1


@pytest.mark.parametrize('fault',['duplicate_key','invalid_amount','schema_drift','orphan','overshipment','incorrect_total'])
def test_bad_batch_preserves_last_accepted(pipeline,accepted,tmp_path,contract,fault):
    before=pipeline.journal.state();root=tmp_path/fault
    m=create_fixture(root,contract,rows=1000,revision=1,fault=fault)
    with serving(root) as url:result=pipeline.execute(fault,m['as_of'],root,url)
    after=pipeline.journal.state()
    assert result['status']=='REJECTED' and not result['dataset_promoted']
    assert after['accepted_batch']==before['accepted_batch']
    assert after['watermarks']==before['watermarks'] and after['generation']==1
    report=ReportReader(pipeline.journal).report(contract['sites'])
    assert report['status']=='DEGRADED' and report['dataset_batch_id']==accepted['batch_id']
    assert report['totals']['ordered_amount']=='827125.38'
    assert pipeline.execute(fault,m['as_of'],root,'http://127.0.0.1:1')['status']=='REJECTED'


def test_no_report_for_initial_rejection(pipeline,tmp_path,contract):
    root=tmp_path/'bad';m=create_fixture(root,contract,1000,fault='invalid_amount')
    with serving(root) as url:result=pipeline.execute('bad',m['as_of'],root,url)
    assert result['status']=='REJECTED'
    with pytest.raises(NoAcceptedData):ReportReader(pipeline.journal).report(contract['sites'])


@pytest.mark.parametrize('failpoint',['after_target_commit','before_accept'])
def test_resume_uses_frozen_capture_and_target(pipeline,source,failpoint,monkeypatch):
    root,m,url=source
    with pytest.raises(InjectedFailure):pipeline.execute('resume',m['as_of'],root,url,failpoint)
    row=pipeline.journal.find('resume');state=pipeline.journal.state()
    assert state['accepted_batch'] is None and not state['watermarks']
    target=read_target(pipeline.root,row['batch_id']);before=digest(target)
    def no_read(*a,**kw):raise AssertionError('A retry must not recapture its source')
    monkeypatch.setattr('ilc.pipeline.extract_all',no_read)
    accepted=pipeline.execute('resume',m['as_of'],root,url)
    assert accepted['target_reused'] and accepted['target_manifest_sha256']==before
    assert accepted['generation']==1
    assert pipeline.journal.find('resume')['attempts']==2


@pytest.mark.parametrize('failpoint',['after_target_commit','after_accept'])
def test_actual_process_exit_and_restart(repo,tmp_path,source,failpoint):
    root,m,url=source;runtime=tmp_path/'crash-runtime'
    command=[sys.executable,'-m','ilc.cli','--repo',str(repo),'run','--root',str(runtime),
             '--fixture',str(root),'--api-url',url,'--key','crash-batch','--until',m['as_of'],
             '--test-failpoint',failpoint,'--test-crash']
    env={**os.environ,'PYTHONPATH':str(repo/'src'),'ILC_ENABLE_TEST_FAILPOINTS':'1'}
    stopped=subprocess.run(command,env=env,cwd=repo,capture_output=True,timeout=30)
    assert stopped.returncode==73,stopped.stderr.decode()
    p=Pipeline(repo,runtime,repo/'contracts/sales.json',repo/'profiles/reference.json')
    try:
        first=p.journal.find('crash-batch');target=read_target(runtime,first['batch_id'])
        assert target is not None
        assert p.journal.state()['generation']==(1 if failpoint=='after_accept' else 0)
        resumed=p.execute('crash-batch',m['as_of'],root,'http://127.0.0.1:1')
        assert resumed['status']=='ACCEPTED' and p.journal.state()['generation']==1
        assert resumed['target_manifest_sha256']==digest(target)
        assert (batch_path(runtime,first['batch_id'])/'acceptance.json').is_file()
        assert len([e for e in p.journal.timeline(first['batch_id']) if e['event']=='PUBLICATION_AND_WATERMARK_COMMITTED'])==1
    finally:p.close()


def test_lost_response_does_not_relabel_accepted(pipeline,source):
    root,m,url=source
    with pytest.raises(InjectedFailure):pipeline.execute('lost',m['as_of'],root,url,'after_accept')
    assert pipeline.journal.state()['last_status']=='ACCEPTED'
    assert pipeline.execute('lost',m['as_of'],root,url)['invocation']=='REPLAY_OF_ACCEPTED_BATCH'


@pytest.mark.parametrize('target',['bronze','target'])
def test_corruption_blocks_retry(pipeline,source,target):
    root,m,url=source
    with pytest.raises(InjectedFailure):pipeline.execute('corrupt',m['as_of'],root,url,'after_target_commit')
    row=pipeline.journal.find('corrupt');base=batch_path(pipeline.root,row['batch_id'])
    path=base/('bronze/orders.json' if target=='bronze' else 'target/gold/site_kpi.json')
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(IntegrityError):pipeline.execute('corrupt',m['as_of'],root,url)
    assert pipeline.journal.state()['accepted_batch'] is None


def test_incomplete_capture_is_not_implicitly_retried(pipeline,source,monkeypatch):
    root,m,url=source
    def fail(*a,**kw):raise RuntimeError('injected capture failure')
    monkeypatch.setattr('ilc.pipeline.extract_all',fail)
    with pytest.raises(RuntimeError):pipeline.execute('uncertain',m['as_of'],root,url)
    with pytest.raises(CaptureError):pipeline.execute('uncertain',m['as_of'],root,url)
    assert not pipeline.journal.state()['watermarks']


def test_key_cannot_change_bounds(pipeline,source,accepted):
    root,m,url=source
    with pytest.raises(ConflictError):pipeline.execute('accepted-baseline','2026-11-12T11:00:00Z',root,url)


def test_key_cannot_change_contract(pipeline,source,accepted,repo,tmp_path,contract,profile):
    root,m,url=source;contract['owner_role']='changed-owner'
    c,f=settings(tmp_path,contract,profile);other=Pipeline(repo,pipeline.root,c,f)
    try:
        with pytest.raises(ConflictError):other.execute('accepted-baseline',m['as_of'],root,url)
    finally:other.close()


def test_stale_retry_cannot_roll_back_new_generation(pipeline,source):
    root,m,url=source
    with pytest.raises(InjectedFailure):pipeline.execute('old-attempt',m['as_of'],root,url,'after_target_commit')
    newer=pipeline.execute('new-attempt',m['as_of'],root,url)
    with pytest.raises(StaleBaseError):pipeline.execute('old-attempt',m['as_of'],root,url)
    assert pipeline.journal.state()['accepted_batch']==newer['batch_id']
    assert pipeline.journal.state()['generation']==1


def test_incremental_revision_replaces_without_duplicate(pipeline,accepted,contract,tmp_path):
    root=tmp_path/'revision';m=create_fixture(root,contract,1000,revision=1)
    with serving(root) as url:receipt=pipeline.execute('revision',m['as_of'],root,url)
    assert receipt['status']=='ACCEPTED' and receipt['gold_fact_rows']==380 and receipt['generation']==2
    assert receipt['source_to_target']['source_amount']!='827125.38'
    silver=read_silver(pipeline.root,receipt['batch_id'])
    assert len({(r['order_id'],r['line_id']) for r in silver['order_lines']})==380


def test_ties_with_different_payload_rejected(pipeline,accepted,contract,tmp_path):
    records=make_records(contract,1000)
    row=records['order_lines'][0];row['unit_price']='1.00';row['amount']=f"{int(row['quantity']):.2f}"
    root=tmp_path/'same-time';m=write_fixture(root,contract,records,as_of='2026-11-12T10:00:00Z')
    with serving(root) as url:receipt=pipeline.execute('changed',m['as_of'],root,url)
    assert receipt['status']=='REJECTED'
    assert receipt['details']['reconciliation']['order_lines']['merge_conflicts']==1
    assert pipeline.journal.state()['accepted_batch']==accepted['batch_id']


def test_add_entity_via_metadata_without_engine_change(repo,pipeline,accepted,tmp_path,contract,profile):
    before=code_manifest(repo);contract['version']='1.1.0'
    contract['entities']['warehouses']={'owner_role':'synthetic-data-owner','classification':'PUBLIC_SYNTHETIC',
        'primary_key':['warehouse_id'],'watermark':'updated_at','fields':[
            {'name':'warehouse_id','type':'string','nullable':False},
            {'name':'site_id','type':'string','nullable':False,'enum':contract['sites']},
            {'name':'updated_at','type':'timestamp_utc','nullable':False}]}
    profile['entity_sources']['warehouses']={'kind':'csv','location':'warehouses.csv','mode':'FULL'}
    records=make_records(contract,1000,revision=1)
    records['warehouses']=[{'warehouse_id':'WH-'+s,'site_id':s,'updated_at':'2026-11-12T11:00:00Z'} for s in contract['sites']]
    root=tmp_path/'extra';m=write_fixture(root,contract,records,as_of='2026-11-12T11:00:00Z')
    c,f=settings(tmp_path,contract,profile);p=Pipeline(repo,pipeline.root,c,f)
    try:
        with serving(root) as url:r=p.execute('extra-entity',m['as_of'],root,url)
        assert r['status']=='ACCEPTED' and r['observed_captured_rows']==1003
        assert len(read_silver(p.root,r['batch_id'])['warehouses'])==3
        assert code_manifest(repo)==before and r['code_sha256']==accepted['code_sha256']
    finally:p.close()


def test_changed_contract_needs_version_bump(repo,pipeline,accepted,source,tmp_path,contract,profile):
    contract['owner_role']='new-owner';c,f=settings(tmp_path,contract,profile)
    p=Pipeline(repo,pipeline.root,c,f);root,m,url=source
    try:
        with pytest.raises(ContractError):p.execute('new-contract',m['as_of'],root,url)
    finally:p.close()


def test_breaking_contract_requires_full_migration(repo,pipeline,accepted,source,tmp_path,contract,profile):
    contract['version']='2.0.0';contract['entities']['orders']['owner_role']='new-owner'
    field=contract['entities']['products']['fields'][1];field['nullable']=True
    c,f=settings(tmp_path,contract,profile);p=Pipeline(repo,pipeline.root,c,f);root,m,url=source
    try:
        with pytest.raises(ContractError):p.execute('breaking',m['as_of'],root,url)
    finally:p.close()


def test_gold_dimensions_cover_fact_keys(pipeline,accepted):
    root=batch_path(pipeline.root,accepted['batch_id'])/'target/gold'
    customers={r['customer_id'] for r in read_json(root/'dim_customer.json')}
    products={r['product_id'] for r in read_json(root/'dim_product.json')}
    sites={r['site_id'] for r in read_json(root/'dim_site.json')}
    for row in read_json(root/'fact_order_fulfillment.json'):
        assert row['customer_id'] in customers and row['product_id'] in products and row['site_id'] in sites
    assert (len(customers),len(products),len(sites))==(30,20,3)
