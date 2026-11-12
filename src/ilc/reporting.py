"""Report only an accepted immutable generation; apply role scope before aggregation."""
from __future__ import annotations
import hashlib
import hmac
import html
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .canonical import digest, read_json, now
from .errors import IntegrityError
from .storage import read_target, batch_path, check_native_receipt


class NoAcceptedData(IntegrityError):
    code = 'NO_ACCEPTED_DATASET'


class ReportReader:
    def __init__(self, journal):
        self.journal=journal

    def report(self, allowed_sites: list[str], requested_site: str | None = None, clock: datetime | None = None):
        if requested_site is not None and requested_site not in allowed_sites:
            raise PermissionError('Site is outside this principal scope')
        state=self.journal.state()
        batch_id=state['accepted_batch']
        if batch_id is None:
            raise NoAcceptedData('No accepted generation exists')
        run=self.journal.get(batch_id)
        manifest=read_target(self.journal.root,batch_id)
        if manifest is None or digest(manifest)!=run['receipt']['target_manifest_sha256']:
            raise IntegrityError('The reporting generation no longer matches its receipt')
        check_native_receipt(self.journal.root,batch_id,run['receipt'])
        root=batch_path(self.journal.root,batch_id)/'target'
        summaries=read_json(root/'gold/site_kpi.json')
        permitted=[requested_site] if requested_site else allowed_sites
        filtered=[row for row in summaries if row['site_id'] in permitted]
        until=datetime.fromisoformat(run['receipt']['dataset_as_of'].replace('Z','+00:00'))
        clock=clock or datetime.now(timezone.utc)
        age=max(0.0,(clock-until).total_seconds())
        future_dated=clock<until
        degraded=state['last_status'] in {'REJECTED','FAILED'}
        stale=age>run['receipt']['freshness_budget_seconds']
        totals={name:sum(row[name] for row in filtered) for name in ['order_count','line_count','quantity','shipped_qty','on_time_qty','backlog_qty']}
        for name in ['ordered_amount','backlog_amount']:
            totals[name]=format(sum((Decimal(row[name]) for row in filtered),Decimal(0)),'.2f')
        return {'status':'DEGRADED' if degraded else ('FUTURE_DATED' if future_dated else ('STALE' if stale else 'CURRENT')),
                'dataset_batch_id':batch_id,'generation':run['receipt']['generation'],
                'dataset_as_of':run['receipt']['dataset_as_of'],'accepted_at':run['receipt']['accepted_at'],
                'generated_at':clock.isoformat(),'age_seconds':round(age,3),'freshness_budget_seconds':run['receipt']['freshness_budget_seconds'],
                'stale':stale,'future_dated':future_dated,'degraded':degraded,'latest_attempt_status':state['last_status'],
                'scope':permitted,'currency':'EUR','totals':totals,'sites':filtered,
                'lineage':{'plan_sha256':run['receipt']['plan_sha256'],'contract_sha256':run['receipt']['contract_sha256'],
                           'target_manifest_sha256':run['receipt']['target_manifest_sha256']},
                'profile':run['receipt']['engine'], 'classification':'PUBLIC_SYNTHETIC'}

    def lines(self, allowed_sites: list[str], order_id: str):
        report=self.report(allowed_sites)
        path=batch_path(self.journal.root,report['dataset_batch_id'])/'target/gold/fact_order_fulfillment.json'
        return [r for r in read_json(path) if r['site_id'] in allowed_sites and r['order_id']==order_id]


class AccessPolicy:
    def __init__(self, document: dict, known_sites: list[str]):
        if document.get('schema_version')!='ilc-access/1' or not isinstance(document.get('principals'),list):
            raise ValueError('Invalid access policy')
        self.principals=[]
        seen=set()
        for principal in document['principals']:
            sha=principal.get('token_sha256','')
            if (len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha) or sha in seen
                    or not set(principal['sites'])<=set(known_sites)
                    or not set(principal['permissions'])<={'report','catalog','evidence'}):
                raise ValueError('Invalid principal scope')
            # Full receipts and catalog counts describe every site. A site reader
            # cannot gain those global views via a separate permission flag.
            if set(principal['permissions']) & {'catalog','evidence'} and set(principal['sites'])!=set(known_sites):
                raise ValueError('Global evidence/catalog permissions require the full site scope')
            seen.add(sha)
            self.principals.append(principal)
    def authenticate(self, token: str):
        candidate=hashlib.sha256(token.encode()).hexdigest()
        principal=None
        for item in self.principals:
            if hmac.compare_digest(candidate,item['token_sha256']):
                principal=item
        return principal


