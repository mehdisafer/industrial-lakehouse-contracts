# P01 — CircleCI qualification

I keep the repository and reviews on GitHub; CircleCI is the independent runner while GitHub Actions admission is blocked by a billing/spending-limit notice. No payment method, plan, repository visibility or vendor tenant is changed here.

## Execution routes and resource bounds

The default `reference-qualification` workflow uses one Linux/Python 3.13 Docker job and the existing Smarter Testing suite. It installs `.[test]`, compiles Python, validates contracts, executes pytest and both 10,000-record reference qualifications. The `run_testsuite_doctor` parameter stays false by default: doctor repeats tests and is not run on every commit. There is no configured lint tool or transitive lockfile; neither is claimed.

The native route uses **one** Linux Docker `large` job (4 vCPU / 8 GB), `cimg/python:3.12-browsers` for Python and Java, and an isolated `postgres:16` service. Java must be 17 or 21. The actual patch versions are recorded, rather than treating mutable minor image tags as an immutable environment. Native dependencies remain pinned in `pyproject.toml`: Psycopg 3.2.13, PySpark 4.0.1, Delta Spark 4.0.1, Dagster 1.11.16.

Only these events select the native workflow:

- a push to the exact qualification branch `qualify/p01-native-20261112`, reserved for deliberate native qualification changes;
- an explicitly triggered pipeline with `run_native: true`.

Ordinary feature pushes do not run native jobs. The `circleci-project-setup` branch remains the onboarding configuration source; its ordinary pushes run **no job**, avoiding duplicate reference/native work when its tree is synchronized. There is no matrix, parallel native job, SSH rerun, automatic retry, Docker Layer Caching or vendor deployment.

`timeout` bounds the native command to 35 minutes (plus a 30-second kill grace). Individual stages are also bounded: installation 8 minutes, PostgreSQL readiness 60 seconds, native pytest 10 minutes and the six-scenario harness 20 minutes. The outer watchdog takes precedence. This is **not an account-level billing cap**: image provisioning, checkout and artifact upload are outside that command. The published gen1 Docker large price is 20 credits/minute, so 35 minutes corresponds to 700 command-time compute credits, plus overhead. Actual usage must be read from CircleCI. No allowance, paid refill or exact cost is fabricated.

## What the native job really executes

`scripts/run_circleci_native.sh` checks the project, commit and synthetic opt-ins before use. It installs the existing optional dependencies, checks their consistency, connects only to the disposable loopback `ilc_demo` database, records Java/Python/PostgreSQL versions, and runs:

1. The real `native`-marked pytest case, without skip being accepted as a result.
2. `scripts/qualify_native.py --rows 10000` with real PostgreSQL, Spark SQL, Delta version-0 writes and final-location readback, and a real Dagster `execute_in_process` job.
3. The six native application scenarios: replay, process exit after target commit, invalid-input rejection, source-target reconciliation, HTTP application role separation and retained/recovered reporting.
4. `scripts/verify_native_ci.py`, which rejects incomplete/skipped tests, a different source SHA, dirty receipts, changed source bytes, incomplete scenarios, missing PostgreSQL/Dagster evidence or mismatching Delta readback proofs.

The full accepted and recovered Delta readback proofs are exported and bound to their receipts. JUnit, resolved dependencies, bounded logs, stage outcome and application receipts are retained. Only synthetic evidence is uploaded; runtime policy files and source databases are excluded. The service password in the config is exclusively a disposable CI fixture, not a shared account credential.

A success status for `native` is evidence that the configured gate returned zero; final reporting still distinguishes that status from independent inspection of the private JUnit and artifact contents. The verifier's own regression tests use synthetic documents and do not qualify PostgreSQL or Spark.

## Scope of native success

This is bounded single-host execution with Spark `local[2]`. The source fixtures include PostgreSQL tables, a paginated loopback HTTP source and a CSV. Dagster executes the job in process, not a distributed daemon/agent deployment. The report consumes JSON projections independently reconciled to Delta, not Power BI Direct Lake. The recovery failpoint occurs after synchronous materialization/stop and target relocation, not during an in-flight Spark action.

No claim is made for distributed scale, high availability, database-native role isolation, PostgreSQL backup restoration, a real OpenMetadata service, Fabric or Power BI. Those remain separate acceptance gates. P05/P03 remain queued behind P01.

## Current evidence boundary

Before this native change, CircleCI reported reference success on feature `840ac5e` and setup `22bbec3`. Previous local V3 evidence reported 193 passed tests and one native skip. Those historical results are not transferred to a new commit. Native cloud attempts and their exact SHAs, job URLs and results are recorded in PR #1 and issue #3 after observation.

## Sources checked 12 November 2026

- CircleCI Docker resources: https://circleci.com/docs/guides/execute/using-docker/
- CircleCI pricing: https://circleci.com/pricing/price-list/
- CircleCI Free resource availability: https://circleci.com/pricing/
- Python image variants: https://circleci.com/developer/images/image/cimg/python
- Conditional workflows: https://circleci.com/docs/reference/configuration-reference/
- Spark/Delta compatibility: https://docs.delta.io/releases/
