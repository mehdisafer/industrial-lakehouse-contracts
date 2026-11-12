import hashlib
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from ilc.canonical import digest,read_json
from ilc.report_api import create_app
from ilc.reporting import AccessPolicy,ReportReader
from ilc.storage import batch_path


def policy(sites):
    return {'schema_version':'ilc-access/1','principals':[
        {'name':'site-a-reader','token_sha256':hashlib.sha256(b'fixture-a').hexdigest(),'sites':['SITE_A'],'permissions':['report']},
        {'name':'admin','token_sha256':hashlib.sha256(b'fixture-admin').hexdigest(),'sites':sites,'permissions':['report','catalog','evidence']}]}


def headers(token):return {'Authorization':'Bearer '+token}


def test_site_filter_precedes_totals(pipeline,accepted,contract):
    with TestClient(create_app(pipeline.journal,contract,policy(contract['sites']))) as client:
        r=client.get('/api/report',headers=headers('fixture-a'));assert r.status_code==200
        v=r.json();assert v['scope']==['SITE_A'] and len(v['sites'])==1
        assert v['totals']['ordered_amount']=='272717.04'
        assert client.get('/api/report?site=SITE_B',headers=headers('fixture-a')).status_code==403
        assert client.get('/api/catalog',headers=headers('fixture-a')).status_code==403
        assert client.get('/api/evidence',headers=headers('fixture-a')).status_code==403
        assert client.get('/api/orders/O000001',headers=headers('fixture-a')).status_code==404
        assert client.get('/api/orders/O000000',headers=headers('fixture-a')).status_code==200
        admin=client.get('/api/report',headers=headers('fixture-admin')).json()
        assert admin['totals']['ordered_amount']=='827125.38'
        assert client.get('/api/catalog',headers=headers('fixture-admin')).json()['provider']=='LOCAL_FILE_CATALOG_NOT_OPENMETADATA'
        assert client.get('/api/evidence',headers=headers('fixture-admin')).json()['batch_id']==accepted['batch_id']


@pytest.mark.parametrize('path',['/api/report','/api/catalog','/api/evidence','/dashboard','/api/orders/O000000'])
def test_all_data_routes_require_authentication(pipeline,accepted,contract,path):
    with TestClient(create_app(pipeline.journal,contract,policy(contract['sites']))) as client:
        assert client.get(path).status_code==401
        assert client.get(path,headers=headers('wrong')).status_code==401
        assert client.get(path).headers['cache-control']=='no-store'
        assert '827125.38' not in client.get('/').text


def test_missing_generation_is_unavailable(pipeline,contract):
    with TestClient(create_app(pipeline.journal,contract,policy(contract['sites']))) as client:
        r=client.get('/api/report',headers=headers('fixture-a'))
        assert r.status_code==503 and r.json()['detail']=='NO_ACCEPTED_DATASET'


def test_modified_published_data_fail_closed(pipeline,accepted,contract):
    p=batch_path(pipeline.root,accepted['batch_id'])/'target/gold/site_kpi.json'
    p.write_bytes(p.read_bytes()+b' ')
    with TestClient(create_app(pipeline.journal,contract,policy(contract['sites']))) as client:
        for path in ['/api/report','/api/orders/O000000','/api/evidence','/api/catalog']:
            r=client.get(path,headers=headers('fixture-admin'))
            assert r.status_code==503


def test_report_freshness_is_independent_of_acceptance(pipeline,accepted,contract):
    reader=ReportReader(pipeline.journal)
    current=reader.report(contract['sites'],clock=datetime(2026,11,12,10,30,tzinfo=timezone.utc))
    stale=reader.report(contract['sites'],clock=datetime(2026,11,12,12,30,tzinfo=timezone.utc))
    assert current['status']=='CURRENT' and stale['status']=='STALE'
    assert current['dataset_batch_id']==stale['dataset_batch_id']


def test_duplicate_credentials_rejected(contract):
    p=policy(contract['sites']);p['principals'][1]['token_sha256']=p['principals'][0]['token_sha256']
    with pytest.raises(ValueError):AccessPolicy(p,contract['sites'])


def test_global_evidence_permission_cannot_bypass_site_scope(contract):
    p=policy(contract['sites']);p['principals'][0]['permissions'].append('evidence')
    with pytest.raises(ValueError):AccessPolicy(p,contract['sites'])


def test_future_source_is_not_reported_as_fresh(pipeline,accepted,contract):
    report=ReportReader(pipeline.journal).report(contract['sites'],clock=datetime(2026,11,12,9,30,tzinfo=timezone.utc))
    assert report['future_dated'] and report['status']=='FUTURE_DATED'


def test_report_consumer_database_is_read_only(pipeline,accepted,contract,profile):
    from ilc.journal import Journal
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    reader=Journal(pipeline.root,profile,read_only=True)
    try:
        assert ReportReader(reader).report(contract['sites'])['dataset_batch_id']==accepted['batch_id']
        with pytest.raises(DBAPIError):
            with reader.engine.begin() as db:db.execute(text('DELETE FROM ilc_registry'))
        with pytest.raises(PermissionError):
            with reader.lock():pass
    finally:reader.close()


def test_read_only_status_does_not_create_missing_runtime(tmp_path,profile):
    from ilc.journal import Journal
    from ilc.errors import IntegrityError
    root=tmp_path/'absent'
    with pytest.raises(IntegrityError):Journal(root,profile,read_only=True)
    assert not root.exists()
