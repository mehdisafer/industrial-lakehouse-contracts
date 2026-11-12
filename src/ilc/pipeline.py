"""One admitted logical batch, many attempts, one accepted reporting generation."""
from __future__ import annotations
import os
import platform
import re
import subprocess
import time
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from .canonical import canonical, code_manifest, digest, immutable_write, now, read_json, utc
from .contracts import validate_contract, validate_profile, compatibility
from .errors import (PipelineError, IntegrityError, ConflictError, CaptureError,
                     SourceError, InjectedFailure, StaleBaseError, ContractError)
from .journal import Journal
from .sources import extract_all
from .storage import (batch_path, read_capture, write_capture, read_target, read_silver, write_target,
                      validate_native_publication, check_native_receipt)
from .transform import bounds_for, build_silver, business_checks, build_gold


def runtime_versions(profile):
    names = ['SQLAlchemy','httpx']
    if profile['engine']=='native_spark':
        names += ['pyspark','delta-spark','dagster','psycopg']
    result = {'python':platform.python_version()}
    for name in names:
        try:
            result[name]=version(name)
        except PackageNotFoundError:
            result[name]='NOT_INSTALLED'
    return result


def git_identity(repo: Path):
    try:
        commit=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,check=True,capture_output=True,timeout=5).stdout.decode().strip()
        dirty=bool(subprocess.run(['git','status','--porcelain'],cwd=repo,check=True,capture_output=True,timeout=5).stdout)
        return {'commit':commit,'worktree_dirty':dirty}
    except (OSError,subprocess.SubprocessError):
        return {'commit':None,'worktree_dirty':None}


