"""S2-T51: all bytes, geometry and operating-system observations are invented."""

from __future__ import annotations

import json
from copy import deepcopy
from itertools import pairwise
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import MultiPolygon, box

from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.gis import snapshot_policy as policy
from eii_custodian.publicdata.gis.snapshot_archive import Archive, verify_selection
from eii_custodian.publicdata.gis.snapshot_runner import acquire
from eii_custodian.publicdata.gis.snapshot_scheme import enumerate_tiles, read_scheme

STAMP = "2026-11-20T00:00:00Z"
JPEG = b"\xff\xd8\xff\xc0\x00\x11\x08\x02\x00\x02\x00\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00invented-tile\xff\xd9"


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
    with policy.run_lock(tmp_path):
        with pytest.raises(policy.SnapshotRefusal, match="locked"):
            with policy.run_lock(tmp_path):
                pytest.fail("second run entered")
    with policy.run_lock(tmp_path):
        pass


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
        with pytest.raises(policy.SnapshotRefusal, match="complete"):
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


def test_all_dates_mode_is_separate_complete_and_explicitly_selected(
    tmp_path, monkeypatch
):
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
        return Response(url, metadata() if url.endswith("?f=json") else JPEG, ())

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
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot
    from eii_custodian.publicdata.gis.snapshot_archive import canonical

    incomplete = deepcopy(complete)
    incomplete["dates"]["1995-02"].pop("0")
    incomplete_body = canonical(incomplete)
    incomplete_id = digest(incomplete_body)
    publish_snapshot(
        root / "all-dates",
        "json",
        incomplete_body,
        {
            "source_id": "gis_imagery_history",
            "key": "gis_imagery_history",
            "retrieved_utc": STAMP,
        },
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


def test_interruption_retains_complete_shards_and_resumes_only_the_gap(tmp_path):
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
            raise TransportFault("http", url, 503)
        return Response(url, JPEG, ())

    land = box(1, 1800, 512 * 0.53 * policy.SHARD_TILES + 1, 1801)
    with pytest.raises(policy.SnapshotRefusal, match="request_failed"):
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
    )
    assert len(result) == 1 and len(completed) == 2
    assert completed[-1].endswith("/0/" + str(policy.SHARD_TILES))


def test_changed_bytes_publish_new_objects_without_overwriting_selected_shard(tmp_path):
    archive, _ = fixture_archive(tmp_path)
    original = archive.read_shard(0)
    with pytest.raises(policy.SnapshotRefusal, match="identity_changed"):
        archive.write_shard(
            0, {(10, 0, 0): JPEG.replace(b"invented-tile", b"invented-change")}, STAMP
        )
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
