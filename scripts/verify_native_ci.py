"""Fail a native CI job unless its executed tests and semantic receipts agree.

This verifier is not a replacement for independent review of the artifacts.
It rejects skipped native tests, reference-only receipts and wrong source SHAs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(evidence: Path, junit: Path, expected_sha: str, repo: Path = ROOT) -> dict:
    need(bool(re.fullmatch('[0-9a-f]{40}', expected_sha)), 'Invalid expected commit')
    load = lambda name: json.loads((evidence / name).read_text(encoding='utf-8'))
    summary = load('qualification-native.json')
    base = load('accepted-receipt.json')
    recovery = load('recovery-receipt.json')
    before = load('report-before-faults.json')
    after = load('report-recovered.json')
    need(summary.get('profile') == 'native_spark/delta_spark/postgresql', 'Not a native profile')
    need(summary.get('status') == 'EXECUTED_SYNTHETIC_NATIVE_CHECKS', 'Qualification not completed')
    need(bool(summary.get('dagster_run_id')), 'No Dagster run')
    for document in (summary, base, recovery):
        identity = document.get('git', {})
        need(identity.get('commit') == expected_sha, 'Receipt has a different source commit')
        need(identity.get('worktree_dirty') is False, 'Receipt has a dirty/unknown worktree')
    source = summary.get('source_code', {})
    need(bool(source) and 'pyproject.toml' in source, 'No source manifest')
    for name, expected in source.items():
        path = (repo / name).resolve()
        need(path.is_relative_to(repo.resolve()) and not Path(name).is_absolute(), 'Invalid source path')
        need(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
             'Source fingerprint mismatch: ' + name)
    checks = summary.get('application_checks', {})
    ids = {f'V-P01-{i:02}' for i in range(1, 7)}
    need(set(checks) == ids, 'Six native acceptance scenarios are required')
    need(all(c.get('status', '').startswith('PASS_NATIVE') for c in checks.values()),
         'Missing native acceptance result')
    need(checks['V-P01-01'].get('same_batch') is True, 'Replay not demonstrated')
    crash = checks['V-P01-02']
    for key in ('target_reused', 'http_source_offline', 'watermark_unchanged_before_resume'):
        need(crash.get(key) is True, 'Recovery evidence missing: ' + key)
    need(crash.get('exit_code') == 73, 'Wrong crash failpoint outcome')
    need(checks['V-P01-03'].get('publication_blocked') is True, 'Invalid data published')
    need(checks['V-P01-06'].get('last_accepted_preserved') is True and
         checks['V-P01-06'].get('degraded_exposed') is True, 'Reporting guard not demonstrated')
    need(checks['V-P01-05'].get('outcomes') == {
        'unauthenticated':401, 'cross_site':403, 'catalog_forbidden':403,
        'evidence_forbidden':403, 'other_site_order':404}, 'HTTP role checks incomplete')
    for receipt, proof_name in ((base, 'accepted-final-readback.json'),
                                (recovery, 'native-final-readback.json')):
        need(receipt.get('status') == 'ACCEPTED' and receipt.get('engine') == 'native_spark',
             'Receipt is not native acceptance')
        need(receipt.get('observed_captured_rows') == 10000 and receipt.get('gold_fact_rows') == 3980,
             'Wrong fixture cardinality')
        need(all(receipt.get('source_to_target', {}).get(k) is True for k in
                 ('line_counts_equal','keys_equal','amounts_equal')), 'Source-target mismatch')
        final = receipt.get('native_final_readback', {})
        need(final.get('status') == 'EXECUTED_AND_RECONCILED_FINAL_PATH' and
             final.get('tables_verified') == 10, 'Final-path Delta tables not all verified')
        proof = load(proof_name)
        raw = (json.dumps(proof,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False)+'\n').encode()
        need(hashlib.sha256(raw).hexdigest()==final.get('proof_sha256'), 'Readback proof digest mismatch')
        need(proof.get('batch_id')==receipt.get('batch_id') and
             proof.get('target_manifest_sha256')==receipt.get('target_manifest_sha256'),
             'Readback proof bound to another batch or target')
        tables=proof.get('tables',{})
        need(len(tables)==10 and all(t.get('version')==0 for t in tables.values()), 'Unexpected Delta table version')
    versions = summary.get('runtime_versions', {})
    for package, expected in {'pyspark':'4.0.1','delta-spark':'4.0.1','dagster':'1.11.16','psycopg':'3.2.13'}.items():
        need(versions.get(package) == expected, 'Unexpected runtime: ' + package)
    seeds=summary.get('source_seeds', [])
    need(len(seeds)==5 and all(160000 <= s.get('server_version',0) < 170000 for s in seeds),
         'Five PostgreSQL 16 source fixtures required')
    need(before.get('generation')==1 and after.get('generation')==2 and
         after.get('dataset_batch_id')==recovery.get('batch_id'), 'Report did not consume recovered batch')
    xml=ET.parse(junit).getroot()
    cases=list(xml.iter('testcase'))
    need(bool(cases) and any(c.get('name')=='test_real_native_qualification' for c in cases),
         'Native pytest did not run')
    need(not any(c.find(tag) is not None for c in cases for tag in ('failure','error','skipped')),
         'Native tests failed or were skipped')
    return {'schema_version':'ilc-native-ci-verification/1','status':'EVIDENCE_GATE_PASSED',
            'source_sha':expected_sha,'tests_executed':len(cases),'native_scenarios':sorted(checks),
            'runtime_versions':versions,'dagster_run_id':summary['dagster_run_id'],
            'captured_rows_per_clean_batch':10000,'gold_fact_rows':3980,
            'limits':summary.get('limits',[]),
            'receipt_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(evidence.glob('*.json'))},
            'junit_sha256':hashlib.sha256(junit.read_bytes()).hexdigest()}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--junit',type=Path,required=True)
    parser.add_argument('--expected-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    need(actual==args.expected_sha, 'Checkout differs from expected revision')
    result=validate(args.evidence,args.junit,args.expected_sha)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
