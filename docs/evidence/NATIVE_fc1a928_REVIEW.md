# Native P01 evidence review — fc1a928

## Decision and exact scope

I accept the bounded synthetic, single-host PostgreSQL / PySpark / Delta / Dagster functional qualification on commit `fc1a9286c937deb09b87b97524c6835b24a1d516`, with the archival reservations below. This is not acceptance of all P01, a production release, a distributed benchmark or an independent maintainer approval.

CircleCI workflow `9567a630-4dd6-487a-9759-0ea538f442c1`, job `d758140f-292d-4177-bb95-68feff064fb6`, project job number 8. The successful native run and the reference run both report success in GitHub. This review consumes existing results; it starts no new pipeline.

Evidence was supplied as copied CircleCI output and three text attachments, not through a direct authenticated artifact download. The qualification summary was recovered from the complete native log, not fabricated to fill a missing file. Duplicate copies of the Java receipt, recovery timeline and initial report are counted once.

## Reconciled observations

| Item | Observed result |
|---|---|
| Command receipt | Exit 0, phase `completed`, 272 seconds |
| Native pytest | 1 passed; 234 deselected; 0 errors, failures or skips; 2 deprecation warnings |
| Pytest suite duration | 62.078 seconds; the one testcase records 61.612 seconds |
| Separate scenario harness | Six scenarios, 139.895874 seconds |
| Python / Java | Python 3.12.16; Temurin 17.0.21+9 |
| PostgreSQL | `server_version=160015` in the environment and five synthetic seed receipts |
| Data engine | PySpark 4.0.1, Delta Spark 4.0.1, Dagster 1.11.16, Psycopg 3.2.13 |
| Dagster | In-process `accepted_sales_job`, run `35cfb69b-d401-4378-b4f7-27e42b0f8ff8`, explicit `RUN_SUCCESS` in the log |
| Source volume | 10,000 records per clean batch, not per entity; 1,621,039 Bronze bytes |
| Gold | 3,980 facts, 995 orders; exact source/Gold Decimal totals |
| Delta | Ten final-path table receipts per accepted batch, all version 0 |
| Reporting | Generation 1 retained during rejected loads; generation 2 consumes the recovered batch |

The six harness scenarios are not six additional pytest cases. The 235 collected cases were not all executed by `pytest -m native`. The independent reference job's exact test count is not inferred from this native result.

### Scenario findings

- **V-P01-01:** same-key replay retains the accepted batch and generation 1.
- **V-P01-02:** controlled child exit 73 after synchronous materialization and target relocation; watermark and accepted pointer unchanged before resume; HTTP source stopped; Bronze and target reused; one generation-2 publication. PostgreSQL remained available.
- **V-P01-03:** duplicate-key members (2 rows), invalid amount (1 row) and schema drift (4,975 shipment rows) are quarantined. Each attempt is `REJECTED`, with `dataset_promoted=false` and `watermark_advanced=false`.
- **V-P01-04:** 30 customers + 20 products + 995 orders + 3,980 lines + 4,975 shipments = 10,000. Source and Gold total 8,857,766.18 EUR for the initial batch.
- **V-P01-05:** application HTTP checks return 401 without authentication, 403 for cross-site/catalog/evidence access and 404 for another site's order. This does not qualify database or cloud-native RBAC.
- **V-P01-06:** rejected attempts preserve generation 1 and all totals while exposing `DEGRADED`. Recovery publishes generation 2 with 8,857,786.18 EUR. The +20.00 EUR change is solely SITE_A and matches deterministic fixture revision 1; quantities, order counts and fact counts are unchanged.

The recovery timeline has one `ADMITTED`, two `ATTEMPT_STARTED`, `BRONZE_REUSED`, `TARGET_RECONCILED` and one `PUBLICATION_AND_WATERMARK_COMMITTED`. The recovered receipt has `invocation=RESUMED` and `target_reused=true`. Its successful attempt duration is 22.657998 seconds, not a production RTO.

`STALE` is expected: dataset time is fixed at 10:00/11:00 UTC, report generation is around 21:35/21:37 UTC and the freshness budget is 3,600 seconds. Acceptance and freshness are separate states. `business.status=PASS` inside a rejected receipt covers one subset of checks; row/schema rejection still blocks publication.

## Hash and source reconciliation

I reconstructed JSON using the actual `src/ilc/canonical.py` rule: sorted keys, compact separators, UTF-8, no non-finite numbers and one trailing LF. **All 14 reconstructed receipt SHA-256 values match the supplied `verified-evidence.json` manifest.** This is a reproducible comparison of supplied contents to the supplied manifest, not a signed external attestation or a claim of direct download.

