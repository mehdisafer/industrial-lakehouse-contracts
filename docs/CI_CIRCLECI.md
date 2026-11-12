# P01 — CircleCI qualification

GitHub holds code and review; CircleCI provides isolated execution while GitHub Actions admission is blocked by its billing/spending notice. No account plan, payment setting, repository visibility or provider tenant is changed.

## Evidence checkpoints

**Native G2:** both jobs succeeded at `fc1a9286c937deb09b87b97524c6835b24a1d516`. Supplied native logs/receipts were reviewed: one native pytest, six separate scenarios, fourteen matching canonical JSON hashes, twenty source-file fingerprints, final-location Delta receipts and recovered reporting. Functional G2 is accepted within its bounded single-host scope. Original raw JUnit hash and actual credits remain reservations. See [the complete review](evidence/NATIVE_fc1a928_REVIEW.md).

**Catalogue G3a:** both `reference` and `catalogue` report success at `cd09de03d658cb66d5aaa29a8ec677fd17a3f977`. The catalogue command provisions and exercises the real OpenMetadata product, not the protocol emulator. Its actual private image/role/readback/trace artifacts have not yet been independently inspected, so final G3a acceptance remains open. See [deployment, checks and artifact paths](OPENMETADATA_LIVE.md).

Reference success is a separate observation. Exact hosted test counts are not inferred from collection counts or historical local tests. Documentation-only updates use `[skip ci]`; no rerun is needed to inspect existing evidence.

## Execution routes

Default `reference-qualification` uses one Linux/Python 3.13 Docker job, `.[test]`, compilation, contract validation, the existing Smarter Testing suite and both 10,000-record reference scripts. `run_testsuite_doctor` is false by default because doctor repeats tests. Its execution remains unobserved. There is no configured lint tool or full transitive lockfile; neither is fabricated.

Native uses one Docker `large` job, parallelism 1, `cimg/python:3.12` and disposable `postgres:16`. A bounded bootstrap retrieves official Temurin 17 GA metadata/archive, checks declared size/SHA-256, restricts HTTPS redirects and safely extracts into a fresh runtime directory. It records the resolved JDK and verifies its major version. No OS packages or persistent Java setting are changed. Mutable image tags/latest-GA selection are not immutable locks; signature verification is not claimed.

The reviewed native runtime reports Python 3.12.16, Temurin 17.0.21+9, PostgreSQL `160015`, Psycopg 3.2.13, PySpark/Delta Spark 4.0.1 and Dagster 1.11.16. Resolved dependencies are recorded separately from direct pins.

Catalogue uses one Linux VM `large` job, an isolated Docker Compose stack (OpenMetadata 1.12.0, PostgreSQL 16, Elasticsearch 9.3.0) and a Python 3.12 test container. Its input is a **fresh accepted reference_sqlite generation**, not a rerun of Spark or a combined native/catalogue attestation. Separate generated credentials, a non-admin writer and a read-only consumer exercise server-side authorization. Images are resolved during the job and recorded by digest; those private values await review.

| Trigger | Route |
|---|---|
| Ordinary feature push | Reference only |
| `qualify/p01-native-20261112` or `run_native: true` | Native, unless catalogue is explicitly selected |
| `qualify/p01-openmetadata-20261113` or `run_catalogue: true` | Catalogue, unless native is explicitly selected |
| `circleci-project-setup` synchronization | No ordinary build; synchronization commits also use `[skip ci]` |

Do not enable both heavy parameters. The existing reference and native job bodies were preserved; catalogue has its own workflow. There is no matrix, automatic retry, remote-Docker service, paid cache or vendor deployment. Main is not merged to enable these routes.

## Resource and credit bounds

Native uses a Docker large executor (4 vCPU / 8 GB). Its main command has a 35-minute timeout plus a 30-second kill grace. Stage limits cover Java bootstrap, installation, readiness, pytest and scenarios; the outer watchdog takes precedence. The reviewed command took 272 seconds and its job UI showed 4m39s. Actual native credits are unreported.

Catalogue uses a Linux VM large executor (4 vCPU / 15 GB). Its main command is bounded to 25 minutes plus kill grace, with shorter pull, migration, readiness and live-qualification timeouts. It stops only its job-owned services, retains no shared deployment and records cleanup outcomes. No DROP, TRUNCATE, prune or shared-volume deletion is used.

