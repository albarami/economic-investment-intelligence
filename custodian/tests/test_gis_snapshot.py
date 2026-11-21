"""S2-T51: all bytes, geometry and operating-system observations are invented."""

from __future__ import annotations

import json
import warnings
from base64 import b64decode
from copy import deepcopy
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from rasterio import Env
from rasterio.errors import NotGeoreferencedWarning, RasterioIOError
from rasterio.io import MemoryFile
from shapely.geometry import MultiPolygon, box

from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.gis import snapshot_policy as policy
from eii_custodian.publicdata.gis.snapshot_archive import Archive, verify_selection
from eii_custodian.publicdata.gis.snapshot_runner import acquire
from eii_custodian.publicdata.gis.snapshot_scheme import enumerate_tiles, read_scheme

STAMP = "2026-11-20T00:00:00Z"
BOUNDARY_RECEIPT = {
    "source_id": "invented_boundary",
    "key": "invented_boundary",
    "publisher": "Invented boundary publisher",
    "url": "https://www.data.gov.qa/invented-boundary",
    "licence_basis": "dataset",
    "licence_id": "CC-BY-4.0",
    "decision_record": "",
    "terms_words": "Invented terms",
    "terms_read_on": "2026-11-20",
}
# Preserve the old header-only bytes as a planted invalid successful response.
NO_SCAN_JPEG = b"\xff\xd8\xff\xc0\x00\x11\x08\x02\x00\x02\x00\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00invented-tile\xff\xd9"


