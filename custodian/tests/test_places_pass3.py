"""Plants for the pass-3 guards. Each new refusal is one fixed line."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import place_row, write_places
from custodian.tests.support.fetch_build import run_build
from custodian.tests.test_frame_census import entry
from custodian.tests.test_places_area_files import (
    _FRAME,
    _install_road,
    _request,
    _walk_10,
    _write_valid,
)
from custodian.tests.test_places_pass2 import _empty_review, _Hand
from custodian.tests.test_publicdata_behaviour import _clock, _entry, _sleep
from shapely.geometry import Point, Polygon, box

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.area_files import (
    ENGINE_PIN,
    AreaRequest,
    FileAreaProvider,
    produce_areas,
    verify_areas,
)
from eii_custodian.publicdata.places.area_requests import _CANDIDATE_AREAS
from eii_custodian.publicdata.places.areas import AreaCutoff, AreaError, AreaMode
from eii_custodian.publicdata.places.integrate import (
    areas_before_stage,
    run_places_before_gazetteer,
)

_PACKAGE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "eii_custodian"
    / "publicdata"
    / "places"
)
_SHOW = (
    "- place_key: SYN-SHOW\n"
    "  mode: walk\n"
    "  cutoff_minutes: 10\n"
    "  source_id: places_ovt\n"
    "  record_key: SYN-P-A\n"
)


def test_moved_point_is_computed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stored file whose point differs from this run is not nothing to do."""
    cache, review, hand = _ready(tmp_path, monkeypatch)
    _again(cache, review)
    _write_place(cache, place_row(lat=25.31))
    second: list[str] = []
    areas_before_stage(cache, second, review)
    assert second == []
    assert hand.polygons == 2
    stored = json.loads(
        (cache / "places_s2_t06" / "areas" / "SYN-SHOW.walk.10.json").read_text()
    )
    assert stored["lat"] == "25.310000"


def test_changed_road_digest_is_computed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A manifest road digest that is not this road is not nothing to do."""
    cache, review, hand = _ready(tmp_path, monkeypatch)
    _again(cache, review)
    path = cache / "places_s2_t06" / "areas" / "manifest.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    loaded["road_sha256"] = "cd" * 32
    path.write_text(json.dumps(loaded), encoding="utf-8")
    second: list[str] = []
    areas_before_stage(cache, second, review)
    assert second == []
    assert hand.polygons == 2


def test_missing_listed_file_is_computed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A manifest name with no file is not nothing to do."""
    cache, review, hand = _ready(tmp_path, monkeypatch)
    _again(cache, review)
    (cache / "places_s2_t06" / "areas" / "SYN-SHOW.walk.10.json").unlink()
    second: list[str] = []
    areas_before_stage(cache, second, review)
    assert second == []
    assert hand.polygons == 2


def test_invalid_review_yaml_is_one_refusal_and_the_build_goes_on(
    tmp_path: Path,
) -> None:
    """A review file that is not YAML is one refusal line. The other stages run."""
    cache = tmp_path / "data" / "public_cache"
    review = _empty_review(tmp_path)
    (review / "showcase_areas.yaml").write_text(":\n", encoding="utf-8")
    _install_road(cache)
    citation = replace(
        _entry(),
        kind="citation_only",
        extension="",
        nightly_live_fetch=False,
        url="https://www.ilo.org/resource/news/planted",
    )
    outcome = run_build((citation,), _unused, cache, _clock, _sleep)
    assert outcome.failure is None
    assert "REFUSED review_unreadable" in outcome.lines
    assert all("Parser" not in line for line in outcome.lines)
    assert any(line.startswith("COVERAGE ") for line in outcome.lines)


def test_unreceipted_places_file_is_refused(tmp_path: Path) -> None:
    """A places file with no receipt is refused and not read."""
    cache, review = _road_review(tmp_path)
    folder = cache / "places_ovt" / "part-00014"
    folder.mkdir(parents=True)
    write_places(folder / "syn.parquet", [place_row()])
    lines: list[str] = []
    areas_before_stage(cache, lines, review)
    assert lines == ["REFUSED places_file_unreceipted"]
    assert not (cache / "places_s2_t06" / "areas").exists()


