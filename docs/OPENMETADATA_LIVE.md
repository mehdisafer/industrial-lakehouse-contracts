# P01 G3a — real OpenMetadata qualification

I qualify the catalogue product separately from the already reviewed native G2
run. The new command uses a freshly accepted **reference_sqlite** generation,
then sends actual HTTP requests to OpenMetadata 1.12.0. This is not an emulator,
and it does not rerun or claim a new combined Spark/catalogue qualification.
The native G2 evidence at `fc1a928` remains unchanged.

## Observed checkpoint — 13 November 2026 (Europe/Paris)

**Both catalogue and reference jobs report SUCCESS on
`cd09de03d658cb66d5aaa29a8ec677fd17a3f977`.** The catalogue success was posted
at 2026-11-12 23:43:13 UTC. The configured live harness completed; private
artifact contents, actual image digests, role/readback traces, cleanup outcomes
and credit usage have not yet been independently inspected. **Final G3a
acceptance remains open in issue #4.**

- [Successful catalogue job](https://app.circleci.com/workflow/44a92cbe-4817-45b8-8df2-70e106367dc9/job/167d2f85-ca05-45a5-a6a7-937bf513354b)
- [Successful reference job](https://app.circleci.com/workflow/a92aa335-2ecb-4898-ae2a-64855831f898/job/f2c4bd4b-baea-40d1-ab3d-ef6d76e82739)

The initial catalogue job at `a99c173` failed; its exact failed step remains
unread. The corrective commit fixes two defects established from source/offline
reproduction: gzip double decoding and the deprecated executable-suite check.
Later success is not proof of the unread first failure's cause. Two catalogue
attempts and two reference jobs were triggered; no additional native/Spark run.

Local targeted checks passed 65 cases (33 harness, 32 publisher), using synthetic
transport/receipt inputs where labelled. An earlier recovered-V3 materialization
run passed 219 cases with one native skip; it did not contain the 41 previously
added GitHub CI tests and is not the complete current hosted suite. Exact hosted
reference test counts are not inferred. The documentation-only checkpoint does
not trigger another run; inspect the existing artifacts instead.

## Reproducible deployment, not a shared environment

`infra/compose.openmetadata.yml` starts PostgreSQL 16, Elasticsearch 9.3.0,
OpenMetadata 1.12.0 migration and server containers on a disposable CircleCI VM.
The version remains pinned to the adapter's reviewed API. The upstream release
reference is `caa14bfd42af6ec84464aa81815addd3e0cd2902`. This is a qualification
version, not a claim that it is the latest supported production release.

Only the server API is published, on `127.0.0.1:8585`. PostgreSQL, Elasticsearch
and the server administration port have no host-published listener. Containers
have no access to client data, personal files or production credentials. The
service's default administrator is a disposable fixture on this isolated host,
never a credential for an external account. Publisher and reader passwords,
JWT signing keys and database/encryption credentials are generated per job.
They remain outside Git and artifact paths. Self-signup and the Airflow ingestion
service client are disabled.

A fresh `ilcg3_<job>_<sha>` Compose project is required. The script refuses an
existing project, output directory or bootstrap entity rather than reinitializing
it. At exit it stops only its own services; named volumes are not deleted or
shared. CircleCI disposes of the VM. No DROP, TRUNCATE, prune, persistent cloud
resource, public ingress, paid refill or personal workstation is involved.

Image tags are version-selected but mutable. `images.json` records each resolved
repository digest and image identity. The run checks the actual API version.
These observations are not a signed supply-chain attestation or a complete
transitive lock. PostgreSQL here stores catalogue metadata, not the P01 source.

## Roles and actual acceptance checks

`qualify_openmetadata.py` creates a dedicated service, owner team, synthetic tag,
policies, roles and two non-administrator users. Admin credentials are used only
for bootstrap and controlled sentinel preparation. Publication uses the writer
session; independent catalogue reads use the reader session.

The writer may create/edit database/schema/table/test metadata and read metadata.
It cannot create/edit/delete policy, role, user, team, tag, classification or
service metadata, and cannot delete data entities. The reader has an explicit
mutation deny. This is **resource-type RBAC on a dedicated server**, not a claim
of multi-tenant, per-namespace isolation. HTTP (not TLS) is deliberate loopback
qualification; this deployment is not a production security template.

| Gate | Required live observation |
|---|---|
| G3-01 | Actual 1.12.0 product, authenticated bootstrap, recorded image digests |
| G3-02 | Two accepted generations: 15 table definitions, 11 lineage relations and one DQ result per generation; column types, owners, tags and implicit basic test suites reread |
| G3-03 | Repeating a verified publication performs no additional write |
| G3-04 | Client transport deliberately loses one response after a real successful database write; a new publisher instance reconciles its durable intent and the same server UUID; exactly one database PUT |
| G3-05 | Unauthenticated read 401, reader table modification 403, writer policy creation 403; the forbidden policy is absent and accepted metadata unchanged |
| G3-06 | A deliberately conflicting database is preserved with no publisher mutation; generation 1 remains unchanged after generation 2 |

The response-loss experiment forwards real HTTP to the real server. Only the
client-visible response is suppressed after success; no fake server response or
MockTransport is used in the live command. It does not prove a physical network
outage, concurrent cross-host writers or distributed exactly-once semantics.

The harness refuses success unless all six gates pass. Metadata definitions and
aggregate reconciliation are exported, never source rows, samples or credentials.
A static HTML view is generated from the actual API readback; it is explicitly
not a screenshot of the OpenMetadata UI. Airflow/SDK connector ingestion is not
part of this API-publisher qualification.

## CircleCI route and credit discipline

The dedicated `catalogue` job uses `machine: ubuntu-2404:current`, class `large`
(4 vCPU / 15 GB), Docker Compose and a Python 3.12 test container. A 25-minute
command watchdog includes image pulls, migration and qualification, with shorter
stage limits. VM provisioning, checkout and artifact upload are outside that
watchdog. It is not a billing cap. The documented gen1 large rate is 20 credits
per minute: 500 command-time credits at the ceiling plus overhead, **not an
observed bill**. Actual credits remain unknown until account usage is read.

Only a deliberate push to `qualify/p01-openmetadata-20261113` or an explicit
`run_catalogue: true` selects this route. Do not combine `run_catalogue` and
`run_native`. Ordinary feature pushes keep reference tests; setup synchronization
runs neither heavy job. The existing native and reference job bodies are
unchanged. There is no matrix, automatic retry, remote-Docker surcharge, paid
cache or plan change. An unexplained failure requires reading diagnostics, not
blindly rerunning or increasing resources.

## Evidence and interpretation

- `openmetadata-diagnostics/images.json`: resolved real container identities.
- `openmetadata-diagnostics/job-attempt.json`: exact commit, phase, exit code and
  elapsed command scope; no inferred billing.
- `openmetadata-diagnostics/{migration,services,qualification}.log`: bounded,
  credential-redacted diagnostics.
- `openmetadata-diagnostics/harness-junit.xml`: **offline harness safeguard tests**,
  not live product test counts.
- `openmetadata-evidence/qualification-openmetadata.json`: actual six-gate result,
  source profile, source fingerprints and limits.
- `openmetadata-evidence/generation*-{acceptance,plan,published,readback}.json`:
  accepted input and independently reread catalogue state.
- HTTP method/path/status trace, conflict receipt and SHA-256 manifest.

A green CI job and these artifacts are distinct evidence levels. Final acceptance
requires reading the actual result and its identities. Missing artifacts are not
success. Tests that use stub HTTP transports are explicitly labelled offline.
The local materialization contains original V3 sources plus the new harness; the
previously added Java/native-evidence CI tests remain on GitHub and are exercised
by the reference job, not falsely included in a local test count.

G3a is **implemented with successful live CI; private artifact review remains
pending** on the exact runtime commit above. The PR/issue retain both attempts. Raw native JUnit
archival and credit accounting remain G2 reservations; they do not trigger another
Spark run. Fabric/Power BI remains an independent authorized-tenant gate. P05/P03
stay queued; `main`, repository visibility and licensing are unchanged.

## Primary references checked for this implementation

- Pinned deployment: https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/docker/docker-compose-quickstart/docker-compose-postgres.yml
- Login schema: https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-spec/src/main/resources/json/schema/auth/loginRequest.json
- User API: https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-service/src/main/java/org/openmetadata/service/resources/teams/UserResource.java
- Database-service request: https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-spec/src/main/resources/json/schema/api/services/createDatabaseService.json
- Policy operation examples: https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-service/src/main/resources/json/data/policy/IngestionBotPolicy.json
- CircleCI Linux VM: https://circleci.com/docs/guides/execution-managed/using-linuxvm/
- Plan availability: https://circleci.com/pricing/
- Credit rates: https://circleci.com/pricing/price-list/

## Transport and test-suite compatibility correction

An offline compressed-response reproduction exposed a double-decompression bug
in the new tracing transport. It now decodes once under a byte budget and removes
upstream encoding/length headers before returning the decoded HTTP response.
Two tests cover gzip decoding and the decompressed response limit.

The pinned OpenMetadata 1.12.0 test-suite schema deprecates `executable` in favour
of `basic` and `basicEntityReference`. The readback now requires `basic=true` and
the exact parent table UUID/type; it does not accept an absent or foreign suite.
Five additional offline cases cover that binding. These are verified source and
unit-test corrections, not a diagnosis inferred from an unread cloud log.

- Pinned suite schema: https://github.com/open-metadata/OpenMetadata/blob/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-spec/src/main/resources/json/schema/tests/testSuite.json
