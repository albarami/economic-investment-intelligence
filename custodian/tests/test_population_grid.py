"""Invented native-cell WorldPop layouts; no publisher cell values."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest
from custodian.tests.fixtures.grids.invented import (
    entry,
    population_file,
    store,
)

from eii_custodian.publicdata.fetch.registry import (
    RegistryError,
    load_registry,
    registry_path,
)
from eii_custodian.publicdata.grids.build import build_grids
from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.population import (
    PopulationSpec,
    read_population,
    spec_from_entry,
)


def spec():
    return PopulationSpec(
        "SYN-release",
        "2025",
        "25",
        "f",
        "people_per_cell",
        "SYN-doi",
        True,
        ("sex",),
    )


def test_worldpop_native_cell(tmp_path):
    rows = read_population(
        tmp_path, population_file(tmp_path / "qat_f_25_2025_SYN.tif"), spec()
    )
    assert len(rows) == 1
    assert rows[0]["grid_key"] == "wa_0_0"
    assert rows[0]["people"] == Decimal("10.4000")
    assert rows[0]["age_band"] == "25"
    assert rows[0]["sex"] == "female"
    assert rows[0]["period"] == "2025"
    assert rows[0]["source_id"] == "worldpop_qat_agesex"
    assert rows[0]["lon"] == Decimal("0.000417")
    assert rows[0]["lat"] == Decimal("0.999583")


@pytest.mark.parametrize(
    "change",
    [
        {"units": "unconfirmed"},
        {"units": "density"},
        {"doi_confirmed": False},
        {"doi": ""},
        {"public_splits": ()},
        {"public_splits": ("age_band", "sex")},
        {"public_splits": ("sex", "age_band")},
        {"public_splits": ("worker", "sex")},
        {"sex_code": "t"},
        {"age_code": "T_F"},
        {"year": "2024"},
    ],
)
def test_worldpop_unconfirmed_and_duplicate_categories(tmp_path, change):
    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    with pytest.raises(GridError, match="worldpop_qat_agesex"):
        read_population(tmp_path, path, replace(spec(), **change))


@pytest.mark.parametrize(
    "path",
    [
        "https://example.invalid/file",
        "file:///tmp/file",
        "/vsicurl/file",
        "/vsizip/file",
    ],
)
def test_worldpop_remote_before_library(tmp_path, monkeypatch, path):
    monkeypatch.setattr(
        "eii_custodian.publicdata.grids.population.import_module",
        lambda _: pytest.fail("library called"),
    )
    with pytest.raises(GridError, match="remote or virtual"):
        read_population(tmp_path, path, spec())


def test_worldpop_symlink_escape(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    link = cache / path.name
    link.symlink_to(path)
    monkeypatch.setattr(
        "eii_custodian.publicdata.grids.population.import_module",
        lambda _: pytest.fail("library called"),
    )
    with pytest.raises(GridError, match="outside cache"):
        read_population(cache, link, spec())


@pytest.mark.parametrize("value", [-1, float("nan")])
def test_worldpop_invalid_population(tmp_path, value):
    import numpy as np
    import rasterio

    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    with rasterio.open(path, "r+") as target:
        target.write(np.array([[value, -99999]], dtype="float32"), 1)
    with pytest.raises(GridError, match="invalid population"):
        read_population(tmp_path, path, spec())


@pytest.mark.parametrize("change", ["crs", "nodata"])
def test_worldpop_schema(tmp_path, change):
    import rasterio

    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    with rasterio.open(path, "r+") as target:
        if change == "crs":
            target.crs = "EPSG:3857"
        if change == "nodata":
            target.nodata = -1
    with pytest.raises(GridError, match="mismatch"):
        read_population(tmp_path, path, spec())


def _population_row():
    return entry(
        "worldpop_qat_agesex",
        "worldpop_qat_agesex/2025/f/25",
        sex="f",
        age_code="25",
        release="SYN-release",
        year="2025",
        period_first="2025",
        period_last="2025",
        cell_units="people_per_cell",
        doi="SYN-doi",
        doi_confirmed=True,
        public_splits=("sex",),
        url="https://data.worldpop.org/SYN/qat_f_25_2025_SYN.tif",
        release_tables=("pub_pop_agesex_grid",),
        caveat_keys=("grid_cells_summed",),
    )


def test_worldpop_table_from_registry_entry(tmp_path):
    row = _population_row()
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    digest = store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {})
    rows = result.tables["pub_pop_agesex_grid"]
    assert len(rows) == 1
    assert rows[0]["grid_key"] == "wa_0_0"
    assert rows[0]["people"] == Decimal("10.4000")
    assert rows[0]["age_band"] == "25"
    assert rows[0]["sex"] == "female"
    assert rows[0]["period"] == "2025"
    assert rows[0]["source_key"] == row.key
    assert rows[0]["source_sha256"] == digest
    assert rows[0]["method"] == "C38"
    assert rows[0]["method_version"] == "MTH-111"
    assert rows[0]["provenance"] == "Public"
    assert rows[0]["evidence_status"] == "Observed"
    assert rows[0]["caveat_keys"] == ["grid_cells_summed"]
    lineage = result.sources[row.key]
    assert lineage["doi"] == "SYN-doi"
    assert lineage["doi_confirmed"] is True
    assert lineage["method"] == "C38"
    assert lineage["method_version"] == "MTH-111"
    manifest = json.loads((tmp_path / "grids" / "manifest.json").read_text("utf-8"))
    assert manifest["files"][0]["sha256"] == digest
    assert manifest["files"][0]["sex"] == "f"
    assert manifest["files"][0]["age_code"] == "25"
    assert manifest["files"][0]["release"] == "SYN-release"
    assert manifest["files"][0]["cell_units"] == "people_per_cell"
    assert manifest["files"][0]["doi_confirmed"] is True
    assert manifest["tables"]["pub_pop_agesex_grid"] == 1
    chain = result.tables["fact_lineage"]
    assert [item["table"] for item in chain] == ["pub_pop_agesex_grid"]
    assert chain[0]["source_key"] == row.key
    assert chain[0]["source_sha256"] == digest
    assert chain[0]["method"] == "C38"
    assert chain[0]["method_version"] == "MTH-111"
    assert chain[0]["licence_id"] == "CC-BY-4.0"
    assert chain[0]["licence_url"] == ""
    assert chain[0]["dataset"] == row.url
    assert chain[0]["release"] == "SYN-release"
    assert chain[0]["period"] == "2025"
    assert chain[0]["period_first"] == "2025"
    assert chain[0]["period_last"] == "2025"
    assert chain[0]["caveat_keys"] == ["grid_cells_summed"]


def test_worldpop_manifest_lists_every_file(tmp_path):
    first = _population_row()
    second = replace(first, key="worldpop_qat_agesex/2025/m/25", sex="m")
    second = replace(second, url="https://data.worldpop.org/SYN/qat_m_25_2025_SYN.tif")
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    store(tmp_path, first, body)
    store(tmp_path, second, body)
    result = build_grids(tmp_path, (first, second), {})
    assert len(result.tables["pub_pop_agesex_grid"]) == 2
    manifest = json.loads((tmp_path / "grids" / "manifest.json").read_text("utf-8"))
    assert [item["key"] for item in manifest["files"]] == [first.key, second.key]
    assert {item["sex"] for item in manifest["files"]} == {"f", "m"}
    assert [item["source_key"] for item in result.tables["source_registry"]] == [
        first.key,
        second.key,
    ]


def test_worldpop_two_files_keep_their_own_hashes(tmp_path):
    import numpy as np
    import rasterio

    first = _population_row()
    second = replace(first, key="worldpop_qat_agesex/2025/m/25", sex="m")
    second = replace(second, url="https://data.worldpop.org/SYN/qat_m_25_2025_SYN.tif")
    first_body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    other = population_file(tmp_path / "qat_m_25_2025_SYN.tif")
    with rasterio.open(other, "r+") as target:
        target.write(np.array([[7.5, -99999]], dtype="float32"), 1)
    second_body = other.read_bytes()
    first_digest = store(tmp_path, first, first_body)
    second_digest = store(tmp_path, second, second_body)
    assert first_digest != second_digest
    result = build_grids(tmp_path, (first, second), {})
    manifest = json.loads((tmp_path / "grids" / "manifest.json").read_text("utf-8"))
    assert [item["sha256"] for item in manifest["files"]] == [
        first_digest,
        second_digest,
    ]
    rows = result.tables["pub_pop_agesex_grid"]
    assert [(item["source_key"], item["source_sha256"]) for item in rows] == [
        (first.key, first_digest),
        (second.key, second_digest),
    ]
    assert [item["source_sha256"] for item in result.tables["source_registry"]] == [
        first_digest,
        second_digest,
    ]


def test_worldpop_files_of_one_year_must_share_the_grid(tmp_path):
    import rasterio
    from rasterio.transform import from_origin

    first = _population_row()
    second = replace(first, key="worldpop_qat_agesex/2025/m/25", sex="m")
    second = replace(second, url="https://data.worldpop.org/SYN/qat_m_25_2025_SYN.tif")
    first_body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    other = population_file(tmp_path / "qat_m_25_2025_SYN.tif")
    with rasterio.open(other, "r+") as target:
        target.transform = from_origin(0, 1, 0.5, 0.5)
    store(tmp_path, first, first_body)
    store(tmp_path, second, other.read_bytes())
    with pytest.raises(GridError, match="grid agreement"):
        build_grids(tmp_path, (first, second), {})


def test_worldpop_real_registry_fails_closed(tmp_path):
    entries = load_registry()
    rows = [
        item
        for item in entries
        if item.source_id == "worldpop_qat_agesex" and "/" in item.key
    ]
    published = (
        "00",
        "01",
        "05",
        "10",
        "15",
        "20",
        "25",
        "30",
        "35",
        "40",
        "45",
        "50",
        "55",
        "60",
        "65",
        "70",
        "75",
        "80",
        "85",
        "90",
    )
    assert len(rows) == 40
    assert all(item.doi_confirmed is False for item in rows)
    assert all(item.cell_units == "unconfirmed" for item in rows)
    assert all(item.public_splits == ("sex",) for item in rows)
    assert all(item.release == "R2025A v1" for item in rows)
    assert {item.doi for item in rows} == {"10.5258/SOTON/WP00841"}
    assert {item.sex for item in rows} == {"f", "m"}
    assert {item.age_code for item in rows} == set(published)
    assert all(item.year == "2025" for item in rows)
    assert all(item.period_first == "2025" for item in rows)
    assert all(item.period_last == "2025" for item in rows)
    assert all("/v1/100m/constrained/" in item.url for item in rows)
    assert all(item.url.endswith("_R2025A_v1.tif") for item in rows)
    hand = (
        "https://data.worldpop.org/GIS/AgeSex_structures/Global_2015_2030/"
        "R2025A/2025/QAT/v1/100m/constrained/"
        "qat_f_25_2025_CN_100m_R2025A_v1.tif"
    )
    female = next(item for item in rows if item.key == "worldpop_qat_agesex/2025/f/25")
    assert female.url == hand
    assert female.age_code == "25"
    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    with pytest.raises(GridError, match="units or DOI unconfirmed"):
        read_population(tmp_path, path, spec_from_entry(rows[0]))


def test_worldpop_real_registry_build_reports_unconfirmed(tmp_path, capsys):
    entries = load_registry()
    row = next(item for item in entries if item.key == "worldpop_qat_agesex/2025/f/25")
    other = next(
        item for item in entries if item.key == "worldpop_qat_agesex/2025/m/25"
    )
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    store(tmp_path, row, body)
    store(tmp_path, other, body)
    result = build_grids(tmp_path, entries, {})
    printed = capsys.readouterr().out
    assert result.tables["pub_pop_agesex_grid"] == []
    assert result.coverage["worldpop_qat_agesex"] == "units or DOI unconfirmed"
    assert printed.count("worldpop_qat_agesex: units or DOI unconfirmed") == 1
    with pytest.raises(GridError, match="units or DOI unconfirmed"):
        read_population(
            tmp_path, tmp_path / "qat_f_25_2025_SYN.tif", spec_from_entry(row)
        )


def test_worldpop_real_registry_empty_cache_is_no_cache(tmp_path):
    entries = load_registry()
    result = build_grids(tmp_path, entries, {})
    keyed = [
        item
        for item in entries
        if item.source_id
        in {"ntl_blackmarble", "worldpop_qat_agesex", "weather_openmeteo"}
        and "/" in item.key
    ]
    assert keyed
    for item in keyed:
        assert result.coverage[f"{item.key}:omitted"] == "NO_CACHE"
    assert result.tables["pub_pop_agesex_grid"] == []
    assert result.tables["pub_night_lights"] == []


def _mutated(tmp_path, name, mutate):
    import yaml

    document = yaml.safe_load(registry_path().read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    mutate(document)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _file_row(document, key):
    rows = document["sources"]
    assert isinstance(rows, list)
    for row in rows:
        if isinstance(row, dict) and row.get("key") == key:
            return row
    raise AssertionError(key)


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"sex": "t"}, "sex is not a recorded value"),
        ({"age_code": "T_F"}, "age_code is not a decimal code"),
        ({"cell_units": "people"}, "cell_units is not a recorded value"),
        ({"year": "25"}, "year is not in the recorded form"),
        ({"doi": ""}, "doi is empty"),
        ({"doi_confirmed": "no"}, "doi_confirmed is not a boolean"),
        ({"release": ""}, "release is empty"),
    ],
)
def test_worldpop_registry_refuses_a_bad_file_value(tmp_path, change, reason):
    def mutate(document):
        _file_row(document, "worldpop_qat_agesex/2025/f/25").update(change)

    with pytest.raises(RegistryError, match=reason):
        load_registry(_mutated(tmp_path, "bad.yaml", mutate))


def test_worldpop_registry_refuses_incomplete_and_misplaced_metadata(tmp_path):
    def incomplete(document):
        _file_row(document, "worldpop_qat_agesex/2025/f/25").pop("doi_confirmed")

    with pytest.raises(RegistryError, match="incomplete file metadata"):
        load_registry(_mutated(tmp_path, "incomplete.yaml", incomplete))

    def misplaced(document):
        _file_row(document, "worldpop_qat_agesex/2025/f/25")["period"] = "2025-01"

    with pytest.raises(RegistryError, match="does not use it"):
        load_registry(_mutated(tmp_path, "misplaced.yaml", misplaced))

    def other_source(document):
        _file_row(document, "lic_active")["sex"] = "f"

    with pytest.raises(RegistryError, match="does not use it"):
        load_registry(_mutated(tmp_path, "other.yaml", other_source))


def test_worldpop_loader_admits_without_a_coverage_rule(tmp_path):
    """The loader no longer refuses a year for a missing file."""

    def lost(document):
        rows = document["sources"]
        assert isinstance(rows, list)
        rows.remove(_file_row(document, "worldpop_qat_agesex/2025/f/25"))

    admitted = load_registry(_mutated(tmp_path, "lost.yaml", lost))
    assert any(item.key == "worldpop_qat_agesex/2025/m/25" for item in admitted)


def test_worldpop_build_checks_one_row_per_sex_and_code(tmp_path):
    """One year is one row per sex and code, with no both-sexes or total file."""
    both = replace(
        _population_row(),
        url="https://data.worldpop.org/SYN/qat_t_25_2025_SYN.tif",
    )
    with pytest.raises(GridError, match="both-sexes or total"):
        build_grids(tmp_path, (both,), {})
    total = replace(
        _population_row(),
        url="https://data.worldpop.org/SYN/qat_T_F_2025_SYN.tif",
    )
    with pytest.raises(GridError, match="both-sexes or total"):
        build_grids(tmp_path, (total,), {})
    uneven = replace(
        _population_row(),
        key="worldpop_qat_agesex/2025/m/30",
        sex="m",
        age_code="30",
        url="https://data.worldpop.org/SYN/qat_m_30_2025_SYN.tif",
    )
    with pytest.raises(GridError, match="one row per sex and code"):
        build_grids(tmp_path, (_population_row(), uneven), {})
    twin = replace(_population_row(), key="worldpop_qat_agesex/2025/f/25-twin")
    with pytest.raises(GridError, match="repeated sex and age code"):
        build_grids(tmp_path, (_population_row(), twin), {})


def test_worldpop_registry_refuses_a_bad_weather_metadata(tmp_path):
    def point(document):
        _file_row(document, "weather_openmeteo/2024-2025/point")["point"] = [1, 2, 3]

    with pytest.raises(RegistryError, match="point is not a pair of numbers"):
        load_registry(_mutated(tmp_path, "point.yaml", point))

    def variables(document):
        _file_row(document, "weather_openmeteo/2024-2025/point")["variables"] = ["SYN"]

    with pytest.raises(RegistryError, match="variables is not a recorded value"):
        load_registry(_mutated(tmp_path, "variables.yaml", variables))

    def repeated(document):
        row = _file_row(document, "weather_openmeteo/2024-2025/point")
        row["variables"] = ["temperature_2m", "temperature_2m"]

    with pytest.raises(RegistryError, match="variables repeats a name"):
        load_registry(_mutated(tmp_path, "repeated.yaml", repeated))

    def cache_role(document):
        row = _file_row(document, "weather_openmeteo/2024-2025/point")
        row["cache_role"] = "release_table"

    with pytest.raises(RegistryError, match="cache_role is not a recorded value"):
        load_registry(_mutated(tmp_path, "role.yaml", cache_role))

    def cache_role_elsewhere(document):
        _file_row(document, "worldpop_qat_agesex/2025/f/25")["cache_role"] = (
            "generator_input"
        )

    with pytest.raises(RegistryError, match="does not use it"):
        load_registry(_mutated(tmp_path, "elsewhere.yaml", cache_role_elsewhere))


def test_worldpop_refuses_a_wrong_band_type(tmp_path):
    """The population band must be the published 32-bit float."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    path = tmp_path / "qat_f_25_2025_SYN.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=2,
        height=1,
        count=1,
        dtype="int32",
        crs="EPSG:4326",
        transform=from_origin(0, 1, 1 / 1200, 1 / 1200),
        nodata=-99999,
    ) as target:
        target.write(np.array([[1, -99999]], dtype="int32"), 1)
    with pytest.raises(GridError, match="band type"):
        read_population(tmp_path, path, spec())
