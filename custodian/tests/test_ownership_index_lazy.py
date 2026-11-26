"""The batch ownership index is built lazily (R1 perf port, S2-R1PORT2 fx1).

Invented inputs only. An empty batch never builds the index, a feature's own
field refusal still comes before a grid refusal, and in the places table the
index is built inside the lookup's own refusal boundary.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from custodian.tests.fixtures.places_fsq.invented import place, write_places
from custodian.tests.test_gis_layers import _grid, _point

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.frame import gazetteer
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.gis import layers
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


@pytest.fixture
def index_builds(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    layer_index = Mock(wraps=layers.ownership_index)
    gazetteer_index = Mock(wraps=gazetteer.ownership_index)
    monkeypatch.setattr(layers, "ownership_index", layer_index)
    monkeypatch.setattr(gazetteer, "ownership_index", gazetteer_index)
    return layer_index, gazetteer_index


def test_empty_valid_landmark_batch_builds_no_index(
    index_builds: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = Mock(wraps=layers.reviewed_points)
    monkeypatch.setattr(layers, "reviewed_points", reviewed)
    assert layers.landmark_rows([], _grid(10.25, 20.5)) == []
    assert [call.call_count for call in index_builds] == [0, 0]
    reviewed.assert_not_called()


def test_empty_invalid_landmark_batch_preserves_cell_refusal(
    index_builds: tuple[Mock, Mock],
) -> None:
    with pytest.raises(LayerError) as caught:
        layers.landmark_rows([], _BAD_GRID)
    assert type(caught.value) is LayerError
    assert caught.value.detail == "cell"
    assert [call.call_count for call in index_builds] == [0, 0]


def test_several_landmarks_share_one_index_and_preserve_base_rows(
    index_builds: tuple[Mock, Mock],
) -> None:
    feature = {
        "attributes": {"ENAME": "SYN MARK", "ANAME": "معلم تجريبي"},
        "geometry": _point(10.25, 20.5),
    }
    rows = layers.landmark_rows([feature, feature, feature], _grid(10.25, 20.5))
    # Captured from 2062194e with these invented inputs before changing sources.
    expected = {
        "kind": "landmark",
        "name_en": "SYN MARK",
        "name_ar": "معلم تجريبي",
        "aliases": None,
        "lon": Decimal("10.250000"),
        "lat": Decimal("20.500000"),
        "cell": 618563496823750655,
        "showcase_verified": False,
        "source_id": "gis_landmarks",
    }
    assert rows == [
        {**expected, "place_key": key}
        for key in (
            "lm-ec8a-078b-f17a-27b5",
            "lm-ec8a-078b-f17a-27b5_2",
            "lm-ec8a-078b-f17a-27b5_3",
        )
    ]
    assert [call.call_count for call in index_builds] == [1, 0]


def test_reviewed_points_without_stored_builds_its_own_index(
    index_builds: tuple[Mock, Mock],
) -> None:
    assert gazetteer.reviewed_points([], {}, _grid(10.25, 20.5)) == []
    assert [call.call_count for call in index_builds] == [0, 1]
