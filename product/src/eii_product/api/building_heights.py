"""Fixed read of the S2-T20 heights asset for the 3D buildings of S3-T16.

The heights are a step of the map-asset pipeline, not a release table
(document 03). They are read only from released immutable files pinned by the
SHA-256 of ``manifest.heights.json`` (C47, MTH-125). ``heights.json`` and the
footprint table are accepted only when their bytes match the hashes the
manifest records, and the building inventory's own manifest only when it
matches the hash the building table's record carries. Each fallback's error
statistic leaves as a Fact whose lineage names the manifest's method and every
public file behind it: each fetched height file, each input of the building
inventory and each landmark citation, with its publisher, address, licence,
retrieval date and hash. The read is whole or refused with one closed reason;
no value is repaired or defaulted.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from eii_core.calc.building_heights import FALLBACKS, HEIGHT_SOURCES, NO_PAIRS
from eii_core.facts import Fact, fact_id
from eii_product.api.results import wire_fact

MANIFEST_SUFFIX = ".json"
HEIGHTS_FILE = "heights.json"
BUILDINGS_FILE = "buildings.geojson"
BUILDING_MANIFEST_FILE = "manifest.buildings.json"
BUILDING_MANIFEST_PATH = "assets/buildings/" + BUILDING_MANIFEST_FILE
# The released folder's artefact path inside a checked release.
RELEASE_FOLDER = "artefacts/heights/"
RELEASE_FILES = frozenset({HEIGHTS_FILE, BUILDINGS_FILE, BUILDING_MANIFEST_FILE})
# The producer's closed error-block fields (S2-T20 ``_error_block``).
ERROR_FIELDS = frozenset(
    {
        "count",
        "mean_absolute_error_m",
        "mean_signed_error_m",
        "median_absolute_error_m",
        "reason",
    }
)
# A count beyond this is not exactly a JSON number of the browser.
_COUNT_MAX = 2**53
HEIGHTS_TABLE = "asset_heights"
LINEAGE_REF = "lin_" + HEIGHTS_TABLE
GEOGRAPHY = {"kind": "national"}
# Slot, metric key, unit and the manifest's error-block field.
STATISTICS = (
    ("pairs", "building_height_pairs", "count", "count"),
    (
        "mean_signed",
        "building_height_mean_signed_error",
        "metres",
        "mean_signed_error_m",
    ),
    ("mean_abs", "building_height_mean_abs_error", "metres", "mean_absolute_error_m"),
    (
        "median_abs",
        "building_height_median_abs_error",
        "metres",
        "median_absolute_error_m",
    ),
)
LABELS = {
    "building_height_pairs": (
        "Buildings with both heights",
        "المباني التي لها الارتفاعان",
    ),
    "building_height_mean_signed_error": ("Mean signed error", "متوسط الخطأ بإشارته"),
    "building_height_mean_abs_error": ("Mean absolute error", "متوسط الخطأ المطلق"),
    "building_height_median_abs_error": (
        "Median absolute error",
        "وسيط الخطأ المطلق",
    ),
}
_HASH = re.compile(r"[0-9a-f]{64}")
_HEIGHT = re.compile(r"[0-9]+(\.[0-9]{1,2})?")
_ERROR = re.compile(r"-?[0-9]+(\.[0-9]{1,2})?")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class HeightsRefusal(ValueError):
    """A closed refusal of the heights read; the message is the reason."""


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _json(body: bytes, reason: str) -> Any:
    try:
        return json.loads(body, parse_float=Decimal, parse_constant=_no_constant)
    except (ValueError, UnicodeDecodeError):
        raise HeightsRefusal(reason) from None


def _no_constant(_name: str) -> None:
    raise ValueError("constant")


def _file_hash(manifest: dict[str, Any], key: str, role: str) -> str:
    """The one hash the manifest records for a named file of a named role."""
    files = manifest.get("files", [])
    if not isinstance(files, list):
        raise HeightsRefusal("heights_manifest_shape")
    found = [
        record
        for record in files
        if isinstance(record, dict) and record.get("key") == key
    ]
    if len(found) != 1 or found[0].get("role") != role:
        raise HeightsRefusal("heights_manifest_shape")
    digest = found[0].get("sha256")
    if not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
        raise HeightsRefusal("heights_manifest_shape")
    return digest


def _text(record: dict[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise HeightsRefusal("heights_lineage")
    return value


def _lineage_row(
    key: str, publisher: str, url: str, licence: str, retrieved: str, digest: str
) -> dict[str, str]:
    """One Public source row from fields ``_text`` required; none defaulted."""
    if _HASH.fullmatch(digest) is None or _DATE.fullmatch(retrieved[:10]) is None:
        raise HeightsRefusal("heights_lineage")
    return {
        "sourceId": key,
        "kind": "public_dataset",
        "inputClass": "public",
        "publisher": publisher,
        "datasetOrPage": url,
        "licenceOrTerms": licence,
        "retrievalDate": retrieved[:10],
        "sha256": digest,
    }


def _source_row(record: dict[str, Any]) -> dict[str, str]:
    """A fetched height file of the manifest (S2-T20 ``_file_record``)."""
    names = ("key", "publisher", "url", "licence_id", "retrieved_utc", "sha256")
    return _lineage_row(*(_text(record, name) for name in names))


def _inventory_row(link: Any) -> dict[str, str]:
    """One input of the building inventory (S2 ``fingerprint``)."""
    if not isinstance(link, dict):
        raise HeightsRefusal("heights_lineage")
    names = ("key", "publisher", "fetch_url", "licence_id", "retrieved_utc", "sha256")
    return _lineage_row(*(_text(link, name) for name in names))


def _landmark_row(entry: Any) -> dict[str, str]:
    """One landmark height's public citation (S2-T20 ``apply_landmark_heights``)."""
    citation = entry.get("citation") if isinstance(entry, dict) else None
    if not isinstance(citation, dict):
        raise HeightsRefusal("heights_lineage")
    names = ("publisher", "page_url", "licence_basis", "retrieved_on", "page_sha256")
    return _lineage_row(
        "landmark_heights/" + _text(entry, "landmark_id"),
        *(_text(citation, name) for name in names),
    )


