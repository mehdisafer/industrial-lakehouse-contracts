# Changelog

## 2026-11-13 — professional review and maintenance checks

- Reorganised the README and documentation around the business problem, reproducible demonstration, data model and architecture decisions.
- Reconciled current native/catalogue acceptance across the operating and design guides; retained historical execution records.
- Added a machine-readable qualification-baseline register and a generated status page.
- Added offline repository checks and regression tests for documentation links/anchors, status drift and accidentally tracked runtime/sensitive paths.
- Integrated the repository check into reference CI alongside the existing history disclosure gate.
- Added contribution/security entry points, structured issue forms, a PR checklist and local-file ignore rules.

Runtime algorithms, dependency versions, integration baselines, licensing and
repository visibility are unchanged by this maintenance pass.

## 2026-11-13 — initial portfolio preview

- Contract-driven ingestion, blocking quality, exact reconciliation and accepted-generation reporting.
- Native PostgreSQL / PySpark / Delta / Dagster single-host qualification at `fc1a928`.
- Separate real OpenMetadata API publication, readback, role denials, replay and lost-response recovery at `cd09de0`.
- Reviewed artifact/source identities, with original XML and billing reservations retained.
- Reachable-history disclosure gate and manually selected alternative GitHub Actions routes.

Fabric/Power BI deployment, distributed performance, HA, PostgreSQL/Delta disaster
recovery and an open-source licence grant remain outside this preview.
