# Qualification protocol and evidence scopes

The deliverable contains a separately generated receipt and JUnit from a specific source commit. I distinguish implementation self-checks from an independent review. The reference suite includes actual SQLite transactions, real local files, loopback HTTP ingestion, API permission tests, abrupt subprocess exits, process-lock exclusion and immutable artifact checks. Fabric preflight tests are transport mocks. Native integration is separately marked and skipped by default.

| Acceptance ID | Reference observation required | Native/provider state |
|---|---|---|
| V-P01-01 | Same key/plan gives same dataset, no extra generation | Native attempts started; no accepted receipt yet |
| V-P01-02 | Hard process exit after target commit; unchanged watermark; resume offline; one publication | Native recovery proof still pending |
| V-P01-03 | Duplicate, invalid decimal, schema drift reject publication | Not executed on provider |
| V-P01-04 | Exact counts, keys, decimal sums on pinned bounded input | Native Spark reconciliation implemented; accepted evidence still pending |
| V-P01-05 | Actual HTTP denies other-site/global views; read-only reporting DB | No Fabric/Power BI/OpenMetadata role qualification |
| V-P01-06 | Actual report keeps accepted batch and declares degraded/stale | No Power BI report built |

Additional cases cover pagination truncation/cycles, changed credentials' target via continuation URLs, incomplete capture, target/capture corruption, changed code/metadata with a reused key, contract evolution, lookback/ties, superseded attempts, accepted/rejected response loss and metadata-only entity onboarding.

## Interpreting the numbers

The fixture's base total is 10,000 records across five entities, not 10,000 rows in each table. Deliberate duplicates add one record. The evidence reports actual captured rows and serialized Bronze bytes. These are SMOKE-level, bounded data; no million-row or distributed-throughput claim is made.

The script records total reference wall time and an attempt duration. Neither is a p95 service SLO. No cloud billing, scale limit, cross-platform performance, HA, durability under power failure or restore RTO/RPO was measured. A bounded reference same-path backup/restore exercise is separate from those operational claims. A test marked skipped is not validated.

Historical local tests used preinstalled dependencies. CircleCI now reports successful reference jobs, with installation commands in their configuration; private step/JUnit evidence has not been independently inspected. The native combination, container build and GitHub Actions qualification remain unaccepted. Direct package pins do not constitute a transitive lock or security audit.

The receipt binds actual importing package bytes to the supplied checkout. A source-directory mismatch fails. A clean local Git commit provides a reproducible checkpoint; it does not by itself establish a remote publication or signed supply-chain attestation. The current repository publication is separately established by GitHub commits and branch readback.

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
on the reference path. The fuller native harness and bounded CircleCI route are
implemented and have triggered real cloud attempts; accepted native receipts, live OpenMetadata, Fabric, Power BI, scale and PostgreSQL
DR gates remain open. No new project starts on the basis of these unit tests.

## Native CI gate introduced 12 November 2026

- `tests/test_native_ci_evidence.py`: 19 cases using synthetic receipts/JUnit; rejects skipped native tests, wrong commits, altered source bytes, incomplete semantic checks and mismatched Delta proofs. These tests do not run Spark or PostgreSQL.
- `tests/test_java_bootstrap.py`: 22 offline metadata/archive tests, including a stub transport/process. They verify selection, hashes and refusal of unsafe input; they do not download or execute an actual JDK.
- A combined local run of these files passed 41 tests. Earlier targeted native gates passed 37 tests with one native skip. These overlapping sets must not be added as distinct tests.
- Two attempted complete local suite runs were interrupted by execution limits before completion. They are not full-suite PASS results. Compilation, shell syntax and YAML structural checks succeeded; CircleCI CLI validation and `testsuite doctor` were not run in the authoring environment.
- The reference job at `fc1a928` reports success through GitHub. Its exact number of executed/skipped tests is not inferred from collection counts.

The native gate requires an actually executed native pytest, all six application scenarios, clean exact-SHA receipts, 10,000 captured records per clean scenario, 3,980 facts, 10 version-pinned Delta tables reread at their final path, a Dagster run ID and PostgreSQL 16 fixture receipts. A green job would establish that this gate returned zero, but final qualification additionally inspects the private artifacts.

These checks do not validate distributed scale, database-native RBAC, in-flight Spark action fencing, PostgreSQL restoration or any vendor tenant.
