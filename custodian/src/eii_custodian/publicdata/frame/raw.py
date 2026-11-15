"""Licensed ZIP shape confirmed by the lead's structure-only note, L-202 R1.

Only the three named members are read; no archive member is extracted to disk.
"""

import io
import json
import re
import zipfile
from typing import Any

from shapely.geometry import shape

from .checks import FrameError
from .geometry import Boundary, index

CRS = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
LEVELS = {1: "municipality", 2: "zone", 3: "district"}
COMMON = {
    "valid_on",
    "valid_to",
    "area_sqkm",
    "version",
    "lang",
    "lang1",
    "lang2",
    "lang3",
    "center_lat",
    "center_lon",
}


def properties_at(level: int) -> set[str]:
    return COMMON | {
        f"adm{n}_{field}"
        for n in range(level + 1)
        for field in ("name", "name1", "name2", "name3", "pcode")
    }


def read_archive(body: bytes) -> dict[str, list[Boundary]]:
    result = {}
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            for level, kind in LEVELS.items():
                member = f"qat_admin{level}.geojson"
                if archive.namelist().count(member) != 1:
                    raise FrameError(f"bnd_hdx: missing member or duplicate {member}")
                result[kind] = parse_level(json.loads(archive.read(member)), level)
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeError) as exc:
        raise FrameError("bnd_hdx: unreadable archive member") from exc
    return result


def parse_level(document: Any, level: int) -> list[Boundary]:
    if not isinstance(document, dict) or set(document) != {
        "type",
        "name",
        "crs",
        "features",
    }:
        raise FrameError("bnd_hdx: collection fields")
    if document["crs"] != CRS:
        raise FrameError("bnd_hdx: coordinate system")
    if document["type"] != "FeatureCollection" or not isinstance(
        document["features"], list
    ):
        raise FrameError("bnd_hdx: FeatureCollection required")
    result = []
    for feature in document["features"]:
        if (
            not isinstance(feature, dict)
            or set(feature) != {"type", "properties", "geometry"}
            or feature["type"] != "Feature"
        ):
            raise FrameError("bnd_hdx: feature fields")
        p = feature["properties"]
        if not isinstance(p, dict) or set(p) != properties_at(level):
            raise FrameError("bnd_hdx: unknown or missing properties")
        for n in range(level + 1):
            for field in ("name", "name1", "pcode"):
                value = p[f"adm{n}_{field}"]
                if not isinstance(value, str) or not value:
                    raise FrameError(f"bnd_hdx: property adm{n}_{field}")
            for field in ("name2", "name3"):
                if p[f"adm{n}_{field}"] is not None:
                    raise FrameError(f"bnd_hdx: property adm{n}_{field}")
        for field in ("valid_to", "lang2", "lang3"):
            if p[field] is not None:
                raise FrameError(f"bnd_hdx: property {field}")
        for field in ("area_sqkm", "center_lat", "center_lon"):
            if type(p[field]) not in {int, float}:
                raise FrameError(f"bnd_hdx: property {field}")
        for field in ("valid_on", "version"):
            if not isinstance(p[field], str) or not p[field]:
                raise FrameError(f"bnd_hdx: property {field}")
        if p["lang"] != "en" or p["lang1"] != "ar":
            raise FrameError("bnd_hdx: property language")
        for n in range(1, level + 1):
            code = p[f"adm{n}_pcode"]
            if re.fullmatch(r"[A-Z]{3}" + rf"[0-9]{{{n * 3}}}", code) is None:
                raise FrameError("bnd_hdx: administrative code")
            if n > 1 and not code.startswith(p[f"adm{n - 1}_pcode"]):
                raise FrameError("bnd_hdx: parent code")
        key = p[f"adm{level}_pcode"]
        if level >= 2:
            zone = int(p["adm2_pcode"][-3:])
            suffix = re.search(r"([0-9]+)$", p["adm2_name"])
            if suffix is None or int(suffix.group(1)) != zone:
                raise FrameError("bnd_hdx: zone name/code disagreement")
            if level == 2:
                key = str(zone)
        geometry = feature["geometry"]
        if not isinstance(geometry, dict) or geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise FrameError("bnd_hdx: geometry type")
        polygon = shape(geometry)
        if polygon.is_empty or not polygon.is_valid:
            raise FrameError("bnd_hdx: invalid polygon")
        result.append(
            Boundary(
                key,
                p[f"adm{level}_name"],
                p[f"adm{level}_name1"],
                p["adm1_pcode"],
                polygon,
            )
        )
    index(result)
    return result
