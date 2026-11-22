"""Pinned inventory lineage and STAC completeness, with no transport."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

import shapely
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .fetch.bounded import file_hash
from .fetch.receipts import sha256_hex
from .fetch.registry import Entry
from .fetch.snapshots import Snapshot, SnapshotError, read_snapshot
from .heights.model import HeightError, unique_json
from .places.fetch import FILE_KEYS
from .places.read import SOURCE_RELEASE, geometry_bounds

BUILDING_PARTS = tuple(key for key in FILE_KEYS if key.startswith("bldg_ovt/"))
STAC_COLLECTION = "bldg_ovt/stac-collection"
BUILDING_METHOD = "national-buildings.v1"
BUILDING_MANIFEST = "manifest.buildings.json"
BUILDING_MANIFEST_RELATIVE = "assets/buildings/" + BUILDING_MANIFEST
FRAME_BOUNDS = (50.7, 24.4, 51.7, 26.2)
OUTSIDE_REVIEW = "custodian/publicdata/review/national_boundary_outside.json"
OUTSIDE_REVIEW_KEYS = frozenset(("version", "bnd_hdx_sha256", "outside_part_sha256"))


def bounds_polygon(bounds: tuple[float, float, float, float]) -> BaseGeometry:
    west, south, east, north = bounds
    return Polygon(
        ((west, south), (east, south), (east, north), (west, north), (west, south))
    )


class BuildingError(ValueError):
    """An inventory refusal, distinct from frame and places errors."""

    def __init__(self, name: str, detail: str = "") -> None:
        self.name, self.detail = name, detail
        super().__init__(name)


def part_hash(part: BaseGeometry) -> str:
    """SHA-256 of one boundary polygon's canonical two-dimensional WKB.

    The stub declares neither function; both exist in the pinned Shapely.
    """
    library = cast(Any, shapely)
    body = library.to_wkb(
        library.normalize(part), output_dimension=2, byte_order=1, include_srid=False
    )
    return sha256_hex(body)


def boundary_parts(
    boundary: BaseGeometry,
) -> tuple[tuple[BaseGeometry, ...], dict[str, BaseGeometry]]:
    """Split the union into parts inside the frame box and parts wholly outside it.

    A part that shares any point with the box without lying in it straddles and
    refuses, as does an empty, invalid or non-areal boundary or one with no
    inside part. Wholly-outside parts are keyed by `part_hash`.
    """
    if (
        boundary.is_empty
        or not boundary.is_valid
        or boundary.geom_type not in ("Polygon", "MultiPolygon")
    ):
        raise BuildingError("national_boundary_outside_frame_box", "boundary")
    frame = bounds_polygon(FRAME_BOUNDS)
    inside: list[BaseGeometry] = []
    outside: dict[str, BaseGeometry] = {}
    for part in getattr(boundary, "geoms", (boundary,)):
        if frame.covers(part):
            inside.append(part)
        elif not frame.intersects(part):
            outside[part_hash(part)] = part
        else:
            raise BuildingError("national_boundary_outside_frame_box", "straddling")
    if not inside:
        raise BuildingError("national_boundary_outside_frame_box", "no_inside_part")
    return tuple(inside), outside


def outside_review_document(
    boundary: BaseGeometry, bnd_sha256: str
) -> dict[str, object]:
    """The review file body the lead commits after reading the real boundary (L4)."""
    _inside, outside = boundary_parts(boundary)
    return {
        "version": 1,
        "bnd_hdx_sha256": bnd_sha256,
        "outside_part_sha256": sorted(outside),
    }


def outside_review(
    path: Path, outside: Mapping[str, BaseGeometry], bnd_sha256: str
) -> str | None:
    """Admit wholly-outside parts only when a review file lists exactly them.

    Returns the review file's SHA-256, or None when no file and no outside part.
    """
    if not path.exists():
        if outside:
            raise BuildingError("national_boundary_outside_frame_box", "unreviewed")
        return None
    try:
        body = path.read_bytes()
        document = unique_json(body, "national_boundary_review")
    except (OSError, HeightError):
        raise BuildingError("national_boundary_review") from None
    listed = document.get("outside_part_sha256") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or set(document) != OUTSIDE_REVIEW_KEYS
        or type(document["version"]) is not int
        or document["version"] != 1
        or not isinstance(document["bnd_hdx_sha256"], str)
        or not isinstance(listed, list)
        or not all(isinstance(item, str) for item in listed)
        or len(set(listed)) != len(listed)
    ):
        raise BuildingError("national_boundary_review")
    if document["bnd_hdx_sha256"] != bnd_sha256 or not set(listed) <= set(outside):
        raise BuildingError("national_boundary_review_stale")
    if set(outside) != set(listed):
        raise BuildingError("national_boundary_outside_frame_box", "unlisted")
    return sha256_hex(body)


def dump(value: object) -> bytes:
    """Canonical JSON, no clocks, nonfinite numbers or locale dependence."""
    return (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def invalidate_buildings(cache: Path) -> None:
    """Callers remove both outputs before attempting the shared frame step."""
    directory = cache.parent / "assets/buildings"
    for name in ("buildings.geojson", BUILDING_MANIFEST):
        (directory / name).unlink(missing_ok=True)


def pinned(
    cache: Path, entries: Sequence[Entry], selections: Mapping[str, str], key: str
) -> Snapshot:
    """Resolve exactly the caller's pin, never the cache's current selection."""
    rows = [entry for entry in entries if entry.key == key]
    if len(rows) != 1:
        raise BuildingError("building_part_unregistered", key)
    entry = rows[0]
    if entry.source_id != key.split("/", 1)[0] or entry.kind != "https_file":
        raise BuildingError("building_part_unregistered", key)
    if entry.skip_reason:
        raise BuildingError("building_part_skipped", key)
    if key not in selections:
        raise BuildingError("building_part_unpinned", key)
    try:
        snapshot = read_snapshot(cache / key, selections[key])
    except (SnapshotError, OSError):
        raise BuildingError("building_part_unreceipted", key) from None
    for field in ("key", "source_id", "publisher", "licence_id", "licence_basis"):
        if snapshot.sidecar.get(field) != getattr(entry, field):
            raise BuildingError("building_part_receipt_mismatch", key)
    if not entry.publisher or snapshot.sidecar.get("switched_off") is not False:
        raise BuildingError("building_part_receipt_mismatch", key)
    if not snapshot.sidecar.get("fetch_url"):
        raise BuildingError("building_part_receipt_mismatch", key)
    return snapshot


def fingerprint(snapshot: Snapshot, identity: str) -> dict[str, object]:
    """Complete public chain with an independently verified receipt hash."""
    fields = (
        "source_id",
        "key",
        "title_en",
        "publisher",
        "licence_id",
        "licence_basis",
        "licence_url",
        "retrieved_utc",
        "fetch_url",
        "landing_url",
        "terms_words",
        "terms_read_on",
    )
    return {
        **{field: snapshot.sidecar.get(field) for field in fields},
        "identity": identity,
        "sha256": snapshot.sha256,
        "receipt_sha256": file_hash(snapshot.receipt_path),
    }


def boundary_review(
    cache: Path, chain: Mapping[str, object], outside_count: int
) -> dict[str, object]:
    """A lead outcome is evidence only when it binds this chain and count."""
    result: dict[str, object] = {
        "outcome": "pending_lead_review" if outside_count else "no_in_box_outside_rows",
        "basis": "dated bnd_hdx; no reclaimed-land assumption",
    }
    path = cache / "review/building_boundary.json"
    if outside_count == 0 or not path.exists():
        return result
    try:
        body = path.read_bytes()
        document = unique_json(body, "building_boundary_review")
    except (OSError, HeightError):
        raise BuildingError("building_boundary_review") from None
    keys = {"version", "source_chain_sha256", "inside_box_outside_boundary", "outcome"}
    if (
        not isinstance(document, dict)
        or set(document) != keys
        or type(document["version"]) is not int
        or document["version"] != 1
        or type(document["inside_box_outside_boundary"]) is not int
        or document["inside_box_outside_boundary"] != outside_count
        or document["source_chain_sha256"] != sha256_hex(dump(chain))
        or document["outcome"]
        not in ("reviewed_no_land", "boundary_amendment_required")
    ):
        raise BuildingError("building_boundary_review")
    result.update(
        outcome=document["outcome"],
        review_path="review/building_boundary.json",
        review_sha256=sha256_hex(body),
    )
    return result


def metadata_keys(entries: Sequence[Entry]) -> tuple[str, ...]:
    return tuple(
        sorted(
            entry.key
            for entry in entries
            if entry.source_id == "bldg_ovt" and entry.key.startswith("bldg_ovt/stac-")
        )
    )


def _document(snapshot: Snapshot) -> dict[str, Any]:
    try:
        value = unique_json(snapshot.body, "building_stac")
    except (HeightError, SnapshotError, OSError):
        raise BuildingError("bldg_ovt_part_set_incomplete") from None
    if not isinstance(value, dict):
        raise BuildingError("bldg_ovt_part_set_incomplete")
    return value


def _bbox(value: object) -> tuple[float, float, float, float]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            isinstance(item, bool) or not isinstance(item, int | float | Decimal)
            for item in value
        )
    ):
        raise BuildingError("bldg_ovt_part_set_incomplete")
    try:
        numbers = tuple(float(item) for item in value)
    except (TypeError, ValueError, OverflowError):
        raise BuildingError("bldg_ovt_part_set_incomplete") from None
    if any(isinstance(item, bool) for item in value) or not all(
        math.isfinite(item) for item in numbers
    ):
        raise BuildingError("bldg_ovt_part_set_incomplete")
    west, south, east, north = numbers
    if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
        raise BuildingError("bldg_ovt_part_set_incomplete")
    return west, south, east, north


def national_guard(
    cache: Path,
    entries: Sequence[Entry],
    selections: Mapping[str, str],
    boundary: BaseGeometry,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Traverse all reviewed STAC item links; compare their assets to fixed parts.

    The required parts are the assets of the items whose bbox meets the bounds
    of the boundary parts inside the frame box; reviewed wholly-outside parts
    require none. Unregistered links, pagination, missing metadata and foreign
    part assets refuse. No bbox from prose or a filename substitutes for a STAC
    item. Returns the boundary scope for the manifest and the metadata chain.
    """
    inside, outside = boundary_parts(boundary)
    bounds = geometry_bounds(unary_union(inside))
    review = outside_review(
        cache.parent.parent / OUTSIDE_REVIEW,
        outside,
        pinned(cache, entries, selections, "bnd_hdx").sha256,
    )
    scope: dict[str, object] = {
        "in_box_bounds": list(bounds),
        "outside_parts": len(outside),
        "outside_part_sha256": sorted(outside),
        "outside_review_sha256": review,
    }
    rows = {entry.key: entry for entry in entries}
    metadata = set(metadata_keys(entries))
    urls = {
        entry.url: entry.key for entry in entries if entry.key in metadata and entry.url
    }
    pending = [STAC_COLLECTION]
    visited: set[str] = set()
    matching: set[str] = set()
    chain: dict[str, dict[str, object]] = {}
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        try:
            snapshot = pinned(cache, entries, selections, key)
        except BuildingError:
            raise BuildingError("bldg_ovt_part_set_incomplete") from None
        chain[key] = fingerprint(snapshot, selections[key])
        document = _document(snapshot)
        kind = document.get("type")
        if key == STAC_COLLECTION and kind != "Collection":
            raise BuildingError("bldg_ovt_part_set_incomplete")
        links = document.get("links", [])
        if not isinstance(links, list):
            raise BuildingError("bldg_ovt_part_set_incomplete")
        for link in links:
            if not isinstance(link, dict):
                raise BuildingError("bldg_ovt_part_set_incomplete")
            if link.get("rel") not in ("item", "child", "next"):
                continue
            href = link.get("href")
            if not isinstance(href, str):
                raise BuildingError("bldg_ovt_part_set_incomplete")
            linked = urls.get(urljoin(rows[key].url, href))
            if linked is None:
                raise BuildingError("bldg_ovt_part_set_incomplete")
            pending.append(linked)
        if kind == "Feature":
            item_bounds = _bbox(document.get("bbox"))
            if (
                bounds_polygon(item_bounds)
                .intersection(bounds_polygon(bounds))
                .is_empty
            ):
                continue
            assets = document.get("assets")
            if not isinstance(assets, dict):
                raise BuildingError("bldg_ovt_part_set_incomplete")
            hrefs = {
                urljoin(rows[key].url, asset["href"])
                for asset in assets.values()
                if isinstance(asset, dict) and isinstance(asset.get("href"), str)
            }
            found = {
                part
                for part in BUILDING_PARTS
                if part in rows and rows[part].url in hrefs
            }
            if len(found) != 1 or matching & found:
                raise BuildingError("bldg_ovt_part_set_incomplete")
            matching.update(found)
        elif kind not in ("Collection", "Catalog"):
            raise BuildingError("bldg_ovt_part_set_incomplete")
    if matching != set(BUILDING_PARTS) or visited != metadata:
        raise BuildingError("bldg_ovt_part_set_incomplete")
    return scope, chain


