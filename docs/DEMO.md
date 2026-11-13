# Demonstration walkthrough

## Business question

For a fictional three-site manufacturer, which accepted order-fulfillment
snapshot can a reporting consumer trust after a rejected batch or an interrupted
publication? This project makes that decision explicit rather than equating a
successful extraction with publishable data.

## A short repository tour

1. Read `contracts/sales.json` and `profiles/reference.json`: entities, fields,
   owners, sites, incremental boundaries and resource budgets are explicit.
2. Follow the reference command in the root README. It starts only disposable
   loopback services, captures five synthetic entities and writes evidence.
3. Inspect the generated reporting HTML and JSON: generation, batch, freshness,
   contract and target manifest are visible alongside exact monetary totals.
4. Inspect the recovery/governance demonstration. Its catalogue peer is an
   emulator; compare it with the separate real-product G3a evidence, not with
   an invented vendor screenshot.

## Reviewed checkpoints

| Scenario | Observed consumer outcome |
|---|---|
| Nominal 10,000-record input | 995 orders and 3,980 facts; ordered amount 8,857,766.18 EUR |
| Duplicate key / invalid amount / schema drift | Candidate rejected, no promotion or watermark advance |
| Process exit after native target materialization | Candidate retained; last accepted generation remains reportable |
| Resume with source HTTP offline | Frozen Bronze/target reused; one generation-2 publication |
| Intended SITE_A revision | Ordered amount 8,857,786.18 EUR; no extra facts or orders |
| Scope violation | Expected application HTTP 401/403/404 responses |
| Catalogue replay | No additional mutation |
| Lost catalogue response | Existing server object reconciled rather than recreated |

The fixed fixture time is deliberate: `STALE` distinguishes old data from failed
processing. `DEGRADED` identifies a rejected latest attempt while retaining the
last accepted data. Neither flag is silently hidden for presentation.

## Inspect the real catalogue proof

The [G3a review](evidence/OPENMETADATA_cd09de0_REVIEW.md) records two actual
OpenMetadata generations with 15 tables and 11 lineage edges each. Bronze is
catalogued as raw serialized strings; Silver and Gold preserve their declared
semantic types. Owners, synthetic classification, exact parent-table suites and
external reconciliation results are read back through the API.

The HTML readback is a static API-derived list, not the OpenMetadata UI. There
is no public service endpoint or hosted Power BI report in this preview.

## Reproducibility and scope

Run from the repository root in a new environment. Do not reuse prior output
paths, production databases or client credentials. Full setup, runtime evidence,
retention limits and error handling are in [RUNBOOK.md](RUNBOOK.md).
The [native evidence review](evidence/NATIVE_fc1a928_REVIEW.md) and catalogue
review identify separate commits and profiles. Correctness on bounded synthetic
fixtures is not a distributed throughput benchmark or business ROI claim.
