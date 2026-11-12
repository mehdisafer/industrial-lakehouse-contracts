"""Consistent reference-profile backup and same-path restore to an absent root.

This deliberately refuses PostgreSQL runtimes: a SQLite copy cannot back up
external PostgreSQL state. Restore never replaces an existing directory and never
changes pipeline identity or historical batch IDs.
"""
from __future__ import annotations

import json
import re
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import zipfile

from .canonical import canonical, digest, file_digest, fsync_dir, immutable_write, read_json, within, pipeline_lock
from .errors import IntegrityError, PipelineError
from .storage import read_target, batch_path, verify_manifest, read_capture

MAX_RESTORE_BYTES = 500_000_000
MAX_RESTORE_FILES = 20_000


class BackupError(PipelineError):
    code = 'BACKUP_ERROR'


def backup_reference(journal, destination: Path) -> dict:
    """Keep the writer lock during the SQLite backup API and file capture."""
    if journal.backend!='sqlite' or journal.read_only:
        raise BackupError('Reference backup needs a writable SQLite journal to hold its lock')
    destination=destination.resolve()
    if destination.is_relative_to(journal.root):
        raise BackupError('Backup destination must be outside its runtime')
    if destination.exists():raise BackupError('Backup already exists; no overwrite')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_name(destination.name+'.sqlite-partial')
    if temp.exists():raise BackupError('An earlier partial backup must be inspected')
    with journal.lock(), pipeline_lock(journal.root / "governance-outbox"):
        state=journal.state()
        if state['accepted_batch'] is None:raise BackupError('No accepted generation to back up')
        accepted=journal.get(state['accepted_batch'])
        if accepted['receipt'].get('target')!='reference_json':
            raise BackupError('This backup route qualifies only the reference JSON target')
        target=read_target(journal.root,state['accepted_batch'])
        if target is None or digest(target)!=accepted['receipt']['target_manifest_sha256']:
            raise IntegrityError('Cannot back up a corrupt accepted dataset')
        paths=[journal.root/'.ilc-sandbox.json']
        for path in sorted((journal.root/'governance-outbox').iterdir()):
            if path.name=='.pipeline.lock':continue
            if path.is_symlink() or not path.is_file() or not re.fullmatch(r'[a-f0-9]{64}(?:\.plan|\.receipt)?\.json',path.name):
                raise BackupError('Unexpected governance outbox entry; inspect before backup')
            paths.append(path)
        for path in sorted((journal.root/'batches').rglob('*')):
            if path.is_symlink():raise IntegrityError('Symlink in runtime inventory')
            if path.is_file():paths.append(path)
        # An ownership/admission marker and batches are included. Bearer policies,
        # external source fixtures, env files and temporary locks are NOT included.
        if len(paths)>MAX_RESTORE_FILES:raise BackupError('File inventory exceeds backup budget')
        with sqlite3.connect(journal.root/'journal.sqlite') as source,sqlite3.connect(temp) as snapshot:
            source.backup(snapshot)
            if snapshot.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise IntegrityError('SQLite backup integrity failed')
        inventory={p.relative_to(journal.root).as_posix():{'bytes':p.stat().st_size,'sha256':file_digest(p)} for p in paths}
        inventory['journal.sqlite']={'bytes':temp.stat().st_size,'sha256':file_digest(temp)}
        if sum(v['bytes'] for v in inventory.values())>MAX_RESTORE_BYTES:
            raise BackupError('Backup exceeds bounded reference byte budget')
        manifest={'schema_version':'ilc-reference-backup/1','backend':'sqlite',
            'pipeline':journal.pipeline,'registry':state,'accepted_receipt_sha256':digest(accepted['receipt']),
            'files':inventory,'restore_policy':'EXACT_ORIGINAL_ROOT_IDENTITY_AND_ABSENT_DIRECTORY',
            'secrets_included':False,'postgresql_backed_up':False,
            'governance_intents_included':True, 'remote_catalog_backed_up':False}
        # A failed archive is kept as evidence and is not overwritten on retry.
        with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('backup-manifest.json',canonical(manifest))
            for p in paths:z.write(p,p.relative_to(journal.root).as_posix())
            z.write(temp,'journal.sqlite')
        with destination.open('rb') as f:os.fsync(f.fileno())
        fsync_dir(destination.parent)
        # Dispose only the temporary SQLite copy made and owned by this call.
        temp.unlink();fsync_dir(temp.parent)
    return {'status':'REFERENCE_BACKUP_WRITTEN','archive_sha256':file_digest(destination),
        'files':len(inventory),'uncompressed_bytes':sum(v['bytes'] for v in inventory.values()),
        'generation':state['generation'],'pipeline':journal.pipeline,
        'restore_tested_by_this_operation':False,'native_backup_qualified':False}


def _safe_member(name: str) -> None:
    p=PurePosixPath(name)
    if p.is_absolute() or '\\' in name or any(x in ('..','.') for x in name.split('/')):
        raise IntegrityError('Archive path is unsafe')
    if name in {'.ilc-sandbox.json','journal.sqlite'}:return
    parts=p.parts
    if len(parts)==2 and parts[0]=='governance-outbox' and re.fullmatch(r'[a-f0-9]{64}(?:\.plan|\.receipt)?\.json',parts[1]):return
    if (len(parts)<3 or parts[0]!='batches' or len(parts[1])!=64
            or any(c not in '0123456789abcdef' for c in parts[1])):
        raise IntegrityError('Archive contains a non-runtime file')


