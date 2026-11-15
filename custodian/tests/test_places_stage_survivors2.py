"""Stage-flow mutation regressions using only invented near-origin fixtures."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    receipt_for,
    write_buildings,
    write_places,
)
from shapely.geometry import box

from eii_custodian.publicdata.places import PlacesError, stage
from eii_custodian.publicdata.places.area_files import AreaRequest, FileAreaProvider
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.build import PlacesResult
from eii_custodian.publicdata.places.display import (
    CensusFigure,
    PubPlace,
    open_listings_caveat,
)
from eii_custodian.publicdata.places.flagship import (
    CandidateInput,
    CheckRecord,
    CountedPlace,
    evaluate_candidates,
)
from eii_custodian.publicdata.places.stage import (
    StageConfig,
    _decision_against_file,
    _provider,
    _source_points,
    run_places_stage,
)
from eii_custodian.publicdata.places_fsq.select import FrameBox

_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_REAL_PATH_READ_TEXT = Path.read_text
_REAL_PATH_WRITE_TEXT = Path.write_text


def _any(value: object) -> Any:
    return value


def _refusal(call: Callable[[], object], whole: str) -> None:
    """Compare the complete refusal text, not a prefix or a regular expression."""
    with pytest.raises(PlacesError) as caught:
        call()
    assert str(caught.value) == whole
    assert caught.value.reason == whole


def _ascii_default_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make an omitted text encoding behave as an ASCII process default."""

    def read_text(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if encoding is None:
            raise LookupError("planted_ascii_default")
        return _REAL_PATH_READ_TEXT(path, encoding=encoding, errors=errors)

    def write_text(
        path: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if encoding is None:
            raise LookupError("planted_ascii_default")
        return _REAL_PATH_WRITE_TEXT(
            path, data, encoding=encoding, errors=errors, newline=newline
        )

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "write_text", write_text)


def _review(root: Path) -> Path:
    review = root / "review"
    review.mkdir()
    (review / "places_ovt_attribution.csv").write_text(
        "dataset_token,licence\n", encoding="utf-8"
    )
    (review / "places_ovt_categories.csv").write_text(
        "basic_category,category_class\n", encoding="utf-8"
    )
    for name in (
        "showcase_areas.yaml",
        "showcase_gazetteer.yaml",
        "flagship_candidates.yaml",
    ):
        (review / name).write_text("[]\n", encoding="utf-8")
    return review


def _config(
    root: Path,
    places_path: Path | None = None,
    buildings_paths: tuple[Path, ...] = (),
    **changes: object,
) -> StageConfig:
    places = root / "syn-places.parquet" if places_path is None else places_path
    if not places.exists():
        places.write_bytes(b"SYN")
    fields: dict[str, object] = {
        "cache": root / "cache",
        "review": root / "review",
        "arabic_tag": "ar",
        "boundary": box(0, 0, 1, 1),
        "grid": (),
        "zones": {},
        "places_path": places,
        "places_receipt": receipt_for(places),
        "buildings_paths": buildings_paths,
    }
    fields.update(changes)
    return StageConfig(**_any(fields))


def _place() -> PubPlace:
    return PubPlace(
        "SYN-P-A",
        "SYN Place",
        "مكان تجريبي",
        "syn_other",
        "other",
        Decimal("0.01"),
        Decimal("0.02"),
        7,
        "syn-release",
        "syn-source",
        "SYN-LICENCE",
        Decimal("0.8"),
        "",
    )


def _empty_result() -> PlacesResult:
    return PlacesResult(
        places=(_place(),),
        verifications=(),
        shown_ids=frozenset(),
        fsq_shown=(),
        excluded={},
        report=(),
        complete=False,
        caveat=open_listings_caveat(),
        unresolved=(),
        hidden=0,
        flagship=None,
        names=(),
        receipts=(),
    )


class _Areas:
    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point_key, point, mode, cutoff
        return AreaResult(
            bytes(box(0, 0, 1, 1).wkb),
            "syn-method",
            "a" * 64,
            "b" * 64,
            "syn-engine",
            False,
        )


def _passing_record() -> CheckRecord:
    candidate = CandidateInput(
        "SYN-CAND", bytes(box(0.4, 0.4, 0.6, 0.6).wkb), "commercial", 0.5, 0.5
    )
    places = tuple(
        CountedPlace(f"SYN-R-{index}", 0.5, 0.5, "restaurant", "verified_open")
        for index in range(6)
    ) + tuple(
        CountedPlace(f"SYN-I-{index}", 0.5, 0.5, "italian_restaurant", "verified_open")
        for index in range(2)
    )
    return evaluate_candidates((candidate,), places, {"69": box(0, 0, 1, 1)}, _Areas())


def test_decision_file_io_is_utf8_under_an_ascii_process_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ascii_default_encoding(monkeypatch)
    review = _review(tmp_path)
    (review / "flagship.yaml").write_text(
        'candidate_key: SYN-CAND\nsyn_note: "مكان تجريبي"\n', encoding="utf-8"
    )
    assert (
        _decision_against_file(review, '{"syn_note":"مكان تجريبي"}\n')
        == "decision_fields"
    )


def test_a_recorded_decision_without_its_key_is_refused(tmp_path: Path) -> None:
    (tmp_path / "flagship.yaml").write_text(
        "digest: ''\nprovisional: true\n", encoding="utf-8"
    )
    assert _decision_against_file(tmp_path, "{}\n") == "decision_fields"


def test_decision_check_file_has_its_named_private_folder_and_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []
    names: list[str] = []
    real = stage.TemporaryDirectory

    def recording(*args: object, **kwargs: object) -> object:
        seen.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(stage, "TemporaryDirectory", recording)
    monkeypatch.setattr(
        stage,
        "validate_recorded_decision",
        lambda decision, path: names.append(path.name),
    )
    (tmp_path / "flagship.yaml").write_text(
        "candidate_key: SYN-CAND\n", encoding="utf-8"
    )
    assert stage._decision_against_file(tmp_path, "{}\n") == "SYN-CAND"
    assert seen == [((), {"prefix": "syn-check-"})]
    assert names == ["flagship_check.json"]


def test_valid_recorded_decision_returns_the_whole_candidate_key(
    tmp_path: Path,
) -> None:
    review = _review(tmp_path)
    record = _passing_record()
    (review / "flagship.yaml").write_text(
        "candidate_key: SYN-CAND\n"
        f"digest: {record.digest}\n"
        "manifest_sha256: syn-manifest\n"
        "provisional: true\n",
        encoding="utf-8",
    )
    check = json.dumps(
        {
            "body": record.body,
            "caveat_key": "open_listings_incomplete",
            "digest": record.digest,
            "manifest_sha256": "syn-manifest",
            "passed_keys": list(record.passed_keys),
            "passing_evidence": record.passing_evidence,
        }
    )
    assert _decision_against_file(review, check) == "SYN-CAND"


def test_source_points_have_exact_place_and_building_coordinates(
    tmp_path: Path,
) -> None:
    places = tmp_path / "syn-places.parquet"
    buildings = tmp_path / "syn-buildings.parquet"
    write_places(places, [place_row(place_id="SYN-P-A", lon=0.03, lat=0.04)])
    ring = ((0, 0), (0.02, 0), (0.02, 0.04), (0, 0.04), (0, 0))
    write_buildings(buildings, [building_row("SYN-B-A", ring)])
    config = _config(tmp_path, places, (buildings,))
    assert _source_points(config) == {
        ("places_ovt", "SYN-P-A"): (0.03, 0.04),
        ("bldg_ovt", "SYN-B-A"): (0.01, 0.02),
    }


def test_source_points_pass_the_frame_box_to_the_building_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    places = tmp_path / "syn-places.parquet"
    buildings = tmp_path / "syn-buildings.parquet"
    write_places(places, [place_row(place_id="SYN-P-A", lon=0.03, lat=0.04)])
    ring = ((1.9, 0.4), (2.1, 0.4), (2.1, 0.6), (1.9, 0.6), (1.9, 0.4))
    write_buildings(buildings, [building_row("SYN-B-A", ring)])
    monkeypatch.setattr(stage, "FRAME_BOX", FrameBox(0, 0, 1, 3))
    config = _config(tmp_path, places, (buildings,))
    _refusal(lambda: _source_points(config), "axis_swapped")


def test_provider_receives_the_shared_area_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    manifest = config.cache / "places_s2_t06" / "areas" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"")
    expected = AreaRequest(
        "SYN-SHOW", "0.010000", "0.020000", AreaMode.WALK, AreaCutoff.MINUTES_10
    )
    captured: dict[str, object] = {}

    def fake_provider(
        cache: Path,
        frame_box: tuple[float, float, float, float],
        requests: Sequence[AreaRequest],
    ) -> FileAreaProvider:
        captured["cache"] = cache
        captured["frame_box"] = frame_box
        captured["requests"] = tuple(requests)
        return FileAreaProvider(cache, frame_box, requests)

    monkeypatch.setattr(stage, "FRAME_BOX", FrameBox(0.0, 0.0, 1.0, 3.0))
    monkeypatch.setattr(stage, "_source_points", lambda _config: {})
    monkeypatch.setattr(stage, "area_requests", lambda _review, _points: (expected,))
    monkeypatch.setattr(stage, "FileAreaProvider", fake_provider)
    assert _provider(config) is not None
    assert captured == {
        "cache": config.cache,
        "frame_box": (0.0, 0.0, 1.0, 3.0),
        "requests": (expected,),
    }


def test_stage_forwards_the_empty_release_and_the_census_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path)
    figure = CensusFigure(
        "est_census", "syn_table", "syn_indicator", "2026-11-14", "c" * 64, 17
    )
    config = _config(
        tmp_path, review=review, fsq_rows=(), fsq_release="", census=figure
    )
    captured: dict[str, object] = {}

    def fake_build(*args: Any, **kwargs: Any) -> PlacesResult:
        del args
        captured.update(kwargs)
        return _empty_result()

    monkeypatch.setattr(stage, "build_places", fake_build)
    run_places_stage(config)
    assert captured["fsq_release"] == ""
    assert captured["census"] is figure


def test_stage_embeds_the_area_manifest_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = _review(tmp_path)
    config = _config(tmp_path, review=review)
    manifest = config.cache / "places_s2_t06" / "areas" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"")
    monkeypatch.setattr(stage, "_provider", lambda _config: None)
    monkeypatch.setattr(stage, "build_places", lambda *args, **kwargs: _empty_result())
    outcome = run_places_stage(config)
    check = json.loads(
        (outcome.directory / "flagship_check.json").read_text(encoding="utf-8")
    )
    assert check["manifest_sha256"] == _EMPTY_SHA256
