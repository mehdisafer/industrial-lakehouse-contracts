"""Collect reference test identity and verify original JUnit plus run evidence.

The collect command imports pytest; verification uses the standard library only.
No network, service startup, token access or automatic retry is performed here.
Success is a source-bound consistency result, not a signed attestation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NATIVE_TEST = ('tests.test_native_gate', 'test_real_native_qualification')
MAX_BYTES = 8 * 1024 * 1024


class EvidenceError(ValueError):
    """A required invariant is absent or inconsistent."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def content(path: Path) -> bytes:
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES,
         'Evidence input must be a bounded regular file')
    current = path.parent
    while current != current.parent:
        need(not current.is_symlink(), 'Evidence input has a symlink parent')
        current = current.parent
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    need(len(raw) <= MAX_BYTES, 'Evidence byte budget exceeded')
    return raw


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def object_pairs(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'Duplicate JSON key')
        out[key] = value
    return out


def read_json(path: Path) -> dict:
    def invalid_constant(_):
        raise EvidenceError('Non-finite JSON value')
    value = json.loads(content(path).decode('utf-8'), object_pairs_hook=object_pairs,
                       parse_constant=invalid_constant)
    need(isinstance(value, dict), 'Evidence document must be an object')
    return value


def source_path(root: Path, name: str) -> Path:
    need(isinstance(name, str) and bool(name), 'Source path must be text')
    path = PurePosixPath(name)
    need(not path.is_absolute() and '..' not in path.parts and '\\' not in name,
         'Invalid source path')
    result = root / path
    need(result.resolve().is_relative_to(root.resolve()), 'Source path escapes checkout')
    return result


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(['git', *args], cwd=root, capture_output=True, timeout=15)
    need(proc.returncode == 0, 'Git identity check failed')
    return proc.stdout.decode('utf-8').strip()


def checkout(root: Path, expected_sha: str) -> str:
    need(isinstance(expected_sha, str) and re.fullmatch(r'[0-9a-f]{40}', expected_sha) is not None,
         'An exact expected source SHA is required')
    need(git(root, 'rev-parse', 'HEAD') == expected_sha, 'Unexpected checkout revision')
    need(not git(root, 'status', '--porcelain'), 'Checkout has uncommitted or untracked changes')
    return git(root, 'rev-parse', 'HEAD^{tree}')


def junit_key(nodeid: str) -> tuple[str, str]:
    # Pytest's default JUnit names: parameters belong to the final name, not class.
    address, bracket, params = nodeid.partition('[')
    components = address.split('::')
    need(len(components) >= 2 and components[0].endswith('.py'), 'Unsupported collected test address')
    components[0] = components[0][:-3].replace('/', '.')
    components[-1] += bracket + params
    return '.'.join(components[:-1]), components[-1]


def collect(root: Path, expected_sha: str) -> dict:
    tree = checkout(root, expected_sha)
    need(os.environ.get('ILC_NATIVE_TESTS') != '1', 'Native execution must not be enabled in the reference job')
    import pytest

    class Collector:
        items: list = []

        def pytest_collection_finish(self, session):
            self.items = list(session.items)

    collector = Collector()
    previous = Path.cwd()
    try:
        os.chdir(root)
        exit_code = pytest.main(['--collect-only', '-q', '-p', 'no:cacheprovider', 'tests'], plugins=[collector])
    finally:
        os.chdir(previous)
    need(exit_code == 0 and bool(collector.items), 'Reference collection failed or produced no tests')
    cases = []
    for item in collector.items:
        classname, name = junit_key(item.nodeid)
        native = item.get_closest_marker('native') is not None
        need(not native or (classname, name) == NATIVE_TEST, 'Unreviewed native test in reference inventory')
        cases.append({'nodeid': item.nodeid, 'classname': classname, 'name': name, 'native': native})
    need(len({(c['classname'], c['name']) for c in cases}) == len(cases), 'Ambiguous collected JUnit identities')
    files = sorted({item.nodeid.partition('::')[0] for item in collector.items})
    checkout(root, expected_sha)
    return {'schema_version': 'ilc-reference-collection/1', 'source_sha': expected_sha,
            'source_tree': tree, 'tests': sorted(cases, key=lambda c: c['nodeid']),
            'test_file_sha256': {n: sha256(content(source_path(root, n))) for n in files}}