def render_snapshot(report: dict) -> str:
    """Static export of already-authorized PUBLIC_SYNTHETIC report data only."""
    def e(x):return html.escape(str(x))
    totals=report['totals']
    cards=''.join(f'<article><span>{e(label)}</span><strong>{e(value)}</strong></article>' for label,value in [
        ('Ordered amount · EUR',totals['ordered_amount']),('Backlog · EUR',totals['backlog_amount']),
        ('Orders',totals['order_count']),('Shipped units',totals['shipped_qty'])])
    rows=''.join('<tr>'+''.join('<td>'+e(row[k])+'</td>' for k in ['site_id','order_count','line_count','quantity','shipped_qty','on_time_qty','ordered_amount','backlog_amount'])+'</tr>' for row in report['sites'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P01 · Accepted sales fulfillment</title><style>
body{{font:16px system-ui,sans-serif;max-width:1180px;margin:48px auto;padding:0 24px;color:#182231;background:#f6f8fb}}h1{{font-size:36px;letter-spacing:-1px;margin-bottom:8px}}h2{{margin-top:36px;font-size:20px}}
.kicker{{font-size:12px;letter-spacing:2px;text-transform:uppercase}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:28px 0}}article{{background:white;padding:24px;border:1px solid #d6dee7}}article span{{display:block;font-size:13px;margin-bottom:12px}}strong{{font-size:27px;font-variant-numeric:tabular-nums}}table{{border-collapse:collapse;width:100%;background:white;font-size:14px}}td,th{{padding:14px;text-align:right;border-bottom:1px solid #d6dee7}}td:first-child,th:first-child{{text-align:left}}.state{{padding:16px;border-left:4px solid #273b50;background:#e8edf3}}code{{overflow-wrap:anywhere;font-size:12px}}p{{line-height:1.6}}footer{{margin-top:36px;font-size:13px}}@media(max-width:800px){{.cards{{grid-template-columns:1fr 1fr}}table{{font-size:11px}}td,th{{padding:8px}}}}
</style><p class="kicker">P01 / industrial lakehouse contracts / synthetic demonstration</p>
<h1>Accepted sales fulfillment</h1><p>One reporting generation. Exact decimal totals. Traceable acceptance.</p>
<div class="state"><b>{e(report['status'])}</b> · Generation {e(report['generation'])} · Last attempt: {e(report['latest_attempt_status'])}<br>
Data as of {e(report['dataset_as_of'])} · Age {e(report['age_seconds'])} seconds · Profile {e(report['profile'])}</div>
<div class="cards">{cards}</div><h2>Authorized site scope</h2><table><thead><tr><th>Site</th><th>Orders</th><th>Lines</th><th>Units ordered</th><th>Shipped</th><th>Shipped on time</th><th>Ordered EUR</th><th>Backlog EUR</th></tr></thead><tbody>{rows}</tbody></table>
<p>On-time units are shipped units delivered no later than the promised timestamp; this is not an OTIF order metric. No currency conversion is performed.</p>
<h2>Lineage and proof</h2><p>Batch <code>{e(report['dataset_batch_id'])}</code><br>Contract <code>{e(report['lineage']['contract_sha256'])}</code><br>Target manifest <code>{e(report['lineage']['target_manifest_sha256'])}</code></p>
<footer>Static export generated from an authorized API response at {e(report['generated_at'])}. PUBLIC_SYNTHETIC only. It is not live Power BI, native platform qualification, or a Big Data benchmark.</footer></html>'''
