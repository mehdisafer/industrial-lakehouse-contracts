# Qualification methodology

## Current acceptance

The [baseline register](STATUS.md) records the accepted native and real catalogue
revisions. I keep execution identity and scope attached to each result rather
than presenting a single undifferentiated "platform validated" status.

| Layer | What it establishes |
|---|---|
| Unit / safeguard tests | Behaviour under specified fixtures, including labelled injected transports/verifiers |
| Reference scenarios | Real SQLite, files, loopback HTTP, application permissions and process recovery |
| Native scenarios | Actual PostgreSQL, PySpark, Delta and in-process Dagster behaviour |
| Catalogue scenarios | Actual OpenMetadata API, publication/readback and server-role behaviour |
| Artifact review | Consistency of supplied results, identities, digests and business invariants |
| Repository / disclosure checks | Documentation integrity and rule-based source-history scanning |

None of these layers alone establishes distributed throughput, production
availability or vendor deployment.

## Native baseline

**Executed revision:** `fc1a9286c937deb09b87b97524c6835b24a1d516`.

| Scenario | Reviewed observation |
|---|---|
| V-P01-01 | Same-key replay keeps the accepted batch and generation |
| V-P01-02 | Controlled exit 73 after target materialisation; unchanged pre-resume watermark; HTTP offline; frozen input/target reuse; one generation-2 publication |
| V-P01-03 | Duplicate keys, invalid amount and schema drift block publication |
| V-P01-04 | 10,000 captured records, 3,980 facts; exact count/key/Decimal reconciliation; ten final-path version-0 Delta readbacks |
| V-P01-05 | Expected application HTTP 401/403/404 denials |
| V-P01-06 | Last accepted report retained during rejects; recovered generation contains the intended SITE_A +20 EUR revision |

Native pytest selected **one test**, with 234 deselected and zero skipped/errors/
failures. Six scenarios belong to the separate script, not six more pytest cases.
The [G2 review](evidence/NATIVE_fc1a928_REVIEW.md) preserves logs, versions, timing
scope and fourteen matching reconstructed JSON digests.

## Catalogue baseline

**Executed revision:** `cd09de03d658cb66d5aaa29a8ec677fd17a3f977`.

The actual OpenMetadata 1.12.0 run checked identity/authentication, two-generation
readback, mutation-free replay, reconciliation after client-visible response loss,
server-side permission denials and conflict preservation. Its input was newly
accepted reference data, not a rerun of the native data path.

The run has **33 offline safeguard tests** and six separate live scenarios.
Reviewed artifacts contain 30 table UUIDs, 170 column definitions, 22 lineage
edges, two external DQ results and two basic suites. All fifteen supplied artifact
hashes matched: fourteen canonical JSON files and one HTML file rebuilt with the
executed formatter. The [G3a review](evidence/OPENMETADATA_cd09de0_REVIEW.md) records
the precise provenance and limits.

## Interpreting evidence

The fixture contains 10,000 records across five entities, not per table. Its
8,857,766.18 EUR initial total changes to 8,857,786.18 EUR through an intended
fixture revision, not duplicated facts. [DATA_MODEL.md](DATA_MODEL.md) defines the
measures, keys and reconciliation rules.

Acceptance, freshness and degradation are separate. Fixed fixture time can produce
`STALE`; a rejected latest attempt can produce `DEGRADED` while the accepted dataset
remains intact. A passing business sub-check does not cancel a blocking row/schema
failure.

Digests are integrity comparisons, not signatures. The artifact reviews used
supplied copied outputs and uploaded files; they were not independent maintainer
approvals or fresh physical Delta rereads. Catalogue acceptance digests bind the
immutable journal receipt without the invocation return-envelope field; the
downloadable receipt-file hash includes that field.

Original JUnit files were supplied through browser rendering with extension-added
markup, so their original-byte hashes remain unverified. JDK/container identities
are recorded by CI, without an independent image pull or signature assessment.
Those archival reservations remain explicit without requiring an unchanged heavy
job to be rerun.

## Timing, resources and warnings

Native command duration was 272 seconds; catalogue command duration was 158 seconds.
Inner test/harness timings overlap those scopes and must not be added. They are
not throughput benchmarks, production RTOs or actual credit bills. Billed credits
remain unreported.

The catalogue migration completed with initialisation warnings, including
missing-relation queries, `SET LOCAL` messages and a Logback version mismatch.
Successful API checks do not mean those upstream warnings were fixed. Earlier
failed attempts are not retrospectively marked successful by a corrective run.

## Maintaining qualification

Every behavioural change needs appropriately scoped regression evidence. Record
commands, source revision, actual results and exclusions. Do not add overlapping
counts from previous local materialisations or transfer an old JUnit total to a
new hosted run. Repository checks have their own regression tests and do not
requalify the native or catalogue runtime.

Update `qualification-baselines.json` only after reviewing a new integration result,
then regenerate [STATUS.md](STATUS.md). Historical evidence records remain intact.
See [CONTRIBUTING.md](../CONTRIBUTING.md) for the workflow and
[PROVIDER_GATES.md](PROVIDER_GATES.md) for unqualified work.
