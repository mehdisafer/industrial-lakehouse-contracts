# P01 — CircleCI qualification

GitHub holds code and review; CircleCI provides isolated execution while GitHub Actions admission is blocked by its billing/spending notice. No account plan, payment setting, repository visibility or provider tenant is changed.

## Reviewed native checkpoint

Both jobs succeeded at `fc1a9286c937deb09b87b97524c6835b24a1d516`. The native results have now been reviewed from supplied logs/receipts: one native pytest, six separate scenarios, 14 matching canonical JSON hashes, 20 source-file fingerprints, final-location Delta receipts and recovered reporting. Functional G2 is accepted within its bounded single-host scope. Original raw JUnit hash and actual credits remain reservations. See [the complete review](evidence/NATIVE_fc1a928_REVIEW.md).

Reference success is a separate observation. Its exact hosted test count is not inferred from native collection counts or historical local results. No CI rerun is needed for evidence-only documentation updates.

## Execution routes

Default `reference-qualification` uses one Linux/Python 3.13 Docker job, `.[test]`, compilation, contract validation, the existing Smarter Testing suite and both 10,000-record reference scripts. `run_testsuite_doctor` is false by default because doctor repeats tests. Its execution remains unobserved. There is no configured lint tool or full transitive lockfile; neither is fabricated.

Native uses one Docker `large` job, parallelism 1, `cimg/python:3.12` and disposable `postgres:16`. A bounded bootstrap retrieves official Temurin 17 GA metadata/archive, checks declared size/SHA-256, restricts HTTPS redirects and safely extracts into a fresh runtime directory. It records the resolved JDK and verifies the major version. No OS packages or persistent Java setting are changed. Minor image tags/latest-GA selection are not immutable locks; signature verification is not claimed.

The reviewed runtime reports Python 3.12.16, Temurin 17.0.21+9, PostgreSQL `160015`, Psycopg 3.2.13, PySpark/Delta Spark 4.0.1 and Dagster 1.11.16. Resolved dependency output is recorded separately from direct pins.

Native runs only on `qualify/p01-native-20261112` or with explicit `run_native: true`. Ordinary feature pushes run reference only. The onboarding configuration source `circleci-project-setup` runs no job on ordinary synchronization pushes, avoiding duplication. There is no native matrix, automatic retry, remote Docker, Docker Layer Caching or vendor deployment.

## Resource and credit bounds

The native executor is large (4 vCPU / 8 GB). The main command has a 35-minute timeout plus a 30-second kill grace. Stage limits are Java bootstrap 4 minutes, installation 8 minutes, PostgreSQL readiness 60 seconds, native pytest 10 minutes and scenario harness 20 minutes; the outer watchdog takes precedence.

This bounds the command, not the account bill. Provisioning, checkout and artifact upload are outside it. The reviewed command took 272 seconds and the job UI showed 4m39s. Actual credits are unreported (`billing_credits_observed=null`); no bill is inferred from timing. The pricing documentation linked below is a reference to recheck, not an observed charge. Only two native attempts were triggered for the reviewed change: one failed, then one succeeded. No paid refill or allowance change was made.

## Commands and evidence gate

`scripts/run_circleci_native.sh` checks CircleCI, repository origin, exact checkout, synthetic opt-ins and loopback `ilc_demo` targets. It installs dependencies, runs `pip check`, captures versions and executes:

1. The real native-marked pytest case.
2. `scripts/qualify_native.py --rows 10000`, using PostgreSQL, Spark SQL, version-0 Delta writes/final-path reads and Dagster `execute_in_process`.
3. `scripts/verify_native_ci.py`, rejecting skipped/error tests, wrong/dirty source identity, source drift, incomplete scenarios, absent PostgreSQL/Dagster evidence and mismatched readback proof bindings.

The gate requires all six application cases, 10,000 clean-batch captured records, 3,980 facts, exact count/key/Decimal reconciliation, ten final-path Delta table receipts and recovered generation 2. Logs, JUnit, environment, attempt receipt, dependency list and both acceptance/readback proofs are artifacts. Only synthetic evidence is uploaded, never runtime bearer policies or source databases.

The verifier unit tests use synthetic receipts; they are not native execution. The actual cloud native test and harness provide the executed evidence. The subsequent review reconciles supplied artifacts; it is not independent re-execution or a signed attestation.

## Scope and history

Spark runs `local[2]`; Dagster runs in process. Reporting consumes JSON projections reconciled against Delta, not Direct Lake. The fault follows synchronous Spark stop/target relocation, not an in-flight executor action. PostgreSQL stays available. Distributed scale, HA, native database permissions, PostgreSQL restore, real OpenMetadata and Fabric/Power BI remain separate gates.

Before native qualification, reference success was observed on `840ac5e` and `22bbec3`; historical local V3 had 193 successes and one native skip. Those results do not become tests on later revisions.

The first native job `9395f4f` failed. Reviewing the browsers image exposed a Java 11 compatibility defect; the corrected `fc1a928` uses explicit Temurin 17 and succeeded. This establishes the fix and later result, not the exact unread first failed step. Bootstrap regression tests use synthetic archives/stub transports and are reported separately.

## Reference documentation

These links were used during the original CI design; mutable offerings should be rechecked before changing resource or billing choices.

- https://circleci.com/docs/guides/execute/using-docker/
- https://circleci.com/pricing/price-list/
- https://circleci.com/pricing/
- https://circleci.com/developer/images/image/cimg/python
- https://circleci.com/docs/reference/configuration-reference/
- https://docs.delta.io/releases/
- https://github.com/CircleCI-Public/cimg-python/blob/main/3.12/browsers/Dockerfile
- https://adoptium.net/installation/archives/
- https://adoptium.net/installation/ci-scripts
