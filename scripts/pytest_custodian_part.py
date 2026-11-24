"""Partition a suite's tests by stable SHA-256 of repository-relative module paths."""

from __future__ import annotations

import hashlib

import pytest

PART_COUNTS = {"custodian": 5, "product": 2}


def pytest_addoption(parser: pytest.Parser) -> None:
    """An omitted option leaves the whole collection unchanged."""
    for suite, count in PART_COUNTS.items():
        parser.addoption(
            f"--{suite}-part",
            choices=tuple(str(part) for part in range(1, count + 1)),
            default=None,
            help=f"select {suite} part 1 to {count} by SHA-256 of the module path",
        )


def module_part(path: str, count: int = PART_COUNTS["custodian"]) -> int:
    """Return the one-based part of a repository-relative POSIX module path."""
    digest = hashlib.sha256(path.encode("utf-8")).digest()
    return int.from_bytes(digest, "big") % count + 1


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Keep whole modules together and report the other items as deselected."""
    chosen = [
        (suite, count, int(option))
        for suite, count in PART_COUNTS.items()
        if (option := config.getoption(f"{suite}_part")) is not None
    ]
    if not chosen:
        return
    if len(chosen) > 1:
        raise pytest.UsageError("only one part option may be given")
    suite, count, part = chosen[0]
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        path = item.path.relative_to(config.rootpath).as_posix()
        (kept if module_part(path, count) == part else deselected).append(item)
    if not kept:
        raise pytest.UsageError(f"{suite} part {part} selected no tests")
    items[:] = kept
    if deselected:
        config.hook.pytest_deselected(items=deselected)
