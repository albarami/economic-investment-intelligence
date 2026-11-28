"""Coverage-only differential oracle for bounded places readers, invented files only."""

from __future__ import annotations

import dataclasses
import importlib.util
import random
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    receipt_for,
    write_buildings,
    write_places,
)
from shapely.geometry import box

from eii_custodian.publicdata.places import PlacesError, read

BASE = "66c0ea750d7df8b54b20e8688a8768d52e21c0b1"
BOX = (51.0, 25.0, 52.0, 26.0)


def base_module(tmp_path):
    """Load the exact base from git into the test's temporary directory."""
    source = subprocess.check_output(
        ["git", "show", f"{BASE}:custodian/src/eii_custodian/publicdata/places/read.py"]
    )
    saved = Path(__file__).with_name("places_read_base.py").read_bytes()
    assert saved == source
    path = tmp_path / "syn_base.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("syn_places_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value):
    if dataclasses.is_dataclass(value):
        return tuple(
            (f.name, canonical(getattr(value, f.name)))
            for f in dataclasses.fields(value)
        )
    if isinstance(value, Decimal):
        return (Decimal, value.as_tuple())
    if isinstance(value, dict):
        return tuple((canonical(k), canonical(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(canonical(v) for v in value))
    return (type(value).__name__, value)


def outcome(call):
    try:
        return ("ok", canonical(call()))
    except Exception as error:
        return (type(error), getattr(error, "reason", str(error)))


def reader(module, kind):
    return getattr(module, f"iter_{kind}_file", getattr(module, f"read_{kind}_file"))


def test_base_copy_is_verbatim(tmp_path):
    base_module(tmp_path)


@pytest.mark.parametrize("seed", range(200))
def test_seeded_reader_parity(tmp_path, seed):
    """P1 coverage: generated files include empty, swapped, mixed and faults."""
    base = base_module(tmp_path)
    rng = random.Random(seed)
    rows = []
    for index in range(rng.randrange(0, 10)):
        lon, lat = rng.choice(((51.5, 25.5), (10.0, 20.0), (25.5, 51.5)))
        rows.append(
            place_row(
                place_id=f"SYN-{index}",
                lon=lon,
                lat=lat,
                confidence=rng.choice([None, -0.1, 0.0, 0.8, 1.1, float("nan")]),
                names={"primary": f"SYN-{seed}-{index}", "common": {"ar": "تجريبي"}},
            )
        )
    if rows and seed % 4 == 0:
        rows[rng.randrange(len(rows))]["id"] = ""
    path = tmp_path / "syn.parquet"
    write_places(path, rows)
    for bounds in (None, BOX):
        assert outcome(
            lambda bounds=bounds: tuple(reader(read, "place")(path, "ar", bounds))
        ) == outcome(lambda bounds=bounds: base.read_place_file(path, "ar", bounds))
    buildings = [
        building_row(f"SYN-B-{i}", tuple(box(x, y, x + 0.01, y + 0.01).exterior.coords))
        for i, (x, y) in enumerate(
            rng.choices(((51.5, 25.5), (10.0, 20.0), (25.5, 51.5)), k=rng.randrange(10))
        )
    ]
    if buildings and seed % 4 == 0:
        buildings[-1]["id"] = ""
    write_buildings(path, buildings)
    assert outcome(lambda: tuple(reader(read, "building")(path, BOX))) == outcome(
        lambda: base.read_building_file(path, BOX)
    )


@pytest.mark.parametrize("position", [0, 2048, 4096])
@pytest.mark.parametrize("fault", ["id", "axis", "geometry"])
def test_decode_fault_precedes_caller_effects(tmp_path, position, fault):
    """P2 coverage: every row is validated before caller state changes."""
    base = base_module(tmp_path)
    path = tmp_path / "syn.parquet"
    rows = [place_row(place_id=f"SYN-{i}") for i in range(4097)]
    if fault == "id":
        rows[position]["id"] = ""
    elif fault == "axis":
        rows[position] = place_row(lon=25.5, lat=120.5)
    else:
        rows[position]["geometry"] = box(1, 1, 2, 2).wkb
    write_places(path, rows)
    expected = outcome(lambda: base.read_place_file(path, "ar", BOX))
    seen = []

    def consume():
        for row in reader(read, "place")(path, "ar", BOX):
            seen.append(row.place_id)

    assert outcome(consume) == expected
    assert seen == []


def test_swap_uses_all_batches(tmp_path):
    path = tmp_path / "syn.parquet"
    rows = [place_row(place_id=f"SYN-{i}", lon=25.5, lat=51.5) for i in range(2049)]
    rows[-1] = place_row(place_id="SYN-LAST")
    write_places(path, rows)
    assert len(tuple(reader(read, "place")(path, "ar", BOX))) == 2049
    rows[-1] = place_row(place_id="SYN-LAST", lon=10, lat=20)
    write_places(path, rows)
    with pytest.raises(PlacesError, match=r"^axis_swapped$"):
        tuple(reader(read, "place")(path, "ar", BOX))


def test_buildings_duplicate_across_files(tmp_path):
    base = base_module(tmp_path)
    paths = [tmp_path / f"syn-{i}.parquet" for i in range(2)]
    ring = tuple(box(51.4, 25.4, 51.5, 25.5).exterior.coords)
    for path in paths:
        write_buildings(path, [building_row("SYN-DUP", ring)])
    receipts = [receipt_for(path) for path in paths]
    expected = outcome(lambda: base.load_boundary_buildings(paths, receipts, box(*BOX)))
    assert expected[1] == "building_duplicate"
    assert (
        outcome(lambda: read.load_boundary_buildings(paths, receipts, box(*BOX)))
        == expected
    )


def test_order_across_batches(tmp_path):
    """P1 coverage: distinct content across each batch boundary."""
    base = base_module(tmp_path)
    path = tmp_path / "syn-order.parquet"
    rows = [
        place_row(place_id=f"SYN-{i}", confidence=(i % 10) / 10) for i in range(4097)
    ]
    write_places(path, rows)
    assert canonical(tuple(reader(read, "place")(path, "ar", BOX))) == canonical(
        base.read_place_file(path, "ar", BOX)
    )


def test_decode_before_duplicate_and_swap(tmp_path):
    """P1 coverage: a later decode fault wins over a duplicate or swapped file."""
    base = base_module(tmp_path)
    path = tmp_path / "syn-priority.parquet"
    ring = tuple(box(25.4, 51.4, 25.5, 51.5).exterior.coords)
    rows = [
        building_row("SYN-DUP", ring),
        building_row("SYN-DUP", ring),
        building_row("", ring),
    ]
    write_buildings(path, rows)
    receipts = [receipt_for(path)]
    expected = outcome(
        lambda: base.load_boundary_buildings([path], receipts, box(*BOX))
    )
    assert expected[1] == "building_id"
    assert (
        outcome(lambda: read.load_boundary_buildings([path], receipts, box(*BOX)))
        == expected
    )


def test_first_decode_fault_wins(tmp_path):
    """Coverage: a later different decode fault cannot replace the first."""
    base = base_module(tmp_path)
    path = tmp_path / "syn-first.parquet"
    rows = [place_row(place_id=""), place_row(geometry=box(1, 1, 2, 2).wkb)]
    write_places(path, rows)
    expected = outcome(lambda: base.read_place_file(path, "ar", BOX))
    assert expected[1] == "place_id"
    assert outcome(lambda: tuple(reader(read, "place")(path, "ar", BOX))) == expected


def test_raw_read_error_precedes_decode(tmp_path, monkeypatch):
    """Coverage: raw fetch failure wins, even after a bad decoded first row."""
    base = base_module(tmp_path)
    path = tmp_path / "syn-raw-error.parquet"
    write_places(path, [place_row(place_id=""), place_row()])
    original = read._connect

    class Cursor:
        def __init__(self, cursor):
            self.cursor = cursor
            self.calls = 0

        def fetchall(self):
            raise RuntimeError("SYN late raw read")

        def fetchmany(self, _size):
            self.calls += 1
            if self.calls == 1:
                return self.cursor.fetchmany(1)
            raise RuntimeError("SYN late raw read")

    class Connection:
        def __init__(self):
            self.connection = original()

        def execute(self, query, *args):
            result = self.connection.execute(query, *args)
            if query.startswith("SELECT id, geometry, confidence"):
                return Cursor(result)
            return result

        def close(self):
            self.connection.close()

    monkeypatch.setattr(read, "_connect", Connection)
    monkeypatch.setattr(base, "_connect", Connection)
    expected = outcome(lambda: base.read_place_file(path, "ar", BOX))
    assert expected == (RuntimeError, "SYN late raw read")
    assert outcome(lambda: tuple(reader(read, "place")(path, "ar", BOX))) == expected


@pytest.mark.parametrize("frame_box", [(51.0, 25.0), (None, 25.0, 52.0, 26.5)])
@pytest.mark.parametrize("kind", ["place", "building"])
def test_later_decode_fault_precedes_box_fault(tmp_path, kind, frame_box):
    """Behaviour: malformed boxes cannot hide a later row's decode refusal."""
    base = base_module(tmp_path)
    path = tmp_path / "syn-box-fault.parquet"
    if kind == "place":
        write_places(path, [place_row(), place_row(place_id="")])
        expected = outcome(lambda: base.read_place_file(path, "ar", frame_box))
        actual = outcome(lambda: tuple(reader(read, kind)(path, "ar", frame_box)))
    else:
        ring = tuple(box(51.4, 25.4, 51.5, 25.5).exterior.coords)
        write_buildings(path, [building_row("SYN-VALID", ring), building_row("", ring)])
        expected = outcome(lambda: base.read_building_file(path, frame_box=frame_box))
        actual = outcome(lambda: tuple(reader(read, kind)(path, frame_box=frame_box)))
    assert expected == (PlacesError, f"{kind}_id")
    assert actual == expected
