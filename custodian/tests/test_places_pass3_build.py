"""The public build reaches the frame only when that stage is ready."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer
from custodian.tests.fixtures.places.invented import place_row, write_places
from custodian.tests.support.fetch_build import run_build
from custodian.tests.test_frame_census import entry
from custodian.tests.test_places_area_files import _install_road
from custodian.tests.test_places_stage import _frame_review
from custodian.tests.test_publicdata_behaviour import _clock, _sleep

from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.transport import Response


def test_run_build_reaches_the_frame_only_when_ready(tmp_path: Path) -> None:
    """run_build reaches the frame after the producer, and not when the frame is not ready."""
    cache = tmp_path / "data" / "public_cache"
    review = tmp_path / "custodian" / "publicdata" / "review"
    review.mkdir(parents=True)
    _frame_review(review)
    spec = {
        "place_key": "SYN-SHOW",
        "kind": "landmark",
        "name_en": "SYN Place",
        "name_ar": "مكان تجريبي",
        "aliases": None,
        "source_id": "places_ovt",
        "record_key": "SYN-LAND",
        "arabic_review": "pending native review",
    }
    (review / "showcase_gazetteer.yaml").write_text(
        json.dumps([spec]), encoding="utf-8"
    )
    (review / "flagship_candidates.yaml").write_text("[]\n", encoding="utf-8")
    (review / "showcase_areas.yaml").write_text("[]\n", encoding="utf-8")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    source = Path(__file__).parent / "fixtures" / "places" / "syn_review"
    for name in ("places_ovt_attribution.csv", "places_ovt_categories.csv"):
        (review / name).write_bytes((source / name).read_bytes())
    names = (
        "bnd_hdx",
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_district_pop",
        "census_zone_hh",
        "pop_muni",
    )
    entries = [entry(name) for name in names]
    place_path = tmp_path / "places.parquet"
    write_places(
        place_path,
        [
            place_row(
                place_id="SYN-LAND",
                lon=0.02,
                lat=0.02,
                names={"primary": "SYN-LAND", "common": {"ar": "SYN-LAND"}},
            )
        ],
    )
    body = place_path.read_bytes()
    places = next(
        item for item in load_registry() if item.key == "places_ovt/part-00014"
    )
    places = replace(
        places,
        skip_reason="",
        publisher="Invented test publisher",
        basis_note=f"recorded_bytes: {len(body)}\nrecorded_etag: syn-places\n",
    )
    entries.append(places)
    bodies = _frame_bodies(entries, body)
    _install_road(cache)
    from eii_custodian.publicdata.review.cache_fixture import select_fixture

    fetched = run_build(tuple(entries), _frame_transport(bodies), cache, _clock, _sleep)
    assert fetched.failure is not None
    assert fetched.failure.check == "building_table_absent"
    assert "stage frame frame_refused" in fetched.lines
    for line in fetched.lines:
        if line.startswith("PASS ") and "sha256=" in line:
            fields = line.split()
            select_fixture(cache, fields[1], fields[2].removeprefix("sha256="))
    ready = run_build(tuple(entries), _frame_transport(bodies), cache, _clock, _sleep)
    assert ready.failure is not None
    assert ready.failure.check == "building_part_unregistered"
    assert "areas: nothing to do" in ready.lines
    points = json.loads(
        (cache / "places_s2_t06" / "place_points.json").read_text(encoding="utf-8")
    )
    assert any(item["record_key"] == "SYN-LAND" for item in points)
    assert all(not line.startswith("stage frame") for line in ready.lines)
    (review / "showcase_gazetteer.yaml").unlink()
    for name in (
        "place_points.json",
        "pub_place.jsonl",
        "pub_place_verification.jsonl",
        "build_report.json",
        "flagship_check.json",
    ):
        (cache / "places_s2_t06" / name).unlink()
    held = run_build(tuple(entries), _frame_transport(bodies), cache, _clock, _sleep)
    assert held.failure is not None
    assert held.failure.check == "building_table_absent"
    assert not (cache / "places_s2_t06" / "place_points.json").exists()


def _frame_bodies(
    entries: list[Entry], places: bytes
) -> dict[str, tuple[bytes, str | None]]:
    found: dict[str, tuple[bytes, str | None]] = {}
    population = json.dumps(
        [
            {
                "year": "2020",
                "municipality": "Invented municipality",
                "lbldy": "اسم تجريبي",
                "indicator": "residents",
                "lmw_shr": "اسم تجريبي",
                "count": 17,
            }
        ]
    ).encode()
    meta = json.dumps(
        {
            "metas": {
                "default": {
                    "publisher": "Invented test publisher",
                    "license": "CC BY",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                }
            }
        }
    ).encode()
    for item in entries:
        if item.source_id == "bnd_hdx":
            found[item.url] = (invented_archive(), None)
        elif item.source_id == "pop_muni":
            found[item.url] = (population, None)
            found[item.url[: -len("/exports/json")]] = (meta, None)
        elif item.source_id == "places_ovt":
            found[item.url] = (places, '"syn-places"')
        elif item.kind == "paged_layer":
            found[item.url] = (
                json.dumps(invented_layer(item.source_id)).encode(),
                None,
            )
    return found


def _frame_transport(
    bodies: dict[str, tuple[bytes, str | None]],
) -> object:
    def transport(url: str) -> Response:
        if "returnCountOnly=true" in url:
            return Response(url, b'{"count": 1}', (), None)
        if "/query?" in url:
            for source, (payload, _etag) in bodies.items():
                if url.startswith(source):
                    loaded = json.loads(payload)
                    page = json.dumps({"features": loaded["features"]}).encode()
                    return Response(url, page, (), None)
            raise AssertionError(url)
        if url not in bodies:
            raise AssertionError(url)
        body, etag = bodies[url]
        return Response(url, body, (), etag)

    return transport
