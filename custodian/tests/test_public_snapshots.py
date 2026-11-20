"""Invented snapshot history in pytest's temporary cache; no source connections."""

import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex


def test_existing_snapshot_survives_refetch_and_failed_publication(tmp_path):
    body = b"syn-invented-body"
    digest = sha256_hex(body)
    old = {
        "source_id": "syn_source",
        "key": "syn_source",
        "sha256": digest,
        "bytes": len(body),
        "retrieved_utc": "2024-01-31T00:00:00Z",
    }
    commit_pair(tmp_path, digest, "json", body, old)
    original = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    new = dict(old, retrieved_utc="2024-02-29T00:00:00Z")
    commit_pair(tmp_path, digest, "json", body, new)
    assert all(p.read_bytes() == data for p, data in original.items())


def test_snapshot_path_and_no_clobber(tmp_path):
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError, publish_snapshot

    body = b"syn-older"
    side = {
        "source_id": "syn_source",
        "key": "syn_source",
        "retrieved_utc": "2024-01-31T00:00:00Z",
    }
    ref = publish_snapshot(tmp_path, "json", body, side)
    assert "2024-01-31" in ref.path.parts
    assert ref.path.stem == sha256_hex(body)
    ref.path.write_bytes(b"syn-tamper")
    with pytest.raises(
        SnapshotError, match=r"snapshot_hash_mismatch|snapshot_conflict"
    ):
        publish_snapshot(tmp_path, "json", body, side)


def test_unchanged_bytes_add_only_check(tmp_path):
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot

    old = publish_snapshot(
        tmp_path,
        "json",
        b"syn-older",
        {
            "source_id": "syn_source",
            "key": "syn_source",
            "retrieved_utc": "2024-01-31T00:00:00Z",
        },
    )
    same = publish_snapshot(
        tmp_path,
        "json",
        b"syn-older",
        {
            "source_id": "syn_source",
            "key": "syn_source",
            "retrieved_utc": "2024-02-29T00:00:00Z",
        },
    )
    newer = publish_snapshot(
        tmp_path,
        "json",
        b"syn-newer",
        {
            "source_id": "syn_source",
            "key": "syn_source",
            "retrieved_utc": "2024-03-31T00:00:00Z",
        },
    )
    assert old.path == same.path
    assert newer.path != old.path
    assert read_snapshot(tmp_path, old.sha256).body == b"syn-older"
    assert len(list((tmp_path / "checks").glob("*.json"))) == 3


@pytest.mark.parametrize("plant", ["body", "receipt", "date", "outside", "missing"])
def test_index_and_every_read_verify(tmp_path, plant):
    from eii_custodian.publicdata.fetch.snapshots import (
        SnapshotError,
        publish_snapshot,
        read_snapshot,
    )

    ref = publish_snapshot(
        tmp_path,
        "json",
        b"syn-body",
        {
            "source_id": "syn_source",
            "key": "syn_source",
            "retrieved_utc": "2024-01-31T00:00:00Z",
        },
    )
    if plant == "body":
        ref.path.write_bytes(b"syn-tamper")
    elif plant == "missing":
        ref.path.unlink()
    else:
        index = tmp_path / "index" / (ref.sha256 + ".json")
        row = json.loads(index.read_text())
        if plant == "receipt":
            row["bytes"] = 999
        elif plant == "date":
            row["retrieved_utc"] = ""
        else:
            row["path"] = "../syn-outside.json"
        index.write_text(json.dumps(row))
    with pytest.raises(SnapshotError):
        read_snapshot(tmp_path, ref.sha256)


