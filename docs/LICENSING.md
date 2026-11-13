# Licensing and third-party scope

## Original project code and documentation

I release the original Industrial Lakehouse Contracts code and its associated
documentation under the [MIT License](../LICENSE), following my explicit licensing
decision on 13 November 2026. The copyright notice is **Copyright (c) 2026 Mehdi Safer**.
The full text in the root LICENSE file governs the grant.

MIT permits use, modification, redistribution and commercial reuse, subject to
retaining its copyright and permission notice in copies or substantial portions
of the software. It includes the stated warranty and liability disclaimer.
This choice is not a claim of production readiness or support availability.

Repository visibility is a separate setting. Adding the licence does not publish
a private repository or deploy its demonstration services. Historical execution
records describe the state at their review date; they are not rewritten to imply
that this licence existed on earlier qualification commits.

## Python distribution metadata

[pyproject.toml](../pyproject.toml) declares the SPDX expression `MIT` and explicitly
includes `LICENSE` through `license-files`. The build-backend minimum is
`setuptools>=77.0.3` for the PEP 639 metadata format. Runtime and optional integration
dependency versions are unchanged by this licensing decision.

The licensing tests check the root notice, declared metadata and the installed
editable distribution's `License-Expression`, `License-File` and included licence
text. Those checks do not constitute a transitive licence audit or a full test of
all distribution formats.

## Contributions

Contributions accepted into the original project must be offered under the same
MIT terms. Contributors retain their copyright and must have the rights needed
to contribute the material. Preserve applicable upstream notices and identify
third-party material explicitly; see [CONTRIBUTING.md](../CONTRIBUTING.md).
Do not submit employer/client code, confidential documents, real records or secrets.

## Dependencies and external products

Python dependencies, upstream API specifications, container images and CI tools
retain their own licences. MIT for this project does not relicense those components.
No OpenMetadata, PostgreSQL, Elasticsearch, JDK or Gitleaks binary is distributed
as original project code.

The Compose files and qualification harness describe an original synthetic
integration. Upstream schema/deployment references remain in
[OPENMETADATA_LIVE.md](OPENMETADATA_LIVE.md) and [SOURCES.md](SOURCES.md).
No claim is made that every transitive dependency has passed legal or security
review. Redistribution of third-party components requires its own notice and
compatibility assessment.

## References

- [Standard MIT text](https://choosealicense.com/licenses/mit/)
- [GitHub repository licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
- [Python package licence metadata](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license-and-license-files)
