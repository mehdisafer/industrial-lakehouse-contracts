"""Real files/SQLite and restore consumer checks; NOT PostgreSQL backup tests."""
import json
from pathlib import Path
import zipfile

import pytest
from ilc.backup import backup_reference,restore_reference,BackupError
from ilc.canonical import file_digest,canonical
from ilc.errors import IntegrityError,BusyError
from ilc.journal import Journal
from ilc.pipeline import Pipeline
from ilc.reporting import ReportReader


def test_restore_same_path_rereads_report_and_replays_without_sources(pipeline,accepted,source,repo,profile,tmp_path):
    report=ReportReader(pipeline.journal).report(['SITE_A'])
    state=pipeline.journal.state();runtime=pipeline.root
    archive=tmp_path/'snapshot.zip';backup=backup_reference(pipeline.journal,archive)
    pipeline.close()
    offline=runtime.with_name(runtime.name+'-preserved-offline')
    runtime.rename(offline)  # Preserve original bytes; do not delete the old runtime.
    restored=restore_reference(archive,runtime,backup['archive_sha256'])
    p=Pipeline(repo,runtime,repo/'contracts/sales.json',repo/'profiles/reference.json')
    try:
        r=ReportReader(p.journal).report(['SITE_A'])
        assert r['totals']==report['totals'] and r['dataset_batch_id']==report['dataset_batch_id']
        assert p.journal.state()==state
        folder,m,_=source
        replay=p.execute('accepted-baseline',m['as_of'],folder,'http://127.0.0.1:1')
        assert replay['invocation']=='REPLAY_OF_ACCEPTED_BATCH'
        assert restored['generation']==1 and offline.exists()
    finally:p.close()


def test_native_journal_backup_is_never_faked(pipeline,tmp_path):
    pipeline.journal.backend='postgresql'
    with pytest.raises(BackupError):backup_reference(pipeline.journal,tmp_path/'x.zip')


def test_missing_acceptance_backup_refused(pipeline,tmp_path):
    with pytest.raises(BackupError):backup_reference(pipeline.journal,tmp_path/'x.zip')


def test_backup_refuses_inplace_destination_or_existing_archive(pipeline,accepted,tmp_path):
    with pytest.raises(BackupError):backup_reference(pipeline.journal,pipeline.root/'x.zip')
    path=tmp_path/'x.zip';path.write_bytes(b'preserve')
    with pytest.raises(BackupError):backup_reference(pipeline.journal,path)
    assert path.read_bytes()==b'preserve'


def test_backup_holds_writer_exclusion(pipeline,accepted,tmp_path):
    with pipeline.journal.lock():
        with pytest.raises(BusyError):backup_reference(pipeline.journal,tmp_path/'x.zip')


def test_access_policy_and_source_fixtures_are_not_backed_up(pipeline,accepted,tmp_path):
    (pipeline.root/'access-policy.json').write_text('VERY-SENSITIVE-TEST-TOKEN')
    archive=tmp_path/'x.zip';backup_reference(pipeline.journal,archive)
    with zipfile.ZipFile(archive) as z:
        assert 'access-policy.json' not in z.namelist()
        assert all(b'VERY-SENSITIVE' not in z.read(n) for n in z.namelist())
        assert 'journal.sqlite-wal' not in z.namelist()


def test_restore_refuses_existing_destination(pipeline,accepted,tmp_path):
    a=tmp_path/'x.zip';r=backup_reference(pipeline.journal,a)
    with pytest.raises(BackupError):restore_reference(a,pipeline.root,r['archive_sha256'])


def test_changed_root_requires_migration(pipeline,accepted,tmp_path):
    a=tmp_path/'x.zip';r=backup_reference(pipeline.journal,a)
    with pytest.raises(BackupError,match='migration'):restore_reference(a,tmp_path/'new-root',r['archive_sha256'])


def test_corrupt_archive_fails_before_restore(pipeline,accepted,tmp_path):
    a=tmp_path/'x.zip';r=backup_reference(pipeline.journal,a);a.write_bytes(a.read_bytes()+b'changed')
    pipeline.close();root=pipeline.root;root.rename(root.with_name('offline'))
    with pytest.raises(IntegrityError):restore_reference(a,root,r['archive_sha256'])
    assert not root.exists()


@pytest.mark.parametrize('member',['../escape','.env','batches/not-a-hash/plan.json'])
def test_untrusted_backup_members_rejected_even_with_supplied_hash(pipeline,accepted,tmp_path,member):
    a=tmp_path/'x.zip';backup_reference(pipeline.journal,a)
    b=tmp_path/'changed.zip'
    with zipfile.ZipFile(a) as z,zipfile.ZipFile(b,'w') as out:
        for name in z.namelist():out.writestr(name,z.read(name))
        out.writestr(member,b'bad')
    pipeline.close();root=pipeline.root;root.rename(root.with_name('offline'))
    with pytest.raises(IntegrityError):restore_reference(b,root,file_digest(b))
    assert not root.exists()


def test_incomplete_restore_not_readable_or_writable(pipeline,profile):
    (pipeline.root/'.restore-in-progress').write_text('{}')
    with pytest.raises(IntegrityError):Journal(pipeline.root,profile)
    with pytest.raises(IntegrityError):Journal(pipeline.root,profile,read_only=True)


def test_governance_intent_is_preserved_not_silently_forgotten(pipeline,accepted,tmp_path):
    from ilc.canonical import immutable_write,digest,read_json
    outbox=pipeline.root/'governance-outbox';key=digest('synthetic-plan')
    state={'plan_sha256':key,'operations':{'remote-write':'REQUESTED'}}
    immutable_write(outbox/(key+'.json'),canonical(state))
    archive=tmp_path/'backup.zip';backup=backup_reference(pipeline.journal,archive)
    root=pipeline.root;pipeline.close();root.rename(root.with_name(root.name+'-offline'))
    restore_reference(archive,root,backup['archive_sha256'])
    assert read_json(root/'governance-outbox'/(key+'.json'))==state


def test_backup_blocks_during_catalog_publication(pipeline,accepted,tmp_path):
    from ilc.canonical import pipeline_lock
    with pipeline_lock(pipeline.root/'governance-outbox'):
        with pytest.raises(BusyError):backup_reference(pipeline.journal,tmp_path/'backup.zip')


def test_unexpected_governance_file_is_not_archived(pipeline,accepted,tmp_path):
    outbox=pipeline.root/'governance-outbox';outbox.mkdir()
    (outbox/'token.txt').write_text('sensitive-fixture')
    with pytest.raises(BackupError,match='Unexpected'):backup_reference(pipeline.journal,tmp_path/'backup.zip')
    assert not (tmp_path/'backup.zip').exists()
