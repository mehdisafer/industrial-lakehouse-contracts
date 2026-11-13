"""Reproductions for the second repository review; no network or service use."""
import importlib.util
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('checker_hardening',
    os.environ.get('ILC_CHECKER_UNDER_TEST', str(ROOT / 'scripts/check_repository.py')))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA = 'a' * 40


@pytest.fixture
def repository(tmp_path):
    for name in gate.REQUIRED:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('# Guide\n', encoding='utf-8')
    (tmp_path / 'docs/proof.md').write_text(f'# Proof\nExecuted `{SHA}`.\n')
    record = {'schema_version': 'ilc-qualification-baselines/1', 'reviewed_on': '2026-11-13',
              'capabilities': [{'id': 'native', 'name': 'Native', 'state': 'accepted',
                               'revision': SHA, 'evidence': 'docs/proof.md', 'scope': 'Synthetic'}]}
    (tmp_path / gate.REGISTER).write_text(json.dumps(record))
    (tmp_path / gate.STATUS_PAGE).write_text(gate.render_status(record))
    return tmp_path, list(gate.REQUIRED) + ['docs/proof.md']


def checked(repository, text=None):
    root, files = repository
    if text is not None:
        (root / 'README.md').write_text('# Project\n' + text + '\n', encoding='utf-8')
    return gate.audit(root, files)


@pytest.mark.parametrize('label', ['`runbook`', '``runbook``', '**`runbook`**'])
def test_code_label_reference_cannot_hide_missing_destination(repository, label):
    assert checked(repository, f'[{label}][run]\n\n[run]: missing.md')['status'] == 'FAIL'


def test_code_label_reference_is_counted_when_valid(repository):
    old = checked(repository)['local_links_checked']
    r = checked(repository, '[`runbook`][run]\n\n[run]: docs/RUNBOOK.md')
    assert r['status'] == 'PASS' and r['local_links_checked'] == old + 1


def test_collapsed_code_label_reference(repository):
    r = checked(repository, '[`runbook`][]\n\n[`runbook`]: docs/RUNBOOK.md')
    assert r['status'] == 'PASS'


def test_reference_labels_normalise_internal_whitespace(repository):
    r = checked(repository, '[Guide][My   Runbook]\n\n[my runbook]: docs/RUNBOOK.md')
    assert r['status'] == 'PASS'


def test_double_backtick_example_with_inner_backtick_is_ignored(repository):
    r = checked(repository, '``Literal ` and [reference][missing]``')
    assert r['status'] == 'PASS'


def test_escaped_opening_bracket_does_not_form_a_link(repository):
    assert checked(repository, r'\[literal](missing.md)')['status'] == 'PASS'


def test_balanced_parentheses_in_destination(repository):
    root, files = repository
    (root / 'docs/guide(v2).md').write_text('# Guide\n')
    files.append('docs/guide(v2).md')
    assert checked(repository, '[Guide](docs/guide(v2).md "Guide")')['status'] == 'PASS'


def test_angle_destination_and_title(repository):
    root, files = repository
    (root / 'docs/guide v2.md').write_text('# Guide\n')
    files.append('docs/guide v2.md')
    assert checked(repository, '[Guide](<docs/guide v2.md> "Guide")')['status'] == 'PASS'


@pytest.mark.parametrize('url', ['https:///missing-host', 'https:', 'http://',
    'https://example.invalid:invalid/path', 'https://example.invalid:70000',
    'https://example.invalid:0', 'https://exam%70le.invalid/x', r'https://host\other/x'])
def test_malformed_http_link_rejected(repository, url):
    assert checked(repository, f'[Guide]({url})')['status'] == 'FAIL'


@pytest.mark.parametrize('url', ['https://example.invalid/x?q=a#b',
    'http://127.0.0.1:8585/api', 'http://[::1]:8585/api', 'mailto:maintainer@example.invalid'])
def test_valid_external_link_never_requires_network(repository, url):
    assert checked(repository, f'[Guide]({url})')['status'] == 'PASS'


@pytest.mark.parametrize('text', [
    '[private](https://someone:SYNTHETIC_PASSWORD@example.invalid/x)',
    '[private](https://example.invalid:SYNTHETIC_PASSWORD/x)',
    '[private](javascript:SYNTHETIC_PASSWORD)',
    '[private](missing.md?token=SYNTHETIC_PASSWORD)',
    '[private][SYNTHETIC_PASSWORD]',
])
def test_document_payload_not_reflected_in_diagnostics(repository, text):
    r = checked(repository, text)
    assert r['status'] == 'FAIL'
    assert 'SYNTHETIC_PASSWORD' not in json.dumps(r)
    assert any('README.md:2' in e for e in r['errors'])


@pytest.mark.parametrize('name', ['data.sqlite', 'data.sqlite3', 'data.sqlite-wal',
    'data.sqlite3-shm', 'data.db', 'data.db-journal', 'id_rsa', 'id_ed25519',
    'x.egg-info/PKG-INFO', '.ruff_cache/entry', 'htmlcov/index.html', '.coverage', 'test-results/junit.xml'])
def test_force_added_runtime_files_fail(repository, name):
    root, files = repository
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b'synthetic fixture')
    files.append(name)
    assert checked(repository)['status'] == 'FAIL'


@pytest.mark.parametrize('text', ['b' + SHA, SHA + 'c', '0x' + SHA + 'f'])
def test_revision_must_be_a_complete_hash_token(repository, text):
    (repository[0] / 'docs/proof.md').write_text('# Proof\n' + text + '\n')
    assert checked(repository)['status'] == 'FAIL'


def test_generated_anchor_does_not_collide_with_explicit_suffix(repository):
    (repository[0] / 'docs/RUNBOOK.md').write_text('# A\n# A\n# A-1\n# A\n')
    assert checked(repository, '[Guide](docs/RUNBOOK.md#a-1-1)\n[Next](docs/RUNBOOK.md#a-2)')['status'] == 'PASS'


def test_wrong_register_state_type_has_controlled_error(repository):
    p = repository[0] / gate.REGISTER
    obj = json.loads(p.read_text()); obj['capabilities'][0]['state'] = []
    p.write_text(json.dumps(obj))
    with pytest.raises(gate.RepositoryError):
        gate.load_register(repository[0])


def test_oversized_register_is_rejected(repository):
    p = repository[0] / gate.REGISTER
    p.write_text(p.read_text() + ' ' * (65 * 1024))
    assert checked(repository)['status'] == 'FAIL'


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='FIFO requires a POSIX filesystem')
def test_fifo_register_is_rejected_without_opening(repository):
    p = repository[0] / gate.REGISTER
    p.unlink(); os.mkfifo(p)
    assert checked(repository)['status'] == 'FAIL'


def test_encoded_evidence_path_is_valid_markdown(repository):
    root, files = repository
    p = root / 'docs/proof (v2).md'
    p.write_text(f'# Proof\n{SHA}\n'); files.append('docs/proof (v2).md')
    obj = json.loads((root / gate.REGISTER).read_text())
    obj['capabilities'][0]['evidence'] = 'docs/proof (v2).md'
    (root / gate.REGISTER).write_text(json.dumps(obj))
    (root / gate.STATUS_PAGE).write_text(gate.render_status(obj))
    assert checked(repository)['status'] == 'PASS'


def test_crlf_status_is_equivalent(repository):
    p = repository[0] / gate.STATUS_PAGE
    p.write_bytes(p.read_bytes().replace(b'\n', b'\r\n'))
    assert checked(repository)['status'] == 'PASS'
