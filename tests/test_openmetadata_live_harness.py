"""Offline checks of live harness safeguards; not a real OpenMetadata run."""
import copy
import gzip
import importlib.util
import io
from pathlib import Path

import httpx
import pytest

ROOT=Path(__file__).parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

live=load('qualify_openmetadata')
redactor=load('redact_catalog_logs')


def good_result():
    return {'schema_version':'ilc-openmetadata-live/1','server_version':'1.12.0','status':'EXECUTED_LIVE_CATALOGUE_CHECKS',
      'source_profile':'reference_sqlite','git':{'worktree_dirty':False},
      'checks':{
        'G3-01':{'status':'PASS_LIVE'},
        'G3-02':{'status':'PASS_LIVE','tables_per_generation':15,'lineage_edges_per_generation':11},
        'G3-03':{'status':'PASS_LIVE','replay_mutations':0},
        'G3-04':{'status':'PASS_LIVE','database_put_count':1},
        'G3-05':{'status':'PASS_LIVE','http_statuses':{'unauthenticated':401,'reader_write':403,'writer_policy_write':403}},
        'G3-06':{'status':'PASS_LIVE','conflict_mutations':0,'baseline_unchanged':True}}}


@pytest.mark.parametrize('endpoint',['http://localhost:8585/api','http://example.com/api',
 'https://127.0.0.1:8585/api','http://127.0.0.1:8585/api?target=x','http://secret@127.0.0.1:8585/api'])
def test_live_endpoint_is_not_user_redirectable(endpoint):
    with pytest.raises(ValueError):live.validate_endpoint(endpoint)


def test_valid_fixture_result_only():live.require_live_result(good_result())

@pytest.mark.parametrize('mutation',[
 lambda x:x.update(server_version='1.12.6'),
 lambda x:x.update(status='NOT_RUN'),
 lambda x:x.update(source_profile='unknown'),
 lambda x:x['git'].update(worktree_dirty=True),
 lambda x:x['checks'].pop('G3-06'),
 lambda x:x['checks']['G3-01'].update(status='NOT_RUN'),
 lambda x:x['checks']['G3-02'].update(tables_per_generation=1),
 lambda x:x['checks']['G3-03'].update(replay_mutations=1),
 lambda x:x['checks']['G3-04'].update(database_put_count=2),
 lambda x:x['checks']['G3-05']['http_statuses'].update(reader_write=200),
 lambda x:x['checks']['G3-06'].update(baseline_unchanged=False),
])
def test_result_gate_refuses_incomplete_or_conflicting_evidence(mutation):
    data=good_result();mutation(data)
    with pytest.raises(ValueError):live.require_live_result(data)


def test_loss_is_injected_only_after_upstream_write_success():
    calls=[];trace=[]
    def actual(request):
        calls.append(request.method)
        return httpx.Response(201,json={'id':'test'})
    transport=live.TraceTransport(trace,drop_database_response=True,inner=httpx.MockTransport(actual))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.ReadError):client.put(live.API+'/v1/databases',json={'name':'ilc_fixture'})
        assert client.get(live.API+'/v1/databases/name/ilc_fixture').status_code==201
    assert calls==['PUT','GET']
    assert trace[0]['response_loss_injected_after_server_success'] is True
    assert 'Authorization' not in str(trace)


def test_failed_write_does_not_become_injected_success():
    trace=[]
    transport=live.TraceTransport(trace,drop_database_response=True,inner=httpx.MockTransport(lambda r:httpx.Response(403)))
    with httpx.Client(transport=transport) as client:assert client.put(live.API+'/v1/databases').status_code==403
    assert 'response_loss_injected_after_server_success' not in trace[0]


def test_transport_refuses_external_host_before_call():
    called=[]
    transport=live.TraceTransport([],inner=httpx.MockTransport(lambda r:called.append(r)))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError):client.get('https://external.invalid/api/v1/tables')
    assert called==[]


def test_api_error_never_echoes_payload_or_response_secret():
    client=live.APIClient('DO-NOT-EXPORT',transport=httpx.MockTransport(lambda r:httpx.Response(403,text='SECRET-BODY')))
    try:
        with pytest.raises(ValueError) as error:client.request('POST','v1/policies',{'secret':'PRIVATE-PAYLOAD'})
        assert all(s not in str(error.value) for s in ['DO-NOT-EXPORT','SECRET-BODY','PRIVATE-PAYLOAD'])
        assert 'HTTP 403' in str(error.value)
    finally:client.close()


