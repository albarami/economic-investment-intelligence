"""Preregistered, immutable measurement contract for invented-fixture proof."""

import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256

BASELINES = ("seasonal_naive", "drift", "simple_exponential_smoothing")
AUTOS = ("auto_ets", "auto_theta", "auto_arima")
COMBINATION = "equal_weight"
POLICY = "nested_policy"
CHALLENGERS = ("chronos_2", "timesfm_2_5")
METHOD = "s6-t27-prefix-mase-v1"
MINIMUM_TARGETS = 12


@dataclass(frozen=True)
class Family:
    source: str
    frequency: str
    measure: str
    unit: str
    currency: str
    valuation: str
    classification: str
    provenance: str


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    family: Family
    periods: tuple[int, ...]
    targets: tuple[int, ...]
    geography: str
    category: str
    source_chain: str
    classifications: tuple[str, ...] = ()


@dataclass(frozen=True)
class Registration:
    series: tuple[SeriesSpec, ...]
    candidates: tuple[str, ...] = BASELINES + AUTOS + (COMBINATION, POLICY)
    horizon: int = 1
    minimum: int = MINIMUM_TARGETS
    seed: int = 27
    version: str = METHOD

    def validate(self) -> None:
        if type(self.series) is not tuple or type(self.candidates) is not tuple:
            raise ValueError("immutable_contract")
        for row in self.series:
            if (
                type(row) is not SeriesSpec
                or type(row.family) is not Family
                or type(row.periods) is not tuple
                or type(row.targets) is not tuple
                or type(row.classifications) is not tuple
            ):
                raise ValueError("immutable_contract")
        if (
            type(self.horizon) is not int
            or self.horizon != 1
            or type(self.minimum) is not int
            or self.minimum != MINIMUM_TARGETS
            or self.version != METHOD
            or type(self.seed) is not int
        ):
            raise ValueError("unreviewed_contract")
        permitted = BASELINES + AUTOS + (COMBINATION, POLICY) + CHALLENGERS
        if (
            not self.candidates
            or len(set(self.candidates)) != len(self.candidates)
            or any(c not in permitted for c in self.candidates)
            or not all(c in self.candidates for c in BASELINES)
            or tuple(c for c in permitted if c in self.candidates) != self.candidates
        ):
            raise ValueError("candidate_contract")
        if COMBINATION in self.candidates and not all(
            c in self.candidates for c in AUTOS
        ):
            raise ValueError("combination_requires_autos")
        if POLICY in self.candidates and not all(
            c in self.candidates for c in (*AUTOS, COMBINATION)
        ):
            raise ValueError("policy_requires_fixed_candidates")
        if not self.series or len({r.key for r in self.series}) != len(self.series):
            raise ValueError("series_membership")
        for row in self.series:
            for text in (
                row.key,
                row.geography,
                row.category,
                row.source_chain,
                *asdict(row.family).values(),
            ):
                if type(text) is not str or not text:
                    raise ValueError("missing_series_metadata")
            if row.family.provenance not in ("public", "generated", "invented"):
                raise ValueError("provenance")
            first = first_origin(row.family.frequency)
            if any(type(p) is not int for p in row.periods):
                raise ValueError("period_type")
            if len(row.periods) - first < 3:
                raise ValueError("series_too_short")
            if any(
                b != a + 1 for a, b in zip(row.periods, row.periods[1:], strict=False)
            ):
                raise ValueError("nonconsecutive_periods")
            if row.classifications and (
                len(row.classifications) != len(row.periods)
                or any(c != row.family.classification for c in row.classifications)
            ):
                raise ValueError("classification_break")
            minimum = first + calibration_minimum(level(row.family.frequency))
            if (
                any(
                    type(o) is not int or not minimum <= o < len(row.periods)
                    for o in row.targets
                )
                or tuple(sorted(set(row.targets))) != row.targets
            ):
                raise ValueError("target_origins")

    @property
    def sha256(self) -> str:
        document = asdict(self)
        document["levels"] = {"year": [4, 5], "quarter": [4, 5], "month": [9, 10]}
        document["aggregation"] = "equal_series_weight_paired_targets"
        document["selection"] = "matured_inner_errors_fixed_order_ties"
        document["decimal"] = "lossless_from_float_context_50_half_up"
        return sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def level(frequency: str) -> Fraction:
    season(frequency)
    return Fraction(9, 10) if frequency == "month" else Fraction(4, 5)


def season(frequency: str) -> int:
    if frequency not in ("year", "quarter", "month"):
        raise ValueError("published_frequency")
    return {"year": 1, "quarter": 4, "month": 12}[frequency]


def first_origin(frequency: str) -> int:
    return max(2, season(frequency) + 1)


def calibration_minimum(coverage: Fraction) -> int:
    if type(coverage) is not Fraction or not 0 < coverage < 1:
        raise ValueError("exact_rational_level")
    return (coverage.denominator - 1) // (coverage.denominator - coverage.numerator)


def number(value: Decimal | float) -> Decimal:
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("finite_output_required")
        return Decimal.from_float(value)
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("finite_decimal_required")
    return value
