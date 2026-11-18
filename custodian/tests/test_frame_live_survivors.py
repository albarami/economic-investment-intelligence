"""Kills unexplained mutants of the live frame build.

Every cache, review file and name here is invented. Expected text is written
by hand from the archive codes and the layer attributes, not copied from a run.
"""

from __future__ import annotations

import contextlib
import io
import json
import locale
import zipfile
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)
from custodian.tests.test_frame_census import entry
from custodian.tests.test_frame_seventh import seventh_build

from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.frame.build import FrameResult, build_frame
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.live import district_aliases
from eii_custodian.publicdata.review.cache_fixture import select_fixture

_RETRIEVED = "2026-11-14T00:00:00Z"
_PUBLISHER = "Invented test publisher"
_MUNICIPALITY_FILE = (
    "hdx_code,municipality_code,name_en,name_ar,layer_name_en,layer_name_ar\r\n"
    "SYN042,9,Invented municipality,اسم تجريبي,"
    "Different invented spelling,اسم تجريبي\r\n"
)
_JOIN_REFUSAL = "bnd_zone_2020: required join source unavailable"
_FREE_REFUSAL = "listed zone has a district"
_CENSUS_REFUSAL = "census_zone_hh: census_zone_key"
_ADMINISTRATIVE = {
    ("municipality:9", "Invented municipality", "municipality"),
    ("zone:42", "Invented zone 42", "zone"),
    ("district:SYN042042042", "Invented district", "district"),
}
_RING = (
    (0.015, 0.015),
    (0.025, 0.015),
    (0.025, 0.025),
    (0.015, 0.025),
    (0.015, 0.015),
)


def _whole_text(found: BaseException, literal: str) -> None:
    """The refusal's whole text equals this hand-written literal."""
    assert str(found) == literal


@contextlib.contextmanager
def _ascii_locale() -> Iterator[None]:
    """C locale, so a read or write with no encoding name rejects Arabic bytes."""
    previous = locale.setlocale(locale.LC_CTYPE)
    locale.setlocale(locale.LC_CTYPE, "C")
    try:
        assert locale.getencoding() == "ANSI_X3.4-1968"
        yield
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)


def _world(tmp_path: Path) -> Any:
    """The seventh-pass invented cache, review and registry rows."""
    return seventh_build.__wrapped__(tmp_path)


def _build(prepared: Any, output: Path) -> FrameResult:
    return build_frame(prepared.cache, prepared.entries, prepared.review, output)


def _store(cache: Path, source: Entry, body: bytes) -> None:
    directory = cache / source.key
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_file():
            child.unlink()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        source,
        digest=digest,
        nbytes=len(body),
        fetch_url=source.url,
        fetch_host=source.fetch_host,
        retrieved_utc=_RETRIEVED,
        publisher=_PUBLISHER,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(directory, digest, source.extension, body, receipt)
    select_fixture(cache, str(receipt["key"]), digest)


def _active(key: str) -> Entry:
    original = next(item for item in load_registry() if item.key == key)
    return replace(original, publisher=_PUBLISHER)


