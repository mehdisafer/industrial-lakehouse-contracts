# Qualification baselines

<!-- Generated from qualification-baselines.json by scripts/check_repository.py. -->

This register identifies the reviewed execution baselines. It is not a claim that every later commit reran those integrations.

Reviewed on **2026-11-13**.

| Capability | State | Executed revision | Scope and evidence |
|---|---|---|---|
| Native PostgreSQL / Spark / Delta / Dagster | accepted | `fc1a9286c937deb09b87b97524c6835b24a1d516` | Bounded synthetic single-host data, recovery and reporting checks. [Evidence](evidence/NATIVE_fc1a928_REVIEW.md). |
| OpenMetadata API integration | accepted | `cd09de03d658cb66d5aaa29a8ec677fd17a3f977` | Real product API, metadata readback and role checks with reference inputs. [Evidence](evidence/OPENMETADATA_cd09de0_REVIEW.md). |
| Combined native-to-catalogue flow | not-run | — | Separate successful runs do not establish one combined execution. [Evidence](PROVIDER_GATES.md). |
| Fabric and Power BI | planned | — | Read-only inventory exists; deployment and tenant qualification remain open. [Evidence](PROVIDER_GATES.md). |

See [qualification methodology](QUALIFICATION.md) for test counts and provenance, and [remaining gates](PROVIDER_GATES.md) for planned work.
