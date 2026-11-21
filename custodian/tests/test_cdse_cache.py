"""Invented metric boundary, RGBA rasters, budgets and receipt attack plants."""

from __future__ import annotations

import io
import json
import subprocess
import tarfile
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
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


def raster(t, *, width=None, alpha=None):
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
            if alpha is not None:
                values[3] = alpha
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
    # 3.003 units / 0.1 quantum must ceil to 3.1, above the minimum.
    assert model.picture_cost(1001, bands=3, samples=1) == Decimal("3.1")
    plan = k.bulk_budget(
        (tile(),),
        model,
        Decimal(10),
        10,
        metadata=1,
        refresh=1,
        retries=1,
        tile_samples=1,
        reserve_note="Invented lead choice",
    )
    assert plan.requests == 5
    assert plan.pixels == 4
    assert plan.kinds == ("token", "metadata", "process", "token", "process")
    assert plan.units == Decimal("1.7")

    def budget(free_units, free_requests):
        return k.bulk_budget(
            (tile(),),
            model,
            free_units,
            free_requests,
            metadata=1,
            refresh=1,
            retries=1,
            tile_samples=1,
            reserve_note="Invented lead choice",
        )

    for free_units, free_requests, allowed in (
        (Decimal("1.7"), 5, True),
        (Decimal("1.8"), 5, True),
        (Decimal("1.6"), 5, False),
        (Decimal("1.7"), 6, True),
        (Decimal("1.7"), 4, False),
    ):
        if allowed:
            assert budget(free_units, free_requests) == plan
        else:
            with pytest.raises(ValueError, match="bulk_allowance_insufficient"):
                budget(free_units, free_requests)
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
                tile_samples=1,
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
            tile_samples=1,
            reserve_note="",
        )


@pytest.mark.parametrize("samples,allowance", [(1, "1.5"), (2, "2")])
def test_bulk_budget_reserves_wire_bands_and_explicit_tile_samples(samples, allowance):
    """INVENTED plan: old RGB/single-sample literals fit, actual factors do not."""
    from eii_custodian.publicdata.cdse.wire import INPUT_BANDS

    t = k.tiles_for(box(0, 0, 7680, 5120), k.CRS)[0]
    model = k.CostModel(
        Decimal(3 * 512 * 512),
        Decimal(1),
        Decimal("0.005"),
        Decimal("0.1"),
        Decimal(0),
        Decimal(0),
        proof(),
    )
    options = dict(metadata=0, refresh=0, retries=1, reserve_note="Invented bound")
    # Exactly two processing attempts: initial request plus one reserved retry.
    # The invented quantum has no effect on these integral documented costs.
    assert k.documented_units(t.width * t.height, INPUT_BANDS, samples) * 2 == (
        Fraction(4 * samples)
    )
    assert model.picture_cost(t.width * t.height, bands=3, samples=1) * 2 <= (
        Decimal(allowance) * 2
    )
    with pytest.raises(
        k.CdseError, match="bulk_allowance_insufficient_fallback_retained"
    ):
        k.bulk_budget(
            (t,), model, Decimal(allowance) * 2, 3, tile_samples=samples, **options
        )
    plan = k.bulk_budget(
        (t,), model, Decimal(4) * samples, 3, tile_samples=samples, **options
    )
    assert plan.units == Decimal(4) * samples
    assert plan.kinds == ("token", "process", "process")


def test_bulk_budget_requires_positive_explicit_tile_sample_bound():
    model = k.CostModel(*(Decimal(1),) * 6, proof())
    options = dict(metadata=0, refresh=0, retries=0, reserve_note="Invented bound")
    with pytest.raises(TypeError, match="tile_samples"):
        k.bulk_budget((tile(),), model, Decimal(100), 2, **options)
    for samples in (0, -1, True, 1.5, None):
        with pytest.raises(k.CdseError, match="quota_inputs_refused"):
            k.bulk_budget(
                (tile(),), model, Decimal(100), 2, tile_samples=samples, **options
            )


@pytest.mark.parametrize(
    "alpha,coverage,reason",
    [
        (128, "partial", "raster_mask_refused"),
        (0, "partial", "raster_no_valid_pixels"),
        (None, "complete_valid_pixels", "coverage_unsupported"),
    ],
)
def test_raster_mask_and_coverage_refusal_plants(alpha, coverage, reason):
    """INVENTED alpha and one-gap rasters must reach their specific refusal."""
    t = tile()
    body = raster(t, alpha=alpha)
    with pytest.raises(k.CdseError, match=f"^{reason}$"):
        c.validate_raster(body, replace(metadata(t), coverage=coverage))


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


def test_documented_unrounded_units_and_nominal_allowance():
    """INVENTED pixels/samples; official factors, never an account balance."""
    rgb = ("B04", "B03", "B02")
    assert k.documented_units(512 * 512, rgb, 1) == Fraction(1)
    assert k.documented_units(512 * 512, (*rgb, "dataMask"), 1) == Fraction(1)
    assert k.documented_units(512 * 512, (*rgb, "SCL", "dataMask"), 3) == Fraction(4)
    assert k.documented_units(4, (*rgb, "SCL", "dataMask"), 1) == Fraction(1, 75)
    assert k.documented_units(4, ("dataMask",), 1) == Fraction(1, 200)
    assert k.GENERAL_FREE_UNITS == Decimal(10000)
    assert k.GENERAL_FREE_REQUESTS == 10000
    assert k.GENERAL_UNITS_PER_MINUTE == k.GENERAL_REQUESTS_PER_MINUTE == 300
    assert k.BILLING_QUANTUM is None  # No rounding rule was stated on the read pages.
    # An INVENTED upper sample count can exhaust the published nominal allowance.
    ts = k.tiles_for(box(0, 0, 22010, 22010), "EPSG:32639")
    assert (
        sum(k.documented_units(t.width * t.height, (*rgb, "SCL"), 1) for t in ts)
        < k.GENERAL_FREE_UNITS
    )
    assert (
        sum(k.documented_units(t.width * t.height, (*rgb, "SCL"), 1000) for t in ts)
        > k.GENERAL_FREE_UNITS
    )
    for pixels, bands, samples in (
        (True, rgb, 1),
        (0, rgb, 1),
        (4, (), 1),
        (4, ("other",), 1),
        (4, ("B04", "B04"), 1),
        (4, rgb, 0),
        (4, rgb, True),
    ):
        with pytest.raises(ValueError):
            k.documented_units(pixels, bands, samples)


