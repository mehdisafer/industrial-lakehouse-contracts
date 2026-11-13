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
4. Run the repository pytest suite through the existing Smarter Testing definition; retain JUnit.
5. Run the reachable-history disclosure gate.
6. Execute the independent 10,000-record reference and recovery/governance scenarios; retain evidence.

The repository checker is standard-library only. It examines tracked local Markdown
links and ATX heading anchors, required documentation, the generated qualification
status page and accidentally tracked runtime/sensitive paths. It does not request
external URLs. Its negative tests prove rejection of deliberately broken inputs,
not correctness of a data integration.

`docs/STATUS.md` is derived from `docs/qualification-baselines.json`; an accepted
entry requires an exact executed revision present in its evidence document. See
[CONTRIBUTING.md](../CONTRIBUTING.md) for regeneration. This register records
historical baselines; it is not a mechanism to transfer an old integration pass
to a new runtime commit.

The optional `run_testsuite_doctor` parameter defaults to false because doctor
repeats tests. No observed doctor execution is claimed. There is no configured
lint tool or transitive dependency lock, and compilation is not labelled lint.

## Disclosure gate

[scripts/publication_gate.py](../scripts/publication_gate.py) verifies the exact
checkout, fetches all remote heads/tags and refuses shallow or incomplete history.
It exports reachable Git blobs and commit/tag metadata under byte/object budgets,
verifying their Git identities before scanning.

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
a live-product result from their job name.

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

There is no heavy-job matrix, automatic retry, paid refill or implicit provider
deployment. Diagnose a failed step before rerunning or increasing resources.
Catalogue cleanup stops only its job-owned services and restores the VM sysctl;
it does not delete shared data or named volumes.

## Result interpretation

A successful commit status establishes successful completion of the configured
job. Detailed test counts, skip reasons and receipts come from its JUnit/artifacts,
not from another run. Local targeted tests, a full hosted reference suite and a
live integration remain separate evidence levels. Historical interrupted runs
and first-attempt failures remain in the execution reviews.

[Configuration](../.circleci/config.yml) · [Native runbook](RUNBOOK.md#native-demonstration) ·
[Catalogue guide](OPENMETADATA_LIVE.md) · [Publication checklist](PUBLICATION.md)