def encoded_jpeg(value=0):
    """A genuine, uniform invented tile encoded by the pinned in-memory driver."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as memory:
            with memory.open(
                driver="JPEG", width=512, height=512, count=1, dtype="uint8"
            ) as dataset:
                dataset.write(np.full((1, 512, 512), value, dtype="uint8"))
            return memory.read()


JPEG = encoded_jpeg()
DQT = JPEG.index(b"\xff\xdb")
NO_QUANTIZATION_JPEG = (
    JPEG[:DQT] + JPEG[DQT + 2 + int.from_bytes(JPEG[DQT + 2 : DQT + 4], "big") :]
)
SOS = JPEG.index(b"\xff\xda")
INVALID_SCAN_JPEG = JPEG[: SOS + 2] + b"\x00\x02\xff\xd9"


def truncated_noise_jpeg(percent, *, progressive=False):
    """Keep a seeded invented scan's prefix and EOI, including zero scan bytes."""
    pixels = np.random.default_rng(79).integers(0, 256, (1, 512, 512), dtype="uint8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as memory:
            with memory.open(
                driver="JPEG",
                width=512,
                height=512,
                count=1,
                dtype="uint8",
                PROGRESSIVE="YES" if progressive else "NO",
            ) as dataset:
                dataset.write(pixels)
            body = memory.read()
        assert (b"\xff\xc2" if progressive else b"\xff\xc0") in body
        # The intact control decodes under the same strict configuration.
        with Env(GDAL_ERROR_ON_LIBJPEG_WARNING="TRUE"):
            with MemoryFile(body, filename="invented.jpg") as memory:
                with memory.open(driver="JPEG") as dataset:
                    assert dataset.read().shape == (1, 512, 512)
    sos = body.index(b"\xff\xda")
    scan = sos + 2 + int.from_bytes(body[sos + 2 : sos + 4], "big")
    return body[: scan + (len(body) - 2 - scan) * percent // 100] + b"\xff\xd9"


@pytest.fixture(autouse=True)
def isolated_machine_lock(monkeypatch):
    monkeypatch.setattr(policy, "MACHINE_LOCK", "\0eii-test-" + uuid4().hex)


@pytest.fixture(autouse=True)
def no_network():
    with patch(
        "socket.socket.connect", side_effect=AssertionError("network forbidden")
    ):
        yield


def metadata():
    return json.dumps(
        {
            "tileInfo": {
                "rows": 512,
                "cols": 512,
                "format": "JPEG",
                "spatialReference": {"wkid": 2932},
                "origin": {"x": 0, "y": 2048},
                "lods": [
                    {"level": n, "resolution": 0.53 * 2 ** (10 - n)} for n in range(11)
                ],
            },
            "fullExtent": {
                "xmin": 0,
                "ymin": 0,
                "xmax": 2048,
                "ymax": 2048,
                "spatialReference": {"wkid": 2932},
            },
        }
    ).encode()


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


def test_closed_contract_and_rate_includes_retries():
    assert len(policy.SERVICES) == 11
    clock = Clock()
    pace = policy.Pacer(clock.time, clock.sleep)
    starts = []
    for _ in range(23):
        pace.wait()
        starts.append(clock.now)
    assert all(b - a >= 0.1 - 1e-12 for a, b in pairwise(starts))
    with pytest.raises(policy.SnapshotRefusal, match="rate"):
        pace.record_start(clock.now)
    pace.defer(4)
    pace.wait()
    assert clock.waits[-1] >= 4


@pytest.mark.parametrize(
    "level,date,reason",
    [
        (11, "1995-02", "level_11_deferred"),
        (12, "1995-02", "level"),
        (-1, "1995-02", "level"),
        (True, "1995-02", "level"),
        (10, "1900-01", "date"),
    ],
)
def test_level_and_date_refused_before_transport(level, date, reason):
    with pytest.raises(policy.SnapshotRefusal, match=reason):
        policy.tile_url(date, level, 0, 0)


@pytest.mark.parametrize(
    "url",
    [
        "http://services.gisqatar.org.qa/x",
        "https://other.invalid/x",
        "https://services.gisqatar.org.qa/server/rest/services/QARS_Custom_Locator/GeocodeServer",
        "https://services.gisqatar.org.qa:444/x",
        "https://services.gisqatar.org.qa/../x",
        "https://services.gisqatar.org.qa/x?token=no",
    ],
)
def test_host_path_and_locator_refused(url):
    with pytest.raises(policy.SnapshotRefusal, match="request"):
        policy.check_url(url)


def test_root_unset_wrong_drive_traversal_and_symlink(tmp_path):
    for value in (
        None,
        "",
        "/tmp/snapshot",
        "/mnt/d",
        "/mnt/d/data/nested",
        "/mnt/d/../x",
    ):
        with pytest.raises(policy.SnapshotRefusal, match="root"):
            policy.configured_root({} if value is None else {policy.ROOT_ENV: value})
    root = tmp_path / "snapshot"
    root.mkdir()
    with pytest.raises(policy.SnapshotRefusal, match="escape"):
        policy.safe_child(root, "../outside")
    other = tmp_path / "elsewhere"
    other.mkdir()
    (root / "link").symlink_to(other, target_is_directory=True)
    with pytest.raises(policy.SnapshotRefusal, match="escape"):
        policy.safe_child(root, "link/file")


def test_lock_is_global_and_nonblocking(tmp_path):
    with policy.run_lock(tmp_path, name=policy.MACHINE_LOCK):
        with pytest.raises(policy.SnapshotRefusal, match="locked"):
            with policy.run_lock(tmp_path, name=policy.MACHINE_LOCK):
                pytest.fail("second run entered")
    with policy.run_lock(tmp_path, name=policy.MACHINE_LOCK):
        pass


def test_machine_lock_refuses_two_different_roots(tmp_path):
    with policy.run_lock(tmp_path / "first", name=policy.MACHINE_LOCK):
        with pytest.raises(policy.SnapshotRefusal, match=r"^run_locked$"):
            with policy.run_lock(tmp_path / "second", name=policy.MACHINE_LOCK):
                pytest.fail("second root admitted")
    with policy.run_lock(tmp_path / "second", name=policy.MACHINE_LOCK):
        pass


def test_lock_does_not_relabel_body_io_errors(tmp_path):
    import errno

    for code in (errno.ENOSPC, errno.EIO):
        with pytest.raises(OSError) as caught:
            with policy.run_lock(tmp_path, name=policy.MACHINE_LOCK):
                raise OSError(code, "invented disk fault")
        assert caught.value.errno == code


def test_production_lock_name_is_constant_across_processes():
    assert (
        policy.run_lock.__wrapped__.__kwdefaults__["name"]
        == "\0eii-gis-imagery-snapshot"
    )


def test_run_passes_exact_machine_lock_name(tmp_path):
    from eii_custodian.publicdata.gis import snapshot_runner as runner

    with (
        patch.object(runner, "configured_root", return_value=tmp_path),
        patch.object(
            runner, "run_lock", side_effect=policy.SnapshotRefusal("lock_probe")
        ) as lock,
    ):
        assert runner.run({}) == 1
    lock.assert_called_once_with(tmp_path, name=policy.MACHINE_LOCK)


@pytest.mark.parametrize(
    "code,reason",
    [(28, "disk_safety_stop"), (122, "disk_safety_stop"), (5, "io_error")],
)
@pytest.mark.parametrize("wrapped", [False, True])
def test_run_reports_disk_and_io_errors_without_paths(
    tmp_path, capsys, code, reason, wrapped
):
    from eii_custodian.publicdata.gis import snapshot_runner as runner
    from eii_custodian.publicdata.gis.snapshot_archive import _immutable

    def fail():
        if wrapped:
            _immutable(tmp_path / "invented-object", b"invented")
        else:
            raise OSError(code, "secret-path")

    with (
        patch.object(runner, "configured_root", return_value=tmp_path),
        patch.object(runner, "lower_priority", fail),
        patch(
            "eii_custodian.publicdata.fetch.snapshots._publish",
            side_effect=OSError(code, "secret-path"),
        ),
    ):
        assert runner.run({}) == 1
    output = capsys.readouterr().out
    assert reason in output and "lock_unavailable" not in output
    assert "secret-path" not in output


def test_priority_and_disk_are_fail_closed():
    calls = []
    policy.lower_priority(lambda: calls.append("nice"), lambda: calls.append("ionice"))
    assert calls == ["nice", "ionice"]
    with pytest.raises(policy.SnapshotRefusal, match="priority"):
        policy.lower_priority(lambda: (_ for _ in ()).throw(OSError()), lambda: None)
    with pytest.raises(policy.SnapshotRefusal, match="disk"):
        policy.check_capacity(
            10, 20, remaining=15, staging=4, reserve=3, system_reserve=11
        )
    policy.check_capacity(
        50, 100, remaining=15, staging=4, reserve=3, system_reserve=11
    )


def test_enumeration_includes_island_and_coastal_intersections():
    scheme = read_scheme(metadata())
    land = MultiPolygon([box(1, 1800, 50, 1900), box(300, 1800, 310, 1900)])
    tiles = enumerate_tiles(scheme, land, levels=(10,))
    assert [(t.level, t.row, t.column) for t in tiles] == [(10, 0, 0), (10, 0, 1)]
    with pytest.raises(policy.SnapshotRefusal, match="level_11_deferred"):
        enumerate_tiles(scheme, land, levels=(11,))


@pytest.mark.parametrize(
    "field,value",
    [
        ("rows", 256),
        ("format", "PNG"),
        ("spatialReference", {"wkid": 4326}),
        ("origin", {"x": float("nan"), "y": 0}),
        ("lods", [{"level": 10, "resolution": 0.132}]),
    ],
)
def test_metadata_scheme_incompatibilities(field, value):
    meta = json.loads(metadata())
    meta["tileInfo"][field] = value
    with pytest.raises(policy.SnapshotRefusal, match="metadata"):
        read_scheme(json.dumps(meta).encode())


def fixture_archive(tmp_path):
    archive = Archive(
        tmp_path,
        {
            "boundary_sha256": "a" * 64,
            "metadata_sha256": "b" * 64,
            "date": "1995-02",
            "level": 10,
            "tiles": [[10, 0, 0]],
        },
    )
    return archive, archive.write_shard(0, {(10, 0, 0): JPEG}, STAMP)


def test_assembled_release_equals_product_imagery_fixture(tmp_path):
    from eii_custodian.publicdata.gis.snapshot_release import assemble

    fixture = (
        Path(__file__).resolve().parents[2] / "product/tests/fixtures/released_imagery"
    )
    assert (fixture / "tile.jpg").read_bytes() == JPEG
    archive, _ = fixture_archive(tmp_path / "acquisition")
    manifest = archive.complete([0], STAMP)
    selection = verify_selection(archive.root, manifest)
    assert tuple(selection.iter_tiles()) == (("1995-02", 10, 0, 0, JPEG),)
    output = tmp_path / "release"
    identity = assemble((selection,), output)
    expected = fixture / "release"
    assert identity == next(expected.glob("*.json")).stem
    assert {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(expected).with_suffix("")
        if path.suffix == ".b64"
        else path.relative_to(expected): b64decode(path.read_bytes())
        if path.suffix == ".b64"
        else path.read_bytes()
        for path in expected.rglob("*")
        if path.is_file()
    }


def test_immutable_shard_receipt_and_resume(tmp_path):
    archive, identity = fixture_archive(tmp_path)
    assert archive.read_shard(0).sha256 == identity
    assert archive.write_shard(0, {(10, 0, 0): JPEG}, STAMP) == identity
    with pytest.raises(policy.SnapshotRefusal, match="identity"):
        Archive(tmp_path, {**archive.enumeration, "boundary_sha256": "c" * 64})
    manifest = archive.complete([0], STAMP)
    selection = verify_selection(tmp_path, manifest)
    assert len(selection.files) >= 3
    assert tuple(selection.iter_tiles()) == (("1995-02", 10, 0, 0, JPEG),)


@pytest.mark.parametrize(
    "corrupt", ["member", "receipt", "shard", "index", "completion"]
)
def test_resume_never_skips_corruption_or_incomplete_publish(tmp_path, corrupt):
    archive, _ = fixture_archive(tmp_path)
    if corrupt == "completion":
        with pytest.raises(policy.SnapshotRefusal, match=r"^archive_integrity$"):
            verify_selection(tmp_path, "d" * 64)
        return
    snap = archive.read_shard(0)
    path = {
        "shard": snap.path,
        "receipt": snap.receipt_path,
        "index": next((tmp_path / "shards" / "000000" / "index").glob("*.json")),
        "member": snap.path,
    }[corrupt]
    if corrupt == "receipt":
        path.unlink()
    else:
        path.write_bytes(b"corrupt invented bytes")
    with pytest.raises(policy.SnapshotRefusal, match="integrity"):
        archive.read_shard(0)


def test_acquire_resumes_and_paces_metadata_and_tiles(tmp_path):
    clock = Clock()
    pace = policy.Pacer(clock.time, clock.sleep)
    calls = []

    def transport(url):
        calls.append((url, clock.now))
        return Response(url, metadata() if url.endswith("?f=json") else JPEG, ())

    boundary = box(1, 1800, 50, 1900)
    first = acquire(
        tmp_path,
        "1995-02",
        boundary,
        "a" * 64,
        transport,
        pace,
        lambda: STAMP,
        lambda: None,
        levels=(10,),
        boundary_receipt=BOUNDARY_RECEIPT,
    )
    again = acquire(
        tmp_path,
        "1995-02",
        boundary,
        "a" * 64,
        transport,
        pace,
        lambda: STAMP,
        lambda: None,
        levels=(10,),
        boundary_receipt=BOUNDARY_RECEIPT,
    )
    assert first == again
    assert len(calls) == 3  # metadata again; no tile skipped without verification
    assert all(b[1] - a[1] >= 0.1 - 1e-12 for a, b in pairwise(calls))

    def changed(url):
        meta = json.loads(metadata())
        meta["copyrightText"] = "changed"
        return Response(url, json.dumps(meta).encode(), ())

    with pytest.raises(policy.SnapshotRefusal, match="identity"):
        acquire(
            tmp_path,
            "1995-02",
            boundary,
            "a" * 64,
            changed,
            pace,
            lambda: STAMP,
            lambda: None,
            levels=(10,),
            boundary_receipt=BOUNDARY_RECEIPT,
        )


def test_redirect_is_not_followed_and_retries_are_bounded(tmp_path):
    clock = Clock()
    pace = policy.Pacer(clock.time, clock.sleep)

    def redirect(url):
        return Response("https://other.invalid/x", b"", ("https://other.invalid/x",))

    with pytest.raises(policy.SnapshotRefusal, match="redirect"):
        acquire(
            tmp_path,
            "1995-02",
            box(1, 1800, 2, 1801),
            "a" * 64,
            redirect,
            pace,
            lambda: STAMP,
            lambda: None,
            levels=(10,),
            boundary_receipt=BOUNDARY_RECEIPT,
        )
    calls = []

    def failure(url):
        calls.append(url)
        raise TransportFault("http", url, 503)

    with pytest.raises(policy.SnapshotRefusal, match="request_failed"):
        acquire(
            tmp_path,
            "1995-02",
            box(1, 1800, 2, 1801),
            "a" * 64,
            failure,
            pace,
            lambda: STAMP,
            lambda: None,
            levels=(10,),
            boundary_receipt=BOUNDARY_RECEIPT,
        )
    assert len(calls) == 4
    assert clock.waits[-3:] == pytest.approx([1, 2, 4], abs=1e-12)


def test_member_hash_guard_independent_of_outer_shard_hash(tmp_path):
    from dataclasses import replace

    from eii_custodian.publicdata.gis.snapshot_archive import unpack

    archive, _ = fixture_archive(tmp_path)
    snap = archive.read_shard(0)
    side = dict(snap.sidecar)
    side["members"] = [{"name": "10/0/0.jpg", "sha256": "0" * 64, "bytes": len(JPEG)}]
    with pytest.raises(policy.SnapshotRefusal, match="integrity"):
        tuple(unpack(replace(snap, sidecar=side)))


def test_long_server_wait_covers_metadata_retry(tmp_path):
    from eii_custodian.publicdata.gis.snapshot_runner import request

    clock = Clock()
    calls = []

    def slow(url):
        calls.append(clock.now)
        if len(calls) == 1:
            return Response(
                url,
                b"",
                (),
                headers={"Retry-After": "13"},
                evidence={"http_status": 429},
            )
        return Response(url, b"invented", ())

    assert (
        request(
            policy.service_url("1995-02") + "?f=json",
            slow,
            policy.Pacer(clock.time, clock.sleep),
            lambda: STAMP,
            lambda: None,
        )
        == b"invented"
    )
    assert calls[0] >= 0.1
    assert calls[1] - calls[0] == pytest.approx(13.0, abs=1e-12)


def test_registry_is_closed_and_ordinary_build_never_selects_snapshot(tmp_path):
    from eii_custodian.publicdata.gis.snapshot_policy import load_contract

    contract = load_contract()
    assert (
        contract["max_level"] == 10
        and contract["ordinary_build"] is False
        and contract["nightly_live_fetch"] is False
    )
    bad = dict(contract, free_text_locator=True)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(policy.SnapshotRefusal, match="contract"):
        load_contract(path)


def test_command_root_unset_refuses_without_any_connection(tmp_path):
    from commands.build_public import run

    with (
        patch(
            "commands.build_public.run_build",
            side_effect=AssertionError("ordinary build entered"),
        ),
        patch(
            "eii_custodian.publicdata.fetch.transport.open_gis_snapshot",
            side_effect=AssertionError("network"),
        ),
    ):
        assert run(tmp_path, {}, ("--gis-imagery-snapshot",)) == 1
        assert run(tmp_path, {}, ("--gis-imagery-snapshot", "--seed", "9")) == 2


def all_dates_acquisition(tmp_path, monkeypatch, plant=None):
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot
    from eii_custodian.publicdata.gis import snapshot_release as release
    from eii_custodian.publicdata.gis import snapshot_runner as runner
    from eii_custodian.publicdata.gis.snapshot_archive import digest

    root = tmp_path / "snapshot"
    root.mkdir()
    from rasterio.warp import transform_geom

    # An invented native-grid patch, inverse-projected solely to exercise the
    # production WGS84-to-QNG path; no country geometry or record is read.
    boundary = json.dumps(
        transform_geom(
            "EPSG:2932",
            "EPSG:4326",
            {
                "type": "Polygon",
                "coordinates": [
                    [[1, 1800], [2, 1800], [2, 1801], [1, 1801], [1, 1800]]
                ],
            },
        )
    ).encode()
    (root / "national-land.geojson").write_bytes(boundary)
    (root / "national-land.meta.json").write_text(
        json.dumps(
            {
                "source_id": "invented_boundary",
                "key": "invented_boundary",
                "publisher": "Invented boundary publisher",
                "fetch_url": "https://www.data.gov.qa/invented-boundary",
                "licence_basis": "dataset",
                "licence_id": "CC-BY-4.0",
                "decision_record": "",
                "terms_words": "Invented terms",
                "terms_read_on": "2026-11-20",
                "retrieved_utc": STAMP,
                "sha256": digest(boundary),
                "method_version": "invented-union-v1",
                "upstream_sha256": "e" * 64,
            }
        )
    )
    (root / "job.json").write_text(
        json.dumps(
            {
                "boundary_sha256": digest(boundary),
                "remaining_bytes": 100 * runner.GIB,
                "staging_bytes": 3 * runner.GIB,
                "reserve_bytes": 5 * runner.GIB,
                "system_reserve_bytes": 2 * runner.GIB,
            }
        )
    )
    clock = Clock()
    called = []

    class Watch:
        def __init__(self, *args, **kwargs):
            pass

        def check(self):
            called.append("disk")

    def transport(url):
        meta = json.loads(metadata())
        if plant == "partial":
            meta["fullExtent"]["xmax"] = 1.5
        if plant == "gap" and not url.endswith("?f=json"):
            return Response(url, b"", (), evidence={"http_status": 404})
        return Response(
            url, json.dumps(meta).encode() if url.endswith("?f=json") else JPEG, ()
        )

    monkeypatch.setattr(runner, "configured_root", lambda env: root)
    monkeypatch.setattr(release, "configured_root", lambda env: root)
    monkeypatch.setattr(runner, "open_gis_snapshot", transport)
    monkeypatch.setattr(
        runner, "Pacer", lambda **kwargs: policy.Pacer(clock.time, clock.sleep)
    )
    monkeypatch.setattr(runner, "lower_priority", lambda: called.append("priority"))
    monkeypatch.setattr(runner, "DiskWatch", Watch)
    assert runner.run({}) == 0
    assert called[0] == "priority" and "disk" in called
    with pytest.raises(policy.SnapshotRefusal, match="selection"):
        release.reviewed_inputs({})  # no implicit latest pin
    pointer = next((root / "all-dates" / "index").glob("*.json"))
    identity = pointer.stem
    complete = json.loads(read_snapshot(root / "all-dates", identity).body)
    assert set(complete["dates"]) == set(policy.SERVICES)
    (root / "release-selection.json").write_text(
        json.dumps({"manifest_sha256": identity})
    )
    selected_root, selections, files = release.reviewed_inputs({})
    assert selected_root == root and len(selections) == 121
    assert all(path != root and path.is_file() for path, _ in files)
    assert all(path.name != "selection.json" for path, _ in files)
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    level_root = root / "1995-02/level-10"
    enumeration = json.loads(
        read_checked(level_root / "completion", complete["dates"]["1995-02"]["10"]).body
    )["enumeration"]
    projected = read_checked(
        level_root / "inputs/boundary", enumeration["inputs"]["boundary"]
    )
    assert projected.sidecar["publisher"] == "Invented boundary publisher"
    assert projected.sidecar["url"] == "https://www.data.gov.qa/invented-boundary"
    assert projected.sidecar["upstream_sha256"] == digest(boundary)
    return root, selections, files, complete, boundary, identity


@pytest.mark.parametrize(
    "plant",
    [None, "gap", "partial", "coverage"]
    + [
        (field, stage)
        for field in (
            "publisher",
            "url",
            "licence_basis",
            "decision_record",
            "terms_read_on",
            "retrieved_utc",
            "bytes",
            "sha256",
            "foreign_url",
            "unknown_field",
            "boundary_source_url",
        )
        for stage in ("resume", "selection")
    ],
)
def test_all_dates_mode_is_separate_complete_and_explicitly_selected(
    tmp_path, monkeypatch, capsys, plant
):
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot
    from eii_custodian.publicdata.gis import snapshot_release as release
    from eii_custodian.publicdata.gis import snapshot_runner as runner
    from eii_custodian.publicdata.gis.snapshot_archive import digest, read_checked

    root, selections, files, complete, _boundary, identity = all_dates_acquisition(
        tmp_path, monkeypatch, plant
    )
    if plant in (None, "gap"):
        # Assembly uses the same immutable manifest/receipt pair as the sandbox.
        # Count copies, too: shared inputs must be carried exactly once.
        from eii_custodian.publicdata.gis.snapshot_archive import canonical

        manifest = read_checked(root / "all-dates", identity)
        manifest_files = (
            (manifest.path, manifest.sha256),
            (manifest.receipt_path, digest(manifest.receipt_path.read_bytes())),
        )
        for item in manifest_files:
            assert sum(item in selection.files for selection in selections) == 1
            assert files.count(item) == 1
        output = tmp_path / "release"
        copied = []
        original_copy = release.shutil.copyfile

        def copy(source, target):
            copied.append(source)
            return original_copy(source, target)

        with patch.object(release.shutil, "copyfile", copy):
            assembled = release.assemble(selections, output)
        for source, sha in manifest_files:
            assert copied.count(source) == 1
            target = output / "objects" / (sha + ".json")
            assert target.read_bytes() == source.read_bytes()
            assert digest(target.read_bytes()) == sha
        release_manifest = json.loads((output / (assembled + ".json")).read_bytes())
        assert bool(release_manifest["tiles"]) is (plant is None)
        assert canonical(complete) == manifest.body
    if plant in ("gap", "partial"):
        coverage = complete["coverage"]["1995-02"]["10"]
        if plant == "gap":
            assert (
                coverage["gaps"][0]["http_status"] == 404 and coverage["gap_count"] == 1
            )
        else:
            from shapely.geometry import shape

            assert not shape(coverage["uncovered"]).is_empty
        return
    if isinstance(plant, tuple):
        field, stage = plant

        def damage(side):
            if field == "foreign_url":
                side["url"] = "https://foreign.invalid/"
            elif field == "unknown_field":
                side["unregistered"] = "invented"
            elif field == "boundary_source_url":
                side.pop("url")
            else:
                side.pop(field)

        folder, receipt_id = (
            (root / "boundary-source", complete["boundary_source"])
            if field == "boundary_source_url"
            else (root / "all-dates", identity)
        )
        rewrite_sidecar(folder, receipt_id, damage)
        if stage == "resume":
            assert runner.run({}) == 1
            if field in {"unknown_field", "boundary_source_url"}:
                assert "receipt_fields" in capsys.readouterr().out
        else:
            reason = (
                r"^receipt_fields$"
                if field in {"unknown_field", "boundary_source_url"}
                else r"receipt|integrity"
            )
            with pytest.raises(policy.SnapshotRefusal, match=reason):
                release.reviewed_inputs({})
        return
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot
    from eii_custodian.publicdata.gis.snapshot_archive import canonical

    if plant == "coverage":
        complete["coverage"]["1995-02"]["10"]["gap_count"] += 1
        changed_body = canonical(complete)
        changed_id = digest(changed_body)
        publish_snapshot(
            root / "all-dates",
            "json",
            changed_body,
            runner.public_chain("all-dates", "all-dates", STAMP),
            identity=changed_id,
        )
        (root / "release-selection.json").write_text(
            json.dumps({"manifest_sha256": changed_id})
        )
        with pytest.raises(
            policy.SnapshotRefusal, match=r"^release_selection_identity$"
        ):
            release.reviewed_inputs({})
        return

    incomplete = deepcopy(complete)
    incomplete["dates"]["1995-02"].pop("0")
    incomplete_body = canonical(incomplete)
    incomplete_id = digest(incomplete_body)
    publish_snapshot(
        root / "all-dates",
        "json",
        incomplete_body,
        runner.public_chain("all-dates", "all-dates", STAMP),
        identity=incomplete_id,
    )
    (root / "release-selection.json").write_text(
        json.dumps({"manifest_sha256": incomplete_id})
    )
    with pytest.raises(policy.SnapshotRefusal, match="incomplete"):
        release.reviewed_inputs({})
    (root / "release-selection.json").write_text(
        json.dumps({"manifest_sha256": identity})
    )
    complete["dates"].pop("2025-07")
    # A missing date cannot be promoted by editing the manifest/index.
    snap = read_snapshot(root / "all-dates", identity)
    snap.path.write_text(json.dumps(complete))
    with pytest.raises(policy.SnapshotRefusal, match="integrity"):
        release.reviewed_inputs({})


def test_resume_refuses_symlinked_index_before_reading_target(tmp_path):
    archive, _ = fixture_archive(tmp_path / "archive")
    index = next((archive.root / "shards/000000/index").glob("*.json"))
    target = tmp_path / "not-an-input.json"
    target.write_bytes(index.read_bytes())
    index.unlink()
    index.symlink_to(target)
    # A trap distinguishes refusal before read from a hash/shape refusal afterwards.
    original = type(target).read_bytes

    def guarded(path):
        if path == index:
            pytest.fail("read followed a symlink")
        return original(path)

    with (
        patch.object(type(target), "read_bytes", guarded),
        pytest.raises(policy.SnapshotRefusal, match=r"integrity|escape"),
    ):
        archive.read_shard(0)


def test_root_requires_the_invented_drive_to_be_mounted(tmp_path):
    root = tmp_path / "snapshot"
    with pytest.raises(policy.SnapshotRefusal, match="root_drive_unmounted"):
        policy.configured_root(
            {policy.ROOT_ENV: str(root)},
            drive=tmp_path,
            drive_ready=lambda drive: False,
        )
    assert (
        policy.configured_root(
            {policy.ROOT_ENV: str(root)}, drive=tmp_path, drive_ready=lambda drive: True
        )
        == root
    )


def test_disk_watch_does_not_credit_other_jobs_consuming_the_drive(tmp_path):
    from types import SimpleNamespace

    from eii_custodian.publicdata.gis.snapshot_runner import DiskWatch

    free = {"system": 100, "data": 100}

    def disk(path):
        return SimpleNamespace(
            free=free["system"] if str(path) == "/" else free["data"]
        )

    watch = DiskWatch(
        tmp_path,
        {
            "remaining_bytes": 70,
            "staging_bytes": 10,
            "reserve_bytes": 10,
            "system_reserve_bytes": 20,
        },
        disk=disk,
    )
    free["data"] = 80
    with pytest.raises(policy.SnapshotRefusal, match="disk"):
        watch.check()


def test_jpeg_dimensions_must_match_the_declared_tile_size():
    from eii_custodian.publicdata.gis.snapshot_archive import jpeg

    wrong = b"\xff\xd8\xff\xc0\x00\x11\x08\x01\x00\x02\x00\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00invented\xff\xd9"
    with pytest.raises(policy.SnapshotRefusal, match="tile_dimensions"):
        jpeg(wrong)


@pytest.mark.parametrize("failure", ["503", "io"])
def test_interruption_retains_complete_shards_and_resumes_only_the_gap(
    tmp_path, failure
):
    clock = Clock()
    pace = policy.Pacer(clock.time, clock.sleep)
    meta = json.loads(metadata())
    meta["fullExtent"]["xmax"] = 200000
    body = json.dumps(meta).encode()
    calls = []

    def interrupted(url):
        calls.append(url)
        if url.endswith("?f=json"):
            return Response(url, body, ())
        if url.endswith("/0/" + str(policy.SHARD_TILES)):
            if failure == "503":
                raise TransportFault("http", url, 503)
            raise OSError("invented interruption")
        return Response(url, JPEG, ())

    land = box(1, 1800, 512 * 0.53 * policy.SHARD_TILES + 1, 1801)
    exception, reason = (
        (policy.SnapshotRefusal, "request_failed")
        if failure == "503"
        else (OSError, "invented interruption")
    )
    with pytest.raises(exception, match=reason):
        acquire(
            tmp_path,
            "1995-02",
            land,
            "a" * 64,
            interrupted,
            pace,
            lambda: STAMP,
            lambda: None,
            levels=(10,),
            boundary_receipt=BOUNDARY_RECEIPT,
        )
    assert not (tmp_path / "1995-02/level-10/completion").exists()
    completed = []

    def resumed(url):
        completed.append(url)
        return Response(url, body if url.endswith("?f=json") else JPEG, ())

    result = acquire(
        tmp_path,
        "1995-02",
        land,
        "a" * 64,
        resumed,
        pace,
        lambda: STAMP,
        lambda: None,
        levels=(10,),
        boundary_receipt=BOUNDARY_RECEIPT,
    )
    assert len(result) == 1 and len(completed) == 2
    assert completed[-1].endswith("/0/" + str(policy.SHARD_TILES))


def test_changed_bytes_publish_new_objects_without_overwriting_selected_shard(tmp_path):
    archive, _ = fixture_archive(tmp_path)
    original = archive.read_shard(0)
    with pytest.raises(policy.SnapshotRefusal, match="identity_changed"):
        archive.write_shard(0, {(10, 0, 0): encoded_jpeg(100)}, STAMP)
    assert archive.read_shard(0).sha256 == original.sha256
    assert len(list((tmp_path / "shards/000000/index").glob("*.json"))) == 2


def test_level_eleven_refused_before_send_with_or_without_keys_and_offline_control(
    tmp_path, monkeypatch
):
    def never(url):
        pytest.fail("transport reached")

    for key in (None, "invented-canary"):
        for offline in (None, "0", "1"):
            for name, value in (("ESRI_API_KEY", key), ("EII_OFFLINE", offline)):
                monkeypatch.delenv(name, raising=False)
                if value is not None:
                    monkeypatch.setenv(name, value)
            with pytest.raises(policy.SnapshotRefusal, match="level_11_deferred"):
                acquire(
                    tmp_path,
                    "1995-02",
                    box(1, 1800, 2, 1801),
                    "a" * 64,
                    never,
                    policy.Pacer(),
                    lambda: STAMP,
                    lambda: None,
                    levels=(11,),
                    boundary_receipt=BOUNDARY_RECEIPT,
                )


def test_real_transport_installs_a_redirect_refusal_before_any_second_send():
    from eii_custodian.publicdata.fetch.transport import open_gis_snapshot

    handlers = []

    class Opener:
        def open(self, *args, **kwargs):
            raise TransportFault("redirect", "")

    def factory(handler):
        handlers.append(handler)
        return Opener()

    with patch("urllib.request.build_opener", factory):
        with pytest.raises(TransportFault, match="redirect"):
            open_gis_snapshot(policy.service_url("1995-02") + "?f=json")
    assert len(handlers) == 1
    with pytest.raises(TransportFault, match="redirect"):
        handlers[0]().redirect_request(
            None, None, 302, "", None, "https://other.invalid/x"
        )


def test_boundary_input_requires_its_public_chain_and_archives_original_bytes(tmp_path):
    from eii_custodian.publicdata.gis.snapshot_archive import digest, read_checked
    from eii_custodian.publicdata.gis.snapshot_runner import pin_boundary

    body = b'{"type":"Polygon","coordinates":[]}'
    with pytest.raises(policy.SnapshotRefusal, match="boundary_lineage"):
        pin_boundary(tmp_path, body, digest(body))
    side = {
        "source_id": "invented_boundary",
        "key": "invented_boundary",
        "publisher": "Invented boundary publisher",
        "fetch_url": "https://www.data.gov.qa/invented-boundary",
        "licence_basis": "dataset",
        "licence_id": "CC-BY-4.0",
        "decision_record": "",
        "terms_words": "Invented terms",
        "terms_read_on": "2026-11-20",
        "retrieved_utc": STAMP,
        "sha256": digest(body),
        "method_version": "invented-union-v1",
        "upstream_sha256": "e" * 64,
    }
    (tmp_path / "national-land.meta.json").write_text(json.dumps(side))
    identity = pin_boundary(tmp_path, body, digest(body))
    assert read_checked(tmp_path / "boundary-source", identity).body == body
    side["sha256"] = "f" * 64
    (tmp_path / "national-land.meta.json").write_text(json.dumps(side))
    with pytest.raises(policy.SnapshotRefusal, match="boundary_lineage"):
        pin_boundary(tmp_path, body, digest(body))


def test_ordinary_build_with_snapshot_variable_never_enters_the_mode(tmp_path):
    from commands.build_public import run
    from eii_custodian.publicdata.fetch.build import BuildOutcome

    with (
        patch("commands.build_public.load_registry", return_value=()),
        patch("commands.build_public.run_build", return_value=BuildOutcome((), None)),
        patch(
            "eii_custodian.publicdata.gis.snapshot_runner.run",
            side_effect=AssertionError("snapshot entered"),
        ),
    ):
        assert (
            run(
                tmp_path,
                {policy.ROOT_ENV: "unread-invalid-path"},
                (),
                transport=lambda url: pytest.fail("transport"),
            )
            == 0
        )


def test_dated_extents_may_differ_but_grid_origins_may_not(tmp_path):
    from dataclasses import replace

    original = read_scheme(metadata())
    wider = replace(original, extent=(0, 0, 4096, 2048))
    assert original.compatible(wider)
    assert not original.compatible(replace(wider, x=-1))
    clock = Clock()

    def transport(url):
        return Response(url, metadata() if url.endswith("?f=json") else JPEG, ())

    with pytest.raises(policy.SnapshotRefusal, match="scheme_changed"):
        acquire(
            tmp_path,
            "1995-02",
            box(1, 1800, 2, 1801),
            "a" * 64,
            transport,
            policy.Pacer(clock.time, clock.sleep),
            lambda: STAMP,
            lambda: None,
            levels=(10,),
            expected_scheme=replace(wider, x=-1),
            boundary_receipt=BOUNDARY_RECEIPT,
        )


@given(st.integers(min_value=10, max_value=100))
def test_every_rolling_second_contains_at_most_ten_starts(count):
    clock = Clock()
    pace = policy.Pacer(clock.time, clock.sleep)
    starts = []
    for _ in range(count):
        pace.wait()
        starts.append(clock.now)
    for start in starts:
        assert sum(start <= value < start + 1.0 for value in starts) <= 10


def test_only_declared_levels_through_the_cap_are_required(tmp_path):
    meta = json.loads(metadata())
    meta["tileInfo"]["lods"] = [meta["tileInfo"]["lods"][-1]]
    body = json.dumps(meta).encode()
    scheme = read_scheme(body)
    assert scheme.levels == (10,)
    clock = Clock()
    calls = []

    def transport(url):
        calls.append(url)
        return Response(url, body if url.endswith("?f=json") else JPEG, ())

    manifests = acquire(
        tmp_path,
        "1995-02",
        box(1, 1800, 2, 1801),
        "a" * 64,
        transport,
        policy.Pacer(clock.time, clock.sleep),
        lambda: STAMP,
        lambda: None,
        boundary_receipt=BOUNDARY_RECEIPT,
    )
    assert len(manifests) == 1 and len(calls) == 2


def test_ionice_failure_is_blocking_and_priority_children_receive_no_keys(monkeypatch):
    import subprocess

    def failure():
        raise OSError("invented priority failure")

    with pytest.raises(policy.SnapshotRefusal, match="priority"):
        policy.lower_priority(lambda: None, failure)
    monkeypatch.setenv("ESRI_API_KEY", "invented-priority-canary")
    calls = []

    def child(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout=b"idle\n", stderr=b"")

    with patch("subprocess.run", child):
        policy._ionice()
    assert len(calls) == 2
    assert all(
        call[1]["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C"} for call in calls
    )
    assert "invented-priority-canary" not in repr(calls)


def rewrite_sidecar(directory, identity, transform):
    """Keep envelope hashes consistent, so tests reach semantic lineage checks."""
    from eii_custodian.publicdata.gis.snapshot_archive import (
        canonical,
        digest,
        read_checked,
    )

    snap = read_checked(directory, identity)
    side = dict(snap.sidecar)
    transform(side)
    snap.receipt_path.write_bytes(canonical(side))
    index = directory / "index" / (identity + ".json")
    row = json.loads(index.read_bytes())
    row["receipt_sha256"] = digest(snap.receipt_path.read_bytes())
    index.write_bytes(canonical(row))


def small_acquisition(root, transport=None):
    clock = Clock()

    def default(url):
        return Response(url, metadata() if url.endswith("?f=json") else JPEG, ())

    return acquire(
        root,
        "1995-02",
        box(1, 1800, 2, 1801),
        "a" * 64,
        transport or default,
        policy.Pacer(clock.time, clock.sleep),
        lambda: STAMP,
        lambda: None,
        levels=(10,),
        boundary_receipt=BOUNDARY_RECEIPT,
    )


@pytest.mark.parametrize(
    "field",
    [
        "publisher",
        "url",
        "licence_basis",
        "decision_record",
        "terms_words",
        "terms_read_on",
        "generator_version",
        "retrieved_utc",
        "sha256",
        "bytes",
        "licence_id",
        "kind",
        "imagery_date",
        "source_id",
        "key",
    ],
)
@pytest.mark.parametrize("kind", ["metadata", "boundary", "completion"])
@pytest.mark.parametrize("stage", ["resume", "selection"])
def test_incomplete_public_receipt_refuses_semantically(tmp_path, field, kind, stage):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (manifest,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    snap = read_checked(level / "completion", manifest)
    enumeration = json.loads(snap.body)["enumeration"]
    folder, identity = (
        (level / "completion", manifest)
        if kind == "completion"
        else (level / "inputs" / kind, enumeration["inputs"][kind])
    )
    rewrite_sidecar(folder, identity, lambda side: side.pop(field, None))
    with pytest.raises(policy.SnapshotRefusal, match=r"receipt|integrity"):
        if stage == "resume":
            small_acquisition(tmp_path)
        else:
            verify_selection(level, manifest)


@pytest.mark.parametrize("kind", ["metadata", "boundary", "completion"])
def test_foreign_public_receipt_refuses(tmp_path, kind):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (manifest,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    enumeration = json.loads(read_checked(level / "completion", manifest).body)[
        "enumeration"
    ]
    folder, identity = (
        (level / "completion", manifest)
        if kind == "completion"
        else (level / "inputs" / kind, enumeration["inputs"][kind])
    )
    rewrite_sidecar(
        folder, identity, lambda side: side.update(url="https://foreign.invalid/")
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"receipt|integrity"):
        verify_selection(level, manifest)


@pytest.mark.parametrize("stage", ["resume", "selection"])
def test_unknown_metadata_receipt_field_is_refused(tmp_path, stage):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (manifest,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    enumeration = json.loads(read_checked(level / "completion", manifest).body)[
        "enumeration"
    ]
    rewrite_sidecar(
        level / "inputs/metadata",
        enumeration["inputs"]["metadata"],
        lambda side: side.update(unregistered="invented"),
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"^receipt_fields$"):
        if stage == "resume":
            small_acquisition(tmp_path)
        else:
            verify_selection(level, manifest)


@pytest.mark.parametrize("stage", ["resume", "selection"])
def test_shard_publisher_is_required_at_each_read_stage(tmp_path, stage):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (manifest,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", manifest).body)
    rewrite_sidecar(
        level / "shards/000000",
        completion["shards"][0]["identity"],
        lambda side: side.pop("publisher"),
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"^receipt_fields$"):
        if stage == "resume":
            small_acquisition(tmp_path)
        else:
            verify_selection(level, manifest)


def republish_completion(level, completion):
    """Rehash the envelope so each coverage plant reaches its semantic guard."""
    from eii_custodian.publicdata.gis.snapshot_archive import canonical, digest
    from eii_custodian.publicdata.gis.snapshot_receipt import (
        public_chain,
        publish_public,
    )

    body = canonical(completion)
    identity = digest(body)
    publish_public(
        level / "completion",
        body,
        public_chain("completion", "1995-02", STAMP),
        identity,
    )
    return identity


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("gap_key", "gap_enumeration_integrity"),
        ("gap_count", "completion_coverage_integrity"),
        ("gap_reason", "gap_reason_integrity"),
        ("boundary_upstream", "boundary_upstream_integrity"),
    ],
)
def test_coverage_guards_refuse_independently_with_valid_hashes(
    tmp_path, plant, reason
):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    def transport(url):
        return Response(
            url,
            metadata() if url.endswith("?f=json") else b"",
            (),
            evidence={"http_status": 200 if url.endswith("?f=json") else 404},
        )

    (manifest,) = small_acquisition(tmp_path, transport)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", manifest).body)
    if plant in {"gap_key", "gap_reason"}:
        gap = completion["gaps"][0]
        gap.update({"key": [10, 9, 9]} if plant == "gap_key" else {"reason": "bogus"})
        # Mirror the changed gap in completion: only the shard semantic guard
        # can refuse it, not the completion/shard coverage equality check.
        rewrite_sidecar(
            level / "shards/000000",
            completion["shards"][0]["identity"],
            lambda side: side.update(gaps=deepcopy(completion["gaps"])),
        )
    elif plant == "gap_count":
        completion["gap_count"] += 1
    else:
        rewrite_sidecar(
            level / "inputs/boundary",
            completion["enumeration"]["inputs"]["boundary"],
            lambda side: side.update(upstream_sha256="f" * 64),
        )
    manifest = republish_completion(level, completion)
    with pytest.raises(policy.SnapshotRefusal, match="^" + reason + "$"):
        verify_selection(level, manifest)


@pytest.mark.parametrize(
    "failure",
    [
        "404",
        "410",
        "empty",
        "non-jpeg",
        "dimensions",
        "no-scan",
        "no-quantization",
        "invalid-scan",
        "sos-no-data",
        "truncated-scan-baseline-10pct",
        "truncated-scan-baseline-90pct",
        "truncated-scan-progressive-50pct",
    ],
)
def test_persistent_tile_gap_completes_and_resume_never_refetches(tmp_path, failure):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked
    from eii_custodian.publicdata.gis.snapshot_release import assemble
    from eii_product.api.gis_imagery import ReleasedImagery, imagery_router

    invalid_bodies = {
        "no-scan": NO_SCAN_JPEG,
        "no-quantization": NO_QUANTIZATION_JPEG,
        "invalid-scan": INVALID_SCAN_JPEG,
        "sos-no-data": truncated_noise_jpeg(0),
        "truncated-scan-baseline-10pct": truncated_noise_jpeg(10),
        "truncated-scan-baseline-90pct": truncated_noise_jpeg(90),
        "truncated-scan-progressive-50pct": truncated_noise_jpeg(50, progressive=True),
    }
    if failure in invalid_bodies:
        # Independent decoder proof: not merely our own marker validation.
        if failure == "no-quantization":
            # Opening succeeds: only a forced pixel read detects this defect.
            with MemoryFile(invalid_bodies[failure], filename="invented.jpg") as memory:
                with memory.open() as dataset:
                    with pytest.raises(RasterioIOError):
                        dataset.read()
        else:
            with (
                Env(GDAL_ERROR_ON_LIBJPEG_WARNING="TRUE"),
                pytest.raises(RasterioIOError),
            ):
                with MemoryFile(
                    invalid_bodies[failure], filename="invented.jpg"
                ) as memory:
                    with memory.open() as dataset:
                        dataset.read()
    calls = []

    def transport(url):
        calls.append(url)
        if url.endswith("?f=json"):
            return Response(url, metadata(), ())
        body = {
            **invalid_bodies,
            "empty": b"",
            "non-jpeg": b"not-a-jpeg",
            "dimensions": JPEG.replace(b"\x02\x00\x02\x00", b"\x01\x00\x02\x00"),
        }.get(failure, b"")
        return Response(
            url,
            body,
            (),
            evidence={"http_status": int(failure) if failure.isdigit() else 200},
        )

    (manifest,) = small_acquisition(tmp_path, transport)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", manifest).body)
    (gap,) = completion["gaps"]
    assert gap["key"] == [10, 0, 0]
    assert gap["attempts"] == 1
    if failure in {"404", "410"}:
        assert gap["http_status"] == int(failure)
    else:
        assert gap["http_status"] == 200
    if failure in invalid_bodies:
        assert gap["reason"] == "tile_format_or_gap"
    selection = verify_selection(level, manifest)
    assert tuple(selection.iter_tiles()) == ()
    assert selection.shards[0].sidecar["members"] == []
    assert selection.shards[0].sidecar["gaps"] == [gap]
    tile_calls = len(calls)
    assert small_acquisition(tmp_path, transport) == (manifest,)
    assert len(calls) == tile_calls + 1  # metadata only, recorded gap is immutable
    output = tmp_path / "release"
    identity = assemble((selection,), output)
    reader = ReleasedImagery(output, identity)
    assert reader.tile("1995-02", 10, 0, 0) is None
    assert reader.coverage["gaps"][0]["key"] == [10, 0, 0]
    credit_route = next(
        route.endpoint
        for route in imagery_router(reader).routes
        if route.path.endswith("/credit")
    )
    assert credit_route()["coverage"] == reader.coverage
    shard = selection.shards[0]
    shard_folder = level / "shards/000000"
    pointer = json.loads((shard_folder / "selection.json").read_bytes())["identity"]
    rewrite_sidecar(
        shard_folder, pointer, lambda side: side["gaps"][0].update(key=[10, 9, 9])
    )
    with pytest.raises(policy.SnapshotRefusal, match="integrity"):
        verify_selection(level, manifest)
    assert shard.path.is_file()


@pytest.mark.parametrize("failure", [429, 500, 502, 503, 504, "unreachable", 403])
def test_transient_tile_failure_stops_without_shard_and_retries_same_key(
    tmp_path, failure
):
    calls = []

    def transport(url):
        calls.append(url)
        if url.endswith("?f=json"):
            return Response(url, metadata(), ())
        if failure == "unreachable":
            raise TransportFault("unreachable", url)
        return Response(url, b"", (), evidence={"http_status": failure})

    with pytest.raises(policy.SnapshotRefusal, match=r"^request_failed$"):
        small_acquisition(tmp_path, transport)
    key = policy.tile_url("1995-02", 10, 0, 0)
    assert calls[1:] == [key] * (1 if failure == 403 else 4)
    level = tmp_path / "1995-02/level-10"
    assert not (level / "completion").exists()
    assert not list((level / "shards").rglob("*.tar"))
    assert not list((level / "shards").rglob("selection.json"))
    resumed = []

    def restored(url):
        resumed.append(url)
        return Response(url, metadata() if url.endswith("?f=json") else JPEG, ())

    (manifest,) = small_acquisition(tmp_path, restored)
    assert resumed == [policy.service_url("1995-02") + "?f=json", key]
    assert tuple(verify_selection(level, manifest).iter_tiles()) == (
        ("1995-02", 10, 0, 0, JPEG),
    )


@pytest.mark.parametrize(
    "status,body,reason",
    [
        (404, b"", "request_failed"),
        (410, b"", "request_failed"),
        (200, b"", "response_bytes_or_gap"),
        (200, b"not-a-jpeg", "tile_format_or_gap"),
    ],
    ids=["404", "410", "empty-200", "invalid-200"],
)
@pytest.mark.parametrize("resume_gap", [True, False], ids=["fresh-404", "intact"])
def test_mixed_retry_gap_stops_before_publication_and_resumes(
    tmp_path, status, body, reason, resume_gap
):
    from eii_custodian.publicdata.gis.snapshot_runner import TileFailure

    calls = []

    def transport(url):
        if url.endswith("?f=json"):
            return Response(url, metadata(), ())
        calls.append(url)
        return Response(
            url,
            b"" if len(calls) == 1 else body,
            (),
            evidence={"http_status": 503 if len(calls) == 1 else status},
        )

    with pytest.raises(TileFailure, match="^" + reason + "$") as caught:
        small_acquisition(tmp_path, transport)
    assert caught.value.attempts == 2
    assert caught.value.status == status
    key = policy.tile_url("1995-02", 10, 0, 0)
    assert calls == [key, key]
    level = tmp_path / "1995-02/level-10"
    shard = level / "shards/000000"
    assert not list(shard.rglob("*.tar"))
    assert not list(shard.rglob("*.json"))  # no receipt, index or selection
    assert not list(shard.glob(".staging-*"))
    assert not (level / "completion").exists()
    resumed = []

    def restored(url):
        resumed.append(url)
        if url.endswith("?f=json"):
            return Response(url, metadata(), ())
        return Response(
            url,
            b"" if resume_gap else JPEG,
            (),
            evidence={"http_status": 404 if resume_gap else 200},
        )

    (manifest,) = small_acquisition(tmp_path, restored)
    assert resumed == [policy.service_url("1995-02") + "?f=json", key]
    selection = verify_selection(level, manifest)
    if resume_gap:
        # L-1303: a fresh first-attempt 404 is a recorded persistent gap.
        assert selection.gaps == (
            {
                "key": [10, 0, 0],
                "http_status": 404,
                "reason": "request_failed",
                "attempts": 1,
                "retrieved_utc": STAMP,
            },
        )
        assert tuple(selection.iter_tiles()) == ()
    else:
        assert selection.gaps == ()
        assert tuple(selection.iter_tiles()) == (("1995-02", 10, 0, 0, JPEG),)
    assert small_acquisition(tmp_path, restored) == (manifest,)
    assert resumed[-1] == policy.service_url("1995-02") + "?f=json"
    assert resumed.count(key) == 1  # verified selected gaps/tiles are skipped


@pytest.mark.parametrize(
    "reason,status,attempts",
    [
        ("request_failed", 404, 2),
        ("request_failed", 410, 2),
        ("request_failed", 503, 1),
        ("response_bytes_or_gap", 200, 2),
        ("tile_format_or_gap", 200, 2),
        ("tile_dimensions_refused", 200, 2),
        ("tile_format_or_gap", 404, 1),
    ],
)
def test_archive_gap_eligibility_checked_before_immutable_publication(
    tmp_path, reason, status, attempts
):
    archive = Archive(
        tmp_path,
        {
            "boundary_sha256": "a" * 64,
            "metadata_sha256": "b" * 64,
            "date": "1995-02",
            "level": 10,
            "tiles": [[10, 0, 0]],
        },
    )
    gaps = [
        {
            "key": [10, 0, 0],
            "http_status": status,
            "reason": reason,
            "attempts": attempts,
            "retrieved_utc": STAMP,
        }
    ]
    with pytest.raises(policy.SnapshotRefusal, match=r"^gap_reason_integrity$"):
        archive.write_shard_stream(0, (), STAMP, gaps=gaps)
    assert gaps[0]["attempts"] == attempts
    shard = tmp_path / "shards/000000"
    assert not list(shard.rglob("*.tar"))
    assert not list(shard.rglob("*.json"))
    assert not list(shard.glob(".staging-*"))
    archive.write_shard(0, {(10, 0, 0): JPEG}, STAMP)
    assert archive.has_shard(0)


def test_partial_service_extent_keeps_country_and_records_uncovered_geometry(tmp_path):
    from shapely.geometry import shape

    from eii_custodian.publicdata.gis.snapshot_archive import read_checked
    from eii_custodian.publicdata.gis.snapshot_release import assemble
    from eii_product.api.gis_imagery import ReleasedImagery

    meta = json.loads(metadata())
    meta["fullExtent"]["xmax"] = 1.5
    calls = []

    def transport(url):
        calls.append(url)
        return Response(
            url, json.dumps(meta).encode() if url.endswith("?f=json") else JPEG, ()
        )

    (manifest,) = small_acquisition(tmp_path, transport)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", manifest).body)
    uncovered = shape(completion["uncovered"])
    assert uncovered.equals(box(1.5, 1800, 2, 1801))
    assert completion["enumeration"]["tiles"] == [[10, 0, 0]]
    output = tmp_path / "release"
    reader = ReleasedImagery(
        output, assemble((verify_selection(level, manifest),), output)
    )
    assert reader.coverage["uncovered"][0]["geometry"] == completion["uncovered"]

    # A second, wholly outside tile exercises the no-request branch, while
    # retaining the partially covered tile and whole-country enumeration.
    clock = Clock()
    land = MultiPolygon([box(1, 1800, 2, 1801), box(300, 1800, 301, 1801)])
    (manifest,) = acquire(
        tmp_path / "outside",
        "1995-02",
        land,
        "a" * 64,
        transport,
        policy.Pacer(clock.time, clock.sleep),
        lambda: STAMP,
        lambda: None,
        levels=(10,),
        boundary_receipt=BOUNDARY_RECEIPT,
    )
    completion = json.loads(
        read_checked(tmp_path / "outside/1995-02/level-10/completion", manifest).body
    )
    assert completion["enumeration"]["tiles"] == [[10, 0, 0], [10, 0, 1]]
    assert completion["gaps"] == [
        {
            "key": [10, 0, 1],
            "reason": "outside_extent",
            "attempts": 0,
            "http_status": None,
            "retrieved_utc": STAMP,
        }
    ]
    assert [url for url in calls if not url.endswith("?f=json")] == [
        policy.tile_url("1995-02", 10, 0, 0),
        policy.tile_url("1995-02", 10, 0, 0),
    ]


def test_acquire_checks_finished_shard_before_completion_or_any_tile_request(tmp_path):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (manifest,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", manifest).body)
    shard = completion["shards"][0]
    snap = read_checked(level / "shards/000000", shard["identity"])
    snap.path.write_bytes(b"planted completed-shard corruption")

    def metadata_only(url):
        assert url.endswith("?f=json"), "tile requested before verifying finished shard"
        return Response(url, metadata(), ())

    with patch.object(
        Archive, "complete", side_effect=AssertionError("reached completion")
    ):
        with pytest.raises(policy.SnapshotRefusal, match="archive_integrity"):
            small_acquisition(tmp_path, metadata_only)


def test_safe_child_refuses_symlink_whose_target_is_inside_root(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (tmp_path / "link").symlink_to(target, target_is_directory=True)
    with pytest.raises(policy.SnapshotRefusal, match=r"^root_escape$"):
        policy.safe_child(tmp_path, "link/file.json")


def test_ordinary_registry_has_no_unenforced_snapshot_switches():
    from pathlib import Path

    import yaml
    from custodian.tests.repository_root import repository_root

    path = (
        repository_root(Path(__file__))
        / "custodian/publicdata/review/s2_t29_sources.yaml"
    )
    rows = yaml.load(path.read_text(), Loader=yaml.CSafeLoader)["gis_confirmation"]
    assert "snapshot_tiles_allowed" not in rows
    assert "snapshot_contract" not in rows
    assert rows["export_tiles_allowed"] is False


BOUNDARY_CHANGES = [
    ("publisher", "Another invented publisher"),
    ("url", "https://www.data.gov.qa/another-invented-boundary"),
    ("licence_id", "CC0-1.0"),
]


@pytest.mark.parametrize("field,value", BOUNDARY_CHANGES)
def test_cf1_resume_projected_lineage_must_match_original(tmp_path, field, value):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (identity,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    enumeration = json.loads(read_checked(level / "completion", identity).body)[
        "enumeration"
    ]
    rewrite_sidecar(
        level / "inputs/boundary",
        enumeration["inputs"]["boundary"],
        lambda side: side.update({field: value}),
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"^boundary_chain_mismatch$"):
        small_acquisition(tmp_path)


@pytest.mark.parametrize("field,value", BOUNDARY_CHANGES)
@pytest.mark.parametrize("stage", ["resume", "selection"])
def test_cf1_full_release_projected_lineage_must_match_original(
    tmp_path, monkeypatch, capsys, field, value, stage
):
    from eii_custodian.publicdata.gis import snapshot_release as release
    from eii_custodian.publicdata.gis import snapshot_runner as runner
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    root, _, _, complete, _, _ = all_dates_acquisition(tmp_path, monkeypatch)
    original = read_checked(root / "boundary-source", complete["boundary_source"])
    original_receipt = original.receipt_path.read_bytes()
    level = root / "1995-02/level-10"
    enumeration = json.loads(
        read_checked(level / "completion", complete["dates"]["1995-02"]["10"]).body
    )["enumeration"]
    rewrite_sidecar(
        level / "inputs/boundary",
        enumeration["inputs"]["boundary"],
        lambda side: side.update({field: value}),
    )
    if stage == "resume":
        assert runner.run({}) == 1
        assert "boundary_chain_mismatch" in capsys.readouterr().out
    else:
        with pytest.raises(policy.SnapshotRefusal, match=r"^boundary_chain_mismatch$"):
            release.reviewed_inputs({})
    assert original.receipt_path.read_bytes() == original_receipt


@pytest.mark.parametrize("field", ["metadata_sha256", "boundary_sha256"])
@pytest.mark.parametrize("stage", ["resume", "selection"])
def test_cf2_shard_source_hash_must_match_enumeration(tmp_path, field, stage):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (identity,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", identity).body)
    rewrite_sidecar(
        level / "shards/000000",
        completion["shards"][0]["identity"],
        lambda side: side.update({field: "0" * 64}),
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"^shard_lineage_integrity$"):
        if stage == "resume":
            small_acquisition(tmp_path)
        else:
            verify_selection(level, identity)


@pytest.mark.parametrize("stage", ["resume", "selection"])
@pytest.mark.parametrize(
    "field,value", [("shard", 7), ("enumeration_sha256", "0" * 64)]
)
def test_cf2_shard_number_and_enumeration_must_match(tmp_path, stage, field, value):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    (identity,) = small_acquisition(tmp_path)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", identity).body)
    rewrite_sidecar(
        level / "shards/000000",
        completion["shards"][0]["identity"],
        lambda side: side.update({field: value}),
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"^shard_lineage_integrity$"):
        if stage == "resume":
            small_acquisition(tmp_path)
        else:
            verify_selection(level, identity)


@pytest.mark.parametrize("field", ["metadata_sha256", "boundary_sha256"])
def test_cf2_full_release_shard_hash_must_match_and_never_reach_credits(
    tmp_path, monkeypatch, field
):
    from eii_custodian.publicdata.gis import snapshot_release as release
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    root, _, _, complete, _, _ = all_dates_acquisition(tmp_path, monkeypatch)
    level = root / "1995-02/level-10"
    completion = json.loads(
        read_checked(level / "completion", complete["dates"]["1995-02"]["10"]).body
    )
    rewrite_sidecar(
        level / "shards/000000",
        completion["shards"][0]["identity"],
        lambda side: side.update({field: "0" * 64}),
    )
    with pytest.raises(policy.SnapshotRefusal, match=r"^shard_lineage_integrity$"):
        release.reviewed_inputs({})


@pytest.mark.parametrize("stage", ["resume", "selection"])
@pytest.mark.parametrize(
    "reason,status,attempts",
    [("request_failed", status, 1) for status in (200, 503, None)]
    + [("request_failed", 404, attempts) for attempts in (0, 2, 4)]
    + [
        (reason, status, attempts)
        for reason in (
            "response_bytes_or_gap",
            "tile_format_or_gap",
            "tile_dimensions_refused",
        )
        for status, attempts in ((404, 1), (None, 1), (200, 0), (200, 2), (200, 4))
    ],
)
def test_gap_reason_status_and_attempt_integrity(
    tmp_path, stage, reason, status, attempts
):
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    def missing(url):
        return Response(
            url,
            metadata() if url.endswith("?f=json") else b"",
            (),
            evidence={"http_status": 200 if url.endswith("?f=json") else 404},
        )

    (identity,) = small_acquisition(tmp_path, missing)
    level = tmp_path / "1995-02/level-10"
    completion = json.loads(read_checked(level / "completion", identity).body)
    completion["gaps"][0].update(reason=reason, http_status=status, attempts=attempts)
    rewrite_sidecar(
        level / "shards/000000",
        completion["shards"][0]["identity"],
        lambda side: side.update(gaps=deepcopy(completion["gaps"])),
    )
    identity = republish_completion(level, completion)
    with pytest.raises(policy.SnapshotRefusal, match=r"^gap_reason_integrity$"):
        if stage == "resume":
            small_acquisition(tmp_path, missing)
        else:
            verify_selection(level, identity)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "another_invented_boundary"),
        ("key", "another_invented_boundary"),
        *BOUNDARY_CHANGES,
        ("licence_basis", "owner_decision"),
        ("decision_record", "0026"),
        ("upstream_sha256", "f" * 64),
        ("method_version", "invented-union-v2"),
    ],
)
def test_pin_boundary_refuses_changed_chain_under_same_identity(
    tmp_path, monkeypatch, field, value
):
    from eii_custodian.publicdata.gis.snapshot_runner import pin_boundary

    root, _, _, _, body, identity = all_dates_acquisition(tmp_path, monkeypatch)
    # identity above names the all-date manifest; the boundary keeps its own hash.
    from eii_custodian.publicdata.gis.snapshot_archive import digest

    assert identity != digest(body)
    path = root / "national-land.meta.json"
    side = json.loads(path.read_bytes())
    if field == "licence_basis":
        # A valid alternative source chain must pass the owner-decision schema.
        side["decision_record"] = "0026"
    side["fetch_url" if field == "url" else field] = value
    path.write_text(json.dumps(side))
    with pytest.raises(policy.SnapshotRefusal, match=r"^boundary_chain_mismatch$"):
        pin_boundary(root, body, digest(body))


def test_boundary_recheck_time_and_terms_reading_are_not_chain_identity(
    tmp_path, monkeypatch
):
    from eii_custodian.publicdata.gis import snapshot_runner as runner
    from eii_custodian.publicdata.gis.snapshot_archive import digest, read_checked

    root, _, _, complete, body, _ = all_dates_acquisition(tmp_path, monkeypatch)
    before = read_checked(root / "boundary-source", complete["boundary_source"])
    receipt_bytes = before.receipt_path.read_bytes()
    path = root / "national-land.meta.json"
    side = json.loads(path.read_bytes())
    side.update(
        retrieved_utc="2026-11-21T00:00:00Z",
        terms_words="Invented later reading",
        terms_read_on="2026-11-21",
    )
    path.write_text(json.dumps(side))
    assert runner.pin_boundary(root, body, digest(body)) == complete["boundary_source"]
    assert runner.run({}) == 0
    assert before.receipt_path.read_bytes() == receipt_bytes


def test_selection_rechecks_projected_upstream_after_level_verification(
    tmp_path, monkeypatch
):
    from eii_custodian.publicdata.gis import snapshot_release as release
    from eii_custodian.publicdata.gis.snapshot_archive import read_checked

    root, selections, _, complete, _, _ = all_dates_acquisition(tmp_path, monkeypatch)
    level = root / "1995-02/level-00"
    completion = json.loads(
        read_checked(level / "completion", complete["dates"]["1995-02"]["0"]).body
    )
    rewrite_sidecar(
        level / "inputs/boundary",
        completion["enumeration"]["inputs"]["boundary"],
        lambda side: side.update(upstream_sha256="f" * 64),
    )
    # Isolate the release boundary's own recheck from verify_selection's earlier
    # transitive upstream check, with the already-verified level as its input.
    with patch.object(
        release, "verify_selection", return_value=selections[0]
    ) as verified:
        with pytest.raises(
            policy.SnapshotRefusal, match=r"^release_selection_identity$"
        ):
            release.reviewed_inputs({})
    assert verified.call_count == 1
