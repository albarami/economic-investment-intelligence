"""National building producer plants, using invented Parquet only."""

import json
from dataclasses import replace

import pytest
from custodian.tests.building_fixture import (
    COLLECTION,
    PARTS,
    footprint,
    manifest,
    parquet,
    table,
    world,
)
from custodian.tests.snapshot_fixture import update_receipt
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from eii_custodian.publicdata.review.cache_fixture import write_cached


def refusal(prepared, name, **kwargs):
    from eii_custodian.publicdata.buildings import BuildingError

    with pytest.raises(BuildingError) as error:
        prepared.produce(**kwargs)
    assert error.value.name == name
    assert not (prepared.output / "manifest.buildings.json").exists()


def test_explicit_pin_wins_over_cache_review(tmp_path):
    prepared = world(tmp_path)
    entry = prepared.entries[0]
    body = parquet(tmp_path / "new.parquet", [footprint("SYN-NEW")])
    newer = write_cached(prepared.cache, entry, body)
    (prepared.cache / "snapshot_pins.json").write_text(
        json.dumps({entry.key: newer.stem})
    )
    prepared.produce()
    assert {
        row["properties"]["building_id"] for row in table(prepared)["features"]
    } == {"SYN-B-0", "SYN-B-1", "SYN-B-2"}


def test_registered_stac_collection_uses_existing_transport_and_receipt(tmp_path):
    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot
    from eii_custodian.publicdata.fetch.transport import Response

    entries = load_registry()
    entry = next(row for row in entries if row.key == COLLECTION)
    assert entry.kind == "https_file" and entry.extension == "json"
    body = b'{"type":"Collection","id":"SYN","links":[]}'
    calls = []

    def transport(url):
        calls.append(url)
        assert url == entry.url
        return Response(url, body, ())

    outcome = run_build(
        (entry,),
        transport,
        tmp_path / "cache",
        lambda: "2026-11-20T00:00:00Z",
        lambda _delay: None,
        _fetch_only=True,
    )
    assert outcome.failure is None
    assert calls == [entry.url]
    snapshot = read_snapshot(tmp_path / "cache" / entry.key, sha256_hex(body))
    assert snapshot.body == body
    assert snapshot.sidecar["source_id"] == "bldg_ovt"
    for row in entries:
        if row.key.startswith("bldg_ovt/stac-part-"):
            assert row.kind == "https_file" and row.extension == "json"
            assert row.url == "" and row.skip_reason == "direct_url_unconfirmed"


@pytest.mark.parametrize(
    "plant,name",
    [
        ("pin", "building_part_unpinned"),
        ("registry", "building_part_unregistered"),
        ("skip", "building_part_skipped"),
        ("snapshot", "building_part_unreceipted"),
        ("bytes", "building_part_unreceipted"),
        ("key", "building_part_receipt_mismatch"),
        ("source_id", "building_part_receipt_mismatch"),
        ("publisher", "building_part_receipt_mismatch"),
        ("licence_id", "building_part_receipt_mismatch"),
        ("licence_basis", "building_part_receipt_mismatch"),
    ],
)
def test_each_part_dependency_refuses_by_name(tmp_path, plant, name):
    prepared = world(tmp_path)
    key = PARTS[0]
    if plant == "pin":
        del prepared.selected[key]
    elif plant == "registry":
        prepared.entries = prepared.entries[1:]
    elif plant == "skip":
        prepared.entries = (
            replace(prepared.entries[0], skip_reason="schema_unconfirmed"),
            *prepared.entries[1:],
        )
    elif plant == "snapshot":
        (prepared.cache / key / "index" / (prepared.selected[key] + ".json")).unlink()
    elif plant == "bytes":
        from eii_custodian.publicdata.fetch.snapshots import read_snapshot

        read_snapshot(prepared.cache / key, prepared.selected[key]).path.write_bytes(
            b"SYN altered"
        )
    else:
        update_receipt(
            prepared.cache, key, prepared.selected[key], {plant: "SYN foreign"}
        )
    refusal(prepared, name)


def test_stac_part_set_and_national_box_are_deciding_guards(tmp_path):
    prepared = world(tmp_path)
    refusal(
        prepared,
        "national_boundary_outside_frame_box",
        boundary=box(51, 25, 51.8, 25.5),
    )
    key = prepared.entries[4].key
    document = {
        "type": "Feature",
        "id": "SYN-other",
        "bbox": [50.7, 24.4, 51.7, 26.2],
        "assets": {"data": {"href": "https://syn.invalid/unregistered-part"}},
    }
    path = write_cached(
        prepared.cache, prepared.entries[4], json.dumps(document).encode()
    )
    prepared.selected[key] = path.stem
    refusal(prepared, "bldg_ovt_part_set_incomplete")