def _read_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The manifest's read records by key; a repeated key refuses."""
    files = manifest.get("files", [])
    records: dict[str, dict[str, Any]] = {}
    for record in files:
        if not isinstance(record, dict):
            raise HeightsRefusal("heights_manifest_shape")
        if record.get("role") != "read":
            continue
        key = _text(record, "key")
        if key in records:
            raise HeightsRefusal("heights_lineage")
        records[key] = record
    return records


def _building_link(manifest: dict[str, Any]) -> str:
    """The hash of the inventory manifest the building table's record points at."""
    chain = _read_records(manifest).get("building_table", {}).get("source_chain")
    if (
        not isinstance(chain, dict)
        or set(chain) != {"path", "sha256"}
        or chain["path"] != BUILDING_MANIFEST_PATH
        or not isinstance(chain["sha256"], str)
        or _HASH.fullmatch(chain["sha256"]) is None
    ):
        raise HeightsRefusal("heights_lineage")
    return chain["sha256"]


def _sources(
    manifest: dict[str, Any], inventory: Any, table_sha256: str
) -> list[dict[str, str]]:
    """Every public source behind the asset: height files, inventory, landmarks.

    The two internal records (``building_table``, ``landmark_heights``) carry no
    address; they are replaced by the chains they stand for. Any other read
    record is a fetched file and needs every field of a source.
    """
    records = _read_records(manifest)
    if "building_table" not in records or "landmark_heights" not in records:
        raise HeightsRefusal("heights_lineage")
    rows = [
        _source_row(record)
        for key, record in records.items()
        if key not in ("building_table", "landmark_heights")
    ]
    if (
        not isinstance(inventory, dict)
        or inventory.get("output_sha256") != table_sha256
        or not isinstance(inventory.get("source_chain"), dict)
        or not inventory["source_chain"]
    ):
        raise HeightsRefusal("heights_lineage")
    rows += [_inventory_row(link) for link in inventory["source_chain"].values()]
    landmarks = manifest.get("landmark_heights")
    if not isinstance(landmarks, list):
        raise HeightsRefusal("heights_lineage")
    rows += [_landmark_row(entry) for entry in landmarks]
    if len({row["sourceId"] for row in rows}) != len(rows):
        raise HeightsRefusal("heights_lineage")
    return sorted(rows, key=lambda row: row["sourceId"])


