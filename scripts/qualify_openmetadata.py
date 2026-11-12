"""Exercise the real OpenMetadata 1.12.0 product in a disposable CI namespace.

The input is a newly accepted reference-profile generation. This isolates the
catalogue contract from Spark's separately accepted native G2 gate. No emulator
or SDK is used by this command. Tokens/passwords never enter exported evidence.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import secrets
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import httpx
from ilc.canonical import canonical, code_manifest, digest, immutable_write, read_json
from ilc.errors import ConflictError
from ilc.fixtures import create_fixture
from ilc.governance import API_VERSION, Publisher, RemoteOutcomeUnknown, build_export, _subset
from ilc.pipeline import Pipeline, git_identity
from ilc.source_api import serving

API = 'http://127.0.0.1:8585/api'
MUTATIONS = {'POST', 'PUT', 'PATCH', 'DELETE'}
DATA_RESOURCES = ['database', 'databaseSchema', 'table', 'testDefinition', 'testSuite', 'testCase']
ADMIN_RESOURCES = ['policy', 'role', 'user', 'team', 'tag', 'classification', 'databaseService']


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_endpoint(url: str) -> str:
    require(url == API, 'Only the dedicated CI loopback OpenMetadata endpoint is admitted')
    return url


def policy_bodies() -> dict:
    def rule(name, resources, operations, effect):
        return {'name': name, 'resources': resources, 'operations': operations, 'effect': effect}
    return {
        'writer': {'name': 'ilc_g3_writer_policy', 'description': 'Disposable P01 metadata writer; no governance administration.',
                   'rules': [rule('metadata_read', ['All'], ['ViewAll'], 'allow'),
                             rule('data_write', DATA_RESOURCES, ['Create', 'EditAll'], 'allow'),
                             rule('no_admin_write', ADMIN_RESOURCES, ['Create', 'EditAll', 'Delete'], 'deny'),
                             rule('no_delete', ['All'], ['Delete'], 'deny')]},
        'reader': {'name': 'ilc_g3_reader_policy', 'description': 'Disposable P01 read-only metadata consumer.',
                   'rules': [rule('metadata_read', ['All'], ['ViewAll'], 'allow'),
                             rule('no_write', ['All'], ['Create', 'EditAll', 'Delete'], 'deny')]},
    }


class TraceTransport(httpx.BaseTransport):
    """Forward real HTTP; optional single response loss AFTER a successful write.

    Only method/path/status are recorded. Response loss is explicitly a client-
    transport fault injection, not a claim of an actual network outage.
    """
    def __init__(self, trace: list, *, drop_database_response: bool = False, inner=None):
        self.trace = trace
        self.drop = drop_database_response
        self.inner = inner if inner is not None else httpx.HTTPTransport(retries=0)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        require(url.scheme == 'http' and url.host == '127.0.0.1' and url.port == 8585
                and url.path.startswith('/api/'), 'HTTP transport escaped the CI catalogue')
        response = self.inner.handle_request(request)
        try:
            # Decode once and enforce the budget while consuming the body.
            # Re-wrapping decoded bytes with the upstream Content-Encoding
            # would make the outer httpx client attempt a second decompression.
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                require(len(body) <= 2_000_000, 'Catalogue response exceeds evidence budget')
            raw = bytes(body)
            status, headers = response.status_code, response.headers.copy()
            for name in ('content-encoding', 'content-length', 'transfer-encoding'):
                headers.pop(name, None)
        finally:
            response.close()
        event = {'method': request.method, 'path': url.path, 'status': status}
        self.trace.append(event)
        if (self.drop and request.method == 'PUT' and url.path == '/api/v1/databases'
                and status in (200, 201)):
            self.drop = False
            event['response_loss_injected_after_server_success'] = True
            raise httpx.ReadError('Deliberate response loss after real catalogue write', request=request)
        return httpx.Response(status, headers=headers, content=raw, request=request)

    def close(self):
        self.inner.close()


class APIClient:
    def __init__(self, token: str | None = None, *, transport=None):
        self.http = httpx.Client(base_url=API+'/', trust_env=False, follow_redirects=False,
                                 timeout=20, transport=transport)
        if token:
            self.http.headers['Authorization'] = 'Bearer '+token

    def close(self): self.http.close()

    def request(self, method: str, path: str, body=None, *, params=None, expected=(200, 201), patch=False):
        require(path.startswith('v1/') and '..' not in path and '://' not in path, 'Unexpected API path')
        headers = {'Content-Type': 'application/json-patch+json'} if patch else None
        try:
            response = self.http.request(method, path, json=body, params=params, headers=headers)
        except httpx.HTTPError:
            raise RuntimeError('Catalogue transport failed: '+method+' '+path) from None
        # Never echo response bodies or auth request payloads in failure messages.
        require(response.status_code in expected, f'{method} {path}: HTTP {response.status_code}; expected {expected}')
        require(len(response.content) <= 2_000_000, 'Response exceeds budget')
        if response.status_code in (401, 403, 404) or not response.content:
            return {'http_status': response.status_code}
        return response.json()

    def get_name(self, collection, name, fields=None):
        return self.request('GET', 'v1/'+collection+'/name/'+quote(name,safe=''),
                            params={'fields':fields} if fields else None)

    def create(self, collection, body):
        name=body['name']
        absent=self.request('GET','v1/'+collection+'/name/'+quote(name,safe=''),expected=(404,))
        require(absent['http_status']==404, 'Refusing an existing bootstrap entity')
        value=self.request('POST','v1/'+collection,body)
        require(value.get('id') and value.get('name')==name, 'Unexpected created identity')
        return value


def login(email: str, password: str) -> str:
    client=APIClient()
    try:
        response=client.request('POST','v1/users/login',{
            'email':email,'password':base64.b64encode(password.encode()).decode()})
        token=response.get('accessToken')
        require(isinstance(token,str) and len(token)>20, 'No session token returned')
        return token
    finally:client.close()


def bootstrap(admin: APIClient, settings: dict) -> tuple[dict, dict]:
    """Create only fresh synthetic entities; never modify a pre-existing role."""
    service=admin.create('services/databaseServices',{'name':settings['service_name'],
        'serviceType':'CustomDatabase','description':'PUBLIC_SYNTHETIC P01 catalogue qualification; metadata only.'})
    teams={}
    for name in sorted(set(settings['owner_teams'].values())):
        teams[name]=admin.create('teams',{'name':name,'teamType':'Group','description':'Synthetic P01 data ownership'})
    classification=admin.create('classifications',{'name':'ILCSynthetic',
        'description':'Synthetic demonstration metadata only','mutuallyExclusive':False})
    # Tag GET is by FQN, unlike its create body name.
    admin.request('GET','v1/tags/name/ILCSynthetic.PUBLIC_SYNTHETIC',expected=(404,))
    tag=admin.request('POST','v1/tags',{'name':'PUBLIC_SYNTHETIC','classification':'ILCSynthetic',
        'description':'No customer data, credentials or real personal records'})
    require(tag.get('fullyQualifiedName')==settings['classification_tag'], 'Wrong classification tag')
    tokens={}; users={}; roles={}; policies={}
    for kind, body in policy_bodies().items():
        policy=admin.create('policies',body);policies[kind]=policy
        role=admin.create('roles',{'name':'ilc_g3_'+kind+'_role',
            'description':'Temporary P01 '+kind,'policies':[policy['name']]});roles[kind]=role
        name='ilc_g3_'+kind; email=name+'@open-metadata.org'
        password='Ilc!9'+secrets.token_hex(16)
        user=admin.create('users',{'name':name,'email':email,'isAdmin':False,'isBot':False,
            'roles':[role['id']],'createPasswordType':'ADMIN_CREATE','password':password,'confirmPassword':password})
        require(user.get('isAdmin') is False, 'Publisher/reader must not be administrator')
        tokens[kind]=login(email,password)
        verification=admin.get_name('users',name,'roles,teams')
        require(role['id'] in {r['id'] for r in verification.get('roles',[])}, 'Role not assigned')
        users[kind]={'id':user['id'],'name':name,'isAdmin':False,'role_id':role['id']}
    # Secret session values remain solely in memory. No full user object is exported.
    return tokens, {'service_id':service['id'],'teams':{n:v['id'] for n,v in teams.items()},
        'classification_id':classification['id'],'tag_id':tag['id'],'users':users,
        'policies':policy_bodies(), 'namespace_scope':'Dedicated disposable server; role resource types, not multi-tenant namespace isolation'}


def write_count(trace):
    return sum(e['method'] in MUTATIONS for e in trace)


def verify_basic_suite(suite: dict, table_id: str) -> None:
    # The pinned 1.12 schema marks executable as deprecated since 1.6.2.
    # Require the actual basic suite and its parent-table identity instead.
    require(suite.get('basic') is True, 'Test suite is not a basic entity-linked suite')
    parent = suite.get('basicEntityReference') or {}
    require(parent.get('id') == table_id and parent.get('type') == 'table',
            'Basic test suite is linked to a different table')


def snapshot(client: APIClient, plan: dict) -> dict:
    """Independently re-read metadata, owners, tags, lineage, DQ and test-suite."""
    tables={}
    for expected in plan['tables']:
        t=client.get_name('tables',expected['fqn'],'owners,tags')
        require(t.get('fullyQualifiedName')==expected['fqn'] and not t.get('deleted',False), 'Missing table')
        require(_subset(expected['body']['columns'],t['columns']), 'Column contract mismatch')
        owners=t.get('owners',[])
        require(len(owners)==1 and owners[0].get('name')==plan['settings']['owner_teams'][expected['owner_role']],
                'Owner mismatch')
        require(plan['settings']['classification_tag'] in {x['tagFQN'] for x in t.get('tags',[])}, 'Tag missing')
        tables[expected['fqn']]={'id':t['id'],'fullyQualifiedName':t['fullyQualifiedName'],
             'version':t['version'],'columns':t['columns'],'owners':owners,'tags':t['tags'],'description':t['description']}
    edges=[]
    for left,right in plan['edges']:
        graph=client.request('GET','v1/lineage/table/'+tables[left]['id'],params={'upstreamDepth':0,'downstreamDepth':1})
        matches=[e for e in graph.get('downstreamEdges',[]) if e.get('fromEntity')==tables[left]['id']
                 and e.get('toEntity')==tables[right]['id']]
        require(len(matches)==1,'Missing or duplicate lineage relation')
        edges.append({'from_fqn':left,'to_fqn':right,'from_id':tables[left]['id'],'to_id':tables[right]['id']})
    fact=plan['database_fqn']+'.gold.fact_order_fulfillment'
    case=client.get_name('dataQuality/testCases',fact+'.ilc_accepted_reconciliation','testDefinition,testSuite')
    require(case.get('testSuite',{}).get('id'), 'No executable suite attached to test case')
    suite=client.request('GET','v1/dataQuality/testSuites/'+case['testSuite']['id'])
    verify_basic_suite(suite, tables[fact]['id'])
    result=client.request('GET','v1/dataQuality/testCases/testCaseResults/'+quote(case['fullyQualifiedName'],safe=''),
        params={'startTs':plan['quality']['timestamp'],'endTs':plan['quality']['timestamp']})
    found=[r for r in result.get('data',[]) if r.get('timestamp')==plan['quality']['timestamp']]
    require(len(found)==1 and _subset(plan['quality'],found[0]), 'Quality result differs')
    return {'database_fqn':plan['database_fqn'],'tables':tables,'edges':edges,
       'test_case':case,'test_suite':suite,'quality_result':found[0]}


def require_live_result(result: dict) -> None:
    require(result.get('schema_version')=='ilc-openmetadata-live/1','Invalid catalogue qualification schema')
    require(result.get('status')=='EXECUTED_LIVE_CATALOGUE_CHECKS','Catalogue execution not completed')
    require(result.get('server_version')==API_VERSION,'Wrong OpenMetadata version')
    require(result.get('source_profile')=='reference_sqlite','Input qualification profile not explicit')
    checks=result.get('checks',{})
    expected={'G3-01','G3-02','G3-03','G3-04','G3-05','G3-06'}
    require(set(checks)==expected and all(x.get('status')=='PASS_LIVE' for x in checks.values()),'Incomplete real-server scenarios')
    require(checks['G3-02'].get('tables_per_generation')==15 and checks['G3-02'].get('lineage_edges_per_generation')==11,'Unexpected catalogue topology')
    require(checks['G3-03'].get('replay_mutations')==0,'Replay wrote again')
    require(checks['G3-04'].get('database_put_count')==1,'Lost-response recovery repeated database write')
    require(checks['G3-05'].get('http_statuses')=={'unauthenticated':401,'reader_write':403,'writer_policy_write':403},'Native authorization not proven')
    require(checks['G3-06'].get('conflict_mutations')==0 and checks['G3-06'].get('baseline_unchanged') is True,'Conflict/baseline not preserved')
    require(result.get('git',{}).get('worktree_dirty') is False,'Dirty executed worktree')


def qualify(output: Path) -> dict:
    require(os.environ.get('ILC_ALLOW_OPENMETADATA_DEMO')=='1','Explicit isolated-catalogue authorization required')
    expected_sha=os.environ.get('CIRCLE_SHA1','')
    identity=git_identity(ROOT)
    require(len(expected_sha)==40 and identity.get('commit')==expected_sha and identity.get('worktree_dirty') is False,
            'An exact clean CI checkout is required')
    validate_endpoint(API)
    require(not output.exists(),'Use a new output directory; no overwrite')
    output=output.resolve();output.mkdir(parents=True,mode=0o700)
    work=output/'work';evidence=output/'evidence';work.mkdir();evidence.mkdir()
    def save(name,value): immutable_write(evidence/name,canonical(value))
    started=time.monotonic(); traces={}; phase='admin_login'
    failure=None
    try:
        with ExitStack() as stack:
            # Official default admin is used ONLY in this isolated, fresh loopback
            # test deployment. No external account or token is admitted.
            admin=APIClient(login('admin@open-metadata.org','admin'));stack.callback(admin.close)
            me=admin.request('GET','v1/users/loggedInUser')
            require(me.get('isAdmin') is True,'Bootstrap is not the fresh instance administrator')
            version=admin.request('GET','v1/system/version')
            require(version.get('version')==API_VERSION,'Running catalogue version does not match pinned adapter')
            save('server-version.json',version)
            settings=read_json(ROOT/'governance/openmetadata.example.json')
            settings['service_name']='ilc_g3_'+expected_sha[:10]
            settings['database_prefix']='ilc_g3'
            settings['owner_teams']={k:'ilc_g3_owners' for k in settings['owner_teams']}
            phase='bootstrap';tokens,bootstrap_receipt=bootstrap(admin,settings)
            save('bootstrap.json',bootstrap_receipt)
            reader=APIClient(tokens['reader']);stack.callback(reader.close)
            contract=read_json(ROOT/'contracts/sales.json')
            pipe=Pipeline(ROOT,work/'runtime',ROOT/'contracts/sales.json',ROOT/'profiles/reference.json')
            stack.callback(pipe.close)
            phase='reference_input'
            source=work/'source';manifest=create_fixture(source,contract,10000)
            with serving(source) as url:accepted=pipe.execute('g3-baseline',manifest['as_of'],source,url)
            require(accepted['status']=='ACCEPTED','No accepted input for catalogue')
            plan=build_export(pipe.journal,settings);save('generation1-plan.json',plan);save('generation1-acceptance.json',accepted)
            phase='publish_generation1';traces['initial']=[]
            p=Publisher(settings,tokens['writer'],work/'outbox',transport=TraceTransport(traces['initial']))
            try:first=p.publish(plan,allow_writes=True)
            finally:p.close()
            save('generation1-published.json',first)
            initial=snapshot(reader,plan);save('generation1-readback.json',initial)
            traces['replay']=[]
            p=Publisher(settings,tokens['writer'],work/'outbox',transport=TraceTransport(traces['replay']))
            try:require(p.publish(plan,allow_writes=True)==first,'Replay receipt changed')
            finally:p.close()
            require(write_count(traces['replay'])==0,'Replay must be read-only')
            phase='server_authorization'
            fact=initial['tables'][plan['database_fqn']+'.gold.fact_order_fulfillment']
            unauth=APIClient();stack.callback(unauth.close)
            unauth.request('GET','v1/tables/'+fact['id'],expected=(401,))
            reader.request('PATCH','v1/tables/'+fact['id'],[{'op':'replace','path':'/description','value':'UNAUTHORIZED_SENTINEL'}],expected=(403,),patch=True)
            writer=APIClient(tokens['writer']);stack.callback(writer.close)
            writer.request('POST','v1/policies',{'name':'ilc_forbidden_policy','description':'Must not be created',
                'rules':[{'name':'forbidden','resources':['All'],'operations':['ViewAll'],'effect':'allow'}]},expected=(403,))
            admin.request('GET','v1/policies/name/ilc_forbidden_policy',expected=(404,))
            require(snapshot(reader,plan)==initial,'A denied mutation changed baseline metadata')
            phase='accepted_generation2'
            source2=work/'source-revised';m2=create_fixture(source2,contract,10000,revision=1)
            with serving(source2) as url:accepted2=pipe.execute('g3-revision',m2['as_of'],source2,url)
            require(accepted2['status']=='ACCEPTED' and accepted2['generation']==2,'Second generation did not publish')
            plan2=build_export(pipe.journal,settings);save('generation2-plan.json',plan2);save('generation2-acceptance.json',accepted2)
            traces['lost_response']=[];phase='response_loss'
            p=Publisher(settings,tokens['writer'],work/'outbox',transport=TraceTransport(traces['lost_response'],drop_database_response=True))
            try:
                try:p.publish(plan2,allow_writes=True)
                except RemoteOutcomeUnknown:pass
                else:raise ValueError('Response-loss branch was not exercised')
            finally:p.close()
            ledger=read_json(work/'outbox'/(digest(plan2)+'.json'))
            require(ledger['operations'].get('databases:'+plan2['database_fqn'])=='REQUESTED','Write intent not durable before failure')
            remote_db=admin.get_name('databases',plan2['database_fqn'])
            p=Publisher(settings,tokens['writer'],work/'outbox',transport=TraceTransport(traces['lost_response']))
            try:second=p.publish(plan2,allow_writes=True)
            finally:p.close()
            require(admin.get_name('databases',plan2['database_fqn'])['id']==remote_db['id'],'Recovery replaced the database')
            puts=sum(e['method']=='PUT' and e['path']=='/api/v1/databases' for e in traces['lost_response'])
            require(puts==1,'Database write was repeated after loss')
            save('generation2-published.json',second)
            recovered=snapshot(reader,plan2);save('generation2-readback.json',recovered)
            require(len(initial['tables'])==len(recovered['tables'])==15,'Expected 15 actual table readbacks per generation')
            require(len(initial['edges'])==len(recovered['edges'])==11,'Expected 11 actual lineage readbacks per generation')
            require(initial['test_suite']['id']!=recovered['test_suite']['id'],'Generations share an unexpected executable suite')
            require(snapshot(reader,plan)==initial,'New generation altered accepted baseline')
            phase='foreign_object_conflict'
            conflict_settings=copy.deepcopy(settings);conflict_settings['database_prefix']='ilc_conflict'
            conflict_plan=build_export(pipe.journal,conflict_settings)
            sentinel=admin.request('POST','v1/databases',{'name':conflict_plan['database'],
                'service':settings['service_name'],'description':'ILC sentinel: intentionally foreign object; preserve'})
            sentinel_before=admin.get_name('databases',conflict_plan['database_fqn'])
            traces['conflict']=[]
            p=Publisher(conflict_settings,tokens['writer'],work/'conflict-outbox',transport=TraceTransport(traces['conflict']))
            try:
                try:p.publish(conflict_plan,allow_writes=True)
                except ConflictError:pass
                else:raise ValueError('Conflicting object not refused')
            finally:p.close()
            require(write_count(traces['conflict'])==0,'Conflict caused mutations')
            require(admin.get_name('databases',conflict_plan['database_fqn'])==sentinel_before,'Conflict overwrote existing object')
            save('conflict-preserved.json',{'id':sentinel['id'],'database_fqn':conflict_plan['database_fqn'],
                'description':sentinel_before['description'],'no_mutations':True})
            phase='evidence_gate'
            checks={
                'G3-01':{'status':'PASS_LIVE','product':'OpenMetadata','version':API_VERSION,'authenticated':True},
                'G3-02':{'status':'PASS_LIVE','generations':2,'tables_per_generation':len(initial['tables']),'lineage_edges_per_generation':len(initial['edges']),
                         'quality_results_per_generation':1,'basic_suites_read_back':2,'owners_tags_types_checked':True},
                'G3-03':{'status':'PASS_LIVE','replay_mutations':0},
                'G3-04':{'status':'PASS_LIVE','database_put_count':puts,'server_object_preserved':True,
                         'injection':'CLIENT_TRANSPORT_DROPS_RESPONSE_AFTER_REAL_SERVER_SUCCESS'},
                'G3-05':{'status':'PASS_LIVE','http_statuses':{'unauthenticated':401,'reader_write':403,'writer_policy_write':403},
                         'native_role_enforcement':True,'publisher_is_admin':False},
                'G3-06':{'status':'PASS_LIVE','conflict_mutations':0,'baseline_unchanged':True}}
            result={'schema_version':'ilc-openmetadata-live/1','status':'EXECUTED_LIVE_CATALOGUE_CHECKS',
                'server_version':API_VERSION,'source_profile':'reference_sqlite','git':identity,
                'classification':'PUBLIC_SYNTHETIC','checks':checks,'source_code':code_manifest(ROOT),
                'qualification_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'elapsed_seconds':round(time.monotonic()-started,6),
                'limits':['Input is a fresh reference generation; no native Spark rerun or combined native/catalogue attestation',
                          'Dedicated server and resource-scoped roles; not multi-tenant namespace isolation',
                          'Client transport injects loss after actual server write; not physical network outage',
                          'No TLS, SSO, scale, HA, backup/restore, Airflow connector ingestion or vendor integration',
                          'No raw data/sample rows or credentials published; metadata and aggregate DQ only']}
            require_live_result(result)
            save('qualification-openmetadata.json',result)
            summary='<html><head><meta charset="utf-8"><title>P01 catalogue readback</title></head><body><h1>P01 — real OpenMetadata API readback</h1><p>Static API-derived evidence, not the OpenMetadata UI.</p>'
            for label, snap in [('Generation 1',initial),('Generation 2',recovered)]:
                summary+='<h2>'+label+'</h2><ul>'+''.join('<li>'+html.escape(k)+'</li>' for k in snap['tables'])+'</ul>'
            (evidence/'catalogue-readback.html').write_text(summary+'</body></html>',encoding='utf-8')
            return result
    except BaseException as exc:
        failure={'phase':phase,'exception_type':type(exc).__name__,'message':str(exc)[:700]}
        # Messages originate from bounded local checks; no arbitrary HTTP body is recorded.
        raise
    finally:
        save('http-traces.json',traces)
        save('attempt.json',{'source_sha':identity['commit'],'phase':phase,'failure':failure,
            'completed':failure is None,'elapsed_seconds':round(time.monotonic()-started,6),'billing_credits_observed':None})
        inventory={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence.iterdir() if p.is_file()}
        save('evidence-manifest.json',{'schema_version':'ilc-catalogue-artifacts/1','sha256':inventory})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(qualify(args.output),indent=2))

if __name__=='__main__':main()
