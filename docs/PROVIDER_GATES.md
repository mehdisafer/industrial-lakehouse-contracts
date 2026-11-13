# Native, governance and provider acceptance gates

## PostgreSQL / Spark / Delta / Dagster — bounded functional G2 accepted

The reviewed CircleCI run at `fc1a9286c937deb09b87b97524c6835b24a1d516` executed native PostgreSQL capture/state, Spark transformation, final-path Delta reread and an in-process Dagster job. One native pytest and six separate functional scenarios were inspected through supplied logs/receipts. All fourteen JSON fingerprints match after canonical reconstruction. See [the evidence review](evidence/NATIVE_fc1a928_REVIEW.md).

G2 acceptance is limited to synthetic single-host functionality: replay, controlled post-target interruption, offline HTTP recovery with PostgreSQL available, quality rejection, reconciliation and application-scoped reporting. The original browser-rendered XML does not establish its raw file hash; actual credit usage is also unreported. Those reservations remain tracked in #3 without requiring another native run.

Still separate: database-native reader-role enforcement, distributed scale, in-flight Spark fencing, PostgreSQL/Delta disaster recovery, HA, alternate native Docker Compose/Windows routes and production operation. Successful reference or native functional CI does not establish these.

## OpenMetadata — real-server CI succeeded, artifact review pending (#4)

The live catalogue and reference jobs both report success on `cd09de03d658cb66d5aaa29a8ec677fd17a3f977`. The catalogue route provisions actual OpenMetadata 1.12.0, PostgreSQL and Elasticsearch in an isolated CircleCI VM. Its mandatory harness uses authenticated non-admin publication and independent reader readback; emulator tests are not substituted for that command. See [governance](GOVERNANCE.md) and [the live runbook](OPENMETADATA_LIVE.md).

The input is a newly accepted **reference_sqlite** generation. The earlier native G2 run remains accepted and is not rerun. A combined native-to-catalogue execution is not claimed. Local `target/catalog/` output remains accurately labelled `LOCAL_FILE_CATALOG_NOT_OPENMETADATA`; real remote publication is a separate operation and receipt.

Configured success requires two generations, fifteen table definitions and eleven lineage edges per generation, owners/classification/types/DQ and basic-suite readback, mutation-free replay, client-injected response loss after a real write, actual 401/403 refusals and conflicting-object preservation. Private runtime/image/role/readback/trace artifacts must still be inspected and reconciled before accepting G3a. A green status is not an independently verified artifact inventory.

Two catalogue attempts were triggered, not an uncontrolled retry loop: `a99c173` failed, `cd09de0` succeeded after two source-established transport/suite compatibility fixes. The first failed-step log remains unread. Actual credits and cleanup outcomes are not inferred from success. No additional run is required to inspect the existing artifacts.

This is dedicated-server resource-type RBAC, not multi-tenant namespace isolation. TLS/SSO, catalogue HA/restore/retention, SDK/Airflow connector ingestion and actual UI inspection are separate. The generated HTML is an API-derived snapshot, not an OpenMetadata UI screenshot.

## Fabric / Power BI — separate provider gate (#5)

`fabric/preflight.py` is opt-in read-only inventory of a specified workspace, with scoped pagination. Its HTTP tests do not contact Microsoft. It does not create a capacity, workspace, lakehouse, notebook, pipeline, semantic model or report.

The provider task remains: explicitly authorized tenant/workspace/capacity, roles and cost ceiling; deployment using supported APIs; execution of the business contract; native run/item/table evidence; a real semantic model and Power BI report; refresh, last-accepted, permissions and source-to-BI checks; observed costs and bounded cleanup. Local HTML is not Power BI, and Spark local acceptance is not Fabric acceptance.

An evaluation offer does not establish account authorization, Terraform capacity support, Data Agent availability or private connectivity. Recheck provider documentation when implementing the integration. No trial or subscription has been activated by these changes.

## Portfolio sequence

P01 remains the sole active project. Native functional G2 is evidence-backed; the real catalogue has a successful CI route awaiting artifact review. Fabric/Power BI is not silently dropped from scope. P05 and P03 remain planned in that order. Moving on requires an explicit portfolio checkpoint, not relabeling an incomplete provider integration as complete.
