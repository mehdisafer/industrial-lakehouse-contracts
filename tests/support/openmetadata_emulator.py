"""Protocol emulator ONLY. This is not an OpenMetadata service implementation."""
import copy
import json
import threading
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import httpx


class CatalogEmulator:
    def __init__(self):
        self.entities={};self.results={};self.edges=[];self.calls=[]
        self.version='1.12.0';self.fail_after_write=False;self.hide_after_write=False
        self.redirect=False;self.denied=False;self.failed=False
        self.team_id='11111111-1111-4111-8111-111111111111'
        self.prereq_missing=None

    def handler(self, req):
        self.calls.append((req.method,str(req.url),req.content.decode() if req.content else None))
        path=unquote(req.url.path).removeprefix('/api/v1/')
        if self.redirect:return httpx.Response(302,headers={'Location':'https://not-authorized.invalid'})
        if self.denied:return httpx.Response(403,text='DO-NOT-PERSIST-RESPONSE')
        if path=='system/version':return httpx.Response(200,json={'version':self.version})
        if path=='services/databaseServices/name/ilc_demo':return httpx.Response(200,json={'name':'ilc_demo','id':str(uuid.UUID(int=1))})
        if path=='teams/name/ilc_data_owners':return httpx.Response(200,json={'name':'ilc_data_owners','id':self.team_id})
        if path=='tags/name/ILCSynthetic.PUBLIC_SYNTHETIC':return httpx.Response(200,json={'fullyQualifiedName':'ILCSynthetic.PUBLIC_SYNTHETIC'})
        if path.startswith('lineage/table/'):
            return httpx.Response(200,json={'downstreamEdges':self.edges})
        if path=='lineage' and req.method=='PUT':
            e=json.loads(req.content)['edge'];self.edges.append({'fromEntity':e['fromEntity']['id'],'toEntity':e['toEntity']['id']})
            return httpx.Response(200,json={})
        if path.startswith('dataQuality/testCases/testCaseResults/'):
            if req.method=='POST':
                r=json.loads(req.content);self.results.setdefault(path,{})[r['timestamp']]=r
                return httpx.Response(200,json=r)
            return httpx.Response(200,json={'data':list(self.results.get(path,{}).values())})
        if req.method=='GET' and '/name/' in path:
            collection,fqn=path.split('/name/',1)
            obj=self.entities.get((collection,fqn))
            if obj is None or (self.hide_after_write and self.failed):return httpx.Response(404,json={})
            value=copy.deepcopy(obj)
            if collection=='dataQuality/testCases' and 'testDefinition' not in req.url.params.get('fields','').split(','):
                value.pop('testDefinition',None)
            return httpx.Response(200,json=value)
        if req.method=='PUT':
            body=json.loads(req.content);obj=copy.deepcopy(body);name=obj['name']
            if path=='databases':
                fqn=body['service']+'.'+name;obj['service']={'name':body['service']}
            elif path=='databaseSchemas':
                fqn=body['database']+'.'+name;obj['database']={'fullyQualifiedName':body['database']}
            elif path=='tables':
                fqn=body['databaseSchema']+'.'+name;obj['databaseSchema']={'fullyQualifiedName':body['databaseSchema']}
            elif path=='dataQuality/testDefinitions':fqn=name
            elif path=='dataQuality/testCases':
                fqn=body['entityLink'].removeprefix('<#E::table::').removesuffix('>')+'.'+name
                obj['testDefinition']={'fullyQualifiedName':body['testDefinition']}
            else:return httpx.Response(400,json={'error':'unsupported emulator path'})
            obj.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL,path+':'+fqn)),fullyQualifiedName=fqn)
            self.entities[path,fqn]=obj
            if self.fail_after_write and not self.failed:
                self.failed=True
                raise httpx.ReadTimeout('Injected lost response',request=req)
            return httpx.Response(200,json=obj)
        return httpx.Response(404,json={})

    @contextmanager
    def serving(self):
        emulator=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def _dispatch(self):
                data=self.rfile.read(int(self.headers.get('Content-Length','0'))) or b''
                req=httpx.Request(self.command,'http://127.0.0.1:'+str(self.server.server_port)+self.path,
                    headers=dict(self.headers),content=data)
                response=emulator.handler(req)
                self.send_response(response.status_code)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response.content)))
                self.end_headers();self.wfile.write(response.content)
            do_GET=_dispatch;do_PUT=_dispatch;do_POST=_dispatch
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield 'http://127.0.0.1:'+str(server.server_port)+'/api'
        finally:server.shutdown();server.server_close();thread.join(5)