def test_unregistered_stac_item_never_proves_completeness(tmp_path):
    prepared = world(tmp_path)
    prepared.entries = tuple(
        row for row in prepared.entries if row.key != prepared.entries[4].key
    )
    refusal(prepared, "bldg_ovt_part_set_incomplete")


def test_national_selection_is_unrounded_with_island_hole_and_separate_counts(tmp_path):
    mainland = Polygon(
        [(51, 25), (51.4, 25), (51.4, 25.5), (51, 25.5)],
        holes=[[(51.2, 25.2), (51.3, 25.2), (51.3, 25.3), (51.2, 25.3)]],
    )
    boundary = unary_union([mainland, box(51.5, 25.6, 51.6, 25.7)])
    prepared = world(
        tmp_path,
        rows=[
            [
                footprint("SYN-island", box(51.51, 25.61, 51.52, 25.62).wkb),
                footprint("SYN-hole", box(51.21, 25.21, 51.22, 25.22).wkb),
                footprint("SYN-outside-box", box(52, 25, 52.1, 25.1).wkb),
                footprint("SYN-round", box(51.4, 25.1, 51.4000008, 25.2).wkb),
            ],
            [footprint("SYN-north", box(51.1, 25.4, 51.2, 25.45).wkb)],
            [],
        ],
    )
    prepared.produce(boundary=boundary)
    block = manifest(prepared)
    assert block["national_completeness"] is True
    assert block["counts"] == {
        "read": 5,
        "kept": 2,
        "outside_frame_box": 1,
        "inside_box_outside_boundary": 2,
        "invalid_footprint": 0,
        "underground": 0,
    }
    assert block["boundary_review"]["outcome"] == "pending_lead_review"
    assert {
        row["properties"]["building_id"] for row in table(prepared)["features"]
    } == {"SYN-island", "SYN-north"}


def test_present_fields_are_null_and_counted_including_unusable_and_modelled(tmp_path):
    prepared = world(
        tmp_path,
        rows=[
            [
                footprint("SYN-height", height=23.5, num_floors=6),
                footprint(
                    "SYN-estimate",
                    height=-1,
                    num_floors=-2,
                    sources=[
                        {"property": "height", "dataset": "SYN model", "license": "SYN"}
                    ],
                ),
            ],
            [],
            [],
        ],
    )
    prepared.produce()
    for row in table(prepared)["features"]:
        assert row["properties"]["recorded_height_m"] is None
        assert row["properties"]["floor_count"] is None
    for name in ("height", "num_floors"):
        assert manifest(prepared)["optional_fields"][name] == {
            "mapping": "off",
            "reason": "recorded_field_unconfirmed",
            "present": 2,
            "usable": 1,
            "unusable": 1,
            "absent": 0,
            "source_value_present_unmapped": 2,
        }


def test_unmapped_height_coverage_uses_c47_usable_precision(tmp_path):
    prepared = world(
        tmp_path,
        rows=[
            [
                footprint("SYN-tiny", height=0.001),
                footprint("SYN-nan", height=float("nan")),
                footprint("SYN-infinite", height=float("inf")),
            ],
            [],
            [],
        ],
    )
    prepared.produce()
    counts = manifest(prepared)["optional_fields"]["height"]
    assert counts["present"] == counts["unusable"] == 3
    assert counts["usable"] == 0


def test_invalid_and_underground_footprints_are_excluded_without_repair(tmp_path):
    bow = Polygon([(51, 25), (51.1, 25.1), (51, 25.1), (51.1, 25), (51, 25)])
    prepared = world(
        tmp_path,
        rows=[
            [
                footprint("SYN-invalid", bow.wkb),
                footprint("SYN-underground", is_underground=True),
            ],
            [footprint("SYN-ok")],
            [],
        ],
    )
    prepared.produce()
    assert [
        row["properties"]["building_id"] for row in table(prepared)["features"]
    ] == ["SYN-ok"]
    assert manifest(prepared)["excluded"] == [
        {"building_id": "SYN-invalid", "part": PARTS[0], "reason": "invalid_footprint"},
        {"building_id": "SYN-underground", "part": PARTS[0], "reason": "underground"},
    ]


