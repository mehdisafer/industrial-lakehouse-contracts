# Continuous integration

I use CircleCI for automatic reference checks and explicitly selected native or
catalogue integration runs. GitHub stores the source, issues and reviews. The
alternative GitHub Actions workflows are manual to avoid duplicate execution.

## Routes

| Job | Execution environment | Trigger and purpose |
|---|---|---|
| `reference` | Linux, Python 3.13, Docker `medium` | Normal development pushes; repository checks, tests, disclosure scan and reference scenarios |
| `native` | Python 3.12, explicit Java 17, disposable PostgreSQL 16, Docker `large` | Exact native qualification branch or `run_native: true` |
| `catalogue` | Ubuntu 24.04 machine `large`, isolated Compose stack | Exact catalogue qualification branch or `run_catalogue: true` |

Do not enable native and catalogue parameters together. Setup-branch synchronisation
is excluded from normal workflows to avoid duplicate builds. The current onboarding
configuration source remains `circleci-project-setup`; changes to CI configuration
must be synchronised there as well as to the development branch. A move to `main`
as configuration source requires an explicit CircleCI project-settings change.

## Reference sequence

1. Record the checked-out revision and Python toolchain.
2. Run `scripts/check_repository.py` and retain its JSON report.
3. Install `.[test]`, compile source/tests/scripts and validate metadata contracts.
4. Collect the complete pytest inventory without executing tests, bound to the clean checkout and test-file fingerprints.
5. Run the repository pytest suite through the existing Smarter Testing definition; retain original JUnit.
6. Run the reachable-history disclosure gate.
7. Execute the independent 10,000-record reference and recovery/governance scenarios; retain evidence.
8. Run `scripts/verify_reference_ci.py verify` to reconcile JUnit identities/counters, source identity, scenario receipts, reporting totals and retained backup bytes.

The repository checker is standard-library only. It examines tracked local Markdown
links and ATX heading anchors, required documentation, the generated qualification
status page and accidentally tracked runtime/sensitive paths. It does not request
external URLs. Diagnostics identify the document/line and failure class without
copying rejected destinations, labels or parser payloads into the report.

`docs/STATUS.md` is derived from `docs/qualification-baselines.json`; an accepted
entry requires an exact executed revision present as a complete hash token in its
evidence document. See [CONTRIBUTING.md](../CONTRIBUTING.md) for regeneration.
This register records historical baselines, not a new pass for a later commit.

The optional `run_testsuite_doctor` parameter defaults to false because doctor
repeats tests. No observed doctor execution is claimed. There is no configured
lint tool or transitive dependency lock, and compilation is not labelled lint.

## Reference verification artifacts

| Path in CircleCI Artifacts | Content |
|---|---|
| `repository-quality/check.json` | Documentation and tracked-file checks |
| `reference-verification/test-inventory.json` | Collected test identities and source fingerprints before execution |
| `reference-verification/verified-evidence.json` | Actual passed/skipped counts, original XML hashes, reference outcomes and input digests |
| `test-results/` | Original pytest XML, not browser-rendered text |
| `reference-evidence/`, `recovery-evidence/` | Original scenario receipts and consumer outputs |
| `publication-review/` | Rule-based disclosure inventory and result |

The verifier requires exactly the collected test identities, zero failures/errors
and only the explicitly disabled native test as an allowed skip. It rejects missing
cases, duplicate outcomes, contradictory counters and unexpected XML elements.
It validates the six reference scenarios, metadata-only extension, same-path restore,
accepted replay and aggregate reporting, including the retained backup archive hash.

The collection and receipt revisions must match `CIRCLE_SHA1`; tracked or untracked
source changes are not accepted. Generated outputs stay in ignored directories.
The result is a mandatory consistency gate, not signed provenance or an independent
artifact download. See [repository and CI validation](REPOSITORY_QUALITY.md).

## Disclosure gate

[scripts/publication_gate.py](../scripts/publication_gate.py) verifies the exact
checkout, fetches all remote heads/tags and refuses shallow or incomplete history.
It exports reachable Git blobs and commit/tag metadata under byte/object budgets,
verifying their identities before scanning.

The Gitleaks 8.30.1 archive is size/SHA-256 pinned. A generated synthetic positive
control must be detected before a zero-finding scan can succeed. Scanner errors,
missing output, exit/result disagreement and findings fail the job. Only redacted
finding metadata is retained. This is distinct from documentation hygiene and is
not an exhaustive confidentiality, licensing or vulnerability assessment.

## Heavy integration evidence

Native runs execute the selected native pytest, six application scenarios and the
exact-revision semantic evidence verifier. Catalogue runs execute offline safeguard
tests followed by six actual-product scenarios. Their reviewed baselines are in
[STATUS.md](STATUS.md); detailed proof boundaries are in [QUALIFICATION.md](QUALIFICATION.md).

The data engine and catalogue jobs have not been combined into one execution.
Reference tests use a named catalogue emulator where appropriate and do not acquire
a live-product result from their job name. The new reference verifier preserves
those exclusions in its output and rejects receipts that overclaim them.

## Resource controls

| Command | Watchdog |
|---|---|
| Publication history scan | 10 minutes |
| Native qualification | 35 minutes, plus kill grace |
| Catalogue qualification | 25 minutes, plus kill grace |

Individual installation/readiness/scenario stages have shorter limits. Provisioning,
checkout and artifact upload are outside these commands; a watchdog is not an
account-wide spending cap. Observed native/catalogue command durations are 272 and
158 seconds respectively. Billed-credit totals remain unobserved.

Reference collection imports tests but does not execute them a second time. Final
verification reads bounded local outputs; it starts no extra service. There is no
heavy-job matrix, automatic retry, paid refill or implicit provider deployment.
Catalogue cleanup stops only its job-owned services and restores the VM sysctl;
it does not delete shared data or named volumes.

## Result interpretation

A successful commit status establishes successful completion of the configured
job. Detailed test counts and receipts come from that run's original artifacts,
not another run. Local targeted tests, a full hosted reference suite and a live
integration remain separate evidence levels. Historical interrupted runs and
first-attempt failures remain in their execution reviews.

[Configuration](../.circleci/config.yml) · [Native runbook](RUNBOOK.md#native-demonstration) ·
[Catalogue guide](OPENMETADATA_LIVE.md) · [Publication checklist](PUBLICATION.md)
