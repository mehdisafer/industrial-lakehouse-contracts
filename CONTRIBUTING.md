# Contributing

I maintain this project around three invariants: accepted data is immutable,
reporting consumes only accepted generations, and every integration claim is tied
to executed evidence. Changes should preserve those invariants or explain their
replacement explicitly.

## Before proposing a change

Open an issue describing the problem, the affected execution profile and the
expected outcome. Use synthetic reproductions only. Do not include credentials,
real records, client schemas or confidential service addresses. Check
[licensing status](docs/LICENSING.md) before proposing third-party material.

For a defect, provide the source revision, Python/runtime versions, command,
expected result, observed result and a sanitised excerpt. For a feature, explain
its operational value, acceptance criteria and resource impact before selecting
a new technology.

## Local checks

Use Python 3.12/3.13 and an editable install from the repository root:

```bash
python -m pip install -e '.[test]'
python scripts/check_repository.py
python -m compileall -q src tests scripts fabric
python -m ilc.cli validate
python -m pytest
```

Reference smoke tests are in [the demonstration guide](docs/DEMO.md). Native and
catalogue qualification are opt-in routes with separate dependencies and resource
limits; unit tests or a skipped integration test do not replace them.

The repository checker makes no external requests. It checks tracked local Markdown
links/ATX heading anchors, required documentation, generated baseline status and
accidentally tracked runtime/sensitive paths. It is not a general Markdown parser,
a runtime qualification or a secret detector. The separate CI disclosure gate
scans reachable Git history.

The [validation guide](docs/REPOSITORY_QUALITY.md) documents the supported syntax,
byte limits, diagnostic redaction and original-JUnit evidence gate. Add a negative
regression before changing a checker: an example that demonstrates the original
failure is more useful than increasing a test total without checking behaviour.
Do not force-add generated `test-results/`, SQLite databases or private-key files.

## Documentation and qualification changes

Update the whole affected path: README, design/model, operating guide, qualification
status and related examples. Keep historical receipts and reviewed execution SHAs
intact. A later documentation commit does not inherit a new integration execution.

`docs/qualification-baselines.json` contains the reviewed integration baselines.
An accepted entry requires an exact executed commit and its evidence record.
After an authorised baseline change, regenerate the derived page:

```bash
python scripts/check_repository.py --render-status > docs/STATUS.md
python scripts/check_repository.py
```

Do not edit the generated status page independently. Planned/unexecuted entries
must not contain an executed revision. The evidence must contain the complete hash,
not that hash embedded in a longer value.

## Pull-request evidence

Keep changes focused. Describe the motivation, behavioural impact, tests actually
run, tests not run, data/security implications and rollback path. Add a regression
case that fails for the original defect whenever practical. Include expected
commands and exact results rather than a generic "tested" statement.

Separate a control-path unit test, a real service integration, an artifact review
and a performance benchmark. Avoid adding their counts or transferring evidence
between profiles. Do not introduce automatic destructive cleanup, a paid resource,
a public listener or a new licence grant as a side effect.

The automatic CircleCI reference route includes repository and history checks,
a collected test inventory, and final reconciliation of the original JUnit and
scenario outputs. An omitted test or unexpected skip is a failure, not a smaller
successful suite. Preserve raw artifacts rather than browser-rendered copies.
Heavy integration routes are explicit, not triggered for every documentation
change. I merge after reviewing the exact candidate and its available checks;
self-review is not an independent approval.
