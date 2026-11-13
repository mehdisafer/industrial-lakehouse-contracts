# Portfolio preview — disclosure checklist

## Target and authority

The publication target is exactly `mehdisafer/industrial-lakehouse-contracts`.
The owner requested public exposure on 13 November 2026. The intended result is
a readable repository with reproducible synthetic demonstrations and evidence,
not an Internet-facing database, catalogue admin endpoint or production service.

Native G2 and catalogue G3a are accepted within their separate documented
scopes. Fabric/Power BI remains open. A public preview is not completion of all
provider work, a production-readiness statement or a new open-source licence.

## Mandatory pre-publication checks

- Review source, current documentation, reachable historical objects, issue/PR
  text and any logs/artifacts that will become visible; exclude client material,
  source databases, runtime policies, JWTs and personal infrastructure records.
- Run `scripts/publication_gate.py` in the exact CircleCI checkout. Its Gitleaks
  8.30.1 binary is size/SHA-256 checked against the pinned upstream release.
  All remote heads/tags are fetched; unique Git blobs and commit/tag metadata
  are exported under bounded byte/object limits and checked against Git identity.
- Require the scanner's positive control to detect a newly generated synthetic
  token-shaped value; require an actual zero-finding history scan with consistent
  exit/result data. Missing Git history, scanner failure or findings block it.
- Review any findings without putting secret values in logs, issues or commits.
  The scanner publishes only rule/location/fingerprint summaries. Do not weaken
  the gate or rewrite history merely to obtain a green status.
- Retain the exact candidate SHA and successful reference status before merging.
  Keep the accepted native/catalogue branches at their executed commits.

The new scan is part of the reference job and has a ten-minute command watchdog.
It does not start Spark or OpenMetadata and does not change a billing plan.
Watchdogs do not constitute account-wide spend caps. Scanner rules are not a
proof that every confidential item, vulnerability or licensing issue is absent.

## Public evidence selection

Publish the bounded reviews, synthetic metadata summaries and source identities.
Do not automatically commit raw VM/service logs or browser-modified JUnit XML.
The detailed catalogue review reconciles all fifteen supplied artifact hashes;
the HTML is explicitly reconstructed rather than represented as a raw download.
Actual credits and original XML bytes remain unverified, not silently invented.

Historical issues and CI can include implementation failures; those are retained
as engineering history rather than rewritten into false successes. The current
README should explain the product and link the evidence, not expose credentials
or advertise unfinished vendor features.

## Visibility and verification

Repository-content writes and PR merge do not change GitHub visibility. The
connected tooling used for this work does not expose a visibility-setting action.
Until the exact repository setting is changed and anonymous access is checked,
public exposure must be reported as pending, even if main is ready.

After the content review and CI gate, the owner-side setting is:
`Settings → General → Danger Zone → Change repository visibility → Make public`.
Verify the repository name before confirming. Then check the root README and
source anonymously, and confirm `private=false` through the repository API.
No GitHub Pages site or always-on service is implicitly created by this setting.

Reference: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility

## Retained exclusions

No new licensing grant, tenant deployment, account subscription, billing-limit
change, force-push, deletion of historical evidence or personal-workstation
operation is part of this publication. The original provider roadmap is in
[PROVIDER_GATES.md](PROVIDER_GATES.md).
