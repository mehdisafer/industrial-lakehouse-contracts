# Changelog

## 2026-11-13 — MIT licensing decision

- Adopted the standard MIT License for the original project code and associated documentation, with Copyright (c) 2026 Mehdi Safer.
- Reconciled the README, contribution terms, licensing guide and publication checklist with the explicit licensing decision.
- Declared `MIT` and the root `LICENSE` in Python package metadata. Raised only the build-backend minimum from setuptools 75 to 77.0.3 for PEP 639 support; runtime/integration dependency versions remain unchanged.
- Added checks for the source notice, declared metadata and licence text embedded in the installed editable distribution.

The disclosure review and repository administration remain separate release gates.
No visibility change, public service deployment or change to third-party terms
is made by this licensing increment. Historical execution records remain unchanged.

## 2026-11-13 — validator hardening and auditable reference CI

- Fixed reproduced documentation-check false successes for code-labelled references, malformed HTTP destinations and revision substrings; resolved heading-ID collisions.
- Removed rejected URL/label payloads from diagnostics and added bounded regular-file reads for metadata/documents.
- Aligned tracked-file checks and ignore rules for test results, local SQLite/database outputs, caches and private-key filenames.
- Added test collection bound to the checkout, exact original-JUnit reconciliation and a mandatory reference/recovery evidence verifier.
- Added checks for missing/duplicate tests, unexpected skips, altered source/receipt identities, reporting totals and retained archive integrity.
- Documented parser boundaries, artifacts and failure handling without changing the application algorithms, dependency versions or historical integration baselines.

## 2026-11-13 — professional review and maintenance checks

- Reorganised the README and documentation around the business problem, reproducible demonstration, data model and architecture decisions.
- Reconciled current native/catalogue acceptance across the operating and design guides; retained historical execution records.
- Added a machine-readable qualification-baseline register and a generated status page.
- Added offline repository checks and regression tests for documentation links/anchors, status drift and accidentally tracked runtime/sensitive paths.
- Integrated the repository check into reference CI alongside the existing history disclosure gate.
- Added contribution/security entry points, structured issue forms, a PR checklist and local-file ignore rules.

Runtime algorithms, dependency versions, integration baselines, licensing and
repository visibility were unchanged by those two maintenance passes.

## 2026-11-13 — initial portfolio preview

- Contract-driven ingestion, blocking quality, exact reconciliation and accepted-generation reporting.
- Native PostgreSQL / PySpark / Delta / Dagster single-host qualification at `fc1a928`.
- Separate real OpenMetadata API publication, readback, role denials, replay and lost-response recovery at `cd09de0`.
- Reviewed artifact/source identities, with original XML and billing reservations retained.
- Reachable-history disclosure gate and manually selected alternative GitHub Actions routes.

Fabric/Power BI deployment, distributed performance, HA and PostgreSQL/Delta
disaster recovery were not included. No open-source licence had yet been selected
at that checkpoint; the later explicit MIT decision is recorded above.
