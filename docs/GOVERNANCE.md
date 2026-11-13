# Accepted-generation metadata publication

## Purpose and API contract

I publish metadata from a verified accepted generation, not directly from a
partially loaded source. The publisher binds schema, ownership, classification,
lineage and aggregate quality to that generation's identity.

The adapter targets OpenMetadata 1.12.0 at upstream revision
`caa14bfd42af6ec84464aa81815addd3e0cd2902`. Its real API qualification at
`cd09de03d658cb66d5aaa29a8ec677fd17a3f977` is accepted; see the
[evidence record](evidence/OPENMETADATA_cd09de0_REVIEW.md).
Unit tests and the named catalogue emulator remain separate protocol evidence.

## Metadata exported

For the five-entity contract, each generation exports fifteen definitions:
five raw-string Bronze tables, five typed Silver tables and five Gold tables.
The plan includes owner-team references, `PUBLIC_SYNTHETIC` classification,
eleven table-level lineage edges and one external reconciliation result.

Source rows, samples, rejected records, credentials and dashboard assets are not
exported. The contract-generated site dimension has no fabricated upstream table.
The source profile remains in the receipt. Accepted aggregate DQ is published;
this is not a complete rejected-run incident feed.

Each generation has an immutable catalogue database name. This preserves historical
identity but increases metadata volume; automatic catalogue retention is not
implemented. [DATA_MODEL.md](DATA_MODEL.md) explains the business and table grains.

## Delivery, readback and conflicts

The outbox records an immutable plan and REQUESTED/VERIFIED states. Intent is
persisted before mutation, and every entity, edge and DQ result is then reread.
A later invocation checks remote state before attempting another effect.

An exact existing object after a lost response is reused. Unresolved absence,
inconsistent state or a foreign object stops the operation; the publisher does
not overwrite, delete or silently repair it. A local writer lock is not cross-host
fencing. A generation change during export construction is also rejected.

The reviewed live run observed mutation-free replay and preserved a conflicting
object with no mutation. Its response-loss test suppressed the client-visible
response after a real successful write, then reconciled the same object.
It was not a physical network-outage experiment.

## Permissions and destination

The standalone publisher admits explicit loopback `/api` settings, the exact
server version, a dedicated `ilc_` service and existing owner-team/tag mappings.
It refuses redirects, credential-bearing URLs and oversized responses. Tokens
remain outside plans, journals and Git. The publisher does not initialise users,
services, teams or classifications.

The separate disposable qualification harness bootstraps those prerequisites,
then publishes with a non-admin writer and rereads with a separate reader. Actual
server denials establish the tested resource-type roles, not multi-tenant namespace
isolation. Full deployment and role details are in [OPENMETADATA_LIVE.md](OPENMETADATA_LIVE.md).

## Commands

Build a metadata-only plan from an accepted reference runtime:

```bash
python scripts/governance.py --root .runtime/pipeline \
  --settings governance/openmetadata.example.json --output artifacts/catalog-plan.json
```

For an explicitly authorised real loopback instance, supply
`ILC_OPENMETADATA_TOKEN` outside Git and enable the two write flags:

```bash
python scripts/governance.py --root .runtime/pipeline \
  --settings governance/openmetadata.example.json \
  --publish --allow-catalog-writes --output artifacts/catalog-receipt.json
```

These commands expect a previously accepted runtime at the stated path. They do
not create one. The CLI defaults to the reference journal; a native-profile
publication requires its separate prerequisites and has not been qualified as a
combined path.

## Result semantics

`REMOTE_METADATA_READ_BACK` describes the publication operation. Deployment,
server-role and recovery evidence comes from the live qualification, not from that
single receipt alone. An earlier data-acceptance receipt's `catalog_provider=NOT_RUN`
is not rewritten after the subsequent catalogue operation.

Result submission uses the pinned test-case result endpoint and basic suites bound
to the exact parent table. The live transport decodes compressed responses once
within its byte budget. Upstream API details and compatibility tests are documented
in [the live guide](OPENMETADATA_LIVE.md#compatibility-and-retained-reservations).

Current limits and future provider work are in [PROVIDER_GATES.md](PROVIDER_GATES.md).
