"""Point readers preserve the base's order and whole-file refusal contract."""

import hashlib
from types import SimpleNamespace

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)
from custodian.tests.test_places_area_files import _install_road, _square
from custodian.tests.test_places_callers_parity import bind
from custodian.tests.test_places_partb_survivors_c import _receipt, _row
from custodian.tests.test_places_read_parity import BOX, base_module, outcome
from custodian.tests.test_places_registry_areas import _candidate
from shapely.geometry import box

from eii_custodian.publicdata.places import PlacesError, integrate, read, stage
from eii_custodian.publicdata.places.area_requests import area_requests


def points(module, kind, path, frame_box=None):
    """Use the existing row API as the reference before point readers exist."""
    projected = getattr(module, f"iter_{kind}_points", None)
    args = (path, "ar", frame_box) if kind == "place" else (path, frame_box)
    if projected is not None:
        yield from projected(*args)
    else:
        reader = getattr(
            module, f"iter_{kind}_file", getattr(module, f"read_{kind}_file")
        )
        for row in reader(*args):
            yield getattr(row, f"{kind}_id"), float(row.lon), float(row.lat)


@pytest.mark.parametrize("kind", ["place", "building"])
@pytest.mark.parametrize(
    "fault", ["valid", "decode", "box", "decode_box", "swap", "missing", "schema"]
)
def test_point_refusal_parity(tmp_path, kind, fault):
    base = base_module(tmp_path)
    path = tmp_path / "syn.parquet"
    frame = BOX
    if fault in {"box", "decode_box"}:
        frame = (51.0, 25.0)
    bad = fault in {"decode", "decode_box"}
    x, y = (25.5, 51.5) if fault == "swap" else (51.5, 25.5)
    if kind == "place":
        rows = [
            place_row(place_id="SYN-A", lon=x, lat=y),
            place_row(place_id="" if bad else "SYN-A", lon=x, lat=y),
        ]
        write_places(
            path,
            rows,
            drop=("names",) if fault == "missing" else (),
            schema_version="bad" if fault == "schema" else "2.0.0",
        )
    else:
        ring = tuple(box(x, y, x + 0.01, y + 0.01).exterior.coords)
        rows = [building_row("SYN-A", ring), building_row("" if bad else "SYN-A", ring)]
        write_buildings(
            path,
            rows,
            drop=("geometry",) if fault == "missing" else (),
            schema_version="bad" if fault == "schema" else "2.0.0",
        )
    expected = outcome(lambda: tuple(points(base, kind, path, frame)))
    assert outcome(lambda: tuple(points(read, kind, path, frame))) == expected


@pytest.mark.parametrize("kind", ["place", "building"])
def test_points_late_invalid_publishes_nothing(tmp_path, kind):
    path = tmp_path / "syn.parquet"
    if kind == "place":
        write_places(path, [place_row(place_id="SYN-A"), place_row(place_id="")])
    else:
        ring = tuple(box(51.4, 25.4, 51.5, 25.5).exterior.coords)
        write_buildings(path, [building_row("SYN-A", ring), building_row("", ring)])
    seen = []
    with pytest.raises(PlacesError, match=f"^{kind}_id$"):
        for point in points(read, kind, path):
            seen.append(point)
    assert seen == []


class _Engine:
    version = "3.9.1"

    def polygon(self, request, road):
        return _square()


def bind_points(patch, module):
    bind(patch, module)
    for consumer in (integrate, stage):
        for kind in ("place", "building"):
            name = f"iter_{kind}_points"
            if hasattr(consumer, name):

                def projected(path, *args, _kind=kind, **kwargs):
                    tagless = args[1:] if _kind == "place" else args
                    frame = kwargs.get("frame_box", tagless[0] if tagless else None)
                    return points(module, _kind, path, frame)

                patch.setattr(consumer, name, projected)


@pytest.mark.parametrize("copies", [1, 10_000])
def test_points_cache_order_and_requests(tmp_path, monkeypatch, copies):
    base = base_module(tmp_path)
    cache, review = _candidate(tmp_path, monkeypatch, "bldg_ovt/part-00384")
    path = cache / "bldg_ovt/part-00384/syn.parquet"
    ring = tuple(box(51.5, 25.3, 51.502, 25.302).exterior.coords)
    last = tuple(box(51.501, 25.301, 51.503, 25.303).exterior.coords)
    write_buildings(
        path,
        [
            building_row("SYN-B-A", ring),
            building_row("SYN-SECOND", ring),
            building_row("SYN-B-A", last),
            *(building_row(f"SYN-EXTRA-B-{index}", ring) for index in range(copies)),
        ],
    )
    _receipt(path)
    _install_road(cache)
    place_path = cache / "places_ovt/part-00014/syn.parquet"
    place_path.parent.mkdir(parents=True)
    write_places(
        place_path,
        [
            place_row(place_id="SYN-FIRST"),
            place_row(place_id="SYN-SECOND"),
            place_row(place_id="SYN-FIRST", lon=51.6),
            *(place_row(place_id=f"SYN-EXTRA-P-{index}") for index in range(copies)),
        ],
    )
    _receipt(place_path)
    entries = (
        _row("places_ovt/part-00014", "places_ovt"),
        _row("bldg_ovt/part-00384", "bldg_ovt"),
    )
    monkeypatch.setattr(integrate, "load_registry", lambda: entries)
    (review / "arabic_tag.txt").write_text("ar")
    config = SimpleNamespace(
        places_path=place_path, arabic_tag="ar", buildings_paths=(path,)
    )
    results = []
    for module in (base, read):
        with monkeypatch.context() as patch:
            bind_points(patch, module)
            patch.setattr(integrate, "open_pinned_engine", _Engine)
            found = integrate._cache_points(cache, review)
            stage_points = stage._source_points(config)
            lines = []
            directory = cache / "places_s2_t06/areas"
            if directory.exists():
                for file in directory.iterdir():
                    file.unlink()
            integrate.areas_before_stage(cache, lines, review)
            outputs = {file.name: file.read_bytes() for file in directory.iterdir()}
            receipts = {
                file.relative_to(cache).as_posix(): file.read_bytes()
                for file in cache.rglob("*.meta.json")
            }
            results.append(
                (
                    hashlib.sha256(repr(tuple(found.items())).encode()).hexdigest(),
                    hashlib.sha256(
                        repr(tuple(stage_points.items())).encode()
                    ).hexdigest(),
                    area_requests(review, found),
                    lines,
                    outputs,
                    receipts,
                )
            )
    assert results[0] == results[1]
    assert stage_points[("places_ovt", "SYN-FIRST")] == (51.6, 25.3)
    assert found[("bldg_ovt", "SYN-B-A")] == (51.502, 25.302)
