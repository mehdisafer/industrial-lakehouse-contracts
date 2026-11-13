# Documentation

I organise the documentation around three questions: what the pipeline does,
why it is designed this way, and what has actually been demonstrated.

## Evaluate the project

| Document | What it answers |
|---|---|
| [Demonstration](DEMO.md) | How to run the reference flow and inspect its outcomes |
| [Business model](DATA_MODEL.md) | Entity grain, keys, relationships and KPI definitions |
| [Architecture](ARCHITECTURE.md) | Data/control separation, publication authority and design trade-offs |
| [Qualification baselines](STATUS.md) | Exact reviewed native and catalogue execution revisions |
| [Qualification method](QUALIFICATION.md) | Test layers, evidence provenance and interpretation |

## Operate and extend

| Document | Purpose |
|---|---|
| [Runbook](RUNBOOK.md) | Prerequisites, commands, evidence and failure handling |
| [Contracts](CONTRACTS.md) | Schema validation and metadata-driven entity onboarding |
| [Recovery](RECOVERY.md) | Idempotency, uncertain outcomes and accepted-state recovery |
| [Backup and restore](BACKUP_RESTORE.md) | Reference-profile backup semantics and limits |
| [Governance](GOVERNANCE.md) | Metadata-only export, durable outbox and readback |
| [OpenMetadata integration](OPENMETADATA_LIVE.md) | Real-product deployment, roles and six qualification scenarios |
| [Continuous integration](CI_CIRCLECI.md) | Test routes, repository checks and resource bounds |
| [Contribution guide](../CONTRIBUTING.md) | Change scope, reproduction and review requirements |

## Review evidence and scope

[Native execution review](evidence/NATIVE_fc1a928_REVIEW.md) and
[catalogue execution review](evidence/OPENMETADATA_cd09de0_REVIEW.md) are historical
records tied to their executed commits. Administrative status statements in those
records describe their review date; the [baseline register](STATUS.md) and
[remaining gates](PROVIDER_GATES.md) describe the current qualification scope.

[Security boundaries](SECURITY.md), [publication checklist](PUBLICATION.md),
[licensing status](LICENSING.md) and [upstream references](SOURCES.md) address
operational and disclosure concerns. The [changelog](../CHANGELOG.md) records
subsequent maintenance without rewriting execution evidence.