@pytest.mark.parametrize("reader", ["review", "frame", "series", "method"])
@pytest.mark.parametrize("tamper", [False, True])
def test_existing_reader_older_of_two_and_tamper(tmp_path, reader, tamper):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.receipts import sidecar_for
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    entry = replace(load_registry()[0], key="syn_source")
    old = b"[]"
    digest = sha256_hex(old)
    for body, stamp in (
        (old, "2024-01-31T00:00:00Z"),
        (b'[{"syn":1}]', "2024-02-29T00:00:00Z"),
    ):
        side = sidecar_for(
            entry,
            digest=sha256_hex(body),
            nbytes=len(body),
            fetch_url=entry.url,
            fetch_host=entry.fetch_host,
            retrieved_utc=stamp,
            publisher=entry.publisher,
            source_modified="",
            row_count=0,
            terms_sha256="",
        )
        ref = publish_snapshot(tmp_path / entry.key, entry.extension, body, side)
        if body == old:
            old_path = ref.path
    if tamper:
        old_path.write_bytes(b"syn-tamper")

    def read():
        if reader == "review":
            from eii_custodian.publicdata.review.cache_fixture import read_cached

            return read_cached(tmp_path, entry, digest=digest).body
        if reader == "frame":
            from eii_custodian.publicdata.frame.build import read_cached

            return read_cached(tmp_path, entry, digest=digest)[0]
        if reader == "series":
            from eii_custodian.publicdata.series.parse import selected_source

            return selected_source(tmp_path, entry, digest)[0]
        import custodian.data_tests.cache as module
        from custodian.data_tests.cache import cached

        original = module.load_registry
        module.load_registry = lambda: (entry,)
        try:
            return cached(tmp_path, entry.key, digest)[0]
        finally:
            module.load_registry = original

    if tamper:
        with pytest.raises(ValueError, match=r"snapshot_|hash"):
            read()
    else:
        assert read() in ([], b"[]")


def test_trade_outputs_metadata_and_manifest_are_dated(tmp_path):
    from dataclasses import replace

    from custodian.tests.fixtures.gravity.invented import configuration, entry
    from custodian.tests.test_gravity_fetch import build

    outcome = build(
        tmp_path, source=replace(entry(), terms_url=configuration()["page"])
    )
    assert outcome.failure is None
    directory = tmp_path / "cepii_gravity"
    assert list((directory / "index").glob("*.json"))
    assert list((directory / "2026-11-16").glob("*.zip"))
    assert list((directory / "metadata" / "index").glob("*.json"))
    assert list((directory / "terms" / "index").glob("*.json"))


@pytest.fixture
def comtrade_archive(tmp_path):
    from custodian.tests.fixtures.comtrade.invented import invented_entry
    from custodian.tests.test_comtrade import _clock, _ok, _sleep

    from eii_custodian.publicdata.comtrade.fetch import fetch_source
    from eii_custodian.publicdata.fetch.transport import SlotSecrets

    result = fetch_source(
        invented_entry(),
        tmp_path,
        _clock,
        _sleep,
        _ok,
        SlotSecrets("", ""),
        api_class="public",
    )
    assert result.failure is None
    directory = tmp_path / "un_comtrade"
    return directory


def test_comtrade_coverage_archived(comtrade_archive):
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    coverage = (comtrade_archive / "coverage.json").read_bytes()
    assert (
        read_snapshot(comtrade_archive / "coverage", sha256_hex(coverage)).body
        == coverage
    )


@pytest.mark.parametrize("name", ["state.json", "state.lock"])
def test_comtrade_state_operational(comtrade_archive, name):
    assert not list(comtrade_archive.glob("*/" + name))
    for index in comtrade_archive.rglob("index/*.json"):
        row = json.loads(index.read_text())
        assert not any(name in part for part in index.parts)
        assert name not in str(row)


def test_fetched_terms_bytes_are_archived(tmp_path):
    from dataclasses import replace

    from custodian.tests.test_publicdata_fetch import _citation_entry, _clock, _sleep

    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.fetch.transport import Response

    entry = replace(
        _citation_entry(),
        skip_reason="syn-unconfirmed",
        terms_url="https://www.data.gov.qa/syn-terms",
    )
    body = b"<p>syn invented terms</p>"
    outcome = run_build(
        (entry,), lambda url: Response(url, body, ()), tmp_path, _clock, _sleep
    )
    assert outcome.failure is None
    assert list((tmp_path / entry.key / "terms" / "index").glob("*.json"))


