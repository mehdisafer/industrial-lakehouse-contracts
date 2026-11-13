"""Offline regression checks for documentation and qualification consistency."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location("repository_quality", Path(__file__).parents[1] / "scripts/check_repository.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA = "a" * 40


@pytest.fixture
def repository(tmp_path):
    for name in gate.REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Guide\n\nRepository fixture.\n", encoding="utf-8")
    proof = tmp_path / "docs/evidence/run.md"
    proof.parent.mkdir(parents=True)
    proof.write_text(f"# Execution record\n\nExecuted `{SHA}`.\n")
    data = {"schema_version": "ilc-qualification-baselines/1", "reviewed_on": "2026-11-13",
            "capabilities": [{"id": "native", "name": "Native engine", "state": "accepted",
                              "revision": SHA, "evidence": "docs/evidence/run.md", "scope": "Single-host synthetic"}]}
    (tmp_path / gate.REGISTER).write_text(json.dumps(data))
    (tmp_path / gate.STATUS_PAGE).write_text(gate.render_status(data))
    return tmp_path, list(gate.REQUIRED) + ["docs/evidence/run.md"]


def result(repository):
    root, inventory = repository
    return gate.audit(root, inventory)


def change_register(root, mutation):
    path = root / gate.REGISTER
    data = json.loads(path.read_text())
    mutation(data)
    path.write_text(json.dumps(data))


def test_consistent_repository_passes(repository):
    assert result(repository)["status"] == "PASS"


def test_stale_status_fails_without_rewriting_it(repository):
    path = repository[0] / gate.STATUS_PAGE
    path.write_text("# Stale status\n")
    assert result(repository)["status"] == "FAIL"
    assert path.read_text() == "# Stale status\n"


@pytest.mark.parametrize("target", ["missing.md", "docs/RUNBOOK.md#absent", "../outside.md", "%2e%2e/outside.md", "docs/RUNBOOK.md?raw=1"])
def test_broken_or_unsafe_local_links_fail(repository, target):
    (repository[0] / "README.md").write_text(f"# Project\n\n[Documentation]({target})\n")
    assert result(repository)["status"] == "FAIL"


def test_inline_reference_root_and_duplicate_heading_links(repository):
    root, _ = repository
    (root / "docs/RUNBOOK.md").write_text("# Guide\n\n## Start\n\n## Start\n")
    (root / "README.md").write_text('# Project\n\n[Root](/docs/RUNBOOK.md#start-1)\n[Run][guide]\n\n[guide]: docs/RUNBOOK.md#start "Runbook"\n')
    assert result(repository)["status"] == "PASS"


def test_undefined_reference_fails(repository):
    (repository[0] / "README.md").write_text("# Project\n[Missing][undefined]\n")
    assert result(repository)["status"] == "FAIL"


def test_code_examples_are_not_treated_as_links(repository):
    (repository[0] / "README.md").write_text("# Project\n`[inline](missing.md)`\n\n```markdown\n[example](missing.md)\n```\n")
    assert result(repository)["status"] == "PASS"


def test_unclosed_code_fence_fails(repository):
    (repository[0] / "README.md").write_text("# Project\n```bash\necho hello\n")
    assert result(repository)["status"] == "FAIL"


def test_external_urls_are_counted_without_requesting_them(repository):
    (repository[0] / "README.md").write_text("# Project\n[External](https://example.invalid/unavailable)\n")
    checked = result(repository)
    assert checked["status"] == "PASS" and checked["external_links_not_requested"] == 1


@pytest.mark.parametrize("target", ["https://secret@example.invalid/x", "javascript:alert", "data:text/plain,hello", "//example.invalid/x"])
def test_unsafe_external_link_fails(repository, target):
    (repository[0] / "README.md").write_text(f"# Project\n[Unsafe]({target})\n")
    assert result(repository)["status"] == "FAIL"


def test_percent_encoded_unicode_local_file(repository):
    root, inventory = repository
    (root / "docs/Équipe.md").write_text("# Équipe\n")
    inventory.append("docs/Équipe.md")
    (root / "README.md").write_text("# Project\n[Guide](docs/%C3%89quipe.md#%C3%A9quipe)\n")
    assert result(repository)["status"] == "PASS"


def test_symlink_is_not_followed(repository):
    root, inventory = repository
    link = root / "docs/linked.md"
    link.symlink_to(root / "docs/RUNBOOK.md")
    inventory.append("docs/linked.md")
    assert result(repository)["status"] == "FAIL"


@pytest.mark.parametrize("name", [".env", ".env.local", ".runtime/run.json", "artifacts/result.json", "build/wheel.whl", "secret.pem", "service.log"])
def test_tracked_generated_or_sensitive_paths_fail(repository, name):
    root, inventory = repository
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test fixture")
    inventory.append(name)
    assert result(repository)["status"] == "FAIL"


def test_env_example_is_allowed(repository):
    root, inventory = repository
    (root / ".env.example").write_text("# Names only; no values.\n")
    inventory.append(".env.example")
    assert result(repository)["status"] == "PASS"


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(schema_version="unsupported"),
    lambda d: d["capabilities"][0].update(revision="main"),
    lambda d: d["capabilities"][0].update(state="production-ready"),
    lambda d: d["capabilities"][0].update(state="planned"),
    lambda d: d["capabilities"][0].update(evidence="../outside.md"),
    lambda d: d["capabilities"][0].update(scope="bad|table"),
    lambda d: d["capabilities"].append(deepcopy(d["capabilities"][0])),
])
def test_invalid_register_is_rejected(repository, mutation):
    change_register(repository[0], mutation)
    with pytest.raises(gate.RepositoryError):
        gate.load_register(repository[0])


def test_register_rejects_duplicate_json_keys(repository):
    (repository[0] / gate.REGISTER).write_text('{"schema_version": "a", "schema_version": "b"}')
    with pytest.raises(gate.RepositoryError, match="Duplicate"):
        gate.load_register(repository[0])


def test_accepted_revision_must_appear_in_evidence(repository):
    (repository[0] / "docs/evidence/run.md").write_text("# Missing source revision\n")
    assert result(repository)["status"] == "FAIL"


def test_missing_required_document_fails(repository):
    repository[1].remove("CONTRIBUTING.md")
    assert result(repository)["status"] == "FAIL"


def test_deleted_tracked_file_is_a_failure(repository):
    (repository[0] / "docs/RUNBOOK.md").unlink()
    assert result(repository)["status"] == "FAIL"


def test_duplicate_inventory_is_rejected(repository):
    repository[1].append("README.md")
    with pytest.raises(gate.RepositoryError):
        result(repository)


def test_non_git_checkout_fails_closed(tmp_path):
    assert gate.main(["--root", str(tmp_path)]) == 2


def test_render_only_does_not_modify_status(repository, capsys):
    root, _ = repository
    before = (root / gate.STATUS_PAGE).read_bytes()
    assert gate.main(["--root", str(root), "--render-status"]) == 0
    assert capsys.readouterr().out == before.decode()
    assert (root / gate.STATUS_PAGE).read_bytes() == before


def test_output_is_not_overwritten(repository, monkeypatch):
    root, inventory = repository
    monkeypatch.setattr(gate, "tracked_files", lambda _: inventory)
    output = root / "result.json"
    output.write_text("preserve")
    assert gate.main(["--root", str(root), "--output", str(output)]) == 2
    assert output.read_text() == "preserve"
