# Operating runbook

## Prerequisites and target selection

Run from a source checkout in a dedicated environment. The reference route requires
Python 3.12/3.13 and no database server. Native and catalogue routes require their
own dependencies and explicit opt-ins. Use synthetic fixtures, loopback services
and new output directories; never substitute a shared operational database.

The [baseline register](STATUS.md) identifies reviewed execution revisions.
The commands below reproduce a route; their presence does not certify a different
platform or a future dependency resolution.

## Reference demonstration

After activating a virtual environment from the repository root:

```bash
python -m pip install -e '.[test]'
python scripts/check_repository.py
python -m ilc.cli validate
python -m pytest --junitxml=artifacts/junit.xml
python scripts/qualify_reference.py --output .runtime/reference-new --rows 10000
python scripts/qualify_recovery_governance.py --output .runtime/recovery-new --rows 10000
```

The scripts refuse existing output roots and stop their loopback services.
Inspect `evidence/qualification.json`, individual receipts and reporting HTML.
The recovery/governance script uses a catalogue protocol emulator; it does not
replace the real-product qualification. [DEMO.md](DEMO.md) explains the outputs.

For interactive use, `ilc fixture`, `ilc source-api`, `ilc run` and `ilc report-api`
expose explicit commands. Run `python -m ilc.cli --help` and the relevant command's
help before use. Generate disposable reporting tokens with
[scripts/create_access_policy.py](../scripts/create_access_policy.py), retain the
access-policy file outside Git, and pass it to the reporting API. `ilc status`
opens state read-only and refuses a missing journal.

## Native demonstration

Use Python 3.12, Java 17, working package/JAR resolution and a new loopback
PostgreSQL database whose name starts with `ilc_demo`. Explicitly supply
`ILC_ALLOW_NATIVE_DEMO=1`, `ILC_SOURCE_DSN` and `ILC_STATE_DSN` outside Git.

```bash
python -m pip install -e '.[native,test]'
python scripts/qualify_native.py --output .runtime/native-new --rows 10000
```

The native pytest additionally requires `ILC_NATIVE_TESTS=1`. Enabling it with
missing prerequisites fails rather than silently falling back to reference.
The separate native harness covers the six acceptance scenarios and final-path
Delta proof. Existing source tables are refused, not truncated.

A prepared alternative is `infra/compose.native.yml`; its instructions require
`ILC_DEMO_DB_PASSWORD` outside Git and a disposable URL-safe password. That Compose
route is not independently qualified by the CircleCI native result. Review its
configuration before executing it.

## Real catalogue qualification

The [OpenMetadata guide](OPENMETADATA_LIVE.md) describes the isolated Compose
machine route, roles, six scenarios, evidence and cleanup. The admin fixture
bootstraps prerequisites; distinct non-admin identities publish and reread metadata.
Only the API is host-published, on loopback.

The standalone [governance publisher](GOVERNANCE.md) builds a plan without contacting
the server. Actual mutation requires `--publish`, `--allow-catalog-writes`, reviewed
settings and `ILC_OPENMETADATA_TOKEN` outside Git. Its default source profile is
reference; a combined native-to-catalogue execution has not been qualified.

## Failure triage

| Observation | First check | Recovery rule |
|---|---|---|
| Metadata validation fails | Contract/profile fields and declared model | Correct the input; do not initialise a runtime to bypass validation |
| Candidate rejected | Row/schema/business rejection receipt | Preserve accepted data; fix the source and submit a distinct valid request |
| Process stopped after target creation | Journal, frozen capture and target inventory | Resume the same bound request and reconcile existing effects |
| Idempotency conflict | Key, upper bound, source/code/contract identity | Do not rebind the old key or overwrite its evidence |
| Catalogue outcome uncertain | Durable outbox and exact remote readback | Reconcile; do not blindly recreate or delete |
| Integrity failure | Artifact bytes, manifests and bound identities | Stop publication and investigate drift |

Important codes include `INVALID_CONTRACT`, `IDEMPOTENCY_CONFLICT`,
`CAPTURE_UNCERTAIN`, `SOURCE_ERROR`, `INTEGRITY_ERROR`, `STALE_BASE`, `BUSY`
and `NATIVE_UNAVAILABLE`. Consult the actual exception class for its serialized
code. Not every failure is retryable.

## Evidence and retention

For native runs, inspect the attempt, environment, dependency receipt, native
JUnit, verifier result, acceptance/recovery receipts and Delta readback proofs.
For catalogue runs, inspect images, attempt/cleanup, version/bootstrap, both
generations' plans/publications/readbacks, traces and the artifact manifest.

Download original XML rather than copying a browser-modified rendering. Missing
artifacts are not a pass. Keep credentials, policies and source databases out of
Git and public artifact bundles. Do not rerun an unchanged expensive job merely
to inspect results already produced.

Preserve candidate state after unknown outcomes. Before disposal, confirm ownership,
exact paths/volumes and exported evidence. Catalogue cleanup stops only its job-owned
services; no automatic shared-data deletion or Docker pruning is used. Reference
backup/restore is same-path SQLite/filesystem recovery, not PostgreSQL/Delta DR.
See [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Continuous integration

The [CI guide](CI_CIRCLECI.md) defines trigger discipline, artifact paths and command
watchdogs. Native and catalogue runs are deliberate and separate. Actual credit
consumption is not inferred from elapsed time.

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is set in CI to isolate unrelated host plugins;
project conftest fixtures still load. The project has no required third-party
pytest plugin. An interrupted local run is not counted as a completed suite.
