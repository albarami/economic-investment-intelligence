"""Hand-written grid-build rows and refusals that kill surviving mutants."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from custodian.tests.fixtures.grids.invented import (
    entry,
    night_file,
    population_file,
    store,
)
from rasterio.transform import from_origin
from shapely.geometry import box

from eii_custodian.publicdata.grids.build import build_grids, cached_bytes
from eii_custodian.publicdata.grids.contracts import GridError

URL = "https://data.worldpop.org/SYN/qat_f_25_2025_SYN.tif"
KEY = "worldpop_qat_agesex/2025/f/25"
NIGHT_URL = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3/2024/"
RETRIEVED = "2026-11-14T00:00:00Z"
LICENCE = "https://syn.example/licence"


def _population(**overrides: object) -> object:
    fields: dict[str, object] = {
        "sex": "f",
        "age_code": "25",
        "release": "SYN-release",
        "year": "2025",
        "period": "",
        "period_first": "",
        "period_last": "",
        "cell_units": "people_per_cell",
        "doi": "SYN-doi",
        "doi_confirmed": True,
        "acknowledgement": "SYN-ack",
        "public_splits": ("sex",),
        "url": URL,
        "landing_url": "",
        "licence_url": LICENCE,
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "caveat_keys": ("grid_cells_summed",),
        "release_tables": ("pub_pop_agesex_grid",),
    }
    fields.update(overrides)
    return entry("worldpop_qat_agesex", KEY, **fields)


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _fact(digest: str) -> dict[str, Any]:
    return {
        "grid_key": "wa_0_0",
        "lon": Decimal("0.000417"),
        "lat": Decimal("0.999583"),
        "age_band": "25",
        "sex": "female",
        "people": Decimal("10.4000"),
        "period": "2025",
        "source_id": "worldpop_qat_agesex",
        "source_key": KEY,
        "source_sha256": digest,
        "method": "C38",
        "method_version": "MTH-111",
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": ["grid_cells_summed"],
    }


def _file_row(digest: str, nbytes: int, **overrides: object) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": KEY,
        "source_id": "worldpop_qat_agesex",
        "publisher": "SYN-publisher",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "retrieved_utc": RETRIEVED,
        "sha256": digest,
        "bytes": nbytes,
        "period": "2025",
        "period_first": "2025",
        "period_last": "2025",
        "tile": "",
        "sex": "f",
        "age_code": "25",
        "release": "SYN-release",
        "year": "2025",
        "cell_units": "people_per_cell",
        "doi": "SYN-doi",
        "doi_confirmed": True,
        "variables": [],
        "method": "C38",
        "method_version": "MTH-111",
    }
    row.update(overrides)
    return row


def _lineage(digest: str) -> dict[str, Any]:
    return {
        "table": "pub_pop_agesex_grid",
        "method": "C38",
        "method_version": "MTH-111",
        "source_key": KEY,
        "publisher": "SYN-publisher",
        "dataset": URL,
        "licence_id": "CC-BY-4.0",
        "licence_url": LICENCE,
        "retrieved_utc": RETRIEVED,
        "source_sha256": digest,
        "release": "SYN-release",
        "period": "2025",
        "period_first": "2025",
        "period_last": "2025",
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": ["grid_cells_summed"],
        "doi": "SYN-doi",
        "acknowledgement": "SYN-ack",
    }


def _registry(digest: str) -> dict[str, Any]:
    return {
        "source_key": KEY,
        "source_id": "worldpop_qat_agesex",
        "publisher": "SYN-publisher",
        "dataset": URL,
        "licence_id": "CC-BY-4.0",
        "licence_url": LICENCE,
        "retrieved_utc": RETRIEVED,
        "source_sha256": digest,
        "release": "SYN-release",
        "period": "2025",
        "period_first": "2025",
        "period_last": "2025",
        "method": "C38",
        "method_version": "MTH-111",
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": ["grid_cells_summed"],
    }


def _source(digest: str) -> dict[str, Any]:
    return {
        "source_id": "worldpop_qat_agesex",
        "source_key": KEY,
        "publisher": "SYN-publisher",
        "dataset": URL,
        "fetch_url": URL,
        "landing_url": "",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "licence_url": LICENCE,
        "retrieved_utc": RETRIEVED,
        "source_sha256": digest,
        "release": "SYN-release",
        "period": "2025",
        "period_first": "2025",
        "period_last": "2025",
        "doi": "SYN-doi",
        "doi_confirmed": True,
        "acknowledgement": "SYN-ack",
        "cell_units": "people_per_cell",
        "cache_role": "",
        "variables": [],
        "method": "C38",
        "method_version": "MTH-111",
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": ["grid_cells_summed"],
    }


def _manifest(digest: str, nbytes: int) -> dict[str, Any]:
    return {
        "method": {
            "ntl_blackmarble": "C36",
            "worldpop_qat_agesex": "C38",
            "weather_openmeteo": "weather.v1",
        },
        "method_version": {
            "ntl_blackmarble": "MTH-109",
            "worldpop_qat_agesex": "MTH-111",
            "weather_openmeteo": "weather.v1",
        },
        "files": [_file_row(digest, nbytes)],
        "tables": {
            "pub_night_lights": 0,
            "pub_pop_agesex_grid": 1,
            "fact_lineage": 1,
            "source_registry": 1,
        },
    }


def test_population_chain_rows_are_the_hand_written_record(tmp_path: Path) -> None:
    """Every source-chain row, and the sorted manifest text, is written by hand."""
    row = _population()
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    digest = _digest(body)
    store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {})
    expected = _manifest(digest, len(body))
    assert result.tables == {
        "pub_night_lights": [],
        "pub_pop_agesex_grid": [_fact(digest)],
        "fact_lineage": [_lineage(digest)],
        "source_registry": [_registry(digest)],
    }
    assert result.sources == {KEY: _source(digest)}
    assert result.manifest == expected
    assert result.coverage == {}
    text = (tmp_path / "grids" / "manifest.json").read_text(encoding="utf-8")
    assert text == json.dumps(expected, sort_keys=True, ensure_ascii=True) + "\n"


def test_one_receipt_is_required_by_name(tmp_path: Path) -> None:
    """Zero receipts and two receipts are the same named refusal."""
    row = _population()
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: expected one cache receipt"
    body = b"SYN-body"
    store(tmp_path, row, body)
    (tmp_path / KEY / "second.meta.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: expected one cache receipt"


def test_receipt_shape_and_fields_are_named(tmp_path: Path) -> None:
    """A list, a blank publisher and a switched-off source are named refusals."""
    row = _population()
    body = b"SYN-body"
    store(tmp_path, row, body)
    digest = _digest(body)
    meta = tmp_path / KEY / f"{digest}.meta.json"
    meta.write_text("[]\n", encoding="utf-8")
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: unreadable receipt"
    store(tmp_path, row, body)
    loaded = json.loads(meta.read_text(encoding="utf-8"))
    loaded["publisher"] = ""
    meta.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: missing receipt publisher"
    loaded["publisher"] = "SYN-publisher"
    loaded["switched_off"] = True
    meta.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: source switched off"


def test_hash_must_be_64_lower_hex_digits(tmp_path: Path) -> None:
    """A short digest and a digest of X are both a malformed hash."""
    row = _population()
    body = b"SYN-body"
    store(tmp_path, row, body)
    digest = _digest(body)
    meta = tmp_path / KEY / f"{digest}.meta.json"
    loaded = json.loads(meta.read_text(encoding="utf-8"))
    loaded["sha256"] = "ab" * 31 + "a"
    meta.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: malformed hash"
    loaded["sha256"] = "X" * 64
    meta.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(GridError) as caught:
        cached_bytes(tmp_path, row)
    assert str(caught.value) == "worldpop_qat_agesex: malformed hash"


def test_each_missing_citation_is_refused(tmp_path: Path) -> None:
    """A night-lights file with a DOI and no acknowledgement is refused by name."""
    row = entry(
        "ntl_blackmarble",
        "ntl_blackmarble/2024-01",
        period="2024-01",
        tile="h23v06",
        release="VNP46A3.002",
        doi="10.5067/VIIRS/VNP46A3.002",
        acknowledgement="",
        extension="h5",
        licence_id="NASA-guidance",
        url=NIGHT_URL,
        fetch_host="ladsweb.modaps.eosdis.nasa.gov",
        caveat_keys=("night_lights_not_activity",),
    )
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    store(tmp_path, row, body)
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (row,), {1: box(0, 0, 1, 1)})
    assert str(caught.value) == "ntl_blackmarble: DOI or acknowledgement missing"


def test_west_bound_is_the_minimum_longitude(tmp_path: Path) -> None:
    """A centre west of the southern edge stays inside a window that starts at longitude 0."""
    row = entry(
        "ntl_blackmarble",
        "ntl_blackmarble/2024-01",
        period="2024-01",
        tile="h23v06",
        release="VNP46A3.002",
        doi="10.5067/VIIRS/VNP46A3.002",
        acknowledgement="SYN-ack",
        extension="h5",
        licence_id="NASA-guidance",
        url=NIGHT_URL,
        fetch_host="ladsweb.modaps.eosdis.nasa.gov",
        caveat_keys=("night_lights_not_activity",),
    )
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {1: box(0, 0.4, 1, 1)})
    assert result.tables["pub_night_lights"] == [
        {
            "cell": 1,
            "period": "2024-01",
            "radiance": Decimal("4.0000"),
            "source_id": "ntl_blackmarble",
            "source_key": row.key,
            "source_sha256": _digest(body),
            "method": "C36",
            "method_version": "MTH-109",
            "provenance": "Public",
            "evidence_status": "Observed",
            "caveat_keys": ["night_lights_not_activity"],
        }
    ]
    assert result.manifest["files"][0]["bytes"] == len(body)


def test_a_cell_with_no_kept_pixel_is_no_data(tmp_path: Path) -> None:
    """Coverage for an empty cell is the text NO_DATA."""
    row = entry(
        "ntl_blackmarble",
        "ntl_blackmarble/2024-01",
        period="2024-01",
        tile="h23v06",
        release="VNP46A3.002",
        doi="10.5067/VIIRS/VNP46A3.002",
        acknowledgement="SYN-ack",
        extension="h5",
        licence_id="NASA-guidance",
        url=NIGHT_URL,
        fetch_host="ladsweb.modaps.eosdis.nasa.gov",
        caveat_keys=("night_lights_not_activity",),
    )
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    store(tmp_path, row, body)
    result = build_grids(
        tmp_path,
        (row,),
        {1: box(0, 0, 1, 1), 2: box(9, 9, 10, 10)},
    )
    assert result.coverage[f"{row.key}:2"] == "NO_DATA"


def test_unconfirmed_units_are_recorded_when_the_doi_is_confirmed(
    tmp_path: Path,
) -> None:
    """Wrong units are a coverage reason even when the DOI is confirmed."""
    row = _population(cell_units="density")
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {})
    assert result.coverage == {"worldpop_qat_agesex": "units or DOI unconfirmed"}
    assert result.tables["pub_pop_agesex_grid"] == []


def test_an_unconfirmed_file_does_not_drop_the_next(tmp_path: Path) -> None:
    """A file with unconfirmed units leaves the next confirmed file in the table."""
    female = _population(cell_units="density")
    male = replace(
        female,
        key="worldpop_qat_agesex/2025/m/25",
        sex="m",
        cell_units="people_per_cell",
        url="https://data.worldpop.org/SYN/qat_m_25_2025_SYN.tif",
    )
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    store(tmp_path, female, body)
    store(
        tmp_path, male, population_file(tmp_path / "qat_m_25_2025_SYN.tif").read_bytes()
    )
    result = build_grids(tmp_path, (female, male), {})
    assert [item["sex"] for item in result.tables["pub_pop_agesex_grid"]] == ["male"]
    assert result.coverage["worldpop_qat_agesex"] == "units or DOI unconfirmed"


def test_two_years_keep_separate_grids(tmp_path: Path) -> None:
    """Two years of one sex and code are built, each on its own grid."""
    first = _population()
    second = replace(
        first,
        key="worldpop_qat_agesex/2024/f/25",
        year="2024",
        url="https://data.worldpop.org/SYN/qat_f_25_2024_SYN.tif",
    )
    store(
        tmp_path,
        first,
        population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes(),
    )
    other = tmp_path / "qat_f_25_2024_SYN.tif"
    with rasterio.open(
        other,
        "w",
        driver="GTiff",
        width=1,
        height=1,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 1, 1, 1),
        nodata=-99999,
    ) as target:
        target.write(np.array([[3.0]], dtype="float32"), 1)
    store(tmp_path, second, other.read_bytes())
    result = build_grids(tmp_path, (first, second), {})
    assert [item["period"] for item in result.tables["pub_pop_agesex_grid"]] == [
        "2025",
        "2024",
    ]


def test_an_uncached_file_does_not_drop_the_next(tmp_path: Path) -> None:
    """A missing cache for one sex still builds the other sex."""
    female = _population()
    male = replace(
        female,
        key="worldpop_qat_agesex/2025/m/25",
        sex="m",
        url="https://data.worldpop.org/SYN/qat_m_25_2025_SYN.tif",
    )
    store(
        tmp_path,
        male,
        population_file(tmp_path / "qat_m_25_2025_SYN.tif").read_bytes(),
    )
    result = build_grids(tmp_path, (female, male), {})
    assert [item["sex"] for item in result.tables["pub_pop_agesex_grid"]] == ["male"]
    assert result.coverage[f"{female.key}:omitted"] == "NO_CACHE"


def test_a_sex_outside_f_and_m_is_both_sexes(tmp_path: Path) -> None:
    """Sex t is a both-sexes file before the name is read."""
    row = _population(sex="t")
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (row,), {})
    assert str(caught.value) == "worldpop_qat_agesex: both-sexes or total file"


def test_male_total_prefix_is_both_sexes(tmp_path: Path) -> None:
    """A qat_T_M_ name is a total file."""
    row = _population(url="https://data.worldpop.org/SYN/qat_T_M_SYN.tif")
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (row,), {})
    assert str(caught.value) == "worldpop_qat_agesex: both-sexes or total file"


def test_slash_free_total_name_is_both_sexes(tmp_path: Path) -> None:
    """A total name with no slash is still the file name."""
    row = _population(sex="m", url="qat_T_M_SYN.tif")
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (row,), {})
    assert str(caught.value) == "worldpop_qat_agesex: both-sexes or total file"


def test_repeated_and_incomplete_years_are_named(tmp_path: Path) -> None:
    """A repeated pair and a missing pair are named refusals."""
    twin = replace(_population(), key="worldpop_qat_agesex/2025/f/25-twin")
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (_population(), twin), {})
    assert str(caught.value) == "worldpop_qat_agesex: repeated sex and age code"
    uneven = replace(
        _population(),
        key="worldpop_qat_agesex/2025/m/30",
        sex="m",
        age_code="30",
        url="https://data.worldpop.org/SYN/qat_m_30_2025_SYN.tif",
    )
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (_population(), uneven), {})
    assert str(caught.value) == "worldpop_qat_agesex: not one row per sex and code"


def test_grids_of_one_year_must_agree_by_name(tmp_path: Path) -> None:
    """Two files of one year on different grids are a named mismatch."""
    first = _population()
    second = replace(
        first,
        key="worldpop_qat_agesex/2025/m/25",
        sex="m",
        url="https://data.worldpop.org/SYN/qat_m_25_2025_SYN.tif",
    )
    store(
        tmp_path,
        first,
        population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes(),
    )
    other = population_file(tmp_path / "qat_m_25_2025_SYN.tif")
    with rasterio.open(other, "r+") as target:
        target.transform = from_origin(0, 1, 0.5, 0.5)
    store(tmp_path, second, other.read_bytes())
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (first, second), {})
    assert str(caught.value) == "worldpop_qat_agesex: grid agreement mismatch"


def test_weather_point_and_body_are_named(tmp_path: Path) -> None:
    """A missing point and a non-object body are named refusals."""
    row = entry(
        "weather_openmeteo",
        "weather_openmeteo/2024-2025/point",
        extension="json",
        licence_basis="provider_terms",
        url="https://archive-api.open-meteo.com/v1/archive?latitude=1&longitude=2",
        fetch_host="archive-api.open-meteo.com",
        period_first="2024-01-01T00:00",
        period_last="2024-01-01T01:00",
        point=None,
        variables=("temperature_2m",),
        cache_role="generator_input",
    )
    store(tmp_path, row, b"{}")
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (row,), {})
    assert str(caught.value) == "weather_openmeteo: point not recorded"
    shutil.rmtree(tmp_path / row.key)
    pointed = replace(row, point=(1.0, 2.0))
    store(tmp_path, pointed, b"[]")
    with pytest.raises(GridError) as caught:
        build_grids(tmp_path, (pointed,), {})
    assert str(caught.value) == "weather_openmeteo: unreadable response"


def test_weather_file_text_is_sorted_and_ascii(tmp_path: Path) -> None:
    """The weather cache file is sorted ASCII, including the degree sign and the byte count."""
    payload = {
        "latitude": 1.1,
        "longitude": 2.1,
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [20, 21],
        },
    }
    body = json.dumps(payload).encode("utf-8")
    row = entry(
        "weather_openmeteo",
        "weather_openmeteo/2024-2025/point",
        extension="json",
        licence_basis="provider_terms",
        url="https://archive-api.open-meteo.com/v1/archive?latitude=1&longitude=2",
        fetch_host="archive-api.open-meteo.com",
        period_first="2024-01-01T00:00",
        period_last="2024-01-01T01:00",
        point=(1.0, 2.0),
        variables=("temperature_2m",),
        cache_role="generator_input",
    )
    store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {})
    digest = _digest(body)
    written = {
        "source_id": "weather_openmeteo",
        "requested_coordinates": [1.0, 2.0],
        "provider_coordinates": [1.1, 2.1],
        "hourly": {
            "time": ["2023-12-31T21:00:00Z", "2023-12-31T22:00:00Z"],
            "temperature_2m": [20, 21],
        },
        "hourly_units": {"time": "UTC", "temperature_2m": "°C"},
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "attribution": (
            "Weather data by Open-Meteo.com — https://open-meteo.com/; "
            "https://creativecommons.org/licenses/by/4.0/; "
            "Generated using Copernicus Climate Change Service information 2022. "
            "Times converted to UTC."
        ),
        "licence_basis": "provider_terms",
        "release_tables": [],
        "source_key": row.key,
        "source_sha256": digest,
        "variables": ["temperature_2m"],
    }
    text = (tmp_path / "grids" / "weather_openmeteo.json").read_text(encoding="utf-8")
    assert text == json.dumps(written, sort_keys=True, ensure_ascii=True) + "\n"
    assert result.manifest["files"][0]["bytes"] == len(body)


def test_a_failed_write_with_no_partial_reraises(tmp_path: Path, monkeypatch) -> None:
    """A write that creates no partial file still raises the original error."""
    row = _population()
    body = population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes()
    store(tmp_path, row, body)

    def boom(self: Path, text: str, encoding: str = "utf-8") -> None:
        raise OSError("SYN-invented write failure")

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(OSError, match="SYN-invented write failure"):
        build_grids(tmp_path, (row,), {})
    assert list((tmp_path / "grids").glob(".manifest.json.partial")) == []
