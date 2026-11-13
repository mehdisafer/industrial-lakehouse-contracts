"""Bounded process exclusion, artifact integrity, and incremental boundary cases."""
import os
import subprocess
import sys
from pathlib import Path
from decimal import Decimal
import pytest
from ilc.canonical import canonical, digest, read_json, pipeline_lock
from ilc.contracts import parse_rows
from ilc.errors import IntegrityError,InjectedFailure,ContractError
from ilc.storage import inventory,verify_manifest,batch_path,read_silver
from ilc.transform import build_silver,bounds_for
from ilc.fixtures import make_records,write_fixture,create_fixture
from ilc.source_api import serving


def test_nested_manifest_is_not_ignored(tmp_path):
    nested=tmp_path/'other';nested.mkdir();(nested/'manifest.json').write_text('{}')
    inv=inventory(tmp_path)
    assert 'other/manifest.json' in inv
    (nested/'manifest.json').write_text('{"changed":true}')
    with pytest.raises(IntegrityError):verify_manifest(tmp_path,{'files':inv})


def test_untracked_file_invalidates_inventory(tmp_path):
    (tmp_path/'one').write_text('one');manifest={'files':inventory(tmp_path)}
    (tmp_path/'extra').write_text('extra')
    with pytest.raises(IntegrityError):verify_manifest(tmp_path,manifest)


def test_symlink_artifact_is_not_followed(tmp_path):
    outside=tmp_path/'outside';outside.write_text('x')
    root=tmp_path/'root';root.mkdir()
    try:(root/'link').symlink_to(outside)
    except OSError:pytest.skip('Symlink creation unavailable to this test account')
    with pytest.raises((ContractError,IntegrityError)):verify_manifest(root,{'files':inventory(root)})


def test_other_process_cannot_acquire_active_lock(repo,tmp_path):
    root=tmp_path/'runtime';root.mkdir()
    code="""from pathlib import Path
import sys
from ilc.canonical import pipeline_lock
from ilc.errors import BusyError
try:
    with pipeline_lock(Path(sys.argv[1])): sys.exit(0)
except BusyError: sys.exit(19)
"""
    command=[sys.executable,'-c',code,str(root)]
    env={**os.environ,'PYTHONPATH':str(repo/'src')}
    with pipeline_lock(root):
        blocked=subprocess.run(command,env=env,capture_output=True,timeout=10)
        assert blocked.returncode==19,blocked.stderr.decode()
    acquired=subprocess.run(command,env=env,capture_output=True,timeout=10)
    assert acquired.returncode==0,acquired.stderr.decode()


def test_overlap_captures_late_update_and_upper_bound(pipeline,accepted,contract,tmp_path):
    records=make_records(contract,1000)
    row=records['order_lines'][0]
    # Newer than its previous event, but earlier than the old upper checkpoint.
    # The old fixture is at 10:00; introduce a new key with an older timestamp.
    late=dict(row);late['line_id']='5';late['updated_at']='2026-11-12T09:58:00Z'
    records['order_lines'].append(late)
    future=dict(row);future['line_id']='6';future['updated_at']='2026-11-12T12:00:00Z'
    records['order_lines'].append(future)
    root=tmp_path/'late';manifest=write_fixture(root,contract,records,as_of='2026-11-12T12:00:00Z')
    with serving(root) as url:r=pipeline.execute('late-update','2026-11-12T11:00:00Z',root,url)
    assert r['status']=='ACCEPTED'
    lines=read_silver(pipeline.root,r['batch_id'])['order_lines']
    assert len(lines)==381 and any(x['line_id']==5 for x in lines) and not any(x['line_id']==6 for x in lines)


def test_watermark_cannot_move_backwards(pipeline,accepted,source):
    root,m,url=source
    with pytest.raises(ValueError):pipeline.execute('backwards','2026-11-12T09:00:00Z',root,url)


def test_changed_rejection_projection_cannot_be_replayed(pipeline,contract,tmp_path):
    root=tmp_path/'bad';m=create_fixture(root,contract,1000,fault='invalid_amount')
    with serving(root) as url:r=pipeline.execute('rejected',m['as_of'],root,url)
    file=batch_path(pipeline.root,r['batch_id'])/'rejection.json'
    file.write_text('{"status":"ACCEPTED"}')
    with pytest.raises(IntegrityError):pipeline.execute('rejected',m['as_of'],root,'http://127.0.0.1:1')


def test_missing_rejection_projection_recovers_from_journal(pipeline,contract,tmp_path):
    root=tmp_path/'bad';m=create_fixture(root,contract,1000,fault='invalid_amount')
    with serving(root) as url:r=pipeline.execute('rejected',m['as_of'],root,url)
    file=batch_path(pipeline.root,r['batch_id'])/'rejection.json';file.unlink()
    replay=pipeline.execute('rejected',m['as_of'],root,'http://127.0.0.1:1')
    assert replay==r and read_json(file)==r


def test_claimed_source_cannot_differ_from_imported_code(repo,tmp_path):
    import shutil
    from ilc.canonical import code_manifest
    clone=tmp_path/'clone';shutil.copytree(repo/'src',clone/'src')
    shutil.copy2(repo/'pyproject.toml',clone/'pyproject.toml')
    (clone/'src/ilc/transform.py').write_text('# not the executed code\n')
    with pytest.raises(IntegrityError):code_manifest(clone)


def test_self_consistent_rewritten_base_is_not_accepted(pipeline,accepted,source):
    root,m,url=source;base=batch_path(pipeline.root,accepted['batch_id'])/'target'
    file=base/'gold/site_kpi.json';rows=read_json(file);rows[0]['ordered_amount']='0.00';file.write_bytes(canonical(rows))
    manifest=read_json(base/'manifest.json');manifest['files']=inventory(base)
    (base/'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(IntegrityError):pipeline.execute('not-on-rewritten-base',m['as_of'],root,url)
    assert pipeline.journal.state()['generation']==1


def test_recovered_candidate_is_compared_with_recomputed_gold(pipeline,source):
    root,m,url=source
    with pytest.raises(InjectedFailure):pipeline.execute('candidate',m['as_of'],root,url,'after_target_commit')
    row=pipeline.journal.find('candidate');base=batch_path(pipeline.root,row['batch_id'])/'target'
    file=base/'gold/site_kpi.json';rows=read_json(file);rows[0]['ordered_amount']='0.00';file.write_bytes(canonical(rows))
    manifest=read_json(base/'manifest.json');manifest['files']=inventory(base)
    (base/'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(IntegrityError):pipeline.execute('candidate',m['as_of'],root,url)
    assert pipeline.journal.state()['accepted_batch'] is None
