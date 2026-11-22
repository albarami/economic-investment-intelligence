"""Offline selected-cache build, internal evidence and fail-closed display output.

Missing confirmed fields stay named blockers. Regression evidence is never a
release fact; it remains available while OI-03 keeps the display gate closed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from eii_core.calc.facts import CalculationFact, Measure, SourceChain
from eii_core.calc.public_series import (
    C2_CALENDAR,
    C2_METHOD_VERSION,
    ZERO,
    Group,
    bulk_months,
    decomposition,
    growth,
    ratio,
    rounded,
    unit_value,
)
from eii_core.calc.sector_economics import Component, sector_norms
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.frame.crosswalk import (
    load_municipality_names,
    normalise_name,
)
from eii_custodian.publicdata.review.activity import (
    IsicClass,
    SpineError,
    class_bucket_counts,
    entry_by_key,
    parse_feed_rows,
)
from eii_custodian.publicdata.series.baskets import (
    reviewed_inputs,
    validate_source_review,
)
from eii_custodian.publicdata.series.frame import (
    MunicipalityFrameRefused,
    frame_municipalities,
)
from eii_custodian.publicdata.series.parse import (
    FIELD_MAP,
    SERIES_REFUSALS,
    Municipality,
    SeriesRefused,
    confirmed_rows,
    country_crosswalk,
    customs_code,
    mapping_gaps,
    municipality_names,
    selected_source,
    source_period,
)
from eii_custodian.publicdata.series.reconcile import (
    R1_SOURCES,
    R2_SOURCES,
    Resolution,
    emit_fact,
    wage_evidence,
)
from eii_custodian.publicdata.series.support import SUPPORT_KEYS, load_support

if TYPE_CHECKING:
    from eii_custodian.publicdata.fetch.build import FetchFailure

DEPENDENCIES = {
    "PUB-62": ("util_elec",),
    "PUB-63": ("wage_occ",),
    "PUB-64": ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"),
    "PUB-65": ("cus_imp_2025",),
    "PUB-66": ("cus_imp_2025",),
    "PUB-67": ("lic_active",),
    "PUB-68": ("lic_cancelled",),
    "PUB-69": ("lic_issued",),
    "PUB-70": ("transit_monthly",),
}
METHOD = "public-series"
VERSION = "1"
CHAIN_FIELDS = (
    "source_id",
    "publisher",
    "slug",
    "licence_id",
    "licence_basis",
    "retrieved_utc",
    "sha256",
    "fetch_url",
)


def validate_figure(figure: Mapping[str, object]) -> None:
    """A missing method/version or source chain is a build failure (MTH-08)."""
    for key in ("method", "method_version"):
        if not isinstance(figure.get(key), str) or not str(figure[key]).strip():
            raise ValueError("missing " + key)
    chain = figure.get("source_chain")
    if not isinstance(chain, list) or not chain:
        raise ValueError("missing source_chain")
    for source in chain:
        if not isinstance(source, dict) or any(
            not isinstance(source.get(key), str) or not source[key].strip()
            for key in CHAIN_FIELDS
        ):
            raise ValueError("incomplete source_chain")
        if re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) is None:
            raise ValueError("invalid source_chain hash")
    tables = figure.get("release_tables")
    if not isinstance(tables, list) or not tables:
        raise ValueError("missing source_chain release_tables")
    if not figure.get("field_mapping"):
        raise ValueError("missing source_chain field_mapping")


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    )


def _envelope(
    sources: Sequence[str], receipts: Mapping[str, dict[str, object]]
) -> dict[str, object]:
    chain = [{key: receipts[source][key] for key in CHAIN_FIELDS} for source in sources]
    return {
        "method": METHOD,
        "method_version": C2_METHOD_VERSION if "lic_cancelled" in sources else VERSION,
        "source_chain": chain,
        "release_tables": sorted(
            {target[0] for source in sources for target in FIELD_MAP[source].values()}
        ),
        "field_mapping": {source: FIELD_MAP[source] for source in sources},
    }


def _groups(
    rows: Sequence[dict[str, object]], source: str
) -> dict[str, dict[str, Group]]:
    dimension = "occupation" if source == "wage_occ" else "economic_activity"
    years: dict[str, dict[str, Group]] = {}
    for row in rows:
        year = str(row["year"])
        key = json.dumps([row["gender"], row[dimension]], ensure_ascii=False)
        groups = years.setdefault(year, {})
        count = Decimal(str(row["paid_employment_workers"]))
        if count == ZERO:
            continue
        if key in groups:
            raise ValueError(source + " duplicate wage group")
        groups[key] = (count, Decimal(str(row["monthly_average_wage_qr"])))
    return years


def contract_rows(
    source: str,
    rows: Sequence[dict[str, object]],
    *,
    municipalities: Sequence[Municipality] = (),
) -> list[dict[str, object]]:
    """Long-form contracts copy values, never replacing a published wage."""
    output: list[dict[str, object]] = []
    countries = country_crosswalk()
    names = municipality_names(municipalities)
    for row in rows:
        if source == "util_elec":
            output.append(
                {
                    "zone_code": row["zone_number"],
                    "period": row["year"],
                    "utility": "electricity",
                    "value": row["value"],
                    "unit": "kWh",
                    "partial_year": row["year"] == "2026",
                    "caveat_keys": ["partial_year_january_august"]
                    if row["year"] == "2026"
                    else [],
                }
            )
        elif source in R2_SOURCES:
            dimension = "occupation" if source == "wage_occ" else "economic_activity"
            key = "&".join(
                f"{name}={quote(str(row[name]), safe='')}"
                for name in sorted(("gender", dimension))
            )
            for field, indicator, unit in (
                ("paid_employment_workers", "paid_workers", "persons"),
                ("monthly_average_wage_qr", "monthly_average_wage", "QAR"),
            ):
                output.append(
                    {
                        "table_code": source,
                        "period": row["year"],
                        "breakdown_key": key,
                        "indicator": indicator,
                        "value": row[field],
                        "unit": unit,
                    }
                )
        elif source in R1_SOURCES:
            for field, (_, target) in FIELD_MAP[source].items():
                if not target.startswith("value:"):
                    continue
                indicator = target.split(":", 1)[1]
                dimensions = [
                    name
                    for name in (
                        "type_of_commodity",
                        "type_of_service",
                        "size_of_establishment",
                    )
                    if name in row
                ]
                if dimensions:
                    indicator += ":" + quote(str(row[dimensions[0]]), safe="")
                unit = "QAR_thousand" if "1_000_qr" in field else "QAR"
                if field.startswith("percentage_"):
                    unit = "percent"
                elif field.startswith("number_of_"):
                    unit = "count"
                output.append(
                    {
                        "activity_code": str(row["activity_code"]),
                        "period": row["year"],
                        "indicator": indicator,
                        "value": row[field],
                        "unit": unit,
                    }
                )
        elif source == "transit_monthly":
            period = source_period(source, row["year"], row["month"])
            for field, mode in (
                ("public_transport_buses", "bus"),
                ("doha_metro", "metro"),
                ("lusail_tram", "tram"),
            ):
                output.append(
                    {
                        "period": period,
                        "mode": mode,
                        "riders": row[field],
                        "anomaly_flag": mode == "tram" and period == "2026-01",
                    }
                )
        elif source.startswith("cus_imp_"):
            earlier = source == "cus_imp_2019"
            output.append(
                {
                    "period": source_period(
                        source,
                        row["lsn_year" if earlier else "year"],
                        row["lshhr_month" if earlier else "month"],
                    ),
                    "tariff_code": customs_code(
                        source, row["hs8" if earlier else "harmonized_system_code"]
                    ),
                    "description_en": row["details"],
                    "description_ar": row["ltfsyl"],
                    "origin_iso3": countries.get(str(row["country_of_origin"])),
                    "quantity": row["quantity"],
                    "quantity_unit": "not stated by the source",
                    "weight_kg": row["weight_kg" if earlier else "weight_in_kilograms"],
                    "value_qar": row[
                        "value_qr" if earlier else "value_in_qatari_riyals"
                    ],
                    "valuation_basis": "not stated by the source",
                }
            )
        elif source.startswith("lic_"):
            target, field = {
                "lic_active": ("active_count", "dd_lrkhs_lnsht"),
                "lic_cancelled": ("cancelled_count", "dd_lrkhs_lmlg"),
                "lic_issued": ("issued_count", "dd_lrkhs_lsdr"),
            }[source]
            # PUB-67 pins this snapshot; never use the publisher modified date.
            period = "2025-05"
            if source != "lic_active":
                year, month = (
                    ("sn_llg", "shhr_llg")
                    if source == "lic_cancelled"
                    else ("sn_lsdr", "shhr_lsdr")
                )
                period = source_period(source, row[year], row[month])
            converted = {
                "municipality_code": names.get(normalise_name(str(row["lbldy"]))),
                "activity_code": row["rmz_lnsht_ltjry"],
                "period": period,
                target: row[field],
            }
            if source == "lic_active":
                converted["activity_name_ar"] = row["lnsht_ltjry"]
            if source == "lic_issued":
                converted["caveat_keys"] = ["openings_incomplete"]
            output.append(converted)
        else:
            raise ValueError(source + " missing confirmed contract fields")
    return output


def _pub64_field(source: str, slot: str) -> str:
    """Resolve one semantic contract slot; never fall back to a source position."""
    fields = [
        field
        for field, target in FIELD_MAP[source].items()
        if target == ("pub_sector_accounts", slot)
    ]
    if len(fields) != 1:
        raise ValueError(source + ": one field required for " + slot)
    return fields[0]


def _pub64_checks(
    data: Mapping[str, list[dict[str, object]]],
    receipts: Mapping[str, dict[str, object]] | None,
) -> dict[str, str]:
    """Adapt PUB-64's published inputs to C4, with selected receipt lineage.

    Selection follows data_tests/test_pinned_methods.py::test_pinned_c4:
    case-insensitive component labels and group totals summed over the selected
    activity/year rows. There is no separate total row or production derivation.
    """
    chosen = {
        source: [
            row
            for row in data[source]
            if str(row[_pub64_field(source, "activity_code")]) == "561"
            and str(row[_pub64_field(source, "period")]) == "2022"
        ]
        for source in R1_SOURCES
    }
    if len(chosen["sec_hr_ind"]) != 1:
        raise ValueError("sec_hr_ind: one restaurant indicator row required")
    if not chosen["sec_hr_size"]:
        raise ValueError("sec_hr_size: restaurant size rows required")
    for source in ("sec_hr_goods", "sec_hr_serv", "sec_hr_size"):
        rows = chosen[source]
        if not rows:
            raise ValueError(source + ": restaurant rows required")
        label = _pub64_field(source, "indicator")
        if len({str(row[label]).casefold() for row in rows}) != len(rows):
            raise ValueError(source + ": duplicate restaurant source row")
    if receipts is None or not R1_SOURCES <= receipts.keys():
        raise ValueError("PUB-64 receipts required")
    chains: dict[str, SourceChain] = {}
    for source in sorted(R1_SOURCES):
        receipt = receipts[source]
        try:
            validate_figure(_envelope([source], receipts))
        except KeyError as exc:
            raise ValueError("PUB-64 incomplete receipt") from exc
        if receipt["source_id"] != source:
            raise ValueError("PUB-64 receipt source mismatch")
        chains[source] = SourceChain(
            lineage_ref=source + ":" + str(receipt["sha256"]),
            table="pub_sector_accounts",
            method=METHOD,
            version=VERSION,
            publisher=str(receipt["publisher"]),
            dataset=str(receipt["slug"]),
            url=str(receipt["fetch_url"]),
            licence=str(receipt["licence_id"]),
            retrieved=datetime.fromisoformat(str(receipt["retrieved_utc"]))
            .date()
            .isoformat(),
            sha256=str(receipt["sha256"]),
        )

    def number(value: object) -> Decimal:
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("PUB-64 numeric source field required") from exc

    def reading(value: object, unit: str, source: str = "sec_hr_ind") -> Measure:
        return Measure(
            value=number(value),
            unit=unit,
            period="2022",
            geography="national",
            geography_kind="national",
            input_class="public",
            sources=(chains[source],),
        )

    def indicator(slot: str) -> object:
        return chosen["sec_hr_ind"][0][_pub64_field("sec_hr_ind", "value:" + slot)]

    def size_total(slot: str) -> Decimal:
        field = _pub64_field("sec_hr_size", "value:" + slot)
        return sum((number(row[field]) for row in chosen["sec_hr_size"]), ZERO)

    employees = size_total("employees")
    components = []
    for source, group, slot, wanted in (
        (
            "sec_hr_goods",
            "goods",
            "intermediate_goods",
            (
                ("food_share_1dp", "Food Stuff"),
                ("beverages_share_1dp", "Beverages"),
            ),
        ),
        (
            "sec_hr_serv",
            "services",
            "intermediate_services",
            (("building_rent_share_1dp", "Rents of Buildings"),),
        ),
    ):
        label = _pub64_field(source, "indicator")
        field = _pub64_field(source, "value:" + slot)
        total = sum((number(row[field]) for row in chosen[source]), ZERO)
        for key, published_label in wanted:
            matching = [
                row
                for row in chosen[source]
                if str(row[label]).casefold() == published_label.casefold()
            ]
            if len(matching) != 1:
                raise ValueError(
                    source + ": one component required: " + published_label
                )
            components.append(
                Component(
                    key,
                    group,
                    reading(matching[0][field], "qar_thousand", source),
                    reading(total, "qar_thousand", source),
                    group,
                )
            )
    norms = sector_norms(
        employees=reading(employees, "count", "sec_hr_size"),
        productivity=reading(indicator("productivity_of_employee"), "qar"),
        compensation_thousand=reading(indicator("compensation"), "qar_thousand"),
        surplus_thousand=reading(indicator("operating_surplus"), "qar_thousand"),
        goods_percent=reading(indicator("goods_share"), "percent"),
        services_percent=reading(indicator("services_share"), "percent"),
        components=components,
    )
    result = {
        "establishments": str(size_total("establishments")),
        "employees": str(employees),
        "compensation": str(indicator("compensation")),
        "operating_surplus": str(indicator("operating_surplus")),
        "average_annual_wage": str(indicator("average_annual_wage")),
        "output_per_employee": str(indicator("productivity_of_employee")),
    }
    for key, norm in (
        ("goods_share_1dp", "goods_percent"),
        ("services_share_1dp", "services_percent"),
        ("compensation_share_1dp", "compensation_percent"),
        ("operating_surplus_share_1dp", "surplus_percent"),
        ("food_share_1dp", "food_share_1dp"),
        ("beverages_share_1dp", "beverages_share_1dp"),
        ("building_rent_share_1dp", "building_rent_share_1dp"),
    ):
        fact = norms[norm]
        if not isinstance(fact, CalculationFact) or not isinstance(fact.value, Decimal):
            raise ValueError("PUB-64 numeric C4 result required")
        result[key] = str(fact.value)
    return result


def compute_checks(
    data: Mapping[str, list[dict[str, object]]],
    *,
    isic_classes: Sequence[IsicClass] = (),
    municipalities: Sequence[Municipality] = (),
    activity_entry: Entry | None = None,
    receipts: Mapping[str, dict[str, object]] | None = None,
) -> dict[str, dict[str, str]]:
    """Only computable checks; no anchor is ever copied into an observed result."""
    checks: dict[str, dict[str, str]] = {}
    if "util_elec" in data:
        values = {
            (str(r["zone_number"]), str(r["year"])): Decimal(str(r["value"]))
            for r in data["util_elec"]
        }
        if len(values) != len(data["util_elec"]):
            raise ValueError("duplicate utility period")
        before, after = values[("69", "2021")], values[("69", "2025")]
        totals = {
            year: sum(
                (value for (_, period), value in values.items() if period == year), ZERO
            )
            for year in ("2021", "2025")
        }
        checks["PUB-62"] = {
            "zone_69_2021": str(before),
            "zone_69_2025": str(after),
            "ratio_2dp": rounded(ratio(after, before), 2),
            "sum_ratio_2dp": rounded(ratio(totals["2025"], totals["2021"]), 2),
        }
    if "wage_occ" in data:
        years = _groups(data["wage_occ"], "wage_occ")
        parts = decomposition(years["2020"], years["2025"])
        if parts["change"] == ZERO:
            raise ValueError("zero change has no mix share")
        checks["PUB-63"] = {
            "populated_groups": str(parts["groups"]),
            "mean_2020": rounded(parts["mean_before"], 0),
            "mean_2025": rounded(parts["mean_after"], 0),
            "rise": rounded(parts["change"], 0),
            "rise_percent_1dp": rounded(
                growth(parts["mean_before"], parts["mean_after"]), 1
            ),
            "within_groups": rounded(parts["within"], 0),
            "mix": rounded(parts["mix"], 0),
            "mix_share_1dp": rounded(parts["mix"] / parts["change"] * 100, 1),
        }
    if R1_SOURCES <= data.keys():
        checks["PUB-64"] = _pub64_checks(data, receipts)
    if "cus_imp_2025" in data:
        rows = [r for r in data["cus_imp_2025"] if r["year"] == "2025"]
        total = sum((Decimal(str(r["value_in_qatari_riyals"])) for r in rows), ZERO)
        checks["PUB-66"] = {
            "rows_2025": str(len(rows)),
            "value_bn_2dp": rounded(total / Decimal(10**9), 2),
        }
    if "cus_imp_2025" in data:
        heading = [
            r
            for r in data["cus_imp_2025"]
            if r["year"] == "2025"
            and str(
                customs_code("cus_imp_2025", r["harmonized_system_code"])
            ).startswith("1902")
        ]
        check = {"valuation_basis_present": "true"}
        for country, key in (
            ("Italy", "italy_2dp"),
            ("Saudi Arabia", "saudi_arabia_2dp"),
        ):
            value, _, _ = unit_value(
                [
                    (
                        Decimal(str(r["value_in_qatari_riyals"])),
                        Decimal(str(r["weight_in_kilograms"])),
                        "kg",
                    )
                    for r in heading
                    if r["country_of_origin"] == country
                ]
            )
            if value is not None:
                check[key] = rounded(value, 2)
        # Basket review is intentionally absent: arithmetic cannot approve editorial lines.
        checks["PUB-65"] = check
    if "lic_active" in data:
        active = data["lic_active"]
        if activity_entry is None:
            raise ValueError("PUB-67 activity entry required")
        if not isic_classes:
            raise ValueError("PUB-67 ISIC classes required")
        try:
            parsed = parse_feed_rows(active, activity_entry)
            if parsed.left_out:
                raise ValueError("PUB-67 unparsed activity codes")
            buckets = class_bucket_counts(parsed.rows, isic_classes)
        except SpineError as exc:
            raise ValueError(str(exc)) from exc
        review = Path(__file__).resolve().parents[4] / "publicdata/review"
        # These are the reviewed name-group keys, not the frame's own keys.
        reviewed_names = load_municipality_names(
            review, {"1", "2", "3", "4", "5", "6", "7", "8"}
        )
        target_names = {
            row["name"] for row in reviewed_names if row["municipality_code"] == "5"
        }
        targets = [
            item.code
            for item in municipalities
            if normalise_name(item.name_ar) in target_names
        ]
        if len(targets) != 1:
            raise ValueError("PUB-67 target municipality absent or ambiguous")
        converted = contract_rows("lic_active", active, municipalities=municipalities)
        if any(row["municipality_code"] is None for row in converted):
            raise ValueError("PUB-67 unresolved source municipality")
        active_total = sum(int(str(row["dd_lrkhs_lnsht"])) for row in active)
        if (
            buckets.total_active != active_total
            or sum(
                (
                    buckets.seven_valid_prefix,
                    buckets.seven_invalid_prefix,
                    buckets.six_legacy,
                    buckets.other_length,
                )
            )
            != active_total
        ):
            raise ValueError("PUB-67 bucket reconciliation")
        checks["PUB-67"] = {
            "rows": str(len(active)),
            "sum_count": str(active_total),
            "distinct_codes": str(len(parsed.rows)),
            "isic_prefix": str(buckets.seven_valid_prefix),
            "other_seven": str(buckets.seven_invalid_prefix),
            "legacy_six": str(buckets.six_legacy),
            "other_lengths": str(buckets.other_length),
            "al_daayen_5610101": str(
                sum(
                    int(str(row["active_count"]))
                    for row in converted
                    if row["municipality_code"] == targets[0]
                    and row["activity_code"] == "5610101"
                )
            ),
            "national_5610101": str(
                sum(
                    int(str(row["active_count"]))
                    for row in converted
                    if row["activity_code"] == "5610101"
                )
            ),
        }
    if "lic_issued" in data:
        issued = data["lic_issued"]
        converted = contract_rows("lic_issued", issued)
        checks["PUB-69"] = {
            "sum_count": str(sum((int(str(r["dd_lrkhs_lsdr"])) for r in issued), 0)),
            "distinct_codes": str(len({r["rmz_lnsht_ltjry"] for r in issued})),
            "restaurant_source_rows": str(
                sum(r["rmz_lnsht_ltjry"] == "5610101" for r in issued)
            ),
            "restaurant_contract_rows": str(
                sum(r["activity_code"] == "5610101" for r in converted)
            ),
            "incompleteness_note": "openings_incomplete",
            "net_formation_built": "false",
        }
    if "lic_cancelled" in data:
        cancellations: dict[str, Decimal] = {}
        for row in data["lic_cancelled"]:
            year, month = row["sn_llg"], row["shhr_llg"]
            period = source_period("lic_cancelled", year, month) or "UNDATED"
            if period != "UNDATED" and period not in C2_CALENDAR:
                raise ValueError(
                    "lic_cancelled period outside the C2 calendar: " + period
                )
            cancellations[period] = cancellations.get(period, ZERO) + Decimal(
                str(row["dd_lrkhs_lmlg"])
            )
        undated = cancellations.pop("UNDATED", ZERO)
        dated = sum(cancellations.values(), ZERO)
        flags = bulk_months(cancellations)
        months = {
            "july_2020": "2020-07",
            "june_2022": "2022-06",
            "september_2024": "2024-09",
        }
        check = {
            name: str(cancellations.get(month, ZERO)) for name, month in months.items()
        }
        check.update(
            {
                name + "_bulk": str(month in flags).lower()
                for name, month in months.items()
            }
        )
        check.update(
            {
                "sum_count": str(dated + undated),
                "undated": str(undated),
                "dated_total": str(dated),
                "combined_share_0dp": rounded(
                    ratio(
                        sum(
                            (cancellations.get(m, ZERO) for m in months.values()), ZERO
                        ),
                        dated,
                    )
                    * 100,
                    0,
                ),
            }
        )
        checks["PUB-68"] = check
    if "transit_monthly" in data:
        riders = {
            source_period("transit_monthly", r["year"], r["month"]): Decimal(
                str(r["doha_metro"])
            )
            for r in data["transit_monthly"]
        }
        if len(riders) != len(data["transit_monthly"]):
            raise ValueError("duplicate transit period")
        before, after = riders["2024-12"], riders["2025-12"]
        checks["PUB-70"] = {
            "metro_2024_12": str(before),
            "metro_2025_12": str(after),
            "growth_0dp": rounded(growth(before, after), 0),
        }
    return checks


def country_totals(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Sum retained customs rows, keeping null origins outside every country."""
    totals: dict[str, dict[str, object]] = {}
    for row in rows:
        key = str(row["origin_iso3"] or "not attributed to a country")
        total = totals.setdefault(
            key,
            {
                "country": key,
                "row_count": 0,
                "value_qar": ZERO,
                "weight_kg": ZERO,
            },
        )
        total["row_count"] = int(str(total["row_count"])) + 1
        for field in ("value_qar", "weight_kg"):
            total[field] = Decimal(str(total[field])) + Decimal(str(row[field]))
    return [totals[key] for key in sorted(totals)]