def inspect_junit(folder: Path, inventory: dict) -> dict:
    need(folder.is_dir() and not folder.is_symlink(), 'Original JUnit directory is missing')
    paths = sorted(folder.rglob('*.xml'))
    need(1 <= len(paths) <= 32, 'Expected a bounded, nonempty original JUnit inventory')
    expected = inventory.get('tests')
    need(isinstance(expected, list) and bool(expected), 'Collected tests are missing')
    expected_keys = Counter((c['classname'], c['name']) for c in expected)
    need(all(n == 1 for n in expected_keys.values()), 'Duplicate collected test identity')
    observed = Counter()
    skipped = []
    allowed_tags = {'testsuites', 'testsuite', 'testcase', 'properties', 'property',
                    'system-out', 'system-err', 'failure', 'error', 'skipped'}
    for path in paths:
        raw = content(path)
        text = raw.decode('utf-8')
        need(re.search(r'<!\s*(?:DOCTYPE|ENTITY)', text, re.I) is None, 'DTD/entity declarations are not admitted')
        xml = ET.fromstring(text)
        need(xml.tag in {'testsuites', 'testsuite'}, 'Unexpected JUnit root')
        need(all(e.tag in allowed_tags for e in xml.iter()), 'Unexpected JUnit element; use the original XML')
        suites = [xml] if xml.tag == 'testsuite' else list(xml)
        need(bool(suites) and all(s.tag == 'testsuite' for s in suites), 'Unexpected JUnit suite layout')
        for suite in suites:
            need(not suite.findall('testsuite'), 'Nested suites are not supported by this pytest gate')
            cases = suite.findall('testcase')
            need(int(suite.get('tests', '-1')) == len(cases), 'JUnit test counter disagrees with testcase elements')
            for tag, attr in [('failure', 'failures'), ('error', 'errors'), ('skipped', 'skipped')]:
                count = sum(len(c.findall(tag)) for c in cases)
                need(int(suite.get(attr, '-1')) == count, 'JUnit outcome counters are inconsistent')
            for case in cases:
                key = (case.get('classname'), case.get('name'))
                need(all(isinstance(v, str) and bool(v) for v in key), 'Missing testcase identity')
                observed[key] += 1
                need(not case.findall('failure') and not case.findall('error'), 'Reference test failed or errored')
                skip = case.findall('skipped')
                need(len(skip) <= 1, 'Repeated skip outcome')
                if skip:
                    need(key == NATIVE_TEST and bool(skip[0].get('message')), 'Unapproved or unexplained reference skip')
                    skipped.append({'classname': key[0], 'name': key[1]})
    need(observed == expected_keys, 'Executed JUnit cases differ from the complete collected suite')
    need(len(skipped) == 1 and expected_keys[NATIVE_TEST] == 1, 'Reference run must explicitly skip its one native test')
    total = sum(observed.values())
    need(total > len(skipped), 'Reference evidence contains no passing tests')
    return {'collected': len(expected), 'executed': total, 'passed': total - len(skipped),
            'skipped': len(skipped), 'errors': 0, 'failures': 0, 'allowed_skips': skipped,
            'original_xml_sha256': {p.relative_to(folder).as_posix(): sha256(content(p)) for p in paths}}


def assert_identity(document: dict, expected_sha: str) -> None:
    need(document.get('git') == {'commit': expected_sha, 'worktree_dirty': False},
         'Evidence does not identify the clean expected checkout')


