"""Hand-written population results that kill surviving numeric mutants."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
import rasterio
from custodian.tests.fixtures.grids.invented import entry, population_file
from rasterio.transform import from_origin

from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.population import (
    grid_signature,
    read_population,
    spec_from_entry,
)

TIE = from_origin(0, 1e-6, 1e-6, 1e-6)
PLAIN = from_origin(0, 1, 1, 1)


def _spec(**overrides: object) -> object:
    base = {
        "release": "SYN-release",
        "year": "2025",
        "age_code": "25",
        "sex_code": "f",
        "units": "people_per_cell",
        "doi": "SYN-doi",
        "doi_confirmed": True,
        "public_splits": ("sex",),
    }
    base.update(overrides)
    from eii_custodian.publicdata.grids.population import PopulationSpec

    return PopulationSpec(**base)


def _write(
    path: Path,
    values: list[list[float]],
    transform: object,
    *,
    crs: str | None = "EPSG:4326",
    dtype: str = "float32",
    nodata: float = -99999,
) -> None:
    array = np.array(values, dtype=dtype)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as target:
        target.write(array, 1)


def test_spec_copies_the_release_unchanged() -> None:
    """The reviewed release is the registry release, not a missing value."""
    row = entry(
        "worldpop_qat_agesex",
        "worldpop_qat_agesex/2025/f/25",
        release="SYN-release",
        year="2025",
        age_code="25",
        sex="f",
        cell_units="people_per_cell",
        doi="SYN-doi",
        doi_confirmed=True,
        public_splits=("sex",),
    )
    copied = spec_from_entry(row)
    assert copied.release == "SYN-release"
    assert copied.year == "2025"
    assert copied.sex_code == "f"
    assert copied.age_code == "25"


def test_signature_reports_epsg_4326_and_six_affine_terms(tmp_path: Path) -> None:
    """A referenced grid reports 4326 and the six affine terms, not a seventh."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[1.0]], TIE)
    assert grid_signature(tmp_path, path) == (
        1,
        1,
        4326,
        1e-6,
        0.0,
        0.0,
        0.0,
        -1e-6,
        1e-6,
    )


def test_signature_without_a_reference_system_is_none(tmp_path: Path) -> None:
    """A grid with no reference system reports none, and does not ask it for a code."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[1.0]], PLAIN, crs=None)
    assert grid_signature(tmp_path, path) == (
        1,
        1,
        None,
        1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        1.0,
    )


def test_half_up_quantizes_the_tie_in_people_and_both_centres(tmp_path: Path) -> None:
    """1.00005 people is 1.0001, and each 5e-7 centre is 0.000001."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[1.00005]], TIE)
    rows = read_population(tmp_path, path, _spec())
    assert rows == [
        {
            "grid_key": "wa_0_0",
            "lon": Decimal("0.000001"),
            "lat": Decimal("0.000001"),
            "age_band": "25",
            "sex": "female",
            "people": Decimal("1.0001"),
            "period": "2025",
            "source_id": "worldpop_qat_agesex",
        }
    ]


def test_zero_people_is_kept(tmp_path: Path) -> None:
    """A source cell of zero people is a counted cell."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[0.0]], PLAIN)
    rows = read_population(tmp_path, path, _spec())
    assert rows[0]["people"] == Decimal("0.0000")
    assert rows[0]["grid_key"] == "wa_0_0"


def test_nodata_does_not_drop_the_next_cell(tmp_path: Path) -> None:
    """A nodata cell leaves the next cell in the same row."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[-99999, 10.4]], from_origin(0, 1, 1 / 1200, 1 / 1200))
    rows = read_population(tmp_path, path, _spec())
    assert rows == [
        {
            "grid_key": "wa_0_1",
            "lon": Decimal("0.001250"),
            "lat": Decimal("0.999583"),
            "age_band": "25",
            "sex": "female",
            "people": Decimal("10.4000"),
            "period": "2025",
            "source_id": "worldpop_qat_agesex",
        }
    ]


def test_male_label_is_the_word_male(tmp_path: Path) -> None:
    """A male file is labelled male."""
    path = tmp_path / "qat_m_25_2025_SYN.tif"
    _write(path, [[4.0]], PLAIN)
    rows = read_population(tmp_path, path, _spec(sex_code="m"))
    assert rows[0]["sex"] == "male"
    assert rows[0]["people"] == Decimal("4.0000")


@pytest.mark.parametrize(
    ("overrides", "name", "message"),
    [
        (
            {"units": "density"},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: units or DOI unconfirmed",
        ),
        (
            {"doi_confirmed": False},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: units or DOI unconfirmed",
        ),
        (
            {"doi": ""},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: units or DOI unconfirmed",
        ),
        (
            {"sex_code": "t"},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: total or undeclared category",
        ),
        (
            {"age_code": "T"},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: total or undeclared category",
        ),
        (
            {"public_splits": ()},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: public_splits mismatch",
        ),
        (
            {"year": "2024"},
            "qat_f_25_2025_SYN.tif",
            "worldpop_qat_agesex: file metadata mismatch",
        ),
    ],
)
def test_population_refusals_use_the_whole_message(
    tmp_path: Path,
    overrides: dict[str, object],
    name: str,
    message: str,
) -> None:
    """Each population refusal is the whole named sentence."""
    path = population_file(tmp_path / name)
    with pytest.raises(GridError) as caught:
        read_population(tmp_path, path, _spec(**overrides))
    assert str(caught.value) == message


def test_wrong_reference_system_names_the_schema(tmp_path: Path) -> None:
    """A grid that is not EPSG:4326 is a schema mismatch."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[1.0]], PLAIN, crs="EPSG:3857")
    with pytest.raises(GridError) as caught:
        read_population(tmp_path, path, _spec())
    assert str(caught.value) == "worldpop_qat_agesex: grid schema mismatch"


def test_wrong_band_type_names_the_band(tmp_path: Path) -> None:
    """An integer band is refused by name."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[1.0]], PLAIN, dtype="int32")
    with pytest.raises(GridError) as caught:
        read_population(tmp_path, path, _spec())
    assert str(caught.value) == "worldpop_qat_agesex: band type"


def test_wrong_nodata_names_the_mismatch(tmp_path: Path) -> None:
    """A nodata marker other than -99999 is refused by name."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[1.0]], PLAIN, nodata=-1)
    with pytest.raises(GridError) as caught:
        read_population(tmp_path, path, _spec())
    assert str(caught.value) == "worldpop_qat_agesex: nodata mismatch"


def test_negative_people_names_the_invalid_cell(tmp_path: Path) -> None:
    """A negative count is refused by name."""
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    _write(path, [[-1.0]], PLAIN)
    with pytest.raises(GridError) as caught:
        read_population(tmp_path, path, _spec())
    assert str(caught.value) == "worldpop_qat_agesex: invalid population"
