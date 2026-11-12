# P01 — CircleCI reference qualification

This project uses GitHub for code review and CircleCI for isolated cloud execution because GitHub Actions jobs currently fail before runner allocation due to the account's billing/spending restriction.

## First pipeline: reference only

`.circleci/config.yml` runs on `cimg/python:3.13` using the existing Python project and its source commands:

- `python -m pip install -e '.[test]'`
- `python -m compileall -q src tests scripts fabric`
- `python -m ilc.cli validate`
- `circleci testsuite run "p01 reference tests"`
- Two independent synthetic pipeline, recovery and governance scenarios (10,000 rows each).

One suite in `.circleci/test-suites.yml` discovers the repository's `tests/test_*.py` files and emits JUnit test results. It does not set any test selection, splitting or retry options.

No lockfile exists, so the starter pipeline deliberately has no dependency cache based on an unstable key. There is no configured lint command; compilation and metadata validation are explicitly named, not mislabeled as lint.

The optional `run_testsuite_doctor: true` pipeline parameter invokes `circleci testsuite doctor "p01 reference tests"` before a normal suite run. Doctor runs tests, so it is disabled on ordinary pushes to avoid doubling credit consumption. Local `circleci config validate` and `testsuite doctor` were not available in the author's isolated environment: both require separate hosted verification.

The native PostgreSQL/PySpark/Delta/Dagster path, real OpenMetadata server and Fabric/Power BI vendor integration remain **not executed by this configuration**. They are independent acceptance gates with their own resource, account and budget checks. Do not infer them from a passing reference job.

## Branches and onboarding

The feature branch `feat/p01-reference-native-qualification` is the P01 development source and Draft PR #1. CircleCI onboarding initially chose `circleci-project-setup` as its configuration-source branch and placed a README-only placeholder there. That bootstrap branch is synchronized non-destructively with the full feature tree and this configuration, so the first real build checks source code rather than a placeholder. After successful onboarding, the CI project may be reconfigured to load its configuration from the desired long-lived branch, provided that branch contains these files.

The repository is private. No client dataset, vendor secret, deployment or paid external resource is used. Keep the generated `.runtime` data and any credentials out of artifacts; only synthetic evidence paths are uploaded.

## Interpreting evidence

The previous P01 V3 local checkpoint reported 193 passing tests, one explicitly skipped native test, and reference E2E runs. It is a separate historical result, **not** CircleCI evidence. A new CircleCI run must be inspected for actual runner allocation, dependency installation, test results, exit status, artifacts and commit SHA.
