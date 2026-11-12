# Native, governance and provider acceptance gates

## PostgreSQL / Spark / Delta / Dagster — bounded functional G2 accepted

The reviewed CircleCI run at `fc1a9286c937deb09b87b97524c6835b24a1d516` executed native PostgreSQL capture/state, Spark transformation, final-path Delta reread and an in-process Dagster job. One native pytest and six separate functional scenarios were inspected through supplied logs/receipts. All fourteen JSON fingerprints match after canonical reconstruction. See [the evidence review](evidence/NATIVE_fc1a928_REVIEW.md).

G2 acceptance is limited to synthetic single-host functionality: replay, controlled post-target interruption, offline HTTP recovery with PostgreSQL available, quality rejection, reconciliation and application-scoped reporting. The original browser-rendered XML does not establish its raw file hash; actual credit usage is also unreported. Those reservations remain tracked in #3 without requiring another native run.

Still separate: database-native reader-role enforcement, distributed scale, in-flight Spark fencing, PostgreSQL/Delta disaster recovery, HA, alternate Docker Compose/Windows routes and production operation. Successful reference or native functional CI does not establish these.

## OpenMetadata — next P01 engineering gate (#4)

Ownership, classification, local lineage and DQ output exist in `target/catalog/`; reporting correctly labels them `LOCAL_FILE_CATALOG_NOT_OPENMETADATA`. The publisher targets pinned OpenMetadata 1.12.0 contracts with authenticated calls and a durable outbox. Unit and real loopback HTTP tests use an explicitly named protocol emulator, not the product. See [governance](GOVERNANCE.md).

Required next: an actual isolated server, dedicated service/teams/classification, positive and negative server-role checks, actual schema/lineage/DQ publication and UI/API readback, plus interrupted-delivery reconciliation. Only synthetic metadata is eligible. The native engine acceptance does not close this product gate and this evidence-review update starts no deployment.

## Fabric / Power BI — separate provider gate (#5)

`fabric/preflight.py` is opt-in read-only inventory of a specified workspace, with scoped pagination. Its HTTP tests do not contact Microsoft. It does not create a capacity, workspace, lakehouse, notebook, pipeline, semantic model or report.

The provider task remains: explicitly authorized tenant/workspace/capacity, roles and cost ceiling; deployment using supported APIs; execution of the business contract; native run/item/table evidence; a real semantic model and Power BI report; refresh, last-accepted, permissions and source-to-BI checks; observed costs and bounded cleanup. Local HTML is not Power BI, and Spark local acceptance is not Fabric acceptance.

An evaluation offer does not establish account authorization, Terraform capacity support, Data Agent availability or private connectivity. Recheck provider documentation when implementing the integration. No trial or subscription has been activated by these changes.

## Portfolio sequence

P01 remains the sole active project. Native functional G2 is now evidence-backed; real OpenMetadata and Fabric/Power BI are not silently dropped from scope. P05 and P03 remain planned in that order. Moving on requires an explicit portfolio checkpoint, not relabeling an incomplete provider integration as complete.
