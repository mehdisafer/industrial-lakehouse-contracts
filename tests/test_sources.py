import copy
import csv
import json
from pathlib import Path
import httpx
import pytest
from ilc.sources import extract_all,read_rest,read_csv,loopback_url,validate_pg_dsn
from ilc.canonical import read_json,canonical
from ilc.errors import SourceError,ContractError


def test_real_http_database_csv_capture(source,contract,profile):
    root,manifest,url=source
    records,receipts,_=extract_all(root,contract,profile,url)
    assert sum(map(len,records.values()))==1000
    assert receipts['shipments']['pages']>1
    assert receipts['orders']['source_backend']=='sqlite'
    assert receipts['products']['connector']=='csv'

@pytest.mark.parametrize('url',['https://example.org','http://127.0.0.1@evil.invalid','file:///tmp/source','http://localhost/path','http://user:pass@127.0.0.1','http://127.0.0.1?x=y'])
def test_network_scope(url):
    with pytest.raises(SourceError):loopback_url(url)

@pytest.mark.parametrize('url',['postgresql://u:p@example.org/prod','sqlite:///x','postgresql:///prod','not-a-url'])
def test_database_scope(url):
    with pytest.raises(SourceError):validate_pg_dsn(url)

@pytest.mark.parametrize('fault',['snapshot','cursor_cycle','total_changed','partial','page_overflow','redirect'])
def test_pagination_faults_fail_closed(profile,fault):
    rows=[{'value':str(i)} for i in range(3)]
    manifest={'snapshot_id':'a'*64,'as_of':'2026-11-12T10:00:00Z','entities':{'shipments':{'count':3,'fields':['value']}}}
    profile['page_size']=2
    def handler(request):
        cursor=request.url.params['cursor'];offset=int(cursor)
        data=rows[offset:offset+2]
        page={'snapshot_id':manifest['snapshot_id'],'entity':'shipments','total_rows':3,'fields':['value'],
              'as_of':manifest['as_of'],'rows':data,'cursor':cursor,'next_cursor':'2' if offset==0 else None}
        if fault=='snapshot':page['snapshot_id']='b'*64
        if fault=='cursor_cycle':page['next_cursor']='0'
        if fault=='total_changed':page['total_rows']=4
        if fault=='partial':page['next_cursor']=None
        if fault=='page_overflow':page['rows']=rows
        if fault=='redirect':return httpx.Response(302,headers={'Location':'https://external.invalid'})
        return httpx.Response(200,json=page)
    with httpx.Client(base_url='http://127.0.0.1',transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError):read_rest(client,manifest,'shipments',profile)


def test_valid_pagination_contract(profile):
    manifest={'snapshot_id':'a'*64,'as_of':'2026-11-12T10:00:00Z','entities':{'shipments':{'count':0,'fields':['value']}}}
    def handler(req):return httpx.Response(200,json={'snapshot_id':'a'*64,'entity':'shipments','cursor':'0','total_rows':0,'fields':['value'],'as_of':manifest['as_of'],'rows':[],'next_cursor':None})
    with httpx.Client(base_url='http://127.0.0.1',transport=httpx.MockTransport(handler)) as client:
        rows,pages=read_rest(client,manifest,'shipments',profile)
    assert rows==[] and pages==1


def test_database_budget_is_enforced(source,contract,profile):
    root,manifest,url=source;profile['max_rows_per_entity']=5
    with pytest.raises(SourceError):extract_all(root,contract,profile,url)


def test_source_drift_against_manifest_is_not_silent(source,contract,profile):
    root,manifest,url=source
    with (root/'products.csv').open('a') as f:f.write('x,x,x,2026-11-12T10:00:00Z\n')
    with pytest.raises(SourceError):extract_all(root,contract,profile,url)

@pytest.mark.parametrize('body',['a,a\n1,2\n','a,b\n1,2,3\n'])
def test_bad_csv_headers_and_width(tmp_path,body):
    p=tmp_path/'source.csv';p.write_text(body)
    with pytest.raises(SourceError):read_csv(tmp_path,'source.csv',10)
