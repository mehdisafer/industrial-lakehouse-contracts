"""Bounded OpenMetadata 1.12.0 publisher for accepted synthetic generations.

No database records, sample data, credentials or host paths are exported. This
adapter uses metadata APIs, not the ingestion SDK. Contract tests and a protocol
emulator do NOT qualify a real OpenMetadata installation.
"""
from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit
import uuid

import httpx

from .canonical import canonical, digest, immutable_write, read_json, atomic_json, pipeline_lock, IDENTIFIER
from .contracts import DECIMAL
from .errors import PipelineError, IntegrityError, ConflictError
from .reporting import ReportReader
from .storage import batch_path, read_target

API_VERSION = "1.12.0"
UPSTREAM_COMMIT = "caa14bfd42af6ec84464aa81815addd3e0cd2902"


class GovernanceError(PipelineError):
    code = "GOVERNANCE_ERROR"


class RemoteOutcomeUnknown(GovernanceError):
    code = "GOVERNANCE_REMOTE_OUTCOME_UNKNOWN"


def validate_settings(settings: dict) -> dict:
    required = {"api_url", "service_name", "database_prefix", "owner_teams", "classification_tag", "server_version"}
    if set(settings) != required or settings["server_version"] != API_VERSION:
        raise GovernanceError("Explicit OpenMetadata 1.12.0 settings required")
    parsed = urlsplit(settings["api_url"])
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/api"):
        raise GovernanceError("This profile only admits an explicit loopback /api endpoint")
    for key in ("service_name", "database_prefix"):
        if not IDENTIFIER.fullmatch(settings[key]) or not settings[key].startswith("ilc_"):
            raise GovernanceError("Dedicated ilc_ service/database identifiers required")
    if not re.fullmatch(r"ILCSynthetic\.PUBLIC_SYNTHETIC", settings["classification_tag"]):
        raise GovernanceError("Only the synthetic classification is allowed")
    teams = settings["owner_teams"]
    if not isinstance(teams, dict) or not teams or any(not isinstance(v,str) or not IDENTIFIER.fullmatch(v) for v in teams.values()):
        raise GovernanceError("Explicit role-to-team mapping required")
    return settings


def column(field: dict) -> dict:
    typ = field["type"]
    item = {"name": field["name"], "constraint": "NULL" if field["nullable"] else "NOT_NULL"}
    if typ == "string": item["dataType"] = "STRING"
    elif typ == "integer": item["dataType"] = "BIGINT"
    elif typ == "timestamp_utc": item["dataType"] = "TIMESTAMP"
    else:
        precision, scale = map(int, DECIMAL.fullmatch(typ).groups())
        item.update(dataType="DECIMAL", precision=precision, scale=scale)
    return item


