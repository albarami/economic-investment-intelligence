"""S2-T08 part B, mismatch class 4: a GeoJSON Feature wrapping a polygon.

The live shape pack's Mismatches item 4 shows ``bnd_muni_2025``'s ``geo_shape``
as a GeoJSON Feature ``{type, geometry, properties}`` whose geometry is a
MultiPolygon. A distinct closed column type, ``geojson_feature_polygon``, admits
exactly that wrapper, and only for that one row. Nothing unwraps it: no build
seam reads this row's geometry, and the frame's licensed geometry is unchanged.
Every geometry below is invented.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root
from custodian.tests.test_publicdata_behaviour import (
    _clock,
    _entry,
    _ok,
    _portal_meta,
    _sidecar,
    _sleep,
)
from custodian.tests.test_registry_survivors import invented_row

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.checks import schema_failure
from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry
from eii_custodian.publicdata.frame.mapping import CONFIRMED_SOURCES

REPO = repository_root(Path(__file__))
PORTAL = "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/"
MUNI_PUBLISHER = (
    "National open data portal (dataset publisher field empty, read 2026-11-16)"
)
KIND = "geojson_feature_polygon"
RING = [[51.0, 25.0], [51.1, 25.0], [51.1, 25.1], [51.0, 25.0]]


def _feature(geometry: object, **changes: object) -> dict[str, object]:
    feature: dict[str, object] = {
        "type": "Feature",
        "geometry": geometry,
        "properties": {},
    }
    feature.update(changes)
    return feature


MULTI = {"type": "MultiPolygon", "coordinates": [[RING]]}
VALID = [
    _feature(MULTI),
    _feature({"type": "Polygon", "coordinates": [RING]}),
    _feature(MULTI, properties=None),
    _feature({"type": "MultiPolygon", "coordinates": [[[[51, 25, 3], *RING[1:]]]]}),
]
INVALID = {
    "missing_geometry": {"type": "Feature", "properties": {}},
    "null_geometry": _feature(None),
    "point_feature": _feature({"type": "Point", "coordinates": [51.0, 25.0]}),
    "bare_multipolygon": MULTI,
    "not_feature": _feature(MULTI, type="FeatureCollection"),
    "extra_member": _feature(MULTI, id="SYN-1"),
    "missing_properties": {"type": "Feature", "geometry": MULTI},
    "properties_text": _feature(MULTI, properties="invented"),
    "coordinates_text": _feature({"type": "MultiPolygon", "coordinates": "x"}),
    "coordinates_empty": _feature({"type": "MultiPolygon", "coordinates": []}),
    "polygon_depth_as_multi": _feature({"type": "MultiPolygon", "coordinates": [RING]}),
    "ring_empty": _feature({"type": "Polygon", "coordinates": [[]]}),
    "position_text": _feature(
        {"type": "Polygon", "coordinates": [[["51", 25.0], *RING[1:]]]}
    ),
    "position_bool": _feature(
        {"type": "Polygon", "coordinates": [[[True, 25.0], *RING[1:]]]}
    ),
    "position_short": _feature(
        {"type": "Polygon", "coordinates": [[[51.0], *RING[1:]]]}
    ),
    "position_nan": _feature(
        {"type": "Polygon", "coordinates": [[[float("nan"), 25.0], *RING[1:]]]}
    ),
    "geometry_extra_member": _feature({**MULTI, "bbox": [0, 0, 1, 1]}),
}


def _muni(columns: tuple[tuple[str, str], ...]):
    return replace(
        _entry(),
        key="bnd_muni_2025",
        source_id="bnd_muni_2025",
        kind="portal_dataset",
        publisher=MUNI_PUBLISHER,
        licence_basis="portal_terms",
        url=PORTAL + "municipalities-in-qatar-2025/exports/json",
        columns=columns,
        row_count_min=1,
        row_count_max=1,
        extension="json",
    )


def _fetch(tmp_path: Path, entry, value: object):
    meta = json.dumps(_portal_meta("", licence="", licence_url="")).encode()

    def transport(url: str):
        return _ok(
            url,
            json.dumps([{"geo_shape": value}]).encode()
            if url.endswith("/exports/json")
            else meta,
        )

    return fetch_entry(entry, transport, tmp_path, _clock, _sleep)


def test_registry_declares_the_feature_for_the_municipality_row_only() -> None:
    entries = {
        e.key: e for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
    }
    assert dict(entries["bnd_muni_2025"].columns)["geo_shape"] == KIND
    others = [key for key, e in entries.items() if KIND in dict(e.columns).values()]
    assert others == ["bnd_muni_2025"]


def test_unrelated_row_may_not_declare_the_feature(tmp_path: Path) -> None:
    row = invented_row(columns=[{"name": "geo_shape", "type": KIND}])
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match="geojson_feature_polygon"):
        load_registry(path)


def test_unrelated_entry_is_refused_at_the_check_as_well() -> None:
    entry = replace(_muni((("geo_shape", KIND),)), source_id="invented_source")
    failure = schema_failure(entry, [{"geo_shape": VALID[0]}], "https://invented.test")
    assert failure is not None
    assert (failure.check, failure.expected) == (
        "declaration_scope",
        f"geo_shape:{KIND}",
    )


@pytest.mark.parametrize("value", VALID, ids=["multi", "polygon", "null_props", "xyz"])
def test_a_polygon_feature_is_admitted(tmp_path: Path, value: object) -> None:
    entry = _muni((("geo_shape", KIND),))
    assert _fetch(tmp_path, entry, value) is None
    assert _sidecar(tmp_path)["columns"] == [{"name": "geo_shape", "type": KIND}]


@pytest.mark.parametrize("name", sorted(INVALID))
def test_other_shapes_are_refused(tmp_path: Path, name: str) -> None:
    entry = _muni((("geo_shape", KIND),))
    failure = _fetch(tmp_path, entry, INVALID[name])
    assert failure is not None
    assert (failure.check, failure.expected) == ("schema_retyped", f"geo_shape:{KIND}")
    assert not list(tmp_path.rglob("*"))


def test_the_bare_geometry_type_still_refuses_a_feature(tmp_path: Path) -> None:
    entry = _muni((("geo_shape", "geojson_geometry"),))
    failure = _fetch(tmp_path, entry, VALID[0])
    assert failure is not None
    assert failure.check == "schema_retyped"


def test_the_frame_still_does_not_read_this_row() -> None:
    # The Feature is admitted at the fetch only; it never stands in for the
    # frame's licensed municipality geometry.
    assert "bnd_muni_2025" not in CONFIRMED_SOURCES


def test_review_record_holds_the_correction() -> None:
    review = yaml.safe_load(
        (REPO / "custodian/publicdata/review/s2_t08_source_review.yaml").read_text(
            encoding="utf-8"
        )
    )
    (row,) = [r for r in review["rows"] if r["mismatch"] == 4]
    assert row["key"] == "bnd_muni_2025"
    assert row["export_sha256"].startswith("e5225806")
    assert row["change"]["columns"]["geo_shape"] == {
        "from": "geojson_geometry",
        "to": KIND,
    }