def test_evalscript_tracks_contributing_dates_and_masks():
    """Execute the fixed script on INVENTED samples; no provider invocation."""
    from eii_custodian.publicdata.cdse.wire import EVALSCRIPT, INPUT_BANDS

    harness = """
const rgb = {B04: 0.1, B03: 0.2, B02: 0.3, SCL: 4, dataMask: 1};
const scenes = {tiles: [{date: '2026-11-01T12:00:00Z'}, {date: '2026-11-02T12:00:00Z'}]};
let outputs = [];
for (const SCL of [0, 1, 3, 7, 8, 9, 10]) {
  outputs.push(evaluatePixel([{...rgb, SCL}, rgb], scenes));
}
outputs.push(evaluatePixel([{...rgb, dataMask: 0}], scenes));
outputs.push(evaluatePixel([{...rgb, SCL: 9}], scenes));
outputs.push(evaluatePixel([], {tiles: []}));
let metadata = {};
updateOutputMetadata(scenes, {}, metadata);
console.log(JSON.stringify({outputs, metadata, settings: setup()}));
"""
    result = subprocess.run(
        ["node", "-e", EVALSCRIPT + harness],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["outputs"][:7] == [[0.25, 0.5, 0.75, 1]] * 7
    assert output["outputs"][7:] == [[0, 0, 0, 0]] * 3
    assert output["metadata"] == {"userData": {"dates": ["2026-11-02T12:00:00Z"]}}
    assert output["settings"]["mosaicking"] == "TILE"
    assert output["settings"]["input"] == list(INPUT_BANDS)
    assert INPUT_BANDS == ("B04", "B03", "B02", "SCL", "dataMask")


def process_archive(
    body,
    dates,
    *,
    names=("default.tif", "userdata.json"),
    raster_type=tarfile.REGTYPE,
    metadata_payload=None,
):
    """INVENTED uncompressed response; never write archive paths to disk."""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:") as archive:
        payloads = (
            body,
            json.dumps({"dates": dates}).encode()
            if metadata_payload is None
            else metadata_payload,
        )
        for index, (name, payload) in enumerate(zip(names, payloads, strict=True)):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            if index == 0:
                info.type = raster_type
            archive.addfile(info, io.BytesIO(payload))
    return stream.getvalue()


def test_process_reply_binds_raster_and_dates():
    from eii_custodian.publicdata.cdse.wire import ProcessSpec, unpack_process

    t = tile()
    body = raster(t)
    meta = metadata(t)
    spec = ProcessSpec(t, meta.start, meta.end)
    packed = process_archive(body, list(meta.dates))
    actual, decoded = unpack_process(packed, spec, box(*t.bounds))
    assert actual == body
    assert decoded == replace(
        meta, method="cdse-process.v1", auxiliary_bands=("SCL", "dataMask")
    )
    from eii_custodian.publicdata.cdse import wire

    digest = k.request_sha256(decoded)
    assert digest == sha256_hex(
        json.dumps(
            wire.process_body(spec), sort_keys=True, separators=(",", ":")
        ).encode()
    )
    with patch.object(wire, "EVALSCRIPT", wire.EVALSCRIPT + "\n// INVENTED change"):
        assert k.request_sha256(decoded) != digest
    for poisoned in (
        b"invalid",
        process_archive(b"invalid", list(meta.dates)),
        process_archive(raster(t, width=3), list(meta.dates)),
        process_archive(body, []),
        process_archive(body, [meta.start, meta.start]),
        process_archive(body, [meta.end]),
        process_archive(body, [meta.start[:10]]),
        process_archive(body, [3]),
        process_archive(body, None),
        process_archive(body, list(meta.dates), metadata_payload=b"[]"),
        process_archive(body, list(meta.dates), metadata_payload=b"{"),
        process_archive(
            body, list(meta.dates), metadata_payload=b'{"dates":[],"extra":1}'
        ),
        process_archive(
            body, list(meta.dates), names=("../default.tif", "userdata.json")
        ),
        process_archive(body, list(meta.dates), names=("default.tif", "default.tif")),
    ):
        with pytest.raises(ValueError, match="process_response_refused"):
            unpack_process(poisoned, spec, box(*t.bounds))
    # These header guards must decide before any archive member is opened.
    for poisoned in (
        process_archive(body, list(meta.dates), raster_type=tarfile.SYMTYPE),
        process_archive(b"", list(meta.dates)),
        process_archive(
            body, list(meta.dates), names=("../default.tif", "userdata.json")
        ),
    ):
        with patch.object(
            tarfile.TarFile,
            "extractfile",
            side_effect=AssertionError("unsafe archive member opened"),
        ):
            with pytest.raises(ValueError, match="process_response_refused"):
                unpack_process(poisoned, spec, box(*t.bounds))
