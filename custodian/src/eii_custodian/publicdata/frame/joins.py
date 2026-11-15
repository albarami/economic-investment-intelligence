"""Key relations confirmed in L-202 section 3, checked again on every build."""

from typing import Any

from .checks import FrameError
from .geometry import Boundary


def join_municipalities(
    municipalities: list[Boundary], zones: list[Boundary], rows: list[dict[str, Any]]
) -> tuple[dict[str, str], list[dict[str, str]]]:
    by_zone = {str(row["ZONE_NO"]): row for row in rows}
    if len(by_zone) != len(rows) or len({z.key for z in zones}) != len(zones):
        raise FrameError("bnd_zone_2020: duplicate_zone")
    if set(by_zone) != {z.key for z in zones}:
        raise FrameError("bnd_zone_2020: zone_sets")
    mapping: dict[str, str] = {}
    for zone in zones:
        code = by_zone[zone.key]["MUNICIPAL_CODE"]
        if (
            zone.municipality_code in mapping
            and mapping[zone.municipality_code] != code
        ):
            raise FrameError("bnd_zone_2020: municipality_consistency")
        mapping[zone.municipality_code] = code
    if set(mapping) != {m.key for m in municipalities} or len(
        set(mapping.values())
    ) != len(mapping):
        raise FrameError("bnd_zone_2020: municipality_bijection")
    review = []
    for municipality in municipalities:
        zone = next(z for z in zones if z.municipality_code == municipality.key)
        row = by_zone[zone.key]
        review.append(
            {
                "hdx_code": municipality.key,
                "municipality_code": mapping[municipality.key],
                "name_en": municipality.name_en,
                "name_ar": municipality.name_ar,
                "layer_name_en": row["Municipality_En"],
                "layer_name_ar": row["Municipality_Ar"],
            }
        )
    return mapping, review


def join_districts(
    districts: list[Boundary],
    rows: list[dict[str, Any]],
    census: list[dict[str, Any]],
    aliases: list[dict[str, str]],
) -> tuple[dict[tuple[int, int], str], list[str]]:
    # The licensed district suffix is never compared with the map layer's number.
    licensed = {(int(d.key[-6:-3]), d.name_en): d.key for d in districts}
    layer = {(r["KEY_NO"], r["ENAME"]): r for r in rows}
    pairs = {(r["KEY_NO"], r["DIST_NO"]) for r in rows}
    if (
        len(licensed) != len(districts)
        or len(layer) != len(rows)
        or len(pairs) != len(rows)
    ):
        raise FrameError("bnd_district_2020: district_pair_unique")
    if any(r["DIST_KEY"] != r["DIST_NO"] for r in rows):
        raise FrameError("bnd_district_2020: district_key_equality")
    if any((r["ZONENO"], r["DISTRICTNO"]) not in pairs for r in census):
        raise FrameError("census_district_pop: district_census_pair")
    alias_map = {}
    for alias_row in aliases:
        if set(alias_row) != {"zone_code", "layer_name", "hdx_name"}:
            raise FrameError("bnd_district_2020: district_alias fields")
        pair = (int(alias_row["zone_code"]), alias_row["layer_name"])
        target = (int(alias_row["zone_code"]), alias_row["hdx_name"])
        if pair in alias_map or pair not in layer or target not in licensed:
            raise FrameError("bnd_district_2020: district_alias missing or duplicate")
        alias_map[pair] = target
    result = {}
    used = set()
    report = []
    for pair, row in layer.items():
        target = alias_map.get(pair, pair)
        if target not in licensed:
            report.append(f"bnd_district_2020: district_name_pair_unmatched: {pair}")
        else:
            if target in used:
                raise FrameError("bnd_district_2020: district_alias many-to-one")
            used.add(target)
            result[(row["KEY_NO"], row["DIST_NO"])] = licensed[target]
    for pair in sorted(licensed.keys() - used):
        report.append(f"bnd_hdx: district_name_pair_unmatched: {pair}")
    return result, report


def check_census_zones(
    source: str, rows: list[dict[str, Any]], known: dict[str, str]
) -> None:
    seen = set()
    for row in rows:
        key = str(row["ZONE_NO"])
        if key in seen:
            raise FrameError(f"{source}: duplicate_zone")
        seen.add(key)
        if key not in known or row["MUNICIPAL_CODE"] != known[key]:
            raise FrameError(f"{source}: census_zone_key")
