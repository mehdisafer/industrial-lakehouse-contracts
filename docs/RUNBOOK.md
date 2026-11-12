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

The native pytest is skipped unless `ILC_NATIVE_TESTS=1`. When explicitly enabled it fails if dependencies/setup are absent; it never converts an unavailable provider into a pass. The original native pytest checks nominal transformation and replay. The additional `qualify_native.py` harness requires real dependencies, seeds separate fresh synthetic schemas per scenario, and is designed to exercise all six P01 cases, the final Delta path, hard child exit after synchronous target creation and authenticated HTTP reporting. It does not replace missing dependencies with mocks. It is not executed in this delivery.

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
same flag is explicit in the candidate reference workflow; hosted execution is
still unverified.