def _footprints(collection: Any) -> dict[str, list[list[float]]]:
    """Outer rings by building id; any other geometry refuses the read."""
    features = collection.get("features") if isinstance(collection, dict) else None
    if not isinstance(features, list):
        raise HeightsRefusal("heights_geometry")
    rings: dict[str, list[list[float]]] = {}
    for feature in features:
        try:
            key = feature["properties"]["building_id"]
            geometry = feature["geometry"]
            ring = geometry["coordinates"][0]
            if geometry["type"] != "Polygon" or not isinstance(key, str):
                raise TypeError
            points = [_point(point) for point in ring]
        except (KeyError, TypeError, ValueError, IndexError, OverflowError):
            raise HeightsRefusal("heights_geometry") from None
        if key in rings or len(points) < 3:
            raise HeightsRefusal("heights_geometry")
        rings[key] = points
    return rings


def _coordinate(value: object, limit: int) -> float:
    """Degrees within ±limit, judged on the original number before float.

    ``limit`` is 180 degrees of longitude or 90 degrees of latitude.
    """
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise TypeError
    degrees = Decimal(value)
    if not -Decimal(limit) <= degrees <= Decimal(limit):
        raise ValueError
    return float(degrees)


def _point(point: object) -> list[float]:
    if not isinstance(point, list) or len(point) != 2:
        raise TypeError
    return [_coordinate(point[0], 180), _coordinate(point[1], 90)]


def _usable_height(height: object) -> bool:
    """Decimal text of metres that the renderer holds as a positive finite number."""
    return (
        isinstance(height, str)
        and _HEIGHT.fullmatch(height) is not None
        and Decimal(height) > 0
        and math.isfinite(float(height))
    )


def _building(row: Any, rings: dict[str, list[list[float]]]) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise HeightsRefusal("heights_row")
    key, height, source = (
        row.get(n) for n in ("building_id", "height_m", "height_source")
    )
    if source not in HEIGHT_SOURCES or not isinstance(key, str):
        raise HeightsRefusal("heights_row")
    if (source == "none") != (height is None) or (
        height is not None and not _usable_height(height)
    ):
        raise HeightsRefusal("heights_row")
    if key not in rings:
        raise HeightsRefusal("heights_join")
    return {
        "building_key": key,
        "footprint": rings[key],
        "height_m": height,
        "height_source": source,
    }


