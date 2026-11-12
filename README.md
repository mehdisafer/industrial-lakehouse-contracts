# Industrial Lakehouse Contracts — P01

**Contract-driven data ingestion with explicit reporting acceptance and recoverable publication.**

An original public-portfolio candidate for a fictional three-site manufacturer. It connects a database, a paginated HTTP source and CSV files, validates five business entities, reconciles exact monetary totals, and exposes only the last accepted reporting generation.

## Current evidence, not a marketing badge

| Surface | Current state |
|---|---|
| Reference profile: SQLite + real loopback HTTP + CSV + SQL + authenticated reporting | Executed in a disposable Linux/Python 3.13 environment |
| Abrupt process exit after target write / before checkpoint | Recovered with the source HTTP server stopped |
| Bad data and schema drift | Publication blocked; previous accepted report retained |
| Metadata-only extra entity | Executed, with unchanged pipeline source hash |
| PostgreSQL + Spark + Delta + Dagster | Real native CircleCI route started; **NO ACCEPTED NATIVE QUALIFICATION YET**. See PR #1 and issue #3 for exact attempts. |
| OpenMetadata | Metadata publisher implemented against pinned 1.12.0 APIs; unit and loopback **protocol-emulator tests executed**, real product **NOT RUN** |
| Fabric / Power BI | Read-only inventory preflight and acceptance plan only; **no tenant integration or BI report built** |
| Reference backup/restore | SQLite snapshot, same-path restore, report readback and offline accepted replay tested; **not PostgreSQL/Delta DR** |
| Hosted Linux reference CI | CircleCI reported success on `fc1a928`; private JUnit/receipts have not been independently inspected. This is not native qualification. |
| Docker build and Windows runtime | Not qualified by the Linux reference job |
| Distributed scale, HA, production readiness | **NOT CLAIMED** |

The reference profile is an explicit capability fallback for this development environment, not a replacement for the agreed native lakehouse. It uses JSON immutable datasets, **not Delta tables**. P01 remains open until its native and provider gates are completed. The subsequent agentic and streaming/ML projects have not started.

## What the demonstration does

1. Read customers, orders and order lines in one SQLite read transaction; products from CSV; shipments through real, bounded HTTP pagination.
2. Bind an immutable run plan to contract/profile/code/runtime hashes, an upper timestamp and the previously accepted generation.
3. Preserve original inputs in Bronze. Type and reconcile Silver, rejecting both members of a duplicate key and conflicting same-timestamp updates.
4. Materialize customer/product/site snapshot dimensions and run a reviewed SQL fact model for order fulfillment. Reconcile line counts, keys and exact Decimal/cents totals independently.
5. Write a candidate dataset without exposing it to reporting. Atomically accept its pointer and watermarks in the state database only after verification.
6. Serve site-scoped reports through FastAPI. Readers cannot see another site's records, totals, catalog or global evidence.
7. Demonstrate rejection, interruption and recovery, with data version and freshness visible to consumers.

## Run the reference slice

Python 3.12 or 3.13 is the declared target; the local qualification exercised **3.13.5**. Use a new virtual environment and a working dependency index:

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

The qualification requires a **new output directory**. It does not delete or overwrite previous runs. Its `evidence/` directory contains receipts, API observations, a recovery timeline, local catalog/lineage and HTML exports from actual authorized API responses. Its `work/` directory contains synthetic source databases and runtime state; do not publish that directory automatically.

No external data, model, production credential or cloud endpoint is used in this reference path. Source and reporting HTTP services bind to loopback and are stopped before the script exits. The script uses an intentionally abrupt child-process exit, explicitly opted in for the synthetic fixture.

### Interactive use

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

The access-policy helper prints two random demonstration tokens once. Keep them outside Git and use them on the local report page or as `Authorization: Bearer ...` headers. `GET /api/report`, `/dashboard` and `/api/orders/{id}` enforce site scope. Catalog/evidence permissions require the full site scope. The `status` and report CLI open the journal read-only; they do not initialize an absent runtime.

The fixture timestamp is fixed for repeatability. A report created later is correctly marked stale; successful loading is not proof of freshness. The source generator accepts an explicit anchor for a new dataset.

## Contracts and business model

`contracts/sales.json` describes five entities: customers, products, orders, order_lines and shipments. Three sites and EUR-only amounts are deliberate. On-time quantity counts units delivered by the promised timestamp; it is **not** an order-level OTIF measure.

`profiles/reference.json` and `profiles/native.json` describe execution, not business meaning. Operations are selected from reviewed code, never arbitrary SQL or Python stored in metadata. The original `ilc-contract/1` format is **not claimed ODCS-compliant**.

