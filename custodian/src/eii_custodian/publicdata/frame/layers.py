"""Closed attribute schemas from L-202 section 2; map geometry is never used."""

from decimal import Decimal
from typing import Any

from .checks import FrameError
from .mapping import fields

COUNTS = {
    "census_zone_sector": (
        "Total_Economic_active___15",
        "Government",
        "Government_Establishment_Compan",
        "Mixed",
        "Private",
        "Diplomatic_Iinternational_Regio",
        "Non_Profit",
        "Household",
    ),
    "census_zone_occ": (
        "Pop_Aged__above__15",
        "Legislators_Senior_Officials_An",
        "Professionals",
        "Technicians_And_Associate_Profe",
        "Clerks",
        "Service_Workers_And_Shop_And_Ma",
        "Skilled_Agricultural_And_Fisher",
        "Craft_And_Related_Trades_Worker",
        "Plant_And_Machine_Operators_And",
        "Elementary_Occupations",
        "Other",
    ),
    "census_zone_hh": ("Qatari", "Non_Qatari"),
    "census_zone_lab": ("labor_gathering", "Small_gathering"),
    "census_district_pop": ("POP2020",),
}
NUMERIC = (int, float, Decimal)
COMMON = {"OBJECTID": (int,), "Shape__Area": NUMERIC, "Shape__Length": NUMERIC}
ZONE = {"ZONE_NO": (int,), "MUNICIPAL_CODE": (str,), **COMMON}
SCHEMAS: dict[str, dict[str, tuple[type, ...]]] = {
    **{
        source: {
            **ZONE,
            **(
                {"Muni_Name": (str,)}
                if source in {"census_zone_sector", "census_zone_occ"}
                else {}
            ),
            **dict.fromkeys(names, (int, type(None))),
        }
        for source, names in COUNTS.items()
        if source != "census_district_pop"
    },
    "census_district_pop": {
        **COMMON,
        "ZONENO": (int,),
        "DISTRICTNO": (int,),
        "POP2020": (int, type(None)),
    },
    "bnd_zone_2020": {
        **ZONE,
        "Municipality_En": (str,),
        "Municipality_Ar": (str,),
        "Mun_code2": (type(None),),
    },
    "bnd_district_2020": {
        **COMMON,
        "DIST_NO": (int,),
        "DIST_KEY": (int,),
        "KEY_NO": (int,),
        "ENAME": (str,),
        "ANAME": (str,),
        "Area_SQKM": NUMERIC,
        "Density_pop": (*NUMERIC, type(None)),
        "GLOBALID": (str,),
        "Field": (type(None),),
    },
}


def layer_rows(source: str, payload: Any) -> list[dict[str, Any]]:
    fields(payload, {"count": int, "features": list}, source)
    rows = []
    for feature in payload["features"]:
        fields(feature, {"attributes": dict, "geometry": dict}, source)
        fields(feature["geometry"], {"rings": list}, source)
        attrs = feature["attributes"]
        schema = SCHEMAS[source]
        missing, extra = schema.keys() - attrs.keys(), attrs.keys() - schema.keys()
        if missing or extra:
            raise FrameError(
                f"{source}: missing fields {sorted(missing)}; unknown fields {sorted(extra)}"
            )
        for name, kinds in schema.items():
            if type(attrs[name]) not in kinds:
                raise FrameError(f"{source}: field {name} type")
        rows.append(attrs)
    if payload["count"] != len(rows):
        raise FrameError(f"{source}: count mismatch")
    return rows