def _buildings(rows: Any, rings: dict[str, list[list[float]]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise HeightsRefusal("heights_row")
    buildings = [_building(row, rings) for row in rows]
    keys = [item["building_key"] for item in buildings]
    if len(set(keys)) != len(keys) or set(keys) != set(rings):
        raise HeightsRefusal("heights_join")
    return buildings


def _statistic(block: dict[str, Any], field: str) -> Decimal | int:
    """A count of at least one, or decimal metres the browser holds exactly."""
    value = block.get(field)
    if field == "count":
        if type(value) is not int or not 1 <= value <= _COUNT_MAX:
            raise HeightsRefusal("heights_error_block")
        return value
    if not isinstance(value, str) or _ERROR.fullmatch(value) is None:
        raise HeightsRefusal("heights_error_block")
    number = Decimal(value)
    if Decimal(str(float(number))) != number:
        raise HeightsRefusal("heights_error_block")
    return number


def _no_pairs(item: dict[str, Any]) -> bool:
    """The producer's no-pairs variant exactly: integer zero, null statistics."""
    if item.get("reason") != NO_PAIRS:
        return False
    if type(item.get("count")) is not int or item["count"] != 0:
        raise HeightsRefusal("heights_error_block")
    if any(item[field] is not None for field in ERROR_FIELDS - {"count", "reason"}):
        raise HeightsRefusal("heights_error_block")
    return True


class ReleasedBuildingHeights:
    """The heights asset of one released folder, pinned by its manifest hash."""

    def __init__(self, directory: Path, manifest_sha256: str) -> None:
        if _HASH.fullmatch(manifest_sha256) is None:
            raise HeightsRefusal("heights_manifest_integrity")
        self.release_id = manifest_sha256
        body = self._bytes(
            manifest_sha256 + MANIFEST_SUFFIX, directory, "heights_manifest_integrity"
        )
        if _sha(body) != manifest_sha256:
            raise HeightsRefusal("heights_manifest_integrity")
        manifest = _json(body, "heights_manifest_shape")
        if (
            not isinstance(manifest, dict)
            or manifest.get("card") != "C47"
            or manifest.get("method") != "MTH-125"
            or not isinstance(manifest.get("errors"), dict)
        ):
            raise HeightsRefusal("heights_manifest_shape")
        rows = self._verified(directory, HEIGHTS_FILE, manifest, "heights", "written")
        table_body = self._checked(
            directory, BUILDINGS_FILE, _file_hash(manifest, "building_table", "read")
        )
        table = _json(table_body, "heights_file_integrity")
        inventory = _json(
            self._checked(directory, BUILDING_MANIFEST_FILE, _building_link(manifest)),
            "heights_lineage",
        )
        self.sources = _sources(manifest, inventory, _sha(table_body))
        self.period = max(row["retrievalDate"] for row in self.sources)
        self.buildings = _buildings(rows, _footprints(table))
        self.errors, self.facts = self._errors(manifest["errors"])

    @staticmethod
    def _bytes(
        name: str, directory: Path, reason: str = "heights_file_integrity"
    ) -> bytes:
        candidate = directory / name
        if (
            directory.resolve() != directory
            or candidate.resolve() != candidate
            or not candidate.is_relative_to(directory)
        ):
            raise HeightsRefusal("heights_path_integrity")
        try:
            return candidate.read_bytes()
        except OSError:
            raise HeightsRefusal(reason) from None

    def _checked(self, directory: Path, name: str, digest: str) -> bytes:
        body = self._bytes(name, directory)
        if _sha(body) != digest:
            raise HeightsRefusal("heights_file_integrity")
        return body

    def _verified(
        self, directory: Path, name: str, manifest: dict[str, Any], key: str, role: str
    ) -> Any:
        body = self._checked(directory, name, _file_hash(manifest, key, role))
        return _json(body, "heights_file_integrity")

    def _fact(self, source: str, metric: str, unit: str, value: Decimal | int) -> Fact:
        label_en, label_ar = LABELS[metric]
        return Fact(
            fact_id=fact_id(
                release_id=self.release_id,
                metric_key=metric,
                geography=GEOGRAPHY,
                period=self.period,
                qualifiers={"height_source": source},
            ),
            value=value,
            unit=unit,
            period=self.period,
            geography=dict(GEOGRAPHY),
            provenance="public",
            input_classes=["public"],
            evidence_status="inferred",
            reliability="not_applicable",
            coverage_keys=[],
            caveat_keys=["heights_are_estimates"],
            label_en=label_en,
            label_ar=label_ar,
            lineage_ref=LINEAGE_REF,
            release_id=self.release_id,
        )

    def _errors(
        self, block: dict[str, Any]
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        """One closed entry per fallback: its four fact ids, or no pairs."""
        if set(block) != set(FALLBACKS):
            raise HeightsRefusal("heights_error_block")
        entries: list[dict[str, str]] = []
        facts: list[dict[str, Any]] = []
        for source in FALLBACKS:
            item = block[source]
            if not isinstance(item, dict) or set(item) != ERROR_FIELDS:
                raise HeightsRefusal("heights_error_block")
            if _no_pairs(item):
                entries.append({"source": source, "reason": NO_PAIRS})
                continue
            if item.get("reason") != "":
                raise HeightsRefusal("heights_error_block")
            entry = {"source": source}
            for slot, metric, unit, field in STATISTICS:
                fact = self._fact(source, metric, unit, _statistic(item, field))
                entry[slot + "_fact_id"] = fact.fact_id
                facts.append(
                    {
                        "fact": wire_fact(fact),
                        "binding": {
                            "metricKey": metric,
                            "qualifiers": {"height_source": source},
                        },
                    }
                )
            entries.append(entry)
        return entries, facts

    def read(self) -> dict[str, Any]:
        """The fixed read: buildings, fallback errors, facts and their chain."""
        return {
            "release_id": self.release_id,
            "buildings": self.buildings,
            "fallback_errors": self.errors,
            "facts": self.facts,
            "lineage": {
                "lineageId": LINEAGE_REF,
                "releaseId": self.release_id,
                "tableName": HEIGHTS_TABLE,
                "method": "MTH-125",
                "methodVersion": "C47",
                "sourceIds": [row["sourceId"] for row in self.sources],
                "inputClasses": ["public"],
            },
            "sources": self.sources,
        }


def heights_from_release(
    folder: Path, artefacts: object
) -> ReleasedBuildingHeights | None:
    """The heights a checked release carries, pinned by its own manifest entry.

    ``artefacts`` is the checked release manifest's list, whose bytes the
    release id covers and whose file hashes startup verified. No entry under
    ``artefacts/heights/`` means no heights. Otherwise the entries are exactly
    the three released files and one ``<sha256>.json`` whose recorded hash is
    its own name; that hash is the trusted pin of the read.
    """
    if not isinstance(artefacts, list):
        raise HeightsRefusal("heights_release_artefacts")
    entries = [
        item
        for item in artefacts
        if isinstance(item, dict) and str(item.get("path")).startswith(RELEASE_FOLDER)
    ]
    if not entries:
        return None
    named = {
        str(item["path"])[len(RELEASE_FOLDER) :]: item.get("sha256") for item in entries
    }
    pins = [
        name.removesuffix(MANIFEST_SUFFIX)
        for name, digest in named.items()
        if name not in RELEASE_FILES and name == f"{digest}{MANIFEST_SUFFIX}"
    ]
    if (
        len(named) != len(entries)
        or len(pins) != 1
        or set(named) != RELEASE_FILES | {pins[0] + MANIFEST_SUFFIX}
    ):
        raise HeightsRefusal("heights_release_artefacts")
    return ReleasedBuildingHeights((folder / RELEASE_FOLDER).resolve(), pins[0])


def building_heights_router(heights: ReleasedBuildingHeights | None) -> APIRouter:
    """Serve ``GET /api/building-heights``; it takes no argument."""
    router = APIRouter()

    @router.get("/api/building-heights")
    def get_heights(request: Request) -> JSONResponse:
        if request.query_params:
            return JSONResponse(
                status_code=422, content={"error": {"code": "INVALID_ARGUMENT"}}
            )
        if heights is None:
            return JSONResponse(
                status_code=404,
                content={"status": "NO_DATA", "reason": "heights_absent"},
            )
        return JSONResponse(content=heights.read())

    return router


__all__ = [
    "HEIGHTS_TABLE",
    "RELEASE_FOLDER",
    "HeightsRefusal",
    "ReleasedBuildingHeights",
    "building_heights_router",
    "heights_from_release",
]
