"""Verbatim base oracle and invented differential population fixtures."""

from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.grids.contracts import GridError, local_file
from eii_custodian.publicdata.grids.population import PopulationSpec


def read_population(
    cache: Path, path: str | Path, spec: PopulationSpec, source_name: str = ""
) -> list[dict[str, Any]]:
    """Return one row per non-nodata source cell without resampling."""
    checked = local_file(cache, path)
    if spec.units != "people_per_cell" or not spec.doi_confirmed or not spec.doi:
        raise GridError("worldpop_qat_agesex: units or DOI unconfirmed")
    if spec.sex_code not in {"f", "m"} or not spec.age_code.isdecimal():
        raise GridError("worldpop_qat_agesex: total or undeclared category")
    if set(spec.public_splits) != {"sex"}:
        raise GridError("worldpop_qat_agesex: public_splits mismatch")
    name = source_name or checked.name
    if not name.startswith(f"qat_{spec.sex_code}_{spec.age_code}_{spec.year}_"):
        raise GridError("worldpop_qat_agesex: file metadata mismatch")
    rasterio = import_module("rasterio")
    with rasterio.open(checked) as source:
        if source.count != 1 or source.crs.to_epsg() != 4326:
            raise GridError("worldpop_qat_agesex: grid schema mismatch")
        if tuple(source.dtypes) != ("float32",):
            raise GridError("worldpop_qat_agesex: band type")
        if source.nodata != -99999:
            raise GridError("worldpop_qat_agesex: nodata mismatch")
        data = source.read(1)
        rows = []
        for row in range(source.height):
            for col in range(source.width):
                value = data[row, col]
                if value == source.nodata:
                    continue
                people = Decimal(str(value))
                if not people.is_finite() or people < 0:
                    raise GridError("worldpop_qat_agesex: invalid population")
                lon, lat = source.xy(row, col)
                rows.append(
                    {
                        "grid_key": f"wa_{row}_{col}",
                        "lon": Decimal(str(lon)).quantize(
                            Decimal("0.000001"), rounding=ROUND_HALF_UP
                        ),
                        "lat": Decimal(str(lat)).quantize(
                            Decimal("0.000001"), rounding=ROUND_HALF_UP
                        ),
                        "age_band": spec.age_code,
                        "sex": {"f": "female", "m": "male"}[spec.sex_code],
                        "people": people.quantize(
                            Decimal("0.0001"), rounding=ROUND_HALF_UP
                        ),
                        "period": spec.year,
                        "source_id": "worldpop_qat_agesex",
                    }
                )
        return rows


def test_reference_function_text():
    import inspect
    import subprocess

    original = subprocess.check_output(
        [
            "git",
            "show",
            "66c0ea750d7df8b54b20e8688a8768d52e21c0b1:custodian/src/eii_custodian/publicdata/grids/population.py",
        ],
        text=True,
    )
    assert (
        inspect.getsource(read_population)
        == original[original.index("def read_population(") :]
    )


def test_compact_storage(tmp_path):
    from custodian.tests.fixtures.grids.invented import population_file
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    assert not isinstance(new_read(tmp_path, path, spec()), list)


def _raster(path, data, **changes):
    import rasterio
    from rasterio.transform import from_origin

    profile = dict(
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=str(data.dtype),
        crs="EPSG:4326",
        nodata=-99999,
        transform=from_origin(0, 1, 1 / 1200, 1 / 1200),
    )
    profile.update(changes)
    with rasterio.open(path, "w", **profile) as target:
        for band in range(1, profile["count"] + 1):
            target.write(data, band)
    return path


def _assert_rows(old, new):
    assert len(old) == len(new)
    for expected, actual in zip(old, new, strict=True):
        assert tuple(expected) == tuple(actual)
        for key, value in expected.items():
            assert type(value) is type(actual[key])
            if isinstance(value, Decimal):
                assert value.as_tuple() == actual[key].as_tuple()
            else:
                assert value == actual[key]


def test_seeded_raster_parity(tmp_path):
    import numpy as np
    from affine import Affine
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    random = np.random.default_rng(2419)
    edges = np.array(
        [
            -99999,
            -0.0,
            0,
            1.23445,
            1.23455,
            0.00005,
            1e-35,
            1e20,
            1 << 24,
            0.000049999,
        ],
        dtype="float32",
    )
    path = tmp_path / "qat_f_25_2025_SYN.tif"
    for case in range(200):
        height, width = random.integers(1, 65, size=2)
        data = random.uniform(0, 1e6, size=(height, width)).astype("float32")
        data.flat[: min(data.size, len(edges))] = edges[: min(data.size, len(edges))]
        options = {}
        if case % 3 == 0:
            options["transform"] = Affine(0.0008, 0.00002, -1, 0.00003, -0.0009, 2)
        _raster(path, data, **options)
        _assert_rows(
            read_population(tmp_path, path, spec()), new_read(tmp_path, path, spec())
        )


