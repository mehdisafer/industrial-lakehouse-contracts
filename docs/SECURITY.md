# Security boundaries

## Data and trust model

All bundled input is generated and labelled `PUBLIC_SYNTHETIC`. The demonstration
requires no production records, credentials or confidential schemas. I keep the
consumer boundary separate from administration of the host, database and filesystem.
A privileged administrator is not an adversary contained by the report API.

## Reporting API

Bearer tokens are stored as hashes and compared in constant time. Site filtering
precedes aggregation. Site-scoped identities cannot retrieve another site's orders
or obtain global evidence/catalogue through a separate permission flag. Reporting
opens journal state read-only.

Responses use no-store, content-type protection, framing denial and no referrer.
The unauthenticated page contains no row data. These are application-level controls,
not SSO, database row-level security, multi-tenant isolation or OS confinement.
External serving needs a separately reviewed deployment, TLS and credential lifecycle.
The demonstration binds to loopback.

## Source and filesystem controls

Source URLs are loopback-only. Redirects, unsafe continuation targets, identifier
injection, path traversal/symlink inputs and database-DSN query overrides are refused.
Capture and response budgets bound input processing. These checks are application
controls, not a kernel egress sandbox; native package/JAR resolution can use the
public network.

Hashes detect drift in ordinary operation; they are not signatures or protection
against privileged modification. Existing source data and ambiguous staged effects
are preserved rather than silently deleted. Filesystem race resistance and
multi-host fencing remain limited by the single-host design.

## Catalogue

The standalone publisher checks an explicit loopback API/version and pre-existing
synthetic service/owner/classification mappings. It refuses redirects, caps decoded
responses and does not persist tokens or server error bodies. Durable intent and
readback prevent blind retries.

The actual-product qualification used separate non-admin writer and reader identities
and exercised server-side denials. This is dedicated-instance resource-type RBAC,
not namespace multitenancy. The admin bootstrap fixture is isolated and ephemeral;
it is not a template for an externally exposed service.

## Credentials, artifacts and restoration

Keep local credentials in environment variables or generated policy files outside
Git. Native Compose requires a disposable URL-safe password or appropriately
encoded DSNs; never substitute a production credential. CI publishes selected
synthetic evidence, not source databases or runtime policies.

Reference archives exclude bearer policies and are not encrypted. Restore checks
archive integrity, rejects unsafe/duplicate/symlink entries and existing roots,
and preserves original path identity. An in-progress marker prevents admission
into an incomplete restore. This is bounded SQLite/filesystem recovery, not
PostgreSQL/Delta DR or a penetration test.

## Assurance and reporting

The repository hygiene check rejects accidentally tracked runtime/credential-file
paths; the separate history scanner looks for known secret patterns. Neither is
a comprehensive vulnerability assessment or SBOM attestation. Direct version pins
are not a full transitive lock, and image identity is not signature verification.

[SECURITY.md](../SECURITY.md) describes how to raise a concern without posting
sensitive material. The [qualification register](STATUS.md) and
[remaining gates](PROVIDER_GATES.md) identify what has and has not been demonstrated.