def verify_building_manifest(
    cache: Path, entries: Sequence[Entry], selections: Mapping[str, str], table: Path
) -> dict[str, object]:
    """Bind a completed table to this run's pins before heights reads its rows."""
    manifest = table.with_name(BUILDING_MANIFEST)
    try:
        block = unique_json(manifest.read_bytes(), "building_manifest")
    except (OSError, HeightError):
        raise HeightError("building_manifest_absent") from None
    if (
        not isinstance(block, dict)
        or block.get("method") != BUILDING_METHOD
        or block.get("source_release") != SOURCE_RELEASE
    ):
        raise HeightError("building_manifest_method")
    if block.get("output_sha256") != file_hash(table):
        raise HeightError("building_table_hash")
    if block.get("national_completeness") is not True:
        raise HeightError("building_manifest_coverage")
    chain = block.get("source_chain")
    keys = {*BUILDING_PARTS, "bnd_hdx", *metadata_keys(entries)}
    if not isinstance(chain, dict) or set(chain) != keys:
        raise HeightError("building_manifest_inputs")
    for key in sorted(keys):
        try:
            current = fingerprint(
                pinned(cache, entries, selections, key), selections[key]
            )
        except BuildingError:
            raise HeightError("building_manifest_inputs") from None
        if chain[key] != current:
            raise HeightError(
                "building_manifest_boundary"
                if key == "bnd_hdx"
                else "building_manifest_pins"
            )
    return {"path": BUILDING_MANIFEST_RELATIVE, "sha256": file_hash(manifest)}
