"""Validated tiles enter the existing immutable archive; no analytical output."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from importlib import import_module
from pathlib import Path

from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.cdse.contracts import (
    Metadata,
    PageEvidence,
    request_sha256,
    validate_metadata,
)
from eii_custodian.publicdata.cdse.transport import HASH, CdseError
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot, utc

SOURCE = "satellite_cdse_backup"
TILE_ID = re.compile(r"tile--?[0-9]+--?[0-9]+")


def cache_root(root: Path) -> None:
    """Confine all writes to an explicit public cache, including existing children."""
    if root.parts[-2:] != ("data", "public_cache") or ".." in root.parts:
        raise CdseError("cache_path_refused")
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise CdseError("cache_symlink_refused")
    source = root / SOURCE
    if source.is_symlink() or (
        source.exists() and any(p.is_symlink() for p in source.rglob("*"))
    ):
        raise CdseError("cache_symlink_refused")


def tile_metadata(meta: Metadata) -> dict[str, object]:
    """Canonical JSON-compatible metadata; its digest binds contribution dates."""
    value: dict[str, object] = json.loads(json.dumps(asdict(meta), default=str))
    return value


def validate_raster(body: bytes, meta: Metadata) -> None:
    """Decode the complete RGBA raster, georeference and transparent gap mask."""
    memory_file = import_module("rasterio.io").MemoryFile
    from_origin = import_module("rasterio.transform").from_origin
    try:
        with memory_file(body) as memory, memory.open() as raster:
            tile = meta.tile
            if (
                raster.driver != "GTiff"
                or raster.width != tile.width
                or raster.height != tile.height
                or raster.count != 4
                or raster.dtypes != ("uint8",) * 4
                or str(raster.crs) != tile.crs
                or raster.transform
                != from_origin(
                    tile.bounds[0], tile.bounds[3], tile.resolution_m, tile.resolution_m
                )
            ):
                raise CdseError("raster_dimensions_or_schema_refused")
            values = raster.read()
            alpha = values[3]
            if not ((alpha == 0) | (alpha == 255)).all():
                raise CdseError("raster_mask_refused")
            if not (alpha == 255).any():
                raise CdseError("raster_no_valid_pixels")
            if meta.coverage == "complete_valid_pixels" and (alpha == 0).any():
                raise CdseError("coverage_unsupported")
    except CdseError:
        raise
    except Exception:
        raise CdseError("raster_invalid") from None


def promote(
    root: Path,
    entry: Entry,
    body: bytes,
    meta: Metadata,
    boundary: BaseGeometry,
    publisher: PageEvidence,
    retrieved: str,
    expected_sha256: str,
) -> dict[str, object]:
    """Validate first, then reuse sidecar_for/commit_pair and S2-T27 snapshots."""
    cache_root(root)
    validate_metadata(meta, boundary)
    publisher.validate()
    utc(retrieved)
    if (
        entry.source_id != SOURCE
        or entry.key != SOURCE
        or entry.kind != "cdse_backup"
        or not entry.publisher
        or entry.publisher != publisher.words
        or entry.commit_allowed
        or entry.release_tables
        or entry.nightly_live_fetch
        or entry.licence_basis != "provider_terms"
        or entry.decision_record
        or entry.skip_reason
        or HASH.fullmatch(expected_sha256) is None
        or sha256_hex(body) != expected_sha256
    ):
        raise CdseError("tile_provenance_refused")
    # Live URL is never accepted without the reviewed endpoint admission.
    from eii_custodian.publicdata.cdse.transport import REVIEWED_ENDPOINTS
    from eii_custodian.publicdata.fetch.allowlist import approve, host_of

    if (
        not approve(entry.url).ok
        or REVIEWED_ENDPOINTS.get("process") != entry.url
        or host_of(entry.url) != entry.fetch_host
    ):
        raise CdseError("provider_contract_pending")
    validate_raster(body, meta)
    side = sidecar_for(
        entry,
        digest=expected_sha256,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc=retrieved,
        publisher=entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    tile = tile_metadata(meta)
    side.update(
        tile=tile,
        request_sha256=request_sha256(meta),
        metadata_sha256=sha256_hex(
            json.dumps(tile, sort_keys=True, separators=(",", ":")).encode()
        ),
        boundary_sha256=sha256_hex(boundary.wkb),
        terms_records={
            name: {
                "status": "pending",
                "reason": "official_page_reading_pending",
                "checked_on": entry.terms_read_on,
            }
            for name in ("imagery_notice", "interface_terms", "complete_attribution")
        },
        publisher_evidence=asdict(publisher),
        cache_role="unread_backup_only",
    )
    directory = root / SOURCE / meta.tile.tile_id
    if (directory / "index" / f"{expected_sha256}.json").exists():
        previous = read_snapshot(directory, expected_sha256)
        for key in (
            "tile",
            "request_sha256",
            "metadata_sha256",
            "boundary_sha256",
            "publisher",
            "publisher_evidence",
            "cache_role",
        ):
            if previous.sidecar.get(key) != side.get(key):
                raise CdseError("immutable_tile_receipt_conflict")
    commit_pair(directory, expected_sha256, "tif", body, side)
    return side


def parents(
    root: Path, members: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    """Resolve explicit immutable parents for a later cache-only derived mosaic.

    No mosaic renderer or product/release path is provided by this task.
    """
    cache_root(root)
    if not members or len({tile for tile, _digest in members}) != len(members):
        raise CdseError("mosaic_membership_refused")
    for tile, digest in members:
        if TILE_ID.fullmatch(tile) is None or HASH.fullmatch(digest) is None:
            raise CdseError("mosaic_parent_refused")
        snap = read_snapshot(root / SOURCE / tile, digest)
        if (
            snap.sidecar.get("source_id") != SOURCE
            or snap.sidecar.get("cache_role") != "unread_backup_only"
        ):
            raise CdseError("mosaic_parent_refused")
    return members
