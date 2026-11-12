# Qualification protocol and evidence scopes

## Current decision

Bounded synthetic native functionality is accepted on `fc1a9286c937deb09b87b97524c6835b24a1d516` after review of supplied CircleCI logs, receipts and browser-rendered JUnit. Original raw XML hash and actual credit consumption remain reservations, not reasons to repeat a successful run. Full detail and all fourteen receipt digests are in [the native review](evidence/NATIVE_fc1a928_REVIEW.md).

This is review within the implementation workstream, not an independent maintainer approval. Reconstructed receipt hashes are compared with a supplied verifier manifest, not signed provenance. Physical Delta files were not downloaded and reread during this review.

| Acceptance ID | Reference observation | Native observation reviewed |
|---|---|---|
| V-P01-01 | Same key/plan, no extra generation | Same accepted batch, generation 1 |
| V-P01-02 | Abrupt target-write exit and offline recovery | Exit 73; unchanged pre-resume watermark; Bronze/target reuse with HTTP source offline; generation 2 |
| V-P01-03 | Invalid data/schema blocked | 2 duplicate rows, 1 invalid amount, 4,975 schema-invalid shipments quarantined; no promotion/checkpoint advance |
| V-P01-04 | Counts/keys/amounts reconciled | 10,000 records, 3,980 facts, exact Decimal equality, ten final-path version-0 Delta table proofs |
| V-P01-05 | Site-scoped actual HTTP denials | Expected 401/403/404 outcomes; application permissions only |
| V-P01-06 | Accepted report retained and degradation exposed | Generation 1 preserved through three rejections; recovered generation 2 carries the intended +20 EUR SITE_A change |

No native database-reader-role, OpenMetadata, Fabric or Power BI authorization is inferred from application API checks. Additional reference cases cover pagination/cycles, unsafe continuation URLs, capture corruption, changed code/contract with reused keys, lookback/ties, superseded attempts, response loss and metadata-only onboarding; they are not all individually exercised by the native selector.

## Exact executed counts

The native console collected 235 cases and selected **one**: `test_real_native_qualification`. It passed in a 62.078-second suite, with 234 deselected, zero skipped/error/failure cases and two dependency deprecation warnings. Six additional application scenarios belong to the separate qualification script, not six further pytest cases.

Historical V3 reference evidence reported 193 passed and one native skip. Later source/CI changes introduced targeted tests; old counts are not transferred to the newer source. The reference job at `fc1a928` reports success, but its own detailed JUnit count has not been reviewed here.

The fixture contains 10,000 records across five entities, not 10,000 per table. A duplicate fixture adds one. Each clean accepted native receipt reports 1,621,039 Bronze bytes and 3,980 facts. The initial ordered amount is 8,857,766.18 EUR; recovery at fixture revision 1 is 8,857,786.18 EUR. The offline audit regenerated the deterministic fixture and recalculated site/total sums; it did not rerun a native pipeline.

## Provenance and timing

All 14 JSON receipt contents, including the summary extracted from the native log and the complete uploaded schema rejection, reproduce the declared SHA-256 under the actual canonical serializer. All 20 runtime manifest files match retained source bytes whose `src` Git tree and pyproject blob match the authenticated executed tree. Aggregate code/contract fingerprints and both final-readback proof bindings also match.

The JUnit browser copy contains a `chrome-extension://` script element. Its counter/testcase content agrees with the console, but original-byte identity cannot be claimed from this copy. Preserve that distinction instead of silently cleaning it into an alleged original. The Java archive SHA-256 is reported by CI; signature verification is `NOT_RUN`, and the binary was not downloaded for this review.

Command time was 272 seconds; the scenario harness recorded 139.895874 seconds; the successful resumed attempt recorded 22.657998 seconds. The UI showed a 4m39s job. These scopes overlap and must not be added or converted into a throughput/SLO/RTO or an actual credit bill. `billing_credits_observed` is null.

## Verification layers

- `test_native_readback.py`: precision and publication-gate tests with injected Delta verification where unavailable; not native execution by themselves.
- `test_governance.py`: metadata/API/outbox checks using MockTransport or CatalogEmulator; not an OpenMetadata product.
- `test_backup.py`: real SQLite/archive/same-path restore checks; not PostgreSQL DR.
- `test_qualification_harness.py`: native preconditions and separate fixture schemas; not native execution by themselves.
- `qualify_recovery_governance.py`: reference services, restore and explicitly emulated governance/response loss.
- `test_native_gate.py` and `qualify_native.py`: actually executed native test and scenario harness on the reviewed CircleCI run.
- `test_native_ci_evidence.py`: 19 synthetic receipt/JUnit verification cases.
- `test_java_bootstrap.py`: 22 synthetic metadata/archive/transport/process cases.

The latter two files had 41 local successes. An earlier 37-success/one-skip targeted set overlaps; do not add the counts. Two full local suite attempts were interrupted, not PASS. Compilation, shell syntax and YAML structural checks were successful; authoring-environment CircleCI CLI validation and testsuite doctor were not executed.

## Remaining boundaries

Direct dependency pins are not a complete transitive lock or a security audit. This native run uses Spark `local[2]` and in-process Dagster. Reporting consumes JSON projections reconciled to final-path Delta. The crash follows Spark stop/target relocation, not in-flight executor fencing. PostgreSQL stays available during recovery.

Distributed scale, HA, database/OS/cloud-native isolation, PostgreSQL restore, live OpenMetadata, Fabric/Power BI and Direct Lake remain unqualified. Compose/Windows/GitHub Actions routes do not inherit CircleCI Linux results. Metadata-only expansion was demonstrated on the reference path, not newly on the native path. No new project starts merely because these bounded checks passed.