| Receipt | Matching SHA-256 |
|---|---|
| accepted-final-readback.json | `07daf93b5245fef01ccca58c39de4034b55b6ba5355043d96871a0668cf271e7` |
| accepted-receipt.json | `aca8977d21b4d65456cfdbe081693a5a6412cf898a6151f85b55e661c1172e5d` |
| duplicate_key-rejection.json | `397038fbd7d16cf8e721b237de3944a802ce28007420052cc4382d592f825d93` |
| duplicate_key-report.json | `d7481bf2d979bbcec3fa52d7034dd05ab9ead25a817f4d32659fdfaaa9c50678` |
| invalid_amount-rejection.json | `ba240eee4c2165eb593675da10baa18ec0d5fba318fb1c3a39dca668f808df1e` |
| invalid_amount-report.json | `6c28dea6167424f56b81cfbab31f1811a8f5121e9926c1ab00f4657e3e23505c` |
| native-final-readback.json | `cba506bdc13ea240dfd9a644a57f569c842ca4ca4512037dfc4c274d7365a346` |
| qualification-native.json | `ad8d8c443e007860cf1581f7813b54fdedf81767704ac434e70508c37f8278c8` |
| recovery-receipt.json | `5ca9d1d2acd186fc4df23d86b489cd53c3a5693115bffcf5ad5ee7f8f83e9f32` |
| recovery-timeline.json | `5a18e1e2201ce46a857ed73d95102543a66f13468eabb12862ace77bf0f94b56` |
| report-before-faults.json | `d47926051ed1a50737751972b96d8980b7e9f268d264d2fc460ee58d5861bdf1` |
| report-recovered.json | `62f327a529c82a4cae10e14e5df33f00e3d9f4bc3ab7774e25605ac3cb9043a5` |
| schema_drift-rejection.json | `7aa42936f6573f1439c77736bdfc8d84af5e8f304f0b6ccc7a83848d41325151` |
| schema_drift-report.json | `db071615861a998d1d0328e93d152275fd38e4632ceff453104720836fdc4441` |

All 20 entries in the runtime source manifest match the retained source bytes. Their `src` Git subtree is `f489fc838570b61b90ad6ef353f3259c42b064e2` and the `pyproject.toml` blob is `2c7eb05812a6f9fa6c2e64e4c75c74a0d7774211`; both match the authenticated GitHub tree at the executed commit. The aggregate code hash and contract hash also match both acceptance receipts. The two final-readback proofs bind to the correct batch IDs, target manifests, table counts and versions.

A separate offline review script completed 144 consistency assertions across these supplied documents, source fingerprints, Decimal sums, chronology and fixture generation. This number is an audit-check count, **not 144 new hosted tests**. No PostgreSQL or Spark pipeline was rerun for this review and physical Delta data files were not downloaded again.

## Reservations and limits

1. The pasted JUnit is a browser-rendered document containing a `chrome-extension://` script element. Its testcase/counter content agrees with the pytest console, but it is not the original XML bytes. The declared raw SHA-256 `9bd483cc767e67f2d24739e449bdee9c2c10da911d8f0b6a630fbc379ee1425b` is **not independently verified**. No script was executed or silently removed to manufacture a matching original.
2. The Java receipt reports SHA-256 integrity for Temurin 17.0.21+9 and explicitly says signature verification `NOT_RUN`. The JDK binary was not downloaded again for this review.
3. Actual CircleCI credits remain unknown: `billing_credits_observed=null`. The command duration is 272 seconds; the prior UI screenshot shows 4m39s for the job. These are different scopes, not a bill or throughput benchmark.
4. The first failed native attempt remains failed; its precise failed-step cause is not established by the later success. Deprecation warnings in the successful pytest do not constitute test failures, but should be considered when upgrading dependencies.
5. This is Spark `local[2]`, in-process Dagster and application API roles. No distributed scale, HA, in-flight Spark fencing, database-native reader role, PostgreSQL restoration, live OpenMetadata, Fabric, Power BI or Direct Lake acceptance is claimed.

Functional G2 evidence is accepted within this boundary. Issue #3 remains open only to track original-XML archival and actual credit usage; these reservations do not require a new native run and do not prevent the next P01 engineering gate, real OpenMetadata (#4). Fabric/Power BI remains #5. P05/P03 have not started; main, visibility, license and billing settings are unchanged.