@pytest.mark.parametrize(
    "options,name",
    [
        ({"schema": "unknown"}, "building_schema_versions"),
        ({"crs": None}, "building_crs"),
        ({"crs": {"id": {"authority": "EPSG", "code": 4326}}}, "building_crs"),
        ({"drop": ("id",)}, "building_missing_column"),
    ],
)
def test_unknown_schema_crs_and_missing_columns_refuse(tmp_path, options, name):
    refusal(world(tmp_path, **options), name)


@pytest.mark.parametrize(
    "rows,name",
    [
        ([[footprint("SYN-dup")], [footprint("SYN-dup")], []], "building_duplicate"),
        ([[footprint("")], [], []], "building_id"),
        (
            [[footprint("SYN-swap", box(25.1, 51.1, 25.2, 51.2).wkb)], [], []],
            "building_axis_swapped",
        ),
    ],
)
def test_identifier_and_axis_plants(tmp_path, rows, name):
    refusal(world(tmp_path, rows=rows), name)


def test_identical_pins_produce_identical_bytes_and_sorted_ids(tmp_path):
    prepared = world(tmp_path, rows=[[footprint("SYN-Z"), footprint("SYN-A")], [], []])
    prepared.produce()
    first = [
        (prepared.output / name).read_bytes()
        for name in ("buildings.geojson", "manifest.buildings.json")
    ]
    prepared.produce()
    assert first == [
        (prepared.output / name).read_bytes()
        for name in ("buildings.geojson", "manifest.buildings.json")
    ]
    assert [
        row["properties"]["building_id"] for row in table(prepared)["features"]
    ] == ["SYN-A", "SYN-Z"]


def test_a_failed_rebuild_removes_earlier_completion_marker(tmp_path):
    prepared = world(tmp_path)
    prepared.produce()
    del prepared.selected[PARTS[0]]
    refusal(prepared, "building_part_unpinned")


@pytest.mark.parametrize("field,value", [("switched_off", True), ("fetch_url", "")])
def test_incomplete_or_switched_off_receipt_refuses(tmp_path, field, value):
    prepared = world(tmp_path)
    update_receipt(
        prepared.cache, PARTS[0], prepared.selected[PARTS[0]], {field: value}
    )
    refusal(prepared, "building_part_receipt_mismatch")


@pytest.mark.parametrize("plant", ["duplicate", "source", "kind"])
def test_part_registry_identity_is_closed(tmp_path, plant):
    prepared = world(tmp_path)
    row = prepared.entries[0]
    if plant == "duplicate":
        prepared.entries = (*prepared.entries, row)
    else:
        field = "source_id" if plant == "source" else "kind"
        changed = replace(row, **{field: "SYN foreign"})
        prepared.entries = (changed, *prepared.entries[1:])
        update_receipt(
            prepared.cache, row.key, prepared.selected[row.key], {field: "SYN foreign"}
        )
    refusal(prepared, "building_part_unregistered")


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"type": "Feature"},
        {"type": "Collection", "links": "SYN malformed"},
        {"type": "Collection", "links": ["SYN malformed"]},
        {"type": "Collection", "links": [{"rel": "item", "href": 7}]},
        {
            "type": "Collection",
            "links": [{"rel": "item", "href": "https://syn.invalid/unregistered"}],
        },
        {"type": "Collection", "links": []},
    ],
)
def test_incomplete_stac_collection_never_proves_completeness(tmp_path, document):
    prepared = world(tmp_path)
    row = next(row for row in prepared.entries if row.key == COLLECTION)
    prepared.selected[COLLECTION] = write_cached(
        prepared.cache, row, json.dumps(document).encode()
    ).stem
    refusal(prepared, "bldg_ovt_part_set_incomplete")


@pytest.mark.parametrize(
    "field,value",
    [
        ("bbox", None),
        ("bbox", [True, 25, 51, 26]),
        ("bbox", ["SYN", 25, 51, 26]),
        ("bbox", ["50.7", 24.4, 51.7, 26.2]),
        ("bbox", [52, 25, 51, 26]),
        ("bbox", [float("inf"), 25, 51, 26]),
        ("bbox", [70, 30, 71, 31]),
        ("assets", None),
        ("type", "SYN unsupported"),
        ("type", []),
    ],
)
def test_malformed_or_noncovering_stac_item_refuses(tmp_path, field, value):
    prepared = world(tmp_path)
    row = prepared.entries[4]
    document = {
        "type": "Feature",
        "bbox": [50.7, 24.4, 51.7, 26.2],
        "assets": {"data": {"href": prepared.entries[0].url}},
        field: value,
    }
    prepared.selected[row.key] = write_cached(
        prepared.cache, row, json.dumps(document).encode()
    ).stem
    refusal(prepared, "bldg_ovt_part_set_incomplete")


