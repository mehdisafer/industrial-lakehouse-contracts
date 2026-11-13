# Repository and reference-CI validation

I treat the verification tooling as production code for the repository: a checker
that accepts a broken input or prints a rejected credential can weaken the release
process even when the data pipeline is correct.

## Documentation and tracked-file checks

`python scripts/check_repository.py` uses only the standard library and makes no
external requests. It checks required tracked documents, local destinations and
supported heading anchors, qualification-register consistency and prohibited
runtime or credential-file paths. An ignored pattern does not protect a file
already tracked by Git; the checker therefore examines the actual index inventory.

The deliberately supported Markdown subset includes ATX headings, single-line
inline links, full/collapsed reference links, fenced code and inline code spans.
Code-formatted link labels remain links; links written entirely inside a code
example are not followed. Destinations support bounded balanced parentheses,
angle brackets and optional titles. Duplicate heading IDs remain unique even
when an explicitly suffixed heading collides with a generated one.

External HTTP(S) destinations need an actual hostname and a valid optional port.
Credential-bearing authorities are refused. Mailto destinations receive a basic
syntax check. This validates shape only, not ownership, availability, DNS or TLS.
HTML links/anchors, shortcut references, Setext headings and all of GitHub-flavoured
Markdown are not claimed to be supported.

Diagnostics retain document and line information but omit rejected destination and
reference-label payloads. Parser/OS errors are represented by category rather than
raw exception values. Register and document reads have byte limits and require
regular files; symlinks and FIFOs are not read. This is not protection against a
privileged concurrent filesystem writer.

The generated status page is compared with its typed register. Accepted revisions
must be complete 40-character commit tokens in the linked evidence, not substrings
of longer hexadecimal values. That consistency check does not verify the historical
execution independently or turn the register into a signature.

## Test collection and original JUnit

Before executing the reference suite, CI runs:

```bash
python scripts/verify_reference_ci.py collect --output artifacts/reference/test-inventory.json
```

`CIRCLE_SHA1` supplies the exact expected revision in CircleCI. In a local clean Git
checkout, `--expected-sha` can supply an explicit commit. Collection uses pytest's
normal discovery without executing tests, records the JUnit identity of every case,
and fingerprints the discovered test files.

After the existing test and scenario commands, CI runs:

```bash
python scripts/verify_reference_ci.py verify --output artifacts/reference/verified-evidence.json
```

The verifier expects the standard CircleCI output locations documented in
[CI_CIRCLECI.md](CI_CIRCLECI.md). It is not a convenience command that creates
missing receipts, reruns tests or manufactures a successful scan result.

It requires the original UTF-8 pytest XML, exact collected identities, consistent
counters and zero failures/errors. The only approved reference skip is
`tests.test_native_gate::test_real_native_qualification`. Unexpected extra skips,
missing tests, duplicate outcomes, DTD/entity declarations or injected browser
markup fail the gate. Raw XML SHA-256 values are recorded before any interpretation.

## Reference and recovery consistency

The verifier binds both scenario summaries and acceptance receipts to the same
clean checkout and application-source manifest. It checks six reference scenarios,
10,000-record input, 3,980 facts, exact site/report/source monetary totals,
rejection without publication, recovery generation 2 and the metadata-only extension.

The separate recovery proof must retain the accepted batch and generation across
backup, same-path restore, offline-source replay and reporting. The actual retained
archive bytes must match the backup and restore digests. The catalogue peer remains
explicitly identified as a protocol emulator; no new Spark or real OpenMetadata
qualification follows from this check.

Repository and disclosure reports are also mandatory. The final output contains
counts and evidence digests, not source rows, tokens or copied failure payloads.
Missing or inconsistent evidence returns nonzero, and an existing output file is
never overwritten. Actual credits remain unreported unless measured separately.

## Review and regression practice

The second review started by reproducing false successes, diagnostic reflection
and anchor collisions against the exact previous checker blob. Tests cover both
invalid and valid examples, including original JUnit reconciliation, altered
receipt/source identities and archive corruption. Real reference and restore
outputs are also exercised separately from those synthetic verifier fixtures.

Run focused checks from the root after installing `.[test]`:

```bash
python -m pytest tests/test_repository_quality.py tests/test_repository_hardening.py tests/test_reference_ci.py
```

The [contribution guide](../CONTRIBUTING.md) defines the wider review process.
Historic native/catalogue receipts and the baseline register are unchanged by
repository-tooling maintenance.

## Primary references

- [Python URL parsing security](https://docs.python.org/3.13/library/urllib.parse.html#url-parsing-security)
- [GitHub section links](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links)
- [CommonMark code spans and reference links](https://spec.commonmark.org/0.31.2/)

These references informed the bounded parser corrections; they do not imply full
CommonMark compliance or external-page rendering tests.
