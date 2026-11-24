"""Adapt this run's selected, receipt-bound producer outputs to method pin rows.

No snapshot is opened here. Customs, census and sale rows are already produced
by series_stage, frame and gis_property_singles; places supplies its selected
file receipt. C5 arithmetic lives only in eii_core.calc.public_methods.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from .assembly import AssemblyError
from .frame.crosswalk import (
    DISTRICT_CROSSWALK_HEADER,
    check_district_crosswalk,
    district_keys,
    read_csv,
)
from .method_card_validation import (
    CONFIGURATION_PINS,
    S7_DEFERRED_PINS,
    _lineage,
    _mapping,
    _registry_by_source,
    _values,
)
from .places.fetch import FILE_KEYS

if TYPE_CHECKING:
    from .assembly_adapters import Production


def source_lineage(
    build: Production, keys: Sequence[str], method: str
) -> list[dict[str, Any]]:
    """Resolve each selected receipt against the same run and registry."""
    if not keys or any(key not in build.receipts for key in keys):
        raise AssemblyError("pin_lineage_receipt_missing")
    rows = []
    for key in sorted(keys):
        receipt = build.receipts[key]
        if build.selected.get(key) != receipt.get("sha256"):
            raise AssemblyError("pin_lineage_selection_mismatch")
        rows.append(
            {
                **{
                    name: receipt[name]
                    for name in (
                        "source_id",
                        "sha256",
                        "publisher",
                        "licence_id",
                        "retrieved_utc",
                    )
                },
                "method_id": method,
            }
        )
    _lineage(
        rows,
        registry_by_source=_registry_by_source(build.entries),
        receipts_by_key=build.receipts,
    )
    return rows


def table_keys(build: Production, table: str, source: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            e.key
            for e in build.entries
            if e.source_id == source and e.key in build.table_sources.get(table, ())
        )
    )


def _c14_values(build: Production, settings: Mapping[str, object]) -> dict[str, object]:
    keys = table_keys(build, "pub_property_sale", "prop_sales")
    if not keys or any(key not in build.selected for key in keys):
        raise AssemblyError("pin_c14_snapshot_missing")
    rows = build.tables.get("pub_property_sale", [])
    crosswalk = read_csv(
        build.review / "district_crosswalk.csv", header=DISTRICT_CROSSWALK_HEADER
    )
    known = {
        str(row["district_key"]) for row in build.needed_frame().tables["district"]
    }
    check_district_crosswalk(crosswalk, known)
    districts, reason = district_keys(
        str(settings["crosswalk_name"]),
        str(settings["municipality_code"]),
        crosswalk,
        known,
    )
    selected = [
        row
        for row in rows
        if row["district_key"] in districts and row["period"] == settings["period"]
    ]
    if reason is not None or not selected:
        raise AssemblyError("pin_c14_medians_missing")
    values: dict[str, object] = {}
    for row in selected:
        key = str(row["district_key"]) + ":" + str(row["property_type"])
        if key + ":deal_count" in values:
            raise AssemblyError("pin_c14_medians_duplicate")
        values[key + ":median_qar_per_m2"] = (
            str(row["median_price_per_m2"])
            if row["median_price_per_m2"] is not None
            else "NO_DATA"
        )
        values[key + ":deal_count"] = row["deal_count"]
    return values


def _c7_values(build: Production, settings: Mapping[str, object]) -> dict[str, object]:
    if any(
        settings.get(key) != value
        for key, value in (
            ("period", "2020"),
            ("indicator", "residents"),
            ("unit", "persons"),
        )
    ):
        raise AssemblyError("pin_c7_weight_settings")
    rows = [
        row
        for row in build.tables.get("pub_census_district", [])
        if all(row.get(key) == settings[key] for key in ("period", "indicator", "unit"))
    ]
    if not rows:
        raise AssemblyError("pin_c7_weights_missing")
    values: dict[str, object] = {
        str(row["district_key"]): str(row["value"]) for row in rows
    }
    if len(values) != len(rows):
        raise AssemblyError("pin_c7_weights_duplicate")
    return values


def collect_pin_rows(
    build: Production, config: Mapping[str, object]
) -> list[dict[str, object]]:
    """Select inputs and copy existing results, with no numerical arithmetic."""
    from .method_pin_supplier import c5_pin_rows

    settings_by_pin = _mapping(config["pins"])
    produced = {str(row["pin_id"]): row for row in c5_pin_rows(build, settings_by_pin)}
    for pin, raw in sorted(settings_by_pin.items()):
        settings = _mapping(raw)
        if pin in produced:
            continue
        lineage: list[dict[str, Any]] = []
        values: dict[str, object]
        if pin in CONFIGURATION_PINS:
            values = dict(
                _values(
                    {key: value for key, value in settings.items() if key != "anchor"}
                )
            )
        elif pin in S7_DEFERRED_PINS:
            values = {}
        elif pin == "c6.release_sha256":
            key = str(settings["source_key"])
            if not any(
                entry.key == key
                and entry.source_id == "places_ovt"
                and key in FILE_KEYS
                for entry in build.entries
            ):
                raise AssemblyError("pin_c6_release_source")
            lineage = source_lineage(build, (key,), "C6.selected_release@v1")
            values = {"value": build.receipts[key]["sha256"]}
        elif pin == "c7.district_weights":
            values = _c7_values(build, settings)
            lineage = source_lineage(
                build,
                table_keys(build, "pub_census_district", "census_district_pop"),
                "C7.census_weights@v1",
            )
        else:
            if settings.get("period") != pin.removeprefix("c14.medians_"):
                raise AssemblyError("pin_c14_period_mismatch")
            values = _c14_values(build, settings)
            lineage = source_lineage(
                build,
                table_keys(build, "pub_property_sale", "prop_sales"),
                "C14.sale_aggregates@v1",
            )
        produced[pin] = {"pin_id": pin, "values": values, "source_lineage": lineage}
    return [produced[pin] for pin in sorted(produced)]
