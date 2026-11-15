"""Receipts, terms, retries, redirects and the checks a fetched row must pass."""

from __future__ import annotations

import http.client
import io
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.build import fetch_entry, run_build
from eii_custodian.publicdata.fetch.kinds import (
    _terms_fingerprint,
    prepare,
    read_terms_page,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.terms_text import (
    FINGERPRINT_VISIBLE_TEXT,
    terms_text_sha256,
)
from eii_custodian.publicdata.fetch.transport import (
    Response,
    TransportFault,
    open_https,
)

PORTAL = "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/planted-slug/exports/json"
META = PORTAL[: -len("/exports/json")]
PORTAL_LICENCE = "CC BY"
PORTAL_LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
FILE_URL = "https://download.openstreetmap.fr/extracts/asia/qatar-latest.osm.pbf"
LAYER = "https://services7.arcgis.com/mffQJB8rpVa5We20/arcgis/rest/services/Planted/FeatureServer"
PAGE = "https://fdiprojects.invest.qa/"
TERMS = "https://fdiprojects.invest.qa/terms"
OTHER = (
    "https://www.data.qa/api/explore/v2.1/catalog/datasets/planted-slug/exports/json"
)
REPO = repository_root(Path(__file__))
_SCRIPTS = REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
KEY_NAMES = ("EARTHDATA_API_KEY", "TOMTOM_API_KEY")


def _clock() -> str:
    return "2026-11-13T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _entry() -> Entry:
    return Entry(
        key="planted",
        source_id="planted",
        slug="planted-slug",
        kind="https_file",
        title_en="Planted file",
        publisher="Planted publisher",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host="download.openstreetmap.fr",
        url=FILE_URL,
        terms_url="",
        nightly_live_fetch=True,
        public_splits=(),
        commit_allowed=False,
        release_tables=(),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="pbf",
        landing_url=FILE_URL,
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        terms_words="invented terms words for a test",
        terms_read_on="2026-11-14",
    )


def _ok(url: str, body: bytes, hops: tuple[str, ...] = ()) -> Response:
    return Response(final_url=url, body=body, hops=hops)


def _portal_meta(
    publisher: str,
    *,
    licence: str = PORTAL_LICENCE,
    licence_url: str = PORTAL_LICENCE_URL,
    modified: str = "",
) -> dict[str, object]:
    """Hand-written portal metadata in the Explore API shape."""
    default: dict[str, str] = {
        "publisher": publisher,
        "license": licence,
        "license_url": licence_url,
    }
    if modified:
        default["modified"] = modified
    return {"metas": {"default": default}}


def _sidecar(folder: Path) -> dict[str, object]:
    found = list(folder.rglob("*.meta.json"))
    if not found:
        found = [path for path in folder.rglob("citation.json")]
    assert len(found) == 1
    loaded = json.loads(found[0].read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_receipt_records_url_publisher_licence_retrieval_and_hash(
    tmp_path: Path,
) -> None:
    """A fixture fetch writes a sha256-named file and a complete sidecar."""
    body = b"invented-bytes"
    entry = _entry()

    def transport(url: str) -> Response:
        assert url == FILE_URL
        return _ok(url, body)

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    digest = sha256_hex(body)
    assert side["sha256"] == digest
    assert side["publisher"] == "Planted publisher"
    assert side["licence_id"] == "CC-BY-4.0"
    assert side["licence_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert side["fetch_url"] == FILE_URL
    assert side["retrieved_utc"] == "2026-11-13T08:00:00Z"
    assert side["terms_words"] == entry.terms_words
    assert side["terms_read_on"] == entry.terms_read_on
    assert side["licence_basis"] == entry.licence_basis
    assert side["decision_record"] is None
    assert side["switched_off"] is False
    assert (tmp_path / "planted" / f"{digest}.pbf").read_bytes() == body


def test_redirect_to_an_unlisted_host_stores_nothing(tmp_path: Path) -> None:
    """A redirect off the allow-list fails before any file is stored."""

    def transport(url: str) -> Response:
        return _ok(url, b"no", hops=("https://evil.example/landed",))

    failure = fetch_entry(_entry(), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "blocked_host"
    assert list(tmp_path.rglob("*")) == [] or all(
        path.is_dir() for path in tmp_path.rglob("*")
    )
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_redirect_guard_blocks_an_unlisted_host_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A redirect off the allow-list fails at once and names the blocked address."""
    blocked = "https://evil.example/landed"
    payload = (
        "HTTP/1.1 302 Found\r\n"
        f"Location: {blocked}\r\n"
        "Content-Length: 0\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    attempts: list[str] = []

    class _ScriptedSocket:
        def sendall(self, data: bytes) -> None:
            return None

        def send(self, data: bytes) -> int:
            return len(data)

        def makefile(
            self, mode: str = "rb", *_args: object, **_kwargs: object
        ) -> io.BytesIO:
            return io.BytesIO(payload)

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        attempts.append(connection.host)
        connection.sock = _ScriptedSocket()

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    sleeps: list[float] = []
    failure = fetch_entry(_entry(), open_https, tmp_path, _clock, sleeps.append)
    assert failure is not None
    assert failure.check == "blocked_host"
    assert failure.observed == blocked
    assert failure.url == blocked
    assert failure.expected == "allow-listed host"
    assert len(attempts) == 1
    assert sleeps == []
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_portal_records_the_host_that_served_the_file(tmp_path: Path) -> None:
    """The sidecar records the host of the final URL, including the other portal host."""
    body = b'[{"zone": 1}]'
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        fetch_host="www.data.gov.qa",
        publisher="Kahramaa",
    )

    def transport(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Kahramaa", modified="2026-08-04")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(OTHER, body)

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["fetch_host"] == "www.data.qa"
    assert side["slug"] == "planted-slug"
    assert side["source_modified"] == "2026-08-04"


def test_portal_publisher_or_licence_mismatch_stores_nothing(tmp_path: Path) -> None:
    """A publisher or licence that is not the registered one stores nothing."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        publisher="Kahramaa",
    )

    def mismatch(url: str) -> Response:
        payload = {"metas": {"default": {"publisher": "Other", "license": "CC BY 4.0"}}}
        return _ok(url, json.dumps(payload).encode("utf-8"))

    failure = fetch_entry(entry, mismatch, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "publisher_mismatch"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []

    def licence(url: str) -> Response:
        payload = {"metas": {"default": {"publisher": "Kahramaa", "license": "closed"}}}
        return _ok(url, json.dumps(payload).encode("utf-8"))

    failure = fetch_entry(entry, licence, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "licence_mismatch"


def test_missing_publisher_stores_nothing(tmp_path: Path) -> None:
    """An empty publisher is a failed check and stores nothing, on every basis."""
    entry = replace(_entry(), kind="portal_dataset", extension="json", url=PORTAL)
    owned = replace(
        entry,
        licence_basis="owner_decision",
        decision_record="0026",
    )

    def no_publisher(url: str) -> Response:
        payload = {"metas": {"default": {"publisher": "", "license": "CC BY 4.0"}}}
        return _ok(url, json.dumps(payload).encode("utf-8"))

    for row, folder in ((entry, tmp_path / "dataset"), (owned, tmp_path / "owned")):
        failure = fetch_entry(row, no_publisher, folder, _clock, _sleep)
        assert failure is not None
        assert failure.check == "publisher_missing"
        assert [path for path in folder.rglob("*") if path.is_file()] == []


def _portal_without_licence(url: str) -> Response:
    if url == META:
        payload = {
            "metas": {"default": {"publisher": "Planted publisher", "license": ""}}
        }
        return _ok(url, json.dumps(payload).encode("utf-8"))
    return _ok(url, b"[]")


def test_owner_decision_portal_without_a_licence_is_stored(tmp_path: Path) -> None:
    """A portal that names no licence still stores an owner_decision row."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        licence_basis="owner_decision",
        decision_record="0026",
    )
    assert fetch_entry(entry, _portal_without_licence, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["portal_licence"] is None
    assert side["portal_licence_url"] is None
    assert side["licence_basis"] == "owner_decision"
    assert side["decision_record"] == "0026"
    assert side["terms_words"] == entry.terms_words
    assert side["terms_read_on"] == entry.terms_read_on
    assert side["switched_off"] is False
    assert list((tmp_path / "planted").glob("*.json"))


def test_portal_terms_without_a_licence_is_stored(tmp_path: Path) -> None:
    """A portal that names no licence still stores a portal_terms row."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        licence_basis="portal_terms",
        decision_record="",
    )
    assert fetch_entry(entry, _portal_without_licence, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["portal_licence"] is None
    assert side["portal_licence_url"] is None
    assert side["licence_basis"] == "portal_terms"
    assert side["switched_off"] is False


def test_provider_terms_portal_without_a_licence_is_stored(tmp_path: Path) -> None:
    """A portal that names no licence still stores a provider_terms row."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        licence_basis="provider_terms",
        decision_record="",
    )
    assert fetch_entry(entry, _portal_without_licence, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["portal_licence"] is None
    assert side["portal_licence_url"] is None
    assert side["licence_basis"] == "provider_terms"


def test_empty_portal_licence_is_returned_as_empty_strings() -> None:
    """A portal with no licence text returns empty licence fields, URL included."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        licence_basis="owner_decision",
        decision_record="0026",
    )

    def transport(url: str) -> Response:
        if url == META:
            payload = {
                "metas": {
                    "default": {
                        "publisher": "Planted publisher",
                        "license": "",
                        "license_url": "https://www.data.gov.qa/planted-licence",
                    }
                }
            }
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b"[]")

    prepared = prepare(entry, transport, _sleep)
    assert prepared.failure is None
    assert prepared.portal_licence == ""
    assert prepared.portal_licence_url == ""


def test_dataset_portal_without_a_licence_fails(tmp_path: Path) -> None:
    """A dataset row claims a stated open licence, so a missing one fails."""
    entry = replace(_entry(), kind="portal_dataset", extension="json", url=PORTAL)
    failure = fetch_entry(entry, _portal_without_licence, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.code == 1
    assert failure.url == META
    assert failure.check == "licence_missing"
    assert failure.expected == (
        "text:CC BY url:https://creativecommons.org/licenses/by/4.0/"
    )
    assert failure.observed == "text: url:"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_owner_decision_portal_licence_mismatch_stores_nothing(tmp_path: Path) -> None:
    """A licence the portal names, when it differs, fails for owner_decision too."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        licence_basis="owner_decision",
        decision_record="0026",
        publisher="Planted publisher",
    )

    def licence(url: str) -> Response:
        payload = {
            "metas": {
                "default": {"publisher": "Planted publisher", "license": "closed"}
            }
        }
        return _ok(url, json.dumps(payload).encode("utf-8"))

    failure = fetch_entry(entry, licence, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "licence_mismatch"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_forbidding_terms_leave_the_source_fetched_and_stored(tmp_path: Path) -> None:
    """A terms page that forbids the use still stores the source, with no OWNER line."""
    entry = replace(
        _entry(),
        key="planted_page",
        source_id="planted_page",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        licence_basis="owner_decision",
        decision_record="0026",
        fetch_host="fdiprojects.invest.qa",
        terms_watch=False,
    )
    page = b"<html>invented</html>"

    def transport(url: str) -> Response:
        if url == TERMS:
            return _ok(url, b"The page forbids the use made here.")
        return _ok(url, page)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    assert not any("OWNER" in line for line in outcome.lines)
    stored = _stored_page(tmp_path, entry.key)
    assert stored.read_bytes() == page
    log = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert not any("OWNER" in line for line in log["lines"])


def test_busy_gmaps_stays_on_when_terms_name_the_use(tmp_path: Path) -> None:
    """busy_gmaps is not switched off, because the owner decided to use it."""
    entry = replace(
        _entry(),
        key="busy_gmaps",
        source_id="busy_gmaps",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        licence_basis="owner_decision",
        decision_record="0026",
        nightly_live_fetch=False,
    )

    def transport(url: str) -> Response:
        if url == TERMS:
            return _ok(url, b"The page forbids the use made here.")
        return _ok(url, b"<html>invented</html>")

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["switched_off"] is False
    assert side["decision_record"] == "0026"
    assert side["terms_words"] == entry.terms_words
    assert side["terms_read_on"] == entry.terms_read_on
    assert isinstance(side["terms_sha256"], str) and side["terms_sha256"]


OLD_FORBIDDING_WORDS = (
    b"the material SHOULD\nnot be copied or modified or "
    b"re-produced in whole or in part without:\npermission. "
    b"The page forbids the use made here."
)


def test_watched_row_with_the_old_forbidding_words_is_fetched(
    tmp_path: Path,
) -> None:
    """A watched row is stored when the terms page still holds the old words."""
    watched = _watched_entry()
    page = b"<html>invented dashboard</html>"
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == watched.terms_url:
            return _ok(url, OLD_FORBIDDING_WORDS)
        if url == watched.url:
            return _ok(url, page)
        raise AssertionError(url)

    outcome = run_build((watched,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    assert not any(line.startswith("OWNER ") for line in outcome.lines)
    assert not any(line.startswith("TERMS ") for line in outcome.lines)
    assert seen == [watched.url, watched.terms_url]
    stored = _stored_page(tmp_path, watched.key)
    assert stored.read_bytes() == page
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert loaded["terms"] == [
        {
            "key": watched.key,
            "retrieved_utc": "2026-11-13T08:00:00Z",
            "terms_sha256": terms_text_sha256(OLD_FORBIDDING_WORDS),
            "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
            "terms_url": watched.terms_url,
            "terms_words": watched.terms_words,
            "terms_read_on": watched.terms_read_on,
        }
    ]


def test_changed_terms_hash_is_logged_and_the_row_is_still_fetched(
    tmp_path: Path,
) -> None:
    """A terms hash that differs from the previous build log is named, and stored."""
    watched = _watched_entry()
    page = b"<html>invented dashboard</html>"
    terms_body = b"Invented terms page for a watched row."
    previous = {
        "lines": [],
        "terms": [
            {
                "key": watched.key,
                "retrieved_utc": "2026-11-12T08:00:00Z",
                "terms_sha256": "a" * 64,
                "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
                "terms_url": watched.terms_url,
            }
        ],
    }
    (tmp_path / "build-log.json").write_text(json.dumps(previous), encoding="utf-8")
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == watched.terms_url:
            return _ok(url, terms_body)
        if url == watched.url:
            return _ok(url, page)
        raise AssertionError(url)

    outcome = run_build((watched,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {watched.key} changed since the last build ({watched.terms_url})"
    assert outcome.failure is None
    assert notice in outcome.lines
    assert not any(line.startswith("OWNER ") for line in outcome.lines)
    assert seen == [watched.url, watched.terms_url]
    assert _stored_page(tmp_path, watched.key).read_bytes() == page
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert notice in loaded["lines"]
    assert loaded["terms"] == [
        {
            "key": watched.key,
            "retrieved_utc": "2026-11-13T08:00:00Z",
            "terms_sha256": terms_text_sha256(terms_body),
            "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
            "terms_url": watched.terms_url,
            "terms_words": watched.terms_words,
            "terms_read_on": watched.terms_read_on,
        }
    ]


def test_skipped_watched_row_hashes_terms_and_does_not_switch_off(
    tmp_path: Path,
) -> None:
    """An unconfirmed watched row is still hashed, named on a change, and left off."""
    watched = _unconfirmed_watched()
    assert watched.terms_watch is True
    assert watched.decision_record == "0026"
    assert watched.terms_words.strip()
    assert watched.terms_read_on
    assert watched.skip_reason != ""
    previous = {
        "lines": [],
        "terms": [
            {
                "key": watched.key,
                "retrieved_utc": "2026-11-12T08:00:00Z",
                "terms_sha256": "b" * 64,
                "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
                "terms_url": watched.terms_url,
            }
        ],
    }
    (tmp_path / "build-log.json").write_text(json.dumps(previous), encoding="utf-8")
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == watched.terms_url:
            return _ok(url, OLD_FORBIDDING_WORDS)
        raise AssertionError(url)

    outcome = run_build((watched,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {watched.key} changed since the last build ({watched.terms_url})"
    assert outcome.failure is None
    assert notice in outcome.lines
    assert not any(line.startswith("OWNER ") for line in outcome.lines)
    assert any(line.startswith("SKIP ") for line in outcome.lines)
    assert seen == [watched.terms_url]
    stored = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name != "build-log.json"
    ]
    assert stored == []
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert notice in loaded["lines"]
    assert loaded["terms"] == [
        {
            "key": watched.key,
            "retrieved_utc": "2026-11-13T08:00:00Z",
            "terms_sha256": terms_text_sha256(OLD_FORBIDDING_WORDS),
            "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
            "terms_url": watched.terms_url,
            "terms_words": watched.terms_words,
            "terms_read_on": watched.terms_read_on,
        }
    ]


def _unconfirmed_watched() -> Entry:
    """A planted watched row whose page list is still unconfirmed."""
    return replace(
        _entry(),
        key="unconfirmed_pages",
        source_id="unconfirmed_pages",
        kind="terms_page",
        extension="html",
        url="https://www.invest.qa/unconfirmed",
        terms_url="https://www.invest.qa/en/terms-and-conditions?tab=terms-of-use",
        terms_watch=True,
        basis_note="Owner decision recorded for this planted unconfirmed row.",
        fetch_host="www.invest.qa",
        landing_url="https://www.invest.qa/unconfirmed",
        licence_basis="owner_decision",
        decision_record="0026",
        skip_reason="page_list_unconfirmed",
    )


def _watched_entry() -> Entry:
    """A planted row that watches its terms page. The flag changes nothing."""
    return replace(
        _entry(),
        key="watched_source",
        source_id="watched_source",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        terms_watch=True,
        licence_basis="owner_decision",
        decision_record="0026",
        fetch_host="fdiprojects.invest.qa",
        landing_url=PAGE,
        basis_note="planted watch",
    )


def _stored_page(folder: Path, key: str) -> Path:
    found = [
        path
        for path in (folder / key).rglob("*")
        if path.is_file() and not path.name.endswith(".meta.json")
    ]
    assert len(found) == 1
    return found[0]


_FILE_TERMS = "https://www.data.gov.qa/planted-terms"
_TERMS_ONE = b"<p>Invented terms sentence one.</p>"
_TERMS_TWO = b"<p>Invented terms sentence two.</p>"


def _file_with_terms(*, watch: bool = False) -> Entry:
    return replace(
        _entry(),
        terms_url=_FILE_TERMS,
        terms_watch=watch,
        basis_note="planted note",
    )


def test_changed_terms_on_an_unwatched_file_are_stored_both_times(
    tmp_path: Path,
) -> None:
    """A changed terms page prints TERMS and the file is stored on both builds."""
    entry = _file_with_terms()
    assert entry.terms_watch is False
    bodies = {"terms": _TERMS_ONE}
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == _FILE_TERMS:
            return _ok(url, bodies["terms"])
        if url == FILE_URL:
            return _ok(url, b"invented-bytes")
        raise AssertionError(url)

    first = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert first.failure is None
    assert not any(line.startswith("TERMS ") for line in first.lines)
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"invented-bytes"
    bodies["terms"] = _TERMS_TWO
    second = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {entry.key} changed since the last build ({_FILE_TERMS})"
    assert second.failure is None
    assert notice in second.lines
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"invented-bytes"
    assert seen.count(FILE_URL) == 2
    assert not any(line.startswith("OWNER ") for line in second.lines)


def test_changed_terms_on_a_skipped_row_store_nothing(tmp_path: Path) -> None:
    """A skipped row is fingerprinted, named on a change, and stores nothing."""
    entry = replace(
        _file_with_terms(),
        skip_reason="publisher_or_schema_unconfirmed",
    )
    bodies = {"terms": _TERMS_ONE}
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == _FILE_TERMS:
            return _ok(url, bodies["terms"])
        raise AssertionError(url)

    first = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert first.failure is None
    assert any(line.startswith("SKIP ") for line in first.lines)
    assert not any(line.startswith("TERMS ") for line in first.lines)
    bodies["terms"] = _TERMS_TWO
    second = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {entry.key} changed since the last build ({_FILE_TERMS})"
    assert second.failure is None
    assert notice in second.lines
    assert any(line.startswith(f"SKIP {entry.key} ") for line in second.lines)
    stored = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name != "build-log.json"
    ]
    assert stored == []
    assert seen == [_FILE_TERMS, _FILE_TERMS]


def test_terms_watch_changes_nothing(tmp_path: Path) -> None:
    """Two rows equal but for terms_watch fetch and report the same way."""
    plain = _file_with_terms(watch=False)
    watched = _file_with_terms(watch=True)

    def transport(url: str) -> Response:
        if url == _FILE_TERMS:
            return _ok(url, _TERMS_ONE)
        if url == FILE_URL:
            return _ok(url, b"invented-bytes")
        raise AssertionError(url)

    left = run_build((plain,), transport, tmp_path / "plain", _clock, _sleep)
    right = run_build((watched,), transport, tmp_path / "watched", _clock, _sleep)
    assert left.failure is None
    assert right.failure is None
    assert left.lines == right.lines


def test_terms_host_off_the_allow_list_is_not_contacted(tmp_path: Path) -> None:
    """An unlisted terms host is not passed to the transport, and the file is stored."""
    terms_url = "https://evil.example/planted-terms"
    entry = replace(_entry(), terms_url=terms_url)
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return _ok(url, b"invented-bytes")

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = (
        f"TERMS {entry.key} not read: host evil.example is not on the allow-list"
        f" ({terms_url})"
    )
    assert outcome.failure is None
    assert notice in outcome.lines
    assert seen == [FILE_URL]
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"invented-bytes"


def test_terms_page_host_off_the_list_is_not_contacted(tmp_path: Path) -> None:
    """A terms_page row does not pass an unlisted terms host to the transport."""
    terms_url = "https://evil.example/planted-terms"
    entry = replace(
        _entry(),
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=terms_url,
        fetch_host="fdiprojects.invest.qa",
        landing_url=PAGE,
    )
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return _ok(url, b"<html>invented</html>")

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = (
        f"TERMS {entry.key} not read: host evil.example is not on the allow-list"
        f" ({terms_url})"
    )
    assert outcome.failure is None
    assert notice in outcome.lines
    assert seen == [PAGE]
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"<html>invented</html>"
    assert _sidecar(tmp_path)["terms_sha256"] is None


def test_terms_redirect_off_the_list_does_not_fail_the_row(tmp_path: Path) -> None:
    """A terms redirect to an unlisted host is named and does not fail the data."""
    entry = _file_with_terms()
    landed = "https://evil.example/landed"

    def transport(url: str) -> Response:
        if url == _FILE_TERMS:
            return _ok(landed, b"terms", hops=(landed,))
        if url == FILE_URL:
            return _ok(url, b"invented-bytes")
        raise AssertionError(url)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {entry.key} not read: blocked_host ({_FILE_TERMS})"
    assert outcome.failure is None
    assert notice in outcome.lines
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"invented-bytes"
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert loaded["terms"] == []


def test_terms_page_without_a_terms_url_stores_no_fingerprint(tmp_path: Path) -> None:
    """A terms page with no terms address stores the page and an empty fingerprint."""
    entry = replace(
        _entry(),
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url="",
        fetch_host="fdiprojects.invest.qa",
        landing_url=PAGE,
    )

    def transport(url: str) -> Response:
        assert url == PAGE
        return _ok(url, b"<html>invented</html>")

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    assert not any(line.startswith("TERMS ") for line in outcome.lines)
    assert _sidecar(tmp_path)["terms_sha256"] is None
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"<html>invented</html>"


def test_terms_page_without_a_terms_url_has_no_unread_reason() -> None:
    """No terms address leaves both the fingerprint and the unread check empty."""
    entry = replace(
        _entry(),
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url="",
        fetch_host="fdiprojects.invest.qa",
        landing_url=PAGE,
    )

    def transport(url: str) -> Response:
        assert url == PAGE
        return _ok(url, b"<html>invented</html>")

    prepared = prepare(entry, transport, _sleep)
    assert prepared.failure is None
    assert prepared.terms_sha256 == ""
    assert prepared.terms_unread == ""


def test_terms_page_unread_names_the_check_and_stores_no_hash(tmp_path: Path) -> None:
    """An allow-listed terms address that cannot be read names that check."""
    entry = replace(
        _entry(),
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=_FILE_TERMS,
        fetch_host="fdiprojects.invest.qa",
        landing_url=PAGE,
    )

    def transport(url: str) -> Response:
        if url == PAGE:
            return _ok(url, b"<html>invented</html>")
        if url == _FILE_TERMS:
            raise TransportFault("unreachable", url)
        raise AssertionError(url)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {entry.key} not read: unreachable ({_FILE_TERMS})"
    assert outcome.failure is None
    assert notice in outcome.lines
    assert _sidecar(tmp_path)["terms_sha256"] is None
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"<html>invented</html>"


def test_unread_terms_page_returns_an_empty_fingerprint() -> None:
    """A terms page that cannot be read returns an empty fingerprint with the failure."""
    entry = replace(_entry(), terms_url=_FILE_TERMS)

    def transport(url: str) -> Response:
        raise TransportFault("unreachable", url)

    page = read_terms_page(entry, transport, _sleep)
    assert page.failure is not None
    assert page.failure.check == "unreachable"
    assert page.sha256 == ""


def test_missing_terms_response_names_check_failed() -> None:
    """No response and no failure is the unread check named check_failed."""
    entry = replace(
        _entry(),
        kind="terms_page",
        url=PAGE,
        terms_url=TERMS,
        fetch_host="fdiprojects.invest.qa",
    )

    def reader(url: str) -> Response:
        assert url == TERMS
        return cast(Response, None)

    fingerprint, unread = _terms_fingerprint(entry, reader)
    assert fingerprint == ""
    assert unread == "check_failed"


def test_skipped_row_retries_its_terms_page(tmp_path: Path) -> None:
    """A skipped row still reads its terms page, and a failed attempt waits."""
    entry = replace(
        _entry(),
        skip_reason="publisher_or_schema_unconfirmed",
        terms_url=_FILE_TERMS,
    )
    slept: list[float] = []
    attempts = {"n": 0}

    def transport(url: str) -> Response:
        assert url == _FILE_TERMS
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TransportFault("unreachable", url)
        return _ok(url, _TERMS_ONE)

    def sleeper(seconds: float) -> None:
        slept.append(seconds)

    outcome = run_build((entry,), transport, tmp_path, _clock, sleeper)
    assert outcome.failure is None
    assert slept == [1.0]
    assert f"SKIP {entry.key} {entry.skip_reason}" in outcome.lines
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert loaded["terms"][0]["terms_sha256"] == terms_text_sha256(_TERMS_ONE)
    assert list(tmp_path.rglob("citation.json")) == []


def test_unread_terms_page_does_not_fail_the_row(tmp_path: Path) -> None:
    """A terms page that cannot be reached leaves the data stored and records no hash."""
    entry = _file_with_terms()

    def transport(url: str) -> Response:
        if url == _FILE_TERMS:
            raise TransportFault("unreachable", url)
        if url == FILE_URL:
            return _ok(url, b"invented-bytes")
        raise AssertionError(url)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    notice = f"TERMS {entry.key} not read: unreachable ({_FILE_TERMS})"
    assert outcome.failure is None
    assert notice in outcome.lines
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"invented-bytes"
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert loaded["terms"] == []


def test_citation_only_with_a_terms_url_calls_nothing(tmp_path: Path) -> None:
    """A citation row with a terms address makes no network call."""
    entry = replace(
        _entry(),
        kind="citation_only",
        extension="",
        nightly_live_fetch=False,
        url="https://www.ilo.org/resource/news/planted",
        terms_url=_FILE_TERMS,
    )

    def transport(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    side = _sidecar(tmp_path)
    assert side["sha256"] == "CITATION_ONLY"
    assert side["switched_off"] is False
    assert side["terms_words"] == entry.terms_words
    assert side["terms_read_on"] == entry.terms_read_on


def test_failed_check_records_the_reason_and_stores_nothing(tmp_path: Path) -> None:
    """A failed check leaves no usable file and names the check in the lines and the log."""
    entry = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        row_count_min=2,
        row_count_max=2,
    )

    def one_row(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Planted publisher")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b"[{}]")

    outcome = run_build((entry,), one_row, tmp_path, _clock, _sleep)
    assert outcome.failure is not None
    assert outcome.failure.check == "row_count"
    assert any(
        line.startswith("FAIL ") and "row_count" in line for line in outcome.lines
    )
    loaded = json.loads((tmp_path / "build-log.json").read_text(encoding="utf-8"))
    assert any("row_count" in line for line in loaded["lines"])
    stored = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name != "build-log.json"
    ]
    assert stored == []


def test_short_total_row_count_schema_and_period(tmp_path: Path) -> None:
    """A short page, a wrong count, a retyped column and a stale period each fail."""
    layer = replace(
        _entry(),
        kind="paged_layer",
        layer=0,
        extension="json",
        url=LAYER,
        fetch_host="services7.arcgis.com",
    )

    def short(url: str) -> Response:
        if "returnCountOnly" in url:
            return _ok(url, b'{"count": 3}')
        return _ok(url, b'{"features": []}')

    failure = fetch_entry(layer, short, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "short_total"

    counted = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        row_count_min=2,
        row_count_max=2,
    )

    def one_row(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Planted publisher")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b"[{}]")

    failure = fetch_entry(counted, one_row, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "row_count"

    typed = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        columns=(("zone", "integer"),),
    )

    def retyped(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Planted publisher")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b'[{"zone": "text"}]')

    failure = fetch_entry(typed, retyped, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "schema_retyped"

    dated = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        period_field="year",
        period_last="2025",
    )

    def stale(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Planted publisher")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b'[{"year": "2020"}]')

    failure = fetch_entry(dated, stale, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "period_last"


def test_unreachable_network_is_exit_six(tmp_path: Path) -> None:
    """An unreachable host is a network failure, code 6, and stores nothing."""

    def transport(url: str) -> Response:
        raise TransportFault("unreachable", url)

    failure = fetch_entry(_entry(), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.code == 6
    assert failure.check == "unreachable"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_row_above_the_maximum_and_a_missing_column(tmp_path: Path) -> None:
    """A count above the maximum and a missing declared column each fail."""
    counted = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        row_count_max=1,
    )

    def two_rows(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Planted publisher")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b"[{}, {}]")

    failure = fetch_entry(counted, two_rows, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "row_count"

    typed = replace(
        _entry(),
        kind="portal_dataset",
        extension="json",
        url=PORTAL,
        columns=(("zone", "integer"),),
    )

    def missing(url: str) -> Response:
        if url == META:
            payload = _portal_meta("Planted publisher")
            return _ok(url, json.dumps(payload).encode("utf-8"))
        return _ok(url, b"[{}]")

    failure = fetch_entry(typed, missing, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "schema_missing"


def test_a_fourth_retry_is_not_attempted(tmp_path: Path) -> None:
    """Three retries are the limit. A transport that would succeed later is not called again."""
    calls: list[str] = []

    def transport(url: str) -> Response:
        calls.append(url)
        if len(calls) < 5:
            raise TransportFault("http", url)
        return _ok(url, b"late")

    failure = fetch_entry(_entry(), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "http_status"
    assert len(calls) == 4
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_interrupted_write_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed replace removes the partial files."""
    import eii_custodian.publicdata.fetch.receipts as receipts

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("planted")

    monkeypatch.setattr(receipts.os, "replace", boom)

    def transport(url: str) -> Response:
        return _ok(url, b"invented-bytes")

    failure = fetch_entry(_entry(), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "write_failed"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_a_skipped_row_and_unreadable_metadata(tmp_path: Path) -> None:
    """A named skip does not call the transport. Unreadable portal metadata fails."""
    skipped = replace(_entry(), skip_reason="publisher_or_licence_unconfirmed")

    def unused(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build((skipped,), unused, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    assert outcome.lines[0].startswith("SKIP planted ")

    portal = replace(_entry(), kind="portal_dataset", extension="json", url=PORTAL)

    def broken(url: str) -> Response:
        return _ok(url, b"not-json")

    failure = fetch_entry(portal, broken, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "metadata_unreadable"


def test_citation_only_writes_metadata_and_does_not_fetch(tmp_path: Path) -> None:
    """A citation row writes sha256 CITATION_ONLY and never calls the transport."""
    entry = replace(
        _entry(),
        kind="citation_only",
        extension="",
        nightly_live_fetch=False,
        url="https://www.ilo.org/resource/news/planted",
    )

    def transport(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    side = _sidecar(tmp_path)
    assert side["sha256"] == "CITATION_ONLY"
    assert side["bytes"] == 0
    assert side["terms_words"] == entry.terms_words
    assert side["terms_read_on"] == entry.terms_read_on
    assert side["switched_off"] is False
    assert (tmp_path / "planted" / "citation.json").is_file()


def test_build_writes_only_under_the_cache(tmp_path: Path) -> None:
    """A successful build creates files only inside the cache directory it was given."""
    marker = tmp_path / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    cache = tmp_path / "data" / "public_cache"

    def transport(url: str) -> Response:
        return _ok(url, b"invented-bytes")

    outcome = run_build((_entry(),), transport, cache, _clock, _sleep)
    assert outcome.failure is None
    assert marker.read_text(encoding="utf-8") == "keep"
    for path in tmp_path.rglob("*"):
        if path.is_file() and path != marker:
            assert "public_cache" in path.parts


def test_production_code_does_not_name_a_key(tmp_path: Path) -> None:
    """The fetch code does not name a key, and a planted value is absent from a receipt."""
    secret = "planted-token-value"
    for folder in (REPO / "custodian" / "src", REPO / "scripts" / "commands"):
        assert folder.is_dir()
        assert any(folder.rglob("*.py"))
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for name in KEY_NAMES:
                assert name not in text

    def transport(url: str) -> Response:
        return _ok(url, b"invented-bytes")

    assert fetch_entry(_entry(), transport, tmp_path, _clock, _sleep) is None
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert secret not in blob
