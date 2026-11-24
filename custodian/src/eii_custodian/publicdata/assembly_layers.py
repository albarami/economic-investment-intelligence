"""Existing GIS, bulletin and single-source builders over selected archives."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from eii_custodian.publicdata.fetch.registry import COLLECTED_FAMILIES

from .assembly import AssemblyError

if TYPE_CHECKING:
    from .assembly_adapters import Production


def check_property_districts(build: Production) -> None:
    """Bind every property crosswalk key to this run's district frame."""
    from .frame.crosswalk import (
        DISTRICT_CROSSWALK_HEADER,
        check_district_crosswalk,
        read_csv,
    )

    rows = read_csv(
        build.review / "district_crosswalk.csv", header=DISTRICT_CROSSWALK_HEADER
    )
    known = {
        str(row["district_key"]) for row in build.needed_frame().tables["district"]
    }
    check_district_crosswalk(rows, known)


def build_layers(build: Production) -> None:
    from .confirm_s2_t13 import completion_evidence, load_confirmation, own_run_pending
    from .frame.crosswalk import load_municipality_names, read_csv
    from .gis.layers import (
        address_rows,
        context_tables,
        health_rows,
        land_price_rows,
        landmark_rows,
        parcel_rows,
        poi_rows,
        rail_rows,
        zoning_rows,
    )
    from .property.bulletin import (
        Deal,
        parse_bulletin,
        refuse_release_identifiers,
        sales_export_rows,
    )
    from .property.quarter import quarter_aggregates
    from .property.sale import sale_aggregates
    from .property.use_map import load_use_map
    from .singles.bank_credit import parse_bank_credit
    from .singles.dcool import parse_dcool
    from .singles.families import family_table_name, parse_family_rows
    from .singles.tenders import publish_tenders, rows_from_pages

    grid = build.needed_frame().tables["grid_cell"]
    deals: list[Deal] = []
    identifiers: set[str] = set()
    deal_sources = []
    sale_sources = []
    family_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    family_sources: dict[str, set[str]] = defaultdict(set)
    parsers: dict[
        str, tuple[str, Callable[[list[dict[str, Any]]], list[dict[str, Any]]]]
    ] = {
        "gis_address": (
            "pub_address_point",
            lambda layers: address_rows(_features(layers), grid),
        ),
        "gis_parcels": ("pub_parcel", lambda layers: parcel_rows(_features(layers))),
        "gis_zoning": ("pub_zoning", zoning_rows),
        "gis_rail": ("pub_rail_plan", rail_rows),
        "gis_phcc": (
            "pub_health_centre",
            lambda layers: list(health_rows(layers).rows),
        ),
        "gis_landmarks": (
            "gazetteer",
            lambda layers: landmark_rows(_features(layers), grid),
        ),
        "gis_poi_comm": (
            "pub_poi_comm",
            lambda layers: poi_rows(_features(layers), grid),
        ),
    }
    for entry in build.entries:
        if entry.skip_reason or entry.kind == "citation_only":
            continue
        source = entry.source_id
        if source in parsers:
            payload = build.raw(entry, standard_json=True)
            layers = payload.get("layers") if isinstance(payload, dict) else None
            if not isinstance(layers, list):
                raise AssemblyError("assembly_gis_shape_invalid")
            table, parse = parsers[source]
            rows = parse(layers)
            if table == "gazetteer" and table in build.tables:
                previous = build.tables[table]
                keys = [row["place_key"] for row in (*previous, *rows)]
                if len(set(keys)) != len(keys):
                    raise AssemblyError("assembly_table_duplicate")
                build.tables[table] = [*previous, *rows]
                build.table_sources[table].add(entry.key)
                build.source_tables.setdefault(entry.key, []).append(table)
            else:
                build.table(table, rows, (entry.key,))
        elif source == "gis_land_price":
            from .property.price_as_of import as_of_from_receipt, require_price_as_of

            payload = build.raw(entry, standard_json=True)
            layers = payload.get("layers") if isinstance(payload, dict) else None
            if not isinstance(layers, list):
                raise AssemblyError("assembly_gis_shape_invalid")
            as_of = as_of_from_receipt(build.receipts[entry.key])
            rows = land_price_rows(_features(layers), entry.url, as_of=as_of)
            for row in rows:
                require_price_as_of(row, as_of)
            build.table("pub_land_price", rows, (entry.key,))
        elif source == "gis_context":
            build.raw(entry)
            for table, rows in context_tables().items():
                build.table(table, rows, (entry.key,))
        elif source == "bank_credit_act":
            build.table(
                "pub_bank_credit",
                [asdict(r) for r in parse_bank_credit(build.raw(entry))],
                (entry.key,),
            )
        elif source == "dcool_capacity":
            codes = {
                str(r["municipality_code"])
                for r in build.needed_frame().tables["municipality"]
            }
            names = load_municipality_names(build.review, codes)
            build.table(
                "pub_district_cooling",
                [asdict(r) for r in parse_dcool(build.raw(entry), names)],
                (entry.key,),
            )
        elif source in {"prop_sales", "prop_resi_units"}:
            check_property_districts(build)
            raw = build.raw(entry)
            if source == "prop_sales":
                raw = sales_export_rows(raw)
            result = parse_bulletin(
                raw,
                source,
                load_use_map(build.review / "property_use_map.csv"),
                {
                    "frame": build.review,
                    "names": read_csv(build.review / "municipality_names.csv"),
                },
            )
            deals.extend(result.deals)
            identifiers.update(result.identifiers)
            deal_sources.append(entry.key)
            if source == "prop_sales":
                sale_sources.append(entry.key)
        elif source in COLLECTED_FAMILIES:
            payload = build.raw(entry, family_archive=True)
            if not isinstance(payload, list):
                raise AssemblyError("assembly_family_shape_invalid")
            receipt = build.receipts[entry.key]
            table = family_table_name(source)
            cells = parse_family_rows(
                entry,
                payload,
                retrieved_utc=str(receipt["retrieved_utc"]),
                sha256=str(receipt["sha256"]),
            )
            family_rows[table].extend(asdict(cell) for cell in cells)
            family_sources[table].add(entry.key)
        elif source == "tenders_pub":
            confirmation = load_confirmation(build.review / "s2_t13_confirmation.yaml")
            if entry.key not in build.selected:
                if own_run_pending(confirmation, entry, None):
                    continue
                raise AssemblyError("snapshot_selection_invalid")
            payload = build.raw(entry, standard_json=True)
            if not isinstance(payload, dict) or not isinstance(
                payload.get("pages"), list
            ):
                raise AssemblyError("assembly_tenders_shape_invalid")
            pages = tuple(
                (str(row["html"]), str(row["list_name"]), str(row["language"]))
                for row in payload["pages"]
            )
            completion_evidence(
                confirmation,
                entry,
                build.receipts[entry.key],
            )
            published = publish_tenders(rows_from_pages(*pages).rows, recorded=True)
            build.table("pub_tender", [asdict(r) for r in published.rows], (entry.key,))
    if deal_sources:
        from .property.price_as_of import (
            as_of_from_receipt,
            require_price_as_of,
            row_has_price_figure,
        )
        from .property.quarter import expected_as_of

        as_of_by_source = {
            entry.source_id: as_of_from_receipt(build.receipts[entry.key])
            for entry in build.entries
            if entry.key in deal_sources
        }
        if sale_sources:
            sale_rows = sale_aggregates(deals, as_of_by_source=as_of_by_source)
            for row in sale_rows:
                require_price_as_of(row, as_of_by_source["prop_sales"])
            refuse_release_identifiers(sale_rows, frozenset(identifiers))
            build.table("pub_property_sale", list(sale_rows), tuple(sale_sources))
        quarter_rows = quarter_aggregates(deals, as_of_by_source=as_of_by_source)
        refuse_release_identifiers(quarter_rows, frozenset(identifiers))
        expected = expected_as_of(deals, as_of_by_source)
        for row in quarter_rows:
            if row_has_price_figure(row):
                key = (
                    str(row["district_key"]),
                    str(row["municipality_code"]),
                    str(row["period"]),
                    str(row["use_key"]),
                    str(row["unit_type"]),
                )
                require_price_as_of(row, expected[key])
        build.table("pub_property_quarter", list(quarter_rows), tuple(deal_sources))
    for table in sorted(family_rows):
        build.table(table, family_rows[table], tuple(sorted(family_sources[table])))


def _features(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    features = []
    for layer in layers:
        if not isinstance(layer, dict) or not isinstance(layer.get("features"), list):
            raise AssemblyError("assembly_gis_shape_invalid")
        features.extend(layer["features"])
    return features
