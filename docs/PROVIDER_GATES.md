# Native, governance and provider gates remain open

## PostgreSQL / Spark / Delta / Dagster

Implemented candidate adapters: PostgreSQL read-only repeatable-read source extraction, transactional state/CAS/advisory lock, new synthetic source seeding, Spark typed Silver, Delta version-0 reads, independent Spark SQL Gold and equivalence checks, and a Dagster job. None was executed in the current sandbox: the dependencies are unavailable and external installation failed.

Next evidence required: clean install/build; actual database/JAR versions; new-table refusal; Dagster run identity; final-path Delta reread after directory promotion; source/Gold/consumer reconciliation; interruption and process cleanup in the native path; PostgreSQL reader-role enforcement. The native pytest covers nominal materialization and replay; the additional `qualify_native.py` harness is designed for six acceptance scenarios including final-path readback and process exit. Both remain unexecuted here. Reference failure tests are not native failure tests.

## OpenMetadata

Ownership, classification, local lineage and DQ output exist in `target/catalog/`.
The report API continues to label those **LOCAL_FILE_CATALOG_NOT_OPENMETADATA**.
A separate authenticated publisher now targets the pinned OpenMetadata 1.12.0
request/resource contract. It creates and rereads metadata with a durable outbox.
Unit/MockTransport and actual loopback HTTP tests use a protocol emulator, not a
real product installation. See [governance](GOVERNANCE.md).

Still required: actual local server, dedicated service/teams/classification,
server-side positive and negative role checks, real schema/lineage/DQ ingestion,
UI/readback evidence and interrupted delivery reconciliation. The publisher and
its emulator tests do not close this gate.

## Fabric / Power BI

`fabric/preflight.py` is an opt-in **read-only** inventory of a specified workspace, with scoped pagination. Its HTTP tests do not contact Microsoft. It does not create a capacity, workspace, lakehouse, notebook, pipeline, semantic model or report.

The provider acceptance task remains: obtain the explicit tenant/workspace/capacity scope, role and cost ceiling; implement deployment using supported content APIs/tools; execute the same business contract; collect native run/item/table versions; build the semantic model and real Power BI report; test refresh, last-accepted behavior, permissions and source→BI reconciliation; export costs and bounded teardown evidence. Never substitute the local HTML report for that Power BI gate.

An evaluation/trial does not establish Terraform capacity support, Data Agent availability, private connectivity or account authorization. Reconfirm current provider documentation when preparing the actual integration. No trial or subscription has been activated.

## Portfolio sequence

P01 is the sole active project. The reference vertical slice is a checkpoint, not closure of the native/provider scope. P05 and P03 stay planned, in that order. Moving to P05 requires a deliberate checkpoint decision; missing P01 integrations must remain visible rather than disappear behind a new project.
