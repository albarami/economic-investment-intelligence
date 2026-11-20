"""Gather real producer evidence; pending human gates never become approval."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import TYPE_CHECKING, Any

from .assembly import AssemblyError
from .assembly_io import bound_files, local, read_object, write_record
from .assembly_sources import (
    CITATIONS,
    DECISION_0019,
    FAMILY_COUNTS,
    PACK_IDENTITIES,
    SOURCE_COMPONENTS,
)
from .draw import Figure, reviewer_sheet
from .fetch.bounded import file_hash

if TYPE_CHECKING:
    from .assembly_adapters import Production

# Contract numeric measures only. Administrative coordinates, keys, source years
# and counters never enter the draw. A new numeric field refuses until reviewed.
MONEY_FIELDS = frozenset(
    {
        "median_price",
        "guide_price",
        "deal_value",
        "median_price_per_ft2",
        "land_median_price_per_ft2",
        "bond_qar",
        "documents_value_qar",
        "value_qar",
        "compensation",
        "operating_surplus",
        "average_annual_wage",
    }
)
RATIO_FIELDS = frozenset({"share", "percentage", "density", "rate", "ratio"})
COUNT_FIELDS = frozenset(
    {
        "value",
        "deal_count",
        "land_deal_count",
        "riders",
        "active_count",
        "cancelled_count",
        "issued_count",
        "document_count",
        "facility_count",
        "quantity",
        "weight_kg",
        "residents",
        "households",
        "establishments",
        "employees",
        "population",
        "radiance",
        "temperature",
        "precipitation",
        "height_m",
    }
)
ADMIN_FIELDS = frozenset(
    {
        "cell",
        "parent_r7",
        "resolution",
        "lon",
        "lat",
        "longitude",
        "latitude",
        "year",
        "month",
        "zone_number",
        "street_number",
        "building_number",
        "building_subtype",
        "period",
        "activity_code",
        "table_code",
        "district_key",
        "municipality_code",
        "zone_code",
        "date_created",
        "date_refreshed",
        "date_closed",
        "geometry",
        "feature_key",
        "as_of",
        "number_of_shares_2400",
    }
)


MONEY_FIELDS = MONEY_FIELDS | frozenset(
    {"gdp_origin", "gdp_destination", "capex_value"}
)
COUNT_FIELDS = COUNT_FIELDS | frozenset(
    {
        "distance",
        "finished_measure",
        "historical_value",
        "publisher_estimate_value",
        "publisher_forecast_value",
        "unclassified_value",
        "jobs",
        "area_m2",
    }
)
RATIO_FIELDS = RATIO_FIELDS | frozenset({"busyness_index"})
ADMIN_FIELDS = ADMIN_FIELDS | frozenset(
    {
        "aggregation_level",
        "decision_record",
        "city_id",
        "lng",
        "tech_level_id",
        "world_region_id",
        "src_country_id",
        "src_state_id",
        "src_world_region_id",
        "level",
        "ordinal",
        "parent_ordinal",
        "project_id",
        "project_month",
        "project_year",
        "sector_id",
        "src_city_id",
        "state_id",
        "country_id",
        "parent_company_id",
        "fdi_sector_id",
        "sub_sector_id",
        "function_id",
        "project_type_id",
        "hour",
    }
)


# Codes and source labels can themselves be numeric text; these contract fields
# are metadata, while numeric text in an unknown field refuses the draw.
TEXT_FIELDS = frozenset(
    {
        "source_id",
        "source_key",
        "source_version",
        "method",
        "method_version",
        "contig",
        "common_language",
        "colonial_link",
        "trade_agreement",
        "distance_unit",
        "distance_status",
        "gdp_origin_unit",
        "gdp_origin_status",
        "gdp_destination_unit",
        "gdp_destination_status",
        "partner2_code",
        "flow_code",
        "classification_revision",
        "customs_code",
        "transport_mode_code",
        "series_role",
        "measure",
        "indicator_code",
        "dimension_key",
        "frequency",
        "scale",
        "publisher_status",
        "source_flags",
        "receipt_sha256",
        "source_row_key",
        "publisher",
        "licence_id",
        "licence_basis",
        "retrieved_utc",
        "sha256",
        "member_sha256",
        "fetch_url",
        "source_name",
        "source_description",
        "name",
        "name_en",
        "name_ar",
        "aliases",
        "kind",
        "feature_kind",
        "place_id",
        "place_key",
        "fsq_place_id",
        "building_id",
        "venue_key",
        "country_code",
        "exporter_code",
        "importer_code",
        "reporter_code",
        "partner_code",
        "product_code",
        "hs_code",
        "hs_revision",
        "hs_detail",
        "origin_code",
        "destination_code",
        "classification",
        "source_release",
        "currency",
        "valuation_basis",
        "quantity_status",
        "value_status",
        "measure_status",
        "measure_unit",
        "value_unit",
        "quantity_unit",
        "grain",
        "unit",
        "indicator",
        "economic_activity",
        "occupation",
        "breakdown_key",
        "activity_key",
        "size_class",
        "age_group",
        "sex",
        "nationality",
        "nationality_group",
        "unit_type",
        "property_type",
        "use_key",
        "sector_key",
        "star_class",
        "facility_type",
        "trade_type",
        "document_type",
        "permit_type",
        "building_type",
        "price_basis",
        "category",
        "language",
        "status",
        "city",
        "region",
        "calendar",
        "period_kind",
        "series_key",
    }
)
NUMERIC_TEXT = re.compile(
    r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?|[-+]?(?:NaN|Infinity)",
    re.ASCII,
)


def _optional(build: Production, name: str) -> dict[str, Any]:
    if not local(build.cache, name).is_file():
        return {}
    return read_object(build.cache, name)


def awards_evidence(receipt: dict[str, Any], seed: int) -> dict[str, Any]:
    """Validate complete T29 link evidence and retain labelled sample statistics.

    The gate report retains summary counts, status and rates; per-link URLs and
    outcomes stay on the source receipt. OI-277 live acceptance stays with the lead.
    """
    from .fetch.award_checks import AwardError, validate_check_receipt
    from .fetch.award_links import validate_links_receipt

    try:
        validate_check_receipt(receipt)
        validate_links_receipt(receipt)
    except AwardError:
        raise AssemblyError("assembly_t29_refused") from None
    check = receipt["award_check"]
    count = receipt.get("registration_double_space_only")
    if (
        check["seed"] != seed
        or check["incomplete"] is not False
        or receipt["award_links"]["incomplete"] is not False
        or type(count) is not int
        or count < 0
    ):
        raise AssemblyError("assembly_t29_refused")
    return {
        "key": "awards_owner_scrape",
        "sha256": receipt["sha256"],
        "award_check": {key: value for key, value in check.items() if key != "results"},
        "award_check_scope": "sample",
        "award_links": {
            key: value
            for key, value in receipt["award_links"].items()
            if key not in {"results", "report_urls"}
        },
        "registration_double_space_only": count,
    }


def own_words_confirmed(build: Production) -> frozenset[str]:
    """Read separate source-owner reviews, bound to exact wording, date and basis."""
    from .fetch.terms_text import terms_text_sha256

    name = "review/s2_t08_terms.json"
    if not local(build.cache, name).is_file():
        return frozenset()
    document = read_object(build.cache, name)
    reviews = document.get("reviews")
    if (
        set(document) != {"method", "reviews"}
        or document["method"] != "s2-t08-terms.v1"
        or not isinstance(reviews, list)
    ):
        raise AssemblyError("assembly_terms_review_invalid")
    entries = {row.key: row for row in build.entries}
    confirmed: set[str] = set()
    for item in reviews:
        if (
            not isinstance(item, dict)
            or set(item)
            != {"key", "terms_sha256", "terms_read_on", "licence_basis", "review_ref"}
            or not all(isinstance(value, str) for value in item.values())
        ):
            raise AssemblyError("assembly_terms_review_invalid")
        row = entries.get(item["key"])
        if (
            row is None
            or row.key in confirmed
            or not item["review_ref"].strip()
            or not row.terms_read_on
            or not row.terms_words.strip()
            or item["terms_sha256"] != terms_text_sha256(row.terms_words.encode())
            or item["terms_read_on"] != row.terms_read_on
            or item["licence_basis"] != row.licence_basis
        ):
            raise AssemblyError("assembly_terms_review_invalid")
        confirmed.add(row.key)
    build.files[name] = file_hash(local(build.cache, name))
    return frozenset(confirmed)


def gather_audit(build: Production) -> dict[str, Any]:
    from . import completeness as c
    from .confirm_s2_t13 import load_confirmation
    from .fetch.forecast_series import load_forecast_series
    from .fetch.page_records import selected_page
    from .fetch.registry import read_yaml, registry_path
    from .gate_report import (
        ConfirmationEvidence,
        confirmations,
        coverage_geography,
        fsq_evidence,
        investment_evidence,
        load_dispositions,
        oi03_line,
        tender_evidence,
        terms_evidence,
    )
    from .series.reconcile import R1_SOURCES, R2_SOURCES

    pack_text = (build.root / "docs/04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    pack = c.pack_sources(pack_text, FAMILY_COUNTS)
    _, required = c.independent_inventory(FAMILY_COUNTS, DECISION_0019, CITATIONS)
    inventory = {
        **PACK_IDENTITIES,
        **{key: PACK_IDENTITIES.get(key, ()) for key in required},
    }
    absences = {
        e.key: c.Absence(e.skip_reason, e.caveat_keys[0])
        for e in build.entries
        if e.skip_reason and e.caveat_keys
    }
    catalogue = c.table_catalogue(
        (build.root / "docs/03_DATA_CONTRACTS.md").read_text(encoding="utf-8")
    )
    # Merely fetching a raw source never credits a release output.
    complete = c.check(
        entries=build.entries,
        pack=pack,
        inventory=inventory,
        catalogue=catalogue,
        receipts=build.receipts,
        outputs=build.source_tables,
        absences=absences,
        cached_source_ids=tuple(p.name for p in build.cache.iterdir() if p.is_dir()),
        family_counts=FAMILY_COUNTS,
        component_keys=SOURCE_COMPONENTS,
    )
    present = {row.source_id for row in build.entries}
    for source in sorted(c.REGISTER_IDS - present):
        complete.append(
            {
                "id": source,
                "state": "failed",
                "reason": "source_completeness: required register row missing",
            }
        )
    evidence = []
    inv_document = read_yaml(build.root / "custodian/publicdata/investment_pages.yaml")
    if isinstance(inv_document, dict):
        evidence.append(
            replace(
                investment_evidence(inv_document, "investment_pages.yaml"),
                receipt_sha256={
                    key: str(build.receipts[key]["sha256"])
                    for key in ("fdi_projects", "investqa_pages")
                    if key in build.receipts
                },
            )
        )
    tender = next((e for e in build.entries if e.source_id == "tenders_pub"), None)
    evidence.append(
        tender_evidence(
            load_confirmation(build.review / "s2_t13_confirmation.yaml"),
            tender,
            build.receipts.get(tender.key) if tender else None,
            "s2_t13_confirmation.yaml",
        )
    )
    fsq = next((e for e in build.entries if e.key == "places_fsq/copy"), None)
    policy = read_yaml(build.review / "places_fsq_policy.yaml")
    if fsq and isinstance(policy, dict):
        releases = {
            str(row.get("source_release") or "")
            for row in build.tables.get("pub_place_fsq", [])
        }
        registry_release = releases.pop() if len(releases) == 1 else ""
        receipt = build.receipts.get(fsq.key, {})
        item = fsq_evidence(
            registry_release,
            policy,
            "places_fsq_policy.yaml",
            str(receipt.get("source_modified") or ""),
        )
        evidence.append(
            replace(
                item,
                source_keys=(fsq.key,),
                receipt_sha256={fsq.key: str(build.receipts[fsq.key]["sha256"])}
                if fsq.key in build.receipts
                else {},
            )
        )
    registry = read_yaml(registry_path())
    forecast = (
        load_forecast_series(registry.get("forecast_series"), build.entries)
        if isinstance(registry, dict)
        else ()
    )
    evidence.append(
        ConfirmationEvidence(
            "S2-T17",
            tuple(sorted({key for item in forecast for key in item.source_keys})),
            ("s2_t17_forecast_series.md",),
            {
                "series_validated": bool(forecast),
                "record_present": (
                    build.review / "s2_t17_forecast_series.md"
                ).is_file(),
            },
            tuple(item.key for item in forecast if item.state == "open"),
            receipt_sha256={
                key: str(receipt["sha256"]) for key, receipt in build.receipts.items()
            },
        )
    )
    t19 = read_yaml(build.review / "s2_t19_confirmation.yaml")
    t19_rows = t19.get("sources", []) if isinstance(t19, dict) else []
    if not isinstance(t19_rows, list) or any(
        not isinstance(row, dict) for row in t19_rows
    ):
        raise AssemblyError("assembly_confirmation_invalid")
    t19_keys = tuple(row["key"] for row in t19_rows)
    if len(set(t19_keys)) != len(t19_keys):
        raise AssemblyError("assembly_confirmation_invalid")
    t19_checked = bool(t19_keys) and all(
        row.get("outcome") == "fetched"
        and row.get("sha256") == build.receipts.get(row["key"], {}).get("sha256")
        and row.get("retrieved_utc")
        == build.receipts.get(row["key"], {}).get("retrieved_utc")
        and row.get("review_ref")
        for row in t19_rows
    )
    evidence.append(
        ConfirmationEvidence(
            "S2-T19",
            t19_keys,
            ("s2_t19_confirmation.yaml",),
            {"confirmed": t19_checked},
            receipt_sha256={
                key: str(build.receipts[key]["sha256"])
                for key in t19_keys
                if key in build.receipts
            },
        )
    )
    heights = _optional(build, "assembly/heights.json")
    height_keys = tuple(
        e.key for e in build.entries if e.source_id in {"bldg_3dglobfp", "bldg_wsf3d"}
    )
    checked_heights = heights.get("state") == "built"
    if checked_heights:
        from .heights.manifest import METHOD_ID
        from .heights.model import HEIGHTS_RELATIVE, load_rules

        rules = load_rules(build.root / "custodian/publicdata/height_rules.yaml")
        files = heights.get("files")
        if not isinstance(files, dict):
            raise AssemblyError("assembly_output_invalid")
        bound_files(
            build.cache.parent,
            {HEIGHTS_RELATIVE + "/" + name: digest for name, digest in files.items()},
        )
        manifest = read_object(
            build.cache.parent, HEIGHTS_RELATIVE + "/manifest.heights.json"
        )
        checked_heights = (
            manifest.get("method") == METHOD_ID
            and manifest.get("storey_height_m")
            == {"value": rules.storey_value, "basis": rules.basis, "label": rules.label}
            and isinstance(manifest.get("errors"), dict)
            and manifest.get("order") == list(rules.order)
        )
    evidence.append(
        ConfirmationEvidence(
            "S2-T20",
            height_keys,
            ("height_rules.yaml", "assembly/heights.json"),
            {
                key: checked_heights
                for key in (
                    "storey_height_recorded",
                    "fallback_errors_recorded",
                    "asset_manifest_recorded",
                    "rules_recorded",
                )
            },
            receipt_sha256={
                key: str(build.receipts[key]["sha256"])
                for key in height_keys
                if key in build.receipts
            },
        )
    )
    decision_name = "0025-reconciliation-of-restaurant-and-wage-figures.md"
    decision_path = build.root / "docs/decisions" / decision_name
    decision = decision_path.read_bytes() if decision_path.is_file() else b""
    note = _optional(build, "review/oi03_signoff.json")
    dispos = _optional(build, "series/internal/reconciliations.json")
    items = (build.root / "OPEN_ITEMS.md").read_text(encoding="utf-8")
    found = re.search(r"^## OI-03\b.*?(?=^## |\Z)", items, re.S | re.M)
    status = "CLOSED" if found and "TYPE: CLOSED" in found.group() else "OPEN"
    oi03 = oi03_line(
        entries=build.entries,
        decision=decision,
        decision_name=decision_name,
        signoff=note,
        sources=R1_SOURCES | R2_SOURCES,
        open_item_type=status,
        dispositions=load_dispositions(json.dumps(dispos).encode()),
    )
    t29 = []
    for entry in build.entries:
        if (
            entry.kind == "public_page"
            and not entry.skip_reason
            and entry.key in build.selected
        ):
            parsed = selected_page(build.cache, entry)
            if parsed.sha256 != build.selected.get(entry.key):
                raise AssemblyError("assembly_t29_refused")
            t29.append({"key": entry.key, "sha256": parsed.sha256})
    awards = build.receipts.get("awards_owner_scrape")
    if awards is not None:
        t29.append(awards_evidence(awards, build.seed))
    confirmed_terms = own_words_confirmed(build)
    terms_rows = terms_evidence(build.entries, confirmed_terms)
    for term in terms_rows:
        if term["id"] in confirmed_terms:
            term["own_words_record"] = "review/s2_t08_terms.json"
            term["own_words_record_sha256"] = build.files["review/s2_t08_terms.json"]
    return {
        "completeness": complete,
        "terms": terms_rows,
        "coverage": coverage_geography(build.entries, build.receipts, frozenset()),
        "oi03": oi03,
        "confirmations": confirmations(evidence, build.entries, build.receipts),
        "investment": _optional(build, "assembly/investment_capture.json"),
        "t29": t29,
        "regressions": {
            key: _optional(build, "assembly/series_stage.json").get(
                key, ["stage_not_run"] if key == "missing" else "stage_not_run"
            )
            for key in ("missing", "mismatch")
        },
    }


def _draw_row_sources(
    build: Production, table: str, data: dict[str, Any]
) -> list[str] | None:
    """Resolve stored row tags; only wholly untagged multi-source tables are excluded."""
    sources = build.table_sources.get(table, set())
    if not sources or any(source not in build.receipts for source in sources):
        raise AssemblyError("assembly_lineage_missing")
    rows = data["tables"][table]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise AssemblyError("assembly_output_invalid")
    if len(sources) == 1:
        return [next(iter(sources))] * len(rows)
    stored = data.get("row_sources", {}).get(table, [])
    if not isinstance(stored, list) or (stored and len(stored) != len(rows)):
        raise AssemblyError("assembly_draw_lineage_ambiguous")
    tags = [
        row.get("source_key") or (stored[index] if stored else None)
        for index, row in enumerate(rows)
    ]
    if not any(tags):
        return None
    if not all(isinstance(tag, str) and tag for tag in tags):
        raise AssemblyError("assembly_draw_lineage_ambiguous")
    resolved = []
    for tag in tags:
        # Additions carry registry keys; series envelopes carry publisher source IDs.
        matches = (
            [tag]
            if tag in sources
            else [key for key in sources if build.receipts[key]["source_id"] == tag]
        )
        if len(matches) != 1:
            raise AssemblyError("assembly_draw_lineage_ambiguous")
        resolved.append(matches[0])
    return resolved


def draw_tables(build: Production) -> dict[str, Callable[[], Sequence[Figure]]]:
    """Bind every registered table to its stored phase envelope and exact hash."""
    files: dict[str, tuple[str, str]] = {}
    for phase in (
        "reviewed_selections",
        "frame",
        "gis_property_singles",
        "fsq",
        "series_stage",
        "additions",
        "busyness",
    ):
        name = "assembly/" + phase + ".json"
        if not local(build.cache, name).is_file():
            continue
        data = read_object(build.cache, name)
        tables = data.get("tables", {})
        if not isinstance(tables, dict):
            raise AssemblyError("assembly_output_invalid")
        for table in tables:
            if table not in build.tables:
                if (
                    table in {"fact_lineage", "source_registry", "grid_cell"}
                    or tables[table] == []
                ):
                    continue
                raise AssemblyError("assembly_draw_table_unindexed")
            if table in files:
                previous_name, previous_hash = files[table]
                bound_files(build.cache, {previous_name: previous_hash})
                previous_rows = read_object(build.cache, previous_name)["tables"][table]
                if not (
                    table == "gazetteer"
                    and phase == "gis_property_singles"
                    and previous_name == "assembly/frame.json"
                    and tables[table][: len(previous_rows)] == previous_rows
                ):
                    raise AssemblyError("assembly_table_duplicate")
            files[table] = (name, file_hash(local(build.cache, name)))
    if set(build.tables) - set(files):
        raise AssemblyError("figure_table_unreachable")

    build.draw_exclusions.clear()
    for table, (name, digest) in sorted(files.items()):
        if len(build.table_sources.get(table, set())) <= 1:
            continue
        bound_files(build.cache, {name: digest})
        if _draw_row_sources(build, table, read_object(build.cache, name)) is None:
            build.draw_exclusions.append(
                {
                    "table": table,
                    "sources": sorted(build.table_sources[table]),
                    "reason": "assembly_draw_lineage_ambiguous",
                }
            )
    excluded = {item["table"] for item in build.draw_exclusions}

    def reader(table: str) -> Sequence[Figure]:
        name, digest = files[table]
        bound_files(build.cache, {name: digest})
        data = read_object(build.cache, name)
        rows = data["tables"][table]
        row_sources = _draw_row_sources(build, table, data)
        if row_sources is None:
            raise AssemblyError("assembly_draw_lineage_ambiguous")
        sources = build.table_sources.get(table, set())
        if not sources or any(source not in build.receipts for source in sources):
            raise AssemblyError("assembly_lineage_missing")
        keys = sorted(sources)
        links = [
            {
                key: build.receipts[source][key]
                for key in ("source_id", "fetch_url", "sha256")
            }
            for source in keys
        ]
        output = []
        for index, row in enumerate(rows):
            receipt = build.receipts[row_sources[index]]
            if not isinstance(row, dict):
                raise AssemblyError("assembly_output_invalid")
            for field, value in row.items():
                if (
                    field in ADMIN_FIELDS
                    or field in TEXT_FIELDS
                    or value is None
                    or isinstance(value, (bool, dict, list))
                ):
                    continue
                if field in MONEY_FIELDS or (
                    field == "value"
                    and (
                        table in {"pub_bank_credit", "pub_baci_trade"}
                        or row.get("unit")
                        in {
                            "QAR",
                            "QAR_thousand",
                            "USD",
                            "USD_thousand",
                            "qar",
                            "qar_thousand",
                        }
                    )
                ):
                    kind = "money"
                elif field in RATIO_FIELDS or (
                    field == "value"
                    and row.get("unit") in {"percent", "percentage", "ratio"}
                ):
                    kind = "ratio"
                elif field in COUNT_FIELDS:
                    kind = "count"
                else:
                    if isinstance(value, (int, float, Decimal)) or (
                        isinstance(value, str) and NUMERIC_TEXT.fullmatch(value.strip())
                    ):
                        raise AssemblyError("assembly_draw_field_unknown")
                    continue
                try:
                    if not Decimal(str(value)).is_finite():
                        raise AssemblyError("assembly_draw_value_invalid")
                except InvalidOperation:
                    raise AssemblyError("assembly_draw_value_invalid") from None
                identity = table + ":" + str(index) + ":" + field
                output.append(
                    Figure(
                        identity,
                        str(receipt["source_id"]),
                        str(receipt["fetch_url"]),
                        "snapshot="
                        + str(receipt["sha256"])
                        + ";table="
                        + table
                        + ";row="
                        + str(index)
                        + ";field="
                        + field
                        + ";inputs="
                        + json.dumps(links, sort_keys=True),
                        str(value),
                        kind,
                    )
                )
        return output

    return {
        table: partial(reader, table)
        for table in sorted(files)
        if table not in excluded
    }


def write_reports(build: Production) -> dict[str, str]:
    bound_files(build.cache, build.files)
    bound_files(build.cache.parent, build.data_files)
    audit = read_object(build.cache, "assembly/final_audit.json")
    drawn = read_object(build.cache, "assembly/draw_values.json")
    if (
        not {"completeness", "terms", "coverage", "oi03", "confirmations", "investment"}
        <= set(audit)
        or drawn.get("seed") != build.seed
    ):
        raise AssemblyError("assembly_reports_invalid")
    figures = [Figure(**item) for item in drawn["figures"]]
    sheet = reviewer_sheet(build.seed, figures)
    values = {**audit, "draw": sheet}
    output = {}
    for key in (
        "completeness",
        "terms",
        "coverage",
        "oi03",
        "confirmations",
        "investment",
        "draw",
    ):
        output.update(
            write_record(build.cache, "assembly/s2_t08_" + key + ".json", values[key])
        )
    return output


def require_complete(audit: dict[str, Any]) -> None:
    """A report that names a pending gate is never a successful public build.

    Ruling L-1001: a terms row's own-words reading is a record, never a gate,
    so a pending ``own_words_state`` fails no criterion. The terms list itself
    stays required and well formed: a missing or malformed list is refused.
    """
    from .gate_report import CONFIRMATION_TASKS

    completeness = audit.get("completeness")
    terms = audit.get("terms")
    confirmations = audit.get("confirmations")
    regressions = audit.get("regressions")
    if (
        not isinstance(completeness, list)
        or not completeness
        or any(
            not isinstance(row, dict)
            or row.get("state") not in {"in use", "NO_DATA", "not yet read"}
            for row in completeness
        )
        or not isinstance(terms, list)
        or not terms
        or any(
            not isinstance(row, dict)
            or row.get("own_words_state") not in {"recorded", "pending"}
            for row in terms
        )
        or audit.get("oi03", {}).get("state") != "recorded"
        or not isinstance(confirmations, list)
        or len(confirmations) != len(CONFIRMATION_TASKS)
        or {row.get("task") for row in confirmations if isinstance(row, dict)}
        != set(CONFIRMATION_TASKS)
        or any(
            not isinstance(row, dict) or row.get("state") != "recorded"
            for row in confirmations
        )
        or not isinstance(regressions, dict)
        or regressions.get("missing") != []
        or regressions.get("mismatch") != ""
    ):
        raise AssemblyError("assembly_gate_pending")