def restore_reference(archive: Path, destination: Path, expected_sha256: str) -> dict:
    """Restore only into a missing original path, retaining evidence on failure.

    A separate externally supplied archive hash is required. Hashes are integrity
    checks, not signatures. A different root requires an explicit migration which
    this function does not silently perform.
    """
    destination=destination.resolve()
    if destination.exists():raise BackupError('Restore destination already exists; no overwrite')
    if not expected_sha256 or file_digest(archive)!=expected_sha256:
        raise IntegrityError('Backup archive digest does not match the supplied receipt')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or len(infos)>MAX_RESTORE_FILES+1:
            raise IntegrityError('Duplicate members or excessive restore inventory')
        if sum(i.file_size for i in infos)>MAX_RESTORE_BYTES:
            raise IntegrityError('Restore exceeds uncompressed byte budget')
        if 'backup-manifest.json' not in names:raise IntegrityError('Missing backup manifest')
        manifest=json.loads(z.read('backup-manifest.json'))
        if manifest.get('schema_version')!='ilc-reference-backup/1' or manifest.get('backend')!='sqlite':
            raise IntegrityError('Unsupported backup schema/backend')
        expected_pipeline=digest({'root':str(destination),'application':'ilc/0.1'})
        if manifest['pipeline']!=expected_pipeline:
            raise BackupError('Different root identity requires a separately reviewed migration')
        if set(names)!={'backup-manifest.json',*manifest['files']}:
            raise IntegrityError('Archive and manifest inventories differ')
        if not {'.ilc-sandbox.json','journal.sqlite'}<=set(manifest['files']):
            raise IntegrityError('Missing journal or sandbox marker')
        for info in infos:
            if info.filename=='backup-manifest.json':continue
            _safe_member(info.filename)
            mode=info.external_attr>>16
            if stat.S_ISLNK(mode) or info.is_dir():raise IntegrityError('Nonregular archive member')
            details=manifest['files'][info.filename]
            if info.file_size!=details['bytes']:raise IntegrityError('Archive size differs from manifest')
            import hashlib
            if hashlib.sha256(z.read(info.filename)).hexdigest()!=details['sha256']:
                raise IntegrityError('Archive file digest differs from manifest')
        # Exclusive mkdir prevents overwriting another runtime, including a racing
        # empty directory. Interrupted restore stays unusable, not partly accepted.
        destination.mkdir(parents=True,exist_ok=False)
        marker=destination/'.restore-in-progress'
        immutable_write(marker,canonical({'backup_sha256':expected_sha256}))
        for name in sorted(manifest['files']):
            immutable_write(within(destination,name),z.read(name))
    expected_marker={'pipeline':expected_pipeline,'classification':'PUBLIC_SYNTHETIC','single_host':True}
    if read_json(destination/'.ilc-sandbox.json')!=expected_marker:
        raise IntegrityError('Restored runtime marker differs from its identity')
    from urllib.parse import quote
    with sqlite3.connect('file:'+quote(str(destination/'journal.sqlite'))+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise IntegrityError('Restored SQLite integrity failed')
        row=db.execute('SELECT * FROM ilc_registry WHERE pipeline=?',(expected_pipeline,)).fetchone()
        if row is None:raise IntegrityError('Restored namespace missing')
        state=dict(row);state['watermarks']=json.loads(state['watermarks'])
        if state!=manifest['registry']:raise IntegrityError('Restored publication state differs')
        runs=db.execute('SELECT * FROM ilc_runs WHERE pipeline=?',(expected_pipeline,)).fetchall()
        active_count=0
        for raw in runs:
            item=dict(raw);plan=json.loads(item['plan']);batch=item['batch_id']
            if read_json(batch_path(destination,batch)/'plan.json')!=plan:
                raise IntegrityError('Restored plan differs from journal')
            if item['status']=='ACCEPTED':
                receipt=json.loads(item['receipt']);target=read_target(destination,batch)
                if target is None or digest(target)!=receipt['target_manifest_sha256']:
                    raise IntegrityError('Restored accepted generation differs')
                captured=read_capture(destination,batch,plan)
                if captured is None or digest(captured[1])!=receipt['capture_sha256']:
                    raise IntegrityError('Restored accepted Bronze differs')
                if batch==state['accepted_batch']:
                    active_count += 1
                    if digest(receipt)!=manifest['accepted_receipt_sha256']:
                        raise IntegrityError('Restored accepted receipt differs')
        if active_count!=1:
            raise IntegrityError('Restored publication must name one accepted run')
    marker.unlink();fsync_dir(destination)
    return {'status':'REFERENCE_RESTORE_VERIFIED','pipeline':expected_pipeline,
        'generation':state['generation'],'watermarks':state['watermarks'],
        'accepted_batch':state['accepted_batch'],'archive_sha256':expected_sha256,
        'native_backup_qualified':False,'consumer_rechecked_by_this_operation':False}
