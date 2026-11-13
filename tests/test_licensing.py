"""Check licence packaging and current notices; not a third-party legal audit."""
from importlib.metadata import distributions
from pathlib import Path
import sysconfig
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_root_license_has_standard_mit_sections_and_owner():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License\n\nCopyright (c) 2026 Mehdi Safer\n")
    assert "[year]" not in text and "[fullname]" not in text
    normalized = " ".join(text.split())
    assert "Permission is hereby granted, free of charge" in normalized
    assert "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." in normalized
    assert 'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND' in normalized
    assert normalized.endswith("SOFTWARE.")


def test_package_declares_mit_and_a_supported_build_backend():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["license"] == "MIT"
    assert metadata["project"]["license-files"] == ["LICENSE"]
    assert "setuptools>=77.0.3" in metadata["build-system"]["requires"]
    assert metadata["build-system"]["build-backend"] == "setuptools.build_meta"


def test_installed_editable_distribution_includes_license():
    # pytest adds src to sys.path; source-tree egg-info is not the installed wheel.
    # Inspect the active environment's installation paths explicitly instead.
    paths = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    matches = [
        item for item in distributions(path=paths)
        if item.metadata.get("Name", "").replace("_", "-").casefold()
        == "industrial-lakehouse-contracts"
    ]
    assert len(matches) == 1, "Expected one project distribution in the active environment"
    installed = matches[0]
    assert installed.metadata.get("License-Expression") == "MIT"
    assert installed.metadata.get_all("License-File") == ["LICENSE"]
    embedded = installed.read_text("licenses/LICENSE")
    assert embedded is not None, "Installed distribution omitted the PEP 639 licence file"
    assert embedded == (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_current_guides_link_the_mit_license_without_obsolete_grant_status():
    expected = {
        "README.md": "[MIT License](LICENSE)",
        "CONTRIBUTING.md": "[MIT License](LICENSE)",
        "docs/LICENSING.md": "[MIT License](../LICENSE)",
        "docs/PUBLICATION.md": "[MIT License](../LICENSE)",
    }
    obsolete = (
        "no open-source licence has been selected",
        "no open-source licence has been granted",
        "no open-source licence is granted",
    )
    for name, link in expected.items():
        content = (ROOT / name).read_text(encoding="utf-8")
        assert link in content, name
        normalized = " ".join(content.casefold().split())
        assert not any(phrase in normalized for phrase in obsolete), name
    # Historical changelog/evidence is deliberately not rewritten into a new grant.
