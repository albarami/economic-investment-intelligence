"""Fixed Public layer reads. Classes and hero eligibility come only from core."""

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from eii_core.calc.facts import CalculationFact
from eii_core.calc.firms_per_tower import CLASS_KEYS
from eii_core.calc.layer_classes import equal_count_classes
from eii_core.calc.public_methods import AnnualEnergy, reliability, zone_momentum
from eii_core.calc.source_geometry import validate_source_geometry
from eii_core.facts import Fact, fact_id, validate_chain
from eii_product.api.results import wire_fact
from eii_product.store.protocol import ReleaseStore
from eii_product.tools.make_area import PublicPoint
from eii_product.tools.public_context_tools import chain, read
from eii_product.tools.sector_facts import Context, Inputs

PUBLIC_LAYER_KEYS = (
    "public_places",
    "land_prices",
    "rail_plan",
    "health_centres",
    "zoning",
    "commercial_points",
    "address_points",
    "parcels",
    "landmarks",
    "fdi_projects",
    "property_prices",
    "night_lights",
    "zone_electricity_growth",
    "company_points",
)
# The same closed point/listing set the browser filters. Source-geography
# layers (including point-shaped rail features) never enter this snapshot.
PUBLIC_POINT_LAYER_KEYS = (
    "public_places",
    "commercial_points",
    "address_points",
    "landmarks",
    "fdi_projects",
)


def public_point_snapshot(store: ReleaseStore) -> Mapping[str, tuple[PublicPoint, ...]]:
    """Use the serving release's fixed reads and exact emitted feature IDs.

    Called only after successful make_area validation/geometry. No request may
    supply these points, and a read refusal propagates through the result boundary.
    """
    result = {}
    for key in PUBLIC_POINT_LAYER_KEYS:
        body = read_layer(store, key)
        features = body["payload"]["layers"][0]["features"]
        result[key] = tuple(
            (
                feature["feature_id"],
                Decimal(str(feature["position"][1])),
                Decimal(str(feature["position"][0])),
            )
            for feature in features
            if feature["geometry_kind"] == "point" and "position" in feature
        )
    return result


TABLES = {
    "public_places": "pub_place",
    "land_prices": "pub_land_price",
    "rail_plan": "pub_rail_plan",
    "health_centres": "pub_health_centre",
    "zoning": "pub_zoning",
    "commercial_points": "pub_poi_comm",
    "address_points": "pub_address_point",
    "parcels": "pub_parcel",
    "landmarks": "gazetteer",
    "fdi_projects": "fdi_projects",
    "property_prices": "pub_property_sale",
    "night_lights": "pub_night_lights",
    "zone_electricity_growth": "pub_zone_utility",
    "company_points": "pub_register_company",
}
METRICS = {
    "public_places": "place_listing",
    "land_prices": "guide_price_class",
    "rail_plan": "rail_feature",
    "health_centres": "health_centre_name",
    "zoning": "permitted_use",
    "commercial_points": "poi_category",
    "address_points": "address_zone",
    "parcels": "parcel_area",
    "landmarks": "landmark_name",
    "fdi_projects": "fdi_company",
    "property_prices": "district_sale",
    "night_lights": "radiance_class",
    "zone_electricity_growth": "electricity_growth_class",
    "company_points": "register_company_point",
}

# Document 03 section 7.3, including the additional page fields loaded by S2-T12.
FDI_FIELDS = (
    "project_key",
    "company",
    "source_country",
    "source_country_iso3",
    "sector",
    "sub_sector",
    "business_function",
    "project_type",
    "capex_unit",
    "location_text",
    "municipality_code",
    "place_key",
    "project_id",
    "project_year",
    "project_month",
    "capex_currency",
    "tags",
    "tech_level_id",
    "city_id",
    "world_region_id",
    "src_country_id",
    "fdi_sector_id",
    "src_world_region_id",
    "src_state_id",
    "function_id",
    "src_city_id",
    "sector_id",
    "state_id",
    "country_id",
    "parent_company_id",
    "project_type_id",
    "src_state_name",
    "freezone_name",
    "city_name",
    "state_name",
    "src_world_region_name",
    "country_name",
    "description",
    "parent_company_name",
    "naics_sub_sector_name",
    "src_city_name",
    "state_abbr",
    "world_region_name",
    "parent_company_website",
    "fdi_sector_name",
    "province",
)