See [CircleCI execution and budgets](docs/CI_CIRCLECI.md), [contracts](docs/CONTRACTS.md), [architecture](docs/ARCHITECTURE.md), [recovery](docs/RECOVERY.md), [security](docs/SECURITY.md), [qualification](docs/QUALIFICATION.md), and [remaining gates](docs/PROVIDER_GATES.md).

## Native qualification — bounded cloud route, acceptance still open

The native adapter is implemented using psycopg source reads/state transactions, Spark SQL, Delta version-pinned writes/reads and a Dagster job. Publication now requires a second reconciliation at the **final target path after rename**, not just at its former staging location. Reporting and accepted retries require the bound final-readback proof. Native decimal normalization preserves the contracted scale. These engine paths have not run in this container; injected verifier tests are not native execution. No missing dependency causes a silent downgrade.

Candidate direct versions: PostgreSQL 16, Java 17, PySpark 4.0.1, Delta Spark 4.0.1, Dagster 1.11.16, psycopg 3.2.13. The CircleCI job provisions these in a disposable environment and records resolved versions; the authoring container has not executed this stack. Only accepted runtime receipts can qualify the combination. The first cloud attempt failed; reviewing the selected browsers image exposed a Java 11 incompatibility. The corrected job uses a checksum-verified Temurin 17 bootstrap. This is not a confirmed diagnosis of the private failed-step log.

Use only a dedicated disposable database whose name begins with `ilc_demo`, on loopback. Initialization requires `ILC_ALLOW_NATIVE_DEMO=1`. Existing source tables are refused, not truncated. CircleCI is the active runner, with an exact native branch or explicit `run_native` parameter and a 35-minute command watchdog. Setup-branch synchronization does not duplicate builds. `infra/compose.native.yml` and `.github/workflows/native.yml` remain alternative prepared routes, not proof that they work. Consult [the runbook](docs/RUNBOOK.md) before running them.

## Scope limitations

This is a bounded single-host implementation. Sources are fully captured under explicit row/byte budgets before incremental selection; no source-pushdown scalability is claimed. Each accepted generation writes a complete materialized candidate. No CDC/delete capture, distributed exactly-once, automatic retention, multi-host fencing or high availability is provided. Reference same-path SQLite backup/restore is tested; PostgreSQL/Delta disaster recovery and path migration remain unqualified. The synthetic manifest checks a shared fixture's source vector; it is not a distributed transaction over independent production systems.

An owner with filesystem/database write access is outside the report API's security boundary. Cryptographic hashes detect drift; they are not signatures. Integrity checks read immutable artifacts and are not yet optimized for large reporting volumes. No customer code, schema, identifier or document is incorporated.

## Governance and recovery increments

The metadata-only OpenMetadata publisher exports owners, classification, 15 base
tables, 11 lineage edges and one accepted quality result. Its durable outbox
records intent before mutation, reads results back, reuses an exact remote object
after a lost response, and refuses an unresolved result or conflicting object.
The real HTTP test peer is a **protocol emulator**. No OpenMetadata server or
native catalog RBAC is claimed. See [governance](docs/GOVERNANCE.md).

Reference backup holds writer locks and uses SQLite's backup API, including the
governance outbox but excluding bearer policies. Restore refuses an existing root
and a changed path identity. The demonstration preserves the original runtime,
restores, rereads the report over HTTP and replays an accepted key without the
HTTP source. See [backup and restore](docs/BACKUP_RESTORE.md).

Check the available capabilities without initializing services:

```bash
python scripts/check_environment.py --output artifacts/environment.json --check-public-dns
```

Exit 2 is an explicit missing-native-dependencies gate, not a failed business
pipeline or a passing native test. The supplied environment receipt records
missing psycopg/PySpark/Delta/Dagster, absent PostgreSQL/Docker binaries and public
package/JAR DNS failures. That receipt describes the original authoring environment. The project now runs reference CI in CircleCI; it still uses no personal computer or client system as a fallback.

## Publication status

The source is published in the private `mehdisafer/industrial-lakehouse-contracts` repository, under Draft PR #1. `main` is not merged. Reference CircleCI status is successful; native/provider acceptance, public visibility, license and final disclosure review remain open. The exact code qualification candidate is `fc1a9286c937deb09b87b97524c6835b24a1d516`; subsequent documentation-only updates do not claim a new runtime test. The package intentionally contains no invented open-source license grant. Until the owner chooses one, do not infer redistribution terms from the presence of source code.

**Résumé français.** P01 démontre actuellement un parcours de référence exécutable : contrats, trois sources réelles locales, contrôles métier, reporting autorisé et reprise après arrêt brutal. La restauration SQLite et les tests de protocole gouvernance complètent ces preuves. Il ne faut pas le présenter comme une plateforme Spark/Fabric/OpenMetadata qualifiée. Ces intégrations restent les prochaines étapes du même projet, avant le lancement de P05 puis P03.
