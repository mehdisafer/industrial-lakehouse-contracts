# OpenMetadata export: implementation and qualification boundary

## Supported contract, not a claim of deployment

The adapter targets **OpenMetadata 1.12.0**, pinned to upstream commit
`caa14bfd42af6ec84464aa81815addd3e0cd2902`. It is built from the published request
schemas and Java resource definitions at that revision, not from a floating SDK
or a guessed endpoint. No OpenMetadata product was installed in the authoring
container. The test peer is explicitly `tests/support/openmetadata_emulator.py`.
A successful exchange with that peer is **protocol/control-flow evidence only**.

The pinned source matters: results use `POST /api/v1/dataQuality/testCases/testCaseResults/{fqn}`,
with `GET` on the same route and `startTs/endTs` in milliseconds. The older
`PUT .../{fqn}/testCaseResult` shape is not used. Test-definition readback requests
`fields=testDefinition`. The 1.12 repository creates a basic test suite when
preparing a new table-linked test case; this adapter does not add an unsupported
`testSuite` field to `CreateTestCase`. Any implicit suite creation is an additional
server-side effect and must be reviewed on the actual sandbox.

## Destination prerequisites and scope

Use only a dedicated local synthetic instance. The configured URL is restricted
to loopback `/api`; redirects and credential-bearing URLs are refused. Before
writing, the adapter checks the exact version, the `ilc_` database service, all
mapped owner teams and the `ILCSynthetic.PUBLIC_SYNTHETIC` classification tag.
Those prerequisites must already exist. No admin user, team, classification or
service is automatically created by this tool.

A service token with the necessary metadata CRUD/view/test permissions is required
for a real test. It is supplied through `ILC_OPENMETADATA_TOKEN`, never inside the
contract, export plan or durable delivery journal. Synthetic names are not access
control; actual token permissions and negative server RBAC tests remain a gate.

## What is exported

Only an accepted generation whose target and receipt have been reread can produce
an export plan. A generation change during plan construction is rejected rather
than combining two snapshots. For the five-entity base contract the plan contains:

- 15 explicit tables: five raw Bronze, five typed Silver and five Gold.
- Owner team references, explicit synthetic classification and contractual column types.
- 11 table-level lineage edges. The contract-generated site dimension does not acquire a fabricated source table.
- One external reconciliation test definition/case and a result tied to the acceptance timestamp/digest.

Bronze columns are serialized strings; they are not falsely described as already
having Silver types. No record samples, rejected rows, credentials, private host
paths or invented dashboard asset are exported. The reference-vs-native source
profile is retained. Only accepted aggregate reconciliation is published currently;
rejected-run diagnostics are still local and are not a complete DQ incident feed.

Each accepted generation gets an immutable `ilc_` catalog database name. This
trades simplicity and provenance for metadata growth. No automatic retention or
deletion is included. This is a bounded demonstration, not a catalog lifecycle
solution for production.

## Durable delivery and unknown effects

The local outbox holds an immutable plan plus `REQUESTED`/`VERIFIED` operation
states. Intent is persisted **before** a metadata mutation. A response alone is
not enough: every created entity, edge and quality result must be read back and
matched. A subsequent invocation first reconciles the remote state.

If a write response was lost but the exact object exists, it is reused. If the
object is absent or inconsistent after an attempted write, the operation stops
with an unknown outcome or conflict; it does not blindly resend. A pre-existing
foreign object or later drift is not overwritten. No automatic retry, DELETE or
repair is performed. One local writer is enforced for the outbox. This does not
provide distributed fencing against other hosts writing the same catalog; use a
single authorized namespace writer.

## Commands

```bash
# Generate a metadata-only plan. This does not contact the catalog.
python scripts/governance.py --root .runtime/pipeline \
  --settings governance/openmetadata.example.json --output artifacts/catalog-plan.json

# On an explicitly authorized real local instance only:
# set ILC_OPENMETADATA_TOKEN outside Git and review the destination first.
python scripts/governance.py --root .runtime/pipeline \
  --settings governance/openmetadata.example.json \
  --publish --allow-catalog-writes --output artifacts/catalog-receipt.json
```

The example CLI defaults to the **reference** journal. An explicit `--profile`
can select a native journal, subject to its separate demo opt-in, dependencies and
database restrictions. That pathway is not executed or qualified in this delivery. `REMOTE_METADATA_READ_BACK` names a readback
observation, not a deployment verdict. Preserve the peer identity/environment in
any external qualification report.

## Evidence still required

Actual server startup/version, service and tag prerequisites, positive/negative
server permissions, entity and column readback, lineage display, DQ result
readback, interrupted real-server recovery and catalog retention. Unit tests,
MockTransport and a real HTTP server running our emulator satisfy none of those
product-specific gates.

## Real product qualification route

The bounded, separate CircleCI deployment and live permission/replay/conflict
scenarios are implemented in [OPENMETADATA_LIVE.md](OPENMETADATA_LIVE.md).
The input is a newly accepted reference-profile generation, not a repeated native
Spark qualification. Existing emulator tests remain emulator evidence. The live
route uses actual OpenMetadata 1.12.0 HTTP APIs, and its precise executed outcome
is recorded in issue #4 only after observation. No default admin token is used
for publication and no secrets are exported.
