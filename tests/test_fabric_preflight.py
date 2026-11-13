"""HTTP contract tests only: no live Fabric tenant is accessed."""
import importlib.util
from pathlib import Path
import httpx
import pytest

spec=importlib.util.spec_from_file_location('fabric_preflight',Path(__file__).parents[1]/'fabric/preflight.py')
preflight=importlib.util.module_from_spec(spec);spec.loader.exec_module(preflight)
WORKSPACE='11111111-1111-4111-8111-111111111111'
ITEM='22222222-2222-4222-8222-222222222222'
BASE='https://api.fabric.microsoft.com/v1/workspaces/'+WORKSPACE+'/items'


def test_read_only_inventory_does_not_claim_integration():
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.method=='GET' and req.headers['Authorization']=='Bearer unit-test-not-a-secret'
        if len(calls)==1:return httpx.Response(200,json={'value':[{'id':ITEM,'type':'Lakehouse'}],'continuationUri':BASE+'?continuationToken=2'})
        return httpx.Response(200,json={'value':[]})
    r=preflight.inspect_workspace(WORKSPACE,'unit-test-not-a-secret',transport=httpx.MockTransport(handler))
    assert r['pages']==2 and r['mutations']==0
    assert r['integration_qualified'] is False and r['power_bi_report_tested'] is False


@pytest.mark.parametrize('target',['https://evil.example/items',BASE.replace('https:','http:'),BASE.replace(WORKSPACE,ITEM),BASE+'#x'])
def test_bearer_never_forwarded_to_unapproved_continuation(target):
    calls=[]
    def handler(req):
        calls.append(req);return httpx.Response(200,json={'value':[],'continuationUri':target})
    with pytest.raises(ValueError):preflight.inspect_workspace(WORKSPACE,'unit-test',transport=httpx.MockTransport(handler))
    assert len(calls)==1


def test_pagination_cycle_fails():
    handler=lambda req:httpx.Response(200,json={'value':[],'continuationUri':BASE})
    with pytest.raises(ValueError,match='cycle'):preflight.inspect_workspace(WORKSPACE,'unit-test',transport=httpx.MockTransport(handler))


def test_error_does_not_echo_response_or_token():
    handler=lambda req:httpx.Response(403,text='sensitive-server-response')
    with pytest.raises(RuntimeError) as err:preflight.inspect_workspace(WORKSPACE,'unit-test-secret',transport=httpx.MockTransport(handler))
    assert str(err.value)=='Fabric inventory returned HTTP 403'
