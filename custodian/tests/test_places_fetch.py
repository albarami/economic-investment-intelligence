"""Stand-in transport only. Size, ETag, host and redirect are planted."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.cadence import Cadence
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.places.fetch import (
    FILE_KEYS,
    fetch_place_file,
    is_place_file,
)


class _Body:
    """A transport result that also carries the object's ETag."""

    def __init__(
        self,
        final_url: str,
        body: bytes,
        hops: tuple[str, ...] = (),
        etag: str = '"syn-etag"',
    ) -> None:
        self.final_url = final_url
        self.body = body
        self.hops = hops
        self.etag = etag


def test_registry_block_names_the_four_files() -> None:
    """The appended rows fetch whole files; the parents check HTTPS listings."""
    entries = load_registry()
    parents = {
        entry.key: entry for entry in entries if entry.key in {"places_ovt", "bldg_ovt"}
    }
    assert parents["places_ovt"].skip_reason == ""
    assert "?list-type=2&prefix=" in parents["places_ovt"].url
    assert parents["bldg_ovt"].skip_reason == ""
    assert parents["bldg_ovt"].url.endswith("theme=buildings/type=building/")
    concrete = [entry for entry in entries if entry.key in FILE_KEYS]
    assert {entry.key for entry in concrete} == set(FILE_KEYS)
    for entry in concrete:
        assert entry.skip_reason == ""
        assert entry.commit_allowed is False
        assert entry.licence_basis == "dataset"
        assert "recorded_bytes: " in entry.basis_note
        assert "recorded_etag: " in entry.basis_note


def test_size_etag_host_and_redirect_plants(tmp_path: Path) -> None:
    """Each fetch guard fails, and a matching file is stored once."""
    body = b"SYN!"
    entry = _entry(len(body))
    calls: list[str] = []

    def transport(url: str) -> _Body:
        calls.append(url)
        return _Body(url, body)

    fetched, failure = fetch_place_file(entry, transport, tmp_path, _clock, _sleep)
    assert failure is None
    assert fetched is not None
    assert calls == [entry.url]
    assert fetched.digest == sha256_hex(body)
    stored = tmp_path / entry.key / f"{fetched.digest}.parquet"
    assert stored.read_bytes() == body

    short, mismatch = fetch_place_file(
        _entry(len(body) + 1), transport, tmp_path / "size", _clock, _sleep
    )
    assert short is None
    assert mismatch is not None
    assert mismatch.check == "size_mismatch"

    def wrong_etag(url: str) -> _Body:
        return _Body(url, body, etag='"syn-other"')

    _ignored, etag = fetch_place_file(
        entry, wrong_etag, tmp_path / "etag", _clock, _sleep
    )
    assert etag is not None
    assert etag.check == "etag_mismatch"

    blocked_calls: list[str] = []

    def blocked(url: str) -> _Body:
        blocked_calls.append(url)
        return _Body(url, body)

    off = _entry(len(body), url="https://evil.example/invented.parquet")
    _ignored, host = fetch_place_file(off, blocked, tmp_path / "host", _clock, _sleep)
    assert host is not None
    assert host.check == "blocked_host"
    assert blocked_calls == []

    def redirected(url: str) -> _Body:
        return _Body(url, body, hops=("https://evil.example/invented",))

    _ignored, hop = fetch_place_file(
        entry, redirected, tmp_path / "hop", _clock, _sleep
    )
    assert hop is not None
    assert hop.check == "blocked_host"


def test_build_hook_propagates_the_failure(tmp_path: Path) -> None:
    """The places file is fetched after the further source, and a mismatch stops the build."""
    entry = _entry(4)

    def transport(url: str) -> _Body:
        return _Body(url, b"SYN")

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert outcome.failure is not None
    assert outcome.failure.check == "size_mismatch"
    assert any(line.startswith("FAIL ") for line in outcome.lines)