@pytest.mark.parametrize("tamper", [False, True])
def test_place_receipt_uses_reviewed_older_snapshot(tmp_path, tamper):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.places.integrate import _receipt_of
    from eii_custodian.publicdata.review.cache_fixture import (
        select_fixture,
        write_cached,
    )

    entry = replace(load_registry()[0], key="syn_place", extension="parquet")
    older = write_cached(tmp_path, entry, b"syn-older")
    write_cached(tmp_path, entry, b"syn-newer", select=False)
    select_fixture(tmp_path, entry.key, sha256_hex(b"syn-older"))
    if tamper:
        older.write_bytes(b"syn-tamper")
        assert _receipt_of(tmp_path, entry) is None
    else:
        selected = _receipt_of(tmp_path, entry)
        assert selected is not None
        assert selected[0].read_bytes() == b"syn-older"


def test_road_older_pin_and_tamper(tmp_path):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.places.area_files import ROAD_KEY, _load_road
    from eii_custodian.publicdata.places.areas import AreaError
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    entry = replace(load_registry()[0], key=ROAD_KEY, extension="pbf")
    older = write_cached(tmp_path, entry, b"syn-road")
    write_cached(tmp_path, entry, b"syn-new-road", select=False)
    assert _load_road(tmp_path)[0] == b"syn-road"
    older.write_bytes(b"syn-tamper")
    with pytest.raises(AreaError):
        _load_road(tmp_path)


def test_snapshot_write_failure_has_source_and_no_upstream_payload(
    tmp_path, monkeypatch
):
    import traceback

    from eii_custodian.publicdata.fetch.snapshots import SnapshotError, publish_snapshot

    def fail_write(*args, **kwargs):
        raise OSError("syn-private-diagnostic")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(SnapshotError) as caught:
        publish_snapshot(
            tmp_path,
            "json",
            b"syn-body",
            {
                "source_id": "syn_source",
                "key": "syn_source",
                "retrieved_utc": "2024-01-31T00:00:00Z",
            },
        )
    assert str(caught.value) == "syn_source: snapshot_write_failed"
    assert "syn-private-diagnostic" not in "".join(
        traceback.format_exception(caught.value)
    )


def test_failed_compatibility_publication_records_no_successful_check(
    tmp_path, monkeypatch
):
    import eii_custodian.publicdata.fetch.bounded as bounded

    body = b"syn-body"
    digest = sha256_hex(body)
    original = bounded.os.link

    def fail_alias(source, target, *args, **kwargs):
        if Path(target).parent == tmp_path:
            raise OSError("syn-private-diagnostic")
        return original(source, target, *args, **kwargs)

    monkeypatch.setattr(bounded.os, "link", fail_alias)
    with pytest.raises((ValueError, OSError)):
        commit_pair(
            tmp_path,
            digest,
            "json",
            body,
            {
                "source_id": "syn_source",
                "key": "syn_source",
                "retrieved_utc": "2024-01-31T00:00:00Z",
            },
        )
    assert not list((tmp_path / "checks").glob("*.json"))


