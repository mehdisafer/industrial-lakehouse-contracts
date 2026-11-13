# Architecture and design decisions

## System boundary

I separate the **data plane** that materialises a candidate from the **control
plane** that decides whether consumers may use it. The implementation targets
reproducible, bounded runs on a single host. It has two execution profiles and a
separately qualified catalogue publisher; [STATUS.md](STATUS.md) records their
exact execution baselines.

| Responsibility | Implementation |
|---|---|
| Contract and execution validation | [contracts.py](../src/ilc/contracts.py), JSON contracts/profiles |
| Database, HTTP and CSV capture | [sources.py](../src/ilc/sources.py) |
| Immutable capture/candidate artifacts | [storage.py](../src/ilc/storage.py) |
| Typing, merge and business model | [transform.py](../src/ilc/transform.py), [native.py](../src/ilc/native.py) |
| Admission, acceptance and watermarks | [pipeline.py](../src/ilc/pipeline.py), [journal.py](../src/ilc/journal.py) |
| Native job orchestration | [orchestration.py](../src/ilc/orchestration.py) |
| Consumer scope and reporting | [reporting.py](../src/ilc/reporting.py), [report_api.py](../src/ilc/report_api.py) |
| Metadata publication and outbox | [governance.py](../src/ilc/governance.py) |

## End-to-end flow

```text
Database transaction + CSV + bounded HTTP pagination
    -> frozen Bronze and source inventory
    -> strict typing and incremental Silver merge
    -> blocking row, schema and business checks
    -> reviewed Gold model
    -> independent count, key and Decimal reconciliation
    -> candidate staging and immutable target
    -> native profile: final-path Delta readback and bound proof
    -> journal transaction: accepted pointer + watermarks + receipt
    -> authorised report / separate metadata publication
```

An admission key is bound to a source locator, upper timestamp, metadata,
implementation bytes and runtime versions. It is not an attempt number. Reusing
that key for another request fails. A committed candidate does not become visible
until the journal accepts it.

## ADR-001 — explicit reference and native profiles

**Decision.** Keep one business contract with distinct reference and native
execution profiles. Reference uses SQLite/JSON; native uses PostgreSQL,
Spark SQL/Delta and an in-process Dagster job.

**Reason.** Fast, deterministic control-path tests and actual engine integration
exercise different risks. Neither should be silently substituted for the other.

**Trade-off.** The native adapter retains bounded driver-side input and independent
reference reconciliation. Using Spark does not by itself establish distributed
scale. Native functionality was executed and reviewed at `fc1a928`; the
[evidence record](evidence/NATIVE_fc1a928_REVIEW.md) defines the tested boundary.

## ADR-002 — the journal is the publication authority

**Decision.** Store and verify immutable candidate data first; commit the accepted
pointer, watermarks and receipt together in the state journal afterwards.

**Reason.** The filesystem and state database do not share a transaction. A crash
between their commits must leave an unaccepted candidate, not a partial report.

**Trade-off.** Recovery needs explicit reconciliation and retained staging artifacts.
A process-owned lock protects the reference writer; native uses a PostgreSQL
advisory lock. Compare-and-swap rejects a publication based on a superseded
accepted generation. These controls are not multi-host filesystem fencing.

Native acceptance additionally rereads all ten version-pinned Delta tables at
their final path after target relocation. A failed readback blocks the journal
transaction. The controlled native crash occurs after synchronous materialisation
and Spark shutdown, not during an in-flight executor operation.

## ADR-003 — metadata-driven ingestion, reviewed business transformations

**Decision.** Contracts declare field semantics, keys, ownership and classification;
profiles declare source mappings and resource bounds. A registry selects reviewed
transformation code.

**Reason.** Configuration should support entity onboarding without becoming an
arbitrary-code execution channel.

**Trade-off.** A compatible additional entity can enter Bronze, Silver and the
catalogue through metadata. It does not automatically create a new fact model or
report metric. [DATA_MODEL.md](DATA_MODEL.md) defines the implemented business grain.

## ADR-004 — capture fidelity before incremental selection

**Decision.** Capture a bounded source snapshot before applying inclusive watermark
bounds and a lookback window to typed records.

**Reason.** Snapshot identity, source counts and frozen input make replay and
interrupted-publication recovery inspectable. HTTP pagination must retain its
snapshot, fields, count and as-of timestamp.

**Trade-off.** This is not source-pushdown optimisation or CDC. Older updates and
physical deletions require explicit future handling. Independently operated source
systems are not covered by a global transaction.

## ADR-005 — metadata delivery has its own outbox

**Decision.** Build the export from a verified accepted generation. Record intent
before a catalogue mutation and verify remote state afterwards.

**Reason.** An absent response does not tell the caller whether a mutation happened.
Recovery reconciles the existing object instead of blindly issuing another create.

**Trade-off.** There is one catalogue writer per namespace, without distributed
fencing. Each accepted generation gets an immutable catalogue database, so retention
is a separate concern. OpenMetadata API/RBAC behaviour was qualified at `cd09de0`
with reference inputs; this does not claim a combined Spark-to-catalogue run.
See [governance](GOVERNANCE.md) and [live qualification](OPENMETADATA_LIVE.md).

## ADR-006 — preserve identity during reference restore

**Decision.** Back up SQLite consistently while holding writer locks, retain
immutable batch/outbox state, and restore only into the absent original root.

**Reason.** Rebinding paths or converting state backends would change the identity
being recovered and invalidate the original acceptance evidence.

**Trade-off.** Same-path reference recovery is implemented; migration, PostgreSQL
restore and Delta disaster recovery remain separate qualifications.
See [backup and restore](BACKUP_RESTORE.md).

## Trust and operational boundaries

Metadata cannot grant arbitrary SQL, shell or Python execution. Loopback URL checks,
path validation, response budgets and application roles reduce the demonstration's
exposure; they are not an OS sandbox. A host/database administrator remains outside
the consumer security boundary. Native package/JAR resolution uses external
repositories and is not air-gapped.

I keep deployment claims tied to executed environments. Fabric inventory is not a
Fabric pipeline, and HTML reporting is not Power BI. The remaining platform work
is explicit in [PROVIDER_GATES.md](PROVIDER_GATES.md).
