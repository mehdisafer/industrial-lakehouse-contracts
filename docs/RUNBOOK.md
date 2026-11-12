# Demonstration runbook

## Reference: reproducible, disposable and bounded

From the repository root, install `.[test]` in an isolated Python 3.12/3.13 environment. Run `python -m ilc.cli validate`, then the full pytest suite, then `python scripts/qualify_reference.py --output .runtime/new-run --rows 10000`. Use a new path for every qualification. The script starts/stops loopback services and uses only synthetic data.

Read `evidence/qualification.json` rather than infer success from the existence of a file. Review all six acceptance cases, code/runtime identity, native/provider statuses, and the API status codes. The HTML is a frozen export of an authorized response, not a continuously updating BI service.

For manual reporting, generate an access policy with `scripts/create_access_policy.py`, start `ilc report-api` on loopback, and use the printed disposable tokens. Do not store them in shell scripts committed to Git. `ilc status` is read-only and refuses an absent journal.

## Native: prepared route, not an instruction to use a personal/client DB

Use a dedicated sandbox with adequate approved resources, no valuable volumes, Python 3.12, Java 17, and working package/JAR downloads. Configure disposable `ILC_SOURCE_DSN` and `ILC_STATE_DSN`, both on loopback with an `ilc_demo`-prefixed database. Set `ILC_ALLOW_NATIVE_DEMO=1` explicitly. Install `.[native,test]` and run `python scripts/qualify_native.py --output .runtime/native-new --rows 10000`.

The prepared Compose route is:

```bash
# Set ILC_DEMO_DB_PASSWORD outside Git, using a disposable URL-safe password.
docker compose -f infra/compose.native.yml config --quiet
docker compose -f infra/compose.native.yml run --build --rm qualify
```

These commands are **not executed or validated by the delivered reference evidence**. They initialize new synthetic tables only. Do not substitute an existing operational database. Native module versions and container tags remain candidates, not a full immutable lock.

The native pytest is skipped unless `ILC_NATIVE_TESTS=1`. When explicitly enabled it fails if dependencies/setup are absent; it never converts an unavailable provider into a pass. The original native pytest checks nominal transformation and replay. The additional `qualify_native.py` harness requires real dependencies, seeds separate fresh synthetic schemas per scenario, and is designed to exercise all six P01 cases, the final Delta path, hard child exit after synchronous target creation and authenticated HTTP reporting. It does not replace missing dependencies with mocks. CircleCI now attempts this real path; its status and receipts must be read before claiming native qualification.

## Retention and cleanup

No clean/delete command is provided. Review ownership, exact path/volume and evidence export before manual disposal. The database and candidate directories are not discarded on an ambiguous failure. Old staged candidates may consume space; retain them until their effects are reconciled. Reference SQLite backup restoration is covered by a separate real exercise. PostgreSQL/Delta restoration, interrupted disk writes/power loss and automated retention remain unqualified.

## Error codes

`INVALID_CONTRACT`: metadata invalid. `IDEMPOTENCY_CONFLICT`: key bound to another request. `CAPTURE_UNCERTAIN`: source read did not finalize. `SOURCE_ERROR`: source contract/budget/read failed. `INTEGRITY_ERROR`: artifact differs. `STALE_BASE`: new publication already superseded the attempt. `BUSY`: another writer. `NATIVE_UNAVAILABLE`: the requested real backend is absent. Consult the actual exception class for the precise serialized code; do not treat all errors as retryable.

## Reference restoration and catalog protocol qualification

`python scripts/qualify_recovery_governance.py --output .runtime/recovery-new --rows 10000`
starts only disposable reference services and a named catalog protocol emulator.
It publishes metadata, checks replay without duplicate mutations, creates a
consistent SQLite archive, preserves the original root, restores to its exact
path and rereads the report over HTTP with the source stopped. A second catalog
experiment injects a lost response through MockTransport. Neither experiment is
an OpenMetadata deployment.

Read [backup/restore](BACKUP_RESTORE.md) and [governance](GOVERNANCE.md) for manual
operations. The real catalog command needs both `--publish` and
`--allow-catalog-writes`, an explicit local endpoint and a token outside Git. No
real catalog instance has been contacted during this qualification.

## Host pytest plugin isolation

The final receipt uses `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` because unrelated pytest
plugins preinstalled in the authoring host stalled earlier attempts. The project
has no required third-party pytest plugin; its conftest fixtures remain loaded.
The early timed-out attempts are retained as attempts, not passing evidence. The
same flag is explicit in the CircleCI reference workflow. GitHub reports a
successful reference status on `fc1a928`; private JUnit and evidence require
separate inspection. No numerical hosted test count is inferred from that status.

## CircleCI native operation and credit control

The active configuration is described in [CI_CIRCLECI.md](CI_CIRCLECI.md). Ordinary feature pushes run only the reference job. A deliberate push to `qualify/p01-native-20261112`, or a pipeline with `run_native: true`, selects one native job. Do not make empty commits or rerun an unchanged failure before reading its diagnostic.

The first native attempt on `9395f4f` failed. The source-established Java 11 incompatibility was corrected at `fc1a928` using plain Python and a verified Temurin 17 archive. The exact failed step of the first job remains unknown without its private logs. The corrected native attempt has its own evidence boundary.

Read `native-diagnostics/attempt.json` first for last phase, exit code, source SHA and duration. Then inspect `java-install.json`, `environment.json`, `native-tests.log`, `native-qualification.log` and JUnit, when those stages were reached. Final acceptance additionally requires `verified-evidence.json` and the complete `native-evidence` receipts. Missing artifacts are not success.

The 35-minute watchdog bounds the command, not image provisioning or artifact upload and not the account billing total. No paid refill or plan change is configured. After an unexplained failed attempt, obtain the CircleCI failure report rather than increase resources speculatively.

Do not copy tokens into GitHub comments or chat. Runtime policies and source databases stay out of CI artifacts. The fixture PostgreSQL password is only for the isolated job service.