def build_export(journal, settings: dict) -> dict:
    """Build only from a reread, accepted and intact generation; no HTTP writes."""
    settings = validate_settings(settings)
    state = journal.state()
    if state["accepted_batch"] is None:
        raise GovernanceError("No accepted generation is available")
    run = journal.get(state["accepted_batch"])
    contract = run["plan"]["contract"]
    report = ReportReader(journal).report(contract["sites"])
    batch = report["dataset_batch_id"]
    receipt = run["receipt"]
    if batch != run['batch_id'] or report['generation'] != receipt['generation']:
        raise ConflictError('Accepted generation changed while building metadata export')
    target = read_target(journal.root, batch)
    root = batch_path(journal.root, batch) / "target"
    quality = read_json(root / "checks.json")
    if quality["status"] != "PASS":
        raise IntegrityError("Accepted quality result is inconsistent")
    roles = {contract["owner_role"]} | {e["owner_role"] for e in contract["entities"].values()}
    if not roles <= settings["owner_teams"].keys():
        raise GovernanceError("Every contracted owner role needs an explicit catalog team")
    database = settings["database_prefix"] + "_" + batch[:16]
    base = settings["service_name"] + "." + database
    marker = "ILC managed immutable snapshot; batch=" + batch + "; contract=" + receipt["contract_sha256"]
    tables = []
    for name, entity in sorted(contract["entities"].items()):
        for layer in ("bronze", "silver"):
            # Bronze contains raw serialized strings. Do not claim its columns
            # already have the Silver types.
            fields = entity["fields"] if layer == "silver" else [
                {**f,"type":"string","nullable":True} for f in entity["fields"]]
            tables.append({"fqn": base+"."+layer+"."+name,
                "owner_role": entity["owner_role"],
                "body": {"name":name,"description":marker,"databaseSchema":base+"."+layer,
                         "columns":[column(f) for f in fields]}})
    gold_fields = {
        "dim_customer": contract["entities"]["customers"]["fields"],
        "dim_product": contract["entities"]["products"]["fields"],
        "dim_site": [{"name":"site_id","type":"string","nullable":False}],
    }
    strings = ("order_id","line_id","customer_id","site_id","currency","product_id")
    integers = ("quantity","shipped_qty","on_time_qty","backlog_qty")
    amounts = ("ordered_amount","backlog_amount")
    def fields(names,typ): return [{"name":n,"type":typ,"nullable":False} for n in names]
    gold_fields["fact_order_fulfillment"] = fields(strings,"string")+fields(integers,"integer")+fields(amounts,"decimal(18,2)")
    gold_fields["site_kpi"] = fields(("site_id","currency"),"string")+fields(("order_count","line_count",*integers),"integer")+fields(amounts,"decimal(18,2)")
    for name, fields_ in gold_fields.items():
        tables.append({"fqn":base+".gold."+name,"owner_role":contract["owner_role"],
            "body":{"name":name,"description":marker,"databaseSchema":base+".gold",
                    "columns":[column(f) for f in fields_]}})
    edges = [(base+".bronze."+n,base+".silver."+n) for n in contract["entities"]]
    edges += [(base+".silver.customers",base+".gold.dim_customer"),
              (base+".silver.products",base+".gold.dim_product")]
    edges += [(base+".silver."+n,base+".gold.fact_order_fulfillment") for n in ("orders","order_lines","shipments")]
    edges += [(base+".gold.fact_order_fulfillment",base+".gold.site_kpi")]
    # dim_site is generated from the contract, not a fabricated upstream table.
    timestamp = int(datetime.fromisoformat(receipt["accepted_at"].replace("Z","+00:00")).timestamp()*1000)
    return {"schema_version":"ilc-governance-export/1","settings":settings,
        "batch_id":batch,"generation":receipt["generation"],"source_profile":receipt["engine"],
        "acceptance_sha256":digest(receipt),"target_manifest_sha256":digest(target),
        "contract_sha256":receipt["contract_sha256"],"database":database,"database_fqn":base,
        "description":marker,"tables":tables,"edges":[list(x) for x in edges],
        "quality":{"timestamp":timestamp,"testCaseStatus":"Success",
            "result":"ILC accepted reconciliation; acceptance_sha256="+digest(receipt),
            "testResultValue":[{"name":k,"value":str(quality["silver_to_gold"][k]).lower()}
                               for k in ("line_counts_equal","keys_equal","amounts_equal")]},
        "limits":["Metadata and aggregate reconciliation only; no samples or records exported",
                  "No dashboard asset fabricated; report remains a separate consumer",
                  "One immutable catalog database per accepted generation; retention is manual",
                  "Single catalog writer per namespace; no cross-host writer fencing"]}


def _subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual,dict) and all(k in actual and _subset(v,actual[k]) for k,v in expected.items())
    if isinstance(expected,list):
        # Named schema members and owner/tag sets are order-independent.
        return isinstance(actual,list) and len(expected)==len(actual) and all(
            any(_subset(item, candidate) for candidate in actual) for item in expected)
    return expected == actual


