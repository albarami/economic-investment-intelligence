"""Layer route for the financial centre's firms per tower.

One key of the closed list is served. Counts come from ``eii_core.calc``.
A fact is emitted only when its lineage resolves. Positions come only from
reviewed rows that agree.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from eii_core.calc.facts import SourceChain
from eii_core.calc.firms_per_tower import (
    CLOSED_CLASS_KEYS,
    ClassBreak,
    DistrictCount,
    FirmsPerTower,
    TowerCount,
    firms_per_tower,
)
from eii_core.calc.public_methods import reliability
from eii_core.facts import Fact, fact_id, validate_chain
from eii_product.register_file import (
    DistrictGeometry,
    GazetteerPlace,
    RegisterBundle,
    RegisterRefusal,
    RegisterRow,
    read_fc_register_rows,
)

FC_CLASS_KEYS = CLOSED_CLASS_KEYS

LAYER_KEY = "fc_firms_per_tower"
CLOSED_LAYER_KEYS = frozenset(
    {
        "zone_electricity_growth",
        "licence_density",
        "transit_riders",
        "presence",
        "crowd_density",
        "traffic",
        "flows",
        "public_places",
        "release_units",
        "openings",
        "closures",
        "firm_density",
        "company_points",
        "fc_firms_per_tower",
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
        "construction_pipeline",
        "night_lights",
    }
)
RULED_REPORT_KEYS = frozenset(
    {
        "zone_without_district",
        "location_unresolved",
        "tower_without_position",
        "tower_without_gazetteer_place",
    }
)
SCREEN_NOTE_KEYS = ("zone_without_district",)
_LABELS = ("Firms registered here", "الشركات المسجلة هنا")


class CoverageKeyError(ValueError):
    """A coverage reason outside the ruled report keys."""

    def __init__(self) -> None:
        super().__init__("reason_unknown")


def seal_coverage(counts: Mapping[str, int]) -> dict[str, int]:
    """Keep ruled report keys only. An unknown key is refused."""
    sealed: dict[str, int] = {}
    for key, value in counts.items():
        if key not in RULED_REPORT_KEYS or type(value) is not int or value < 1:
            raise CoverageKeyError()
        sealed[key] = value
    return sealed


def build_layer_router(
    setting: str | None,
    rows_reader: Callable[..., RegisterBundle | None] = read_fc_register_rows,
    *,
    public_readers: Mapping[str, Callable[[str | None], dict[str, object]]]
    | None = None,
) -> APIRouter:
    """Serve ``GET /api/layers/{layer}`` for the one key this task owns."""
    router = APIRouter()

    @router.get("/api/layers/{layer}")
    def get_layer(layer: str, request: Request) -> JSONResponse:
        if public_readers is not None and layer in public_readers:
            import re

            from eii_product.api.results import error_response

            pairs = list(request.query_params.multi_items())
            month = None
            if pairs:
                if (
                    layer != "night_lights"
                    or len(pairs) != 1
                    or pairs[0][0] != "month_key"
                    or re.fullmatch(r"[1-9][0-9]{3}-(0[1-9]|1[0-2])", pairs[0][1])
                    is None
                ):
                    return _invalid()
                month = pairs[0][1]
            try:
                return JSONResponse(content=public_readers[layer](month))
            except Exception as error:
                return error_response(error)
        if request.query_params:
            return _invalid()
        if layer not in CLOSED_LAYER_KEYS:
            return _missing()
        if layer != LAYER_KEY:
            return _not_implemented()
        if setting is None:
            return _no_data("missing_input")
        try:
            bundle = rows_reader(setting)
        except RegisterRefusal as exc:
            if exc.reason == "read_refused":
                return _no_data("read_refused")
            raise
        if bundle is None or _chain_broken(bundle):
            return _no_data("missing_input")
        body = _serve(bundle)
        return JSONResponse(status_code=200, content=body)

    return router


def _invalid() -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_ARGUMENT"}},
    )


def _missing() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND"}})


def _not_implemented() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "NOT_IMPLEMENTED", "reason": "not_implemented"}},
    )


def _no_data(reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"status": "NO_DATA", "reason": reason, "facts": []},
    )


def _chain_broken(bundle: RegisterBundle) -> bool:
    method, version = "eii_core.calc.firms_per_tower", "v1"
    if bundle.lineage["transform"] != method + "@" + version:
        return True
    try:
        source = SourceChain(
            lineage_ref=str(bundle.lineage["lineage_id"]),
            table="pub_register_company",
            method=method,
            version=version,
            publisher=str(bundle.source["publisher"]),
            dataset=str(bundle.source["title"]),
            url=str(bundle.source["url"]),
            licence=str(bundle.source["licence"]),
            retrieved=str(bundle.source["retrieved_on"]),
            sha256=str(bundle.source["sha256"]),
        )
    except ValueError:
        return True
    return (
        validate_chain(
            str(bundle.lineage["lineage_id"]),
            [bundle.lineage],
            [bundle.source],
            numerator_table="pub_register_company",
            required_sources=(source,),
        )
        is not None
    )


def _serve(bundle: RegisterBundle) -> dict[str, object]:
    counted = firms_per_tower([_count_row(row) for row in bundle.rows])
    by_key = {row.registration_key: row for row in bundle.rows}
    features: list[dict[str, object]] = []
    companies: list[dict[str, object]] = []
    facts: list[dict[str, object]] = []
    emitted: dict[str, str] = {}
    missed = 0
    for tower in counted.towers:
        place = bundle.gazetteer.get(tower.tower)
        if place is None:
            missed += 1
            continue
        fact = _count_fact(
            bundle,
            count=tower.count,
            code=place.place_code,
        )
        feature_id = _feature_id(tower.tower)
        features.append(_tower_feature(tower, place, fact.fact_id, feature_id))
        companies.extend(_company_rows(tower, by_key, feature_id))
        facts.append(fact.model_dump(mode="json"))
        emitted[tower.tower] = fact.fact_id
    for district in counted.districts:
        geometry = bundle.districts.get(district.district_key)
        if geometry is None:
            continue
        code = "district:" + district.district_key
        fact = _count_fact(bundle, count=district.count, code=code)
        features.append(_district_feature(district, geometry, fact.fact_id))
        facts.append(fact.model_dump(mode="json"))
    coverage = dict(counted.coverage)
    if missed:
        coverage["tower_without_gazetteer_place"] = missed
    sealed = seal_coverage(coverage)
    notes = [key for key in SCREEN_NOTE_KEYS if key in sealed]
    breaks = _break_chips(counted, emitted)
    source_id = str(bundle.source["source_id"])
    chain_id = facts[0]["fact_id"] if facts else ""
    retrieved = bundle.source["retrieved_on"]
    retrieved_text = retrieved.isoformat() if hasattr(retrieved, "isoformat") else ""
    payload = {
        "layers": [
            {
                "key": LAYER_KEY,
                "visible": True,
                "source_chain_fact_id": chain_id,
                "source_id": source_id,
                "features": features,
            }
        ],
        "sources": [
            {
                "sourceId": source_id,
                "attribution": [{"kind": "plain", "text": bundle.source["title"]}],
                "retrievalDate": retrieved_text,
                "publisher": [{"kind": "plain", "text": bundle.source["publisher"]}],
                "datasetOrPage": bundle.source["title"],
                "licenceOrTerms": bundle.source["licence"],
            }
        ],
        "count_fact_ids": [chip["fact_id"] for chip in breaks],
        "count_facts": [
            {"fact_id": chip["fact_id"], "year": bundle.year} for chip in breaks
        ],
        "fc_firms": {
            "direction": "higher",
            "companies": companies,
            "coverage_note_keys": notes,
            "breaks": breaks,
            "no_data": bool(notes),
        },
    }
    return {
        "status": "ok",
        "facts": facts,
        "coverage_report": {"counts": sealed},
        "payload": payload,
    }


def _count_row(row: RegisterRow) -> dict[str, object]:
    return {
        "registration_key": row.registration_key,
        "tower_or_building": row.tower_or_building,
        "position": row.position,
        "district_key": row.district_key,
        "district_free_zone": row.district_free_zone,
    }


def _count_fact(bundle: RegisterBundle, *, count: int, code: str) -> Fact:
    geography = {"kind": "public", "public_code": code}
    identifier = fact_id(
        release_id=bundle.release_id,
        metric_key="firms_per_tower",
        geography=geography,
        period=bundle.year,
        qualifiers={},
    )
    return Fact.model_validate(
        {
            "fact_id": identifier,
            "value": count,
            "unit": "count",
            "period": bundle.year,
            "geography": geography,
            "provenance": "public",
            "input_classes": ["public"],
            "evidence_status": "observed",
            "reliability": reliability(count),
            "coverage_keys": [],
            "caveat_keys": ["calculated"],
            "label_en": _LABELS[0],
            "label_ar": _LABELS[1],
            "lineage_ref": bundle.lineage["lineage_id"],
            "release_id": bundle.release_id,
        }
    )


def _tower_feature(
    tower: TowerCount,
    place: GazetteerPlace,
    fact: str,
    feature_id: str,
) -> dict[str, object]:
    feature: dict[str, object] = {
        "feature_id": feature_id,
        "metric_key": "firms_per_tower",
        "provenance": "public",
        "subject": "place",
        "geometry_kind": "point",
        "class_id": tower.class_key,
        "fact_id": fact,
        "geography_code": place.place_code,
        "place_key": place.place_code.removeprefix("place:"),
        "words": {"name": tower.tower},
    }
    if tower.position_status == "agree" and tower.position is not None:
        feature["position"] = [float(tower.position[0]), float(tower.position[1])]
    return feature


def _district_feature(
    district: DistrictCount,
    geometry: DistrictGeometry,
    fact: str,
) -> dict[str, object]:
    return {
        "feature_id": "feat-district-" + _feature_token(geometry.district_key),
        "metric_key": "firms_per_tower",
        "provenance": "public",
        "subject": "statistic",
        "geometry_kind": "fill",
        "class_id": district.class_key,
        "fact_id": fact,
        "geography_code": "district:" + geometry.district_key,
        "words": {"name": geometry.name},
        "ring": [[float(lon), float(lat)] for lon, lat in geometry.ring],
    }


def _company_rows(
    tower: TowerCount,
    by_key: Mapping[str, RegisterRow],
    feature_id: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in tower.companies:
        row = by_key[key]
        rows.append(
            {
                "feature_id": feature_id,
                "row_id": row.row_id,
                "fields": [{"key": name, "text": text} for name, text in row.card],
            }
        )
    return rows


def _break_chips(
    counted: FirmsPerTower,
    emitted: Mapping[str, str],
) -> list[dict[str, str]]:
    chips: list[dict[str, str]] = []
    for band in counted.breaks:
        bound = _bound_fact(band, emitted)
        if bound is None:
            continue
        chips.append({"class_id": band.class_key, "fact_id": bound})
    return chips


def _bound_fact(
    band: ClassBreak,
    emitted: Mapping[str, str],
) -> str | None:
    return emitted.get(band.boundary_tower)


def _feature_token(text: str) -> str:
    """Encode a name or key injectively for a feature identifier.

    Kept characters (``[a-z0-9]``) stay as they are; every other character,
    upper-case letters included, becomes a tilde-fenced escape of its code
    point in lower-case hexadecimal. A kept character is never a tilde, so
    the fenced escape can be read back uniquely and distinct texts never
    share a token.
    """
    parts: list[str] = []
    for char in text:
        if "a" <= char <= "z" or "0" <= char <= "9":
            parts.append(char)
        else:
            parts.append("~" + format(ord(char), "x") + "~")
    return "".join(parts)


def _feature_id(tower: str) -> str:
    return "feat-tower-" + _feature_token(tower)