def test_places_body_that_misses_its_receipt_is_refused(tmp_path: Path) -> None:
    """A places body that is not the receipt digest is refused and not read."""
    cache, review = _road_review(tmp_path)
    folder = cache / "places_ovt" / "part-00014"
    folder.mkdir(parents=True)
    body_path = folder / "syn.parquet"
    write_places(body_path, [place_row()])
    _matching_receipt(body_path)
    (folder / "syn.meta.json").write_text(
        json.dumps(
            {
                "sha256": "ab" * 32,
                "retrieved_utc": "2026-11-14T00:00:00Z",
                "publisher": "SYN",
            }
        ),
        encoding="utf-8",
    )
    lines: list[str] = []
    areas_before_stage(cache, lines, review)
    assert lines == ["REFUSED places_file_digest"]
    assert not (cache / "places_s2_t06" / "areas").exists()


def test_frame_error_is_one_log_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A swallowed frame error names the stage and a closed reason, not the message."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise FrameError("planted secret")

    monkeypatch.setattr("eii_custodian.publicdata.frame.build.build_frame", boom)
    cache = tmp_path / "data" / "public_cache"
    _empty_review(tmp_path)
    hdx = replace(entry("bnd_hdx"), kind="citation_only", extension="")
    (cache / hdx.key).mkdir(parents=True)
    (cache / hdx.key / "syn.meta.json").write_text("{}", encoding="utf-8")
    outcome = run_build((hdx,), _unused, cache, _clock, _sleep)
    assert outcome.failure is not None
    assert outcome.failure.check == "building_table_absent"
    assert "stage frame frame_refused" in outcome.lines
    assert all("secret" not in line for line in outcome.lines)
    assert any(line.startswith("COVERAGE ") for line in outcome.lines)


def test_places_error_removes_a_stale_points_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A swallowed places error names its reason and drops an earlier points file."""

    def boom(_config: object) -> None:
        raise PlacesError("pub_place_field")

    monkeypatch.setattr(
        "eii_custodian.publicdata.places.integrate.run_places_stage", boom
    )
    cache = tmp_path / "cache"
    review = tmp_path / "review"
    review.mkdir()
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    folder = cache / "places_ovt" / "part-00014"
    folder.mkdir(parents=True)
    write_places(folder / "syn.parquet", [place_row()])
    _matching_receipt(folder / "syn.parquet")
    stale = cache / "places_s2_t06" / "place_points.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("[]\n", encoding="utf-8")
    lines: list[str] = []
    placed = next(
        item for item in load_registry() if item.key == "places_ovt/part-00014"
    )
    run_places_before_gazetteer(
        cache,
        review,
        (replace(placed, skip_reason=""),),
        (box(51.0, 25.0, 52.0, 26.0),),
        (),
        {},
        lines,
    )
    assert lines == ["stage places pub_place_field"]
    assert not stale.exists()


def test_missing_arabic_tag_is_one_log_line(tmp_path: Path) -> None:
    """Without the tag the stage does not run, and the log names arabic_tag_missing."""
    cache = tmp_path / "cache"
    review = tmp_path / "review"
    review.mkdir()
    stale = cache / "places_s2_t06" / "place_points.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("[]\n", encoding="utf-8")
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (), (box(0, 0, 1, 1),), (), {}, lines)
    assert lines == ["stage places arabic_tag_missing"]
    assert stale.exists()


def test_readme_names_the_tag_and_the_rebuild_call() -> None:
    """The package README names who writes the tag and the lead's rebuild call."""
    text = (_PACKAGE / "README.md").read_text(encoding="utf-8")
    assert "arabic_tag.txt" in text
    assert "arabic_tag_missing" in text
    assert "stage places arabic_tag_missing" in text
    assert "verify_areas(" in text


