"""Native population cells; unconfirmed units and DOI mappings fail closed."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from pathlib import Path
from typing import Any, overload

import numpy as np

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
) -> PopulationRows:
    """Return compact native cells, exposing the original row values on access."""
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
        indices = np.flatnonzero(data.ravel() != source.nodata).astype("uint64")
        coefficients = np.empty((len(indices), 3), dtype="uint64")
        signs = np.empty(len(indices), dtype="uint8")
        coordinates: tuple[dict[int, Decimal], dict[int, Decimal], bool] = (
            {},
            {},
            bool(source.transform.b or source.transform.d),
        )
        for index, offset in enumerate(indices):
            row, col = divmod(int(offset), source.width)
            people = Decimal(str(data[row, col]))
            if not people.is_finite() or people < 0:
                raise GridError("worldpop_qat_agesex: invalid population")
            _cell_centres(source, row, col, coordinates)
            people = people.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            # Coefficients count ten-thousandths of a person; sign is separate
            # so a zero coefficient retains the source's negative zero.
            coefficient = int(people.copy_abs().scaleb(4))
            coefficients[index] = (
                coefficient & ((1 << 64) - 1),
                (coefficient >> 64) & ((1 << 64) - 1),
                coefficient >> 128,
            )
            signs[index] = people.is_signed()
        return PopulationRows(
            indices, coefficients, signs, source.width, coordinates, spec
        )


def _coordinate(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _cell_centres(
    source: Any,
    row: int,
    col: int,
    coordinates: tuple[dict[int, Decimal], dict[int, Decimal], bool],
) -> None:
    """Share axis centres; rotation and shear retain per-pixel source.xy calls."""
    lon, lat, rotated = coordinates
    offset = row * source.width + col
    xkey, ykey = (offset, offset) if rotated else (col, row)
    if xkey not in lon or ykey not in lat:
        x, y = source.xy(row, col)
        if xkey not in lon:
            lon[xkey] = _coordinate(x)
        if ykey not in lat:
            lat[ykey] = _coordinate(y)


class _RowSequence(Sequence[dict[str, Any]]):
    """Keep list value equality without materializing the compact rows."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (list, _RowSequence)):
            return False
        return len(self) == len(other) and all(
            left == right for left, right in zip(self, other, strict=True)
        )


class PopulationRows(_RowSequence):
    """Read-only columns; each access returns a fresh, ordinary base-shaped row."""

    def __init__(
        self,
        indices: Any,
        coefficients: Any,
        signs: Any,
        width: int,
        coordinates: tuple[dict[int, Decimal], dict[int, Decimal], bool],
        spec: PopulationSpec,
    ) -> None:
        for column in (indices, coefficients, signs):
            column.flags.writeable = False
        self._indices = indices
        self._coefficients = coefficients
        self._signs = signs
        self._width = width
        self._coordinates = coordinates
        self._spec = spec
        self._facts: dict[str, Any] = {}

    def with_facts(self, facts: dict[str, Any]) -> PopulationRows:
        """Bind one file's constant lineage without retaining it per pixel."""
        result = PopulationRows(
            self._indices,
            self._coefficients,
            self._signs,
            self._width,
            self._coordinates,
            self._spec,
        )
        result._facts = facts.copy()
        return result

    def __len__(self) -> int:
        return len(self._indices)

    @overload
    def __getitem__(self, index: int) -> dict[str, Any]: ...
    @overload
    def __getitem__(self, index: slice) -> list[dict[str, Any]]: ...
    def __getitem__(self, index: int | slice) -> dict[str, Any] | list[dict[str, Any]]:
        if isinstance(index, slice):
            return [self[item] for item in range(*index.indices(len(self)))]
        offset = int(self._indices[index])
        row, col = divmod(offset, self._width)
        low, middle, high = self._coefficients[index]
        coefficient = int(low) | (int(middle) << 64) | (int(high) << 128)
        people = Decimal(
            (int(self._signs[index]), tuple(map(int, str(coefficient))), -4)
        )
        lon, lat, rotated = self._coordinates
        spec = self._spec
        result = {
            "grid_key": f"wa_{row}_{col}",
            "lon": lon[offset if rotated else col],
            "lat": lat[offset if rotated else row],
            "age_band": spec.age_code,
            "sex": {"f": "female", "m": "male"}[spec.sex_code],
            "people": people,
            "period": spec.year,
            "source_id": "worldpop_qat_agesex",
        }
        result.update(
            {
                key: value.copy() if isinstance(value, list) else value
                for key, value in self._facts.items()
            }
        )
        return result

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return (self[index] for index in range(len(self)))


class PopulationTable(_RowSequence):
    """Keep file order while holding only one compact column block per file."""

    def __init__(self, parts: Sequence[PopulationRows]) -> None:
        self._parts = tuple(parts)

    def __len__(self) -> int:
        return sum(len(part) for part in self._parts)

    @overload
    def __getitem__(self, index: int) -> dict[str, Any]: ...
    @overload
    def __getitem__(self, index: slice) -> list[dict[str, Any]]: ...
    def __getitem__(self, index: int | slice) -> dict[str, Any] | list[dict[str, Any]]:
        if isinstance(index, slice):
            return [self[item] for item in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0:
            raise IndexError(index)
        for part in self._parts:
            if index < len(part):
                return part[index]
            index -= len(part)
        raise IndexError(index)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return (row for part in self._parts for row in part)
