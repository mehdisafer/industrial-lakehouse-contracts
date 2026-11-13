# CircleCI execution, evidence and disclosure controls

GitHub stores source/review; CircleCI is the active automatic execution route.
The optional GitHub Actions reference and native workflows are manual-only.
This avoids a duplicate automatic OS/Python matrix; it does not modify account
billing or claim that the historical runner-admission problem has been fixed.

## Reviewed functional checkpoints

| Route | Executed commit | Reviewed decision |
|---|---|---|
| Native | `fc1a9286c937deb09b87b97524c6835b24a1d516` | Bounded G2 accepted; one native pytest and six script scenarios |
| Real catalogue | `cd09de03d658cb66d5aaa29a8ec677fd17a3f977` | Bounded G3a accepted; 33 offline safeguard tests and six live scenarios |

The [native](evidence/NATIVE_fc1a928_REVIEW.md) and
[catalogue](evidence/OPENMETADATA_cd09de0_REVIEW.md) reviews retain their actual
source profiles, hashes, warnings and archival/accounting reservations.
The catalogue input is reference_sqlite, not a combined native/catalogue rerun.

## Reference route

`reference-qualification` uses Linux `cimg/python:3.13`, resource class medium,
`.[test]`, Python compilation, contract validation and the repository's Smarter
Testing suite. Its two separate reference scripts exercise 10,000 synthetic
records and recovery/governance emulation. No native backend is substituted for
an emulator or inferred from reference success.

`run_testsuite_doctor` defaults to false because doctor repeats tests; no observed
doctor result is claimed. There is no configured lint tool or complete transitive
lockfile, and neither is invented for presentation. Hosted test counts require
the job's own JUnit; older local counts are not transferred to it.

## Reachable-history disclosure gate

The reference job additionally runs `scripts/publication_gate.py` under a ten-minute
watchdog. Gitleaks 8.30.1 is downloaded from its official release with fixed archive
size and SHA-256, and its version is checked. A generated synthetic token-shaped
positive control must be detected before the actual history scan can succeed.

The script checks the exact repository, commit and clean tracked worktree, fetches
all remote heads/tags and refuses shallow history. It exports unique reachable
blob bytes and commit/tag metadata under object/byte budgets, validating each Git
object identity. It scans the export directory, including bounded archive/encoding
inspection, rather than trusting an unchecked git-log pipeline.

Scanner errors, missing output, exit/result disagreement and any finding fail the
job. Only redacted rule/location/fingerprint summaries are published. The code
never changes visibility, permissions, history or billing. `artifacts/publication`
contains its inventory and summary. A successful configured gate is distinct from
an independent download/review of that inventory.

The first integrated gate/reference job succeeded at `235bd381e9ef5cc906e77ea63bcca9c64700d2e2`.
The exact final documentation candidate must also have its reference result checked
before merge. Rule-based absence of findings is not a guarantee against every
confidential item, vulnerability or licensing problem; issues/logs need separate
review. See [PUBLICATION.md](PUBLICATION.md).

## Native route

Native uses one Docker large job, `cimg/python:3.12`, disposable PostgreSQL 16 and
explicit verified Temurin 17 bootstrap. The bootstrap checks official HTTPS hosts,
archive size/SHA-256, safe extraction and Java major version. It records the
resolved release, not an immutable future JDK selection or signature verification.

The reviewed runtime was Python 3.12.16, Temurin 17.0.21+9, PostgreSQL 160015,
Psycopg 3.2.13, PySpark/Delta Spark 4.0.1 and Dagster 1.11.16. The job runs native
pytest, the six-scenario harness and a mandatory exact-SHA/semantic evidence gate.
It rejects skipped tests, dirty/wrong source identity, missing scenarios and
inconsistent final-path Delta proofs. All ten version-0 tables, source-target
reconciliation and recovered reporting generation 2 are required.

Only `qualify/p01-native-20261112` or explicit `run_native: true` selects this route.
No native matrix, automatic retry, remote Docker or paid layer cache is enabled.

## Catalogue route

Catalogue uses one disposable Ubuntu 24.04 machine large job, Compose, actual
OpenMetadata 1.12.0, PostgreSQL metadata storage and Elasticsearch 9.3.0. Credentials
and signing keys are generated per job outside artifact directories. Only the API
is host-published, on loopback. Two non-admin identities separate publication and
readback; the admin fixture is limited to bootstrap/sentinel preparation.

Only `qualify/p01-openmetadata-20261113` or explicit `run_catalogue: true` selects
this route. Never enable native and catalogue parameters together. Setup branch
synchronizations run neither heavy route. Full setup and evidence paths are in
[OPENMETADATA_LIVE.md](OPENMETADATA_LIVE.md).

## Timeouts, credits and cleanup

Native command watchdog: 35 minutes plus kill grace; Java/install/readiness/test/
scenario stages have shorter limits. Catalogue command watchdog: 25 minutes with
bounded pulls, migration, readiness and qualification. Reference disclosure scan:
10 minutes. Provisioning, checkout and artifact upload are outside these commands;
none is an account-wide spend cap.

Reviewed command durations were 272 seconds native and 158 seconds catalogue.
Actual billed credits are unknown and must not be inferred from timestamps.
Historical qualification used two native attempts and two catalogue attempts,
each with one correction; publication review does not rerun either stack.
No subscription, refill, spending ceiling or resource-class increase is made.

The catalogue exit handler stops only its job-owned Compose project and records
service-stop/sysctl-restoration codes, both zero in the reviewed receipt. It does
not DROP/TRUNCATE shared data, prune Docker or delete named volumes. The VM is
disposable infrastructure, not a persistent hosted catalogue.

## Failure history and limitations

The first native attempt failed; source review identified Java 11 in the browsers
image and the explicit Java 17 correction subsequently succeeded. The first
catalogue attempt also failed; a reproduced gzip double-decoding defect and a
deprecated suite-field assumption were corrected before success. Neither later
success establishes the precise unread first failed step.

Native remains Spark local[2] and in-process Dagster; JSON reports are reconciled
to Delta, not Direct Lake. Catalogue remains a dedicated-instance API-publisher
qualification, not TLS/SSO, multitenancy, HA, Airflow ingestion or product-UI review.
Fabric/Power BI remains separate. Source-visible publication is not deployment.

## Primary references

- https://circleci.com/docs/reference/configuration-reference/
- https://circleci.com/docs/guides/execution-managed/using-linuxvm/
- https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1
- https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md
- https://adoptium.net/installation/archives/
- https://docs.delta.io/releases/
