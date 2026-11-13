# Primary technical references

I use version-specific upstream contracts to review compatibility and API behaviour.
Executed integration baselines are recorded separately in [STATUS.md](STATUS.md).

- Spark 4.0.1 requirements: https://spark.apache.org/docs/4.0.1/
- Delta/Spark compatibility: https://docs.delta.io/releases/
- Delta batch/version-pinned reads: https://docs.delta.io/delta-batch/
- Delta Spark 4.0.1 distribution: https://pypi.org/project/delta-spark/4.0.1/
- PostgreSQL transaction isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- Fabric read-only item inventory: https://learn.microsoft.com/en-us/rest/api/fabric/core/items/list-items

Documentation supports implementation decisions; actual runtime and permission
claims require execution evidence. The native and real catalogue runs have
separate reviewed baselines. Fabric/Power BI remains unqualified.

## OpenMetadata API contract — reviewed 12 November 2026

OpenMetadata is pinned to tag `1.12.0-release`, commit
`caa14bfd42af6ec84464aa81815addd3e0cd2902`. The following primary files were read:

- `api/data/createTable.json` — blob `ce0b34b634aef3fd5b25f290e21ac8ade0297a08`.
- `api/tests/createTestDefinition.json` — blob `13891c45e0e39082278737070ce24bca0b8ca20b`.
- `api/tests/createTestCase.json` — blob `a93a42eb20471bb3f8f4cd38dbac41485a3cc712`.
- `api/tests/createTestCaseResult.json` — blob `e4643ca9f1fe6c33db82f664df4d202c3a743ae9`.
- `tests/testDefinition.json` — supported `Other` platform.
- `tests/basic.json` — timestamp and result value contracts.
- `resources/dqtests/TestCaseMapper.java` — FQN string mapping.
- `jdbi3/TestCaseRepository.java` — optional `testDefinition` fields and automatic basic suite creation.
- `resources/dqtests/TestCaseResultResource.java` — actual POST/GET result route, blob `d60b8db1d5f3db00dcb9155c9532bd97b537416b`.

Schema root: https://github.com/open-metadata/OpenMetadata/tree/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-spec/src/main/resources/json/schema
Service root: https://github.com/open-metadata/OpenMetadata/tree/caa14bfd42af6ec84464aa81815addd3e0cd2902/openmetadata-service/src/main/java/org/openmetadata/service

The version-pinned request schema and resource take precedence over a generic
example describing an older PUT result route or unsupported testSuite field.
The protocol emulator is original test code, not vendored OpenMetadata; source
inspection and this emulator do not validate a real server.

Compatibility documentation reviewed: Spark 4.0.1 requires Java 17+, and the
Delta matrix pairs Delta 4.0.x with Spark 4.0.x. Compatibility documentation alone does not establish installation or execution.
The [native review](evidence/NATIVE_fc1a928_REVIEW.md) records the versions actually
installed and exercised on the accepted CI run.

## Repository maintenance references

- [GitHub issue-form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [GitHub issue-form validation](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/common-validation-errors-when-creating-issue-forms)
- [Python URL parsing and validation boundaries](https://docs.python.org/3.13/library/urllib.parse.html)

The repository checker uses a deliberately limited Markdown subset and makes no
external URL requests. Its supported behaviour is defined by regression tests,
not by a claim of full GitHub-flavoured Markdown conformance.
