# Demonstration runbook

## Accepted checkpoints and safe scope

Native single-host functionality is accepted at `fc1a928`; real OpenMetadata API
publication is accepted separately at `cd09de0`. Their evidence reviews are in
[qualification](QUALIFICATION.md). Catalogue input is reference_sqlite. No combined
run, production readiness or Fabric/Power BI qualification is implied.

Use disposable synthetic environments, fresh output paths and explicitly reviewed
loopback destinations. Do not use a personal/client database, expose an admin
service on the Internet, or repeat CI merely to inspect existing evidence.

## Reference demonstration

From the repository root in a new Python 3.12/3.13 virtual environment:

```bash
python -m pip install -e '.[test]'
python -m ilc.cli validate
python -m pytest --junitxml=artifacts/junit.xml
python scripts/qualify_reference.py --output .runtime/reference-new --rows 10000
python scripts/qualify_recovery_governance.py --output .runtime/recovery-new --rows 10000
```

Both scripts refuse existing output roots and stop their loopback services.
Read `evidence/qualification.json` and actual per-scenario receipts, not just file
existence. HTML is a frozen authorized response, not Power BI. `work/` and source
databases are not public evidence.

For interactive use, run `ilc fixture`, `ilc source-api`, `ilc run` and
`ilc report-api` as described in the CLI help. Generate disposable access tokens
with `scripts/create_access_policy.py`, keep them outside Git, and pass an access
policy file to the report API. `ilc status` is read-only and refuses a missing
journal. Site filtering precedes totals; unauthorized global evidence/catalogue
and cross-site records are denied.

## Native demonstration

Required: a dedicated sandbox, Python 3.12, Java 17, package/JAR access and a new
loopback database whose name starts with `ilc_demo`. Explicitly set
`ILC_ALLOW_NATIVE_DEMO=1`, `ILC_SOURCE_DSN` and `ILC_STATE_DSN` outside Git.

```bash
python -m pip install -e '.[native,test]'
python scripts/qualify_native.py --output .runtime/native-new --rows 10000
```

The pytest native case additionally requires `ILC_NATIVE_TESTS=1`; enabled native
execution fails on missing prerequisites rather than downgrading to reference.
The test covers nominal processing/replay; the separate harness covers all six
scenarios, final-location Delta reads and controlled child-process exit/recovery.

A prepared alternative route is:

```bash
# Supply ILC_DEMO_DB_PASSWORD outside Git; use a disposable URL-safe password.
docker compose -f infra/compose.native.yml config --quiet
docker compose -f infra/compose.native.yml run --build --rm qualify
```

Those alternative commands are not separately qualified by the CircleCI result.
Existing source tables are refused, not truncated. Latest-GA JDK selection and
minor image tags are not a fully immutable toolchain.

## Real OpenMetadata

Use the separately scoped CircleCI catalogue route in
[OPENMETADATA_LIVE.md](OPENMETADATA_LIVE.md). It starts actual OpenMetadata,
PostgreSQL metadata storage and Elasticsearch in a fresh VM-owned Compose project.
Only the API is host-published, on loopback. Generated JWT keys/passwords are not
uploaded. Admin bootstraps fixtures; publication and independent readback use
separate non-admin identities.

The six live gates exercise identity, two-generation readback, replay, injected
response loss after a real write, server-side denials and conflict preservation.
The protocol emulator in the reference recovery script is not this product route.

For a separately authorized existing loopback catalogue, `scripts/governance.py`
can generate a plan without contacting it. Mutation needs `--publish`,
`--allow-catalog-writes`, reviewed settings and `ILC_OPENMETADATA_TOKEN` outside Git.
The CLI defaults to a reference journal. Native-profile catalogue publication
has not been qualified as a combined execution.

## Evidence and retries

Native: inspect attempt, Java/environment/dependencies, JUnit, verifier output,
acceptance/recovery and final-path Delta proofs. Catalogue: inspect images,
job-attempt, version, bootstrap, both generations' acceptance/plan/published/readback,
HTTP traces, conflict proof and artifact manifest. Missing evidence is not success.
Download original XML rather than copying its browser rendering; do not execute
or silently normalize extension-added markup as an alleged original file.

The first native and catalogue attempts failed. Source-established fixes later
succeeded, but the exact unread failed steps are not retrospectively invented.
Read diagnostics before rerunning, increasing resources or changing strategy.

## CI and budgets

CircleCI is automatic reference CI. Native and catalogue each require their
specific qualification branch or explicit pipeline parameter; never enable both.
Setup synchronizations use `[skip ci]`. Optional GitHub Actions workflows are
manual-only to avoid an automatic duplicate matrix.

Native command watchdog: 35 minutes. Catalogue: 25 minutes. Publication history
scan in reference: 10 minutes. Stage limits are shorter where applicable.
Provisioning and artifact transfer are outside the watchdogs; they are not account
spending caps. Observed native/catalogue command times are 272/158 seconds; billed
credits are unknown. No refill or plan change is configured.

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids unrelated host plugins; project fixtures
still load. Testsuite doctor is optional because it repeats tests; no observed
doctor execution is claimed. See [CI_CIRCLECI.md](CI_CIRCLECI.md).

## Retention and restoration

Do not blanket-delete runtimes or volumes. Preserve candidate state after unknown
outcomes, check ownership and export evidence before manual disposal. The catalogue
exit handler stops only its job-owned services and restores the VM sysctl; its
reviewed receipt reports both exit codes as zero, without volume deletion.

Reference backup holds writer locks, captures SQLite consistently and excludes
bearer policies. Restore refuses existing roots, unsafe archives and changed path
identity. It does not convert PostgreSQL into SQLite or qualify PostgreSQL/Delta
restore. Automatic staging/catalogue retention, power-loss durability and HA remain
outside scope. See [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Error interpretation

`INVALID_CONTRACT`: invalid metadata. `IDEMPOTENCY_CONFLICT`: key rebound to a
different plan. `CAPTURE_UNCERTAIN`: unfinished source capture. `SOURCE_ERROR`:
source/budget failure. `INTEGRITY_ERROR`: artifact drift. `STALE_BASE`: superseded
attempt. `BUSY`: active writer. `NATIVE_UNAVAILABLE`: real backend absent.
Consult actual exception classes for serialized codes; not every failure is retryable.

Public exposure concerns repository content only. Follow [PUBLICATION.md](PUBLICATION.md)
for history review and visibility; do not bind demo services to public interfaces.
