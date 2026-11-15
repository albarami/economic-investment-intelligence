"""Plants for the pass-2 guards. Each input asserts one fixed reason."""

from __future__ import annotations

import builtins
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import place_row, write_places
from custodian.tests.test_places_area_files import (
    _FRAME,
    _RING,
    _install_road,
    _provider,
    _request,
    _walk_10,
    _write_valid,
)
from custodian.tests.test_places_flagship import (
    _FOOT,
    _ZONE_69,
    _ZONE_70,
    _Areas,
    _candidate,
    _italians,
    _restaurants,
)
from custodian.tests.test_publicdata_behaviour import _clock, _entry, _sleep
from shapely.geometry import Polygon
from shapely.wkb import dumps as dump_wkb

import h3
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.transport import TransportFault
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.places.area_files import (
    ENGINE_PIN,
    AreaRequest,
    FileAreaProvider,
    produce_areas,
    verify_areas,
)
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
)
from eii_custodian.publicdata.places.flagship import evaluate_candidates
from eii_custodian.publicdata.places.integrate import areas_before_stage
from eii_custodian.publicdata.places.stage import (
    _decision_against_file,
    render_place_rows,
    render_verification_rows,
    resolve_review,
)

_SHA = "ab" * 32
_OTHER = "cd" * 32
_ENGINE = "eii_custodian.publicdata.places.area_engine"


def test_method_version_operand_is_area_inputs_hash(tmp_path: Path) -> None:
    """A wrong method version is refused even when the inputs hash still matches."""
    _refuse(tmp_path, {"method_version": "places.area.plant"}, "area_inputs_hash")


def test_manifest_road_digest_operand_is_unreceipted(tmp_path: Path) -> None:
    """The manifest road digest, not the file's graph hash, is the second operand."""
    _install_road(tmp_path)
    _write_valid(tmp_path)
    path = tmp_path / "places_s2_t06" / "areas" / "manifest.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    loaded["road_sha256"] = _OTHER
    path.write_text(json.dumps(loaded), encoding="utf-8")
    _expect(tmp_path, "area_graph_unreceipted")


def test_west_south_and_north_bounds_are_area_polygon_form(tmp_path: Path) -> None:
    """Each of the other three frame edges refuses the polygon on its own."""
    west = (
        (50.60, 25.00),
        (50.80, 25.00),
        (50.80, 25.10),
        (50.60, 25.10),
        (50.60, 25.00),
    )
    south = (
        (51.00, 24.30),
        (51.10, 24.30),
        (51.10, 24.50),
        (51.00, 24.50),
        (51.00, 24.30),
    )
    north = (
        (51.00, 26.10),
        (51.10, 26.10),
        (51.10, 26.30),
        (51.00, 26.30),
        (51.00, 26.10),
    )
    for ring in (west, south, north):
        _refuse(
            tmp_path, {"polygon_wkb_hex": Polygon(ring).wkb.hex()}, "area_polygon_form"
        )


