"""Native population cells; unconfirmed units and DOI mappings fail closed."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.registry import Entry

from .contracts import GridError, local_file


@dataclass(frozen=True)
class PopulationSpec:
    """Reviewed source metadata of one population file."""

    release: str
    year: str
    age_code: str
    sex_code: str
    units: str
    doi: str
    doi_confirmed: bool
    public_splits: tuple[str, ...]


def spec_from_entry(entry: Entry) -> PopulationSpec:
    """Return the reviewed metadata of one registry file entry, unchanged."""
    return PopulationSpec(
        release=entry.release,
        year=entry.year,
        age_code=entry.age_code,
        sex_code=entry.sex,
        units=entry.cell_units,
        doi=entry.doi,
        doi_confirmed=entry.doi_confirmed,
        public_splits=entry.public_splits,
    )


def grid_signature(cache: Path, path: str | Path) -> tuple[Any, ...]:
    """Return the native dimensions, reference system, origin and pixel size."""
    checked = local_file(cache, path)
    rasterio = import_module("rasterio")
    with rasterio.open(checked) as source:
        return (
            source.width,
            source.height,
            source.crs.to_epsg() if source.crs is not None else None,
            *tuple(source.transform)[:6],
        )


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
