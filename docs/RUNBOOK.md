# Demonstration runbook

## Current accepted checkpoint

Native synthetic single-host functionality was reviewed and accepted at `fc1a9286c937deb09b87b97524c6835b24a1d516`; see [evidence and reservations](evidence/NATIVE_fc1a928_REVIEW.md). This is not a reason to rerun the same CI job merely to inspect files. Original raw JUnit archival and actual credit usage remain open; real OpenMetadata and Fabric/Power BI are separate gates.

## Reference: reproducible, disposable and bounded

From the repository root, install `.[test]` in an isolated Python 3.12/3.13 environment. Run `python -m ilc.cli validate`, the pytest suite, and `python scripts/qualify_reference.py --output .runtime/new-run --rows 10000`. Use a new output path. The script starts/stops loopback services and uses synthetic data only.

Read `evidence/qualification.json`, not just file existence. Check all six cases, source/runtime identity, provider statuses and API outcomes. HTML is a frozen authorized response, not live BI. For manual reporting, generate an access policy with `scripts/create_access_policy.py`, run `ilc report-api` on loopback and keep its disposable tokens outside Git. `ilc status` is read-only and refuses an absent journal.

## Native: isolated execution only

Use a dedicated approved sandbox, no valuable volumes, Python 3.12, Java 17 and working package/JAR resolution. Configure disposable loopback `ILC_SOURCE_DSN` and `ILC_STATE_DSN`, with an `ilc_demo`-prefixed database, and explicitly set `ILC_ALLOW_NATIVE_DEMO=1`. Install `.[native,test]` and run `python scripts/qualify_native.py --output .runtime/native-new --rows 10000`.

The alternative prepared Compose commands remain:

```bash
# Set ILC_DEMO_DB_PASSWORD outside Git, with a disposable URL-safe password.
docker compose -f infra/compose.native.yml config --quiet
docker compose -f infra/compose.native.yml run --build --rm qualify
```

CircleCI success does not qualify these Compose commands. They initialize new synthetic tables, not existing operational data. Do not use a personal or client database as a substitute. Observed native versions are recorded, not a full immutable image/transitive lock.

The native pytest is skipped unless `ILC_NATIVE_TESTS=1`. Explicit enablement fails when prerequisites are missing, never silently downgrades. That test covers nominal transformation and replay. The separate native harness covers all six scenarios, final-location readback, controlled child exit after synchronous materialization and authenticated HTTP reporting. The reviewed run executed both with real dependencies.

## Retention and cleanup

No blanket clean/delete command is provided. Review ownership, exact paths, volumes and exported evidence before manual disposal. Preserve candidate state after ambiguous outcomes. Old staged candidates can consume space; retain until reconciled. Reference SQLite same-path restore is tested; PostgreSQL/Delta restore, power-loss durability and automatic retention are not qualified.

## Error codes

`INVALID_CONTRACT`: metadata invalid. `IDEMPOTENCY_CONFLICT`: reused key bound differently. `CAPTURE_UNCERTAIN`: source read not finalized. `SOURCE_ERROR`: source contract/budget/read failure. `INTEGRITY_ERROR`: artifact drift. `STALE_BASE`: another publication superseded the attempt. `BUSY`: active writer. `NATIVE_UNAVAILABLE`: requested real backend absent. Consult the actual exception class for serialized codes; not all errors are retryable.

## Reference restoration and governance protocol

`python scripts/qualify_recovery_governance.py --output .runtime/recovery-new --rows 10000` starts disposable reference services and a catalog protocol emulator. It publishes metadata, checks no duplicate mutation, preserves the old runtime, creates/restores a consistent SQLite snapshot and rereads the report with source HTTP stopped. A separate MockTransport experiment models response loss. Neither is live OpenMetadata.

Consult [backup/restore](BACKUP_RESTORE.md) and [governance](GOVERNANCE.md). A real catalog write needs `--publish`, `--allow-catalog-writes`, a specific local endpoint and a token outside Git. No real catalog instance was contacted by the reviewed native run.

## Pytest plugin isolation

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids unrelated host plugins; project conftest fixtures still load and no third-party pytest plugin is required. Historical interrupted local suites remain interrupted attempts, not passing evidence. Native pytest now has a reviewed one-test result. Reference CircleCI remains successful at job-status level; its own exact JUnit count has not been reviewed.

## CircleCI and credit controls

See [CI_CIRCLECI.md](CI_CIRCLECI.md). Feature pushes run reference tests. A deliberate push to `qualify/p01-native-20261112`, or `run_native: true`, selects one native job. Avoid empty commits and unchanged reruns. Setup synchronizations and documentation-only changes skip duplicate execution.

The first native attempt `9395f4f` failed. The Java image compatibility defect was corrected at `fc1a928`; its successful run is reviewed. The exact first failed step is still not established from a complete failed-job log.

For new runs, inspect `attempt.json`, Java/environment/dependency receipts, logs, JUnit and `verified-evidence.json`, then complete `native-evidence` contents. Missing files are not success. Download original XML rather than copy a browser-rendered document; the reviewed browser copy has an extension-added script and cannot reproduce the original raw hash. Never execute it or silently present a cleaned copy as original.

The command watchdog is 35 minutes, not an account spend cap; provisioning and artifact upload are outside it. The accepted command took 272 seconds. Actual credits remain unknown. No paid refill or plan change is configured. Inspect diagnostics before changing resources after a failure.

Keep tokens, runtime policies and source databases out of Git and artifact uploads. The PostgreSQL password in CI is exclusively a disposable loopback fixture credential.