def test_two_road_files_are_road_file_missing(tmp_path: Path) -> None:
    """Two road files are the same refusal as none."""
    _install_road(tmp_path)
    extra = tmp_path / "roads_osm" / f"{_OTHER}.pbf"
    extra.write_bytes(b"SYN-OTHER")
    with pytest.raises(AreaError) as caught:
        produce_areas(_Hand(), (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert caught.value.reason == "road_file_missing"


def test_wrong_road_name_is_unreceipted(tmp_path: Path) -> None:
    """A road file whose name is not its digest is unreceipted."""
    _install_road(tmp_path)
    found = next((tmp_path / "roads_osm").glob("*.pbf"))
    found.rename(found.parent / "SYN.pbf")
    with pytest.raises(AreaError) as caught:
        produce_areas(_Hand(), (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert caught.value.reason == "road_file_unreceipted"


def test_unreadable_road_receipt_is_unreceipted(tmp_path: Path) -> None:
    """A receipt that is not JSON is unreceipted."""
    _install_road(tmp_path)
    receipt = next((tmp_path / "roads_osm").glob("*.meta.json"))
    receipt.write_text("SYN", encoding="utf-8")
    with pytest.raises(AreaError) as caught:
        produce_areas(_Hand(), (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert caught.value.reason == "road_file_unreceipted"


def test_manifest_form_each_branch(tmp_path: Path) -> None:
    """Each manifest-form branch and operand returns area_manifest_form."""
    plants: tuple[object, ...] = (
        "SYN",
        [],
        {"files": [], "road_sha256": _SHA, "extra": 1},
        {"files": [], "road_sha256": "SYN"},
        {"files": {}, "road_sha256": _SHA},
        {"files": [{"name": "SYN-POINT.walk.10.json"}], "road_sha256": _SHA},
        {"files": [{"name": 1, "sha256": _SHA}], "road_sha256": _SHA},
        {"files": [{"name": "", "sha256": _SHA}], "road_sha256": _SHA},
        {"files": [{"name": "SYN/POINT.json", "sha256": _SHA}], "road_sha256": _SHA},
        {"files": [{"name": "SYN-POINT.json", "sha256": "SYN"}], "road_sha256": _SHA},
        {
            "files": [
                {"name": "SYN-POINT.walk.10.json", "sha256": _SHA},
                {"name": "SYN-POINT.walk.10.json", "sha256": _OTHER},
            ],
            "road_sha256": _SHA,
        },
    )
    for plant in plants:
        directory = tmp_path / "places_s2_t06" / "areas"
        directory.mkdir(parents=True, exist_ok=True)
        text = plant if isinstance(plant, str) else json.dumps(plant)
        (directory / "manifest.json").write_text(text, encoding="utf-8")
        _expect(tmp_path, "area_manifest_form")


def test_byte_order_and_srid_branches(tmp_path: Path) -> None:
    """Big-endian is accepted. An unknown order and an SRID flag are refused."""
    accepted = dump_wkb(Polygon(_RING), byte_order=0)
    _refuse(tmp_path, {"polygon_wkb_hex": accepted.hex()}, "")
    unknown = bytearray(Polygon(_RING).wkb)
    unknown[0] = 2
    _refuse(tmp_path, {"polygon_wkb_hex": bytes(unknown).hex()}, "area_polygon_form")
    flagged = dump_wkb(Polygon(_RING), srid=4326)
    _refuse(tmp_path, {"polygon_wkb_hex": flagged.hex()}, "area_polygon_form")


def test_wkb_both_branches(tmp_path: Path) -> None:
    """A non-string and a bad hex are both area_polygon_form."""
    _refuse(tmp_path, {"polygon_wkb_hex": 1}, "area_polygon_form")
    _refuse(tmp_path, {"polygon_wkb_hex": "zz"}, "area_polygon_form")


def test_object_both_branches(tmp_path: Path) -> None:
    """Invalid JSON and a JSON array are both area_request_mismatch."""
    _body(tmp_path, b"SYN")
    _expect(tmp_path, "area_request_mismatch")
    _body(tmp_path, b"[]")
    _expect(tmp_path, "area_request_mismatch")


def test_request_of_three_operands(tmp_path: Path) -> None:
    """Mode, cut-off and a non-text coordinate each refuse the stored request."""
    _verify_change(tmp_path, {"mode": "fly"}, "area_request_mismatch")
    _verify_change(tmp_path, {"cutoff_minutes": 7}, "area_request_mismatch")
    _verify_change(tmp_path, {"lon": 51}, "area_request_mismatch")


def test_engine_non_bytes_is_polygon_form(tmp_path: Path) -> None:
    """A bytearray answer is area_polygon_form before geometry decoding."""
    _install_road(tmp_path)
    with pytest.raises(AreaError) as caught:
        produce_areas(
            _Hand(answer=bytearray(Polygon(_RING).wkb)),
            (_request(),),
            cache=tmp_path,
            frame_box=_FRAME,
        )
    assert caught.value.reason == "area_polygon_form"


def test_engine_index_and_key_errors_are_engine_failed(tmp_path: Path) -> None:
    """IndexError and KeyError from the engine are engine_failed."""
    _install_road(tmp_path)
    for kind in (IndexError, KeyError):
        with pytest.raises(AreaError) as caught:
            produce_areas(
                _Hand(error=kind), (_request(),), cache=tmp_path, frame_box=_FRAME
            )
        assert caught.value.reason == "engine_failed"


def test_provider_uses_the_shared_request_text(tmp_path: Path) -> None:
    """The provider reads the shared list, so a reformatted coordinate cannot pass."""
    _install_road(tmp_path)
    _write_valid(tmp_path)
    listed = AreaRequest(
        "SYN-POINT", "51.500001", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_10
    )
    provider = FileAreaProvider(tmp_path, _FRAME, (listed,))
    with pytest.raises(AreaError) as caught:
        provider.area(*_walk_10())
    assert caught.value.reason == "area_request_mismatch"


def test_empty_tables_are_zero_lines() -> None:
    """An empty table is an empty file, zero lines."""
    assert render_place_rows(()) == ""
    assert render_verification_rows((), frozenset()) == ""


def test_stale_digest_stale_manifest_and_failed_candidate(tmp_path: Path) -> None:
    """The stage reports the validator's reason and never the failed candidate."""
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    check = _check(record.body, record.digest, record.passed_keys, _SHA)
    review = tmp_path / "review"
    review.mkdir()
    _decision(review, record.digest, _OTHER)
    assert _decision_against_file(review, check) == "stale_manifest"
    _decision(review, _OTHER, _SHA)
    assert _decision_against_file(review, check) == "stale_digest"
    failed = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False, fail="walk_5"),
    )
    failed_check = _check(failed.body, failed.digest, failed.passed_keys, _SHA)
    _decision(review, failed.digest, _SHA)
    assert _decision_against_file(review, failed_check) == "failed_candidate"
    assert _decision_against_file(review, "[]\n") == "decision_fields"


def test_duplicate_place_key_is_reraise(tmp_path: Path) -> None:
    """A duplicate key is the frame error, not record_missing."""
    del tmp_path
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
    cell = h3.str_to_int(h3.latlng_to_cell(25.30, 51.50, 9))
    points = {("places_ovt", "SYN-LAND"): {"lon": "51.500000", "lat": "25.300000"}}
    with pytest.raises(FrameError) as caught:
        resolve_review([spec, spec], points, [{"cell": cell}])
    assert "duplicate place key" in str(caught.value)


def test_producer_nothing_to_do_and_missing_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing to do is one line. A missing engine is one refusal and writes nothing."""
    cache = tmp_path / "data" / "public_cache"
    review = _empty_review(tmp_path)
    _install_road(cache)
    lines: list[str] = []
    areas_before_stage(cache, lines, review)
    assert lines == ["areas: nothing to do"]
    _point(cache, review)
    popped = sys.modules.pop(_ENGINE, None)
    real = builtins.__import__

    def blocked(
        name: str,
        global_values: dict[str, object] | None = None,
        local_values: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == _ENGINE:
            raise ImportError("planted")
        return real(name, global_values, local_values, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    refused: list[str] = []
    areas_before_stage(cache, refused, review)
    monkeypatch.undo()
    if popped is not None:
        sys.modules[_ENGINE] = popped
    assert refused == ["REFUSED engine_package_missing"]
    assert not (cache / "places_s2_t06" / "areas").exists()


def test_producer_writes_then_does_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The producer writes once, then a matching manifest is one line."""
    cache = tmp_path / "data" / "public_cache"
    review = _empty_review(tmp_path)
    _install_road(cache)
    _point(cache, review)
    hand = _Hand()
    monkeypatch.setattr(
        "eii_custodian.publicdata.places.integrate.open_pinned_engine",
        lambda: hand,
    )
    first: list[str] = []
    areas_before_stage(cache, first, review)
    assert first == []
    name = "SYN-SHOW.walk.10.json"
    assert (cache / "places_s2_t06" / "areas" / name).is_file()
    second: list[str] = []
    areas_before_stage(cache, second, review)
    assert second == ["areas: nothing to do"]
    assert hand.polygons == 1


def test_build_public_leaves_other_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skip, a missing receipt and a missing frame leave the other stages as before."""
    cache = tmp_path / "data" / "public_cache"
    called: list[str] = []

    def frame(*_args: object, **_kwargs: object) -> None:
        called.append("frame")

    monkeypatch.setattr("eii_custodian.publicdata.frame.build.build_frame", frame)
    citation = replace(
        _entry(),
        kind="citation_only",
        extension="",
        nightly_live_fetch=False,
        url="https://www.ilo.org/resource/news/planted",
    )
    quiet = run_build((citation,), _unused, cache, _clock, _sleep)
    assert quiet.failure is None
    assert called == []
    assert any(line.startswith("COVERAGE ") for line in quiet.lines)
    assert all(not line.startswith("areas:") for line in quiet.lines)
    skipped = replace(citation, skip_reason="planted skip")
    left = run_build((skipped,), _unused, cache, _clock, _sleep)
    assert left.failure is None
    assert left.lines[0] == "SKIP planted planted skip"
    assert any(line.startswith("COVERAGE ") for line in left.lines)
    assert all(not line.startswith("areas:") for line in left.lines)

    def transport(_url: str) -> object:
        raise TransportFault("unreachable", "https://download.openstreetmap.fr/planted")

    missing = run_build((_entry(),), transport, cache, _clock, _sleep)
    assert missing.failure is not None
    assert all(not line.startswith("areas:") for line in missing.lines)
    assert all(not line.startswith("REFUSED") for line in missing.lines)
    review = _empty_review(tmp_path)
    _install_road(cache)
    (review / "showcase_gazetteer.yaml").write_text("[]\n", encoding="utf-8")
    again = run_build((citation,), _unused, cache, _clock, _sleep)
    assert again.failure is None
    assert "areas: nothing to do" in again.lines
    assert any(line.startswith("COVERAGE ") for line in again.lines)
    assert called == []


def _refuse(cache: Path, change: dict[str, object], reason: str) -> None:
    _install_road(cache)
    _write_valid(cache, **change)
    if reason == "":
        result = _provider(cache).area(*_walk_10())
        assert result.stand_in is False
        return
    _expect(cache, reason)


def _expect(cache: Path, reason: str) -> None:
    with pytest.raises(AreaError) as caught:
        _provider(cache).area(*_walk_10())
    assert caught.value.reason == reason


def _body(cache: Path, body: bytes) -> None:
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    _install_road(cache)
    _write_valid(cache)
    path = cache / "places_s2_t06" / "areas" / "SYN-POINT.walk.10.json"
    path.write_bytes(body)
    manifest = cache / "places_s2_t06" / "areas" / "manifest.json"
    loaded = json.loads(manifest.read_text(encoding="utf-8"))
    loaded["files"][0]["sha256"] = sha256_hex(body)
    manifest.write_text(json.dumps(loaded), encoding="utf-8")


def _verify_change(cache: Path, change: dict[str, object], reason: str) -> None:
    _install_road(cache)
    _write_valid(cache, **change)
    with pytest.raises(AreaError) as caught:
        verify_areas(_Hand(), cache=cache, frame_box=_FRAME)
    assert caught.value.reason == reason


def _check(
    body: dict[str, object], digest: str, keys: tuple[str, ...], manifest: str
) -> str:
    return json.dumps(
        {
            "body": body,
            "digest": digest,
            "manifest_sha256": manifest,
            "passed_keys": list(keys),
            "passing_evidence": True,
        }
    )


def _decision(review: Path, digest: str, manifest: str) -> None:
    text = (
        "candidate_key: SYN-CAND-1\n"
        f"digest: {digest}\n"
        f"manifest_sha256: {manifest}\n"
        "provisional: true\n"
    )
    (review / "flagship.yaml").write_text(text, encoding="utf-8")


def _empty_review(root: Path) -> Path:
    review = root / "custodian" / "publicdata" / "review"
    review.mkdir(parents=True)
    for name in (
        "showcase_areas.yaml",
        "showcase_gazetteer.yaml",
        "flagship_candidates.yaml",
    ):
        (review / name).write_text("[]\n", encoding="utf-8")
    return review


def _point(cache: Path, review: Path) -> None:
    text = (
        "- place_key: SYN-SHOW\n"
        "  mode: walk\n"
        "  cutoff_minutes: 10\n"
        "  source_id: places_ovt\n"
        "  record_key: SYN-P-A\n"
    )
    (review / "showcase_areas.yaml").write_text(text, encoding="utf-8")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    folder = cache / "places_ovt" / "part-00014"
    folder.mkdir(parents=True)
    body = folder / "syn.parquet"
    write_places(body, [place_row()])
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    digest = sha256_hex(body.read_bytes())
    (folder / "syn.meta.json").write_text(
        json.dumps(
            {
                "sha256": digest,
                "retrieved_utc": "2026-11-14T00:00:00Z",
                "publisher": "SYN",
            }
        ),
        encoding="utf-8",
    )


def _unused(_url: str) -> object:
    raise AssertionError("transport")


class _Hand:
    """A stand-in engine. It returns one square or a planted error."""

    version = ENGINE_PIN

    def __init__(
        self, answer: object | None = None, error: type[Exception] | None = None
    ) -> None:
        self._answer = bytes(Polygon(_RING).wkb) if answer is None else answer
        self._error = error
        self.polygons = 0

    def polygon(self, request: AreaRequest, road: bytes) -> object:
        del request, road
        self.polygons += 1
        if self._error is not None:
            raise self._error("planted")
        return self._answer
