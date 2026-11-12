# Industrial Lakehouse Contracts — P01

**Contract-driven data ingestion with explicit reporting acceptance and recoverable publication.**

I am building an original portfolio project for a fictional three-site manufacturer. It connects a database, a paginated HTTP source and CSV files, validates five business entities, reconciles exact monetary totals, and exposes only the last accepted reporting generation.

## Current evidence, not a marketing badge

| Surface | Current state |
|---|---|
| Reference: SQLite, loopback HTTP, CSV, SQL, authenticated reporting | Executed; local evidence and separate hosted reference success |
| PostgreSQL / PySpark / Delta / Dagster | **Bounded native functional qualification accepted at `fc1a928`**, after review of supplied CircleCI evidence; original XML hash and credit usage reservations remain |
| Abrupt exit after target write / before checkpoint | Native recovery with HTTP source offline, Bronze/target reused and one publication |
| Bad data and schema drift | Native publication blocked; previous report retained |
| Metadata-only extra entity | Executed on reference profile with unchanged pipeline source hash |
| OpenMetadata | Publisher and protocol-emulator tests implemented; **real product NOT RUN** |
| Fabric / Power BI | Read-only preflight only; **no tenant integration or BI report** |
| Reference backup/restore | Same-path SQLite restoration tested; **not PostgreSQL/Delta DR** |
| Docker Compose build / Windows runtime | Not qualified by the CircleCI Linux route |
| Distributed scale / HA / production readiness | **NOT CLAIMED** |

The [native evidence review](docs/evidence/NATIVE_fc1a928_REVIEW.md) records 1 executed native pytest, 234 deselected tests, six separate application scenarios, 14 matching reconstructed JSON hashes and 20 matching runtime source files. It distinguishes copied evidence from raw downloads and preserves the browser-modified XML limitation. Historical reference results are not transferred into native counts.

The reference profile uses immutable JSON datasets, **not Delta tables**. It remains a useful independent profile; native qualification uses real PostgreSQL/Spark/Delta/Dagster. P01 is not complete: real governance and provider gates remain open. P05 and P03 have not started.

## What the demonstration does

1. Read customers, orders and order lines transactionally from the selected database; products from CSV; shipments through bounded HTTP pagination.
2. Bind an immutable run plan to contract/profile/code/runtime hashes, an upper timestamp and the previously accepted generation.
3. Preserve Bronze inputs, type and reconcile Silver, and reject duplicate-key members or conflicting same-timestamp updates.
4. Materialize customer/product/site snapshot dimensions and a reviewed order-fulfillment fact model; independently reconcile line counts, keys and exact Decimal totals.
5. Write a candidate without exposing it to reporting; accept its pointer and watermarks transactionally after verification. Native execution also rereads Delta at the final path.
6. Serve site-scoped FastAPI reports. Other-site records/totals and unauthorized catalog/evidence views are refused.
7. Demonstrate rejection, interruption, recovery and honest reporting of version, freshness and degradation.

The native synthetic run captured 10,000 records, produced 3,980 facts and reconciled 8,857,766.18 EUR initially. Fixture revision 1 adds 20.00 EUR on SITE_A; recovered generation 2 reports 8,857,786.18 EUR without adding facts or orders. These are correctness observations, not business performance or scale claims.

## Run the reference slice

Python 3.12 or 3.13 is the declared target; the historical local reference qualification used 3.13.5. Use a new virtual environment:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
python -m ilc.cli validate
python -m pytest --junitxml=artifacts/junit.xml
python scripts/qualify_reference.py --output .runtime/qualification-001 --rows 10000
python scripts/qualify_recovery_governance.py --output .runtime/recovery-001 --rows 10000
```

Use a **new output directory**. The scripts do not overwrite previous runs. `evidence/` contains receipts, API observations, recovery chronology, local catalog/lineage and HTML exports from authorized responses. `work/` contains source databases and runtime state: do not publish it automatically.

The reference route uses synthetic data and loopback HTTP services, stopped before script exit. Its deliberate abrupt child-process exit is an explicitly opted-in fixture, not a production fault injector.

### Interactive reference use

```bash
ilc fixture --output .runtime/source --rows 10000
ilc source-api --fixture .runtime/source --port 8765
# In another terminal:
ilc run --root .runtime/pipeline --fixture .runtime/source \
  --key first-load --until 2026-11-12T10:00:00Z --api-url http://127.0.0.1:8765
