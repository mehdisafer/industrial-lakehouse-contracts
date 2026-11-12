# Reference backup and controlled same-path restoration

This route qualifies the **single-host SQLite + immutable JSON reference**. It
refuses PostgreSQL journals and Delta targets. It neither backs up a remote
catalog nor claims database PITR, cross-host failover, HA, RTO/RPO or power-loss
durability.

## Consistent snapshot

The backup owns the pipeline writer lock and governance-outbox lock. SQLite's
backup API captures the database consistently rather than copying only its main
file while ignoring WAL. Before archiving, the currently accepted target is
verified against its committed receipt. The archive contains the sandbox marker,
SQLite snapshot, batch plans/input/target evidence and the governance delivery
plans/intents/receipts. Pending metadata effects must not be forgotten on restore.

Access policies, bearer tokens, external source fixtures, temporary locks and
credentials are excluded. Unexpected files in the outbox cause a refusal rather
than accidental credential export. The catalog database itself is not in this
archive; post-restore metadata replay must reconcile it by GET before any write.
The manifest has sizes and SHA-256s; the receipt carries the archive SHA-256.
Those are integrity checks, not signatures or backup encryption.

## Restore invariants

The caller supplies the archive digest from a separately retained receipt. Restore
requires an **absent destination at the original absolute root**, because the
pipeline namespace is derived from that path. No path relocation is smuggled into
recovery. No existing directory is erased or overwritten.

Member paths, inventories, duplicate ZIP entries, type/size budgets and hashes
are checked before extraction. The destination gets a `.restore-in-progress`
marker and is unreadable/unwritable through Journal until verification completes.
An interrupted or corrupt extraction is kept for inspection. The final checks
reread SQLite integrity, publication state, batch plans, accepted Bronze/targets,
and the one accepted run named by the pointer.

The tested recovery procedure closed the original runtime, renamed it to a
preserved sibling, restored to the original location, reread the report through
real HTTP and replayed the accepted key with the HTTP source offline. It also
reread restored governance intent and verified no additional catalog writes
against the explicitly named protocol emulator.

## Commands and operator responsibility

```bash
python scripts/backup.py create --root .runtime/pipeline \
  --archive artifacts/reference-backup.zip --receipt artifacts/backup-receipt.json
```

Stop readers/writers before the restoration exercise. Review the exact original
root and preserve it outside the destination. The tool does not rename it for you,
does not infer consent to destroy it, and refuses to overwrite it.

```bash
python scripts/backup.py restore --root .runtime/pipeline \
  --archive artifacts/reference-backup.zip --expected-sha256 <verified-archive-sha256> \
  --receipt artifacts/restore-receipt.json
```

Then re-establish an access policy outside the archive, start the read-only report
consumer and validate dataset/generation/totals/site scope. An archive created
successfully does not prove restoration. A restore receipt does not by itself
prove that the HTTP consumer was exercised. Use the separate end-to-end harness:

```bash
python scripts/qualify_recovery_governance.py --output .runtime/recovery-001 --rows 10000
```

That harness preserves the original runtime and archive under its private `work/`
directory; only its `evidence/` is a candidate for disclosure review. It starts an
explicit catalog protocol emulator, not the OpenMetadata product.