class Pipeline:
    def __init__(self, repo: Path, root: Path, contract_path: Path, profile_path: Path):
        self.repo, self.root = repo.resolve(), root.resolve()
        self.contract = validate_contract(read_json(contract_path))
        self.profile = validate_profile(read_json(profile_path), self.contract)
        self.code = code_manifest(self.repo)
        self.versions = runtime_versions(self.profile)
        self.journal = Journal(self.root, self.profile)

    def close(self):
        self.journal.close()

    def execute(self, key: str, until: str, fixture_root: Path, api_url: str,
                failpoint: str | None = None, crash: bool = False):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]{0,99}',key):
            raise ValueError('Invalid logical request key')
        if failpoint not in {None,'after_target_commit','before_accept','after_accept'}:
            raise ValueError('Unknown test failpoint')
        until=utc(until)
        signature={'contract_sha256':digest(self.contract),'profile_sha256':digest(self.profile),
                   'code_sha256':digest(self.code),'runtime_versions':self.versions,'until':until,
                   'source_locator_sha256':digest(str(fixture_root.resolve()))}
        with self.journal.lock():
            old=self.journal.find(key)
            if old:
                if old['signature']!=signature:
                    raise ConflictError('Logical key is already bound to another request or runtime')
                plan=old['plan']
            else:
                state=self.journal.state()
                if state['accepted_batch'] is not None:
                    prior_contract=self.journal.get(state['accepted_batch'])['plan']['contract']
                    if digest(prior_contract)!=digest(self.contract):
                        old_version=tuple(map(int,prior_contract['version'].split('.')))
                        new_version=tuple(map(int,self.contract['version'].split('.')))
                        if new_version<=old_version:
                            raise ContractError('Changed metadata require a higher business contract version')
                        comparison=compatibility(prior_contract,self.contract)
                        if not comparison['compatible'] and (new_version[0]<=old_version[0] or any(s['mode']!='FULL' for s in self.profile['entity_sources'].values())):
                            raise ContractError('Breaking migration requires a new major and a full snapshot of every entity')
                plan={'schema_version':'ilc-run-plan/1','contract':self.contract,'profile':self.profile,
                      'contract_sha256':digest(self.contract),'profile_sha256':digest(self.profile),
                      'code_sha256':digest(self.code),'source_code':self.code,'runtime_versions':self.versions,
                      'base_accepted_batch':state['accepted_batch'],
                      'bounds':bounds_for(self.contract,self.profile,state['watermarks'],until),
                      'until':until,'single_host':True,'classification':'PUBLIC_SYNTHETIC'}
                old=self.journal.admit(key,signature,plan)
                plan=old['plan']
            batch_id=old['batch_id']
            location=batch_path(self.root,batch_id)
            immutable_write(location/'plan.json',canonical(plan))
            if old['status']=='ACCEPTED':
                target=read_target(self.root,batch_id)
                if target is None or digest(target)!=old['receipt']['target_manifest_sha256']:
                    raise IntegrityError('Accepted target no longer matches its receipt')
                check_native_receipt(self.root,batch_id,old['receipt'])
                immutable_write(location/'acceptance.json',canonical(old['receipt']))
                return {**old['receipt'],'invocation':'REPLAY_OF_ACCEPTED_BATCH'}
            if old['status']=='REJECTED':
                immutable_write(location/'rejection.json',canonical(old['receipt']))
                return old['receipt']
            self.journal.start_attempt(batch_id)
            start=time.perf_counter()
            try:
                captured=read_capture(self.root,batch_id,plan)
                if captured is None:
                    # A durable marker protects the interval between remote reading
                    # and the finalized Bronze manifest. Never recapture uncertain input.
                    marker=location/'capture_started.json'
                    if marker.exists():
                        raise CaptureError('Previous source capture outcome is uncertain; do not silently reread')
                    immutable_write(marker,canonical({'batch_id':batch_id,'at':now()}))
                    raw,source_receipts,source_manifest=extract_all(fixture_root,self.contract,self.profile,api_url)
                    if utc(source_manifest['as_of'])<until:
                        raise SourceError('The source snapshot does not cover the requested upper bound')
                    capture=write_capture(self.root,batch_id,raw,source_receipts,source_manifest,plan)
                    self.journal.mark(batch_id,'CAPTURED')
                else:
                    raw,capture=captured
                    self.journal.event(batch_id,'BRONZE_REUSED',{'capture_sha256':digest(capture)})
                base=plan['base_accepted_batch']
                if base is not None:
                    prior_target=read_target(self.root,base)
                    prior_receipt=self.journal.get(base)['receipt']
                    if prior_target is None or digest(prior_target)!=prior_receipt['target_manifest_sha256']:
                        raise IntegrityError('Accepted base differs from its committed receipt')
                previous=read_silver(self.root,base)
                silver,rejections,reconciliation=build_silver(raw,previous,self.contract,self.profile,plan['bounds'])
                business=business_checks(silver,self.contract)
                bad=sum(len(x) for x in rejections.values())
                if bad or business['status']!='PASS':
                    return self._reject(location,batch_id,plan,{'row_rejections':rejections,'business':business,
                                        'reconciliation':reconciliation},'DATA_QUALITY_BLOCK')
                facts,summary,gold_checks=build_gold(silver)
                if not all(gold_checks[k] for k in ['line_counts_equal','keys_equal','amounts_equal']):
                    return self._reject(location,batch_id,plan,{'gold':gold_checks},'RECONCILIATION_BLOCK')
                checks={'business':business,'source_to_silver':reconciliation,'silver_to_gold':gold_checks,
                        'reject_count':0,'status':'PASS'}
                target,reused=write_target(self.root,batch_id,plan,capture,silver,facts,summary,checks,self.contract,self.profile)
                self._fail('after_target_commit',failpoint,crash)
                self.journal.event(batch_id,'TARGET_RECONCILED' if reused else 'TARGET_WRITTEN',
                                   {'target_manifest_sha256':digest(target)})
                native_readback=validate_native_publication(self.root,batch_id,target,self.contract)
                self._fail('before_accept',failpoint,crash)
                watermarks={name:spec['upper'] for name,spec in plan['bounds'].items()}
                receipt={'schema_version':'ilc-evidence/1','project_id':'P01','batch_id':batch_id,
                         'plan_sha256':digest(plan),'contract_sha256':digest(self.contract),
                         'profile_sha256':digest(self.profile),'code_sha256':digest(self.code),
                         'git':git_identity(self.repo),'runtime_versions':self.versions,
                         'target_manifest_sha256':digest(target),'capture_sha256':digest(capture),
                         'dataset_as_of':until,'source_snapshot_id':capture['source_manifest']['snapshot_id'],
                         'engine':self.profile['engine'],'target':self.profile['target'],
                         'native_final_readback':native_readback,
                         'observed_captured_rows':sum(len(r) for r in raw.values()),
                         'observed_bronze_bytes':sum(f['bytes'] for f in capture['files'].values()),
                         'gold_fact_rows':len(facts),'source_to_target':gold_checks,
                         'elapsed_attempt_seconds':round(time.perf_counter()-start,6),
                         'target_reused':reused,'freshness_budget_seconds':self.profile['freshness_seconds'],
                         'provider_integration':'NOT_RUN','catalog_provider':'NOT_RUN',
                         'measurements_scope':'single-host bounded synthetic reference' if self.profile['engine']=='reference_sqlite' else 'single-host bounded synthetic native',
                         'limitations':['No global transaction across external sources','No CDC or tombstone/delete capture',
                                        'No distributed exactly-once claim','No Big Data throughput claim','No Fabric/Power BI qualification',
                                        'Whole-source bounded capture before incremental merge; no pushdown scalability claim',
                                        'Application RBAC is not OS isolation']}
                accepted=self.journal.accept(batch_id,plan['base_accepted_batch'],watermarks,receipt)
                self._fail('after_accept',failpoint,crash)
                immutable_write(location/'acceptance.json',canonical(accepted))
                return {**accepted,'invocation':'RESUMED' if old['attempts'] else 'FIRST_ATTEMPT'}
            except SourceError as exc:
                return self._reject(location,batch_id,plan,{'source_error':exc.code},'SOURCE_CAPTURE_BLOCK')
            except BaseException as exc:
                # An accepted transaction is never relabelled failed after lost response.
                current=self.journal.get(batch_id)
                if current['status'] not in {'ACCEPTED','REJECTED'}:
                    self.journal.mark(batch_id,'FAILED',getattr(exc,'code','INTERNAL_ERROR'))
                raise

    @staticmethod
    def _fail(here,selected,crash):
        if here!=selected:
            return
        if crash:
            if os.environ.get('ILC_ENABLE_TEST_FAILPOINTS')!='1':
                raise ValueError('Crash injection needs explicit synthetic-test opt-in')
            os._exit(73)
        raise InjectedFailure(here)

    def _reject(self,location,batch_id,plan,details,reason):
        receipt={'schema_version':'ilc-evidence/1','project_id':'P01','batch_id':batch_id,
                 'status':'REJECTED','reason':reason,'plan_sha256':digest(plan),
                 'details':details,'watermark_advanced':False,'dataset_promoted':False,'at':now()}
        self.journal.reject(batch_id,receipt)
        immutable_write(location/'rejection.json',canonical(receipt))
        return receipt