ilc status --root .runtime/pipeline
python scripts/create_access_policy.py --output .runtime/access-policy.json
ilc report-api --root .runtime/pipeline --access-policy .runtime/access-policy.json --port 8766
```

The policy helper prints two random demonstration tokens once. Keep them outside Git. Use them on the report page or in `Authorization: Bearer ...` headers. `/api/report`, `/dashboard` and `/api/orders/{id}` enforce site scope; catalog/evidence require the full site scope. Read-only status/report commands refuse an absent runtime instead of initializing it.

Fixture time is fixed for repeatability. A successfully loaded report can correctly be `STALE`; failed subsequent loads expose `DEGRADED` while preserving accepted totals. Successful loading is not proof of freshness. A new fixture may use an explicit anchor.

## Contracts and business model

`contracts/sales.json` covers customers, products, orders, order_lines and shipments across three sites, with EUR-only amounts. On-time quantity counts units delivered by the promised timestamp; it is **not** order-level OTIF. No currency conversion is performed.

`profiles/reference.json` and `profiles/native.json` describe execution rather than business meaning. Metadata selects reviewed operations, not arbitrary SQL or Python. The original `ilc-contract/1` format is **not claimed ODCS-compliant**.

See [contracts](docs/CONTRACTS.md), [architecture](docs/ARCHITECTURE.md), [recovery](docs/RECOVERY.md), [security](docs/SECURITY.md), [qualification](docs/QUALIFICATION.md), [CircleCI](docs/CI_CIRCLECI.md) and [remaining gates](docs/PROVIDER_GATES.md).

## Native route and reviewed environment

The accepted CircleCI run used Python 3.12.16, Temurin 17.0.21+9, PostgreSQL `server_version=160015`, PySpark/Delta Spark 4.0.1, Dagster 1.11.16 and Psycopg 3.2.13. Dagster ran `accepted_sales_job` in process. Ten Delta tables per accepted batch were reconciled at their final location at version 0. Native reporting/retries require the bound final-readback proof, and decimal normalization preserves the contracted scale.

The job installs a size/SHA-256-checked official Temurin 17 archive. Its exact release is recorded, but latest-GA selection and minor image tags are not an immutable toolchain lock; JDK signature verification is not claimed. The earlier native attempt failed; the later success does not establish the precise unread first failure cause.

Only a dedicated disposable loopback database prefixed `ilc_demo` is allowed, with `ILC_ALLOW_NATIVE_DEMO=1`. Existing source tables are refused, not truncated. CircleCI native execution requires the scoped qualification branch or `run_native: true`; a 35-minute command watchdog and stage limits bound work. No new run is needed to review the existing receipts. Compose and GitHub Actions remain prepared alternative routes, not separately qualified routes. See [the runbook](docs/RUNBOOK.md).

## Scope limitations

This is bounded single-host Spark `local[2]`, not distributed Big Data. Sources are fully captured under row/byte budgets before incremental selection; no source-pushdown scalability is claimed. Every accepted generation writes a complete candidate. No CDC/delete capture, distributed exactly-once, automatic retention, multi-host fencing or HA is provided.

Recovery was exercised after synchronous Spark materialization/stop and target relocation, not during an in-flight executor action. PostgreSQL remained available. The report reads JSON projections reconciled against Delta, not Direct Lake. Application API permissions do not establish database/OS/cloud isolation. Reference SQLite restore does not qualify PostgreSQL/Delta DR or path migration.

Filesystem/database owners are outside the report API security boundary. Hashes detect drift but are not signatures. Integrity checks are not optimized for large reporting volumes. A synthetic source-vector check is not a distributed transaction across production systems. No client code, schema, identifier or document is incorporated.

## Governance and reference restoration

The OpenMetadata publisher exports owners, classification, 15 base tables, 11 lineage edges and one accepted DQ result. Its durable outbox records intent before mutation, reads back outcomes, reuses an exact remote object after response loss and refuses unresolved/conflicting outcomes. Tests use a **protocol emulator**, not a live OpenMetadata product. See [governance](docs/GOVERNANCE.md).

Reference backup holds writer locks and uses SQLite's backup API, preserving the outbox but excluding bearer policies. Restore refuses an existing root or changed path identity. The demonstration preserves the old runtime, restores, rereads the HTTP report and replays offline. See [backup/restore](docs/BACKUP_RESTORE.md).

```bash
python scripts/check_environment.py --output artifacts/environment.json --check-public-dns
```

Exit 2 means missing native prerequisites, not a successful native test. Older environment receipts describe the restricted authoring environment; they do not negate the later CircleCI native execution. No personal computer or client system is used as a fallback.

## Publication and evidence status

The repository remains private under Draft PR #1; `main` is not merged. Native functional G2 is accepted for **`fc1a9286c937deb09b87b97524c6835b24a1d516` only**, with original-XML archival and actual-credit reservations tracked in #3. Later documentation commits do not claim a new runtime execution. Reference CI success remains distinct from a full review of reference JUnit.

OpenMetadata (#4), Fabric/Power BI (#5), license, public visibility and final disclosure review remain open. No redistribution license is invented. P05/P03 remain queued.

**Résumé français.** Le parcours natif PostgreSQL/PySpark/Delta/Dagster est désormais accepté sur un périmètre synthétique mono-hôte : contrats, qualité, réconciliation, reporting autorisé et reprise contrôlée. Les 14 reçus JSON concordent avec leurs empreintes. Le XML brut et les crédits restent des réserves documentaires ; OpenMetadata réel, Fabric/Power BI et la qualification de charge ne sont pas validés.
