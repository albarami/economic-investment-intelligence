"""Invented metric boundary, RGBA rasters, budgets and receipt attack plants."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box

from eii_custodian.publicdata.cdse import cache as c
from eii_custodian.publicdata.cdse import contracts as k
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot


@pytest.fixture(autouse=True)
def offline():
    with (
        patch("socket.socket", side_effect=AssertionError("network")),
        patch(
            "eii_custodian.publicdata.fetch.allowlist.ALLOWED_HOSTS",
            frozenset({"cdse.invalid"}),
        ),
        patch(
            "eii_custodian.publicdata.cdse.transport.REVIEWED_ENDPOINTS",
            {"process": "https://cdse.invalid/process"},
        ),
    ):
        yield


def tile():
    return k.tiles_for(box(500000, 2700000, 500020, 2700020), "EPSG:32639")[0]


def raster(t, *, width=None):
    width = t.width if width is None else width
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=width,
            height=t.height,
            count=4,
            dtype="uint8",
            crs=t.crs,
            transform=from_origin(t.bounds[0], t.bounds[3], 10, 10),
        ) as ds:
            values = np.ones((4, t.height, width), dtype=np.uint8)
            values[3] *= 255
            values[3, 0, 0] = 0  # Honest transparent gap, never a cloud-free claim.
            ds.write(values)
        return memory.read()


def metadata(t):
    return k.Metadata(
        t,
        "2026-10-19T00:00:00Z",
        "2026-11-19T00:00:00Z",
        ("2026-11-01T12:00:00Z",),
        "least_cloudy",
        "cloud_and_nodata_transparent",
        "partial",
        "sentinel-2-l2a",
        ("B04", "B03", "B02"),
        Decimal("2.5"),
        "cdse-cache.v1",
    )


def entry():
    base = next(e for e in load_registry() if e.source_id == "satellite_cdse_backup")
    return replace(
        base,
        publisher="Invented fixture publisher",
        fetch_host="cdse.invalid",
        url="https://cdse.invalid/process",
        skip_reason="",
    )


def proof():
    return k.PageEvidence(
        "https://cdse.invalid/document",
        "2026-11-19",
        "a" * 64,
        "Invented fixture publisher",
    )


def test_tiling_and_metadata_plants():
    ts = k.tiles_for(box(0, 0, 22010, 22010), "EPSG:32639")
    assert len(ts) == 4
    assert [t.width for t in ts] == [2200, 2200, 1, 1]
    for t in ts:
        assert t.width <= 2500 and t.height <= 2500
    valid = metadata(tile())
    k.validate_metadata(valid, box(500000, 2700000, 500020, 2700020))
    for changed in (
        replace(valid, start=valid.end),
        replace(valid, start="2026-10-19"),
        replace(valid, dates=()),
        replace(valid, dates=("2026-12-01T00:00:00Z",)),
        replace(valid, bands=("B08",)),
        replace(valid, collection="other"),
        replace(valid, coverage="cloud_free"),
        replace(valid, ordering="newest"),
        replace(valid, mask="none"),
        replace(valid, factor=Decimal(3)),
        replace(valid, tile=replace(valid.tile, width=2501)),
        replace(valid, tile=replace(valid.tile, width=1)),
        replace(valid, tile=replace(valid.tile, bounds=(0, 0, 20, 20))),
    ):
        with pytest.raises(ValueError):
            k.validate_metadata(changed, box(500000, 2700000, 500020, 2700020))
    with pytest.raises(ValueError):
        k.tiles_for(box(0, 0, 2, 2), "EPSG:4326")


def test_quota_unknown_insufficient_rounding_and_enumeration():
    model = k.CostModel(
        Decimal(100),
        Decimal("0.1"),
        Decimal("0.5"),
        Decimal("0.1"),
        Decimal("0.2"),
        Decimal("0.3"),
        proof(),
    )
    assert model.picture_cost(101, bands=3, samples=1) == Decimal("0.5")
    assert model.picture_cost(1000, bands=3, samples=1) == Decimal(3)
    plan = k.bulk_budget(
        (tile(),),
        model,
        Decimal(10),
        10,
        metadata=1,
        refresh=1,
        retries=1,
        reserve_note="Invented lead choice",
    )
    assert plan.requests == 5
    assert plan.pixels == 4
    assert plan.kinds == ("token", "metadata", "process", "token", "process")
    for cost, units, requests in (
        (None, Decimal(10), 10),
        (model, None, 10),
        (model, Decimal("0.1"), 10),
        (model, Decimal(10), 4),
    ):
        with pytest.raises(ValueError):
            k.bulk_budget(
                (tile(),),
                cost,
                units,
                requests,
                metadata=1,
                refresh=1,
                retries=1,
                reserve_note="Invented lead choice",
            )
    with pytest.raises(ValueError):
        k.bulk_budget(
            (tile(),),
            model,
            Decimal(10),
            10,
            metadata=1,
            refresh=0,
            retries=1,
            reserve_note="",
        )


def test_receipt_chain_and_snapshot_immutability(tmp_path):
    t = tile()
    body = raster(t)
    root = tmp_path / "data/public_cache"
    side = c.promote(
        root,
        entry(),
        body,
        metadata(t),
        box(*t.bounds),
        proof(),
        "2026-11-19T08:00:00Z",
        sha256_hex(body),
    )
    assert side["sha256"] == sha256_hex(body)
    assert side["release_tables"] == []
    assert side["terms_words"] == "terms to be read"
    directory = root / "satellite_cdse_backup" / t.tile_id
    snap = read_snapshot(directory, sha256_hex(body))
    assert snap.body == body
    assert side["tile"]["dates"] == ["2026-11-01T12:00:00Z"]
    before = snap.receipt_path.read_bytes()
    c.promote(
        root,
        entry(),
        body,
        metadata(t),
        box(*t.bounds),
        proof(),
        "2026-11-19T09:00:00Z",
        sha256_hex(body),
    )
    assert snap.receipt_path.read_bytes() == before
    with pytest.raises(ValueError):
        c.promote(
            root,
            entry(),
            body,
            replace(metadata(t), dates=("2026-11-02T12:00:00Z",)),
            box(*t.bounds),
            proof(),
            "2026-11-19T10:00:00Z",
            sha256_hex(body),
        )
    snap.path.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        read_snapshot(directory, sha256_hex(body))


def test_receipt_raster_paths_and_partial_write_plants(tmp_path):
    t = tile()
    meta = metadata(t)
    body = raster(t)
    boundary = box(*t.bounds)
    root = tmp_path / "data/public_cache"
    for e, b, p, digest in (
        (replace(entry(), publisher=""), body, proof(), sha256_hex(body)),
        (replace(entry(), release_tables=("facts",)), body, proof(), sha256_hex(body)),
        (entry(), b"invalid", proof(), sha256_hex(b"invalid")),
        (entry(), raster(t, width=3), proof(), sha256_hex(raster(t, width=3))),
        (entry(), body, replace(proof(), sha256="wrong"), sha256_hex(body)),
        (entry(), body, proof(), "f" * 64),
    ):
        with pytest.raises(ValueError):
            c.promote(root, e, b, meta, boundary, p, "2026-11-19T08:00:00Z", digest)
    for bad in (
        tmp_path / "product/assets",
        tmp_path / "data/releases",
        root / "../escape",
        tmp_path / "web/public",
    ):
        with pytest.raises(ValueError):
            c.promote(
                bad,
                entry(),
                body,
                meta,
                boundary,
                proof(),
                "2026-11-19T08:00:00Z",
                sha256_hex(body),
            )
    root.mkdir(parents=True, exist_ok=True)
    (root / "satellite_cdse_backup").symlink_to(
        tmp_path / "escape", target_is_directory=True
    )
    with pytest.raises(ValueError):
        c.promote(
            root,
            entry(),
            body,
            meta,
            boundary,
            proof(),
            "2026-11-19T08:00:00Z",
            sha256_hex(body),
        )
    (root / "satellite_cdse_backup").unlink()
    with patch(
        "eii_custodian.publicdata.fetch.snapshots.publish_complete",
        side_effect=OSError("invented partial write"),
    ):
        with pytest.raises(ValueError):
            c.promote(
                root,
                entry(),
                body,
                meta,
                boundary,
                proof(),
                "2026-11-19T08:00:00Z",
                sha256_hex(body),
            )
    assert not list(root.rglob("*.meta.json"))
    assert not list(root.rglob("*.tif"))


def test_parent_hash_and_membership_plants(tmp_path):
    t = tile()
    body = raster(t)
    root = tmp_path / "data/public_cache"
    c.promote(
        root,
        entry(),
        body,
        metadata(t),
        box(*t.bounds),
        proof(),
        "2026-11-19T08:00:00Z",
        sha256_hex(body),
    )
    members = ((t.tile_id, sha256_hex(body)),)
    assert c.parents(root, members) == members
    for bad in (
        ((t.tile_id, "f" * 64),),
        (("../escape", sha256_hex(body)),),
        (members[0], members[0]),
        (),
    ):
        with pytest.raises(ValueError):
            c.parents(root, bad)


def test_request_hash_excludes_response_metadata():
    meta = metadata(tile())
    assert k.request_sha256(meta) == k.request_sha256(
        replace(meta, dates=("2026-11-02T12:00:00Z",), coverage="complete_valid_pixels")
    )
    assert k.request_sha256(meta) != k.request_sha256(
        replace(meta, end="2026-11-18T00:00:00Z")
    )
