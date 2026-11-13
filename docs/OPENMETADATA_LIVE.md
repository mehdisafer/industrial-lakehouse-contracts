# OpenMetadata integration qualification

## Accepted scope

I qualified the API publisher against **OpenMetadata 1.12.0** at
`cd09de03d658cb66d5aaa29a8ec677fd17a3f977`. The successful CircleCI execution and
supplied artifact review establish the bounded G3a baseline. The
[evidence record](evidence/OPENMETADATA_cd09de0_REVIEW.md) contains the reviewed
identities, counts, hashes and warnings.

The catalogue receives newly accepted **reference_sqlite** generations. Native
PostgreSQL/Spark/Delta/Dagster was qualified separately at `fc1a928`; these two
baselines do not claim a combined native-to-catalogue execution.

## Deployment topology

[compose.openmetadata.yml](../infra/compose.openmetadata.yml) starts PostgreSQL 16
for catalogue state, Elasticsearch 9.3.0, the OpenMetadata migration container and
the server on a disposable CircleCI machine. Python 3.12 runs the qualification
client. The adapter uses the pinned upstream API revision
`caa14bfd42af6ec84464aa81815addd3e0cd2902`.

Only `127.0.0.1:8585` is published on the host. Database, search and administration
ports have no host-published listener. Credentials and signing keys are generated
per job outside the artifact paths. Self-signup and the Airflow ingestion-service
client are disabled.

A fresh job-owned Compose project and output directory are required. The script
refuses an existing project or bootstrap entity. At exit, it stops its own
services and restores the temporary VM sysctl setting without deleting volumes.
The reviewed attempt records zero exit codes for both cleanup operations.

The images use version-selected tags. `images.json` records the digests actually
resolved; tags are not a fully immutable dependency lock. This is an isolated
qualification topology, not a public hosting or production security template.

## Identities and permissions

The administrator initialises the fixture service, owner team, classification,
policies, roles and two non-administrator users. Actual publication uses the writer;
independent readback uses the reader.

The writer may create/edit database, schema, table and test metadata. It cannot
administer policies, roles, users, teams, tags, classifications or services, and
cannot delete data entities. The reader has an explicit mutation deny.

These checks establish resource-type role enforcement on a dedicated instance.
They do not establish per-namespace multitenancy, TLS or SSO.

## Live scenarios

| ID | Required observation |
|---|---|
| G3-01 | Actual product version and authenticated API access |
| G3-02 | Two accepted generations; 15 tables, 11 lineage edges and one DQ result per generation; owners, tags, types and exact-parent basic suites reread |
| G3-03 | Replayed publication produces no additional mutation |
| G3-04 | A response is suppressed after a real successful database write; the next publisher reconciles the same server object, with one database PUT |
| G3-05 | Unauthenticated read returns 401; reader mutation and writer policy creation return 403; forbidden object remains absent |
| G3-06 | A conflicting remote database is preserved without publisher mutation; the first generation remains unchanged |

The loss experiment uses real HTTP and the actual server. It suppresses the
client-visible response after success; it does not simulate a physical network
outage. Source rows, samples and credentials are excluded from publication.
The static HTML readback is derived from API responses, not the product UI.

## Execution and resource bounds

The dedicated CircleCI `catalogue` job uses an Ubuntu 24.04 machine executor,
class `large`, one job and no matrix. It is selected only by the qualification
branch or an explicit `run_catalogue: true` parameter. Do not enable it together
with `run_native`.

[scripts/run_circleci_openmetadata.sh](../scripts/run_circleci_openmetadata.sh)
sets a 25-minute command watchdog with shorter stage limits. The reviewed command
took 158 seconds; the live harness recorded 20.831684 seconds. These scopes overlap.
Runner provisioning and artifact transfer are outside the watchdog, and billed
credits remain unobserved. No automatic rerun or paid refill is configured.

For a separately authorised loopback server, the standalone publisher commands
are described in [GOVERNANCE.md](GOVERNANCE.md). Review the exact target and credentials
before enabling writes; the qualification setup is not a shared-server migration.

## Evidence inventory

| Artifact | Purpose |
|---|---|
| `openmetadata-diagnostics/images.json` | Resolved image identities |
| `openmetadata-diagnostics/job-attempt.json` | Commit, phase, exit, duration and cleanup |
| `openmetadata-diagnostics/harness-junit.xml` | Offline safeguards, not the live scenario count |
| `openmetadata-diagnostics/qualification.log` | Client execution and six-gate result |
| `openmetadata-evidence/qualification-openmetadata.json` | Live outcome, source profile, hashes and exclusions |
| `generation*-acceptance/plan/published/readback.json` | Accepted source and remote publication/readback chain |
| `http-traces.json`, conflict receipt and manifest | Mutation history, preserved conflict and artifact identities |

The reviewed run has 33 offline safeguard tests and six separate live scenarios.
The artifact review reconciled 30 table UUIDs, 170 column definitions, 22 lineage
edges, two DQ results and two basic suites. All fifteen supplied artifact digests
matched, with HTML explicitly reconstructed rather than described as a raw download.

## Compatibility and retained reservations

The tracing transport decodes compressed responses once under a byte budget and
removes obsolete framing headers. Basic-suite verification requires `basic=true`
and an exact `basicEntityReference` to the table UUID/type; it does not use the
deprecated `executable` field. Regression tests cover both behaviours.

Migration completed but emitted missing-relation queries during empty-database
initialisation, `SET LOCAL` warnings and a Logback core/classic mismatch. The review
preserves those observations. Original browser-rendered JUnit bytes, actual billing,
image signature verification, HA/restore/retention, TLS/SSO, Airflow/SDK ingestion
and UI inspection remain outside the accepted proof.

## Pinned upstream references

- [Deployment definition](https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/docker/docker-compose-quickstart/docker-compose-postgres.yml)
- [User API](https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-service/src/main/java/org/openmetadata/service/resources/teams/UserResource.java)
- [Test-suite schema](https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-spec/src/main/resources/json/schema/tests/testSuite.json)

The version is the adapter's qualification baseline, not a claim about the latest
production release. [Remaining gates](PROVIDER_GATES.md) cover subsequent platform work.