def test_failed_prepare_is_engine_failed(tmp_path: Path) -> None:
    """A prepare that fails is engine_failed before any polygon call."""
    _install_road(tmp_path)

    class _Prep:
        version = ENGINE_PIN
        polygons = 0

        def prepare(self, road: bytes) -> None:
            del road
            raise RuntimeError("planted")

        def polygon(self, request: AreaRequest, road: bytes) -> bytes:
            del request, road
            self.polygons += 1
            return b""

    engine = _Prep()
    with pytest.raises(AreaError) as caught:
        produce_areas(engine, (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert caught.value.reason == "engine_failed"
    assert engine.polygons == 0


def test_verify_prepares_the_road_once(tmp_path: Path) -> None:
    """The rebuild prepares the road once for the run."""
    _install_road(tmp_path)
    requests = (
        _request(),
        AreaRequest(
            "SYN-OTHER", "51.510000", "25.310000", AreaMode.WALK, AreaCutoff.MINUTES_5
        ),
    )

    class _Count:
        version = ENGINE_PIN

        def __init__(self) -> None:
            self.prepared = 0

        def prepare(self, road: bytes) -> None:
            del road
            self.prepared += 1

        def polygon(self, request: AreaRequest, road: bytes) -> bytes:
            del request, road
            return bytes(Polygon(_RING).wkb)

    engine = _Count()
    produce_areas(engine, requests, cache=tmp_path, frame_box=_FRAME)
    engine.prepared = 0
    verify_areas(engine, cache=tmp_path, frame_box=_FRAME)
    assert engine.prepared == 1


def test_provider_derives_a_request_the_list_lacks(tmp_path: Path) -> None:
    """With no listed request, the provider derives the point, mode and cut-off."""
    _install_road(tmp_path)
    _write_valid(tmp_path)
    result = FileAreaProvider(tmp_path, _FRAME, ()).area(*_walk_10())
    assert result.stand_in is False


def test_candidate_areas_match_flagship() -> None:
    """The request list and the flagship checks name the same three areas."""
    assert _candidate_pairs() == _flagship_pairs()


def test_short_point_and_empty_polygons_are_refused(tmp_path: Path) -> None:
    """These shapes are refused by the decode and the polygon test."""
    _refuse_hex(tmp_path, "00")
    _refuse_hex(tmp_path, Point(51.50, 25.30).wkb.hex())
    _refuse_hex(tmp_path, Polygon().wkb.hex())


_RING = (
    (51.50, 25.30),
    (51.51, 25.30),
    (51.51, 25.31),
    (51.50, 25.31),
    (51.50, 25.30),
)


def _ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, _Hand]:
    cache, review = _road_review(tmp_path)
    _write_place(cache, place_row())
    hand = _Hand()
    monkeypatch.setattr(
        "eii_custodian.publicdata.places.integrate.open_pinned_engine",
        lambda: hand,
    )
    return cache, review, hand


def _road_review(tmp_path: Path) -> tuple[Path, Path]:
    cache = tmp_path / "data" / "public_cache"
    review = _empty_review(tmp_path)
    (review / "showcase_areas.yaml").write_text(_SHOW, encoding="utf-8")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    _install_road(cache)
    return cache, review


def _write_place(cache: Path, row: dict[str, object]) -> None:
    folder = cache / "places_ovt" / "part-00014"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "syn.parquet"
    path.unlink(missing_ok=True)
    write_places(path, [row])
    _matching_receipt(path)


def _matching_receipt(path: Path) -> None:
    from custodian.tests.snapshot_fixture import place

    place(path)


def _again(cache: Path, review: Path) -> None:
    first: list[str] = []
    areas_before_stage(cache, first, review)
    assert first == []


def _refuse_hex(cache: Path, text: str) -> None:
    from custodian.tests.test_places_area_files import _provider

    _install_road(cache)
    _write_valid(cache, polygon_wkb_hex=text)
    with pytest.raises(AreaError) as caught:
        _provider(cache).area(*_walk_10())
    assert caught.value.reason == "area_polygon_form"


def _unused(_url: str) -> object:
    raise AssertionError("transport")


def _candidate_pairs() -> tuple[tuple[str, str], ...]:
    return tuple((mode.name, cutoff.name) for mode, cutoff in _CANDIDATE_AREAS)


def _flagship_pairs() -> tuple[tuple[str, str], ...]:
    path = _PACKAGE / "flagship.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "_areas":
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign) or len(child.targets) != 1:
                continue
            target = child.targets[0]
            if not isinstance(target, ast.Name) or target.id != "requests":
                continue
            if not isinstance(child.value, ast.Tuple):
                continue
            found: list[tuple[str, str]] = []
            for item in child.value.elts:
                if not isinstance(item, ast.Tuple) or len(item.elts) != 3:
                    continue
                mode, cutoff = item.elts[1], item.elts[2]
                if not isinstance(mode, ast.Attribute) or not isinstance(
                    cutoff, ast.Attribute
                ):
                    continue
                found.append((mode.attr, cutoff.attr))
            return tuple(found)
    raise AssertionError("flagship areas")
