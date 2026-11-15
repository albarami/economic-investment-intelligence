"""The root finder works from a checkout's depth and from the mutation copy's depth."""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.repository_root import (
    RepositoryRootNotFoundError,
    repository_root,
)


def invented_root(tmp_path: Path) -> Path:
    root = tmp_path / "invented"
    (root / "custodian/publicdata").mkdir(parents=True)
    (root / "AGENTS.md").write_text("Invented.\n")
    (root / "custodian/publicdata/sources.yaml").write_text("sources: []\n")
    return root


@pytest.mark.parametrize(
    "test_file",
    ["custodian/tests/test_invented.py", "custodian/mutants/tests/test_invented.py"],
    ids=["checkout", "mutation-copy"],
)
def test_root_is_found_from_both_depths(tmp_path: Path, test_file: str) -> None:
    root = invented_root(tmp_path)
    assert repository_root(root / test_file) == root.resolve()


def test_real_root_is_found_from_this_file() -> None:
    root = repository_root(Path(__file__))
    assert (root / "AGENTS.md").is_file()
    assert (root / "custodian/publicdata/sources.yaml").is_file()


@pytest.mark.parametrize("missing", ["AGENTS.md", "custodian/publicdata/sources.yaml"])
def test_folder_with_one_marker_only_is_refused(tmp_path: Path, missing: str) -> None:
    root = invented_root(tmp_path)
    (root / missing).unlink()
    with pytest.raises(RepositoryRootNotFoundError, match=r"AGENTS\.md and custodian"):
        repository_root(root / "custodian/tests/test_invented.py")


def test_root_more_than_four_levels_up_is_refused(tmp_path: Path) -> None:
    root = invented_root(tmp_path)
    assert repository_root(root / "a/b/c/test_invented.py") == root.resolve()
    with pytest.raises(RepositoryRootNotFoundError, match="within 4 levels"):
        repository_root(root / "a/b/c/d/test_invented.py")