def test_etag_form_weak_empty_body_and_recorded_lines(tmp_path: Path) -> None:
    """Quotes, a weak tag, an empty body and a bad recorded line each refuse."""
    body = b"SYN!"
    entry = _entry(len(body))

    def transport(url: str) -> _Body:
        return _Body(url, body)

    fetched, failure = fetch_place_file(entry, transport, tmp_path, _clock, _sleep)
    assert failure is None
    assert fetched is not None

    def bare(url: str) -> _Body:
        return _Body(url, body, etag="syn-etag")

    _ignored, form = fetch_place_file(entry, bare, tmp_path / "form", _clock, _sleep)
    assert form is not None
    assert form.check == "etag_form"

    def weak(url: str) -> _Body:
        return _Body(url, body, etag='W/"syn-etag"')

    _ignored, weak_failure = fetch_place_file(
        entry, weak, tmp_path / "weak", _clock, _sleep
    )
    assert weak_failure is not None
    assert weak_failure.check == "etag_weak"

    zero = replace(entry, basis_note="recorded_bytes: 0\nrecorded_etag: syn-etag\n")
    _ignored, size = fetch_place_file(
        zero, transport, tmp_path / "zero", _clock, _sleep
    )
    assert size is not None
    assert size.check == "recorded_size"

    def empty(url: str) -> _Body:
        return _Body(url, b"")

    three = _entry(3)
    _ignored, blank = fetch_place_file(three, empty, tmp_path / "empty", _clock, _sleep)
    assert blank is not None
    assert blank.check == "empty_body"

    twice_size = replace(
        entry,
        basis_note="recorded_bytes: 4\nrecorded_bytes: 4\nrecorded_etag: syn-etag\n",
    )
    _ignored, repeated_size = fetch_place_file(
        twice_size, transport, tmp_path / "twice-size", _clock, _sleep
    )
    assert repeated_size is not None
    assert repeated_size.check == "recorded_size"
    twice_etag = replace(
        entry,
        basis_note="recorded_bytes: 4\nrecorded_etag: syn-etag\nrecorded_etag: syn-etag\n",
    )
    _ignored, repeated_etag = fetch_place_file(
        twice_etag, transport, tmp_path / "twice-etag", _clock, _sleep
    )
    assert repeated_etag is not None
    assert repeated_etag.check == "recorded_etag"
    bad_size = replace(
        entry, basis_note="recorded_bytes: 4 \nrecorded_etag: syn-etag\n"
    )
    _ignored, malformed_size = fetch_place_file(
        bad_size, transport, tmp_path / "bad-size", _clock, _sleep
    )
    assert malformed_size is not None
    assert malformed_size.check == "recorded_size"
    bad_etag = replace(
        entry, basis_note='recorded_bytes: 4\nrecorded_etag: "syn-etag"\n'
    )
    _ignored, malformed_etag = fetch_place_file(
        bad_etag, transport, tmp_path / "bad-etag", _clock, _sleep
    )
    assert malformed_etag is not None
    assert malformed_etag.check == "recorded_etag"


def test_real_response_and_missing_recorded_lines(tmp_path: Path) -> None:
    """A real response without an ETag, a ranged URL, and each missing line."""
    entry = _entry(4)
    calls: list[str] = []

    def transport(url: str) -> Response:
        calls.append(url)
        return Response(url, b"SYN!", ())

    _ignored, failure = fetch_place_file(
        entry, transport, tmp_path / "real", _clock, _sleep
    )
    assert failure is not None
    assert failure.check == "etag_unobserved"
    ranged = _entry(4, url=entry.url + "?bytes=0-3")
    ranged_calls: list[str] = []

    def counted(url: str) -> Response:
        ranged_calls.append(url)
        return Response(url, b"SYN!", ())

    _ignored, byte_range = fetch_place_file(
        ranged, counted, tmp_path / "range", _clock, _sleep
    )
    assert byte_range is not None
    assert byte_range.check == "byte_range"
    assert ranged_calls == []
    no_size = replace(entry, basis_note="recorded_etag: syn-etag\n")
    _ignored, size = fetch_place_file(
        no_size, transport, tmp_path / "no-size", _clock, _sleep
    )
    assert size is not None
    assert size.check == "recorded_size"
    no_etag = replace(entry, basis_note="recorded_bytes: 4\n")
    _ignored, etag = fetch_place_file(
        no_etag, transport, tmp_path / "no-etag", _clock, _sleep
    )
    assert etag is not None
    assert etag.check == "recorded_etag"