def test_comtrade_equal_body_reuses_object_across_receipts(comtrade_archive):
    from custodian.tests.fixtures.comtrade.invented import (
        invented_entry,
        invented_policy,
        trusted_source,
    )

    from eii_custodian.publicdata.comtrade.assemble import verify_child
    from eii_custodian.publicdata.comtrade.fetch import _store_child
    from eii_custodian.publicdata.comtrade.partition import initial_partitions
    from eii_custodian.publicdata.comtrade.policy import (
        policy_sha256,
        selection_sha256,
    )
    from eii_custodian.publicdata.comtrade.state import fresh
    from eii_custodian.publicdata.fetch.snapshots import checked_times, read_snapshot

    policy = invented_policy()
    partition = initial_partitions(policy)[0]
    manifest = json.loads((comtrade_archive / "manifest.json").read_text())
    child = next(row for row in manifest["children"] if row["key"] == partition.key())
    older_id = child["receipt_sha256"]
    older = read_snapshot(comtrade_archive, older_id)
    before = {p: p.read_bytes() for p in comtrade_archive.rglob("*") if p.is_file()}
    checks_before = len(checked_times(comtrade_archive))
    stamp = "2026-11-17T08:00:00Z"
    ledger = fresh(
        policy_sha256(policy), selection_sha256(policy), (partition.key(),), stamp[:10]
    )
    newer_id = _store_child(
        invented_entry(policy),
        comtrade_archive,
        policy,
        partition,
        older.body,
        1,
        policy.public_record_limit,
        ledger,
        "public",
        stamp,
    )
    assert newer_id != older_id
    newer = read_snapshot(comtrade_archive, newer_id)
    assert newer.path == older.path
    assert list(comtrade_archive.glob(f"????-??-??/{older.sha256}.json")) == [
        older.path
    ]
    assert (comtrade_archive / f"{newer_id}.json").samefile(older.path)
    assert len(checked_times(comtrade_archive)) == checks_before + 1
    assert all(path.read_bytes() == body for path, body in before.items())
    for identity, expected_stamp in (
        (older_id, older.sidecar["retrieved_utc"]),
        (newer_id, stamp),
    ):
        snapshot = read_snapshot(comtrade_archive, identity)
        assert snapshot.body == older.body
        assert snapshot.sidecar["retrieved_utc"] == expected_stamp
        verified = verify_child(
            comtrade_archive,
            policy,
            child_key=partition.key(),
            receipt_sha256=identity,
            **trusted_source(policy),
        )
        assert verified.retrieved_utc == expected_stamp
        assert verified.body_sha256 == older.sha256
        assert verified.count == 1


@pytest.mark.parametrize("phase", ["child", "manifest", "coverage"])
def test_comtrade_snapshot_storage_failure_is_safe(tmp_path, monkeypatch, phase):
    from custodian.tests.fixtures.comtrade.invented import invented_entry
    from custodian.tests.test_comtrade import _clock, _ok, _sleep

    from eii_custodian.publicdata.comtrade.fetch import fetch_source
    from eii_custodian.publicdata.fetch import snapshots
    from eii_custodian.publicdata.fetch.transport import SlotSecrets

    directory = tmp_path / "un_comtrade"
    target = (
        directory
        if phase == "child"
        else directory / ("manifests" if phase == "manifest" else "coverage")
    )
    original = snapshots.publish_file
    entered = []

    def fail_archive(folder, *args, **kwargs):
        if folder == target:
            entered.append(folder)
            assert (directory / "state.json").is_file()
            raise snapshots.SnapshotError("snapshot_conflict syn-upstream-diagnostic")
        return original(folder, *args, **kwargs)

    monkeypatch.setattr(snapshots, "publish_file", fail_archive)
    result = fetch_source(
        invented_entry(),
        tmp_path,
        _clock,
        _sleep,
        _ok,
        SlotSecrets("", ""),
        api_class="public",
    )
    assert entered == [target]
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    assert "un_comtrade" in str(result.failure)
    assert "syn-upstream-diagnostic" not in repr(result)
    assert "snapshot_conflict" not in repr(result)
    assert result.digest == ""
    if phase != "coverage":
        assert result.requested_cells == 8
    assert not (directory / "state.lock").exists()


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("key", "syn-other", "selected receipt mismatch"),
        ("publisher", "", "incomplete receipt"),
    ],
)
def test_method_selected_receipt_integrity_reason(
    tmp_path, monkeypatch, field, value, reason
):
    from dataclasses import replace

    import custodian.data_tests.cache as module

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    entry = replace(load_registry()[0], key="syn_source", source_id="syn_source")
    monkeypatch.setattr(module, "load_registry", lambda: (entry,))
    path = write_cached(tmp_path, entry, b"[]")
    directory = tmp_path / entry.key
    index = directory / "index" / f"{path.stem}.json"
    row = json.loads(index.read_text())
    receipt = directory / row["receipt"]
    side = json.loads(receipt.read_text())
    side[field] = row[field] = value
    receipt.write_text(json.dumps(side))
    row["receipt_sha256"] = sha256_hex(receipt.read_bytes())
    index.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="^" + reason + "$"):
        module.cached(tmp_path, entry.key, path.stem)


