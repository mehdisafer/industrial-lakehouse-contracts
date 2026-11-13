# OpenMetadata publication and durable delivery

## Qualified API contract

The publisher targets OpenMetadata **1.12.0**, upstream commit
`caa14bfd42af6ec84464aa81815addd3e0cd2902`. Request schemas and Java resource
contracts, rather than a floating SDK or guessed endpoint, define the adapter.
Unit tests and a named protocol emulator remain offline evidence. The separate
actual-product run at `cd09de0` is now accepted after supplied-artifact review;
see [G3a evidence](evidence/OPENMETADATA_cd09de0_REVIEW.md).

Results use `POST /api/v1/dataQuality/testCases/testCaseResults/{fqn}` and GET on
the same route with millisecond `startTs/endTs`. Test-case readback requests
`fields=testDefinition`. The server implicitly creates a basic suite for a
new table-linked case; no unsupported `testSuite` request property is invented.
The live readback verifies `basic=true` and the exact parent-table UUID/type.

## Destination and permissions

The publisher admits only explicit loopback `/api` settings, the exact version,
a dedicated `ilc_` database service, mapped owner teams and the synthetic tag.
Redirects, credential-bearing URLs and oversized responses are refused.
The publisher itself does not create admin identities, services, teams or tags.

Its separate disposable CI harness bootstraps prerequisites using an admin fixture,
then publishes with a non-admin writer and rereads with a distinct reader. Actual
server logs show the expected unauthenticated 401 and mutation/administration 403
responses. This is resource-type RBAC in a dedicated instance, not multi-tenant
namespace isolation. Supply credentials outside plans, journals and Git.

## Export contents

Only a reread accepted generation can create an export plan. Generation drift
while building it is rejected. For the five-entity contract, each plan contains
fifteen tables: five raw-string Bronze, five typed Silver and five Gold; owner
team references; synthetic classification; eleven table-level lineage edges; and
one external reconciliation result bound to acceptance time/digest.

The contract-generated site dimension has no fabricated upstream table. No source
records, samples, rejected rows, credentials, private host paths or dashboard
assets are exported. The source profile is retained. Accepted aggregate DQ is
published, not a complete rejected-run incident feed.

Each generation receives an immutable catalogue database name. This preserves
provenance at the expense of metadata growth. Automatic retention/deletion is
not implemented or implied by the demonstration.

## Durable intent, replay and conflicts

The outbox stores an immutable plan and REQUESTED/VERIFIED states. Intent is
persisted before mutation; every entity, edge and DQ result must subsequently be
read back and matched. A later invocation reconciles remote state first.

A lost response with an exact existing object is reused; unresolved absence or
inconsistency after a requested effect stops instead of blindly repeating it.
Foreign objects are not overwritten. No automatic DELETE or repair is performed.
A local writer lock does not provide cross-host fencing.

In the reviewed actual run, replay has zero mutations, conflict handling has five
reads and zero mutations, and generation-2 recovery has exactly one database PUT
whose successful response was deliberately suppressed in the client transport.
This is a controlled client fault, not a physical network outage. The shared test
definition is reused, explaining 33 initial mutations versus 32 in generation 2.

## Commands

```bash
# Build a metadata-only plan without contacting the catalogue.
python scripts/governance.py --root .runtime/pipeline \
  --settings governance/openmetadata.example.json --output artifacts/catalog-plan.json

# On an explicitly authorized real loopback instance only;
# supply ILC_OPENMETADATA_TOKEN outside Git first.
python scripts/governance.py --root .runtime/pipeline \
  --settings governance/openmetadata.example.json \
  --publish --allow-catalog-writes --output artifacts/catalog-receipt.json
```

The CLI defaults to the reference journal. An explicit native profile is subject
to separate dependencies, database restrictions and opt-in; that combined pathway
has not been executed in the reviewed G3a run.

## Evidence boundaries

The live catalogue used newly accepted reference_sqlite generations, not a repeated
native Spark qualification. `REMOTE_METADATA_READ_BACK` is an operation receipt;
actual deployment/RBAC/recovery evidence comes from the separate live harness and
its reviewed server traces. An earlier data receipt's `catalog_provider=NOT_RUN`
is not rewritten after the subsequent metadata operation.

Fifteen artifact hashes, thirty table UUIDs, 170 columns, twenty-two edges, two DQ
results and two basic suites reconcile. Original XML bytes and billed credits
remain unverified. The HTML is an API-derived snapshot, not an OpenMetadata UI
screenshot. TLS/SSO, HA, catalogue restore/retention, SDK/Airflow connectors and
multi-tenant security remain outside scope.

See [live deployment](OPENMETADATA_LIVE.md), [qualification](QUALIFICATION.md)
and [remaining provider gates](PROVIDER_GATES.md).
