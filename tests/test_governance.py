"""Contract and real-HTTP emulator tests; no OpenMetadata product is started."""
import copy
import json
from pathlib import Path

import httpx
import pytest
from ilc.governance import (build_export, validate_settings, Publisher, GovernanceError,
    RemoteOutcomeUnknown, column)
from ilc.errors import IntegrityError, ConflictError
from ilc.storage import batch_path
from support.openmetadata_emulator import CatalogEmulator


@pytest.fixture
def config(repo):return json.loads((repo/'governance/openmetadata.example.json').read_text())

@pytest.fixture
def export(pipeline,accepted,config):return build_export(pipeline.journal,config)


def publisher(config,tmp_path,server):
    return Publisher(config,'fixture-bearer-not-a-real-credential',tmp_path/'ledger',transport=httpx.MockTransport(server.handler))


def test_plan_only_never_contains_rows_or_external_secrets(export,accepted):
    assert len(export['tables'])==15 and len(export['edges'])==11
    assert export['source_profile']=='reference_sqlite'
    assert export['quality']['testCaseStatus']=='Success'
    assert export['quality']['timestamp']>1_000_000_000_000
    assert all(t['body']['description'].find(accepted['batch_id'])>=0 for t in export['tables'])
    assert 'sampleData' not in json.dumps(export)


def test_no_publication_plan_without_accepted_data(pipeline,config):
    with pytest.raises(GovernanceError):build_export(pipeline.journal,config)


def test_corrupt_target_prevents_export(pipeline,accepted,config):
    path=batch_path(pipeline.root,accepted['batch_id'])/'target/catalog/tables.json'
    path.write_text('[]')
    with pytest.raises(IntegrityError):build_export(pipeline.journal,config)


@pytest.mark.parametrize('url',['https://external.invalid/api','http://user:secret@localhost/api',
    'http://127.0.0.1/api?x=1','http://127.0.0.1/api#bad','ftp://localhost/api','http://localhost/not-api'])
def test_scope_validation(config,url):
    config['api_url']=url
    with pytest.raises(GovernanceError):validate_settings(config)


@pytest.mark.parametrize('field,value',[('service_name','production'),('database_prefix','prod'),
    ('server_version','9.0.0'),('classification_tag','PII.Sensitive')])
def test_namespace_and_version_are_explicit(config,field,value):
    config[field]=value
    with pytest.raises(GovernanceError):validate_settings(config)


def test_missing_owner_mapping_refuses_export(pipeline,accepted,config):
    config['owner_teams']={'not-a-real-owner-role':'ilc_data_owners'}
    with pytest.raises(GovernanceError):build_export(pipeline.journal,config)


def test_columns_preserve_contract_scale():
    assert column({'name':'amount','type':'decimal(12,4)','nullable':False})=={
        'name':'amount','dataType':'DECIMAL','precision':12,'scale':4,'constraint':'NOT_NULL'}


def test_write_requires_explicit_opt_in(config,export,tmp_path):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    try:
        with pytest.raises(GovernanceError):p.publish(export)
        assert not server.calls
    finally:p.close()


def test_delivery_replay_rechecks_remote_without_second_write(config,export,tmp_path):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    try:
        first=p.publish(export,allow_writes=True)
        writes=sum(m=='PUT' for m,_,_ in server.calls)
        again=p.publish(export,allow_writes=True)
        assert first==again and writes==sum(m=='PUT' for m,_,_ in server.calls)
        assert first['tables_read_back']==15 and first['lineage_edges_read_back']==11
        assert first['quality_results_read_back']==1
        assert 'fixture-bearer' not in ''.join(f.read_text() for f in (tmp_path/'ledger').glob('*.json'))
    finally:p.close()


def test_lost_response_recovers_original_remote_object_after_client_restart(config,export,tmp_path):
    server=CatalogEmulator();server.fail_after_write=True
    p=publisher(config,tmp_path,server)
    try:
        with pytest.raises(RemoteOutcomeUnknown):p.publish(export,allow_writes=True)
    finally:p.close()
    p=publisher(config,tmp_path,server)
    try:
        r=p.publish(export,allow_writes=True)
        assert r['status']=='REMOTE_METADATA_READ_BACK'
        dbputs=[c for c in server.calls if c[0]=='PUT' and c[1].endswith('/databases')]
        assert len(dbputs)==1
    finally:p.close()


