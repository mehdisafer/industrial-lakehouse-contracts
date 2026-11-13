# Qualification status and remaining work

I use execution evidence, not library installation or implementation status, to
accept an integration. The [baseline register](STATUS.md) is the concise source
for current qualification states; detailed historical reviews retain their own
source revision and provenance.

## Native processing — accepted

**Executed revision:** `fc1a9286c937deb09b87b97524c6835b24a1d516`.

PostgreSQL capture/state, PySpark transformation, final-path Delta readback and
in-process Dagster execution were reviewed with the six application scenarios.
The accepted scope is bounded synthetic single-host functionality: replay,
controlled post-target interruption, recovery with HTTP offline and PostgreSQL
available, data rejection, reconciliation and application-scoped reporting.
See the [G2 evidence record](evidence/NATIVE_fc1a928_REVIEW.md).

Distributed execution, in-flight executor fencing, database-native reader roles,
HA and PostgreSQL/Delta disaster recovery are not included. Original JUnit-byte
identity and billed-credit accounting remain archival reservations, not failed
functional gates.

## OpenMetadata API integration — accepted

**Executed revision:** `cd09de03d658cb66d5aaa29a8ec677fd17a3f977`.

The real OpenMetadata 1.12.0 deployment was reviewed for two-generation publication,
schema/owner/classification/lineage/DQ readback, exact-parent basic suites, replay,
recovery after client-visible response loss, server-side permission denials and
conflict preservation. See the [G3a evidence record](evidence/OPENMETADATA_cd09de0_REVIEW.md).

Input was newly accepted **reference_sqlite** data. Native and catalogue execution
are separate baselines; no combined native-to-catalogue run is claimed. Dedicated
resource-type roles do not establish multi-tenant namespace isolation. TLS/SSO,
HA, catalogue lifecycle/restore, Airflow/SDK ingestion and product-UI inspection
remain separate work.

## Fabric and Power BI — planned implementation and qualification

[The existing preflight](../fabric/preflight.py) performs opt-in read-only inventory
of a specified workspace. It creates no capacity, workspace, lakehouse, notebook,
pipeline, semantic model or report. Its transport tests are not tenant validation.

The next provider milestone requires:

1. An explicitly authorised tenant, workspace, capacity, identities and cost ceiling.
2. Reproducible deployment of the business contract and synthetic inputs through supported item APIs.
3. A real semantic model/report, with refresh, last-accepted behaviour, site permissions and source-to-BI reconciliation.
4. Recorded run/item/table identity, resource consumption and a reviewed teardown procedure.

This work remains [issue #5](https://github.com/mehdisafer/industrial-lakehouse-contracts/issues/5).
Local Spark and HTML outcomes do not satisfy it. No trial or subscription is
activated by publishing the repository.

## Prioritised engineering backlog

| Work item | Evidence needed before claiming completion |
|---|---|
| Combined native-to-catalogue flow | One executed path binding native acceptance to actual catalogue readback |
| Fully reproducible toolchain | Resolved dependency lock, image digests and tested refresh process |
| Distributed scale | Defined workloads, load profile, measured bottlenecks and cost/resource evidence |
| Operational hardening | Appropriate IAM/TLS, backup/restore, retention, concurrency and failure testing |
| Provider reporting | Actual Fabric/Power BI behaviour under the business and access contract |

These are intentionally separate from professional source publication. A readable,
reproducible repository can expose the existing engineering work without presenting
a roadmap item as an implemented production capability.
