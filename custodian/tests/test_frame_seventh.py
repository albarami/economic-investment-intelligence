"""Seventh-pass regressions, using only invented records and points."""

from decimal import ROUND_UP, Decimal, localcontext

import pytest

import h3
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame import grid
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.gazetteer import make_row
from eii_custodian.publicdata.frame.mapping import inspect_source
from eii_custodian.publicdata.review.cache_fixture import select_fixture


def test_stored_point_owns_cell():
    raw = (0.00009805126222314894, -0.0003110495176352933)
    cells = frozenset(h3.str_to_int(c) for c in ("89754e64997ffff", "89754e64993ffff"))
    assert grid.point_cell(*raw, cells) == h3.str_to_int("89754e64997ffff")
    row = make_row(
        "SYN-P", "landmark", "Invented", "تجريبي", None, *raw, "places_ovt", cells
    )
    assert row["lon"] == Decimal("0.000098")
    assert row["lat"] == Decimal("-0.000311")
    assert row["cell"] == h3.str_to_int("89754e64993ffff")
    assert grid.point_cell(float(row["lon"]), float(row["lat"]), cells) == row["cell"]


def test_rounding_is_explicit_half_even():
    with localcontext() as context:
        context.rounding = ROUND_UP
        row = make_row(
            "SYN-P",
            "district",
            "Invented",
            "تجريبي",
            None,
            0.1234565,
            -0.1234575,
            "bnd_hdx",
            frozenset(),
        )
    assert row["lon"] == Decimal("0.123456")
    assert row["lat"] == Decimal("-0.123458")
    assert row["lon"].as_tuple().exponent == -6


def test_ownership_index_reads_grid_once():
    class CountingRows(list):
        reads = 0

        def __iter__(self):
            self.reads += 1
            return super().__iter__()

    rows = CountingRows([{"cell": h3.str_to_int("89754e64993ffff")}])
    stored = grid.ownership_index(rows)
    for _ in range(50):
        assert grid.point_cell(0, 0, stored) == h3.str_to_int("89754e64993ffff")
    assert rows.reads == 1


def population(indicator, name="Invented A"):
    return {
        "year": "2020",
        "municipality": name,
        "lbldy": name,
        "indicator": indicator,
        "lmw_shr": "تجريبي",
        "count": 17,
    }


def test_population_review_filters_and_keeps_own_key(tmp_path):
    from eii_custodian.publicdata.frame.population import population_rows

    (tmp_path / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nInvented omitted,\nInvented people,residents\n"
    )
    names = [
        {"name": "Invented A", "municipality_code": "SYN-A"},
        {"name": "Invented B", "municipality_code": "SYN-B"},
    ]
    rows, report = population_rows(
        [
            population("Invented omitted"),
            population("Invented people", "Invented B"),
            population("Invented omitted"),
        ],
        tmp_path,
        names,
        None,
    )
    assert rows == [
        {
            "municipality_code": "SYN-B",
            "period": "2020",
            "indicator": "residents",
            "value": 17,
            "unit": "persons",
        }
    ]
    assert report == "pop_muni: 2 rows not loaded: Invented omitted"


@pytest.mark.parametrize(
    "review,reason",
    [
        ("Invented people,unknown", "invalid_indicator"),
        ("Invented people,residents\nInvented people,residents", "duplicate_indicator"),
    ],
)
def test_population_review_refusals(tmp_path, review, reason):
    from eii_custodian.publicdata.frame.population import load_indicators

    (tmp_path / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\n" + review + "\n"
    )
    with pytest.raises(FrameError, match=reason):
        load_indicators(tmp_path)


def test_population_unlisted_refuses_all_rows():
    inspected = inspect_source(
        "pop_muni",
        [population("Invented people"), population("Invented unknown")],
        {"Invented people": "residents"},
    )
    assert inspected.rows == []
    assert inspected.reason == "unreviewed_indicator: Invented unknown"


def test_population_key_length_refuses(tmp_path, monkeypatch):
    from eii_custodian.publicdata.frame import population as module

    (tmp_path / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nInvented people,residents\n"
    )
    monkeypatch.setattr(module, "municipality_keys", lambda *args: [])
    with pytest.raises(FrameError, match="municipality_key_length_mismatch"):
        module.population_rows([population("Invented people")], tmp_path, [], None)


def establishments():
    return [
        {
            "economic_activity": name,
            "economic_activity_ar": "تجريبي",
            "census_2020": now,
            "census_2010_2010": old,
            "percent_census_2020": Decimal("1.5"),
            "percent_census_2010": Decimal("2.5"),
            "percent_change": Decimal("-1.5"),
        }
        for name, now, old in [
            ("Invented A", 2, 1),
            ("Invented B", 3, 4),
            ("Invented C", 7, 2),
        ]
    ]