class Publisher:
    """Create-only namespace with durable write intent and mandatory readback.

    After an uncertain write, a new invocation reconciles by GET. If no exact
    remote object can be found it refuses another mutation, rather than treating
    a lost response as permission to repeat an operation.
    """
    def __init__(self, settings: dict, token: str, state_dir: Path, *, transport=None):
        self.settings=validate_settings(settings)
        if not isinstance(token,str) or not token or "\n" in token or "\r" in token:
            raise GovernanceError("A non-empty token is required outside persisted metadata")
        self.state_dir=state_dir
        self.client=httpx.Client(base_url=settings['api_url']+'/',
            headers={'Authorization':'Bearer '+token},timeout=15,trust_env=False,
            follow_redirects=False,transport=transport)
        self.ledger=None
        self.state=None

    def close(self): self.client.close()

    def request(self, method, path, body=None, params=None, absent=False):
        if not path.startswith('v1/') or '..' in path or '://' in path:
            raise GovernanceError('Unexpected catalog endpoint')
        try:
            with self.client.stream(method,path,json=body,params=params) as r:
                if r.status_code==404 and absent:return None
                if r.status_code not in (200,201):
                    raise GovernanceError('Catalog returned HTTP '+str(r.status_code))
                buf=bytearray()
                for block in r.iter_bytes():
                    buf.extend(block)
                    if len(buf)>2_000_000:raise GovernanceError('Catalog response exceeded byte budget')
                if not buf:return {}
                value = json.loads(buf)
                if not isinstance(value, dict):
                    raise GovernanceError("Catalog response must be an object")
                return value
        except httpx.HTTPError:
            # Do not leak URL, response body or bearer in a persisted exception.
            raise RemoteOutcomeUnknown('Catalog response unavailable; reconcile before any further write') from None
        except (ValueError,TypeError):
            raise GovernanceError('Catalog returned invalid JSON') from None

    def _save(self): atomic_json(self.ledger,self.state)

    def _operation(self, key, read, write, matches):
        prior=self.state['operations'].get(key)
        current=read()
        if current is not None:
            if not matches(current):raise ConflictError('Existing remote metadata differ: '+key)
            self.state['operations'][key]='VERIFIED';self._save()
            return current
        if prior is not None:
            raise RemoteOutcomeUnknown('Previously attempted remote object cannot be reconciled: '+key)
        self.state['operations'][key]='REQUESTED';self._save()
        write()
        current=read()
        if current is None or not matches(current):
            raise RemoteOutcomeUnknown('Write response is insufficient; remote readback differs: '+key)
        self.state['operations'][key]='VERIFIED';self._save()
        return current

    def entity(self, collection, fqn, body, expected, fields=None):
        path='v1/'+collection
        result=self._operation(collection+':'+fqn,
            lambda:self.request('GET',path+'/name/'+quote(fqn,safe=''),params={'fields':fields} if fields else None,absent=True),
            lambda:self.request('PUT',path,body),
            lambda actual:actual.get('fullyQualifiedName',actual.get('name'))==fqn
                and not actual.get('deleted',False) and _subset(expected,actual))
        try: uuid.UUID(result['id'])
        except (ValueError,KeyError,TypeError):raise GovernanceError('Catalog entity lacks a valid UUID') from None
        return result

    def publish(self, plan: dict, *, allow_writes: bool = False) -> dict:
        if not allow_writes:raise GovernanceError('Explicit metadata-write authorization required')
        if plan.get('schema_version')!='ilc-governance-export/1' or plan.get('settings')!=self.settings:
            raise GovernanceError('Plan and destination settings differ')
        expected_database=self.settings['database_prefix']+'_'+plan['batch_id'][:16]
        if (not re.fullmatch('[a-f0-9]{64}',plan['batch_id']) or plan['database']!=expected_database
            or plan['database_fqn']!=self.settings['service_name']+'.'+expected_database):
            raise GovernanceError('Plan escaped its synthetic catalog namespace')
        # Validates all names and links BEFORE the first outbound write.
        fqns={table['fqn'] for table in plan['tables']}
        base=plan['database_fqn']
        for table in plan['tables']:
            body=table['body']
            if (not IDENTIFIER.fullmatch(body['name']) or body['databaseSchema'] not in {base+'.'+s for s in ('bronze','silver','gold')}
                or table['fqn']!=body['databaseSchema']+'.'+body['name'] or body['description']!=plan['description']):
                raise GovernanceError('Unexpected table in immutable export plan')
        if any(a not in fqns or b not in fqns for a,b in plan['edges']):
            raise GovernanceError('Lineage edge leaves the approved export')
        self.state_dir.mkdir(parents=True,exist_ok=True)
        with pipeline_lock(self.state_dir):
            plan_hash=digest(plan)
            self.ledger=self.state_dir/(plan_hash+'.json')
            self.state=read_json(self.ledger) if self.ledger.exists() else {'plan_sha256':plan_hash,'operations':{}}
            if self.state['plan_sha256']!=plan_hash:raise IntegrityError('Governance journal is bound to another plan')
            immutable_write(self.state_dir/(plan_hash+'.plan.json'),canonical(plan))
            self._save()
            version=self.request('GET','v1/system/version')
            if version.get('version')!=API_VERSION:raise GovernanceError('Unqualified OpenMetadata server version')
            service=self.request('GET','v1/services/databaseServices/name/'+quote(self.settings['service_name'],safe=''))
            if service.get('name')!=self.settings['service_name'] or service.get('deleted',False):
                raise GovernanceError('Dedicated metadata service is missing or deleted')
            teams={}
            for role, name in sorted(self.settings['owner_teams'].items()):
                team=self.request('GET','v1/teams/name/'+quote(name,safe=''))
                try: uuid.UUID(team['id'])
                except (ValueError,KeyError,TypeError):raise GovernanceError('Owner team has invalid identity') from None
                if team.get('name')!=name or team.get('deleted',False):raise GovernanceError('Owner team mismatch')
                teams[role]={'id':team['id'],'type':'team'}
            tag=self.request('GET','v1/tags/name/'+self.settings['classification_tag'])
            if tag.get('fullyQualifiedName')!=self.settings['classification_tag'] or tag.get('deleted',False):
                raise GovernanceError('Synthetic classification must exist before publishing')
            desc=plan['description']
            self.entity('databases',base,{'name':plan['database'],'service':self.settings['service_name'],'description':desc},
                {'name':plan['database'],'service':{'name':self.settings['service_name']},'description':desc})
            for layer in ('bronze','silver','gold'):
                self.entity('databaseSchemas',base+'.'+layer,{'name':layer,'database':base,'description':desc},
                    {'name':layer,'database':{'fullyQualifiedName':base},'description':desc})
            ids={}
            for table in plan['tables']:
                tags=[{'tagFQN':self.settings['classification_tag'],'labelType':'Manual','state':'Confirmed','source':'Classification'}]
                body={**table['body'],'owners':[teams[table['owner_role']]],'tags':tags}
                expected={**body,'databaseSchema':{'fullyQualifiedName':body['databaseSchema']}}
                ids[table['fqn']]=self.entity('tables',table['fqn'],body,expected,'owners,tags')['id']
            for a,b in plan['edges']:
                edge={'fromEntity':{'id':ids[a],'type':'table'},'toEntity':{'id':ids[b],'type':'table'}}
                def read_edge(a=a,b=b):
                    graph=self.request('GET','v1/lineage/table/'+ids[a],params={'upstreamDepth':0,'downstreamDepth':1})
                    matches=[e for e in graph.get('downstreamEdges',[]) if e.get('fromEntity')==ids[a] and e.get('toEntity')==ids[b]]
                    return matches[0] if matches else None
                self._operation('lineage:'+a+'->'+b,read_edge,
                    lambda edge=edge:self.request('PUT','v1/lineage',{'edge':edge}),
                    lambda actual,a=a,b=b:actual.get('fromEntity')==ids[a] and actual.get('toEntity')==ids[b])
            definition=self.settings['database_prefix']+'_accepted_reconciliation'
            definition_body={'name':definition,'description':'ILC deterministic source/Silver/Gold reconciliation; external result only.',
                             'entityType':'TABLE','testPlatforms':['Other']}
            self.entity('dataQuality/testDefinitions',definition,definition_body,definition_body)
            table=base+'.gold.fact_order_fulfillment'
            name='ilc_accepted_reconciliation';case=table+'.'+name
            body={'name':name,'testDefinition':definition,'entityLink':'<#E::table::'+table+'>','description':desc}
            self.entity('dataQuality/testCases',case,body,{**body,'testDefinition':{'fullyQualifiedName':definition}},'testDefinition')
            result_path='v1/dataQuality/testCases/testCaseResults/'+quote(case,safe='')
            timestamp=plan['quality']['timestamp']
            def read_result():
                data=self.request('GET',result_path,params={'startTs':timestamp,'endTs':timestamp})
                found=[r for r in data.get('data',[]) if r.get('timestamp')==timestamp]
                if len(found)>1:raise ConflictError('Multiple results share the accepted timestamp')
                return found[0] if found else None
            self._operation('quality:'+case+':'+str(timestamp),read_result,
                lambda:self.request('POST',result_path,plan['quality']),lambda actual:_subset(plan['quality'],actual))
            receipt={'schema_version':'ilc-governance-receipt/1','status':'REMOTE_METADATA_READ_BACK',
                'batch_id':plan['batch_id'],'generation':plan['generation'],'plan_sha256':plan_hash,
                'acceptance_sha256':plan['acceptance_sha256'],'source_profile':plan['source_profile'],
                'server_version':API_VERSION,'upstream_contract_commit':UPSTREAM_COMMIT,
                'tables_read_back':len(ids),'lineage_edges_read_back':len(plan['edges']),
                'quality_results_read_back':1,'operations_verified':len(self.state['operations']),
                'database_fqn':base,'record_samples_exported':False,
                'qualification_note':'Readback is not a full server deployment, RBAC, resilience or scale qualification'}
            atomic_json(self.state_dir/(plan_hash+'.receipt.json'),receipt)
            return receipt
