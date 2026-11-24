"""The places stage writes checked rows and reads areas only from files."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    receipt_for,
    write_buildings,
    write_places,
)
from custodian.tests.repository_root import repository_root
from shapely.geometry import Polygon, box

import h3
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.places import PlacesError, stage
from eii_custodian.publicdata.places.area_files import (
    AreaRequest,
    produce_areas,
)
from eii_custodian.publicdata.places.area_requests import area_requests
from eii_custodian.publicdata.places.display import CAVEAT_KEY, PubPlace
from eii_custodian.publicdata.places.read import SOURCE_RELEASE
from eii_custodian.publicdata.places.review import (
    STATUSES,
    Verification,
    load_flagship_candidates,
    load_showcase_gazetteer,
)
from eii_custodian.publicdata.places.stage import (
    PLACE_COLUMNS,
    VERIFICATION_COLUMNS,
    StageConfig,
    _decision_against_file,
    commit_files,
    render_place_rows,
    render_verification_rows,
    resolve_review,
    run_places_stage,
    validate_recorded_decision,
)
from eii_custodian.publicdata.places_fsq.parse import ParsedRow

_RELEASE = "2025-01-10"
_FRAME = (50.7, 24.4, 51.7, 26.2)
_BUILD = date(2026, 11, 15)
_LINK = "https://example.invalid/syn"


class _PolygonEngine:
    version = "3.9.1"

    def polygon(self, request: AreaRequest, road: bytes) -> bytes:
        del request, road
        return bytes(Polygon(_ring()).wkb)


def test_missing_arabic_tag_writes_nothing(tmp_path: Path) -> None:
    """The stage refuses to run when the Arabic tag is absent."""
    review = _review(tmp_path, verified="")
    places = _places(tmp_path, _food())
    with pytest.raises(PlacesError) as caught:
        run_places_stage(_config(tmp_path, review, places, arabic_tag=""))
    assert caught.value.reason == "arabic_tag_missing"
    assert not (tmp_path / "cache" / "places_s2_t06" / "pub_place.jsonl").exists()


def test_without_area_files_nothing_is_complete(tmp_path: Path) -> None:
    """No area provider reports the areas pending and the decision pending."""
    review = _review(tmp_path, verified="", candidates=False, areas=False)
    places = _places(tmp_path, [_one("SYN-LAND", 51.5, 25.3, "syn_other", "0.8")])
    outcome = run_places_stage(_config(tmp_path, review, places))
    report = json.loads((outcome.directory / "build_report.json").read_text())
    assert report["complete"] is False
    assert "showcase_areas_pending" in report["report"]
    assert "census_comparison_pending" in report["report"]
    assert report["decision"] == "pending"
    assert report["caveat_key"] == CAVEAT_KEY


def test_stage_with_area_manifest_refuses_missing_flagship_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path, verified="")
    places = _places(tmp_path, _food())
    _buildings(tmp_path)
    _areas(tmp_path)
    config = _config(tmp_path, review, places)
    run_places_stage(config)
    points = stage._source_points(config)
    del points[("bldg_ovt", "SYN-BLDG")]
    monkeypatch.setattr(stage, "_source_points", lambda _config: points)
    with pytest.raises(PlacesError, match=r"^flagship_point_missing$"):
        run_places_stage(config)


def test_place_and_verification_rows_round_trip(tmp_path: Path) -> None:
    """Written rows keep their fields. A bad licence, status or place stores nothing."""
    review = _review(tmp_path, verified=_verified_food())
    places = _places(tmp_path, _food())
    _buildings(tmp_path)
    _areas(tmp_path)
    outcome = run_places_stage(_config(tmp_path, review, places, fsq=True))
    rows = _lines(outcome.directory / "pub_place.jsonl")
    assert list(rows[0]) == list(PLACE_COLUMNS)
    assert all(
        row["source_provider"] and row["licence"] and row["confidence"] for row in rows
    )
    checks = _lines(outcome.directory / "pub_place_verification.jsonl")
    assert list(checks[0]) == list(VERIFICATION_COLUMNS)
    planted = PubPlace(
        "SYN-BARE",
        "SYN Bare",
        None,
        "syn_other",
        "other",
        Decimal("51.500000"),
        Decimal("25.300000"),
        1,
        SOURCE_RELEASE,
        "syn-source",
        "",
        Decimal("0.8000"),
        "",
    )
    with pytest.raises(PlacesError) as missing_licence:
        render_place_rows((planted,))
    assert missing_licence.value.reason == "pub_place_field"
    known = frozenset(row["place_id"] for row in rows)
    four = tuple(
        Verification(
            next(iter(known)),
            f"2026-01-0{index}",
            "reviewer",
            _LINK,
            status,
            "tenant_directory",
        )
        for index, status in enumerate(sorted(STATUSES), start=1)
    )
    stored = _lines_text(render_verification_rows(four, known))
    assert [row["status"] for row in stored] == sorted(STATUSES)
    orphan = Verification(
        "SYN-NOBODY",
        "2026-01-01",
        "reviewer",
        _LINK,
        "verified_open",
        "tenant_directory",
    )
    with pytest.raises(PlacesError) as missing_place:
        render_verification_rows((orphan,), known)
    assert missing_place.value.reason == "orphan_place_id"
    fifth = Verification(
        next(iter(known)),
        "2026-01-01",
        "reviewer",
        _LINK,
        "invented",
        "tenant_directory",
    )
    with pytest.raises(PlacesError) as extra:
        render_verification_rows((fifth,), known)
    assert extra.value.reason == "unknown_status"


def test_caveat_is_required_on_every_written_file(tmp_path: Path) -> None:
    """A planted output without the caveat key is refused and nothing is written."""
    files = {
        name: _json({"caveat_key": CAVEAT_KEY})
        for name in (
            "pub_place.jsonl",
            "pub_place_verification.jsonl",
            "place_points.json",
            "build_report.json",
            "flagship_check.json",
        )
    }
    files["build_report.json"] = "{}\n"
    with pytest.raises(PlacesError) as caught:
        commit_files(tmp_path / "out", files)
    assert caught.value.reason == "caveat_missing"
    assert not (tmp_path / "out").exists()


def test_file_areas_select_the_flagship_and_the_shown_points(tmp_path: Path) -> None:
    """Invented area files pass checks (a) to (e). Membership follows the file."""
    review = _review(tmp_path, verified=_verified_filled())
    places = _places(tmp_path, _food() + _edges())
    _buildings(tmp_path)
    _areas(tmp_path)
    outcome = run_places_stage(_config(tmp_path, review, places, fsq=True))
    assert outcome.complete is True
    report = json.loads((outcome.directory / "build_report.json").read_text())
    assert set(report["resolved"]) == {"SYN-SHOW", "SYN-CAND"}
    shown = set(report["shown"])
    assert "SYN-IN" in shown
    assert "SYN-OUT" in shown
    assert "SYN-LOW" not in shown
    assert "SYN-LAND" not in shown
    record = json.loads((outcome.directory / "flagship_check.json").read_text())
    candidate = record["body"]["candidates"][0]
    assert candidate["checks"] == {
        "a_footprint_in_zones": True,
        "b_restaurants_walk_5": True,
        "c_italian_walk_10": True,
        "d_areas_returned": True,
        "e_landmark_use": True,
    }
    assert candidate["counts"] == {"italian_walk_10": 2, "restaurants_walk_5": 8}
    assert record["passing_evidence"] is True
    decision = _choice(record, record["manifest_sha256"])
    validate_recorded_decision(decision, outcome.directory / "flagship_check.json")
    stale = dict(decision)
    stale["digest"] = "ab" * 32
    with pytest.raises(PlacesError) as digest:
        validate_recorded_decision(stale, outcome.directory / "flagship_check.json")
    assert digest.value.reason == "stale_digest"
    other = dict(decision)
    other["manifest_sha256"] = "cd" * 32
    with pytest.raises(PlacesError) as manifest:
        validate_recorded_decision(other, outcome.directory / "flagship_check.json")
    assert manifest.value.reason == "stale_manifest"


def test_missing_drive_area_fails_the_check_and_cannot_be_chosen(
    tmp_path: Path,
) -> None:
    """Without the drive 10 file, check (d) fails and no decision can name it."""
    review = _review(tmp_path, verified=_verified_filled())
    places = _places(tmp_path, _food() + _edges())
    _buildings(tmp_path)
    _areas(tmp_path)
    drive = tmp_path / "cache" / "places_s2_t06" / "areas" / "SYN-CAND.drive.10.json"
    drive.unlink()
    outcome = run_places_stage(_config(tmp_path, review, places, fsq=True))
    record = json.loads((outcome.directory / "flagship_check.json").read_text())
    checks = record["body"]["candidates"][0]["checks"]
    assert checks["d_areas_returned"] is False
    decision = _choice(record, record["manifest_sha256"])
    with pytest.raises(PlacesError) as caught:
        validate_recorded_decision(decision, outcome.directory / "flagship_check.json")
    assert caught.value.reason == "failed_candidate"


def test_planted_area_digest_is_named_in_the_report(tmp_path: Path) -> None:
    """A planted area-file digest is the refusal named in the written report."""
    review = _review(tmp_path, verified=_verified_food())
    places = _places(tmp_path, _food())
    _buildings(tmp_path)
    _areas(tmp_path)
    manifest_path = tmp_path / "cache" / "places_s2_t06" / "areas" / "manifest.json"
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in loaded["files"]:
        if item["name"] == "SYN-SHOW.walk.10.json":
            item["sha256"] = "ab" * 32
    manifest_path.write_text(json.dumps(loaded), encoding="utf-8")
    outcome = run_places_stage(_config(tmp_path, review, places))
    report = json.loads((outcome.directory / "build_report.json").read_text())
    assert "showcase area error: area_file_digest" in report["report"]


def test_stand_in_area_is_not_evidence(tmp_path: Path) -> None:
    """A stand-in flag stays a refusal. Check (d) fails with area_stand_in and names no candidate."""
    review = _review(tmp_path, verified=_verified_food())
    places = _places(tmp_path, _food())
    _buildings(tmp_path)
    _areas(tmp_path)
    _mark_stand_in(tmp_path, "SYN-SHOW.walk.10.json")
    _mark_stand_in(tmp_path, "SYN-CAND.drive.10.json")
    outcome = run_places_stage(_config(tmp_path, review, places, fsq=True))
    assert outcome.complete is False
    assert "showcase area error: area_stand_in" in outcome.report
    record = json.loads((outcome.directory / "flagship_check.json").read_text())
    candidate = record["body"]["candidates"][0]
    assert candidate["checks"]["d_areas_returned"] is False
    assert candidate["inputs"]["area_errors"]["drive_10"] == "area_stand_in"
    assert "drive_10" not in candidate["inputs"]["areas"]
    choice = _choice(record, record["manifest_sha256"])
    (review / "flagship.yaml").write_text(
        "candidate_key: "
        + str(choice["candidate_key"])
        + "\ndigest: "
        + str(choice["digest"])
        + "\nmanifest_sha256: "
        + str(choice["manifest_sha256"])
        + "\nprovisional: true\n",
        encoding="utf-8",
    )
    again = run_places_stage(_config(tmp_path, review, places, fsq=True))
    report = json.loads((again.directory / "build_report.json").read_text())
    assert report["decision"] == "failed_candidate"
    assert report["decision"] != "SYN-CAND"


_POINT = {"lon": "51.500000", "lat": "25.300000"}
_POINT_GRID = [{"cell": h3.str_to_int(h3.latlng_to_cell(25.30, 51.50, 9))}]


def _invented_spec(place_key: str, source: object, record: object) -> dict[str, object]:
    return {
        "place_key": place_key,
        "kind": "landmark",
        "name_en": "SYN Place",
        "name_ar": "مكان تجريبي",
        "aliases": None,
        "source_id": source,
        "record_key": record,
        "arabic_review": "pending native review",
    }


@pytest.mark.parametrize(
    ("source", "record"),
    [
        (None, None),
        ("places_ovt", None),
        (None, "SYN-LAND"),
        ("", "SYN-LAND"),
        ("places_ovt", ""),
    ],
)
def test_an_unfilled_key_stays_pending(source: object, record: object) -> None:
    """A key with either half null or empty stays pending S2-T06, even with a point."""
    points = {("places_ovt", "SYN-LAND"): _POINT}
    spec = _invented_spec("SYN-A", source, record)
    assert resolve_review((spec,), points, _POINT_GRID) == (
        [],
        ("gazetteer: source point pending S2-T06: SYN-A",),
    )
    assert resolve_review((), points, _POINT_GRID) == ([], ())


def test_a_filled_key_without_its_record_is_refused() -> None:
    """A filled key whose record is absent is record_missing, though another is present."""
    points = {("places_ovt", "SYN-OTHER"): _POINT}
    spec = _invented_spec("SYN-A", "places_ovt", "SYN-MISSING")
    with pytest.raises(PlacesError) as caught:
        resolve_review((spec,), points, _POINT_GRID)
    assert caught.value.reason == "record_missing"


def test_every_committed_key_is_null_and_stays_pending() -> None:
    """S2-L4 fx1 cleared the one stored key (a shop, not its landmark): all eleven pend."""
    review = repository_root(Path(__file__)) / "custodian/publicdata/review"
    specs = load_showcase_gazetteer(review / "showcase_gazetteer.yaml", None)[1]
    candidates = load_flagship_candidates(review / "flagship_candidates.yaml", None)[1]
    everything = (*specs, *candidates)
    filled = [
        spec["place_key"]
        for spec in everything
        if spec["record_key"] is not None or spec["source_id"] is not None
    ]
    assert filled == []
    points = {("places_ovt", "SYN-LAND"): _POINT}
    resolved, report = resolve_review(everything, points, _POINT_GRID)
    assert resolved == []
    assert report == tuple(
        f"gazetteer: source point pending S2-T06: {spec['place_key']}"
        for spec in everything
    )
    assert len(report) == 11


def test_a_decision_file_names_its_candidate_and_a_list_stays_pending(
    tmp_path: Path,
) -> None:
    """No file and a list stay pending. A mapping that does not validate is not copied."""
    assert _decision_against_file(tmp_path, "{}\n") == "pending"
    (tmp_path / "flagship.yaml").write_text("[]\n", encoding="utf-8")
    assert _decision_against_file(tmp_path, "{}\n") == "pending"
    (tmp_path / "flagship.yaml").write_text(
        "candidate_key: SYN-CAND\n", encoding="utf-8"
    )
    assert _decision_against_file(tmp_path, "{}\n") == "decision_fields"


def _frame_stage_fixture(tmp_path: Path):
    from dataclasses import replace

    from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer
    from custodian.tests.fixtures.places.invented import place_row, write_places
    from custodian.tests.test_frame_census import entry

    from eii_custodian.publicdata.fetch.registry import load_registry

    cache, review, output = (tmp_path / name for name in ("cache", "review", "output"))
    review.mkdir()
    _frame_review(review)
    spec = {
        "place_key": "SYN-SHOW",
        "kind": "landmark",
        "name_en": "SYN Place",
        "name_ar": "مكان تجريبي",
        "aliases": None,
        "source_id": "places_ovt",
        "record_ref": "SYN-LAND",
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
    for source_entry in entries:
        body = (
            invented_archive()
            if source_entry.source_id == "bnd_hdx"
            else json.dumps(invented_layer(source_entry.source_id)).encode()
            if source_entry.source_id != "pop_muni"
            else json.dumps(
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
        )
        _store(cache, source_entry, body)
    places = next(
        item for item in load_registry() if item.key == "places_ovt/part-00014"
    )
    places = replace(places, skip_reason="")
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
    _store(cache, places, place_path.read_bytes())
    entries.append(places)
    return cache, review, output, entries


def test_stage_call_sits_after_the_fetch_and_before_gazetteer_resolution(
    tmp_path: Path,
) -> None:
    """The real loader accepts a header-only verification file before gazetteer."""
    from datetime import date

    from eii_custodian.publicdata.frame.build import build_frame
    from eii_custodian.publicdata.places.review import VERIFIED_COLUMNS

    cache, review, output, entries = _frame_stage_fixture(tmp_path)
    (review / "verified_places.csv").write_text(",".join(VERIFIED_COLUMNS) + "\n")
    result = build_frame(
        cache, tuple(entries), review, output, build_date=date(2026, 11, 17)
    )
    points_path = cache / "places_s2_t06" / "place_points.json"
    frame_file = output / "municipality_names.csv"
    assert frame_file.is_file()
    assert points_path.is_file()
    assert frame_file.stat().st_mtime_ns <= points_path.stat().st_mtime_ns
    points = json.loads(points_path.read_text(encoding="utf-8"))
    stored = next(item for item in points if item["record_key"] == "SYN-LAND")
    resolved = [
        row for row in result.tables["gazetteer"] if row.get("place_key") == "SYN-SHOW"
    ]
    assert len(resolved) == 1
    assert str(resolved[0]["lon"]) == stored["lon"]
    assert str(resolved[0]["lat"]) == stored["lat"]
    assert resolved[0]["cell"] in {row["cell"] for row in result.tables["grid_cell"]}


def _config(
    tmp: Path, review: Path, places: Path, arabic_tag: str = "ar", fsq: bool = False
) -> StageConfig:
    buildings = tmp / "buildings.parquet"
    paths = (buildings,) if buildings.is_file() else ()
    receipts = (receipt_for(buildings, "bldg_ovt"),) if buildings.is_file() else ()
    rows = (_fsq(),) if fsq else None
    return StageConfig(
        cache=tmp / "cache",
        review=review,
        arabic_tag=arabic_tag,
        boundary=box(51.2, 25.0, 51.7, 25.5),
        grid=_grid(),
        zones={
            "69": box(51.45, 25.25, 51.55, 25.35),
            "70": box(51.55, 25.25, 51.65, 25.35),
        },
        places_path=places,
        places_receipt=receipt_for(places, "places_ovt"),
        build_date=_BUILD,
        fsq_rows=rows,
        fsq_release=_RELEASE if fsq else "",
        fsq_licence="SYN-FSQ-LICENCE" if fsq else "",
        buildings_paths=paths,
        buildings_receipts=receipts,
    )


def _review(
    tmp: Path, verified: str, candidates: bool = True, areas: bool = True
) -> Path:
    review = tmp / "review"
    review.mkdir()
    source = Path(__file__).parent / "fixtures" / "places" / "syn_review"
    for name in (
        "places_ovt_attribution.csv",
        "places_ovt_categories.csv",
        "showcase_areas.yaml",
        "showcase_gazetteer.yaml",
        "flagship_candidates.yaml",
    ):
        (review / name).write_bytes((source / name).read_bytes())
    (review / "verified_places.csv").write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        + verified,
        encoding="utf-8",
    )
    if not areas:
        (review / "showcase_areas.yaml").write_text(
            yaml.safe_dump([]), encoding="utf-8"
        )
        (review / "showcase_gazetteer.yaml").write_text(
            yaml.safe_dump([]), encoding="utf-8"
        )
    if not candidates:
        (review / "flagship_candidates.yaml").write_text(
            yaml.safe_dump([]), encoding="utf-8"
        )
    return review


def _places(tmp: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp / "places.parquet"
    write_places(path, rows)
    return path


def _buildings(tmp: Path) -> None:
    ring = (
        (51.50, 25.30),
        (51.502, 25.30),
        (51.502, 25.302),
        (51.50, 25.302),
        (51.50, 25.30),
    )
    write_buildings(tmp / "buildings.parquet", [building_row("SYN-BLDG", ring)])


def _areas(tmp: Path) -> None:
    cache = tmp / "cache"
    from custodian.tests.snapshot_fixture import road

    road(cache, b"SYN-ROAD")
    from eii_custodian.publicdata.places.read import read_building_file

    building = next(iter(read_building_file(tmp / "buildings.parquet")))
    requests = area_requests(
        tmp / "review",
        {
            ("places_ovt", "SYN-LAND"): (51.5, 25.3),
            ("bldg_ovt", building.building_id): (
                float(building.lon),
                float(building.lat),
            ),
        },
    )
    produce_areas(_PolygonEngine(), requests, cache=cache, frame_box=_FRAME)


def _food() -> list[dict[str, object]]:
    rows = [_one("SYN-LAND", 51.5, 25.3, "syn_other", "0.8")]
    points = (
        ("SYN-F1", 51.501, 25.301, "syn_restaurant"),
        ("SYN-F2", 51.502, 25.301, "syn_restaurant"),
        ("SYN-F3", 51.503, 25.301, "syn_restaurant"),
        ("SYN-F4", 51.501, 25.302, "syn_restaurant"),
        ("SYN-F5", 51.502, 25.302, "syn_restaurant"),
        ("SYN-F6", 51.503, 25.302, "syn_restaurant"),
        ("SYN-I1", 51.501, 25.303, "syn_italian"),
        ("SYN-I2", 51.502, 25.303, "syn_italian"),
    )
    rows.extend(
        _one(key, lon, lat, category, "0.8") for key, lon, lat, category in points
    )
    return rows


def _edges() -> list[dict[str, object]]:
    return [
        _one("SYN-IN", 51.49, 25.29, "syn_other", "0.1"),
        _one("SYN-OUT", 51.35, 25.15, "syn_other", "0.8"),
        _one("SYN-LOW", 51.36, 25.16, "syn_other", "0.1"),
    ]


def _one(
    key: str, lon: float, lat: float, category: str, confidence: str
) -> dict[str, object]:
    return place_row(
        place_id=key,
        lon=lon,
        lat=lat,
        basic_category=category,
        confidence=float(confidence),
        names={"primary": key, "common": {"ar": key}},
    )


def _verified_filled() -> str:
    text = (
        Path(__file__).parent
        / "fixtures"
        / "places"
        / "syn_review"
        / "verified_places.csv"
    ).read_text(encoding="utf-8")
    return text.split("\n", 1)[1]


def _verified_food() -> str:
    keys = (
        "SYN-F1",
        "SYN-F2",
        "SYN-F3",
        "SYN-F4",
        "SYN-F5",
        "SYN-F6",
        "SYN-I1",
        "SYN-I2",
    )
    return "".join(_verified(key) for key in keys)


def _verified(key: str) -> str:
    return f"{key},2026-11-01,reviewer,{_LINK},verified_open,tenant_directory\n"


def _grid() -> list[dict[str, int]]:
    points = [(25.3, 51.5), (25.301, 51.501), (25.301, 51.502), (25.301, 51.503)]
    points += [(25.302, 51.501), (25.302, 51.502), (25.302, 51.503)]
    points += [(25.303, 51.501), (25.303, 51.502), (25.29, 51.49)]
    points += [(25.15, 51.35), (25.16, 51.36), (25.301, 51.501)]
    return [
        {"cell": h3.str_to_int(h3.latlng_to_cell(lat, lon, 9))} for lat, lon in points
    ]


def _fsq() -> ParsedRow:
    return ParsedRow(
        "SYN-FSQ-1",
        "SYN Further",
        None,
        "",
        "",
        Decimal("51.550000"),
        Decimal("25.250000"),
        "QA",
        None,
        None,
        None,
    )


def _mark_stand_in(tmp: Path, name: str) -> None:
    path = tmp / "cache" / "places_s2_t06" / "areas" / name
    loaded = json.loads(path.read_text(encoding="utf-8"))
    loaded["stand_in"] = True
    body = json.dumps(loaded, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(body)
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if item["name"] == name:
            item["sha256"] = sha256_hex(body)
    manifest_path.write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    )


def _choice(record: dict[str, object], manifest: object) -> dict[str, object]:
    return {
        "candidate_key": "SYN-CAND",
        "digest": record["digest"],
        "manifest_sha256": manifest,
        "provisional": True,
    }


def _lines(path: Path) -> list[dict[str, object]]:
    return _lines_text(path.read_text(encoding="utf-8"))


def _lines_text(text: str) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in text.splitlines() if line and "place_id" in line
    ]


def _frame_review(review: Path) -> None:
    arabic = "اسم تجريبي"
    (review / "zones_without_districts.csv").write_text(
        "zone_code,reason\n", encoding="utf-8"
    )
    (review / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "Invented municipality,9\n"
        f"{arabic},9\n"
        "Different invented spelling,9\n"
        "Invented municipality,9\n",
        encoding="utf-8",
    )
    (review / "zone_crosswalk.csv").write_text(
        "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,census_district_pop,"
        "census_zone_hh,status\n42,42,42,42,42,42,matched\n",
        encoding="utf-8",
    )
    (review / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nresidents,residents\n", encoding="utf-8"
    )
    (review / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n", encoding="utf-8"
    )
    (review / "greater_doha_municipalities.csv").write_text(
        "name\nDifferent invented spelling\n", encoding="utf-8"
    )


def _store(cache: Path, source_entry: object, body: bytes) -> None:
    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.fetch.registry import Entry

    if not isinstance(source_entry, Entry):
        raise TypeError("registry entry")
    digest = sha256_hex(body)
    receipt = sidecar_for(
        source_entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=source_entry.url,
        fetch_host=source_entry.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=source_entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(cache / source_entry.key, digest, source_entry.extension, body, receipt)
    from eii_custodian.publicdata.review.cache_fixture import select_fixture

    select_fixture(cache, source_entry.key, digest)


def _ring() -> tuple[tuple[float, float], ...]:
    loaded = json.loads(
        (Path(__file__).parent / "fixtures" / "places" / "syn_polygon.json").read_text()
    )
    return tuple((float(lon), float(lat)) for lon, lat in loaded["ring"])


def _json(payload: dict[str, str]) -> str:
    return json.dumps(payload) + "\n"
