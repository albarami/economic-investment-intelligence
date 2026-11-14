"""S2-T17 source admission only; C30 backtests and release checks remain mandatory."""

from __future__ import annotations

from dataclasses import dataclass, fields

from eii_custodian.publicdata.fetch.registry import Entry, RegistryError

# Closed Public list of PUB-103; the released monthly statistics live elsewhere.
FREQUENCIES = {
    "licence_issues": "month",
    "licence_cancellations": "month",
    "property_prices": "year",
    "hotel_demand_and_room_rates": "month",
    "consumer_prices": "month",
    "producer_prices": "",
    "imports_by_product": "month",
    "announced_investment": "year",
    "construction_pipeline": "year",
    "expected_households_and_workers": "",
    "property_prices_quarterly": "quarter",
}
DISTRICT_SERIES = {"property_prices", "property_prices_quarterly"}
SOURCES = {
    "licence_issues": ("lic_issued",),
    "licence_cancellations": ("lic_cancelled",),
    "property_prices": ("prop_sales",),
    "hotel_demand_and_room_rates": ("hotel_segment",),
    "consumer_prices": ("cpi_group",),
    "producer_prices": (),
    "imports_by_product": ("cus_imp_2019", "cus_imp_2025"),
    "announced_investment": ("fdi_projects",),
    "construction_pipeline": (
        "permits_muni/total-building-completion-certificates-issued-by-municipality-and-type-of-building-type-of",
    ),
    "expected_households_and_workers": (),
    "property_prices_quarterly": (
        "prop_sales",
        "prop_resi_units/weekly-residential-units-sales-bulletin",
    ),
}


@dataclass(frozen=True)
class ForecastSeries:
    """Table-level history evidence, not proof of history at every forecast grain."""

    key: str
    state: str
    source_keys: tuple[str, ...]
    table: str
    period: str
    frequency: str
    past_count: int | None
    subject: str
    reason: str
    note: str = ""
    evidence: str = ""


def load_forecast_series(
    rows: object, entries: tuple[Entry, ...]
) -> tuple[ForecastSeries, ...]:
    """Validate the forecast_series block against the admitted registry rows."""
    if not isinstance(rows, list):
        raise RegistryError("forecast_series is not a list")
    result = tuple(_series(row, entries) for row in rows)
    keys = [row.key for row in result]
    if len(keys) != len(set(keys)):
        raise RegistryError("duplicate forecast series")
    return result


def _series(raw: object, entries: tuple[Entry, ...]) -> ForecastSeries:
    if not isinstance(raw, dict):
        raise RegistryError("forecast series is not a map")
    if set(raw) - {field.name for field in fields(ForecastSeries)}:
        raise RegistryError("unknown field in forecast series")
    text = {}
    for name in (
        "key",
        "state",
        "table",
        "period",
        "frequency",
        "subject",
        "reason",
        "note",
        "evidence",
    ):
        value = raw.get(name, "")
        if not isinstance(value, str):
            raise RegistryError(name + " is not text")
        text[name] = value
    key = text["key"]
    if key not in FREQUENCIES:
        raise RegistryError("unknown series: " + key)
    state = text["state"]
    if state not in {"held", "open"}:
        raise RegistryError("unknown forecast state")
    if key in DISTRICT_SERIES and text["subject"] != "district":
        raise RegistryError("property series requires district subject")
    if key == "property_prices_quarterly" and state != "open":
        raise RegistryError("quarterly series awaits S2-T19")
    sources = raw.get("source_keys")
    if not isinstance(sources, list) or not all(
        isinstance(item, str) for item in sources
    ):
        raise RegistryError("source_keys is not a list of text")
    if tuple(sources) != SOURCES[key]:
        raise RegistryError("source keys outside closed series mapping")
    count = raw.get("past_count")
    if state == "held":
        if type(count) is not int or count <= 0:
            raise RegistryError("held past_count must be a positive integer")
        if not text["period"].strip():
            raise RegistryError("held period is missing")
        if not text["frequency"] or text["frequency"] != FREQUENCIES[key]:
            raise RegistryError("held frequency does not match series")
        if text["reason"]:
            raise RegistryError("held reason must be empty")
        by_key = {entry.key: entry for entry in entries}
        if not sources or any(source not in by_key for source in sources):
            raise RegistryError("held source is not registered")
        if any(
            text["table"] not in by_key[source].release_tables for source in sources
        ):
            raise RegistryError("held table is not registered for its source")
    else:
        if count is not None:
            raise RegistryError("open series carries past_count")
        if not text["reason"].strip():
            raise RegistryError("open reason is missing")
    return ForecastSeries(**text, source_keys=tuple(sources), past_count=count)


def forecast_refusal_reason(
    key: str, series: tuple[ForecastSeries, ...], entries: tuple[Entry, ...]
) -> str:
    """Return the source gate's refusal reason, or empty text when admitted.

    Admission does not replace C30's actual grain, continuity, unit and backtest
    checks, nor establish that a table is mounted in the current release.
    """
    by_key = {row.key: row for row in series}
    if key not in by_key:
        raise RegistryError("unknown series: " + key)
    row = by_key[key]
    if row.state == "open":
        return row.reason
    sources = {entry.key: entry for entry in entries}
    for source in row.source_keys:
        if source not in sources:
            return "source_not_registered"
        if row.table not in sources[source].release_tables:
            return "table_not_registered"
        if sources[source].skip_reason:
            return sources[source].skip_reason
    return ""


def forecastable(
    key: str, series: tuple[ForecastSeries, ...], entries: tuple[Entry, ...]
) -> bool:
    """Whether S6-T14 may proceed to its release and C30 checks for this source."""
    return forecast_refusal_reason(key, series, entries) == ""
