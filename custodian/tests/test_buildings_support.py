"""The shared building-table helper is the non-heights build path."""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.fixtures.atlas.invented import (
    configuration,
    entry,
    metadata,
    stream,
)
from custodian.tests.support.buildings import (
    building_table_path,
    ensure_minimal_building_table,
)
from custodian.tests.support.fetch_build import run_build

from eii_custodian.publicdata.atlas.config import Config
from eii_custodian.publicdata.fetch.build import run_build as production_run_build


def test_run_build_leaves_unrelated_assets_in_non_pytest_named_dir(
    tmp_path: Path,
) -> None:
    """Unrelated assets survive when the cache sits in a non-temporary ``pytest-*`` folder."""
    workspace = tmp_path / "pytest-not-temporary"
    cache = workspace / "data" / "public_cache"
    cache.mkdir(parents=True)
    marker = workspace / "assets" / "unrelated-marker.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("keep", encoding="utf-8")

    outcome = run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is None
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_minimal_building_table_satisfies_run_build(tmp_path: Path) -> None:
    """Without the helper's table the same build refuses ``building_table_absent``."""
    cache = tmp_path / "data" / "public_cache"
    cache.mkdir(parents=True)
    refused = production_run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert refused.failure is not None
    assert refused.failure.check == "building_table_absent"

    ensure_minimal_building_table(cache)
    path = building_table_path(cache.parent)
    assert path.is_file()
    accepted = run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert accepted.failure is None
    path.unlink()
    with pytest.raises((FileNotFoundError, OSError)):
        path.read_bytes()
    refused_again = production_run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert refused_again.failure is not None
    assert refused_again.failure.check == "building_table_absent"
