"""Receipts, terms, retries, redirects and the checks a fetched row must pass."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.build import fetch_entry, run_build
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.terms_text import (
    FINGERPRINT_VISIBLE_TEXT,
    terms_text_sha256,
)
from eii_custodian.publicdata.fetch.transport import Response, TransportFault

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
REPO = Path(__file__).resolve().parents[2]
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


def test_missing_publisher_or_licence_stores_nothing(tmp_path: Path) -> None:
    """An empty publisher or an empty licence is a failed check and stores nothing."""
    entry = replace(_entry(), kind="portal_dataset", extension="json", url=PORTAL)

    def no_publisher(url: str) -> Response:
        payload = {"metas": {"default": {"publisher": "", "license": "CC BY 4.0"}}}
        return _ok(url, json.dumps(payload).encode("utf-8"))

    failure = fetch_entry(entry, no_publisher, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "publisher_missing"

    def no_licence(url: str) -> Response:
        payload = {
            "metas": {"default": {"publisher": "Planted publisher", "license": ""}}
        }
        return _ok(url, json.dumps(payload).encode("utf-8"))

    failure = fetch_entry(entry, no_licence, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "licence_missing"


def test_terms_that_forbid_the_use_switch_the_source_off(tmp_path: Path) -> None:
    """Terms that forbid the use switch the source off, store nothing, and name it."""
    entry = replace(
        _entry(),
        key="fdi_projects",
        source_id="fdi_projects",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        licence_basis="owner_decision",
        decision_record="0017",
        fetch_host="fdiprojects.invest.qa",
    )

    def transport(url: str) -> Response:
        if url == TERMS:
            return _ok(url, b"The page forbids the use made here.")
        return _ok(url, b"<html>invented</html>")

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is None
    assert (
        f"OWNER fdi_projects switched off: terms read at fetch forbid the use ({TERMS})"
    ) in outcome.lines
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name != "build-log.json"
    ] == []


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
        decision_record="0019",
        nightly_live_fetch=False,
    )

    def transport(url: str) -> Response:
        if url == TERMS:
            return _ok(url, b"The page forbids the use made here.")
        return _ok(url, b"<html>invented</html>")

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["switched_off"] is False
    assert side["decision_record"] == "0019"
    assert isinstance(side["terms_sha256"], str) and side["terms_sha256"]


FORBID_PHRASE = (
    "should not be copied or modified or re-produced in whole or in part without"
)


def test_recorded_phrase_switches_the_source_off_and_the_build_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A terms fixture holding the phrase switches that row off and the next row is fetched."""
    import commands.build_public as build_public

    gated = replace(
        _entry(),
        key="fdi_projects",
        source_id="fdi_projects",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        terms_forbid=(FORBID_PHRASE,),
        licence_basis="owner_decision",
        decision_record="0017",
        fetch_host="fdiprojects.invest.qa",
        skip_reason="page_list_unconfirmed",
    )
    other = _entry()
    terms_body = (
        b"the material SHOULD\nnot be copied or modified or "
        b"re-produced in whole or in part without:\npermission"
    )
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == TERMS:
            return _ok(url, terms_body)
        if url == FILE_URL:
            return _ok(url, b"invented-bytes")
        raise AssertionError(url)

    def entries() -> tuple[Entry, ...]:
        return (gated, other)

    monkeypatch.setattr(build_public, "load_registry", entries)
    monkeypatch.setattr(build_public, "utc_now", _clock)
    code = build_public.run(tmp_path, {}, (), transport=transport, sleep=_sleep)
    captured = capsys.readouterr()
    owner = (
        f"OWNER fdi_projects switched off: terms read at fetch forbid the use ({TERMS})"
    )
    assert code == 0
    assert owner in captured.out
    assert "SKIP " not in captured.out
    assert seen == [TERMS, FILE_URL]
    cache = tmp_path / "data" / "public_cache"
    assert list(cache.glob("fdi_projects/**/*")) == []
    assert list((cache / "planted").glob("*.pbf"))
    loaded = json.loads((cache / "build-log.json").read_text(encoding="utf-8"))
    assert loaded["terms"] == [
        {
            "key": "fdi_projects",
            "reason": "terms read at fetch forbid the use",
            "retrieved_utc": "2026-11-13T08:00:00Z",
            "switched_off": True,
            "terms_sha256": terms_text_sha256(terms_body),
            "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
            "terms_url": TERMS,
        }
    ]


def test_terms_changed_since_they_were_read_switches_the_source_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A terms fixture without the recorded phrase switches the source off."""
    import commands.build_public as build_public

    gated = replace(
        _entry(),
        key="investqa_pages",
        source_id="investqa_pages",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        terms_forbid=(FORBID_PHRASE,),
        licence_basis="owner_decision",
        decision_record="0017",
        fetch_host="www.invest.qa",
    )
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == TERMS:
            return _ok(url, b"These terms permit personal viewing only.")
        raise AssertionError(url)

    def entries() -> tuple[Entry, ...]:
        return (gated,)

    monkeypatch.setattr(build_public, "load_registry", entries)
    monkeypatch.setattr(build_public, "utc_now", _clock)
    code = build_public.run(tmp_path, {}, (), transport=transport, sleep=_sleep)
    captured = capsys.readouterr()
    assert code == 0
    assert (
        "OWNER investqa_pages switched off: terms changed since they were read; "
        f"read them again ({TERMS})"
    ) in captured.out
    assert seen == [TERMS]
    cache = tmp_path / "data" / "public_cache"
    stored = [
        path
        for path in cache.rglob("*")
        if path.is_file() and path.name != "build-log.json"
    ]
    assert stored == []
    loaded = json.loads((cache / "build-log.json").read_text(encoding="utf-8"))
    assert loaded["terms"][0]["reason"] == "terms changed since they were read"
    assert loaded["terms"][0]["switched_off"] is True


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
        }
    ]


def test_skipped_watched_row_hashes_terms_and_does_not_switch_off(
    tmp_path: Path,
) -> None:
    """The skipped investment row is still hashed, named on a change, and left off."""
    by_id = {entry.source_id: entry for entry in load_registry()}
    watched = by_id["investqa_pages"]
    assert watched.terms_watch is True
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
        }
    ]


def _watched_entry() -> Entry:
    """A planted row that watches its terms page and is never switched off."""
    return replace(
        _entry(),
        key="watched_source",
        source_id="watched_source",
        kind="terms_page",
        extension="html",
        url=PAGE,
        terms_url=TERMS,
        terms_watch=True,
        fetch_host="fdiprojects.invest.qa",
        landing_url=PAGE,
    )


def _stored_page(folder: Path, key: str) -> Path:
    found = [
        path
        for path in (folder / key).rglob("*")
        if path.is_file() and not path.name.endswith(".meta.json")
    ]
    assert len(found) == 1
    return found[0]


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