def basket_exclusion_review(
    rows: Sequence[dict[str, object]], review: Path | None = None
) -> bool:
    """Check every reviewed input against the selected source, not its old hash."""
    path = (
        review
        if review is not None
        else Path(__file__).resolve().parents[4] / "publicdata/review/baskets.yaml"
    )
    document = json.loads(path.read_text())
    validate_source_review(document, rows)
    return bool(reviewed_inputs(document, "5610"))


def _clear_outputs(cache: Path) -> None:
    """Invalidate only this builder's outputs, including on a missing selection."""
    root = cache / "series"
    for folder in ("display", "internal", "regression"):
        directory = root / folder
        directory.mkdir(parents=True, exist_ok=True)
        for stale in directory.glob("*.json"):
            stale.unlink()
    # Legacy owned files cannot mask a refused new build.
    for figure in DEPENDENCIES:
        (cache / "figures" / f"{figure}.json").unlink(missing_ok=True)


def build_series(
    cache: Path,
    entries: Sequence[Entry],
    selected: Mapping[str, str],
    *,
    request: str = "series",
    resolutions: Sequence[Resolution] = (),
    basket_review: Path | None = None,
    municipalities: Sequence[Municipality] = (),
    supporting_selected: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build selected versions only, clearing prior owned outputs before any refusal."""
    from eii_custodian.publicdata.stage import run_stage

    _clear_outputs(cache)
    root = cache / "series"
    if request != "series":
        raise ValueError("refused request: " + request)
    by_source = {
        entry.source_id: entry for entry in entries if entry.source_id in FIELD_MAP
    }
    if set(selected) != set(by_source):
        raise ValueError("selected sources must exactly match owned entries")
    data: dict[str, list[dict[str, object]]] = {}
    receipts: dict[str, dict[str, object]] = {}
    blocked: dict[str, tuple[str, ...]] = {}
    tables: dict[str, list[dict[str, object]]] = {}
    table_sources: dict[str, list[str]] = {}
    row_sources: dict[str, list[str]] = {}
    coverage: dict[str, object] = {}
    basket_checked = False
    countries = country_crosswalk()
    for source, digest in selected.items():
        rows, receipts[source] = selected_source(cache, by_source[source], digest)
        data[source] = confirmed_rows(by_source[source], rows)
        gaps = mapping_gaps(source)
        if gaps:
            blocked[source] = gaps
        if source == "cus_imp_2019":
            lengths: dict[str, int] = {}
            for row in rows:
                length = str(len(str(row["hs8"])))
                lengths[length] = lengths.get(length, 0) + 1
            coverage["cus_imp_2019.hs8_lengths"] = lengths
            _write(root / "internal" / "coverage.json", coverage)
        table = next(iter(FIELD_MAP[source].values()))[0]
        converted = contract_rows(source, rows, municipalities=municipalities)
        if source.startswith("cus_imp_"):
            coverage[source + ".code_not_stated"] = sum(
                r["tariff_code"] is None for r in converted
            )
            coverage[source + ".country_not_stated"] = sum(
                r["country_of_origin"] is None for r in rows
            )
            coverage[source + ".country_unmatched"] = sorted(
                {
                    str(r["country_of_origin"])
                    for r, c in zip(rows, converted, strict=True)
                    if r["country_of_origin"] is not None
                    and str(r["country_of_origin"]) not in countries
                }
            )
            _write(root / "internal" / "coverage.json", coverage)
            if coverage[source + ".country_unmatched"]:
                raise ValueError(
                    source
                    + " country_unmatched: "
                    + str(coverage[source + ".country_unmatched"])
                )
            totals = {
                **_envelope([source], receipts),
                "rows": country_totals(converted),
            }
            _write(root / "internal" / (source + ".country_totals.json"), totals)
            if source == "cus_imp_2025":
                basket_checked = basket_exclusion_review(rows, basket_review)
        if source.startswith("lic_"):
            coverage[source + ".municipality_exact_match"] = sorted(
                {
                    str(r["lbldy"])
                    for r, c in zip(rows, converted, strict=True)
                    if c["municipality_code"] is None
                }
            )
            if not municipalities:
                blocked[source] = ("municipality_frame_not_supplied",)
            elif coverage[source + ".municipality_exact_match"]:
                # B13: a spelling neither the frame nor the reviewed names file
                # holds refuses the build before any table file is written.
                _write(root / "internal" / "coverage.json", coverage)
                raise SeriesRefused(
                    "unmapped_municipality_spelling",
                    source + " unmapped municipality spelling",
                )
        _write(root / "internal" / "coverage.json", coverage)
        tables.setdefault(table, []).extend(converted)
        table_sources.setdefault(table, []).append(source)
        row_sources.setdefault(table, []).extend([source] * len(converted))
    for table, rows in tables.items():
        envelope = _envelope(table_sources[table], receipts)
        envelope.update({"rows": rows, "row_sources": row_sources[table]})
        validate_figure(envelope)
        _write(root / "internal" / f"{table}.json", envelope)
    evidence: dict[str, object] = {}
    if R2_SOURCES <= data.keys():
        wages = {source: _groups(data[source], source) for source in sorted(R2_SOURCES)}
        years = sorted(wages["wage_occ"].keys() & wages["wage_act"].keys())
        evidence["R2"] = {
            **_envelope(sorted(R2_SOURCES), receipts),
            **wage_evidence(wages, years),
        }
    if R1_SOURCES <= data.keys():
        indicators = [
            row
            for row in data["sec_hr_ind"]
            if str(row["activity_code"]) == "561" and str(row["year"]) == "2022"
        ]
        # The reference row has several published measures and no production
        # field. Compare the actual indicators, never manufacture that measure.
        indicator_measures = [
            target.split(":", 1)[1]
            for _, target in FIELD_MAP["sec_hr_ind"].values()
            if target.startswith("value:")
        ]
        matches = [
            {
                "source": source,
                "field": field,
                "year": row["year"],
                "activity_scope": row["main_economic_activity"],
                "value": value,
                "measure": FIELD_MAP[source][field][1].split(":", 1)[-1],
                "establishments": row.get(
                    "number_of_establishments", "not on this row"
                ),
                "indicator_comparisons": [
                    {
                        "activities": (
                            str(reference["activity_code"]),
                            str(row["activity_code"]),
                        ),
                        "measure": (
                            indicator_measures,
                            FIELD_MAP[source][field][1].split(":", 1)[-1],
                        ),
                        "year": (reference["year"], row["year"]),
                        "establishments": (
                            reference.get(
                                "number_of_establishments", "not on this row"
                            ),
                            row.get("number_of_establishments", "not on this row"),
                        ),
                    }
                    for reference in indicators
                ],
            }
            for source in sorted(R1_SOURCES)
            for row in data[source]
            for field, value in row.items()
            if type(value) in (int, Decimal) and value == Decimal("8579462")
        ]
        evidence["R1"] = {
            **_envelope(sorted(R1_SOURCES), receipts),
            "matches": matches,
            "status": "open" if matches else "closed: not published",
            "blocked": "matched figure requires signed scope resolution; no production or revenue fact"
            if matches
            else "production_value absent from present datasets; no production or revenue fact",
        }
    _write(root / "internal" / "reconciliations.json", evidence)
    required = tuple(
        figure
        for figure, sources in DEPENDENCIES.items()
        if set(sources) & selected.keys()
    )
    checks: dict[str, dict[str, str]] = {}
    support = None
    groups = [{source: data[source]} for source in data if source not in R1_SOURCES]
    if R1_SOURCES <= data.keys():
        groups.append({source: data[source] for source in R1_SOURCES})
    for group in groups:
        source = next(iter(group))
        try:
            if source == "lic_active":
                if not municipalities:
                    continue  # The existing frame blocker already prevents release.
                classes, support = load_support(
                    cache, entries, supporting_selected or {}, municipalities
                )
                checks.update(
                    compute_checks(
                        group,
                        isic_classes=classes,
                        municipalities=municipalities,
                        activity_entry=by_source[source],
                        receipts=receipts,
                    )
                )
            else:
                checks.update(compute_checks(group, receipts=receipts))
        except OSError as exc:
            from ..assembly_log import observe

            observe("series_stage", exc)
            blocked[source] = (
                *blocked.get(source, ()),
                "regression: " + type(exc).__name__,
            )
        except (ValueError, KeyError, SpineError) as exc:
            from ..assembly_log import observe

            observe("series_stage", exc)
            blocked[source] = (*blocked.get(source, ()), "regression: " + str(exc))
    if "PUB-65" in checks:
        checks["PUB-65"]["basket_excludes_noodles"] = str(basket_checked).lower()
    for figure, values in checks.items():
        envelope = {**_envelope(DEPENDENCIES[figure], receipts), "values": values}
        if figure == "PUB-67":
            envelope["supporting_provenance"] = support
        validate_figure(envelope)
        _write(root / "regression" / f"{figure}.json", envelope)
    if support is not None and "PUB-67" in checks:
        table = "pub_licence_active"
        envelope = {
            **_envelope(table_sources[table], receipts),
            "rows": tables[table],
            "row_sources": row_sources[table],
            "supporting_provenance": support,
        }
        _write(root / "internal" / f"{table}.json", envelope)
    stage = run_stage(cache, required=required, evidence=True)
    if not stage.mismatch:
        states = {source: entry.reconciliation for source, entry in by_source.items()}
        for table in tables:
            envelope = {
                **_envelope(table_sources[table], receipts),
                "rows": tables[table],
                "row_sources": row_sources[table],
            }
            if table == "pub_licence_active":
                envelope["supporting_provenance"] = support
            if any(source in blocked for source in table_sources[table]):
                continue
            if (
                emit_fact(envelope, table_sources[table], states, resolutions)
                is not None
            ):
                _write(root / "display" / f"{table}.json", envelope)
    result: dict[str, object] = {
        "selected": dict(selected),
        "coverage": coverage,
        "checks": checks,
        "blocked": blocked,
        "required": required,
        "mismatch": stage.mismatch,
        "missing": stage.missing,
    }
    _write(root / "internal" / "build.json", result)
    return result


def _refused(lines: list[str], word: str) -> FetchFailure:
    """One closed word for the line and the record; never an exception's text."""
    from eii_custodian.publicdata.fetch.build import FetchFailure

    if word not in SERIES_REFUSALS:
        raise ValueError("series_refusal_unknown")
    lines.append("FAIL series " + word)
    return FetchFailure(1, "series", "", "public_data", "valid selected input", word)


def finish_build(
    entries: Sequence[Entry], cache: Path, lines: list[str]
) -> FetchFailure | None:
    """One fetch/build call; take the exact hashes returned by this run's fetches."""
    from eii_custodian.publicdata.fetch.build import FetchFailure

    owned = [entry for entry in entries if entry.source_id in FIELD_MAP]
    if not owned:
        return None
    _clear_outputs(cache)
    selected = {}
    for entry in owned:
        prefix = "PASS " + entry.key + " sha256="
        matches = [
            line[len(prefix) :].split(" ", 1)[0]
            for line in lines
            if line.startswith(prefix)
        ]
        if len(matches) != 1:
            lines.append("FAIL " + entry.key + " selected receipt missing")
            return FetchFailure(
                1, entry.key, "", "selected_receipt", "one selected hash", "missing"
            )
        selected[entry.source_id] = matches[0]
    licence = sorted(
        entry.source_id for entry in owned if entry.source_id.startswith("lic_")
    )
    municipalities: tuple[Municipality, ...] = ()
    if licence:
        try:
            municipalities = frame_municipalities(cache)
        except MunicipalityFrameRefused as exc:
            lines.append(
                "FAIL series municipality_frame_not_supplied " + " ".join(licence)
            )
            return FetchFailure(
                1,
                "series",
                "",
                "public_data",
                "the municipalities of this build's frame",
                exc.reason,
            )
    try:
        supporting_selected = {}
        if "lic_active" in selected:
            for key in SUPPORT_KEYS:
                try:
                    entry_by_key(entries, key)
                except SpineError:
                    lines.append(
                        "FAIL " + key + " supporting registry identity required"
                    )
                    raise ValueError("supporting registry identity required") from None
                prefix = "PASS " + key + " sha256="
                hashes = [
                    line[len(prefix) :].split(" ", 1)[0]
                    for line in lines
                    if line.startswith(prefix)
                ]
                if len(hashes) != 1:
                    lines.append("FAIL " + key + " selected receipt missing")
                    raise ValueError("one supporting selected hash required")
                supporting_selected[key] = hashes[0]
        result = build_series(
            cache,
            entries,
            selected,
            municipalities=municipalities,
            supporting_selected=supporting_selected,
        )
    except SeriesRefused as exc:
        return _refused(lines, exc.word)
    except (OSError, ValueError, KeyError):
        return _refused(lines, "selected_input_refused")
    # B15: a blocked source always leaves its figure's regression file absent,
    # so the real stage names that figure; no fallback word is needed here.
    mismatch = str(result["mismatch"])
    if mismatch:
        lines.append("FAIL " + mismatch + " public_data selected-cache check")
        return FetchFailure(
            1, mismatch, "", "public_data", "section 10 anchor", mismatch
        )
    return None