def inspect_reference(root: Path, expected_sha: str, reference: Path, recovery: Path) -> dict:
    summary = read_json(reference / 'qualification.json')
    restored = read_json(recovery / 'qualification.json')
    for value in (summary, restored):
        assert_identity(value, expected_sha)
        manifest = value.get('source_code')
        names = sorted(p.relative_to(root).as_posix() for p in (root / 'src/ilc').glob('*.py')) + ['pyproject.toml']
        need(bool(names[:-1]) and isinstance(manifest, dict) and set(manifest) == set(names),
             'Application source manifest is incomplete')
        need(all(manifest[n] == sha256(content(source_path(root, n))) for n in names), 'Application bytes differ from the receipt')
    need(summary.get('qualified_profile') == 'reference_sqlite/reference_json', 'Unexpected reference profile')
    need(summary.get('actual_captured_rows_per_clean_base_batch') == 10000, 'Unexpected reference input volume')
    for key in ('native_postgresql_spark_delta_dagster', 'openmetadata', 'fabric', 'power_bi', 'big_data_scale'):
        need(summary.get(key) == 'NOT_RUN', 'Reference receipt overclaims an unexecuted integration')
    checks = summary.get('application_checks', {})
    need(set(checks) == {f'V-P01-{i:02}' for i in range(1, 7)}, 'Missing reference scenario')
    need(all(c.get('status', '').startswith('PASS_REFERENCE') for c in checks.values()), 'Reference scenario failed')
    need(checks['V-P01-01'].get('same_batch') is True and checks['V-P01-01'].get('generation_after_replay') == 1,
         'Accepted replay is not demonstrated')
    crash = checks['V-P01-02']
    need(crash.get('child_exit') == 73 and crash.get('accepted_generation') == 2, 'Unexpected recovery outcome')
    need(all(crash.get(k) is True for k in ('target_exists_before_accept', 'watermark_unchanged_before_resume',
             'resume_with_source_offline', 'candidate_reused')), 'Recovery invariants are incomplete')
    need(checks['V-P01-03'].get('publication_blocked') is True, 'Bad-data publication is not blocked')
    need(checks['V-P01-05'].get('outcomes') == {'unauthenticated': 401, 'wrong_token': 401, 'cross_site': 403,
             'global_evidence': 403, 'global_catalog': 403, 'other_site_order': 404}, 'Application role outcomes differ')
    need(all(checks['V-P01-06'].get(k) is True for k in ('last_accepted_preserved', 'degraded_exposed')),
         'Reporting protection is incomplete')
    receipts = []
    reports = []
    for receipt_name, report_name, generation in [('baseline-receipt.json', 'report-initial.json', 1),
                                                  ('recovery-receipt.json', 'report-recovered.json', 2)]:
        receipt = read_json(reference / receipt_name)
        report = read_json(reference / report_name)
        assert_identity(receipt, expected_sha)
        need(receipt.get('status') == 'ACCEPTED' and receipt.get('engine') == 'reference_sqlite'
             and receipt.get('target') == 'reference_json', 'Receipt is not accepted reference data')
        need(receipt.get('observed_captured_rows') == 10000 and receipt.get('gold_fact_rows') == 3980,
             'Reference cardinalities disagree')
        recon = receipt.get('source_to_target', {})
        need(all(recon.get(k) is True for k in ('line_counts_equal', 'keys_equal', 'amounts_equal')),
             'Reference reconciliation is incomplete')
        need(recon.get('source_amount') == recon.get('gold_amount') == report['totals']['ordered_amount'],
             'Source, Gold and reporting amounts disagree')
        need(receipt.get('generation') == report.get('generation') == generation
             and report.get('dataset_batch_id') == receipt.get('batch_id'), 'Report generation/batch differs')
        need(report['lineage']['target_manifest_sha256'] == receipt['target_manifest_sha256'], 'Reporting lineage differs')
        for measure in report['totals']:
            need(sum(Decimal(str(s[measure])) for s in report['sites']) == Decimal(str(report['totals'][measure])),
                 'Site totals do not reconcile')
        receipts.append(receipt); reports.append(report)
    need(receipts[1].get('target_reused') is True and receipts[1].get('invocation') == 'RESUMED', 'Target reuse absent')
    amounts = [Decimal(r['source_to_target']['gold_amount']) for r in receipts]
    need(amounts == [Decimal('8857766.18'), Decimal('8857786.18')], 'Unexpected fixture amount revision')
    for fault in ('duplicate_key', 'invalid_amount', 'schema_drift'):
        rejection = read_json(reference / ('rejected-' + fault + '.json'))
        report = read_json(reference / ('report-after-' + fault + '.json'))
        need(rejection.get('status') == 'REJECTED' and rejection.get('dataset_promoted') is False
             and rejection.get('watermark_advanced') is False, 'Rejected candidate was promoted or incomplete')
        need(report.get('dataset_batch_id') == receipts[0]['batch_id'] and report.get('status') == 'DEGRADED'
             and report.get('totals') == reports[0]['totals'], 'Rejection changed the accepted report')
    extension = summary.get('metadata_extension', {})
    need(extension.get('status') == 'PASS_REFERENCE' and extension.get('new_rows') == 3
         and extension.get('report_generation') == 3 and extension.get('engine_code_unchanged') is True
         and extension.get('consumer_catalog_observed') is True, 'Metadata-only extension is incomplete')
    need(restored.get('status') == 'REFERENCE_RECOVERY_AND_PROTOCOL_CHECKS_EXECUTED', 'Restore harness not completed')
    need(restored.get('source_rows') == 10000 and restored.get('gold_rows') == 3980, 'Restore fixture differs')
    restore = restored.get('reference_restore', {})
    need(all(restore.get(k) is True for k in ('sqlite_backup_api_used', 'original_runtime_retained', 'same_path_identity',
        'totals_equal', 'report_reread_over_real_http', 'unauthenticated_refused', 'accepted_replay_http_source_offline',
        'publication_state_equal', 'governance_outbox_restored')), 'Restore proof is incomplete')
    need(restore.get('catalog_replay_additional_writes') == 0, 'Restored catalogue replay mutated the peer')
    protocol = restored.get('openmetadata', {})
    need(protocol.get('scope') == 'PROTOCOL_EMULATOR_NOT_OPENMETADATA_PRODUCT'
         and protocol.get('server_product_qualified') is False and protocol.get('server_rbac_qualified') is False,
         'Protocol emulator is presented as a real product')
    need(protocol.get('database_create_requests_after_lost_response') == 1, 'Unknown catalogue effect was duplicated')
    for key in ('native_profile', 'fabric', 'power_bi'):
        need(restored.get(key) == 'NOT_RUN', 'Restore receipt overclaims a provider')
    backup = read_json(recovery / 'backup-receipt.json')
    restore_receipt = read_json(recovery / 'restore-receipt.json')
    acceptance = read_json(recovery / 'acceptance.json')
    replay = read_json(recovery / 'replay-after-restore.json')
    before = read_json(recovery / 'report-before-restore.json')
    after = read_json(recovery / 'report-after-restore.json')
    assert_identity(acceptance, expected_sha)
    assert_identity(replay, expected_sha)
    archive_hash = backup.get('archive_sha256')
    need(backup.get('status') == 'REFERENCE_BACKUP_WRITTEN'
         and restore_receipt.get('status') == 'REFERENCE_RESTORE_VERIFIED'
         and backup.get('native_backup_qualified') is False
         and restore_receipt.get('native_backup_qualified') is False, 'Wrong backup/restore proof scope')
    need(isinstance(archive_hash, str) and re.fullmatch(r'[0-9a-f]{64}', archive_hash) is not None
         and archive_hash == restore.get('archive_sha256') == restore_receipt.get('archive_sha256'),
         'Backup and restore identify different archives')
    need(sha256(content(recovery.parent / 'work/reference-snapshot.zip')) == archive_hash,
         'Retained backup bytes differ from the restore receipt')
    batch = acceptance.get('batch_id')
    need(acceptance.get('status') == replay.get('status') == 'ACCEPTED'
         and acceptance.get('engine') == 'reference_sqlite' and batch == replay.get('batch_id')
         and batch == before.get('dataset_batch_id') == after.get('dataset_batch_id')
         and batch == restore_receipt.get('accepted_batch'), 'Restore did not preserve the accepted batch')
    need(acceptance.get('generation') == replay.get('generation') == before.get('generation')
         == after.get('generation') == backup.get('generation') == restore_receipt.get('generation') == 1,
         'Restore/replay changed the accepted generation')
    need(before.get('totals') == after.get('totals') and before.get('totals') is not None
         and replay.get('invocation') == 'REPLAY_OF_ACCEPTED_BATCH', 'Restored consumer/replay differs')
    return {'scenarios': sorted(checks), 'rows_per_clean_batch': 10000, 'gold_facts': 3980,
            'ordered_amount_eur': [str(n) for n in amounts], 'recovery_generation': 2,
            'metadata_extension_generation': 3, 'same_path_reference_restore': True,
            'catalogue_peer': 'PROTOCOL_EMULATOR_NOT_OPENMETADATA_PRODUCT'}


