"""Strict application facts, semantic identities and Public lineage (DAT-90-95).

Only units and geography kinds reached by built tools are admitted. Calculation
results retain their existing dataclasses in calc.facts.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from eii_core.calc import least_real
from eii_core.calc.facts import SourceChain

UNITS = frozenset(
    {
        "count",
        "ratio",
        "percent",
        "calendar_month",
        "size_band",
        "qar_per_month",
        "qar_thousand",
        "qar",
        "published_text",
        "metres",
        "radiance_nw_cm2_sr",
        "relative_index",
        "square_metre",
        "qar_per_ft2",
        "qar_per_m2",
        "calendar_date",
        "calendar_year",
        "usd_million",
        "announced_jobs",
        "decimal_degree",
    }
)
METRIC_KEYS = frozenset(
    (
        "bulk_month",
        "place_listing",
        "guide_price_class",
        "rail_feature",
        "health_centre_name",
        "permitted_use",
        "poi_category",
        "address_zone",
        "address_street",
        "address_building",
        "parcel_area",
        "landmark_name",
        "fdi_company",
        "fdi_capex",
        "fdi_jobs",
        "fdi_location",
        "fdi_field",
        "district_sale",
        "radiance_class",
        "electricity_growth_class",
        "register_company_point",
        "night_lights_radiance",
        "venue_busyness_index",
        "population_grid_people",
        "active_count",
        "including_ratio",
        "including_percent",
        "excluding_percent",
        "churn_low",
        "churn_high",
        "undated_count",
        "bulk_share",
        "arrivals",
        "beverages",
        "building_rent",
        "change",
        "change_percent",
        "compensation",
        "compensation_percent",
        "employees",
        "establishments",
        "facilities",
        "firms_per_tower",
        "fixed_composition_change",
        "fixed_composition_percent",
        "food",
        "goods_percent",
        "guests",
        "licence_density",
        "local_count",
        "location_quotient",
        "lq_high",
        "lq_low",
        "mean_after",
        "mean_before",
        "mix",
        "mix_share",
        "national_ratio",
        "populated_groups",
        "purchases",
        "ranked_ratio",
        "relative",
        "sales",
        "services_percent",
        "size_class",
        "stocks",
        "surplus_percent",
        "within",
        "zone_ratio",
        "place_distance_metres",
        "place_confidence",
        "venue_visits",
        "found_near_quotient",
        "place_source_release",
        "place_check_date",
        "place_name",
        "place_licence",
        "place_source_attribution",
    )
)
QUALIFIER_KEYS = frozenset(
    {
        "activity",
        "table_code",
        "indicator",
        "size_class",
        "nationality_group",
        "breakdown_key",
        "utility",
        "use_category",
        "price_basis",
        "facility_type",
        "trade_type",
        "base_period",
        "base_geography",
        "base_geography_kind",
        "treatment",
        "month",
        "source_table",
        "origin",
        "routing_method",
        "routing_graph",
        "category",
        "language",
        "age_band",
        "sex",
        "day_of_week",
        "hour",
        "field",
    }
)
KEY = re.compile(r"[a-z][a-z0-9_]*")
HASH = re.compile(r"[0-9a-f]{64}")
SIZE_BAND = re.compile(r"(?:no_payroll|s[0-9]{2}_(?:[0-9]{2}|plus))")


class Fact(BaseModel):
    """Exactly the fifteen application fields; no coercion or extra fields."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    fact_id: str
    # JSON Decimal parsing accepts digit-only strings; prefer the declared text
    # branch so published references retain their exact type and spelling.
    value: str | Decimal | int | float | None
    unit: str
    period: str
    geography: dict[str, str]
    provenance: Literal["public", "synthetic", "simulated", "suppressed"]
    input_classes: list[Literal["public", "synthetic", "simulated", "user_input"]]
    evidence_status: Literal["observed", "inferred", "still_to_test"]
    reliability: Literal["standard", "low_count", "not_applicable"]
    coverage_keys: list[str]
    caveat_keys: list[str]
    label_en: str
    label_ar: str
    lineage_ref: str
    release_id: str

    @model_validator(mode="after")
    def contract(self) -> Self:
        for field_text, pattern, reason in (
            (self.fact_id, r"f_[0-9a-f]{32}", "fact_id_invalid"),
            (self.release_id, r"[0-9a-f]{64}", "release_id_invalid"),
            (self.lineage_ref, r"lin_[a-z0-9_]+", "lineage_ref_invalid"),
        ):
            if re.fullmatch(pattern, field_text) is None:
                raise ValueError(reason)
        if len(self.period) < 4:
            raise ValueError("period_invalid")
        if not self.label_en or not self.label_ar:
            raise ValueError("label_empty")
        if any(c.isdigit() for c in self.label_en + self.label_ar):
            raise ValueError("label_digit")
        if any(KEY.fullmatch(k) is None for k in self.coverage_keys + self.caveat_keys):
            raise ValueError("key_invalid")
        geo = self.geography
        if geo == {"kind": "national"}:
            pass
        elif set(geo) == {"kind", "area_id"} and geo["kind"] == "area_shape":
            context_area = (
                self.provenance == "public"
                and self.input_classes == ["public"]
                and self.evidence_status == "observed"
                and "calculated" in self.caveat_keys
                and (
                    (
                        self.unit == "radiance_nw_cm2_sr"
                        and "night_lights_not_activity" in self.caveat_keys
                        and "grid_cells_summed" not in self.caveat_keys
                    )
                    or (
                        self.unit == "count" and "grid_cells_summed" in self.caveat_keys
                    )
                )
            )
            area_pattern = r"ma1/[0-9a-f]{16}/(?:polygon/[0-9a-f]{64}|(?:distance|walk|drive)/(?:0|[1-9][0-9]*)/(?:none|0|[1-9][0-9]*)/-?(?:0|[1-9][0-9]*)\.[0-9]{6}/-?(?:0|[1-9][0-9]*)\.[0-9]{6})"
            if (
                not context_area
                or re.fullmatch(area_pattern, geo["area_id"]) is None
                or geo["area_id"].split("/")[1] != self.release_id[:16]
            ):
                raise ValueError("geography_invalid")
        elif set(geo) == {"kind", "public_code"} and geo["kind"] == "public":
            if (
                re.fullmatch(
                    r"(zone|municipality|district|place|cell|feature):.+",
                    geo["public_code"],
                )
                is None
            ):
                raise ValueError("geography_invalid")
        else:
            raise ValueError("geography_invalid")
        if (
            geo.get("public_code", "").startswith(("cell:", "feature:"))
            or self.unit in {"square_metre", "qar_per_ft2", "qar_per_m2"}
        ) and (self.provenance, self.input_classes, self.evidence_status) != (
            "public",
            ["public"],
            "observed",
        ):
            raise ValueError("published_status_invalid")
        if self.unit not in UNITS:
            raise ValueError("unit_unknown")
        if self.unit in {"usd_million", "announced_jobs", "decimal_degree"}:
            if (
                self.provenance,
                self.input_classes,
                self.evidence_status,
                self.reliability,
            ) != ("public", ["public"], "observed", "not_applicable"):
                raise ValueError("published_status_invalid")
            if (
                self.unit in {"usd_million", "announced_jobs"}
                and "fdi_estimates" not in self.caveat_keys
            ):
                raise ValueError("announced_estimate_unlabelled")
        if not self.input_classes or len(set(self.input_classes)) != len(
            self.input_classes
        ):
            raise ValueError("input_classes_invalid")
        if self.provenance != "suppressed" and self.provenance != least_real(
            self.input_classes
        ):
            raise ValueError("provenance_mismatch")
        if "user_input" in self.input_classes and self.evidence_status != "inferred":
            raise ValueError("user_input_status")
        if self.unit == "calendar_date":
            if (
                type(self.value) is not str
                or re.fullmatch(r"[1-9][0-9]{3}-[0-9]{2}-[0-9]{2}", self.value) is None
            ):
                raise ValueError("calendar_date_invalid")
            try:
                date.fromisoformat(self.value)
            except ValueError:
                raise ValueError("calendar_date_invalid") from None
            if (
                self.provenance,
                self.input_classes,
                self.evidence_status,
                self.reliability,
            ) != ("public", ["public"], "observed", "not_applicable"):
                raise ValueError("published_status_invalid")
        elif self.unit in {"calendar_month", "calendar_year"}:
            if (
                type(self.value) is not str
                or re.fullmatch(
                    r"[1-9][0-9]{3}-(0[1-9]|1[0-2])"
                    if self.unit == "calendar_month"
                    else r"[1-9][0-9]{3}",
                    self.value,
                )
                is None
            ):
                raise ValueError("calendar_month_invalid")
            if (
                self.provenance,
                self.input_classes,
                self.evidence_status,
                self.reliability,
            ) != ("public", ["public"], "observed", "not_applicable"):
                raise ValueError("published_status_invalid")
        elif self.unit == "published_text":
            text = self.value
            if type(text) is not str or not 1 <= len(text) <= 200:
                raise ValueError("published_text_length")
            if text != text.strip() or not any(c in "0123456789" for c in text):
                raise ValueError("published_text_form")
            if any(
                (c.isdigit() and c not in "0123456789")
                or unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"}
                for c in text
            ):
                raise ValueError("published_text_character")
            if re.search(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])", text):
                raise ValueError("published_text_identifier")
            if (
                self.provenance,
                self.input_classes,
                self.evidence_status,
                self.reliability,
            ) != ("public", ["public"], "observed", "not_applicable"):
                raise ValueError("published_status_invalid")
        elif self.provenance == "suppressed":
            if self.value is not None:
                raise ValueError("suppressed_value")
        elif self.value is None:
            raise ValueError("value_missing")
        elif self.unit == "size_band":
            if type(self.value) is not str or SIZE_BAND.fullmatch(self.value) is None:
                raise ValueError("size_band_invalid")
        else:
            if type(self.value) not in (int, float, Decimal):
                raise ValueError("number_required")
            number = Decimal(str(self.value))
            if not number.is_finite():
                raise ValueError("number_nonfinite")
            if self.unit == "count" and number != number.to_integral_value():
                raise ValueError("count_fractional")
        return self


