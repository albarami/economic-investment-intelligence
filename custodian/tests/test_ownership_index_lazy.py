"""The batch ownership index is built lazily (R1 perf port, S2-R1PORT2 fx1).

Invented inputs only. An empty batch never builds the index, a feature's own
field refusal still comes before a grid refusal, and in the places table the
index is built inside the lookup's own refusal boundary.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.fixtures.places_fsq.invented import place, write_places

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.gis.layers import LayerError, address_rows, poi_rows
from eii_custodian.publicdata.places_fsq.assemble import _table_row, build_places
from eii_custodian.publicdata.places_fsq.constants import ATTRIBUTION
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.parse import parse_file
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX

_BAD_GRID: list[dict[str, object]] = [{"cell": True}]
_POINT = {"x": 51.5, "y": 25.3, "spatialReference": {"wkid": 4326}}


def test_empty_layers_with_an_invalid_grid_return_no_rows() -> None:
    assert address_rows([], _BAD_GRID) == []
    assert poi_rows([], _BAD_GRID) == []


def test_a_feature_field_refusal_comes_before_the_grid_refusal() -> None:
    address = {"attributes": {"ZONE_NO": "SYN-not-a-number"}, "geometry": _POINT}
    with pytest.raises(LayerError) as caught:
        address_rows([address], _BAD_GRID)
    assert caught.value.detail == "number"
    poi = {"attributes": {"ENAME": ""}, "geometry": _POINT}
    with pytest.raises(LayerError) as caught:
        poi_rows([poi], _BAD_GRID)
    assert caught.value.detail == "text"


def test_places_with_no_kept_row_never_build_the_index(tmp_path: Path) -> None:
    path = tmp_path / "places.parquet"
    write_places(path, [place(longitude=0.5, latitude=0.5)])
    built = build_places(
        files={"near.parquet": path},
        expected_sha256={"near.parquet": sha256_hex(path.read_bytes())},
        frame=FRAME_BOX,
        grid=[{"SYN-not-cell": 1}],
        places=(),
        mapping=(),
        labels=(),
        min_edit_distance=3,
        release="2025-01-10",
        attribution=ATTRIBUTION,
        receipt_sha256="a" * 64,
    )
    assert built.rows == built.eligible == ()


def test_places_index_is_built_inside_the_cell_refusal(tmp_path: Path) -> None:
    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    row = parse_file(path)[0]

    def refused() -> frozenset[int]:
        raise FrameError("SYN-grid")

    with pytest.raises(PlacesFsqError) as caught:
        _table_row(row, [], "2025-01-10", refused)
    assert caught.value.reason == "cell"