def test_refusal_parity(tmp_path):
    from dataclasses import replace

    import numpy as np
    import pytest
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    path = tmp_path / "qat_f_25_2025_SYN.tif"
    for change in (
        {"units": "density"},
        {"doi_confirmed": False},
        {"doi": ""},
        {"sex_code": "t"},
        {"age_code": "total"},
        {"public_splits": ()},
        {"year": "2024"},
    ):
        _raster(path, np.ones((2, 2), dtype="float32"))
        with pytest.raises(GridError) as error:
            read_population(tmp_path, path, replace(spec(), **change))
        with pytest.raises(GridError) as candidate:
            new_read(tmp_path, path, replace(spec(), **change))
        assert str(candidate.value) == str(error.value)
    for changes in (
        {"count": 2},
        {"crs": "EPSG:3857"},
        {"nodata": -1},
        {"dtype": "float64"},
    ):
        data = np.ones((2, 2), dtype=changes.get("dtype", "float32"))
        _raster(path, data, **changes)
        with pytest.raises(GridError) as error:
            read_population(tmp_path, path, spec())
        with pytest.raises(GridError) as candidate:
            new_read(tmp_path, path, spec())
        assert str(candidate.value) == str(error.value)
    for invalid in (np.nan, np.inf, -1.0):
        _raster(path, np.array([[1, invalid]], dtype="float32"))
        with pytest.raises(GridError, match="worldpop_qat_agesex: invalid population"):
            read_population(tmp_path, path, spec())
        with pytest.raises(GridError, match="worldpop_qat_agesex: invalid population"):
            new_read(tmp_path, path, spec())


def test_float32_rounding_and_negative_zero(tmp_path):
    from decimal import localcontext

    import numpy as np
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    values = np.array(
        [[-0.0, 1.23445, 1.23455, 0.00005, 1e-35, np.finfo("float32").max]],
        dtype="float32",
    )
    path = _raster(tmp_path / "qat_f_25_2025_SYN.tif", values)
    with localcontext() as context:
        context.prec = 60
        _assert_rows(
            read_population(tmp_path, path, spec()), new_read(tmp_path, path, spec())
        )


def test_axis_centres_and_rotation(tmp_path):
    import numpy as np
    from affine import Affine
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    for transform in (
        Affine(0.3, 0, -0.0, -0.0, -0.3, 0),
        Affine(0.3, 0.02, -1, 0.01, -0.3, 1),
    ):
        path = _raster(
            tmp_path / "qat_f_25_2025_SYN.tif",
            np.ones((7, 9), dtype="float32"),
            transform=transform,
        )
        _assert_rows(
            read_population(tmp_path, path, spec()), new_read(tmp_path, path, spec())
        )


def test_row_major_order_and_read_only(tmp_path):
    import numpy as np
    import pytest
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    path = _raster(
        tmp_path / "qat_f_25_2025_SYN.tif", np.arange(6, dtype="float32").reshape(2, 3)
    )
    rows = new_read(tmp_path, path, spec())
    assert [row["grid_key"] for row in rows] == [
        "wa_0_0",
        "wa_0_1",
        "wa_0_2",
        "wa_1_0",
        "wa_1_1",
        "wa_1_2",
    ]
    rows[0]["people"] = 99
    assert isinstance(rows[0]["people"], Decimal)
    assert rows[0]["people"].as_tuple() == Decimal("0.0000").as_tuple()
    assert rows[-1] == rows[5]
    assert rows[1:4] == list(rows)[1:4]
    with pytest.raises(IndexError):
        _ = rows[len(rows)]


def test_table_index_refusals(tmp_path):
    import pytest
    from custodian.tests.fixtures.grids.invented import population_file
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids import population as population_module
    from eii_custodian.publicdata.grids.population import (
        read_population as new_read,
    )

    table_type = getattr(population_module, "PopulationTable", None)
    assert table_type is not None

    path = population_file(tmp_path / "qat_f_25_2025_SYN.tif")
    rows = new_read(tmp_path, path, spec())
    table = table_type([rows])
    assert table[-len(table)] == table[0]
    assert table[-1] == table[len(table) - 1]
    assert table[:] == list(table)
    assert table == list(table)
    assert list(table) == table
    assert table != []
    assert table != tuple(table)
    assert table != [{"SYN": "different"}]
    with pytest.raises(IndexError, match=r"^-1$"):
        _ = table[-len(table) - 1]
    with pytest.raises(IndexError, match=r"^0$"):
        _ = table[len(table)]
    with pytest.raises(IndexError, match=r"^0$"):
        _ = table_type([])[0]


def _assert_context_parity(tmp_path, emin):
    from decimal import Context, localcontext

    import numpy as np
    from custodian.tests.test_population_grid import spec

    from eii_custodian.publicdata.grids.population import read_population as new_read

    path = _raster(
        tmp_path / "qat_f_25_2025_SYN.tif",
        np.array([[1.23445, 0.00005]], dtype="float32"),
    )
    with localcontext(Context(prec=60, Emax=3, Emin=emin)):
        expected = read_population(tmp_path, path, spec())
        assert expected[0]["people"].adjusted() == 0
        assert expected[1]["people"].as_tuple() == Decimal("0.0001").as_tuple()
        failure = None
        try:
            actual = new_read(tmp_path, path, spec())
        except ArithmeticError as error:
            failure = error
        assert failure is None, repr(failure)
        _assert_rows(expected, actual)
        assert list(actual) == expected


def test_reduced_emax_parity(tmp_path):
    _assert_context_parity(tmp_path, -10)


def test_reduced_emin_parity(tmp_path):
    _assert_context_parity(tmp_path, -3)