def test_unknown_outcome_does_not_blindly_reissue(config,export,tmp_path):
    server=CatalogEmulator();server.fail_after_write=True;server.hide_after_write=True
    p=publisher(config,tmp_path,server)
    try:
        with pytest.raises(RemoteOutcomeUnknown):p.publish(export,allow_writes=True)
        before=sum(m=='PUT' for m,_,_ in server.calls)
        with pytest.raises(RemoteOutcomeUnknown):p.publish(export,allow_writes=True)
        assert sum(m=='PUT' for m,_,_ in server.calls)==before
    finally:p.close()


def test_preexisting_foreign_object_is_not_overwritten(config,export,tmp_path):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    server.entities['databases',export['database_fqn']]={'name':export['database'],'fullyQualifiedName':export['database_fqn'],
        'description':'Owned by someone else','id':server.team_id}
    try:
        with pytest.raises(ConflictError):p.publish(export,allow_writes=True)
        assert all(method=='GET' for method,_,_ in server.calls)
    finally:p.close()


@pytest.mark.parametrize('mutation',['owner','columns','tag','deleted'])
def test_readback_drift_fails_replay(config,export,tmp_path,mutation):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    try:
        p.publish(export,allow_writes=True)
        table=server.entities['tables',export['tables'][0]['fqn']]
        if mutation=='owner':table['owners']=[]
        if mutation=='columns':table['columns'][0]['dataType']='BOOLEAN'
        if mutation=='tag':table['tags']=[]
        if mutation=='deleted':table['deleted']=True
        before=sum(m=='PUT' for m,_,_ in server.calls)
        with pytest.raises(ConflictError):p.publish(export,allow_writes=True)
        assert sum(m=='PUT' for m,_,_ in server.calls)==before
    finally:p.close()


@pytest.mark.parametrize('mode',['version','redirect','denied'])
def test_preflight_errors_do_not_mutate_or_expose_body(config,export,tmp_path,mode):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    if mode=='version':server.version='0.0.0'
    if mode=='redirect':server.redirect=True
    if mode=='denied':server.denied=True
    try:
        with pytest.raises(GovernanceError) as err:p.publish(export,allow_writes=True)
        assert 'DO-NOT-PERSIST' not in str(err.value) and 'fixture-bearer' not in str(err.value)
        assert all(m=='GET' for m,_,_ in server.calls)
    finally:p.close()


def test_out_of_namespace_plan_rejected_before_network(config,export,tmp_path):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    export['tables'][0]['body']['databaseSchema']='production.secret'
    try:
        with pytest.raises(GovernanceError):p.publish(export,allow_writes=True)
        assert server.calls==[]
    finally:p.close()


def test_real_loopback_transport_against_protocol_emulator(pipeline,accepted,config,tmp_path):
    server=CatalogEmulator()
    with server.serving() as url:
        config['api_url']=url;export=build_export(pipeline.journal,config)
        p=Publisher(config,'synthetic-loopback-token',tmp_path/'http-ledger')
        try:
            r=p.publish(export,allow_writes=True)
            assert r['operations_verified']==33
        finally:p.close()
    assert len(server.entities)==21


def test_result_route_matches_pinned_112_post_contract(config,export,tmp_path):
    server=CatalogEmulator();p=publisher(config,tmp_path,server)
    try:
        p.publish(export,allow_writes=True)
        posts=[(m,u,b) for m,u,b in server.calls if m=='POST']
        assert len(posts)==1 and '/testCases/testCaseResults/' in posts[0][1]
        assert set(json.loads(posts[0][2]))=={'timestamp','testCaseStatus','result','testResultValue'}
        case_gets=[u for m,u,_ in server.calls if m=='GET' and '/testCases/name/' in u]
        assert case_gets and all('fields=testDefinition' in u for u in case_gets)
    finally:p.close()


def test_non_object_remote_json_is_rejected(config,tmp_path):
    p=Publisher(config,'test-only-token',tmp_path/'ledger',transport=httpx.MockTransport(
        lambda req:httpx.Response(200,json=['wrong-shape'])))
    try:
        with pytest.raises(GovernanceError,match='object'):p.request('GET','v1/system/version')
    finally:p.close()


def test_export_never_mixes_generations(pipeline,accepted,config,monkeypatch):
    from ilc.reporting import ReportReader
    original=ReportReader.report
    def changed(reader,*args,**kwargs):
        result=original(reader,*args,**kwargs);result['generation']+=1;return result
    monkeypatch.setattr(ReportReader,'report',changed)
    with pytest.raises(ConflictError,match='generation'):build_export(pipeline.journal,config)