def _spec(place_key: str, record_key: str, source_id: str) -> dict[str, object]:
    return {
        "place_key": place_key,
        "kind": "landmark" if source_id == "places_ovt" else "building",
        "name_en": "SYN Invented",
        "name_ar": "اسم تجريبي",
        "aliases": None,
        "source_id": source_id,
        "record_key": record_key,
        "arabic_review": "pending native review",
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_bnd_hdx_receipt_is_kept_under_that_source_id(tmp_path: Path) -> None:
    """The licensed archive receipt is returned under bnd_hdx."""
    prepared = _world(tmp_path)
    result = _build(prepared, tmp_path / "output")
    receipt = result.sources["bnd_hdx"]
    assert receipt["source_id"] == "bnd_hdx"
    assert receipt["retrieved_utc"] == _RETRIEVED
    assert receipt["publisher"] == _PUBLISHER
    assert receipt["sha256"] == sha256_hex(invented_archive())


def test_missing_zone_join_source_refuses_with_its_whole_sentence(
    tmp_path: Path,
) -> None:
    """A registry without the zone layer refuses before any join."""
    prepared = _world(tmp_path)
    kept = tuple(item for item in prepared.entries if item.source_id != "bnd_zone_2020")
    with pytest.raises(FrameError) as caught:
        build_frame(prepared.cache, kept, prepared.review, tmp_path / "output")
    _whole_text(caught.value, _JOIN_REFUSAL)


def test_output_is_created_when_its_parent_is_missing(tmp_path: Path) -> None:
    """The municipality file is written under a parent that does not exist yet."""
    prepared = _world(tmp_path)
    output = tmp_path / "not-yet" / "frame-out"
    result = _build(prepared, output)
    assert result.tables["municipality"]
    assert (output / "municipality_names.csv").is_file()


def test_an_existing_output_directory_is_reused(tmp_path: Path) -> None:
    """A second build into an existing directory still writes the name file."""
    prepared = _world(tmp_path)
    output = tmp_path / "frame-out"
    output.mkdir()
    _build(prepared, output)
    assert (output / "municipality_names.csv").is_file()


def test_municipality_names_and_place_text_stay_utf_8_in_the_c_locale(
    tmp_path: Path,
) -> None:
    """Arabic in the name file, the point file and the review spec survives locale C."""
    prepared = _world(tmp_path)
    review = prepared.review
    _write_json(
        _points_path(prepared.cache),
        [
            {
                "source_id": "places_ovt",
                "record_key": "SYN-R",
                "lon": "0.020000",
                "lat": "0.020000",
                "label": "اسم تجريبي",
            }
        ],
    )
    _write_json(
        review / "showcase_gazetteer.yaml",
        [_spec("SYN-LAND", "SYN-R", "places_ovt")],
    )
    _write_json(review / "flagship_candidates.yaml", [])
    output = tmp_path / "frame-out"
    with _ascii_locale():
        result = _build(prepared, output)
    written = (output / "municipality_names.csv").read_bytes()
    assert written == _MUNICIPALITY_FILE.encode("utf-8")
    assert any(row["place_key"] == "SYN-LAND" for row in result.tables["gazetteer"])


def _points_path(cache: Path) -> Path:
    path = cache / "places_s2_t06" / "place_points.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_inventory_lists_the_frame_zone_code(tmp_path: Path) -> None:
    """The archive's one zone number is stored under zone_code, sorted."""
    prepared = _world(tmp_path)
    result = _build(prepared, tmp_path / "output")
    assert result.inventory["bnd_hdx"] == {"zone_code": ("42",)}


def test_gazetteer_keeps_the_administrative_rows(tmp_path: Path) -> None:
    """Municipality 9, zone 42 and the level-three district stay on gazetteer."""
    prepared = _world(tmp_path)
    result = _build(prepared, tmp_path / "output")
    found = {
        (row["place_key"], row["name_en"], row["kind"])
        for row in result.tables["gazetteer"]
        if row["kind"] in {"municipality", "zone", "district"}
    }
    assert found == _ADMINISTRATIVE


def test_a_district_free_listing_of_a_covered_zone_is_refused(tmp_path: Path) -> None:
    """Zone 42 has a district, so listing it as district-free is refused."""
    prepared = _world(tmp_path)
    (prepared.review / "zones_without_districts.csv").write_text(
        "zone_code,reason\n42,no_district_in_boundary_source\n",
        encoding="utf-8",
    )
    with pytest.raises(FrameError) as caught:
        _build(prepared, tmp_path / "output")
    _whole_text(caught.value, _FREE_REFUSAL)


def test_a_census_zone_on_the_wrong_municipality_is_refused(tmp_path: Path) -> None:
    """Household zone 42 coded 8 is not municipality 9, so the build refuses."""
    prepared = _world(tmp_path)
    source = entry("census_zone_hh")
    payload = invented_layer("census_zone_hh")
    payload["features"][0]["attributes"]["MUNICIPAL_CODE"] = "8"
    _store(prepared.cache, source, json.dumps(payload).encode())
    (prepared.review / "zone_crosswalk.csv").write_text(
        "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,census_zone_hh,status\n"
        "42,42,42,42,42,matched\n",
        encoding="utf-8",
    )
    entries = (*prepared.entries, source)
    with pytest.raises(FrameError) as caught:
        build_frame(prepared.cache, entries, prepared.review, tmp_path / "output")
    _whole_text(caught.value, _CENSUS_REFUSAL)


def test_local_aliases_are_added_to_the_committed_aliases(tmp_path: Path) -> None:
    """Committed alias rows stay when the local cache file adds its own rows."""
    review = tmp_path / "review"
    review.mkdir()
    (review / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n41,Invented committed,Invented one\n",
        encoding="utf-8",
    )
    local = tmp_path / "cache" / "review"
    local.mkdir(parents=True)
    (local / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n42,Invented local,Invented two\n",
        encoding="utf-8",
    )
    assert district_aliases(review, tmp_path / "cache") == [
        {
            "zone_code": "41",
            "layer_name": "Invented committed",
            "hdx_name": "Invented one",
        },
        {
            "zone_code": "42",
            "layer_name": "Invented local",
            "hdx_name": "Invented two",
        },
    ]


def test_a_non_object_place_point_does_not_hide_the_next_point(
    tmp_path: Path,
) -> None:
    """A null item is skipped, and the following source point still resolves."""
    prepared = _world(tmp_path)
    _write_json(
        _points_path(prepared.cache),
        [
            None,
            {
                "source_id": "places_ovt",
                "record_key": "SYN-R",
                "lon": "0.020000",
                "lat": "0.020000",
            },
        ],
    )
    _write_json(
        prepared.review / "showcase_gazetteer.yaml",
        [_spec("SYN-LAND", "SYN-R", "places_ovt")],
    )
    result = _build(prepared, tmp_path / "output")
    assert any(row["place_key"] == "SYN-LAND" for row in result.tables["gazetteer"])


def test_a_point_missing_one_text_key_is_ignored(tmp_path: Path) -> None:
    """A record key that is not text is ignored, and the next point resolves."""
    prepared = _world(tmp_path)
    _write_json(
        _points_path(prepared.cache),
        [
            {"source_id": "places_ovt", "record_key": 4, "lat": "0.020000"},
            {
                "source_id": "places_ovt",
                "record_key": "SYN-R",
                "lon": "0.020000",
                "lat": "0.020000",
            },
        ],
    )
    _write_json(
        prepared.review / "showcase_gazetteer.yaml",
        [_spec("SYN-LAND", "SYN-R", "places_ovt")],
    )
    result = _build(prepared, tmp_path / "output")
    assert any(row["place_key"] == "SYN-LAND" for row in result.tables["gazetteer"])


def _zone_sixty_nine(body: bytes) -> bytes:
    """Same invented squares, with the zone number changed from 42 to 69."""
    incoming = io.BytesIO(body)
    outgoing = io.BytesIO()
    with (
        zipfile.ZipFile(incoming) as source,
        zipfile.ZipFile(outgoing, "w") as target,
    ):
        for info in source.infolist():
            raw = source.read(info)
            document = json.loads(raw)
            props = document["features"][0]["properties"]
            if "adm2_pcode" in props:
                props["adm2_pcode"] = "SYN042069"
                props["adm2_name"] = "Invented zone 69"
            if "adm3_pcode" in props:
                props["adm3_pcode"] = "SYN042069069"
            target.writestr(info.filename, json.dumps(document))
    return outgoing.getvalue()


def test_flagship_check_receives_zone_69(tmp_path: Path) -> None:
    """Zone 69 is a flagship zone, so its geometry is in the check inputs."""
    prepared = _world(tmp_path)
    by_id = {item.source_id: item for item in prepared.entries}
    _store(prepared.cache, by_id["bnd_hdx"], _zone_sixty_nine(invented_archive()))
    zone = invented_layer("bnd_zone_2020")
    zone["features"][0]["attributes"]["ZONE_NO"] = 69
    _store(prepared.cache, by_id["bnd_zone_2020"], json.dumps(zone).encode())
    district = invented_layer("bnd_district_2020")
    district["features"][0]["attributes"]["KEY_NO"] = 69
    _store(
        prepared.cache,
        by_id["bnd_district_2020"],
        json.dumps(district).encode(),
    )
    (prepared.review / "zone_crosswalk.csv").write_text(
        "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,status\n"
        "69,69,69,69,matched\n",
        encoding="utf-8",
    )
    review = prepared.review
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    (review / "places_ovt_attribution.csv").write_text(
        "dataset_token,licence\n",
        encoding="utf-8",
    )
    (review / "places_ovt_categories.csv").write_text(
        "basic_category,category_class\n",
        encoding="utf-8",
    )
    (review / "showcase_areas.yaml").write_text("[]\n", encoding="utf-8")
    candidate = _spec("SYN-CAND", "SYN-B-A", "bldg_ovt")
    candidate["use"] = "commercial"
    _write_json(review / "flagship_candidates.yaml", [candidate])
    _write_json(review / "showcase_gazetteer.yaml", [])
    places = _active("places_ovt/part-00014")
    buildings = _active("bldg_ovt/part-00288")
    places_path = tmp_path / "syn-places.parquet"
    buildings_path = tmp_path / "syn-buildings.parquet"
    write_places(places_path, [place_row(lon=0.02, lat=0.02)])
    write_buildings(buildings_path, [building_row("SYN-B-A", _RING)])
    _store(prepared.cache, places, places_path.read_bytes())
    _store(prepared.cache, buildings, buildings_path.read_bytes())
    result = build_frame(
        prepared.cache,
        (*prepared.entries, places, buildings),
        review,
        tmp_path / "output",
    )
    check = json.loads(
        (prepared.cache / "places_s2_t06" / "flagship_check.json").read_text(
            encoding="utf-8"
        )
    )
    inputs = check["body"]["candidates"][0]["inputs"]
    assert set(inputs["zones"]) == {"69"}
    assert check["body"]["candidates"][0]["checks"]["a_footprint_in_zones"] is True
    assert any(row["place_key"] == "SYN-CAND" for row in result.tables["gazetteer"])
