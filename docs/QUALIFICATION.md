# Qualification protocol and evidence scopes

The deliverable contains a separately generated receipt and JUnit from a specific source commit. Tests are an implementing-assistant self-check, not an independent review. The reference suite includes actual SQLite transactions, real local files, loopback HTTP ingestion, API permission tests, abrupt subprocess exits, process-lock exclusion and immutable artifact checks. Fabric preflight tests are transport mocks. Native integration is separately marked and skipped by default.

| Acceptance ID | Reference observation required | Native/provider state |
|---|---|---|
| V-P01-01 | Same key/plan gives same dataset, no extra generation | Not executed |
| V-P01-02 | Hard process exit after target commit; unchanged watermark; resume offline; one publication | Not executed on PostgreSQL/Spark/Delta |
| V-P01-03 | Duplicate, invalid decimal, schema drift reject publication | Not executed on provider |
| V-P01-04 | Exact counts, keys, decimal sums on pinned bounded input | Native Spark reconciliation implemented, not executed |
| V-P01-05 | Actual HTTP denies other-site/global views; read-only reporting DB | No Fabric/Power BI/OpenMetadata role qualification |
| V-P01-06 | Actual report keeps accepted batch and declares degraded/stale | No Power BI report built |

Additional cases cover pagination truncation/cycles, changed credentials' target via continuation URLs, incomplete capture, target/capture corruption, changed code/metadata with a reused key, contract evolution, lookback/ties, superseded attempts, accepted/rejected response loss and metadata-only entity onboarding.

## Interpreting the numbers

The fixture's base total is 10,000 records across five entities, not 10,000 rows in each table. Deliberate duplicates add one record. The evidence reports actual captured rows and serialized Bronze bytes. These are SMOKE-level, bounded data; no million-row or distributed-throughput claim is made.

The script records total reference wall time and an attempt duration. Neither is a p95 service SLO. No cloud billing, scale limit, cross-platform performance, HA, durability under power failure or restore RTO/RPO was measured. A bounded reference same-path backup/restore exercise is separate from those operational claims. A test marked skipped is not validated.

The environment already contained Python dependencies. A fresh installation, candidate native package versions, container build and hosted Actions remain unverified. Direct package pins do not constitute a transitive lock or security audit.

The receipt binds actual importing package bytes to the supplied checkout. A source-directory mismatch fails. A clean local Git commit provides a reproducible checkpoint; it does not establish a remote GitHub publication or signed supply-chain attestation.

## Incremental verification layers

- `test_native_readback.py`: scalar precision and final-publication gates; the
  Delta verifier is injected where unavailable. **No Spark execution.**
- `test_governance.py`: immutable accepted export, pinned API paths, prerequisites,
  scopes, owner/type/tag drift, unknown-response reconciliation and HTTP behavior.
  The peer is MockTransport or `CatalogEmulator`. **No OpenMetadata product.**
- `test_backup.py`: real SQLite backup, archive integrity, same-path restoration,
  consumer result and replay, lock conflict, outbox preservation and unsafe input.
- `test_qualification_harness.py`: native preconditions and separate fixture
  schemas. **No native qualification.**
- `qualify_recovery_governance.py`: real reference source/consumer and restore,
  real loopback HTTP to a named catalog emulator, plus separately labelled mocked
  response-loss test. Secrets/policies remain outside exported evidence.

The final JUnit and clean source-commit receipt, not this document's presence,
state which checks ran. The original six P01 requirements remain qualified only
on the reference path. The fuller native harness and updated manual CI route are
implemented candidates; live OpenMetadata, Fabric, Power BI, scale and PostgreSQL
DR gates remain open. No new project starts on the basis of these unit tests.