def test_etag_that_is_not_text_is_unobserved(tmp_path: Path) -> None:
    """An entity tag that is present and not text is unobserved."""
    entry = _entry(4)

    class _Numbered:
        def __init__(self, url: str) -> None:
            self.final_url = url
            self.body = b"SYN!"
            self.hops = ()
            self.etag = 7

    def transport(url: str) -> _Numbered:
        return _Numbered(url)

    _ignored, failure = fetch_place_file(entry, transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "etag_unobserved"
    assert failure.observed == ""


def test_skip_reason_still_set_fetches_nothing(tmp_path: Path) -> None:
    """With the reason still set, the row is not a place file and the hook fetches nothing."""
    entry = next(item for item in load_registry() if item.key == FILE_KEYS[0])
    planted = replace(entry, skip_reason="transport_etag_pending_s2_t06_part_b")
    assert is_place_file(planted) is False
    calls: list[str] = []

    def transport(url: str) -> Response:
        calls.append(url)
        return Response(url, b"SYN", ())

    outcome = run_build((planted,), transport, tmp_path, _clock, _sleep)
    assert calls == []
    assert outcome.failure is None
    expected = _skipped_lines(planted)
    assert outcome.lines[: len(expected)] == expected


def _skipped_lines(entry: Entry) -> tuple[str, str]:
    """Filled terms keep their off-list advisory before the technical skip."""
    assert entry.terms_url
    assert approve(entry.terms_url).ok is False
    host = urlsplit(entry.terms_url).hostname
    return (
        f"TERMS {entry.key} not read: host {host} is not on the allow-list "
        f"({entry.terms_url})",
        f"SKIP {entry.key} {entry.skip_reason}",
    )


def test_pack_scopes_the_foursquare_line_and_the_readme_orders_the_build() -> None:
    """The Apache row names places_ovt, and the package readme states the order."""
    root = repository_root(Path(__file__))
    pack = (root / "docs/04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    assert (
        'for `places_ovt`: "Data from Foursquare. Copyright 2024 Foursquare Labs, Inc.'
        in pack
    )
    assert (
        '`places_fsq`: "Copyright 2024 Foursquare Labs, Inc. All rights reserved. '
        'Licensed under Apache 2.0; transformed to the Overture schema."' in pack
    )
    readme = (
        root / "custodian/src/eii_custodian/publicdata/places/README.md"
    ).read_text(encoding="utf-8")
    assert "after the frame's boundary, grid and zones" in readme
    assert "before the gazetteer resolves its pending entries" in readme


def test_skipped_places_preserve_other_build_stages(tmp_path, monkeypatch):
    """The four files add terms advisories and skips, preserving every stage."""
    from custodian.tests.test_publicdata_behaviour import _entry as public_entry
    from custodian.tests.test_publicdata_behaviour import _ok

    from eii_custodian.publicdata.fetch import build

    events = []
    original_publish = build.publish_investment
    original_stage = build.run_stage

    def publish(*args, **kwargs):
        events.append("investment")
        return original_publish(*args, **kwargs)

    def stage(*args, **kwargs):
        events.append("series" if "build_entries" in kwargs else "regression")
        return original_stage(*args, **kwargs)

    def transport(url):
        return _ok(url, b"invented-bytes")

    monkeypatch.setattr(build, "publish_investment", publish)
    monkeypatch.setattr(build, "run_stage", stage)
    baseline = run_build(
        (public_entry(),), transport, tmp_path / "baseline", _clock, _sleep
    )
    assert baseline.failure is None
    assert events == ["investment", "series", "regression"]
    events.clear()
    skipped = tuple(
        replace(entry, skip_reason="transport_etag_pending_s2_t06_part_b")
        for entry in load_registry()
        if entry.key in FILE_KEYS
    )
    joined = run_build(
        (*skipped, public_entry()), transport, tmp_path / "joined", _clock, _sleep
    )
    assert joined.failure is None
    expected = tuple(line for entry in skipped for line in _skipped_lines(entry))
    assert joined.lines[: len(expected)] == expected
    assert joined.lines[len(expected) :] == baseline.lines
    assert events == ["investment", "series", "regression"]


def _entry(size: int, url: str = "") -> Entry:
    address = url or (
        "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/invented.parquet"
    )
    return Entry(
        refetch=Cadence("none", "frequency_unconfirmed", ""),
        key="places_ovt/part-00014",
        source_id="places_ovt",
        slug="",
        kind="https_file",
        title_en="Invented places part",
        publisher="Overture Maps Foundation",
        licence_id="other",
        licence_basis="dataset",
        decision_record="",
        fetch_host="overturemaps-us-west-2.s3.us-west-2.amazonaws.com",
        url=address,
        terms_url="",
        terms_words="terms to be read",
        terms_read_on="2026-11-15",
        nightly_live_fetch=True,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_place",),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="parquet",
        landing_url="https://stac.overturemaps.org/2026-10-21.0/places/place/collection.json",
        basis_note=f"recorded_bytes: {size}\nrecorded_etag: syn-etag\n",
    )


def _clock() -> str:
    return "2026-11-14T12:00:00Z"


def _sleep(_seconds: float) -> None:
    return None