These watchdogs bound commands, not account bills. VM/image provisioning, checkout and artifact upload are outside them. Actual catalogue credits and cleanup results have not yet been read. No bill is inferred from success or status timestamps. The increment triggered **two catalogue attempts** (one failed, one succeeded), two reference jobs and **no additional native/Spark job**. Setup synchronization and final documentation updates do not duplicate those runs. No paid refill or allowance change was made.

## Native commands and evidence gate

`scripts/run_circleci_native.sh` checks CircleCI, repository origin, exact checkout, synthetic opt-ins and loopback `ilc_demo` targets. It installs dependencies, runs `pip check`, captures versions and executes the native-marked pytest, `qualify_native.py --rows 10000` and `verify_native_ci.py`.

The native verifier rejects skipped/error tests, wrong/dirty source identity, source drift, incomplete scenarios, absent PostgreSQL/Dagster evidence and mismatched readback proof bindings. It requires six application cases, 10,000 clean-batch captured records, 3,980 facts, exact count/key/Decimal reconciliation, ten final-path Delta table receipts and recovered generation 2. Logs, JUnit, environment and acceptance/readback proofs are artifacts. Runtime policies and source databases are not exported.

Its unit tests use synthetic receipts, not native execution. The cloud test and harness supply the executed evidence; review reconciles supplied artifacts, not an independent re-execution or signed attestation.

## Catalogue commands and evidence gate

`scripts/run_circleci_openmetadata.sh` checks repository/commit identity and a fresh job namespace, provisions the disposable stack, waits for the actual API and executes the offline safeguard tests followed by `qualify_openmetadata.py`. The latter emits its success result only after six real-server scenarios: product identity, two generations of metadata/DQ readback, zero-write replay, response-loss reconciliation, permission refusals and preservation of an existing conflicting object.

The response loss is deliberately injected by the client transport after the actual server write succeeds. It is not a physical network-outage claim. The HTML report is derived from API responses, not the OpenMetadata UI. `harness-junit.xml` counts offline guard tests; it must not be described as the six live scenarios. Final acceptance requires `qualification-openmetadata.json`, readbacks, traces, artifact hashes, image identities and the job attempt record. A green status is not a substitute for reading those artifacts.

## Scope, failures and prior evidence

Spark runs `local[2]`; Dagster runs in process. Native reporting consumes JSON projections reconciled against Delta, not Direct Lake. Its fault follows synchronous Spark stop/target relocation and PostgreSQL stays available. Distributed scale, HA, native database permissions, PostgreSQL restore and Fabric/Power BI remain separate gates. Catalogue adds dedicated-server resource-type roles, not TLS, SSO, multi-tenant isolation or SDK/Airflow connector qualification.

The first native job `9395f4f` failed. A source-established Java 11 image defect was corrected at `fc1a928`, which succeeded; the precise first failed step remains unread. Historical V3 reference 193-pass/one-skip evidence and local verifier/bootstrap tests remain distinct, not additive cloud counts.

The first catalogue job `a99c173` failed; its reference job succeeded. Review reproduced a gzip double-decoding error in the new tracing transport and identified the deprecated `executable` suite check. `cd09de0` decodes once under a byte budget and binds the actual `basic` suite to the exact table UUID/type. Seven regression cases cover these corrections. The corrective catalogue and reference jobs succeeded; this does not prove the exact cause in the unread first job log.

Final targeted local tests: **65 passed**, comprising 33 new harness cases and 32 publisher cases. An earlier local run had 219 passed and one native skip on the recovered V3 materialization plus the initial new tests; it excluded 41 earlier GitHub-only CI tests. These sets overlap and do not represent a full current hosted test count. Compilation, shell syntax and YAML structural checks passed; local Docker startup, CircleCI CLI validation and doctor were not executed.

## Reference documentation

Mutable offerings should be rechecked before changing resources or billing.

- https://circleci.com/docs/guides/execute/using-docker/
- https://circleci.com/docs/guides/execution-managed/using-linuxvm/
- https://circleci.com/pricing/price-list/
- https://circleci.com/pricing/
- https://circleci.com/developer/images/image/cimg/python
- https://circleci.com/docs/reference/configuration-reference/
- https://docs.delta.io/releases/
- https://github.com/CircleCI-Public/cimg-python/blob/main/3.12/browsers/Dockerfile
- https://adoptium.net/installation/archives/
- https://adoptium.net/installation/ci-scripts
