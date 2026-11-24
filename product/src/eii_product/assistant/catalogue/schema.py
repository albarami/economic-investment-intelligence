"""Closed types for the four catalogues and a returned fact."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

FILE_NAMES = ("claims.yaml", "components.yaml", "fragments.yaml", "questions.yaml")
FILE_VERSION = 1

KEY = re.compile(r"^[a-z][a-z0-9_]*$")
FACT_ID = re.compile(r"^f_[0-9a-f]{32}$")
LINEAGE = re.compile(r"^lin_[a-z0-9_]+$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")

PERIOD_PATTERNS = {
    "calendar_date": re.compile(
        r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"
    ),
    "calendar_month": re.compile(r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$"),
    "calendar_year": re.compile(r"^[1-9][0-9]{3}$"),
    "month_window": re.compile(
        r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])/[1-9][0-9]{3}-(0[1-9]|1[0-2])$"
    ),
}

PLAYBOOKS = frozenset(
    {
        "site_check",
        "staffing_and_pay",
        "costs_and_suppliers",
        "market_entry",
        "rank_areas",
        "site_fit",
        "customer_finder",
        "partner_finder",
        "labour_market",
        "where_to_grow",
        "serve_region",
        "depot_options",
        "branch_check",
    }
)
PERSONAS = frozenset({"international", "local", "start_up"})
SUBJECTS = frozenset(
    {
        "area",
        "place_public",
        "fdi_project",
        "register_company",
        "district",
        "municipality",
        "sector",
        "national",
        "scenario",
    }
)
SECTIONS = frozenset({"observed", "inferred"})
STRENGTHS = frozenset({"strong", "indicative", "illustrative"})
GEOGRAPHY_KINDS = frozenset(
    {"release_units", "public", "national", "user_scenario", "area_shape"}
)
PROVENANCE_ALLOWED = frozenset({"public", "synthetic", "simulated"})
PROVENANCE_ALL = PROVENANCE_ALLOWED | frozenset({"suppressed"})
EVIDENCE_STATUSES = frozenset({"observed", "inferred", "still_to_test"})
PUBLIC_BREAKDOWNS = frozenset({"sex", "nationality"})
SIMULATED_BREAKDOWNS = frozenset({"age_band", "gender", "nationality_group"})
BREAKDOWNS = PUBLIC_BREAKDOWNS | SIMULATED_BREAKDOWNS | frozenset({"none"})

FACT_UNITS = frozenset(
    {
        "count",
        "qar_per_month",
        "qar",
        "qar_thousand",
        "qar_million",
        "qar_per_kg",
        "qar_per_m2",
        "usd_million",
        "kwh",
        "riders",
        "ratio",
        "percent",
        "index",
        "relative_index",
        "wage_band",
        "size_band",
        "volume_band",
        "metres",
        "minutes",
        "covers_per_day",
        "people_per_km2",
        "tonnage",
        "rank",
        "direction",
        "calendar_date",
        "calendar_month",
        "calendar_year",
        "published_text",
        "radiance_nw_cm2_sr",
        "qar_per_ft2",
        "years",
    }
)
MONEY_UNITS = frozenset(
    {
        "qar_per_month",
        "qar",
        "qar_thousand",
        "qar_million",
        "qar_per_kg",
        "qar_per_m2",
        "usd_million",
        "qar_per_ft2",
    }
)
ESTIMATE_SHARE_SCORE = frozenset(
    {
        "estimate_low",
        "estimate_middle",
        "estimate_high",
        "estimate_driver_swing",
        "catchment_share_outlet",
        "catchment_share_competitors",
    }
)

_COUNT = frozenset({"count"})
_PERCENT = frozenset({"percent"})
_QAR = frozenset({"qar"})
_RATIO = frozenset({"ratio"})

# DAT-141: the register's published company attribute, never a worker split.
# Extend only with explicitly defined public-card fields, never aggregate metrics.
PUBLIC_REGISTER_CARD_METRICS = frozenset({"establishment_nationality"})
REGISTER_COMPANY_METRICS = PUBLIC_REGISTER_CARD_METRICS | {"employee_count"}

METRIC_UNITS: dict[str, frozenset[str]] = {
    "forecast_value": FACT_UNITS,
    "forecast_low": FACT_UNITS,
    "forecast_high": FACT_UNITS,
    "forecast_backtest_error": _RATIO,
    "forecast_backtest_points": _COUNT,
    "forecast_inside": _COUNT,
    "forecast_tested": _COUNT,
    "base_rate_share": _PERCENT,
    "base_rate_numerator": _COUNT,
    "base_rate_denominator": _COUNT,
    "base_rate_low": _PERCENT,
    "base_rate_high": _PERCENT,
    "present_by_pay_band": _COUNT,
    "estimate_low": _QAR,
    "estimate_middle": _QAR,
    "estimate_high": _QAR,
    "estimate_driver_swing": _QAR,
    "catchment_share_outlet": _PERCENT,
    "catchment_share_competitors": _PERCENT,
    "scenario_low": _QAR,
    "scenario_middle": _QAR,
    "scenario_high": _QAR,
    "venue_busyness_index": frozenset({"relative_index"}),
    "night_lights_radiance": frozenset({"radiance_nw_cm2_sr"}),
    "population_grid_people": _COUNT,
    "register_openings": _COUNT,
    "register_closures": _COUNT,
    "register_without_date": _COUNT,
    "talent_pool": _COUNT,
    "competing_demand": _COUNT,
    "talent_ratio": _RATIO,
    "commute_total": _COUNT,
    "sites_covered_demand": _COUNT,
    "sites_set_cover_count": _COUNT,
    "branch_shared_reach": _COUNT,
    "branch_shared_reach_share": _PERCENT,
    "sites_hold_runs": _COUNT,
    "sites_runs": _COUNT,
    "sites_sensitivity_index": _RATIO,
    "price_per_ft2_median": frozenset({"qar_per_ft2"}),
    "land_price_per_ft2_median": frozenset({"qar_per_ft2"}),
    "price_deal_count": _COUNT,
    "land_deal_count": _COUNT,
    "price_deal_value": _QAR,
    "guide_land_price": frozenset({"qar_per_ft2", "qar_per_m2"}),
    "unit_price_median": frozenset({"qar", "qar_per_m2"}),
    "affordability_years": frozenset({"years"}),
    "credit_growth": _PERCENT,
    "sector_growth": _PERCENT,
    "firms_per_tower": _COUNT,
    "employee_count": _COUNT,
    "establishment_nationality": frozenset({"published_text"}),
}

BRIEF_ORDER = (
    "catalogue_version",
    "headline_key",
    "decision_template_key",
    "observed",
    "inferred",
    "still_to_test",
    "not_measured",
    "next_questions",
    "layout",
    "stage",
)
CLAIM_FIELDS = frozenset(
    {
        "claim_key",
        "section",
        "subject",
        "slots",
        "required_caveat_keys",
        "required_companions",
        "strengths_allowed",
        "template_en",
        "template_ar",
    }
)
SLOT_FIELDS = frozenset(
    {
        "name",
        "metric_key",
        "unit",
        "geography_role",
        "period_rule",
        "allowed_provenance",
        "breakdown",
    }
)
COMPONENT_FIELDS = frozenset({"component_key", "max_count", "props"})
QUESTION_FIELDS = frozenset(
    {"question_key", "playbook", "personas", "slots", "template_en", "template_ar"}
)
HEADLINE_FIELDS = ("template_en", "template_ar")
DECISION_FIELDS = ("lead_en", "lead_ar", "cheapest_test_en", "cheapest_test_ar")
DIRECTIVE_KINDS = frozenset(
    {
        "target",
        "enumeration",
        "identifier",
        "boolean",
        "identifier_list",
        "area_ids",
        "fact_id",
    }
)
STAGE_DIRECTIVES = (
    "fly",
    "layer",
    "highlight",
    "rings",
    "dial",
    "hour",
    "day",
    "month",
    "split",
    "set_scenario_inputs",
)


def join_path(prefix: str, suffix: str) -> str:
    """Join an item path and a suffix with a dot."""
    if prefix:
        return f"{prefix}.{suffix}"
    return suffix


@dataclass(frozen=True)
class Refusal:
    """One refused catalogue rule, with the path of the item that failed."""

    rule_code: str
    item_path: str


@dataclass(frozen=True)
class Slot:
    """One fact slot on a claim or a question."""

    name: str
    metric_key: str
    unit: str
    geography_role: str
    period_rule: str
    allowed_provenance: tuple[str, ...]
    breakdown: str


@dataclass(frozen=True)
class Claim:
    """One claim definition."""

    key: str
    section: str
    subject: str
    slots: tuple[Slot, ...]
    required_caveat_keys: tuple[str, ...]
    required_companions: tuple[str, ...]
    strengths_allowed: tuple[str, ...]
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Component:
    """One layout component."""

    key: str
    max_count: int
    props: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class Fragment:
    """One headline or decision fragment."""

    key: str
    kind: str
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Question:
    """One next-question definition."""

    key: str
    playbook: str
    personas: tuple[str, ...]
    slots: tuple[Slot, ...]
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FieldSpec:
    """One property of a stage directive."""

    name: str
    kind: str
    values: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    const: bool | None = None


@dataclass(frozen=True)
class Alternative:
    """One allowed shape of a directive's properties."""

    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class Directive:
    """One stage directive schema."""

    name: str
    alternatives: tuple[Alternative, ...]


