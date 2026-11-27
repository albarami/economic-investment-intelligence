"""D2 declarations at the assembly/completeness consumer; invented bytes only."""

import json
from dataclasses import replace

import pytest
from custodian.tests.building_fixture import world
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, failures

from eii_custodian.publicdata import assembly_adapters, completeness
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.review.cache_fixture import write_cached

KEYS = ("places_ovt", "places_ovt/part-00014")
TABLES = ("pub_place", "pub_place_verification")


def _places_entries():
    # Only declarations come from the contract; every source/receipt is invented.
    declarations = {row.key: row.release_tables for row in load_registry()}
    return tuple(
        entry("places_ovt", key=key, release_tables=declarations[key]) for key in KEYS
    )


def _assembled(tmp_path, monkeypatch):
    prepared = world(tmp_path)
    places = _places_entries()
    build = context(prepared.cache, (*prepared.entries, *places))
    for row in places:
        stored = replace(row, key=row.key + "/listing") if row.key == KEYS[0] else row
        path = write_cached(prepared.cache, stored, b'{"invented":true}', select=False)
        prepared.selected[row.key] = path.stem
    (prepared.cache / "snapshot_pins.json").write_text(json.dumps(prepared.selected))
    build.reviewed_selections()

    def frame(*_args, **_kwargs):
        prepared.produce()
        directory = prepared.cache / "places_s2_t06"
        directory.mkdir()
        for name in (*TABLES, "place_points", "build_report", "flagship_check"):
            (
                directory / (name + ".jsonl" if name in TABLES else name + ".json")
            ).write_text(json.dumps({"place_id": "SYN-P-A"}) + "\n")
        return FrameResult(
            {
                name: [
                    {"municipality_code": "SYN-M", "name_en": "SYN", "name_ar": "SYN"}
                ]
                for name in ("municipality", "zone", "district", "grid_cell")
            },
            [],
            {"bnd_hdx": {"sha256": "a" * 64}, "bnd_zone_2020": {"sha256": "b" * 64}},
        )

    monkeypatch.setattr(assembly_adapters, "build_public_frame", frame)
    build.frame()
    return build, places


def _check(build, places):
    return completeness.check(
        entries=places,
        pack=completeness.Pack({"places_ovt": ()}, frozenset()),
        inventory={"places_ovt": ()},
        component_keys={"places_ovt": frozenset({KEYS[1]})},
        catalogue=set(TABLES),
        receipts={key: build.receipts[key] for key in KEYS},
        outputs={key: build.source_tables[key] for key in KEYS},
        absences={},
        cached_source_ids=(),
    )


@pytest.mark.parametrize("key", KEYS)
def test_places_declared_outputs_match_assembly(tmp_path, monkeypatch, key):
    build, places = _assembled(tmp_path, monkeypatch)
    assert build.source_tables[key] == list(TABLES)
    assert [row for row in _check(build, places) if row["id"] == key] == [
        {"id": key, "state": "in use", "reason": ""}
    ]


@pytest.mark.parametrize("key", KEYS)
def test_places_third_undeclared_table_still_fails(tmp_path, monkeypatch, key):
    build, places = _assembled(tmp_path, monkeypatch)
    assert failures(_check(build, places)) == []
    build.table("pub_invented_third", [], (key,))
    assert failures(_check(build, places)) == [
        {"id": key, "state": "failed", "reason": "source_completeness: output tables"}
    ]


@pytest.mark.parametrize("key", KEYS)
def test_missing_places_selection_refuses_assembly(tmp_path, monkeypatch, key):
    from eii_custodian.publicdata.assembly import AssemblyError

    build, _places = _assembled(tmp_path, monkeypatch)
    selected = dict(build.selected)
    del selected[key]
    (build.cache / "snapshot_pins.json").write_text(json.dumps(selected))
    with pytest.raises(AssemblyError, match=r"^snapshot_selection_invalid$"):
        context(build.cache, build.entries).reviewed_selections()


def test_places_declarations_change_only_places_fingerprints(tmp_path, monkeypatch):
    from custodian.tests.test_fetch_fingerprint import _stub_roots

    from eii_custodian.publicdata.fetch.fingerprint import scan_run

    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        files=("sources.yaml",),
        brancher=lambda row, large: "listing" if row.key == KEYS[0] else "a",
    )
    after = (*_places_entries(), entry("SYN-control"))
    before = tuple(
        replace(row, release_tables=("pub_place",)) if row.key in KEYS else row
        for row in after
    )
    old = scan_run(before, roots, large=False).records
    new = scan_run(after, roots, large=False).records
    assert all(value is not None for value in (*old.values(), *new.values()))
    assert {key for key in old if old[key] != new[key]} == set(KEYS)
    assert old[KEYS[0]]["siblings"] != new[KEYS[0]]["siblings"]