def verify(root: Path, expected_sha: str) -> dict:
    tree = checkout(root, expected_sha)
    inventory_path = root / 'artifacts/reference/test-inventory.json'
    inventory = read_json(inventory_path)
    need(inventory.get('schema_version') == 'ilc-reference-collection/1'
         and inventory.get('source_sha') == expected_sha and inventory.get('source_tree') == tree,
         'Test collection belongs to another checkout')
    hashes = inventory.get('test_file_sha256')
    need(isinstance(hashes, dict) and bool(hashes), 'Missing test source fingerprints')
    need(all(h == sha256(content(source_path(root, n))) for n, h in hashes.items()), 'Test bytes changed after collection')
    junit = inspect_junit(root / 'test-results', inventory)
    repository = read_json(root / 'artifacts/repository/check.json')
    need(repository.get('status') == 'PASS' and repository.get('errors') == []
         and repository.get('tracked_files', 0) > 0, 'Repository check did not pass')
    disclosure = read_json(root / 'artifacts/publication/summary.json')
    need(disclosure.get('source_sha') == expected_sha
         and disclosure.get('status') == 'RULE_BASED_HISTORY_SCAN_NO_FINDINGS'
         and disclosure.get('finding_count') == 0 and disclosure.get('findings') == []
         and disclosure.get('scanner', {}).get('positive_control_detected') is True,
         'History disclosure evidence is incomplete or failed')
    reference = root / '.runtime/circleci-reference/evidence'
    recovery = root / '.runtime/circleci-recovery/evidence'
    outcomes = inspect_reference(root, expected_sha, reference, recovery)
    paths = [inventory_path, root / 'artifacts/repository/check.json', root / 'artifacts/publication/summary.json']
    for folder in (reference, recovery):
        paths += sorted(folder.glob('*.json'))
    checkout(root, expected_sha)
    return {'schema_version': 'ilc-reference-ci-verification/1', 'status': 'REFERENCE_EVIDENCE_CONSISTENT',
            'source_sha': expected_sha, 'source_tree': tree, 'test_results': junit,
            'reference': outcomes, 'repository_check': 'PASS', 'history_scan': 'NO_FINDINGS',
            'input_sha256': {p.relative_to(root).as_posix(): sha256(content(p)) for p in paths},
            'limits': ['Reference profile and named catalogue emulator only; no new native or live catalogue qualification',
                       'Original XML hashes are observed in this job; no signature or independent download is asserted',
                       'Rule-based disclosure check, not exhaustive security certification'],
            'billing_credits_observed': None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect', 'verify'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--expected-sha', default=os.environ.get('CIRCLE_SHA1', ''))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        need(not args.output.exists() and not args.output.is_symlink(), 'Output already exists; no overwrite')
        result = collect(args.root.resolve(), args.expected_sha) if args.command == 'collect' else verify(args.root.resolve(), args.expected_sha)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            output.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
        print(json.dumps(result if args.command == 'verify' else
                         {'status': 'COLLECTION_RECORDED', 'tests': len(result['tests']), 'source_sha': args.expected_sha}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, InvalidOperation, ET.ParseError, subprocess.SubprocessError) as exc:
        message = str(exc) if isinstance(exc, EvidenceError) else 'Unable to validate reference evidence (' + type(exc).__name__ + ')'
        print(json.dumps({'status': 'ERROR', 'error': message}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
