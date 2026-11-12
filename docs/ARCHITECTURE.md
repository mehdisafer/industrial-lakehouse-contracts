# Architecture and implementation decisions

## Data and control paths

```text
Synthetic snapshot manifest
  |-- database: customers, orders, order_lines (one read transaction)
  |-- CSV: products
  `-- HTTP: shipments (snapshot ID, total, cursor, fields, page/byte budgets)
        |
  immutable Bronze + finalized inventory
        |
  strict contract -> typed Silver -> blocking row/business checks
        |
  reviewed SQL Gold -> independent Decimal/key/count reconciliation
        |
  attempt-specific candidate staging -> inventory -> atomic directory rename
        |
  native-only: reread final-path Delta, reconcile and persist bound proof
        |
  journal transaction: accepted pointer + watermarks + evidence receipt
        |
  read-only consumer -> verify accepted digest -> scope -> aggregate -> report
```

The admission key is distinct from attempt count. A key is bound to its upper bound, metadata, source locator, executing package bytes and runtime versions. An existing key with a changed request is rejected. A promoted dataset is immutable; retries cannot replace it with new live input.

## ADR-001: two explicit execution profiles

The phase-2 design calls for PostgreSQL, Spark, Delta, Dagster and Fabric/Power BI. Those capabilities were unavailable in the current sandbox and dependency downloads failed. Rather than falsely label SQLite as a lakehouse qualification, this increment implements a named `reference_sqlite/reference_json` profile and a separate native adapter.

The reference proves business/control semantics with actual SQLite, files, HTTP and process behavior. The native profile must still be installed and executed. Its driver-bounded inputs and reference reconciliation do not become a distributed-scale engine just because Spark is present. No gate for native/platform acceptance is closed by reference tests.

## ADR-002: acceptance is the sole publication authority

Filesystem commit and state commit do not share a transaction. Candidate data are durably stored first. The state journal then commits the accepted pointer, watermarks and receipt together. A crash between the two leaves a candidate, not a reportable generation. On retry, Bronze is reused, outputs are recomputed and the existing target is checked before publication.

Compare-and-swap prevents an older attempt based on an earlier generation from replacing a newer accepted generation. The reference lock is process-owned, single-host. Native operation adds a PostgreSQL advisory lock. No lock prevents malicious host administrators from modifying files.

Native Spark writes to an attempt-specific staging directory. A surviving worker has no authority to publish the accepted pointer or rename a candidate. Post-move Delta re-reading is now implemented as a mandatory publication gate, with an immutable proof outside the target inventory. A failure prevents the acceptance/watermark transaction. This code is unit-tested with an injected verifier, not a live Spark qualification. Staging cleanup is not automated; native process-tree behavior and post-move reads still require the actual engine run.

## ADR-003: fixed business model, extensible entity ingestion

A strict contract selects only `sales_fulfillment_v1`. Extra compatible entities can enter Bronze, Silver and the catalog by metadata alone; the qualification adds `warehouses`. This does **not** automatically generate new business metrics or a universal report for arbitrary entities. A new Gold model requires reviewed code and tests.

## ADR-004: source fidelity before incremental merge

The fixture's database, HTTP server and files expose a pinned synthetic source vector. Count/digest agreement is required before processing. Database tables are read in one transaction; HTTP pages must retain the same snapshot, fields, count and as-of timestamp.

Full-source bounded capture is deliberate for the first demonstration. Incremental bounds are applied to typed records; ties are inclusive and a bounded lookback admits late updates. Equal-key/equal-timestamp conflicting payloads are rejected. Updates older than the lookback and physical deletes require separate reconciliation/CDC; they are not covered.

## ADR-005: native provider claims require provider evidence

Local table, lineage and quality JSON are real output artifacts. A metadata-only publisher is now implemented against the pinned OpenMetadata 1.12.0 API. Its emulator tests exercise HTTP and delivery logic, not the product itself. A Fabric inventory call is read-only connectivity metadata, not a deployed pipeline or Power BI report. `NOT_RUN` is retained until an authorized account and the corresponding end-to-end validation exist.

## Deliberate operational limits

No unbounded retry loop, arbitrary shell/SQL from metadata, hidden network fallback, automatic deletion, scheduler activation or personal-machine operation exists. Reference loopback restrictions are application checks, not a kernel egress sandbox. Java/Maven dependency resolution on the native profile may use the public network; that native installation path is not an air-gapped guarantee.

## ADR-006: metadata effects have their own durable outbox

The accepted immutable dataset is the export source; a request never grants the
catalog permission to alter the data pipeline. A generation change during export
construction is rejected. Intent and readback state are persisted separately from
the data acceptance. Unknown effects are reconciled, not silently reissued. The
loopback token and pre-existing service/team/tag permissions are external to the
contract. The native/provider qualification status is never inherited from the
reference source profile or emulator.

## ADR-007: backup the reference state without changing identity

The reference backup holds both writer locks and captures SQLite consistently,
immutable batch artifacts and governance intent. Credentials and the remote
catalog are out of scope. Restoration requires the missing original root, checks
all archive/accepted-state evidence and keeps an interrupted restore unavailable.
No silent path rebase or PostgreSQL-to-SQLite conversion is allowed.
