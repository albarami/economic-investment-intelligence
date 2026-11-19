"""Owner tile inputs and deterministic fixture contracts; no provider constants."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from urllib.parse import urlsplit

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.cdse.transport import HASH, CdseError
from eii_custodian.publicdata.fetch.snapshots import utc

CRS = "EPSG:32639"
RESOLUTION_M = 10
TARGET_M = 22000
EDGE_CAP = 2500


@dataclass(frozen=True)
class PageEvidence:
    url: str
    read_on: str
    sha256: str
    words: str

    def validate(self) -> None:
        """A provider fact needs a complete public-page chain; pending is no fact."""
        try:
            parts = urlsplit(self.url)
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.username is not None
                or parts.password is not None
                or parts.query
                or parts.fragment
                or parts.port not in (None, 443)
                or any(ord(c) <= 32 for c in self.url)
                or len(self.read_on) != 10
                or date.fromisoformat(self.read_on).isoformat() != self.read_on
                or HASH.fullmatch(self.sha256) is None
                or not self.words.strip()
                or self.words.casefold().startswith(("pending", "terms to be read"))
            ):
                raise ValueError
        except ValueError:
            raise CdseError("provider_evidence_missing") from None


@dataclass(frozen=True)
class Tile:
    tile_id: str
    bounds: tuple[int, int, int, int]
    crs: str
    width: int
    height: int
    resolution_m: int = RESOLUTION_M


def tiles_for(boundary: BaseGeometry, crs: str) -> tuple[Tile, ...]:
    """Grid a reviewed Qatar frame in metres. Tests inject an invented boundary."""
    if crs != CRS or boundary.is_empty or not boundary.is_valid:
        raise CdseError("metric_boundary_required")
    lo_x, lo_y, hi_x, hi_y = boundary.bounds
    if not all(math.isfinite(v) for v in (lo_x, lo_y, hi_x, hi_y)):
        raise CdseError("metric_boundary_required")
    start_x = math.floor(lo_x / RESOLUTION_M) * RESOLUTION_M
    start_y = math.floor(lo_y / RESOLUTION_M) * RESOLUTION_M
    end_x = math.ceil(hi_x / RESOLUTION_M) * RESOLUTION_M
    end_y = math.ceil(hi_y / RESOLUTION_M) * RESOLUTION_M
    tiles: list[Tile] = []
    for x in range(start_x, end_x, TARGET_M):
        for y in range(start_y, end_y, TARGET_M):
            right, top = min(x + TARGET_M, end_x), min(y + TARGET_M, end_y)
            if (
                boundary.intersection(
                    shape(
                        {
                            "type": "Polygon",
                            "coordinates": [
                                [[x, y], [right, y], [right, top], [x, top], [x, y]]
                            ],
                        }
                    )
                ).area
                <= 0
            ):
                continue
            tiles.append(
                Tile(
                    f"tile-{x}-{y}",
                    (x, y, right, top),
                    crs,
                    (right - x) // RESOLUTION_M,
                    (top - y) // RESOLUTION_M,
                )
            )
    if not tiles:
        raise CdseError("metric_boundary_required")
    return tuple(tiles)


@dataclass(frozen=True)
class Metadata:
    tile: Tile
    start: str
    end: str
    dates: tuple[str, ...]
    ordering: str
    mask: str
    coverage: str
    collection: str
    bands: tuple[str, ...]
    factor: Decimal
    method: str


def request_sha256(meta: Metadata) -> str:
    """Hash sanitized request inputs, excluding response dates and coverage."""
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    inputs = asdict(meta)
    del inputs["dates"]
    del inputs["coverage"]
    return sha256_hex(
        json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str).encode()
    )


def validate_metadata(meta: Metadata, boundary: BaseGeometry) -> None:
    """Closed owner parameters, explicit UTC interval and actual contribution dates."""
    if meta.tile not in tiles_for(boundary, meta.tile.crs):
        raise CdseError("tile_outside_frame_or_dimensions")
    tile = meta.tile
    if (
        type(tile.width) is not int
        or type(tile.height) is not int
        or not 0 < tile.width <= EDGE_CAP
        or not 0 < tile.height <= EDGE_CAP
        or tile.resolution_m != RESOLUTION_M
    ):
        raise CdseError("tile_dimensions_refused")
    start, end = utc(meta.start), utc(meta.end)
    if start >= end or not meta.dates or tuple(sorted(set(meta.dates))) != meta.dates:
        raise CdseError("acquisition_dates_missing")
    if any(not start <= utc(value) < end for value in meta.dates):
        raise CdseError("acquisition_dates_outside_window")
    if (
        meta.ordering != "least_cloudy"
        or meta.mask != "cloud_and_nodata_transparent"
        or meta.coverage not in {"partial", "complete_valid_pixels"}
        or meta.collection != "sentinel-2-l2a"
        or meta.bands != ("B04", "B03", "B02")
        or meta.factor != Decimal("2.5")
        or meta.method != "cdse-cache.v1"
    ):
        raise CdseError("tile_metadata_refused")


@dataclass(frozen=True)
class CostModel:
    """An explicit linear fixture formula, pending official formula verification.

    Each Decimal carries processing units except pixels_per_unit (pixels), and
    quantum (processing units). There are no default provider costs or quotas.
    """

    pixels_per_unit: Decimal
    band_sample_factor: Decimal
    minimum: Decimal
    quantum: Decimal
    token_cost: Decimal
    metadata_cost: Decimal
    evidence: PageEvidence

    def validate(self) -> None:
        self.evidence.validate()
        values = (
            self.pixels_per_unit,
            self.band_sample_factor,
            self.minimum,
            self.quantum,
            self.token_cost,
            self.metadata_cost,
        )
        if any(not v.is_finite() or v < 0 for v in values) or any(
            v == 0 for v in values[:4]
        ):
            raise CdseError("quota_formula_unknown")

    def picture_cost(self, pixels: int, *, bands: int, samples: int) -> Decimal:
        """Round up only in the explicitly supplied provider unit and quantum."""
        self.validate()
        if any(type(v) is not int or v <= 0 for v in (pixels, bands, samples)):
            raise CdseError("quota_inputs_refused")
        units = (
            Decimal(pixels)
            / self.pixels_per_unit
            * bands
            * samples
            * self.band_sample_factor
        )
        return (max(self.minimum, units) / self.quantum).to_integral_value(
            rounding=ROUND_CEILING
        ) * self.quantum


@dataclass(frozen=True)
class Budget:
    kinds: tuple[str, ...]
    requests: int
    pixels: int
    units: Decimal
    reserve_note: str


def bulk_budget(
    tiles: tuple[Tile, ...],
    model: CostModel | None,
    free_units: Decimal | None,
    free_requests: int | None,
    *,
    metadata: int,
    refresh: int,
    retries: int,
    reserve_note: str,
) -> Budget:
    """Reserve every metadata/refresh/retry attempt before bulk acquisition."""
    if model is None or free_units is None or free_requests is None:
        raise CdseError("bulk_quota_unknown")
    model.validate()
    if (
        not tiles
        or not reserve_note.strip()
        or not free_units.is_finite()
        or free_units < 0
        or type(free_requests) is not int
        or free_requests < 0
        or any(type(n) is not int or n < 0 for n in (metadata, refresh, retries))
    ):
        raise CdseError("bulk_budget_refused")
    for tile in tiles:
        if (
            type(tile.width) is not int
            or type(tile.height) is not int
            or not 0 < tile.width <= EDGE_CAP
            or not 0 < tile.height <= EDGE_CAP
        ):
            raise CdseError("tile_dimensions_refused")
    costs = tuple(
        model.picture_cost(tile.width * tile.height, bands=3, samples=1)
        for tile in tiles
    )
    pixels = sum(tile.width * tile.height for tile in tiles)
    kinds = (
        ("token",)
        + ("metadata",) * metadata
        + ("process",) * len(tiles)
        + ("token",) * refresh
        + ("process",) * retries
    )
    units = (
        sum(costs, Decimal(0))
        + model.token_cost * (1 + refresh)
        + model.metadata_cost * metadata
        + max(costs) * retries
    )
    if len(kinds) > free_requests or units > free_units:
        raise CdseError("bulk_allowance_insufficient_fallback_retained")
    return Budget(kinds, len(kinds), pixels, units, reserve_note)
