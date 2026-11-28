"""P2 coverage-only: same invented caller outputs, refusal and effects as base."""

from __future__ import annotations

import hashlib

import pytest
from custodian.tests import test_places_stage as fixture
from custodian.tests.test_places_read_parity import base_module, canonical, outcome
from custodian.tests.test_places_registry_areas import _candidate

from eii_custodian.publicdata.places import build, integrate, read, stage
from eii_custodian.publicdata.places.area_requests import area_requests


def bind(monkeypatch, module):
    def places(path, tag, frame_box=None, *, outside=None):
        source = getattr(module, "iter_place_file", module.read_place_file)
        if hasattr(module, "_validated_rows"):
            return source(path, tag, frame_box, outside=outside)
        rows = source(path, tag, frame_box)
        if outside is None:
            return rows
        omitted = [0]
        kept = []
        for row in rows:
            if frame_box is not None and not module._in_box(
                float(row.lon), float(row.lat), frame_box
            ):
                omitted[-1] += 1
            else:
                kept.append(row)
                omitted.append(0)
        outside.extend(omitted)
        return kept

    for consumer in (build, stage, integrate):
        if hasattr(consumer, "read_place_file"):
            monkeypatch.setattr(consumer, "read_place_file", places)
        for kind in ("place", "building"):
            name = f"iter_{kind}_points"
            if hasattr(consumer, name):

                def projected(path, *args, _kind=kind, **kwargs):
                    source = getattr(module, f"iter_{_kind}_points", None)
                    if source is not None:
                        return source(path, *args, **kwargs)
                    source = getattr(module, f"read_{_kind}_file")
                    return (
                        (getattr(row, f"{_kind}_id"), float(row.lon), float(row.lat))
                        for row in source(path, *args, **kwargs)
                    )

                monkeypatch.setattr(consumer, name, projected)
        if hasattr(consumer, "read_building_file"):
            monkeypatch.setattr(
                consumer,
                "read_building_file",
                getattr(module, "iter_building_file", module.read_building_file),
            )
        if hasattr(consumer, "load_boundary_buildings"):
            monkeypatch.setattr(
                consumer, "load_boundary_buildings", module.load_boundary_buildings
            )


def test_stage_bytes_and_provider(tmp_path, monkeypatch):
    """Full stage includes build_places, _provider, _buildings and all outputs."""
    base = base_module(tmp_path)
    review = fixture._review(tmp_path, fixture._verified_filled())
    places = fixture._places(tmp_path, fixture._food() + fixture._edges())
    fixture._buildings(tmp_path)
    fixture._areas(tmp_path)
    config = fixture._config(tmp_path, review, places, fsq=True)
    results = []
    for module in (base, read):
        with monkeypatch.context() as patch:
            bind(patch, module)
            points = stage._source_points(config)
            requests = area_requests(review, points)
            buildings = stage._buildings(config)
            result = stage.run_places_stage(config)
            outputs = {
                p.name: (p.read_bytes(), hashlib.sha256(p.read_bytes()).hexdigest())
                for p in result.directory.iterdir()
                if p.is_file()
            }
            results.append(
                (
                    canonical(result),
                    canonical(requests),
                    canonical(buildings),
                    outputs,
                    canonical(config.places_receipt),
                    canonical(config.buildings_receipts),
                )
            )
    assert results[0] == results[1]


@pytest.mark.parametrize("position", [0, 2048, 4096])
def test_build_late_fault_has_no_keep_effects(tmp_path, monkeypatch, position):
    base = base_module(tmp_path)
    review = fixture._review(tmp_path, "", candidates=False, areas=False)
    rows = [
        fixture._one(f"SYN-{i}", 51.5, 25.3, "syn_other", "0.8") for i in range(4097)
    ]
    rows[position]["id"] = ""
    places = fixture._places(tmp_path, rows)
    config = fixture._config(tmp_path, review, places)
    results = []
    for module in (base, read):
        with monkeypatch.context() as patch:
            bind(patch, module)
            effects = []
            original = build._keep

            def keep(*args, _effects=effects, _original=original, **kwargs):
                _effects.append(args[0].place_id)
                return _original(*args, **kwargs)

            patch.setattr(build, "_keep", keep)
            result = outcome(lambda: stage.run_places_stage(config))
            results.append((result, effects))
    assert results[0][0][1] == "place_id"
    assert results[0] == results[1]
    assert results[1][1] == []


def test_integrate_loop_and_receipts(tmp_path, monkeypatch):
    base = base_module(tmp_path)
    cache, review = _candidate(tmp_path, monkeypatch, "bldg_ovt/part-00384")
    results = []
    for module in (base, read):
        with monkeypatch.context() as patch:
            bind(patch, module)
            results.append(
                (
                    integrate._cache_points(cache, review),
                    area_requests(review, integrate._cache_points(cache, review)),
                )
            )
    assert results[0] == results[1]


def test_build_excluded_and_report(tmp_path, monkeypatch):
    base = base_module(tmp_path)
    review = fixture._review(tmp_path, "", candidates=False, areas=False)
    places = fixture._places(
        tmp_path,
        fixture._food()
        + fixture._edges()
        + [fixture._one("SYN-FAR", 10, 20, "syn_other", "0.8")],
    )
    config = fixture._config(tmp_path, review, places)
    attribution = stage.load_attribution(review / "places_ovt_attribution.csv", None)[1]
    categories = stage.load_categories(review / "places_ovt_categories.csv", None)[1]
    results = []
    for module in (base, read):
        with monkeypatch.context() as patch:
            bind(patch, module)
            results.append(
                canonical(
                    build.build_places(
                        places,
                        arabic_tag="ar",
                        boundary=config.boundary,
                        grid=config.grid,
                        attribution=attribution,
                        categories=categories,
                        places_receipt=config.places_receipt,
                    )
                )
            )
    assert results[0] == results[1]
