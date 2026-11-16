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
