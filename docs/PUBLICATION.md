# Source-publication checklist

## Scope

I publish this repository to make its implementation, design decisions and
execution evidence inspectable. Source visibility does not deploy the reporting
API or OpenMetadata server and does not complete the Fabric/Power BI roadmap.
The target repository is `mehdisafer/industrial-lakehouse-contracts`.

## Content review

Before changing visibility, I check the current tree and reachable history for
credentials, confidential material and unsupported claims. Issues, PR discussions
and any newly exposed logs/artifacts need their own review. Source databases,
runtime policies and raw service dumps are not automatically publication material.

The reference CI includes two complementary checks:

- `scripts/check_repository.py` checks tracked documentation paths/anchors,
  generated qualification status and repository hygiene.
- `scripts/publication_gate.py` scans reachable Git objects with a size/SHA-256
  pinned Gitleaks binary and a synthetic positive control.

A missing inventory, inconsistent scanner result or finding blocks the disclosure
gate. Rule-based absence of findings is not a full security, privacy, ownership
or dependency assessment. Review findings; do not weaken checks to obtain a green
status. Keep redacted reports rather than publishing secret values.

## Evidence and release review

The [baseline register](STATUS.md) and historical reviews distinguish accepted
native/catalogue functionality from planned provider work. Evidence stays tied to
its actual execution revision. Reconstructed JSON/HTML, browser-modified JUnit and
observed-versus-unknown billing are described accurately in the reviews.

Before release, verify the exact candidate's reference CI, complete affected
documentation and merge state. Preserve the accepted integration branches and
receipts. A documentation-only revision does not create a new runtime proof.

## Repository settings

Visibility remains a separate administrative decision. After the content review,
change only this repository through GitHub Settings and verify anonymous access
to the README and source. A merge, changelog entry or CI success is not evidence
that the visibility setting has changed.

The original project uses the [MIT License](../LICENSE), approved on 13 November
2026. Keep the root notice, package metadata and contribution terms consistent;
third-party components retain their own licences as described in
[LICENSING.md](LICENSING.md). This licensing decision does not close the disclosure
review or change repository visibility.

Review the description, topics, required CI checks and contribution/security entry
points as part of the release decision. Verify the applied branch rules through
GitHub; a documented proposal is not an enforced server-side rule. GitHub Pages
or an always-on service is not implicitly created by publishing source.

## Release boundary

Keep demonstration services loopback-bound. Do not add public ingress, provider
credentials, paid capacity, destructive cleanup or a change of licence terms as an
unrelated side effect. The [security guide](SECURITY.md) and
[remaining gates](PROVIDER_GATES.md) define the operational boundaries.