def test_duplicate_stac_part_assets_refuse(tmp_path):
    prepared = world(tmp_path)
    row = prepared.entries[5]
    document = {
        "type": "Feature",
        "bbox": [50.7, 24.4, 51.7, 26.2],
        "assets": {"data": {"href": prepared.entries[0].url}},
    }
    prepared.selected[row.key] = write_cached(
        prepared.cache, row, json.dumps(document).encode()
    ).stem
    refusal(prepared, "bldg_ovt_part_set_incomplete")


@pytest.mark.parametrize(
    "geo",
    [
        {"primary_column": "other"},
        {"primary_column": "geometry", "columns": {"geometry": {"encoding": "WKT"}}},
        {
            "primary_column": "geometry",
            "columns": {
                "geometry": {
                    "encoding": "WKB",
                    "crs": {
                        "id": {"authority": "OGC", "code": "CRS84"},
                        "coordinate_system": {
                            "axis": [{"direction": "north"}, {"direction": "east"}]
                        },
                    },
                }
            },
        },
    ],
)
def test_geoparquet_encoding_and_axes_are_not_guessed(tmp_path, geo):
    refusal(world(tmp_path, geo=geo), "building_crs")


def test_explicit_crs84_and_absent_optional_columns_are_supported(tmp_path):
    prepared = world(
        tmp_path,
        crs={"id": {"authority": "OGC", "code": "CRS84"}},
        drop=("height", "num_floors", "sources", "is_underground"),
    )
    prepared.produce()
    assert manifest(prepared)["optional_fields"]["height"]["absent"] == 3
    assert manifest(prepared)["footprint_contributors"] == {"unconfirmed": 3}


def test_axis_range_and_malformed_source_flag_refuse(tmp_path):
    prepared = world(
        tmp_path / "axis",
        rows=[[footprint("SYN-range", box(200, 25, 201, 26).wkb)], [], []],
    )
    refusal(prepared, "building_axis_range")
    prepared = world(
        tmp_path / "flag",
        rows=[[footprint("SYN-flag", is_underground="SYN malformed")], [], []],
        kinds_override={"is_underground": "VARCHAR"},
    )
    refusal(prepared, "building_underground_flag")


def test_receipted_nonparquet_refuses_with_producer_name(tmp_path):
    prepared = world(tmp_path)
    prepared.selected[PARTS[0]] = write_cached(
        prepared.cache, prepared.entries[0], b"SYN not parquet"
    ).stem
    refusal(prepared, "building_parquet")


def test_footprint_attribution_counts_record_level_datasets_only(tmp_path):
    prepared = world(
        tmp_path,
        rows=[
            [
                footprint(
                    "SYN-A",
                    sources=[
                        {"property": "", "dataset": "SYN first", "license": "SYN one"},
                        {
                            "property": "",
                            "dataset": "SYN second",
                            "license": "SYN two",
                        },
                        {
                            "property": "height",
                            "dataset": "SYN model",
                            "license": "SYN three",
                        },
                    ],
                )
            ],
            [],
            [],
        ],
    )
    prepared.produce()
    assert manifest(prepared)["footprint_contributors"] == {
        "SYN first": 1,
        "SYN second": 1,
    }
    assert set(manifest(prepared)["attribution_notices"]) == set(PARTS)


def test_reversed_source_rows_keep_table_bytes_and_id_hash(tmp_path):
    prepared = world(
        tmp_path / "first", rows=[[footprint("SYN-Z"), footprint("SYN-A")], [], []]
    )
    prepared.produce()
    other = world(
        tmp_path / "second", rows=[[footprint("SYN-A"), footprint("SYN-Z")], [], []]
    )
    other.produce()
    assert (prepared.output / "buildings.geojson").read_bytes() == (
        other.output / "buildings.geojson"
    ).read_bytes()
    assert (
        manifest(prepared)["parts"][PARTS[0]]["kept_ids_sha256"]
        == manifest(other)["parts"][PARTS[0]]["kept_ids_sha256"]
    )