def segments(value: str, record: str) -> list[dict[str, str]]:
    # Published strings with digits are references, never silently stripped names.
    if any(c.isdecimal() for c in value):
        return [
            {
                "kind": "reference",
                "referenceKind": "published_text",
                "value": value,
                "recordId": record,
            }
        ]
    return [{"kind": "plain", "text": value}]


def announced_kind(value: str) -> str:
    """Copy the source precision; do not invent a missing month or day."""
    patterns = (
        ("calendar_year", r"[1-9][0-9]{3}"),
        ("calendar_month", r"[1-9][0-9]{3}-(?:0[1-9]|1[0-2])"),
        (
            "calendar_date",
            r"[1-9][0-9]{3}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])",
        ),
    )
    for kind, pattern in patterns:
        if re.fullmatch(pattern, value):
            return kind
    raise ValueError("announced_invalid")


def source_geometry(value: str) -> dict[str, Any]:
    """Decode without dropping, reordering or simplifying source vertices."""
    import shapely

    shape = shapely.from_wkb(bytes.fromhex(value))
    interface = shape.__geo_interface__

    def lists(item: Any) -> Any:
        return (
            [lists(child) for child in item]
            if isinstance(item, (tuple, list))
            else item
        )

    geometry = {
        "type": interface["type"],
        "coordinates": lists(interface["coordinates"]),
    }
    return validate_source_geometry(geometry)


def polygon_fields(value: str) -> dict[str, Any]:
    geometry = source_geometry(value)
    # Keep the existing simple-ring wire shape byte-identical. The closed
    # geometry member represents holes and every part when a ring cannot.
    if geometry["type"] == "Polygon":
        ring, *holes = geometry["coordinates"]
        if not holes:
            return {"ring": ring}
    if geometry["type"] not in ("Polygon", "MultiPolygon"):
        raise ValueError("source_geometry_invalid")
    return {"geometry": geometry}


