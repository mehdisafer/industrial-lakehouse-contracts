# Run and inspect the demonstration

## Scenario

A reporting consumer needs the last trustworthy sales-fulfillment snapshot even
when a source delivers invalid data or a process stops between materialisation
and publication. This demonstration shows that distinction through actual data,
state transitions and reporting responses.

## Run the reference flow

Clone the repository, activate a Python 3.12/3.13 virtual environment and install
the project as described in the [README](../README.md#quick-start). From the root:

```bash
python scripts/check_repository.py
python -m ilc.cli validate
python scripts/qualify_reference.py --output .runtime/demo-001 --rows 10000
```

Use a new destination on each run. The script creates synthetic database/CSV
fixtures, starts bounded loopback HTTP services, executes the scenarios and stops
the services when it exits. No managed cloud account is required.

## Inspect the outputs

In `.runtime/demo-001/evidence/`, inspect:

| Output | What to examine |
|---|---|
| `qualification.json` | Scenario results, source identity and measured scope |
| `report-initial.html` | First accepted generation and reconciled totals |
| `report-degraded.html` | Rejected latest attempt; previous accepted dataset retained |
| `report-recovered.html` | Recovered generation and its batch/contract/target lineage |

The HTML files are static exports of authorised reporting API responses. Open them
as files; no public server or credentials are needed. Read the accompanying JSON
receipts for the underlying evidence rather than treating a screenshot as a test.
The `work/` directory contains runtime/source state and is not a publication bundle.

The fixed fixture time can produce `STALE`. That indicates old data, not failed
processing. `DEGRADED` indicates a rejected latest attempt, not loss of the previous
accepted dataset. [DATA_MODEL.md](DATA_MODEL.md) defines the measures and grains.

## Expected business behaviour

| Event | Consumer outcome |
|---|---|
| Clean 10,000-record input | 995 orders, 3,980 facts; ordered amount 8,857,766.18 EUR |
| Duplicate key, invalid amount or schema drift | Candidate rejected; no publication or watermark advance |
| Interrupted target publication | Last accepted generation remains reportable |
| Resume with the HTTP source stopped | Frozen input and target reconciled; one replacement generation |
| Intended SITE_A revision | Ordered amount 8,857,786.18 EUR; order/fact counts unchanged |
| Request outside permitted site scope | Request denied before unauthorised totals can be exposed |

These figures describe the deterministic fixture, not a performance benchmark or
customer outcome. The [reviewed native run](evidence/NATIVE_fc1a928_REVIEW.md)
exercised its engine-specific path separately.

## Explore recovery and governance

```bash
python scripts/qualify_recovery_governance.py --output .runtime/recovery-001 --rows 10000
```

This additional reference flow exercises same-path SQLite restoration and a
catalogue **protocol emulator**. For the real OpenMetadata API integration, use the
[separate catalogue guide](OPENMETADATA_LIVE.md) and its
[reviewed evidence](evidence/OPENMETADATA_cd09de0_REVIEW.md). The static catalogue
readback is API-derived, not a screenshot of the product UI.

## Extend the model

Start with [contracts](CONTRACTS.md) and the [architecture decisions](ARCHITECTURE.md).
Entity ingestion is metadata-driven; a new business metric still requires reviewed
code, reconciliation and tests. Use the [contribution guide](../CONTRIBUTING.md)
for the required change evidence.
