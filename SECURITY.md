# Security

This repository is an inspectable synthetic data-platform implementation. Its
services are designed for isolated, loopback-bound demonstrations, not direct
Internet exposure.

I document the application, filesystem, database and catalogue boundaries in
[the security guide](docs/SECURITY.md). Reviewed functionality is recorded in the
[qualification baselines](docs/STATUS.md); this is not a production security
certification or a vulnerability-response SLA.

## Reporting a concern

Do not place tokens, private records, exploitable credentials or confidential
infrastructure details in a public issue. Use GitHub's private vulnerability
reporting option when it is enabled for this repository. Otherwise, open only a
non-sensitive request for a private reporting channel; do not post the sensitive
payload while arranging that channel.

A useful report identifies the affected commit/profile, a synthetic reproduction,
the observed boundary violation and the expected behaviour. Runtime policies,
bearer tokens, source databases and raw service dumps should remain outside Git.
