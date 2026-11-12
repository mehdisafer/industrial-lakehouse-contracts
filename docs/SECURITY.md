# Security boundary and disclosure review

All bundled input is generated, fictional and labelled `PUBLIC_SYNTHETIC`. No employer/client code, exports, names, identifiers, contracts or credentials are needed.

The API authenticates hashed bearer tokens with constant-time comparison. Site filtering precedes totals. A site-scoped identity cannot access other-site orders, nor global evidence/catalog through a separate permission flag. The CLI reporting consumer opens its state database read-only. Responses are `no-store`, `nosniff`, deny framing and omit referrers. No row data appear on the unauthenticated page.

These controls are **application-level demonstration RBAC**, not SSO, enterprise IAM, RLS in Fabric, OS confinement, multitenancy or resistance to an administrator of the host/database. TLS, token rotation/revocation and externally reachable serving need a separately reviewed deployment. Do not bind the demo to a public address.

Source URLs are loopback-only; redirects, external continuation targets, identifier injection and filesystem traversal/symlinks are rejected. Database DSN query overrides are rejected. The Fabric inventory helper follows only the exact allowed HTTPS host/workspace/path and never echoes server bodies or tokens on an HTTP error. Those Fabric tests use a mock HTTP transport and are not tenant validation.

The runtime hashes real bytes and detects ordinary drift. Digests are not signatures or a trust anchor against a privileged attacker. Immutable-directory conventions and path checks do not remove every host filesystem race. Existing source data and staging evidence are never automatically deleted.

Secrets belong in local environment variables or the generated access-policy file outside Git. The qualification uses random in-memory tokens and exports no tokens or password hashes in its evidence bundle. Test literals are deliberately non-production fixtures. Native Compose interpolation requires a URL-safe disposable password or separately encoded DSNs; production credentials are forbidden.

Before public release: confirm the repository/visibility/license; review every tracked file and artifact for data ownership, credentials, system paths and unsupported claims; qualify the CI; pin container images and evaluate dependency advisories. This increment has not performed a full security audit, SBOM attestation or vulnerability assessment.

## New governance and restore boundaries

OpenMetadata publishing accepts only an explicit loopback API/version and a
synthetic `ilc_` namespace. It checks prerequisite owners/classification before
mutations, refuses redirects, caps response bytes and does not persist tokens or
response error bodies. Write intents and exact readback prevent blind retries;
they are not distributed locks or proof of the server's authorization rules.

Reference archives exclude access policies and credentials. They are not
encrypted. SHA-256 must be retained outside the archive; it is not a signature.
Restoration refuses existing roots, unsafe ZIP paths, duplicate members, symlinks,
excessive sizes and changed root identity. An in-progress restore marker prevents
read/write admission. Restore tests are bounded filesystem/SQLite tests, not a
penetration test or a guarantee against a privileged host administrator.