def test_establishment_sums():
    result = inspect_source("est_census", establishments())
    assert result.rows == [
        {
            "period": "2020",
            "indicator": "establishments",
            "unit": "establishments",
            "value": 12,
        },
        {
            "period": "2010",
            "indicator": "establishments",
            "unit": "establishments",
            "value": 7,
        },
    ]
    assert result.inventory == {}


@pytest.mark.parametrize(
    "case,reason",
    [
        ("empty", "empty_records"),
        ("unknown", "unknown fields"),
        ("missing", "missing fields"),
        ("boolean", "census_2020"),
        ("decimal_count", "census_2010_2010"),
        ("name_type", "economic_activity_ar"),
        ("percent_type", "percent_change"),
        ("negative", "negative_count"),
        ("duplicate", "duplicate_activity"),
    ],
)
def test_establishment_refusals(case, reason):
    rows = establishments()
    if case == "empty":
        rows = []
    elif case == "unknown":
        rows[0]["unknown"] = 1
    elif case == "missing":
        del rows[0]["percent_census_2010"]
    elif case == "duplicate":
        rows[1]["economic_activity"] = rows[0]["economic_activity"]
    else:
        field, value = {
            "boolean": ("census_2020", True),
            "decimal_count": ("census_2010_2010", 1.5),
            "name_type": ("economic_activity_ar", 1),
            "percent_type": ("percent_change", "1.5"),
            "negative": ("census_2010_2010", -1),
        }[case]
        rows[0][field] = value
    with pytest.raises(FrameError, match=reason):
        inspect_source("est_census", rows)


@pytest.mark.parametrize(
    "case,reason",
    [
        ("unlisted", "util_elec: unlisted zone"),
        ("duplicate", "duplicate zone code"),
        ("missing", "frame zone not matched"),
        ("unknown", "matched zone outside frame"),
    ],
)
def test_zone_checks(case, reason):
    from eii_custodian.publicdata.frame.crosswalk import check_zones

    rows = [{"zone_code": "SYN-Z", "util_elec": "SYN-Z", "status": "matched"}]
    observed = {"util_elec": {"SYN-Z"}}
    if case == "unlisted":
        observed["util_elec"].add("SYN-OTHER")
    elif case == "duplicate":
        rows += rows
    elif case == "missing":
        rows[0]["status"] = "absent_in_source"
    else:
        rows.append({"zone_code": "SYN-OTHER", "util_elec": "", "status": "matched"})
    with pytest.raises(FrameError, match=reason):
        check_zones(rows, observed, {"SYN-Z"})


@pytest.fixture
def seventh_build(tmp_path):
    import json

    from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer
    from custodian.tests.test_frame_census import entry

    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame.build import build_frame

    review = tmp_path / "review"
    review.mkdir()
    arabic = "اسم تجريبي"
    for name, content in {
        "municipality_names.csv": f"name,municipality_code\nInvented municipality,9\nDifferent invented spelling,9\n{arabic},9\n",
        "greater_doha_municipalities.csv": "name\nInvented municipality\n",
        "population_indicators.csv": "indicator,mapped_indicator\nInvented omitted,\nInvented people,residents\n",
        "zone_crosswalk.csv": "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,status\n42,42,42,42,matched\n",
        "district_layer_aliases.csv": "zone_code,layer_name,hdx_name\n",
        "zones_without_districts.csv": "zone_code,reason\n",
        "showcase_gazetteer.yaml": "[]",
        "flagship_candidates.yaml": "[]",
    }.items():
        (review / name).write_text(content)
    source_names = (
        "bnd_hdx",
        "bnd_zone_2020",
        "bnd_district_2020",
        "est_census",
        "pop_muni",
    )
    entries = tuple(entry(name) for name in source_names)
    cache = tmp_path / "cache"
    for source in entries:
        name = source.source_id
        if name == "bnd_hdx":
            body = invented_archive()
        else:
            if name == "est_census":
                payload = establishments()
                for row in payload:
                    for key in (
                        "percent_census_2020",
                        "percent_census_2010",
                        "percent_change",
                    ):
                        row[key] = float(row[key])
            elif name == "pop_muni":
                payload = [
                    population("Invented omitted", "Invented municipality"),
                    population("Invented people", "Invented municipality"),
                ]
                for row in payload:
                    row["lbldy"] = "اسم تجريبي"
            else:
                payload = invented_layer(name)
            body = json.dumps(payload).encode()
        digest = sha256_hex(body)
        receipt = sidecar_for(
            source,
            digest=digest,
            nbytes=len(body),
            fetch_url=source.url,
            fetch_host=source.fetch_host,
            retrieved_utc="2026-11-14T00:00:00Z",
            publisher=source.publisher,
            source_modified="",
            row_count=None,
            terms_sha256="",
        )
        commit_pair(cache / source.key, digest, source.extension, body, receipt)
        select_fixture(cache, str(receipt["key"]), digest)

    def _run():
        return build_frame(cache, entries, review, tmp_path / "output")

    _run.cache = cache
    _run.review = review
    _run.entries = entries
    return _run