@pytest.mark.parametrize("outcome", ["reviewed_no_land", "boundary_amendment_required"])
def test_lead_boundary_review_is_bound_to_input_chain_and_count(tmp_path, outcome):
    from eii_custodian.publicdata.building_inputs import dump
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    prepared = world(
        tmp_path, rows=[[footprint("SYN-out", box(51.5, 25.2, 51.6, 25.3).wkb)], [], []]
    )
    prepared.produce()
    block = manifest(prepared)
    review = prepared.cache / "review/building_boundary.json"
    review.parent.mkdir()
    review.write_bytes(
        dump(
            {
                "version": 1,
                "source_chain_sha256": sha256_hex(dump(block["source_chain"])),
                "inside_box_outside_boundary": 1,
                "outcome": outcome,
            }
        )
    )
    prepared.produce()
    result = manifest(prepared)["boundary_review"]
    assert result["outcome"] == outcome
    assert result["review_sha256"] == sha256_hex(review.read_bytes())


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("outcome", "SYN invented"),
        ("inside_box_outside_boundary", 2),
        ("inside_box_outside_boundary", True),
        ("source_chain_sha256", "a" * 64),
        ("SYN-extra", "SYN"),
    ],
)
def test_stale_or_malformed_boundary_review_refuses(tmp_path, field, value):
    from eii_custodian.publicdata.building_inputs import dump
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    prepared = world(
        tmp_path, rows=[[footprint("SYN-out", box(51.5, 25.2, 51.6, 25.3).wkb)], [], []]
    )
    prepared.produce()
    block = manifest(prepared)
    document = {
        "version": 1,
        "source_chain_sha256": sha256_hex(dump(block["source_chain"])),
        "inside_box_outside_boundary": 1,
        "outcome": "reviewed_no_land",
        field: value,
    }
    review = prepared.cache / "review/building_boundary.json"
    review.parent.mkdir()
    review.write_bytes(dump(document))
    refusal(prepared, "building_boundary_review")


@pytest.mark.parametrize(
    "plant,name",
    [
        ("missing", "building_manifest_absent"),
        ("table", "building_table_hash"),
        ("pin", "building_manifest_pins"),
        ("boundary", "building_manifest_boundary"),
        ("method", "building_manifest_method"),
        ("coverage", "building_manifest_coverage"),
        ("inputs", "building_manifest_inputs"),
        ("unreceipted", "building_manifest_inputs"),
        ("metadata_pin", "building_manifest_pins"),
    ],
)
def test_heights_rejects_stale_or_altered_building_chain_before_read(
    tmp_path, plant, name
):
    from eii_custodian.publicdata.heights.model import HeightError
    from eii_custodian.publicdata.heights.step import build_heights

    prepared = world(tmp_path)
    prepared.produce()
    marker = prepared.output / "manifest.buildings.json"
    table_path = prepared.output / "buildings.geojson"
    if plant == "missing":
        marker.unlink()
    elif plant == "table":
        table_path.write_bytes(table_path.read_bytes() + b" ")
    elif plant == "unreceipted":
        from eii_custodian.publicdata.fetch.snapshots import read_snapshot

        read_snapshot(
            prepared.cache / PARTS[0], prepared.selected[PARTS[0]]
        ).path.unlink()
    elif plant in {"pin", "boundary", "metadata_pin"}:
        key = {"pin": PARTS[0], "boundary": "bnd_hdx", "metadata_pin": COLLECTION}[
            plant
        ]
        row = next(row for row in prepared.entries if row.key == key)
        prepared.selected[key] = write_cached(
            prepared.cache, row, b"SYN changed input"
        ).stem
    else:
        document = json.loads(marker.read_text())
        if plant == "inputs":
            del document["source_chain"][PARTS[0]]
        else:
            document["method" if plant == "method" else "national_completeness"] = (
                "SYN altered"
            )
        marker.write_text(json.dumps(document))
    output = prepared.output.parent / "heights"
    output.mkdir()
    (output / "heights.json").write_text("SYN stale")
    with pytest.raises(HeightError) as error:
        build_heights(
            prepared.cache,
            prepared.entries,
            table_path,
            output,
            [],
            selections=prepared.selected,
        )
    assert error.value.name == name
    assert not (output / "heights.json").exists()


