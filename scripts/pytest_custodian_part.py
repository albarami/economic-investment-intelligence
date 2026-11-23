"""Partition custodian tests by stable SHA-256 of repository-relative module paths."""

from __future__ import annotations

import hashlib

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """An omitted option leaves the whole collection unchanged."""
    parser.addoption(
        "--custodian-part",
        choices=("1", "2", "3", "4", "5"),
        default=None,
        help="select custodian part 1 to 5 by SHA-256 of the module path",
    )


def module_part(path: str) -> int:
    """Return the one-based part of a repository-relative POSIX module path."""
    return int.from_bytes(hashlib.sha256(path.encode("utf-8")).digest(), "big") % 5 + 1


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Keep whole modules together and report the other items as deselected."""
    option = config.getoption("custodian_part")
    if option is None:
        return
    part = int(option)
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        path = item.path.relative_to(config.rootpath).as_posix()
        (kept if module_part(path) == part else deselected).append(item)
    if not kept:
        raise pytest.UsageError(f"custodian part {part} selected no tests")
    items[:] = kept
    if deselected:
        config.hook.pytest_deselected(items=deselected)