def test_filled_place_point_enters_the_live_gazetteer(seventh_build, tmp_path):
    """A filled spec resolves through the places output of build_live_frame."""
    import json

    from eii_custodian.publicdata.frame.build import inspect_cache
    from eii_custodian.publicdata.frame.live import build_live_frame

    cache = seventh_build.cache
    review = seventh_build.review
    point_dir = cache / "places_s2_t06"
    point_dir.mkdir()
    (point_dir / "place_points.json").write_text(
        json.dumps(
            [
                {
                    "source_id": "places_ovt",
                    "record_key": "SYN-R",
                    "lon": "0.020000",
                    "lat": "0.020000",
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (review / "showcase_gazetteer.yaml").write_text(
        json.dumps(
            [
                {
                    "place_key": "SYN-LAND",
                    "kind": "landmark",
                    "name_en": "SYN Invented",
                    "name_ar": "اسم تجريبي",
                    "aliases": None,
                    "source_id": "places_ovt",
                    "record_key": "SYN-R",
                    "arabic_review": "pending native review",
                }
            ]
        ),
        encoding="utf-8",
    )
    inspected = inspect_cache(
        cache, seventh_build.entries, review, reviewed_selections(cache)
    )
    result = build_live_frame(
        cache,
        seventh_build.entries,
        review,
        tmp_path / "gazetteer-out",
        inspected,
        reviewed_selections(cache),
    )
    assert any(row["place_key"] == "SYN-LAND" for row in result.tables["gazetteer"])


def test_seventh_live_build(seventh_build):
    from eii_custodian.publicdata.frame.grid import ownership_index, point_cell

    result = seventh_build()
    assert result.tables["pub_census_national"] == [
        {
            "period": "2020",
            "indicator": "establishments",
            "unit": "establishments",
            "value": Decimal(12),
            "source_id": "est_census",
        },
        {
            "period": "2010",
            "indicator": "establishments",
            "unit": "establishments",
            "value": Decimal(7),
            "source_id": "est_census",
        },
    ]
    assert (
        result.sources["est_census"]["method"]
        == "frame.v1: sum count columns over source activity rows"
    )
    assert result.sources["est_census"]["retrieved_utc"] == "2026-11-14T00:00:00Z"
    assert result.report.count("pop_muni: 1 rows not loaded: Invented omitted") == 1
    assert not any("unlisted zone numbers" in line for line in result.report)
    stored = ownership_index(result.tables["grid_cell"])
    for row in result.tables["gazetteer"]:
        assert row["lon"].as_tuple().exponent == -6
        assert row["lat"].as_tuple().exponent == -6
        if row["cell"] is not None:
            assert (
                point_cell(float(row["lon"]), float(row["lat"]), stored) == row["cell"]
            )


@pytest.mark.parametrize(
    "case,reason",
    [
        ("unlisted", "bnd_zone_2020: unlisted zone"),
        ("duplicate", "duplicate zone code"),
        ("missing", "frame zone not matched"),
        ("unknown", "matched zone outside frame"),
    ],
)
def test_live_zone_plants(seventh_build, tmp_path, case, reason):
    path = tmp_path / "review" / "zone_crosswalk.csv"
    text = path.read_text()
    if case == "unlisted":
        text = text.replace("42,42,42,42,matched", "42,42,,42,matched")
    elif case == "duplicate":
        text += "42,42,42,42,matched\n"
    elif case == "missing":
        text = text.replace("matched", "absent_in_source")
    else:
        text += "43,,,,matched\n"
    path.write_text(text)
    with pytest.raises(FrameError, match=reason):
        seventh_build()
    assert (tmp_path / "output" / "proposed_zone_crosswalk.csv").exists()


def test_required_establishment_cache_missing(tmp_path):
    from custodian.tests.test_frame_census import entry

    from eii_custodian.publicdata.frame.build import build_frame

    with pytest.raises(FrameError, match="snapshot_path_invalid"):
        build_frame(tmp_path / "cache", (entry("est_census"),), tmp_path / "review")


def test_establishment_registry_fields():
    from eii_custodian.publicdata.fetch.registry import load_registry

    source = next(e for e in load_registry() if e.source_id == "est_census")
    assert source.skip_reason == ""
    assert dict(source.columns) == {
        "economic_activity": "string",
        "economic_activity_ar": "string",
        "census_2020": "integer",
        "percent_census_2020": "number",
        "census_2010_2010": "integer",
        "percent_census_2010": "number",
        "percent_change": "number",
    }


@pytest.mark.parametrize("field", ["census_2020", "census_2010_2010"])
@pytest.mark.parametrize("bad", [True, False, -1, 1.5, "2", None])
def test_each_establishment_count_checked(field, bad):
    rows = establishments()
    rows[0][field] = bad
    with pytest.raises(FrameError):
        inspect_source("est_census", rows)


@pytest.mark.parametrize("field", list(establishments()[0]))
def test_each_establishment_field_required(field):
    rows = establishments()
    del rows[0][field]
    with pytest.raises(FrameError, match="missing fields"):
        inspect_source("est_census", rows)


@pytest.mark.parametrize(
    "field",
    [
        "economic_activity",
        "economic_activity_ar",
        "percent_census_2020",
        "percent_census_2010",
        "percent_change",
    ],
)
def test_each_establishment_shape_type_checked(field):
    rows = establishments()
    rows[0][field] = True
    with pytest.raises(FrameError, match=field):
        inspect_source("est_census", rows)


@pytest.mark.parametrize("payload", [{}, [None]])
def test_establishment_container_shapes(payload):
    with pytest.raises(FrameError, match=r"expected list|expected object"):
        inspect_source("est_census", payload)


def test_establishment_zero_and_number_percentages():
    rows = establishments()
    rows[0].update(
        census_2020=0,
        census_2010_2010=0,
        percent_census_2020=0,
        percent_census_2010=1.5,
    )
    result = inspect_source("est_census", rows)
    assert [row["value"] for row in result.rows] == [10, 6]


def test_population_filtered_key_length_refuses(tmp_path, monkeypatch):
    from eii_custodian.publicdata.frame import population as module
    from eii_custodian.publicdata.frame.mapping import Inspection

    (tmp_path / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nInvented people,residents\n"
    )
    monkeypatch.setattr(module, "inspect_source", lambda *args: Inspection([], {}, ""))
    names = [{"name": "Invented A", "municipality_code": "SYN-A"}]
    with pytest.raises(FrameError, match="municipality_key_length_mismatch"):
        module.population_rows([population("Invented people")], tmp_path, names, None)


def test_observed_zone_fields_are_shared_and_complete():
    from eii_custodian.publicdata.frame.crosswalk import observed_zones

    inventory = {
        name: {field: ("SYN-Z",)}
        for name, field in [
            ("util_elec", "zone_number"),
            ("census_zone_hh", "ZONE_NO"),
            ("bnd_district_2020", "KEY_NO"),
            ("census_district_pop", "ZONENO"),
            ("bnd_hdx", "zone_code"),
        ]
    }
    inventory["pop_muni"] = {"indicator": ("Invented",)}
    assert observed_zones(inventory) == {
        "util_elec": {"SYN-Z"},
        "census_zone_hh": {"SYN-Z"},
        "bnd_district_2020": {"SYN-Z"},
        "census_district_pop": {"SYN-Z"},
        "bnd_hdx": {"SYN-Z"},
    }


@pytest.mark.parametrize(
    "token,unit",
    [
        ("residents", "persons"),
        ("households", "households"),
        ("establishments", "establishments"),
        ("employees", "persons"),
    ],
)
def test_population_each_reviewed_token_and_unit(tmp_path, token, unit):
    from eii_custodian.publicdata.frame.population import population_rows

    (tmp_path / "population_indicators.csv").write_text(
        f"indicator,mapped_indicator\nInvented count,{token}\n"
    )
    names = [{"name": "Invented A", "municipality_code": "SYN-A"}]
    rows, report = population_rows(
        [population("Invented count")], tmp_path, names, None
    )
    assert rows == [
        {
            "municipality_code": "SYN-A",
            "period": "2020",
            "indicator": token,
            "value": 17,
            "unit": unit,
        }
    ]
    assert report == ""


def test_population_unlisted_in_assembler(tmp_path):
    from eii_custodian.publicdata.frame.population import population_rows

    (tmp_path / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nInvented people,residents\n"
    )
    names = [{"name": "Invented A", "municipality_code": "SYN-A"}]
    rows, report = population_rows(
        [population("Invented people"), population("Invented unknown")],
        tmp_path,
        names,
        None,
    )
    assert rows == []
    assert report == "unreviewed_indicator: Invented unknown"


def test_k1_live_unlisted_indicator_refuses_after_proposal(
    seventh_build, tmp_path, monkeypatch
):
    import json

    from custodian.tests.test_frame_census import entry

    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame import build as build_module

    source = entry("pop_muni")
    folder = tmp_path / "cache" / source.key
    payload = [
        {**population(name, "Invented municipality"), "lbldy": "اسم تجريبي"}
        for name in ("Invented omitted", "Invented people", "Invented unlisted")
    ]
    body = json.dumps(payload).encode()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        source,
        digest=digest,
        nbytes=len(body),
        fetch_url=source.url,
        fetch_host=source.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=source.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(folder, digest, source.extension, body, receipt)
    select_fixture(tmp_path / "cache", str(receipt["key"]), digest)

    captured = []
    original_inspect = build_module.inspect_cache

    def record_inspect(*args, **kwargs):
        inspected = original_inspect(*args, **kwargs)
        captured.append(inspected)
        return inspected

    monkeypatch.setattr(build_module, "inspect_cache", record_inspect)
    with pytest.raises(
        FrameError,
        match=r"^pop_muni: unreviewed_indicator: Invented unlisted$",
    ):
        seventh_build()
    assert len(captured) == 1
    assert all(rows == [] for rows in captured[0].tables.values())
    assert (tmp_path / "output" / "proposed_population_indicators.csv").read_text() == (
        "indicator,mapped_indicator\n"
        "Invented omitted,\n"
        "Invented people,\n"
        "Invented unlisted,\n"
    )


def test_k1_live_listed_mapped_and_blank_indicators_pass(seventh_build):
    result = seventh_build()
    assert result.tables["pub_population_municipality"] == [
        {
            "municipality_code": "9",
            "period": "2020",
            "indicator": "residents",
            "value": Decimal(17),
            "unit": "persons",
            "source_id": "pop_muni",
        }
    ]
    assert result.report.count("pop_muni: 1 rows not loaded: Invented omitted") == 1


def assert_population_indicators_pinned(review_dir):
    from eii_custodian.publicdata.frame.crosswalk import read_csv
    from eii_custodian.publicdata.frame.population import load_indicators

    rows = read_csv(review_dir / "population_indicators.csv")
    indicators = load_indicators(review_dir)
    tokens = [row["mapped_indicator"] for row in rows if row["mapped_indicator"]]
    assert len(tokens) == 1, f"expected one mapped indicator, got {len(tokens)}"
    assert tokens == ["residents"]
    assert "Employed" in indicators
    assert indicators["Employed"] == ""


def committed_review_dir():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "publicdata" / "review"


def test_k2_committed_population_indicators_pinned():
    assert_population_indicators_pinned(committed_review_dir())


@pytest.mark.parametrize("mode", ["add_employed_token", "move_residents_to_employed"])
def test_k2_population_indicators_pin_refuses_employed_token(tmp_path, mode):
    committed = (committed_review_dir() / "population_indicators.csv").read_text(
        encoding="utf-8"
    )
    if mode == "add_employed_token":
        tampered = committed.replace("\nEmployed,\n", "\nEmployed,employees\n")
    else:
        tampered = committed.replace(
            "\nPopulation,residents\n", "\nPopulation,\n"
        ).replace("\nEmployed,\n", "\nEmployed,residents\n")
    (tmp_path / "population_indicators.csv").write_text(tampered, encoding="utf-8")
    with pytest.raises(AssertionError):
        assert_population_indicators_pinned(tmp_path)


def test_live_frame_retains_reviewed_older_snapshot(seventh_build):
    from eii_custodian.publicdata.fetch.snapshots import (
        read_snapshot,
        reviewed_selections,
    )
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    cache = seventh_build.cache
    entry = next(row for row in seventh_build.entries if row.key == "bnd_hdx")
    older = read_snapshot(cache / entry.key, reviewed_selections(cache)[entry.key])
    write_cached(cache, entry, b"syn-newer-invalid-archive", select=False)
    result = seventh_build()
    assert result.sources[entry.source_id]["sha256"] == older.sha256
    older.path.write_bytes(b"syn-tamper")
    with pytest.raises(FrameError, match="snapshot_hash_mismatch"):
        seventh_build()