def fact_id(
    *,
    release_id: str,
    metric_key: str,
    geography: Mapping[str, str],
    period: str,
    qualifiers: Mapping[str, str],
) -> str:
    """DAT-93: UTF-8, sorted object keys, compact JSON, no tool-call fields."""
    if metric_key not in METRIC_KEYS:
        raise ValueError("metric_unknown")
    if any(
        k not in QUALIFIER_KEYS or type(v) is not str for k, v in qualifiers.items()
    ):
        raise ValueError("qualifier_unknown")
    data = dict(
        release_id=release_id,
        metric_key=metric_key,
        geography=dict(geography),
        period=period,
        qualifiers=dict(qualifiers),
    )
    encoded = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return "f_" + sha256(encoded).hexdigest()[:32]


def validate_chain(
    lineage_ref: str,
    lineage_rows: Sequence[Mapping[str, object]],
    source_rows: Sequence[Mapping[str, object]],
    *,
    required_sources: Sequence[SourceChain] = (),
    numerator_table: str | None = None,
) -> str | None:
    """Return a closed refusal reason, or None. Never create or repair lineage."""
    lines = [r for r in lineage_rows if r.get("lineage_id") == lineage_ref]
    if not lines:
        return "lineage_missing"
    resolved = []
    for line in lines:
        table, transform = line.get("table_name"), line.get("transform")
        if not isinstance(table, str) or not table:
            return "lineage_table_missing"
        if numerator_table is not None and table != numerator_table:
            return "lineage_numerator_mismatch"
        if not (
            lineage_ref == "lin_" + table
            or lineage_ref.startswith("lin_" + table + "_")
        ):
            return "lineage_table_mismatch"
        if (
            not isinstance(transform, str)
            or re.fullmatch(
                r"[a-zA-Z_][a-zA-Z_0-9.]*\.[a-zA-Z_][a-zA-Z_0-9]*@[^\s@]+", transform
            )
            is None
        ):
            return "lineage_transform_missing"
        if line.get("input_class") != "public":
            return "lineage_class_invalid"
        sources = [
            s for s in source_rows if s.get("source_id") == line.get("source_id")
        ]
        if len(sources) != 1:
            return "source_missing"
        source = sources[0]
        for key in ("publisher", "title", "licence", "url"):
            if not isinstance(source.get(key), str) or not str(source[key]).strip():
                return "source_" + key + "_missing"
        digest = source.get("sha256")
        if not isinstance(digest, str) or HASH.fullmatch(digest) is None:
            return "source_hash_missing"
        retrieved = source.get("retrieved_on")
        if type(retrieved) is not date:
            return "source_retrieval_missing"
        resolved.append(source)
    for required in required_sources:
        if not any(
            (
                s["publisher"],
                s["title"],
                s["url"],
                s["licence"],
                str(s["retrieved_on"]),
                s["sha256"],
            )
            == (
                required.publisher,
                required.dataset,
                required.url,
                required.licence,
                required.retrieved,
                required.sha256,
            )
            for s in resolved
        ):
            return "lineage_inputs_incomplete"
    return None
