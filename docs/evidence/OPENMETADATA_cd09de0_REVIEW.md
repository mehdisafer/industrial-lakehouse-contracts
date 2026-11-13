# OpenMetadata G3a — reviewed bounded functional acceptance

## Decision and exact execution

I accept the **bounded API-publisher qualification on an isolated OpenMetadata
1.12.0 server** at `cd09de03d658cb66d5aaa29a8ec677fd17a3f977`.
The review was completed on 13 November 2026 from supplied CircleCI outputs and
uploaded JSON/log files, after the successful catalogue and reference jobs.
It is not an independent maintainer approval, signed attestation or new execution.

- [Catalogue job](https://app.circleci.com/workflow/44a92cbe-4817-45b8-8df2-70e106367dc9/job/167d2f85-ca05-45a5-a6a7-937bf513354b)
- [Executed source](https://github.com/mehdisafer/industrial-lakehouse-contracts/tree/cd09de03d658cb66d5aaa29a8ec677fd17a3f977)
- [Machine-readable review](OPENMETADATA_cd09de0_REVIEW.json)

The input was a fresh **reference_sqlite** accepted generation. Native
PostgreSQL/Spark/Delta/Dagster was qualified separately at `fc1a928`.
This does not claim a combined native-to-catalogue execution.

## Results actually reconciled

| Area | Reviewed observation |
|---|---|
| Product | OpenMetadata 1.12.0; API revision `caa14bfd42af6ec84464aa81815addd3e0cd2902` agrees with server/migration image labels |
| Source | Exact clean commit; 20 application manifest files and the live qualification script match the retained source bytes |
| Generations | Two separately accepted 10,000-record batches, each producing 3,980 facts |
| Tables | 15 per generation, 30 distinct remote table UUIDs; five Bronze, five Silver and five Gold per generation |
| Columns | 170 definitions compared, including names, types, nullability and decimal precision/scale |
| Ownership/classification | Dedicated synthetic team and `ILCSynthetic.PUBLIC_SYNTHETIC`, confirmed on every table |
| Lineage | 11 edges per generation, 22 endpoint pairs reconciled to exact table UUIDs |
| Data quality | Two external reconciliation results; two basic suites bound to their exact fact-table UUID/type |
| Reconciliation | 8,857,766.18 EUR then 8,857,786.18 EUR after the intended +20 EUR fixture revision |
| Replayed publication | Zero mutations; existing accepted metadata reused |
| Lost response | Exactly one database PUT; injected response loss follows real server HTTP 201; subsequent GET finds the object |
| Conflict | Five reads, zero mutations; existing sentinel preserved |
| Permissions | Server logs corroborate 401 unauthenticated read, 403 reader PATCH and 403 writer policy POST; forbidden policy GET returns 404 |
| Cleanup | Job receipt reports service-stop exit 0 and VM sysctl-restoration exit 0; no volume deletion |

The review checked 250 HTTP access records in the supplied server-log excerpt.
No HTTP 5xx occurs in that excerpt; this is not a statement about every possible
server log or an operational SLO. The initial publisher trace has 33 mutations;
the recovered generation has 32 because the shared test definition already exists.
`operations_verified=33` is not the number of mutations in every invocation.

## Hashes, envelopes and reconstruction

All **15 entries in the supplied artifact manifest** match: 14 canonical JSON
files plus one HTML file reconstructed with the exact executed formatter and
plan order. The HTML was not supplied as original bytes. JSON reconstruction
uses the repository's sorted-key, compact UTF-8 format with a trailing newline.
The machine-readable review retains each expected digest.

The offline review completed **463 assertions**. These are audit assertions,
not 463 additional cloud tests. The separately recorded JUnit has 33 offline
harness-safeguard tests; six live G3 scenarios run in the qualification script.

The published acceptance digest binds the journal's immutable receipt, excluding
the caller's `invocation` return-envelope field. Recomputing that exact object
matches both plans and DQ results. The downloadable acceptance file includes the
field and therefore has a different file hash; this is an intentional distinction,
not an unexplained mismatch.

`catalog_provider=NOT_RUN` in the earlier data-acceptance receipt describes that
pipeline operation. The subsequent `REMOTE_METADATA_READ_BACK` receipt and live
G3 result establish the separate catalogue publication. Historical receipts are
not rewritten to pretend that two operations were a single transaction.

## Runtime identity and timing

Resolved Linux/amd64 image digests, recorded by CI:

| Image | Repository digest |
|---|---|
| PostgreSQL 16 | `sha256:63e83b5a3dc36a917dccb76fe1bd2ac51f1ec9c1deb47ff20d4f04233bf6eae9` |
| Elasticsearch 9.3.0 | `sha256:4f6bdcb742e892539c6ac49b0dd3e4e182e90218546e8c6a22db378c344acb60` |
| OpenMetadata 1.12.0 | `sha256:c11deba30a45e61071955a48838cb0b84a403c5b79a8c4f48f9a89ebb19dd5fa` |
| cimg/python 3.12 | `sha256:a78dfb790fe48e58b792c6499495de0630d33edb377a92840e726d40320a33ea` |

These identities were not independently pulled or signature-verified during
review. Future executions still resolve the configured tags; this is an observed
image record, not a complete immutable dependency lock.

The command receipt records 158 seconds; live checks record 20.831684 seconds.
Those scopes overlap and are not additive. The 25-minute watchdog excludes runner
provisioning and artifact transfer. Actual billed credits remain **unknown**.

## Warnings and retained limitations

Migration exits 0, but its logs are not clean: missing-relation queries occur
while initializing the empty database, `SET LOCAL` warnings are present and
Logback core/classic versions differ (1.5.19/1.5.18). Later successful product API
checks support this bounded gate, not a claim that upstream startup warnings are
fixed or suitable for production. The first failed catalogue attempt remains an
unread failed-step history; the later gzip/basic-suite corrections do not prove
its precise root cause.

The supplied JUnit is a browser-rendered copy containing an extension-added
script; original XML bytes/hash are unverified. No script was executed and no
cleaned copy is represented as an original. Raw service logs and this modified
browser XML are not included in the public evidence summary.

This is dedicated-instance resource-type RBAC, not multi-tenant isolation. The
loss is injected in the client after a real successful response, not a physical
network outage. Metadata and aggregate DQ only are exported; no sample records.
TLS/SSO, distributed scale, HA, catalogue restore/retention, Airflow/SDK ingestion,
product-UI inspection, Fabric/Power BI and production operation are not qualified.

The first native G2 evidence remains separately documented in
[NATIVE_fc1a928_REVIEW.md](NATIVE_fc1a928_REVIEW.md).
