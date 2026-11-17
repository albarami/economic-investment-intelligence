"""Invented whole-file responses and exact refusal records; no network."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_places_fetch import _entry

from eii_custodian.publicdata.fetch import allowlist
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.places.fetch import (
    FileFailure,
    fetch_place_file,
    is_place_file,
)

URL = "https://files.example/invented.parquet"
FINAL = "https://mirror.example/whole.parquet"
BLOCKED = "https://blocked.example/invented.parquet"


@pytest.fixture(autouse=True)
def invented_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", frozenset({"files.example", "mirror.example"})
    )


def _invented() -> Entry:
    return replace(
        _entry(4, URL),
        publisher="Invented publisher",
        fetch_host="files.example",
        landing_url="https://files.example/catalogue",
    )


def _clock() -> str:
    return "2026-11-15T01:02:03Z"


def _no_sleep(seconds: float) -> None:
    pytest.fail(f"unexpected sleep {seconds}")


def _wrong_type(value: object) -> Any:
    return value


def _failure(
    actual: FileFailure | None,
    code: int,
    url: str,
    check: str,
    expected: str,
    observed: str,
) -> None:
    assert actual is not None
    assert asdict(actual) == {
        "code": code,
        "url": url,
        "check": check,
        "expected": expected,
        "observed": observed,
    }


@pytest.mark.parametrize(
    "kind,code,check,expected,observed",
    [
        ("blocked_host", 1, "blocked_host", "allow-listed host", BLOCKED),
        ("unreachable", 6, "unreachable", "reachable host", "unreachable"),
        ("http", 1, "http_status", "http success", "http status"),
    ],
)
def test_transport_faults(
    tmp_path: Path, kind: str, code: int, check: str, expected: str, observed: str
) -> None:
    calls = []

    def transport(url: str) -> Response:
        calls.append(url)
        raise TransportFault(kind, BLOCKED)

    fetched, failure = fetch_place_file(
        _invented(), transport, tmp_path, _clock, _no_sleep
    )
    assert fetched is None
    _failure(failure, code, BLOCKED, check, expected, observed)
    assert calls == [URL]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "url,check,expected",
    [
        (URL + "?ByTeS=0-3", "byte_range", "whole file"),
        (URL + "?RaNgE=0-3", "byte_range", "whole file"),
        (BLOCKED, "blocked_host", "allow-listed host"),
    ],
)
def test_request_refusals(tmp_path: Path, url: str, check: str, expected: str) -> None:
    def transport(address: str) -> Response:
        pytest.fail(f"refused request reached transport: {address}")

    fetched, failure = fetch_place_file(
        replace(_invented(), url=url), transport, tmp_path, _clock, _no_sleep
    )
    assert fetched is None
    _failure(failure, 1, url, check, expected, url)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("final,hops", [(BLOCKED, ()), (FINAL, (URL, BLOCKED, FINAL))])
def test_redirect_refusals(tmp_path: Path, final: str, hops: tuple[str, ...]) -> None:
    def transport(url: str) -> Response:
        return Response(final, b"SYN!", hops, '"syn-etag"')

    fetched, failure = fetch_place_file(
        _invented(), transport, tmp_path, _clock, _no_sleep
    )
    assert fetched is None
    _failure(failure, 1, BLOCKED, "blocked_host", "allow-listed host", BLOCKED)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "body,check,observed",
    [
        (b"", "empty_body", "0"),
        (b"SYN", "size_mismatch", "3"),
        (b"SYN!!", "size_mismatch", "5"),
    ],
)
def test_body_refusals(tmp_path: Path, body: bytes, check: str, observed: str) -> None:
    def transport(url: str) -> Response:
        return Response(FINAL, body, (), '"syn-etag"')

    fetched, failure = fetch_place_file(
        _invented(), transport, tmp_path, _clock, _no_sleep
    )
    assert fetched is None
    _failure(failure, 1, FINAL, check, "4", observed)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "etag,check,observed",
    [
        (None, "etag_unobserved", ""),
        (7, "etag_unobserved", ""),
        ('W/"syn-etag"', "etag_weak", 'W/"syn-etag"'),
        ("", "etag_form", ""),
        ('"', "etag_form", '"'),
        ('"syn-etag', "etag_form", '"syn-etag'),
        ('syn-etag"', "etag_form", 'syn-etag"'),
        ('""', "etag_mismatch", ""),
        ('"syn-other"', "etag_mismatch", "syn-other"),
    ],
)
def test_response_etags(
    tmp_path: Path, etag: object, check: str, observed: str
) -> None:
    def transport(url: str) -> Response:
        return Response(FINAL, b"SYN!", (), _wrong_type(etag))

    fetched, failure = fetch_place_file(
        _invented(), transport, tmp_path, _clock, _no_sleep
    )
    assert fetched is None
    _failure(failure, 1, FINAL, check, "syn-etag", observed)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "note,check,expected,observed",
    [
        ("recorded_etag: syn-etag\n", "recorded_size", "bytes", ""),
        (
            "recorded_bytes: 4\nrecorded_bytes: 4\nrecorded_etag: syn-etag\n",
            "recorded_size",
            "bytes",
            "",
        ),
        ("recorded_bytes: 0\nrecorded_etag: syn-etag\n", "recorded_size", "bytes", "0"),
        (
            "recorded_bytes: 4 \nrecorded_etag: syn-etag\n",
            "recorded_size",
            "bytes",
            "4 ",
        ),
        (
            "recorded_bytes:bad\nrecorded_bytes: 4\nrecorded_etag: syn-etag\n",
            "recorded_size",
            "bytes",
            "4",
        ),
        ("recorded_bytes: 4\n", "recorded_etag", "etag", ""),
        (
            "recorded_bytes: 4\nrecorded_etag: syn-etag\nrecorded_etag: syn-etag\n",
            "recorded_etag",
            "etag",
            "",
        ),
        (
            "recorded_bytes: 4\nrecorded_etag:bad\nrecorded_etag: syn-etag\n",
            "recorded_etag",
            "etag",
            "syn-etag",
        ),
        ("recorded_bytes: 4\nrecorded_etag: \n", "recorded_etag", "etag", ""),
        (
            "recorded_bytes: 4\nrecorded_etag: W/syn-etag\n",
            "recorded_etag",
            "etag",
            "W/syn-etag",
        ),
        (
            'recorded_bytes: 4\nrecorded_etag: "syn-etag"\n',
            "recorded_etag",
            "etag",
            '"syn-etag"',
        ),
        (
            "recorded_bytes: 4\nrecorded_etag: syn tag\n",
            "recorded_etag",
            "etag",
            "syn tag",
        ),
    ],
)
def test_recorded_refusals(
    tmp_path: Path, note: str, check: str, expected: str, observed: str
) -> None:
    def transport(url: str) -> Response:
        pytest.fail("invalid registry reached transport")

    fetched, failure = fetch_place_file(
        replace(_invented(), basis_note=note), transport, tmp_path, _clock, _no_sleep
    )
    assert fetched is None
    _failure(failure, 1, URL, check, expected, observed)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("extension", ["", "invented"])
def test_success_receipt(tmp_path: Path, extension: str) -> None:
    entry = replace(
        _invented(),
        extension=extension,
        basis_note="recorded_bytes: 1\nrecorded_etag: syn-etag\n",
    )
    calls = []

    def transport(url: str) -> Response:
        calls.append(url)
        return Response(FINAL, b"a", (FINAL,), '"syn-etag"')

    fetched, failure = fetch_place_file(entry, transport, tmp_path, _clock, _no_sleep)
    assert failure is None
    assert fetched is not None
    assert asdict(fetched) == {
        "digest": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "host": "mirror.example",
    }
    assert calls == [URL]
    directory = tmp_path / "places_ovt/part-00014"
    suffix = extension or "parquet"
    assert (
        directory
        / f"ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb.{suffix}"
    ).read_bytes() == b"a"
    receipt = json.loads(
        (
            directory
            / "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb.meta.json"
        ).read_text()
    )
    assert receipt == {
        "source_id": "places_ovt",
        "key": "places_ovt/part-00014",
        "slug": "",
        "kind": "https_file",
        "fetch_mode": "fetch",
        "title_en": "Invented places part",
        "publisher": "Invented publisher",
        "fetch_host": "mirror.example",
        "fetch_url": FINAL,
        "landing_url": "https://files.example/catalogue",
        "licence_id": "other",
        "licence_basis": "dataset",
        "licence_url": None,
        "portal_licence": None,
        "portal_licence_url": None,
        "terms_sha256": None,
        "terms_words": "terms to be read",
        "terms_read_on": "2026-11-15",
        "decision_record": None,
        "public_splits": [],
        "commit_allowed": False,
        "retrieved_utc": "2026-11-15T01:02:03Z",
        "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "bytes": 1,
        "source_modified": None,
        "period_first": None,
        "period_last": None,
        "row_count": None,
        "file": None,
        "coverage_note": None,
        "columns": [],
        "reconciliation": "none",
        "release_tables": ["pub_place"],
        "caveat_keys": [],
        "switched_off": False,
    }
    assert len(list(directory.iterdir())) == 5
    assert (directory / "index").is_dir()
    assert (directory / "checks").is_dir()


@pytest.mark.parametrize(
    "key,skip,expected",
    [
        ("places_ovt/part-00014", "", True),
        ("bldg_ovt/part-00288", "", True),
        ("bldg_ovt/part-00384", "", True),
        ("bldg_ovt/part-00385", "", True),
        ("places_ovt/part-invented", "", False),
        ("places_ovt/part-00014", "invented_skip", False),
    ],
)
def test_file_selection(key: str, skip: str, expected: bool) -> None:
    assert is_place_file(replace(_invented(), key=key, skip_reason=skip)) is expected
