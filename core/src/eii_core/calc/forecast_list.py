"""C30 published/released admission; S2-T17 metadata, document 03 §7.3, S6-T14 step-one handoff.

Row-carried units are deliberately unspecified here. Display scales are the
retained part-A assumption (OI-320), not a claim about publisher precision.
"""

from dataclasses import dataclass

DEFINITION_VERSION = "c30-series-v3"
HORIZON = 1
NONNEGATIVE = True
ERROR_PLACES = 2
SEASONS = (("month", 12), ("quarter", 4), ("year", 1))
RANGE_CAVEAT = "forecast_backtest_range"
SYNTHETIC_CAVEATS = ("synthetic_not_evidence_about_qatar", "synthetic_change")
WORK_FEEDS = ("business_register.v1", "employment.v1", "wages.v1")
RESIDENCE_FEEDS = (
    "business_register.v1",
    "employment.v1",
    "residence.v1",
    "wages.v1",
)


@dataclass(frozen=True)
class Definition:
    key: str
    state: str
    tables: tuple[str, ...]
    input_class: str
    frequency: str
    levels: tuple[str, ...]
    subjects: tuple[str, ...]
    measures: tuple[str, ...]
    unit: str | None
    places: int
    caveats: tuple[str, ...]
    open_reason: str = ""
    confirmed_sources: tuple[str, ...] = ()

    @property
    def season(self) -> int:
        return dict(SEASONS)[self.frequency]

    @property
    def horizon(self) -> int:
        return HORIZON

    @property
    def nonnegative(self) -> bool:
        return NONNEGATIVE


DEFINITIONS = (
    Definition(
        "licence_issues",
        "held",
        ("pub_licence_issued",),
        "public",
        "month",
        ("municipality",),
        ("municipality",),
        ("issued_count",),
        "count",
        0,
        ("openings_incomplete",),
    ),
    Definition(
        "licence_cancellations",
        "held",
        ("pub_licence_cancelled",),
        "public",
        "month",
        ("municipality",),
        ("municipality",),
        ("cancelled_count",),
        "count",
        0,
        (),
    ),
    Definition(
        "property_prices",
        "held",
        ("pub_property_sale",),
        "public",
        "year",
        ("district",),
        ("district",),
        ("median_price_per_m2",),
        "qar_per_m2",
        2,
        ("deal_count_shown",),
    ),
    Definition(
        "hotel_demand_and_room_rates",
        "held",
        ("pub_hotel_monthly",),
        "public",
        "month",
        ("national",),
        ("national",),
        ("demand", "adr"),
        None,
        2,
        (),
    ),
    Definition(
        "announced_investment",
        "held",
        ("fdi_projects",),
        "public",
        "year",
        ("national", "municipality"),
        ("sector",),
        ("project_count", "announced_capex"),
        None,
        2,
        ("fdi_estimates",),
    ),
    Definition(
        "construction_pipeline",
        "held",
        ("pub_building_permits",),
        "public",
        "year",
        ("municipality",),
        ("municipality",),
        ("completion_certificates",),
        "count",
        0,
        ("permit_not_start",),
    ),
    Definition(
        "consumer_prices",
        "open",
        ("pub_price_index",),
        "public",
        "month",
        (),
        (),
        (),
        None,
        0,
        (),
        "publisher_or_licence_unconfirmed",
    ),
    Definition(
        "producer_prices",
        "open",
        (),
        "public",
        "",
        (),
        (),
        (),
        None,
        0,
        (),
        "no_source_table",
    ),
    Definition(
        "imports_by_product",
        "open",
        ("pub_customs_import",),
        "public",
        "month",
        (),
        (),
        (),
        None,
        0,
        (),
        "past_count_not_stated",
    ),
    Definition(
        "expected_households_and_workers",
        "open",
        (),
        "public",
        "",
        (),
        (),
        (),
        None,
        0,
        (),
        "no_conversion_parameter_source_table",
    ),
    Definition(
        "property_prices_quarterly",
        "open",
        ("pub_property_quarter",),
        "public",
        "quarter",
        (),
        (),
        (),
        None,
        0,
        (),
        "awaiting_reviewed_use_map_and_district_crosswalk",
    ),
    Definition(
        "establishments_by_area",
        "conditional",
        ("pub_register_snapshot",),
        "public",
        "month",
        ("area", "national"),
        ("area",),
        ("establishment_count",),
        "count",
        0,
        (),
    ),
    Definition(
        "pay_level",
        "released",
        ("worker_pay", "resident_pay"),
        "synthetic",
        "month",
        ("area", "municipality", "national"),
        ("area",),
        ("mean_wage",),
        "qar_per_month",
        0,
        SYNTHETIC_CAVEATS,
        confirmed_sources=RESIDENCE_FEEDS,
    ),
    Definition(
        "earner_count",
        "released",
        ("worker_pay", "resident_pay"),
        "synthetic",
        "month",
        ("area", "national"),
        ("area",),
        ("earner_count",),
        "count",
        0,
        SYNTHETIC_CAVEATS,
        confirmed_sources=RESIDENCE_FEEDS,
    ),
    Definition(
        "wage_bill",
        "released",
        ("worker_pay", "resident_pay"),
        "synthetic",
        "month",
        ("area", "municipality", "national"),
        ("area",),
        ("wage_bill",),
        "qar",
        0,
        SYNTHETIC_CAVEATS,
        confirmed_sources=RESIDENCE_FEEDS,
    ),
    Definition(
        "stayer_index",
        "released",
        ("month_change",),
        "synthetic",
        "month",
        ("municipality", "national"),
        ("area",),
        ("stayer_wage_index",),
        "index",
        1,
        SYNTHETIC_CAVEATS,
        confirmed_sources=RESIDENCE_FEEDS,
    ),
    Definition(
        "employment_by_area",
        "released",
        ("worker_pay",),
        "synthetic",
        "month",
        ("area", "national"),
        ("area",),
        ("earner_count",),
        "count",
        0,
        SYNTHETIC_CAVEATS,
        confirmed_sources=WORK_FEEDS,
    ),
    Definition(
        "employment_by_occupation_residence",
        "released",
        ("occupation_pay",),
        "synthetic",
        "month",
        ("area", "national"),
        ("area",),
        ("earner_count",),
        "count",
        0,
        SYNTHETIC_CAVEATS,
        confirmed_sources=RESIDENCE_FEEDS,
    ),
    Definition(
        "employment_by_occupation_workplace",
        "released",
        ("occupation_pay",),
        "synthetic",
        "month",
        ("area", "national"),
        ("area",),
        ("earner_count",),
        "count",
        0,
        SYNTHETIC_CAVEATS,
        confirmed_sources=WORK_FEEDS,
    ),
)


def definition(key: str) -> Definition | None:
    if type(key) is not str:
        raise ValueError("exact text required")
    return next((row for row in DEFINITIONS if row.key == key), None)
