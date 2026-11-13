# Qualification protocol and evidence scopes

## Decisions

**G2 native functionality is accepted** at
`fc1a9286c937deb09b87b97524c6835b24a1d516` after review of supplied CircleCI logs,
receipts and browser-rendered JUnit. See [the native review](evidence/NATIVE_fc1a928_REVIEW.md).

**G3a real OpenMetadata API-publisher functionality is accepted** at
`cd09de03d658cb66d5aaa29a8ec677fd17a3f977` after the 13 November artifact review.
See [the catalogue review](evidence/OPENMETADATA_cd09de0_REVIEW.md).
Its input is reference_sqlite; separate successful native and catalogue runs are
not represented as a combined native-to-catalogue qualification.

Both decisions are bounded synthetic, single-host demonstrations. They are not
independent maintainer approval, signed provenance or production certification.
Original raw XML identity and observed billed credits remain reservations, not
reasons to repeat successful expensive jobs. Fabric/Power BI remains open.

## Native acceptance scenarios

| ID | Actual reviewed observation |
|---|---|
| V-P01-01 | Same accepted batch on replay; generation 1 retained |
| V-P01-02 | Controlled exit 73 after target materialization; unchanged pre-resume watermark; stopped HTTP source; Bronze/target reuse and generation 2 |
| V-P01-03 | Two duplicate rows, one invalid amount and 4,975 schema-invalid shipments rejected; no promotion/checkpoint advance |
| V-P01-04 | 10,000 captured records, 3,980 facts, exact Decimal/count/key equality and ten final-path version-0 Delta proofs |
| V-P01-05 | Expected 401/403/404 application-role denials |
| V-P01-06 | Generation 1 retained through rejection; generation 2 reports the intended SITE_A +20 EUR revision |

Native console collection found 235 cases and selected **one**:
`test_real_native_qualification`. It passed; 234 were deselected, none skipped,
failed or errored. Suite duration was 62.078 seconds with two dependency
warnings. The six script scenarios are not six additional pytest cases.

Each clean batch contains 10,000 records **across** five entities, 1,621,039 Bronze
bytes, 995 orders and 3,980 facts. Ordered amount changes from 8,857,766.18 to
8,857,786.18 EUR by fixture design. The prior offline audit recalculated the
fixture/site totals without re-executing Spark.

## Real catalogue scenarios and counts

G3-01 checks actual server identity/authentication. G3-02 publishes and rereads
two generations with fifteen tables, eleven lineage edges and one DQ result each.
G3-03 replays without mutations. G3-04 reconciles a response lost after real server
success. G3-05 exercises native server denials for unauthenticated access, reader
mutation and writer administration. G3-06 preserves a conflicting remote object
and the first accepted generation.

The run records **33 offline harness-safeguard pytest cases**, zero failures,
errors or skips, and six separate live scenarios. The supplied product artifacts
were checked for thirty table UUIDs, 170 column definitions, twenty-two edges,
two external DQ results, two exact-parent basic suites and actual server denials.
The subsequent offline artifact review executed 463 assertions, not 463 cloud tests.

## Provenance and integrity

Native review reproduced fourteen canonical JSON hashes and twenty application
source fingerprints. Catalogue review reproduced all fifteen artifact-manifest
entries: fourteen canonical JSON files and HTML rebuilt with the executed
formatter. Twenty application file hashes and the live script hash agree.

The canonical serializer uses sorted keys, compact UTF-8 JSON and a trailing
newline. Catalogue acceptance digests intentionally exclude the invocation return
envelope; downloadable receipt-file hashes include it. Batch, source profile,
plan, acceptance, target and remote-entity identities are checked separately.

A copied browser XML tree is not original JUnit bytes: the supplied copies contain
an extension-added script, and the catalogue copy includes rendered lambda names.
No browser script is executed or silently removed to manufacture an original.
JDK/container digests are recorded by CI; repeat binary downloads and signature
verification are not claimed. Physical Delta files were not independently
retaken for the later evidence review.

## Timing and warning interpretation

Native command: 272 seconds; native harness: 139.895874 seconds; resumed attempt:
22.657998 seconds. Catalogue command: 158 seconds; live harness: 20.831684 seconds.
These scopes overlap. They are not additive, throughput benchmarks, RTOs or bills.
Actual credits are unreported.

Fixed fixture time correctly produces STALE reports. DEGRADED identifies a rejected
latest attempt, not loss of the accepted dataset. A business sub-check PASS does
not override row/schema rejection. Catalogue initialization logs contain missing
relation queries, SET LOCAL warnings and a Logback version mismatch; migration
exit 0 and successful API checks do not erase those warnings.

## Test-layer inventory

- Reference tests exercise real SQLite/files/loopback HTTP; native-marked tests
  skip unless their explicit environment opt-in is present.
- Publisher unit and CatalogEmulator tests remain protocol evidence, not the
  OpenMetadata product. Live G3 uses the actual product separately.
- Native-readback, native-receipt, Java-bootstrap and live-harness safeguard tests
  use labelled injected/synthetic inputs where appropriate.
- Reference backup tests cover same-path SQLite/filesystem restoration, not
  PostgreSQL/Delta disaster recovery.
- Publication-gate unit tests exercise scope/path/Git failure handling and deleted
  historical content; the actual Gitleaks invocation is a separate CI step.

Historical local V3 had 193 passes and one native skip. The 41 subsequent Java and
native-verifier cases overlap with an earlier 37-pass set; do not add them.
The catalogue increment's targeted set had 65 passes (33 harness plus 32 publisher).
An earlier recovered-V3 materialization had 219 passes and one skip and excluded
those 41 CI-specific files. The publication increment's recovered local materialization completed 242 passes and one native skip in 58.06 seconds, including the sixteen new disclosure guards but excluding those 41 CI-specific files. Current hosted suite counts must come from its own JUnit, not these older totals. Incomplete earlier local runs remain incomplete.

## Remaining boundaries

Direct dependency pins are not a full transitive lock or vulnerability audit.
Spark local[2], in-process Dagster, whole-source capture before incremental selection,
post-stop crash injection, JSON reporting projections, dedicated catalogue roles
and client response suppression all have deliberately limited scope.

Distributed scale, HA, database/OS/cloud-native isolation, in-flight Spark fencing,
PostgreSQL/Delta restore, TLS/SSO, catalogue lifecycle/restore, Airflow ingestion,
Fabric/Power BI and Direct Lake remain unqualified. Alternative native Compose,
Windows and GitHub Actions execution do not inherit CircleCI Linux acceptance.
See [provider gates](PROVIDER_GATES.md) and [publication](PUBLICATION.md).
