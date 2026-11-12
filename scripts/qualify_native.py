"""Opt-in native qualification; requires real Postgres/Spark/Delta/Dagster.

No mock or fallback is used. This harness is a candidate until its receipts have
actually been observed. It seeds new synthetic schemas only; no DROP/TRUNCATE.
Run on a disposable Linux runner with the database and package access approved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from ilc.canonical import canonical, code_manifest, digest, read_json, immutable_write
from ilc.errors import NativeUnavailable
from ilc.fixtures import create_fixture
from ilc.hosting import serve_report
from ilc.journal import Journal
from ilc.native import require_native, seed_postgres
from ilc.pipeline import Pipeline, git_identity
from ilc.report_api import create_app
from ilc.reporting import render_snapshot
from ilc.source_api import serving
from ilc.storage import batch_path, read_target


def scenario_profile(template: dict, output: Path, name: str) -> dict:
    """Keep each fixture in its own deterministic, dedicated source schema."""
    if name not in {'base', 'duplicate_key', 'invalid_amount', 'schema_drift', 'recovery'}:
        raise ValueError('Unknown native qualification scenario')
    return {**template, 'source_schema': 'ilc_demo_' + digest(str(output.resolve()))[:12] + '_' + name}


def _crash_child(command: list[str], env: dict[str, str]) -> int:
    """Own the POSIX process group; stop residual gateway children before resume.

    The selected failpoint is after synchronous Spark writes and Spark.stop(), not
    during an in-flight Spark action. This does not qualify mid-action fencing.
    """
    if os.name != 'posix':
        raise NativeUnavailable('This native process-group harness requires a disposable POSIX runner')
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return process.wait(timeout=600)
    finally:
        # Only the newly created process group belongs to this harness. Never use
        # a name-based java/python kill, which could affect another application.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        # Processes can still be reaped by init after their owner died. Any live
        # group is killed before a new batch owner is allowed by this harness.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if Path('/proc').is_dir():
            deadline=time.monotonic()+10
            while True:
                live=[]
                for entry in Path('/proc').iterdir():
                    if not entry.name.isdigit():continue
                    try:
                        stat_text=(entry/'stat').read_text()
                        fields=stat_text[stat_text.rfind(')')+2:].split()
                        # /proc pid stat: state, ppid, pgrp, session, ...
                        if int(fields[2])==process.pid and fields[0]!='Z':live.append(int(entry.name))
                    except (FileNotFoundError,ProcessLookupError,PermissionError):continue
                if not live:break
                if time.monotonic()>deadline:
                    raise RuntimeError('Owned crash-fixture process group still has live members')
                time.sleep(.05)


def qualify(output: Path, rows: int = 10000) -> dict:
    require_native()
    if os.environ.get('ILC_ALLOW_NATIVE_DEMO') != '1':
        raise NativeUnavailable('Explicit disposable native database opt-in required')
    if os.name != 'posix':
        raise NativeUnavailable('Use a disposable Linux runner for this native harness')
    if output.exists():
        raise FileExistsError('Use a new qualification output; nothing is overwritten')
    from ilc.orchestration import accepted_sales_job
    import httpx

    output = output.resolve()
    output.mkdir(parents=True)
    output.chmod(0o700)
    work, evidence = output / 'work', output / 'evidence'
    work.mkdir(); evidence.mkdir()
    contract_path = ROOT / 'contracts/sales.json'
    contract = read_json(contract_path)
    template = read_json(ROOT / 'profiles/native.json')
    started = time.perf_counter()
    checks, seeds = {}, []

    def save(name, value):
        immutable_write(evidence / name, canonical(value))

    def prepare(name, revision=0, fault=None):
        source = work / ('source-' + name)
        manifest = create_fixture(source, contract, rows, revision=revision, fault=fault)
        profile = scenario_profile(template, output, name)
        path = work / ('profile-' + name + '.json')
        immutable_write(path, canonical(profile))
        seeds.append(seed_postgres(source, contract, profile))
        return source, manifest, profile, path

    source, manifest, profile, profile_path = prepare('base')
    root = work / 'runtime'
    with serving(source) as api:
        result = accepted_sales_job.execute_in_process(run_config={'ops': {
            'execute_accepted_batch': {'config': {
                'repo': str(ROOT), 'root': str(root), 'contract': str(contract_path),
                'profile': str(profile_path), 'fixture': str(source), 'api_url': api,
                'key': 'native-base', 'until': manifest['as_of']}}}})
        assert result.success
        accepted = result.output_for_node('execute_accepted_batch')
        pipe = Pipeline(ROOT, root, contract_path, profile_path)
        try:
            replay = pipe.execute('native-base', manifest['as_of'], source, api)
            assert replay['batch_id'] == accepted['batch_id'] and pipe.journal.state()['generation'] == 1
        finally:
            pipe.close()
    assert accepted['engine'] == 'native_spark' and accepted['observed_captured_rows'] == rows
    assert accepted['native_final_readback']['status'] == 'EXECUTED_AND_RECONCILED_FINAL_PATH'
    save('accepted-receipt.json', accepted)
    checks['V-P01-01'] = {'status': 'PASS_NATIVE', 'same_batch': True, 'generation': 1}
    checks['V-P01-04'] = {'status': 'PASS_NATIVE', 'checks': accepted['source_to_target'],
                         'captured_rows': rows, 'gold_fact_rows': accepted['gold_fact_rows'],
                         'final_delta_readback': accepted['native_final_readback']}
    tokens = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
    access = {'schema_version': 'ilc-access/1', 'principals': [
        {'name': 'native-all-sites', 'token_sha256': hashlib.sha256(tokens[0].encode()).hexdigest(),
         'sites': contract['sites'], 'permissions': ['report', 'catalog', 'evidence']},
        {'name': 'native-site-a', 'token_sha256': hashlib.sha256(tokens[1].encode()).hexdigest(),
         'sites': ['SITE_A'], 'permissions': ['report']}]}
    headers = [{'Authorization': 'Bearer ' + t} for t in tokens]
    consumer = Journal(root, profile, read_only=True)
    try:
        with serve_report(create_app(consumer, contract, access)) as url, httpx.Client(base_url=url, timeout=15, trust_env=False) as client:
            first = client.get('/api/report', headers=headers[0]); first.raise_for_status(); first = first.json()
            site = client.get('/api/report', headers=headers[1]); site.raise_for_status(); site = site.json()
            assert site['scope'] == ['SITE_A'] and all(x['site_id'] == 'SITE_A' for x in site['sites'])
            outcomes = {
                'unauthenticated': client.get('/api/report').status_code,
                'cross_site': client.get('/api/report?site=SITE_B', headers=headers[1]).status_code,
                'catalog_forbidden': client.get('/api/catalog', headers=headers[1]).status_code,
                'evidence_forbidden': client.get('/api/evidence', headers=headers[1]).status_code,
                'other_site_order': client.get('/api/orders/O000001', headers=headers[1]).status_code}
            assert outcomes == {'unauthenticated':401, 'cross_site':403, 'catalog_forbidden':403,
                                'evidence_forbidden':403, 'other_site_order':404}
            checks['V-P01-05'] = {'status':'PASS_NATIVE_HTTP_APPLICATION_RBAC', 'outcomes':outcomes,
                                 'limits':'Application roles only; no database or cloud RBAC qualification'}
            save('report-before-faults.json', first)
            for fault in ('duplicate_key', 'invalid_amount', 'schema_drift'):
                src, m, _, pp = prepare(fault, revision=1, fault=fault)
                p = Pipeline(ROOT, root, contract_path, pp)
                try:
                    with serving(src) as api:
                        rejected = p.execute('native-' + fault, m['as_of'], src, api)
                    assert rejected['status'] == 'REJECTED'
                finally:
                    p.close()
                current = client.get('/api/report', headers=headers[0]); current.raise_for_status(); current = current.json()
                assert current['dataset_batch_id'] == first['dataset_batch_id']
                assert current['status'] == 'DEGRADED' and current['totals'] == first['totals']
                save(fault + '-rejection.json', rejected)
                save(fault + '-report.json', current)
            checks['V-P01-03'] = {'status':'PASS_NATIVE', 'faults':['duplicate_key','invalid_amount','schema_drift'],
                                 'publication_blocked':True}
            checks['V-P01-06'] = {'status':'PASS_NATIVE_HTTP', 'last_accepted_preserved':True, 'degraded_exposed':True}
            src, m, _, pp = prepare('recovery', revision=1)
            p = Pipeline(ROOT, root, contract_path, pp)
            try:
                before = p.journal.state()
                with serving(src) as api:
                    command = [sys.executable, '-m', 'ilc.cli', '--repo', str(ROOT), 'run',
                        '--root',str(root), '--contract',str(contract_path), '--profile',str(pp),
                        '--fixture',str(src), '--api-url',api, '--key','native-crash', '--until',m['as_of'],
                        '--test-failpoint','after_target_commit', '--test-crash']
                    exit_code = _crash_child(command, {**os.environ, 'PYTHONPATH':str(ROOT/'src'),
                                                     'ILC_ENABLE_TEST_FAILPOINTS':'1'})
                assert exit_code == 73
                row = p.journal.find('native-crash')
                target = read_target(root, row['batch_id'])
                assert target is not None
                assert p.journal.state()['watermarks'] == before['watermarks']
                assert p.journal.state()['accepted_batch'] == before['accepted_batch']
                # Source HTTP stopped; PG stays up because it also hosts the journal.
                recovered = p.execute('native-crash', m['as_of'], src, 'http://127.0.0.1:1')
                assert recovered['target_reused'] and recovered['target_manifest_sha256'] == digest(target)
                assert recovered['generation'] == 2
                assert recovered['native_final_readback']['status'] == 'EXECUTED_AND_RECONCILED_FINAL_PATH'
                checks['V-P01-02'] = {'status':'PASS_NATIVE_REAL_PROCESS_EXIT', 'exit_code':exit_code,
                    'target_reused':True, 'http_source_offline':True, 'watermark_unchanged_before_resume':True,
                    'limits':'Crash after Spark.stop/target rename, not an in-flight Spark action; PG remains available'}
                save('recovery-receipt.json', recovered)
                save('recovery-timeline.json', p.journal.timeline(row['batch_id']))
                save('native-final-readback.json', read_json(batch_path(root,row['batch_id'])/'native_final_readback.json'))
            finally:
                p.close()
            report = client.get('/api/report', headers=headers[0]); report.raise_for_status(); report = report.json()
            assert report['dataset_batch_id'] == recovered['batch_id'] and report['generation'] == 2
            save('report-recovered.json', report)
            (evidence/'report.html').write_text(render_snapshot(report), encoding='utf-8')
        summary = {'project':'P01', 'profile':'native_spark/delta_spark/postgresql',
            'status':'EXECUTED_SYNTHETIC_NATIVE_CHECKS', 'application_checks':checks,
            'dagster_run_id':result.run_id, 'source_seeds':seeds,
            'runtime_versions':accepted['runtime_versions'], 'git':git_identity(ROOT),
            'source_code':code_manifest(ROOT), 'elapsed_seconds':round(time.perf_counter()-started,6),
            'limits':['Bounded single-host qualification, not distributed scale',
                      'Report API consumes JSON projections reconciled against final-path Delta, not Direct Lake',
                      'No PostgreSQL restore, OS security, live OpenMetadata, Fabric or Power BI qualification',
                      'New synthetic schemas are retained; no DROP/TRUNCATE/cleanup of shared data']}
        save('qualification-native.json',summary)
        return summary
    finally:
        consumer.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rows',type=int,default=10000)
    args=parser.parse_args()
    try:
        result=qualify(args.output,args.rows)
    except NativeUnavailable as exc:
        print(json.dumps({'status':'BLOCKED_NATIVE_NOT_EXECUTED','code':exc.code,'reason':str(exc)}))
        return 2
    print(json.dumps(result,indent=2));return 0

if __name__=='__main__':sys.exit(main())