def test_full_polygon_holes_and_multipolygons_are_preserved(tmp_path):
    from shapely.geometry import MultiPolygon

    polygon = Polygon(
        [(51.05, 25.05), (51.15, 25.05), (51.15, 25.15), (51.05, 25.15)],
        holes=[[(51.07, 25.07), (51.09, 25.07), (51.09, 25.09), (51.07, 25.09)]],
    )
    multi = MultiPolygon([box(51.2, 25.1, 51.3, 25.2), box(51.1, 25.3, 51.15, 25.4)])
    prepared = world(
        tmp_path,
        rows=[
            [footprint("SYN-hole-footprint", polygon.wkb)],
            [footprint("SYN-multi", multi.wkb)],
            [],
        ],
    )
    prepared.produce()
    geometries = {
        row["properties"]["building_id"]: row["geometry"]
        for row in table(prepared)["features"]
    }
    assert geometries["SYN-hole-footprint"] == json.loads(
        json.dumps(polygon.__geo_interface__)
    )
    assert geometries["SYN-multi"] == json.loads(json.dumps(multi.__geo_interface__))


def test_heights_manifest_uses_building_manifest_path_and_hash(tmp_path):
    from eii_custodian.publicdata.fetch.bounded import file_hash
    from eii_custodian.publicdata.heights.step import build_heights

    prepared = world(tmp_path)
    prepared.produce()
    output = prepared.output.parent / "heights"
    build_heights(
        prepared.cache,
        prepared.entries,
        prepared.output / "buildings.geojson",
        output,
        [],
        selections=prepared.selected,
    )
    block = json.loads((output / "manifest.heights.json").read_text())
    source = next(row for row in block["files"] if row["key"] == "building_table")
    assert source["source_chain"] == {
        "path": "assets/buildings/manifest.buildings.json",
        "sha256": file_hash(prepared.output / "manifest.buildings.json"),
    }
    assert {
        row["building_id"] for row in json.loads((output / "heights.json").read_text())
    } == {"SYN-B-0", "SYN-B-1", "SYN-B-2"}


def test_legacy_frame_wrapper_preserves_named_producer_failure(tmp_path, monkeypatch):
    from eii_custodian.publicdata.buildings import BuildingError
    from eii_custodian.publicdata.places.integrate import frame_when_ready

    prepared = world(tmp_path)
    review = prepared.cache.parent.parent / "custodian/publicdata/review"
    review.mkdir(parents=True)
    (review / "showcase_gazetteer.yaml").write_text("[]")
    prepared.produce()

    def fail(*_args, **_kwargs):
        assert not (prepared.output / "buildings.geojson").exists()
        raise BuildingError("building_part_unpinned")

    monkeypatch.setattr("eii_custodian.publicdata.frame.build.build_frame", fail)
    lines = []
    with pytest.raises(BuildingError):
        frame_when_ready(prepared.cache, prepared.entries, lines)
    assert any(
        line.startswith("FAIL buildings") and "building_part_unpinned" in line
        for line in lines
    )


@pytest.mark.parametrize("plant", ["boundary", "review", "frame_refusal", "noop"])
def test_frame_early_returns_and_noop_never_reuse_old_buildings(
    tmp_path, monkeypatch, plant
):
    from eii_custodian.publicdata.frame.checks import FrameError
    from eii_custodian.publicdata.places.integrate import frame_when_ready

    prepared = world(tmp_path)
    prepared.produce()
    review = prepared.cache.parent.parent / "custodian/publicdata/review"
    review.mkdir(parents=True)
    (review / "showcase_gazetteer.yaml").write_text("[]")
    entries = prepared.entries
    if plant == "boundary":
        entries = tuple(row for row in entries if row.key != "bnd_hdx")
    elif plant == "review":
        (review / "showcase_gazetteer.yaml").unlink()
    else:

        def frame(*_args, **_kwargs):
            if plant == "frame_refusal":
                raise FrameError("SYN refused")
            return None

        monkeypatch.setattr("eii_custodian.publicdata.frame.build.build_frame", frame)
    if plant == "noop":
        from eii_custodian.publicdata.buildings import BuildingError

        with pytest.raises(BuildingError, match="building_frame_absent"):
            frame_when_ready(prepared.cache, entries, [])
    else:
        frame_when_ready(prepared.cache, entries, [])
    assert not (prepared.output / "buildings.geojson").exists()
    assert not (prepared.output / "manifest.buildings.json").exists()