@dataclass(frozen=True)
class Catalogue:
    """The four files, the directive schemas and the computed version."""

    version: str
    claims: tuple[Claim, ...]
    components: tuple[Component, ...]
    fragments: tuple[Fragment, ...]
    questions: tuple[Question, ...]
    directives: tuple[Directive, ...]

    def find_claim(self, key: str) -> Claim | None:
        """Return the claim with this key, if the catalogue holds it."""
        return _find(self.claims, key)

    def find_component(self, key: str) -> Component | None:
        """Return the component with this key, if the catalogue holds it."""
        return _find(self.components, key)

    def find_fragment(self, key: str) -> Fragment | None:
        """Return the fragment with this key, if the catalogue holds it."""
        return _find(self.fragments, key)

    def find_question(self, key: str) -> Question | None:
        """Return the question with this key, if the catalogue holds it."""
        return _find(self.questions, key)

    def find_directive(self, name: str) -> Directive | None:
        """Return the directive schema with this name, if the catalogue holds it."""
        for item in self.directives:
            if item.name == name:
                return item
        return None


def _find[Item: (Claim, Component, Fragment, Question)](
    items: tuple[Item, ...], key: str
) -> Item | None:
    for item in items:
        if item.key == key:
            return item
    return None


@dataclass(frozen=True)
class ReturnedFact:
    """A fact a tool returned, plus the metric key beside it."""

    fact_id: str
    metric_key: str
    unit: str
    period: str
    geography_kind: str
    provenance: str
    evidence_status: str
    lineage_ref: str | None
    breakdown: str = "none"


Facts = Mapping[str, ReturnedFact]