class LayerRead:
    def __init__(self, store: ReleaseStore, key: str):
        self.store = store
        self.key = key
        self.facts: dict[str, Fact] = {}
        self.sources: dict[str, dict[str, Any]] = {}

    def fact(
        self,
        table: str,
        metric: str,
        value: Any,
        unit: str,
        period: str,
        code: str,
        qualifiers: Mapping[str, str] | None = None,
        caveats: tuple[str, ...] = (),
        source_id: str | None = None,
    ) -> Fact | None:
        try:
            source, lines, sources = chain(self.store, table)
        except ValueError:
            return None
        if validate_chain(source.lineage_ref, lines, sources) is not None:
            return None
        if source_id is not None and source_id not in {
            line["source_id"] for line in lines if line["table_name"] == table
        }:
            return None
        geography = {"kind": "public", "public_code": code}
        identifier = fact_id(
            release_id=self.store.release_id,
            metric_key=metric,
            geography=geography,
            period=period,
            qualifiers=qualifiers or {},
        )
        fact = Fact.model_validate(
            dict(
                fact_id=identifier,
                value=value,
                unit=unit,
                period=period,
                geography=geography,
                provenance="public",
                input_classes=["public"],
                evidence_status="observed",
                reliability=reliability(None),
                coverage_keys=[],
                caveat_keys=list(caveats),
                label_en="Published layer value",
                label_ar="قيمة الطبقة المنشورة",
                lineage_ref=source.lineage_ref,
                release_id=self.store.release_id,
            )
        )
        self.facts[fact.fact_id] = fact
        for src in sources:
            self.sources.setdefault(
                src["source_id"],
                {
                    "sourceId": src["source_id"],
                    "attribution": segments(src["title"], src["source_id"]),
                    "publisher": segments(src["publisher"], src["source_id"]),
                    "datasetOrPage": src["title"],
                    "licenceOrTerms": src["licence"],
                    "retrievalDate": str(src["retrieved_on"]),
                },
            )
        return fact

    def feature(
        self, identifier: str, fact: Fact, metric: str, **fields: Any
    ) -> dict[str, Any]:
        return dict(
            feature_id=identifier,
            metric_key=metric,
            provenance="public",
            fact_id=fact.fact_id,
            subject="statistic",
            geometry_kind="fill",
            **fields,
        )

    def response(self, features: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
        if self.key in {"night_lights", "land_prices", "zone_electricity_growth"}:
            if any(feature.get("class_id") not in CLASS_KEYS for feature in features):
                raise ValueError("class_missing")
            for group in fields.get("class_breaks", []):
                if set(group) != {"group_key", "breaks"} or any(
                    set(band) != {"class_id", "fact_id"} for band in group["breaks"]
                ):
                    raise ValueError("class_break_invalid")
        layer = dict(
            key=self.key,
            visible=True,
            source_chain_fact_id=next(iter(self.facts), ""),
            source_id=next(iter(self.sources), ""),
            features=features,
            **fields,
        )
        payload: dict[str, Any] = {
            "layers": [layer],
            "sources": list(self.sources.values()),
            "gazetteer_points": [],
        }
        return {
            "status": "ok" if features else "NO_DATA",
            "facts": [wire_fact(f) for f in self.facts.values()],
            "coverage_report": {"counts": {}},
            "payload": payload,
        }


def class_group(
    features: list[dict[str, Any]], facts: Mapping[str, Fact], group: str | None
) -> dict[str, Any]:
    classes = equal_count_classes(
        [
            (f["feature_id"], cast(Decimal | int, facts[f["fact_id"]].value))
            for f in features
        ]
    )
    by = {f["feature_id"]: f for f in features}
    for f in features:
        f["class_id"] = classes.classes[f["feature_id"]]
    return {
        "group_key": group,
        "breaks": [
            {"class_id": b.class_key, "fact_id": by[b.boundary_key]["fact_id"]}
            for b in classes.breaks
        ],
    }


def read_layer(
    store: ReleaseStore, key: str, month_key: str | None = None
) -> dict[str, Any]:
    ctx = LayerRead(store, key)
    if key == "company_points":
        return seal_company_points(company_points(ctx), store)
    if key == "zone_electricity_growth":
        return hero(ctx)
    if key == "land_prices":
        return land(ctx)
    if key == "night_lights":
        months = read(store, "layer_night_lights_months")
        if month_key is None:
            # Queries return key order; the latest published string is the declared default.
            month_key = months[-1]["period"] if months else None
        rows = (
            read(store, "layer_night_lights", month_key=month_key) if month_key else []
        )
        features = []
        from h3 import get_resolution, int_to_str

        for row in rows:
            if row["radiance"] is None:
                continue
            f = ctx.fact(
                "pub_night_lights",
                "radiance_class",
                row["radiance"],
                "radiance_nw_cm2_sr",
                row["period"],
                "cell:" + str(row["cell"]),
                caveats=("night_lights_not_activity",),
                source_id=row["source_id"],
            )
            if f:
                feature = ctx.feature(
                    "night:" + str(row["cell"]),
                    f,
                    "radiance_class",
                    cell=int_to_str(row["cell"]),
                    resolution=get_resolution(int_to_str(row["cell"])),
                )
                feature["geometry_kind"] = "hex"
                features.append(feature)
        body = ctx.response(
            features,
            **(
                {"class_breaks": [class_group(features, ctx.facts, None)]}
                if features
                else {}
            ),
        )
        if features:
            body["payload"]["night"] = {
                "month": month_key,
                "direction": "higher",
                "class_id": features[0]["class_id"],
                "unit": "radiance_nw_cm2_sr",
                "caveat_key": "night_lights_not_activity",
            }
        return body
    return ordinary(ctx)


def land(ctx: LayerRead) -> dict[str, Any]:
    geometry = {
        r["district_key"]: r for r in read(ctx.store, "layer_district_geometry")
    }
    features = []
    for row in read(ctx.store, "layer_land_prices"):
        district = geometry.get(row["district_key"])
        if district is None or row["guide_price"] is None:
            continue
        identifier = (
            "land:"
            + row["use_category"]
            + ":"
            + row["district_key"].removeprefix("INVENTED-district-")
        )
        f = ctx.fact(
            "pub_land_price",
            "guide_price_class",
            row["guide_price"],
            "qar_per_ft2",
            row["period"],
            "district:" + row["district_key"],
            {"use_category": row["use_category"], "price_basis": row["price_basis"]},
            source_id=row["source_id"],
        )
        if f:
            feature = ctx.feature(
                identifier,
                f,
                "guide_price_class",
                class_group=row["use_category"],
                **polygon_fields(district["geometry"]),
                name_segments=segments(district["name_en"], identifier),
            )
            features.append(feature)
    groups = []
    for use in sorted({f["class_group"] for f in features}):
        groups.append(
            class_group(
                [f for f in features if f["class_group"] == use], ctx.facts, use
            )
        )
    return ctx.response(features, **({"class_breaks": groups} if groups else {}))


def hero(ctx: LayerRead) -> dict[str, Any]:
    calc_ctx = Context(
        ctx.store,
        Inputs(activity="INVENTED", topic="zone_momentum", geography="national"),
    )
    rows = read(ctx.store, "sector_facts_utility", periods=["2021", "2025"])
    totals = read(ctx.store, "sector_facts_utility_national", periods=["2021", "2025"])

    def energy(row: Mapping[str, Any], national: bool = False) -> AnnualEnergy:
        code = "national" if national else "zone:" + row["zone_code"]
        reading = calc_ctx.measure(row, "pub_zone_utility", "value", "kwh", code)
        return AnnualEnergy(
            code,
            {"2021": 2021, "2025": 2025}[row["period"]],
            reading.value,
            national or row["completeness"] == "complete",
            reading,
        )

    national = {r["period"]: energy(r, True) for r in totals}
    result = cast(
        dict[str, Any],
        zone_momentum([energy(r) for r in rows], national["2021"], national["2025"]),
    )
    features = []
    not_ranked = []
    for zone in read(ctx.store, "layer_zone_geometry"):
        key = "zone:" + zone["zone_code"]
        values = result["zones"].get(key)
        ratio = values.get("ranked_ratio") if isinstance(values, dict) else None
        geometry = polygon_fields(zone["geometry"])
        name = segments(zone["name_en"], key)
        if isinstance(values, dict) and values["ranked_unrounded"] is True:
            built = calc_ctx.calculated(
                cast(CalculationFact, ratio),
                qualifiers={"utility": "electricity"},
                caveats=("activity_proxy_not_population",),
            )
            if built:
                # Register its verified chain and preserve the calculator's fact unchanged.
                registered = ctx.fact(
                    "pub_zone_utility",
                    "ranked_ratio",
                    built.value,
                    built.unit,
                    built.period,
                    key,
                    {"utility": "electricity"},
                )
                if registered:
                    ctx.facts.pop(registered.fact_id)
                ctx.facts[built.fact_id] = built
                features.append(
                    ctx.feature(
                        key,
                        built,
                        "electricity_growth_class",
                        **geometry,
                        name_segments=name,
                    )
                )
        else:
            reason = (
                "below_ranking_floor"
                if isinstance(ratio, CalculationFact)
                else (
                    "missing_input"
                    if values is None
                    else getattr(values, "reason", "no_denominator")
                )
            )
            not_ranked.append(
                dict(feature_id=key, **geometry, reason_key=reason, name_segments=name)
            )
    return ctx.response(
        features,
        not_ranked=not_ranked,
        **(
            {"class_breaks": [class_group(features, ctx.facts, None)]}
            if features
            else {}
        ),
    )


def ordinary(ctx: LayerRead) -> dict[str, Any]:
    key = ctx.key
    table = TABLES[key]
    rows = [(table, r) for r in read(ctx.store, "layer_" + key)]
    if key == "public_places":
        rows.extend(
            ("pub_place_fsq", r) for r in read(ctx.store, "layer_public_places_fsq")
        )
    districts = (
        {r["district_key"]: r for r in read(ctx.store, "layer_district_geometry")}
        if key == "property_prices"
        else {}
    )
    features = []
    gazetteer_points: list[str] = []
    filter_options: dict[str, list[dict[str, Any]]] = {
        name: [] for name in ("sector", "source_country", "period", "stated_location")
    }
    for table, row in rows:
        identifier = (
            row["project_key"]
            if key == "fdi_projects"
            else str(
                next(
                    row[k]
                    for k in (
                        "place_id",
                        "fsq_place_id",
                        "feature_key",
                        "place_key",
                        "project_key",
                        "district_key",
                    )
                    if k in row
                )
            )
        )
        period = row.get("period") or "published"
        value = (
            row.get("name") or row.get("name_en") or row.get("company") or identifier
        )
        unit = "published_text"
        if key == "parcels":
            value, unit = row["area_m2"], "square_metre"
        if key == "property_prices":
            value, unit = row["median_price_per_m2"], "qar_per_m2"
        if value is None:
            continue
        if unit == "published_text" and not any(c.isdecimal() for c in str(value)):
            source, _, _ = chain(ctx.store, table)
            value, unit = source.retrieved, "calendar_date"
        fact = ctx.fact(
            table,
            METRICS[key],
            value,
            unit,
            period,
            (
                "district:"
                if key == "property_prices"
                else "place:"
                if key
                in {"public_places", "commercial_points", "landmarks", "health_centres"}
                else "feature:"
            )
            + identifier,
            source_id=row["source_id"],
        )
        if fact is None:
            continue
        feature = ctx.feature(
            identifier if key == "fdi_projects" else key + ":" + identifier,
            fact,
            METRICS[key],
            source_id=row["source_id"],
            name_segments=segments(
                str(
                    row.get("name")
                    or row.get("name_en")
                    or row.get("company")
                    or identifier
                ),
                identifier,
            ),
        )
        if key == "fdi_projects":
            fdi_fields(ctx, row, feature, gazetteer_points, filter_options)
            features.append(feature)
            continue
        if table == "pub_place_fsq":
            release = row["source_release"]
            # Validate the copied reference with the same strict date contract.
            Fact.model_validate(
                {**fact.model_dump(), "unit": "calendar_date", "value": release}
            )
            source_entry = ctx.sources[row["source_id"]]
            previous = source_entry.get("sourceRelease")
            if previous is not None and previous["value"] != release:
                raise ValueError("source_release_conflict")
            source_entry["sourceRelease"] = {
                "referenceKind": "calendar_date",
                "value": release,
                "recordId": row["source_id"] + "-release",
            }
        if key == "property_prices":
            district = districts.get(row["district_key"])
            if district is None:
                continue
            feature.update(polygon_fields(district["geometry"]))
        elif "geometry" in row:
            geometry = source_geometry(row["geometry"])
            if geometry["type"] == "Point":
                feature.update(
                    geometry_kind="point",
                    subject="place",
                    position=geometry["coordinates"],
                )
            elif geometry["type"] == "LineString":
                feature.update(geometry_kind="line", path=geometry["coordinates"])
            else:
                feature.update(
                    geometry_kind="outline", **polygon_fields(row["geometry"])
                )
        else:
            feature.update(
                geometry_kind="point",
                subject="place",
                position=[
                    float(row["lon"]),
                    float(row["lat"]),
                ],
            )
        if key == "rail_plan" and feature["geometry_kind"] == "point":
            feature["status_key"] = "planned"
        if key == "zoning":
            feature["words"] = {"permitted_use": row["permitted_uses"]}
        if key == "address_points":
            feature["address"] = {
                k: row[k + "_number"] for k in ("zone", "street", "building")
            }
        features.append(feature)
    body = ctx.response(features)
    if key == "fdi_projects" and ctx.sources:
        body["payload"]["gazetteer_points"] = gazetteer_points
        body["payload"]["filter_options"] = filter_options
        src = next(iter(ctx.sources.values()))
        body["payload"]["credits"] = {
            "publisher": src["publisher"],
            "gatherer": src["attribution"],
            "read_on": src["retrievalDate"],
            "dashboard_url": chain(ctx.store, "fdi_projects")[0].url,
        }
    return body


def fdi_fields(
    ctx: LayerRead,
    row: dict[str, Any],
    feature: dict[str, Any],
    gazetteer_points: list[str],
    filter_options: dict[str, list[dict[str, Any]]],
) -> None:
    """Copy the closed published columns. Never infer a field or a location."""
    identifier = row["project_key"]
    year = row["announced"][:4] if row["announced"] else str(row["project_year"] or "")
    feature.update(
        subject="fdi_project",
        geometry_kind="point",
        year=year,
        place_key=row["place_key"],
        caveat_keys=["fdi_estimates"],
    )

    def fact(field: str, value: Any, unit: str, metric: str = "fdi_field") -> Fact:
        built = ctx.fact(
            "fdi_projects",
            metric,
            value,
            unit,
            year or "undated",
            "feature:" + identifier,
            {"field": field},
            caveats=("fdi_estimates",) if metric in {"fdi_capex", "fdi_jobs"} else (),
            source_id=row["source_id"],
        )
        if built is None:
            raise ValueError("fdi_field_unbound")
        return built

    def text_field(field: str, value: str) -> list[dict[str, str]]:
        parts = segments(value, identifier)
        if parts[0]["kind"] == "reference":
            parts[0]["recordId"] = fact(field, value, "published_text").fact_id
        return parts

    feature["field_segments"] = {
        field: text_field(field, str(row[field]))
        for field in FDI_FIELDS
        if row[field] is not None
    }
    feature["words"] = {
        field: parts[0]["text"]
        for field, parts in feature["field_segments"].items()
        if parts[0]["kind"] == "plain"
    }
    if row["announced"] is not None:
        kind = announced_kind(row["announced"])
        announced = fact("announced", row["announced"], kind)
        feature["announced"] = dict(
            referenceKind=kind, value=row["announced"], recordId=announced.fact_id
        )
    for field, slot, metric, unit in (
        ("capex_value", "capex_fact_id", "fdi_capex", "usd_million"),
        ("jobs", "jobs_fact_id", "fdi_jobs", "announced_jobs"),
        ("lng", "lon_fact_id", "fdi_location", "decimal_degree"),
        ("lat", "lat_fact_id", "fdi_location", "decimal_degree"),
    ):
        if row[field] is not None:
            if field == "capex_value" and (
                row["capex_unit"],
                row["capex_currency"],
            ) != ("Mn USD", "USD"):
                raise ValueError("fdi_capex_unit_invalid")
            feature[slot] = fact(field, row[field], unit, metric).fact_id
    supported = (
        read(ctx.store, "layer_fdi_gazetteer", place_key=row["place_key"])
        if row["place_key"]
        else []
    )
    if supported:
        point = supported[0]
        if point["place_key"] not in gazetteer_points:
            gazetteer_points.append(point["place_key"])
        feature["position"] = [float(point["lon"]), float(point["lat"])]
    if row["lng"] is not None and row["lat"] is not None:
        feature["position"] = [float(row["lng"]), float(row["lat"])]
    feature["filter"] = {}
    for key, field, value in (
        ("sector", "sector", row["sector"]),
        ("source_country", "source_country", row["source_country"]),
        ("period", "project_year", year or None),
        ("stated_location", "location_text", row["location_text"]),
    ):
        if value is None:
            continue
        value = str(value)
        feature["filter"][key] = value
        if not any(option["key"] == value for option in filter_options[key]):
            label = text_field("filter_" + field, value)
            filter_options[key].append(dict(key=value, label=label))


# S3-T12 box 12: the commerce register's establishment points. A point is the
# centre of the company's registered base cell and carries no origin meaning
# (decision 0035 item 1). The card holds the register's published fields that
# the release contract carries (docs/03 section 7.3), person names excluded.
REGISTER_COMPANY_CARD_FIELDS = ("establishment_nationality",)
# The application serves public_only releases only (release.py `Summary`), and
# `register_company_list` is Protected: the count is absent, never a zero.
COMPANY_ABSENT_REASON = "protected_not_in_public_release"
COMPANY_CARD_KEYS = frozenset({"feature_id", "row_id", "fields", "employee_count"})
# The card is closed at every nesting level: a field, a segment and the count
# each hold exactly these keys, and every leaf is a string.
COMPANY_FIELD_KEYS = frozenset({"key", "segments"})
COMPANY_SEGMENT_KEYS = {
    "plain": frozenset({"kind", "text"}),
    "reference": frozenset({"kind", "referenceKind", "value", "recordId"}),
}
COMPANY_FEATURE_KEYS = frozenset(
    {
        "feature_id",
        "metric_key",
        "provenance",
        "fact_id",
        "subject",
        "geometry_kind",
        "source_id",
        "position",
    }
)


class CompanyPointRefusal(ValueError):
    """A labour, residence, Simulated or Synthetic detail on a register company."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _company_token(registration: str) -> str:
    """An opaque feature token; the register's own key never reaches the wire."""
    import hashlib

    return hashlib.sha256(registration.encode()).hexdigest()[:16]


def company_points(ctx: LayerRead) -> dict[str, Any]:
    from h3 import cell_to_latlng, int_to_str

    features: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    try:
        source, _, _ = chain(ctx.store, "pub_register_company")
    except ValueError:
        # A broken source chain draws no point (rule 7).
        rows: list[dict[str, Any]] = []
    else:
        rows = read(ctx.store, "layer_company_points")
    for row in rows:
        if row["registered_cell"] is None:
            continue
        token = _company_token(str(row["registration_number"]))
        fact = ctx.fact(
            "pub_register_company",
            "register_company_point",
            source.retrieved,
            "calendar_date",
            "published",
            "feature:company-" + token,
            source_id=row["source_id"],
        )
        if fact is None:
            continue
        lat, lon = cell_to_latlng(int_to_str(int(row["registered_cell"])))
        identifier = "company_points:" + token
        feature = ctx.feature(
            identifier,
            fact,
            "register_company_point",
            source_id=row["source_id"],
        )
        feature.update(geometry_kind="point", subject="business", position=[lon, lat])
        features.append(feature)
        cards.append(
            {
                "feature_id": identifier,
                "row_id": "company-" + token,
                # The contract holds no field fact for a card field: a
                # digit-bearing value leaves here as an unbound reference and
                # the seal refuses the response (rule 7).
                "fields": [
                    {"key": name, "segments": segments(str(row[name]), identifier)}
                    for name in REGISTER_COMPANY_CARD_FIELDS
                    if row[name] is not None
                ],
                "employee_count": {
                    "state": "absent",
                    "reason_key": COMPANY_ABSENT_REASON,
                },
            }
        )
    body = ctx.response(features)
    body["payload"]["company_cards"] = cards
    return body


def seal_company_points(body: dict[str, Any], store: ReleaseStore) -> dict[str, Any]:
    """Refuse the response if any point, label or card holds anything else.

    Only Public facts of `pub_register_company` may bind a point; a wage, a
    wage bill or any other labour or residence detail, a Simulated figure and a
    Synthetic figure (the permitted `employee_count` is absent in public_only)
    each refuse the whole response (FE-103, FE-115, DAT-140). A card is closed
    at every nesting level, and a point's fact and a card reference each bind a
    carried fact of the `company_points` entry's own table and metric (`TABLES`,
    `METRICS`).
    """
    for fact in body["facts"]:
        if fact["provenance"] != "public" or fact["input_classes"] != ["public"]:
            raise CompanyPointRefusal("not_public")
    facts = {fact["fact_id"]: fact for fact in body["facts"]}
    try:
        lineage: str | None = chain(store, TABLES["company_points"])[0].lineage_ref
    except ValueError:
        # A broken source chain binds no point and no reference (rule 7).
        lineage = None
    for layer in body["payload"]["layers"]:
        for feature in layer["features"]:
            if set(feature) - COMPANY_FEATURE_KEYS:
                raise CompanyPointRefusal("detail_on_point")
            position = feature["position"]
            if (
                not all(
                    isinstance(value, str)
                    for key, value in feature.items()
                    if key != "position"
                )
                or not isinstance(position, list)
                or not all(type(value) is float for value in position)
            ):
                raise CompanyPointRefusal("detail_on_point")
            try:
                _lon, _lat = position
            except (ValueError, TypeError) as exc:
                raise CompanyPointRefusal("detail_on_point") from exc
            if (
                feature["provenance"] != "public"
                or feature["metric_key"] != "register_company_point"
                or feature["subject"] != "business"
                or feature["geometry_kind"] != "point"
            ):
                raise CompanyPointRefusal("not_public")
    for card in body["payload"]["company_cards"]:
        if not isinstance(card, dict) or set(card) != COMPANY_CARD_KEYS:
            raise CompanyPointRefusal("detail_on_card")
        if not isinstance(card["feature_id"], str) or not isinstance(
            card["row_id"], str
        ):
            raise CompanyPointRefusal("detail_on_card")
        if not isinstance(card["fields"], list):
            raise CompanyPointRefusal("detail_on_card")
        for field in card["fields"]:
            _seal_company_field(field, facts, lineage, store.release_id)
        if card["employee_count"] != {
            "state": "absent",
            "reason_key": COMPANY_ABSENT_REASON,
        }:
            raise CompanyPointRefusal("employee_count_not_released")
    # No point without its fact (rules 7 and 19): the fact a point names is
    # carried here and is the entry's own, as for a card reference.
    for layer in body["payload"]["layers"]:
        for feature in layer["features"]:
            if not _company_entry_fact(
                facts.get(feature.get("fact_id")), lineage, store.release_id
            ):
                raise CompanyPointRefusal("point_fact_unbound")
    return body


def _seal_company_field(
    field: Any, facts: Mapping[str, Any], lineage: str | None, release_id: str
) -> None:
    """One card field: exactly its keys, typed segments, no unbound numeral."""
    if not isinstance(field, dict) or set(field) != COMPANY_FIELD_KEYS:
        raise CompanyPointRefusal("detail_on_card")
    if field["key"] not in REGISTER_COMPANY_CARD_FIELDS:
        raise CompanyPointRefusal("detail_on_card")
    parts = field["segments"]
    if not isinstance(parts, list) or not parts:
        raise CompanyPointRefusal("detail_on_card")
    for part in parts:
        if not isinstance(part, dict) or not all(
            isinstance(value, str) for value in part.values()
        ):
            raise CompanyPointRefusal("detail_on_card")
        keys = COMPANY_SEGMENT_KEYS.get(part.get("kind", ""))
        if keys is None or frozenset(part) != keys:
            raise CompanyPointRefusal("detail_on_card")
        if part["kind"] == "plain":
            if any(c.isdigit() for c in part["text"]):
                raise CompanyPointRefusal("numeral_in_plain_segment")
            continue
        # No number without its fact (rules 7 and 23): a reference names a
        # fact this response carries, of the same unit and the same value.
        bound = facts.get(part["recordId"])
        if (
            bound is None
            or bound["unit"] != part["referenceKind"]
            or bound["value"] != part["value"]
        ):
            raise CompanyPointRefusal("card_reference_unbound")
        if not _company_entry_fact(bound, lineage, release_id):
            raise CompanyPointRefusal("card_reference_unbound")


def _company_entry_fact(bound: Any, lineage: str | None, release_id: str) -> bool:
    """Whether a carried fact is of the `company_points` entry's table and metric.

    The wire fact names no table and no metric. Its table is the one its
    lineage belongs to, and its identifier holds its metric key (DAT-93): both
    are the entry's own (`TABLES`, `METRICS`). A point and a card reference
    are held to this one test.
    """
    if bound is None or lineage is None or bound["lineage_ref"] != lineage:
        return False
    return bool(
        bound["fact_id"]
        == fact_id(
            release_id=release_id,
            metric_key=METRICS["company_points"],
            geography=bound["geography"],
            period=bound["period"],
            qualifiers={},
        )
    )