@pytest.mark.parametrize("kind", ["baci", "gravity", "atlas", "comtrade"])
@pytest.mark.parametrize("tamper", [False, True], ids=["older", "tamper"])
def test_trade_reader_older_of_two_and_tamper(tmp_path, kind, tamper):
    import re
    from dataclasses import replace
    from decimal import Decimal
    from importlib import import_module

    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot
    from eii_custodian.publicdata.fetch.transport import SlotSecrets

    stamps = ("2026-11-16T08:00:00Z", "2026-11-17T08:00:00Z")
    if kind == "comtrade":
        from custodian.tests.fixtures.comtrade.invented import (
            invented_entry,
            invented_policy,
            trusted_source,
        )
        from custodian.tests.test_comtrade import _ok, _sleep

        from eii_custodian.publicdata.comtrade.assemble import assemble
        from eii_custodian.publicdata.comtrade.fetch import fetch_source
        from eii_custodian.publicdata.comtrade.policy import SafeRefusal

        policy = invented_policy()
        entry = invented_entry(policy)
        directory = tmp_path / entry.key / "manifests"
        error = SafeRefusal
        reason = "un_comtrade https://invented.example/cached manifest_hash endpoint=assemble"

        def read(digest):
            return assemble(
                tmp_path,
                entry.key,
                policy,
                manifest_sha256=digest,
                **trusted_source(policy),
            )

        def build_version(index):
            state = tmp_path / entry.key / "state.json"
            if index:
                state.unlink()  # Begin another run; archived snapshots stay untouched.

            def supplied(request):
                response = _ok(request)
                return replace(
                    response,
                    body=response.body.replace(b"1.25", b"2.50")
                    if index
                    else response.body,
                )

            result = fetch_source(
                entry,
                tmp_path,
                lambda: stamps[index],
                _sleep,
                supplied,
                SlotSecrets("", ""),
                api_class="public",
            )
            assert result.failure is None
            return result.digest

    else:
        fixture = import_module(f"custodian.tests.fixtures.{kind}.invented")
        config_module = import_module(f"eii_custodian.publicdata.{kind}.config")
        contracts = import_module(f"eii_custodian.publicdata.{kind}.contracts")
        entry = fixture.entry()
        directory = tmp_path / entry.key
        error = getattr(config_module, kind.title() + "Error")
        reason = "manifest_hash"

        def read(digest):
            return contracts.read_selected(tmp_path, digest)

        def build_version(index):
            config = fixture.configuration()
            config["source_version"] = ("syn-older-release", "syn-newer-release")[index]
            stream_key = "stream_transport" if kind == "baci" else kind + "_stream"
            result = run_build(
                [entry],
                fixture.metadata,
                tmp_path,
                lambda: stamps[index],
                lambda _: None,
                **{
                    stream_key: fixture.stream,
                    kind + "_config": config_module.Config.from_mapping(config),
                },
            )
            assert result.failure is None
            return result.manifests[entry.source_id]

    older_id = build_version(0)
    older = read(older_id)
    older_body = read_snapshot(directory, older_id)
    newer_id = build_version(1)
    newer = read(newer_id)
    assert older_id != newer_id
    assert older != newer
    newer_body = read_snapshot(directory, newer_id)
    assert older_body.sidecar["retrieved_utc"] == stamps[0]
    assert newer_body.sidecar["retrieved_utc"] == stamps[1]
    assert older_body.body != newer_body.body
    if kind == "comtrade":
        assert older.retrieved_utc == stamps[0]
        assert newer.retrieved_utc == stamps[1]
        assert {(row.measure, row.value) for row in older.rows} == {
            ("trade_value", Decimal("1.25")),
            ("net_weight", None),
        }
        assert {(row.measure, row.value) for row in newer.rows} == {
            ("trade_value", Decimal("2.50")),
            ("net_weight", None),
        }
    else:
        assert older.manifest["config"]["source_version"] == "syn-older-release"
        assert newer.manifest["config"]["source_version"] == "syn-newer-release"
        table = {
            "baci": "trade",
            "gravity": "bilateral",
            "atlas": "country_product_year",
        }[kind]
        assert {row.source_version for row in getattr(older, table)} == {
            "syn-older-release"
        }
        assert {row.source_version for row in getattr(newer, table)} == {
            "syn-newer-release"
        }

    if tamper:
        older_body.path.write_bytes(older_body.body + b" ")
        with pytest.raises(error, match="^" + re.escape(reason) + "$"):
            read(older_id)
        assert read(newer_id) == newer
    else:
        assert read(older_id) == older


