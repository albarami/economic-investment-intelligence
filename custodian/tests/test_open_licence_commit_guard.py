"""Guards of decision 0026 item 5: no committed value of a non-open source.

The regression stage's expected anchors and the district-layer alias rows of
`bnd_district_2020` (licence_basis `owner_decision`) may never hold a record,
name or value of a source without an open licence. These tests read the
committed files and fail if one comes back; each carries its planted violation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.series.figures import DEPENDENCIES
from eii_custodian.publicdata.stage import EXPECTED, SECTION_10_IDS


def _pack_section_10_sources() -> dict[str, frozenset[str]]:
    """Source ids of each regression row, from the pack table's last cell."""
    pack = repository_root(Path(__file__)) / "docs" / "04_PUBLIC_DATA_PACK.md"
    text = pack.read_text(encoding="utf-8")
    section = text.split("## 10. Regression examples", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, frozenset[str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().split("|")]
        if len(cells) < 4 or not cells[1].startswith("PUB-"):
            continue
        rows[cells[1]] = frozenset(re.findall(r"`([a-z0-9_]+)`", cells[-2]))
    return rows


def _closed_source_rows(expected: Mapping[str, object]) -> dict[str, list[str]]:
    """Expected rows whose declared sources are not openly licensed datasets."""
    pack = _pack_section_10_sources()
    declared = {
        figure: pack.get(figure, frozenset()) | frozenset(DEPENDENCIES.get(figure, ()))
        for figure in SECTION_10_IDS
    }
    bases = {entry.source_id: entry.licence_basis for entry in load_registry()}
    return {
        figure: sorted(
            source
            for source in declared.get(figure, ())
            if bases.get(source) != "dataset"
        )
        for figure in expected
        if any(bases.get(source) != "dataset" for source in declared.get(figure, ()))
    }


@pytest.mark.public_data
def test_expected_anchors_only_cover_open_dataset_sources() -> None:
    """`EXPECTED` holds no figure of a source without an open licence."""
    pack = _pack_section_10_sources()
    assert set(pack) == set(SECTION_10_IDS)
    assert set(EXPECTED) < set(SECTION_10_IDS)
    for figure, sources in DEPENDENCIES.items():
        assert set(sources) == pack[figure]
    assert _closed_source_rows(EXPECTED) == {}
    planted = {**EXPECTED, "PUB-71": {"invented_anchor": "1"}}
    assert _closed_source_rows(planted) == {"PUB-71": ["census_zone_sector"]}


@pytest.mark.public_data
def test_committed_district_layer_aliases_hold_no_source_row() -> None:
    """The committed alias file keeps its header alone (`bnd_district_2020`)."""
    path = (
        repository_root(Path(__file__))
        / "custodian/publicdata/review/district_layer_aliases.csv"
    )
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "zone_code,layer_name,hdx_name"
    assert _alias_data_rows(text) == []
    planted = text + "42,invented-layer-district,invented-hdx-district\n"
    assert _alias_data_rows(planted) != []


def _alias_data_rows(text: str) -> list[str]:
    """Data rows of the alias CSV; the guard refuses any committed row."""
    return [line for line in text.splitlines()[1:] if line.strip()]


def test_local_alias_file_rows_reach_join_districts(tmp_path: Path) -> None:
    """Alias rows of the uncommitted cache review folder reach the district join."""
    from dataclasses import replace

    from custodian.tests.fixtures.frame.invented import (
        invented_frame,
        invented_layer,
    )

    from eii_custodian.publicdata.frame.joins import join_districts
    from eii_custodian.publicdata.frame.layers import layer_rows
    from eii_custodian.publicdata.frame.live import district_aliases

    _, _, districts = invented_frame()
    districts = [
        replace(
            districts[0],
            key="SYN042042009",
            municipality_code="SYN042",
            name_en="Invented district",
        )
    ]
    district_rows = layer_rows("bnd_district_2020", invented_layer("bnd_district_2020"))
    census = layer_rows("census_district_pop", invented_layer("census_district_pop"))
    changed = [{**district_rows[0], "ENAME": "Invented unmatched"}]
    review = tmp_path / "review"
    review.mkdir()
    (review / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n"
    )
    cache = tmp_path / "cache"
    joined, report = join_districts(
        districts, changed, census, district_aliases(review, cache)
    )
    assert joined == {}
    assert all("district_name_pair_unmatched" in line for line in report)
    local = cache / "review"
    local.mkdir(parents=True)
    (local / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n42,Invented unmatched,Invented district\n"
    )
    assert join_districts(
        districts, changed, census, district_aliases(review, cache)
    ) == ({(42, 73): "SYN042042009"}, [])
