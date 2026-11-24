"""The package imports from its source tree and reports the version of its metadata."""

import subprocess
import tomllib
from pathlib import Path

import eii_product

PACKAGE = Path(__file__).resolve().parents[1]


def test_import_resolves_to_the_source_tree() -> None:
    assert Path(eii_product.__file__).resolve().is_relative_to(PACKAGE / "src")


def test_version_equals_the_version_in_pyproject() -> None:
    metadata = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))
    assert eii_product.__version__ == metadata["project"]["version"]


def test_tracked_product_paths_are_not_symlinks() -> None:
    """Reject indexed links and links replacing tracked paths or their parents."""
    root = PACKAGE.parent
    tracked = subprocess.run(
        ["git", "ls-files", "--stage", "-z", "--", "product/"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    assert tracked.stdout, "no tracked product paths found"
    links: list[str] = []
    for entry in tracked.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = Path(raw_path.decode("utf-8"))
        if metadata.split()[0] == b"120000" or any(
            (root / part).is_symlink() for part in (path, *path.parents[:-1])
        ):
            links.append(path.as_posix())
    assert not links, f"tracked product symlinks: {links}"