def test_pub04_row_describes_s2_t27_dated_archive_and_citation_snapshots():
    document = Path(__file__).resolve().parents[2] / "docs/04_PUBLIC_DATA_PACK.md"
    text = document.read_text().splitlines()
    row = next(line for line in text if line.startswith("| PUB-04 |"))
    assert "retrieval-date" in row
    assert "0045" in row
    assert "0064" in row
    assert "citation_only" in row
    assert "data/public_cache/<source_id>/<sha256>.<ext>" not in row


def test_overture_removal_note_is_separate_and_verbatim():
    document = Path(__file__).resolve().parents[2] / "docs/04_PUBLIC_DATA_PACK.md"
    sentence = (
        "the advisor's reading of 2026-11-16 reports that a release is removed "
        "after at most 60 days; not yet confirmed from a public page"
    )
    cells = [line for line in document.read_text().splitlines() if sentence in line]
    assert len(cells) == 4
    assert all("<br>" + sentence in line for line in cells)


def test_reused_body_date_tamper_is_confined(tmp_path):
    from eii_custodian.publicdata.fetch.snapshots import (
        SnapshotError,
        publish_snapshot,
        read_snapshot,
    )

    body = b"syn-shared-body"
    older_id = sha256_hex(b"syn-older-receipt")
    newer_id = sha256_hex(b"syn-newer-receipt")
    for identity, stamp in (
        (older_id, "2024-01-31T00:00:00Z"),
        (newer_id, "2024-02-29T00:00:00Z"),
    ):
        publish_snapshot(
            tmp_path,
            "json",
            body,
            {"source_id": "syn_source", "key": "syn_source", "retrieved_utc": stamp},
            identity=identity,
        )
    older = read_snapshot(tmp_path, older_id)
    newer = read_snapshot(tmp_path, newer_id)
    assert older.path == newer.path
    assert older.body == newer.body == body
    index = tmp_path / "index" / f"{newer_id}.json"
    row = json.loads(index.read_text())
    assert row["body_date"] == "2024-01-31"
    before = dict(row)
    row["body_date"] = "2024-03-31"
    assert row["path"] == before["path"]
    assert {key for key in row if row[key] != before[key]} == {"body_date"}
    index.write_text(json.dumps(row))
    with pytest.raises(SnapshotError, match=r"^snapshot_path_invalid$"):
        read_snapshot(tmp_path, newer_id)
    assert read_snapshot(tmp_path, older_id).body == body
