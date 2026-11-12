"""The package imports from its source tree and reports the version of its metadata."""

import tomllib
from pathlib import Path

import eii_core

PACKAGE = Path(__file__).resolve().parents[1]


def test_import_resolves_to_the_source_tree() -> None:
    assert Path(eii_core.__file__).resolve().is_relative_to(PACKAGE / "src")


def test_version_equals_the_version_in_pyproject() -> None:
    metadata = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))
    assert eii_core.__version__ == metadata["project"]["version"]
