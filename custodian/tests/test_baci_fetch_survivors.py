"""Bounded invented transports, retry schedules and published result contracts."""

import json
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest
from custodian.tests.test_baci import MEMBERS, archive, configuration
from custodian.tests.test_baci_fetch import entry, metadata, stream

from eii_custodian.publicdata.baci import fetch
from eii_custodian.publicdata.baci.config import BaciError, Config
from eii_custodian.publicdata.fetch.transport import Response


@contextmanager
def refusal(message):
    with pytest.raises(BaciError) as caught:
        yield
    assert str(caught.value) == message


def call(
    cache, *, source=None, raw=None, byte=metadata, chunks=stream, sleep=lambda _: None
):
    return fetch.fetch_baci(
        entry() if source is None else source,
        Config.from_mapping(configuration() if raw is None else raw),
        byte,
        chunks,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        sleep,
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("licence_id", "", "licence_basis"),
        ("terms_read_on", "2026-W47-1", "terms_date"),
        ("skip_reason", "invented", "baci_metadata_unconfirmed"),
    ],
)
def test_baci_fetch_entry_messages(tmp_path, field, value, reason):
    with refusal(reason):
        call(tmp_path, source=replace(entry(), **{field: value}))


def test_baci_unconfirmed_message(tmp_path):
    raw = configuration()
    raw["confirmed"] = False
    with refusal("baci_metadata_unconfirmed"):
        call(tmp_path, raw=raw)


def test_baci_stream_missing_message(tmp_path):
    with refusal("stream_transport_missing"):
        call(tmp_path, chunks=None)


def test_baci_metadata_invalid_message(tmp_path):
    def broken(_):
        raise RuntimeError("invented upstream failure")

    with refusal("transport_metadata_invalid"):
        call(tmp_path, byte=broken)


def test_baci_dataset_basis_and_unequal_bounds(tmp_path):
    raw = configuration()
    raw["raw_rows"] = [3, 5]
    source = replace(
        entry(),
        licence_basis="dataset",
        decision_record="",
        row_count_min=3,
        row_count_max=5,
    )
    assert call(tmp_path, source=source, raw=raw).host == "www.data.gov.qa"


def test_baci_metadata_exact_bound(tmp_path):
    raw = configuration()
    payload = b"x" * 4096
    raw["page_sha256"] = sha256(payload).hexdigest()
    assert (
        call(tmp_path, raw=raw, byte=lambda url: Response(url, payload, ())).host
        == "www.data.gov.qa"
    )


@pytest.mark.parametrize("phase", ["metadata", "archive"])
def test_baci_retry_backoff_and_missing_partial(tmp_path, phase):
    attempts = []
    delays = []

    def broken(url):
        attempts.append(url)
        raise OSError("invented connection failure")

    with refusal("network_exhausted"):
        call(
            tmp_path,
            byte=broken if phase == "metadata" else metadata,
            chunks=broken if phase == "archive" else stream,
            sleep=delays.append,
        )
    assert len(attempts) == 4
    assert delays == [1.0, 2.0, 4.0]


def test_baci_declared_bounds_message(tmp_path):
    @contextmanager
    def supplied(url):
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=4097, chunks=iter(())
        )

    with refusal("archive_bytes"):
        call(tmp_path, chunks=supplied)


@pytest.mark.parametrize("size,accepted", [(65536, True), (65537, False)])
def test_baci_exact_chunk_bound(tmp_path, size, accepted):
    raw = configuration()
    raw["archive_bytes"] = [1, 100000]
    raw["members"][0]["bytes"] = [1, 100000]
    members = dict(MEMBERS)
    members["invented-country.csv"] = members["invented-country.csv"].replace(
        "Invented target", "invented " * 9000
    )
    body = archive(members)

    @contextmanager
    def supplied(url):
        yield SimpleNamespace(
            final_url=url,
            hops=(),
            declared_length=len(body),
            chunks=iter([body[:size], body[size:]]),
        )

    if accepted:
        assert call(tmp_path, raw=raw, chunks=supplied).host == "www.data.gov.qa"
    else:
        with refusal("stream_chunk"):
            call(tmp_path, raw=raw, chunks=supplied)


def test_baci_multiple_chunks(tmp_path):
    body = archive()

    @contextmanager
    def supplied(url):
        yield SimpleNamespace(
            final_url=url,
            hops=(),
            declared_length=len(body),
            chunks=iter([body[:100], body[100:]]),
        )

    assert call(tmp_path, chunks=supplied).host == "www.data.gov.qa"


@pytest.mark.parametrize("terms", [False, True])
def test_baci_result_and_manifest(tmp_path, terms):
    raw = configuration()
    source = entry()
    if terms:
        source = replace(source, terms_url=source.url + "-terms")
        raw["reviewed_urls"].append(source.terms_url)
    result = call(tmp_path, raw=raw, source=source)
    expected_hash = sha256(b"Invented publisher page").hexdigest() if terms else ""
    assert result.host == "www.data.gov.qa"
    assert result.terms_sha256 == expected_hash
    assert result.terms_unread == ("" if terms else "terms_to_be_read")
    assert result.retrieved_utc == "2026-11-16T00:00:00Z"
    path = tmp_path / "cepii_baci" / f"{result.digest}.manifest.json"
    payload = path.read_bytes()
    manifest = json.loads(payload)
    assert payload == (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    assert sha256(payload).hexdigest() == result.digest
    assert manifest["terms_unread"] == ("" if terms else "terms_to_be_read")
    assert manifest["receipt"]["terms_sha256"] == (expected_hash if terms else None)
    assert call(tmp_path, raw=raw, source=source) == result


def test_baci_staging_paths_and_cleanup(tmp_path, monkeypatch):
    original = fetch._publish
    names = []
    stages = []

    def checked(path, destination, receipt):
        assert path.parent.parent == tmp_path / "cepii_baci"
        assert path.parent.name.startswith(".stage-")
        names.append(path.name)
        stages.append(path.parent)
        original(path, destination, receipt)

    monkeypatch.setattr(fetch, "_publish", checked)
    call(tmp_path)
    assert names == [
        "archive.zip",
        "pub_baci_trade.jsonl",
        "pub_baci_country.jsonl",
        "pub_baci_product.jsonl",
        "manifest.json",
    ]
    assert not any(stage.exists() for stage in stages)


def test_baci_manifest_explicit_encoding(tmp_path, monkeypatch):
    from pathlib import Path

    original = Path.write_text

    def other_default(path, data, encoding=None, errors=None, newline=None):
        return original(
            path, data, encoding=encoding or "cp037", errors=errors, newline=newline
        )

    monkeypatch.setattr(Path, "write_text", other_default)
    test_baci_result_and_manifest(tmp_path, False)
