"""S2-T08 part B, mismatch class 1: a declared layer's page reference.

Invented responses only. The server states the spatial reference once, at the
top level of each query page (shape pack, mismatch 1, the `gis_address` page
sample); the paging step copies that validated EPSG:4326 reference into the
geometries that lack one and refuses a missing, conflicting, boolean or other
page reference. The downstream checks of `gis/layers.py` stay unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from custodian.tests.test_gis_paged import (
    _clock,
    _entry,
    _LayerTransport,
    _params,
    _qars_feature,
    _sleep,
    _stored,
)

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.gis.layers import geometry_shape

_PAGE_4326 = {"wkid": 4326, "latestWkid": 4326}
_MISSING = object()


class _PageReferenceTransport(_LayerTransport):
    """The same answers, with the reference stated once at the page's top level."""

    def __init__(self, features, max_count, reference=_PAGE_4326, **kwargs):
        super().__init__(features, max_count, **kwargs)
        self.reference = reference

    def __call__(self, url: str) -> Response:
        response = super().__call__(url)
        if "/query" not in url or "returnCountOnly" in url:
            return response
        body = json.loads(response.body)
        if self.reference is not _MISSING:
            body["spatialReference"] = self.reference
        return Response(final_url=url, body=json.dumps(body).encode(), hops=())


def _bare(pin: int = 1001) -> dict[str, object]:
    feature = _qars_feature(pin)
    geometry = feature["geometry"]
    assert isinstance(geometry, dict)
    del geometry["spatialReference"]
    return feature


def _fetch(tmp_path: Path, transport):
    return fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)


def test_page_reference_is_inherited_by_geometries_that_lack_one(tmp_path):
    transport = _PageReferenceTransport([_bare(1001), _bare(1002)], max_count=1)
    assert _fetch(tmp_path, transport) is None
    features = _stored(tmp_path)["layers"][0]["features"]
    assert [f["geometry"]["spatialReference"] for f in features] == [_PAGE_4326] * 2
    # The unchanged downstream check accepts the stored geometry.
    assert geometry_shape(features[0]["geometry"], "point").x == 10.25


def test_own_matching_reference_is_kept(tmp_path):
    transport = _PageReferenceTransport([_qars_feature()], max_count=5)
    assert _fetch(tmp_path, transport) is None
    geometry = _stored(tmp_path)["layers"][0]["features"][0]["geometry"]
    assert geometry["spatialReference"] == {"wkid": 4326}


@pytest.mark.parametrize(
    "reference",
    [
        _MISSING,
        None,
        {"wkid": 3857},
        {"wkid": True},
        {"wkid": "4326"},
        {"latestWkid": 4326},
        4326,
        [4326],
    ],
)
def test_bare_geometry_without_a_valid_page_reference_refuses(tmp_path, reference):
    transport = _PageReferenceTransport([_bare()], max_count=5, reference=reference)
    failure = _fetch(tmp_path, transport)
    assert failure is not None and failure.check == "spatial_reference"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "own,page",
    [
        ({"wkid": 4326}, {"wkid": 3857}),
        ({"wkid": 4326}, {"wkid": True}),
        ({"wkid": 2932}, _PAGE_4326),
    ],
)
def test_conflicting_geometry_and_page_references_refuse(tmp_path, own, page):
    feature = _qars_feature()
    feature["geometry"]["spatialReference"] = own
    transport = _PageReferenceTransport([feature], max_count=5, reference=page)
    failure = _fetch(tmp_path, transport)
    assert failure is not None and failure.check == "spatial_reference"
    assert list(tmp_path.iterdir()) == []


def test_never_taken_attribute_still_refuses_with_an_inherited_reference(tmp_path):
    feature = _bare()
    feature["attributes"]["WATER_NO"] = "SYN-UTILITY"
    failure = _fetch(tmp_path, _PageReferenceTransport([feature], max_count=5))
    assert failure is not None and failure.check == "never_taken"
    assert failure.observed == "WATER_NO"
    assert list(tmp_path.iterdir()) == []


def test_page_total_still_refuses_with_an_inherited_reference(tmp_path):
    transport = _PageReferenceTransport([_bare()], max_count=2, reported_count=3)
    failure = _fetch(tmp_path, transport)
    assert failure is not None and failure.check == "short_total"
    assert list(tmp_path.iterdir()) == []


def test_undeclared_layer_keeps_its_native_geometry(tmp_path):
    entry = next(
        item for item in load_registry() if item.source_id == "census_zone_sector"
    )
    feature = {"attributes": {}, "geometry": {"rings": []}}
    transport = _PageReferenceTransport([feature], max_count=2000)
    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    stored = _stored(tmp_path)
    assert stored["features"] == [feature]
    assert all("outSR" not in _params(url) for url in transport.urls)
