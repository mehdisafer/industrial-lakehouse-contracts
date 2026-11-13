"""Authenticated reporting surface. No row data in its unauthenticated page."""
from __future__ import annotations
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from .canonical import read_json
from .errors import IntegrityError
from .reporting import AccessPolicy, ReportReader, render_snapshot
from .storage import batch_path

LOGIN_PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><title>P01 report</title>
<style>body{font:16px system-ui;max-width:900px;margin:48px auto;padding:24px}input{width:70%;padding:12px}button{padding:12px}pre{white-space:pre-wrap}</style>
<h1>P01 · Accepted reporting</h1><p>Enter a demo bearer token. It is kept in memory only; no cloud service is contacted.</p>
<input id="token" type="password" autocomplete="off" aria-label="Demo token"><button id="load">Load my report</button><pre id="output"></pre>
<script>document.getElementById('load').onclick=async()=>{const t=document.getElementById('token').value;const r=await fetch('/api/report',{headers:{Authorization:'Bearer '+t},cache:'no-store'});document.getElementById('output').textContent=JSON.stringify(await r.json(),null,2);};</script></html>'''


def create_app(journal, contract: dict, access_policy: dict) -> FastAPI:
    policy=AccessPolicy(access_policy,contract['sites'])
    reader=ReportReader(journal)
    app=FastAPI(title='P01 accepted reporting',docs_url=None,redoc_url=None,openapi_url=None)
    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(status_code=503,content={'detail':exc.code})
    @app.middleware('http')
    async def security_headers(request, call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        return response
    def principal(authorization: str | None=Header(default=None)):
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401,detail='AUTH_REQUIRED')
        item=policy.authenticate(authorization[7:])
        if item is None:
            raise HTTPException(401,detail='INVALID_CREDENTIAL')
        return item
    def permission(item, name):
        if name not in item['permissions']:
            raise HTTPException(403,detail='PERMISSION_DENIED')
    def get_report(item,site):
        permission(item,'report')
        try:
            return reader.report(item['sites'],site)
        except PermissionError:
            raise HTTPException(403,detail='SITE_SCOPE_DENIED') from None
        except IntegrityError as exc:
            raise HTTPException(503,detail=exc.code) from None
    @app.get('/',response_class=HTMLResponse)
    def index():return LOGIN_PAGE
    @app.get('/health')
    def health():return {'process':'ALIVE','accepted_generation_present':journal.state()['accepted_batch'] is not None}
    @app.get('/api/report')
    def report(site: str | None=Query(default=None,max_length=30),item=Depends(principal)):
        return get_report(item,site)
    @app.get('/dashboard',response_class=HTMLResponse)
    def dashboard(site: str | None=Query(default=None,max_length=30),item=Depends(principal)):
        return render_snapshot(get_report(item,site))
    @app.get('/api/orders/{order_id}')
    def order(order_id: str,item=Depends(principal)):
        permission(item,'report')
        try:
            data=reader.lines(item['sites'],order_id)
        except IntegrityError as exc:
            raise HTTPException(503,detail=exc.code) from None
        if not data:
            raise HTTPException(404,detail='NOT_FOUND')
        return data
    @app.get('/api/evidence')
    def evidence(item=Depends(principal)):
        permission(item,'evidence')
        # Integrity is checked before returning the accepted receipt.
        report=reader.report(contract['sites'])
        return journal.get(report['dataset_batch_id'])['receipt']
    @app.get('/api/catalog')
    def catalog(item=Depends(principal)):
        permission(item,'catalog')
        report=reader.report(contract['sites'])
        root=batch_path(journal.root,report['dataset_batch_id'])/'target/catalog'
        return {'provider':'LOCAL_FILE_CATALOG_NOT_OPENMETADATA',
                'tables':read_json(root/'tables.json'),'lineage':read_json(root/'lineage.json'),
                'quality':read_json(root/'quality.json')}
    return app