def test_existing_bootstrap_entity_is_not_updated():
    calls=[]
    def response(r):calls.append(r.method);return httpx.Response(200,json={'id':'existing'})
    client=live.APIClient('token',transport=httpx.MockTransport(response))
    try:
        with pytest.raises(ValueError):client.create('policies',{'name':'ilc_existing'})
    finally:client.close()
    assert calls==['GET']


def test_writer_not_admin_and_reader_explicitly_denies_writes():
    policies=live.policy_bodies()
    writer=policies['writer']['rules'];reader=policies['reader']['rules']
    allowed=[r for r in writer if r['effect']=='allow' and 'Create' in r['operations']]
    assert len(allowed)==1 and set(allowed[0]['resources'])==set(live.DATA_RESOURCES)
    assert not set(live.DATA_RESOURCES)&set(live.ADMIN_RESOURCES)
    deny=[r for r in reader if r['effect']=='deny']
    assert deny[0]['resources']==['All'] and set(deny[0]['operations'])=={'Create','EditAll','Delete'}


def test_missing_ci_opt_in_never_creates_runtime(tmp_path,monkeypatch):
    monkeypatch.delenv('ILC_ALLOW_OPENMETADATA_DEMO',raising=False)
    with pytest.raises(ValueError):live.qualify(tmp_path/'no-runtime')
    assert not (tmp_path/'no-runtime').exists()


def test_secrets_are_redacted_before_logs_leave_runtime(monkeypatch):
    monkeypatch.setenv('ILC_OM_DB_PASSWORD','secret-db')
    monkeypatch.setenv('ILC_OM_FERNET_KEY','secret-fernet')
    message='secret-db secret-fernet Authorization: Bearer abc.def password=secret accessToken=abc eyJabcdefghijk.abcdefghijkl.abcdefghijk'
    value=redactor.redact(message)
    assert all(s not in value for s in ['secret-db','secret-fernet','abc.def','password=secret','accessToken=abc','eyJabcdefghijk'])


def test_log_budget_consumes_input_without_broken_pipe(monkeypatch):
    stream=io.StringIO('first\n'+'x'*100+'\nlast\n');out=io.StringIO()
    monkeypatch.setattr(redactor,'MAX_BYTES',12)
    monkeypatch.setattr(redactor.sys,'stdin',stream);monkeypatch.setattr(redactor.sys,'stdout',out)
    redactor.main()
    assert stream.read()=='' and '[DIAGNOSTIC OUTPUT TRUNCATED]' in out.getvalue()


def test_compressed_product_response_is_decoded_exactly_once():
    trace=[]
    def upstream(request):
        data=gzip.compress(b'{"id":"synthetic-catalogue-object"}')
        return httpx.Response(200,headers={'content-encoding':'gzip','content-length':str(len(data))},
                              stream=httpx.ByteStream(data))
    transport=live.TraceTransport(trace,inner=httpx.MockTransport(upstream))
    with httpx.Client(transport=transport) as client:
        result=client.get(live.API+'/v1/tables/name/synthetic')
        assert result.json()=={'id':'synthetic-catalogue-object'}
        assert 'content-encoding' not in result.headers
        assert int(result.headers['content-length'])==len(result.content)
    assert trace==[{'method':'GET','path':'/api/v1/tables/name/synthetic','status':200}]


def test_oversized_decoded_response_is_rejected_before_export():
    data=gzip.compress(b'x'*2_000_001)
    transport=live.TraceTransport([],inner=httpx.MockTransport(lambda request:
        httpx.Response(200,headers={'content-encoding':'gzip'},stream=httpx.ByteStream(data))))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError,match='budget'):
            client.get(live.API+'/v1/tables/name/synthetic')


def test_basic_suite_is_bound_to_exact_table():
    live.verify_basic_suite({'basic':True,'basicEntityReference':{'id':'table-1','type':'table'}},'table-1')


@pytest.mark.parametrize('suite',[
    {'executable':True},
    {'basic':False,'basicEntityReference':{'id':'table-1','type':'table'}},
    {'basic':True,'basicEntityReference':{'id':'other','type':'table'}},
    {'basic':True,'basicEntityReference':{'id':'table-1','type':'database'}},
])
def test_deprecated_or_wrongly_bound_suite_is_rejected(suite):
    with pytest.raises(ValueError):live.verify_basic_suite(suite,'table-1')
