"""Required large sources: invented streams, bounded memory and complete hashes."""

from __future__ import annotations

import hashlib
import io
import json
import tracemalloc
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import large
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response, StreamResponse


@pytest.fixture(scope="module")
def entries():
    return {e.key: e for e in load_registry()}


class Sink:
    def __init__(self):
        self.count = 0
        self.digest = hashlib.sha256()

    def write(self, body):
        self.count += len(body)
        self.digest.update(body)
        return len(body)


def stream(entry, chunks, size=None, etag=None, final=None):
    @contextmanager
    def read(url):
        assert url == entry.url
        yield StreamResponse(final or url, (), size, iter(chunks), etag=etag)

    return read


@pytest.mark.parametrize("key", large.REQUIRED_KEYS)
def test_required_source_admits_more_than_300_mib_with_constant_memory(
    entries, key, monkeypatch
):
    from eii_custodian.publicdata.fetch import transport

    entry = entries[key]
    # The real stream opener reads an invented response without a large file.
    size = large.recorded_size(entry) or (300 * 1024 * 1024 + 9)

    class Body:
        def __init__(self):
            self.headers = {"Content-Length": str(size)}
            tag = large.recorded_etag(entry)
            if tag is not None:
                self.headers["ETag"] = tag
            self.left = size
            self.read_count = 0
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

        def geturl(self):
            return entry.url

        def read(self, count=-1):
            assert 0 < count <= 65536, "unbounded_read"
            self.read_count += 1
            amount = min(self.left, count)
            self.left -= amount
            return b"x" * amount

    response = Body()
    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *_a: SimpleNamespace(open=lambda *_a, **_k: response),
    )
    sink = Sink()
    tracemalloc.start()
    try:
        result = large.receive(entry, transport.open_https_stream, sink)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.nbytes == sink.count == size
    assert result.sha256 == sink.digest.hexdigest()
    assert peak < 2 * 1024 * 1024
    assert response.left == 0 and response.closed
    assert response.read_count > 1


@pytest.mark.parametrize("key", large.REQUIRED_KEYS)
def test_oversize_chunk_is_named_and_never_written(entries, key):
    entry = entries[key]
    sink = Sink()
    with pytest.raises(large.IntakeError, match="stream_chunk"):
        large.receive(
            entry, stream(entry, [b"x" * 65537], etag=large.recorded_etag(entry)), sink
        )
    assert sink.count == 0


def test_overture_keeps_exact_recorded_bytes_and_etag(entries):
    entry = entries["places_ovt/part-00014"]
    with pytest.raises(large.IntakeError, match="size_mismatch"):
        large.receive(entry, stream(entry, [], large.recorded_size(entry) + 1), Sink())
    small = replace(entry, basis_note="recorded_bytes: 2\nrecorded_etag: SYN-tag")
    sink = Sink()
    with pytest.raises(large.IntakeError, match="size_mismatch"):
        large.receive(small, stream(small, [b"abc"], etag='"SYN-tag"'), sink)
    assert sink.count == 0
    with pytest.raises(large.IntakeError, match="etag_mismatch"):
        large.receive(small, stream(small, [b"ab"], 2, '"SYN-other"'), Sink())


def test_lower_source_cap_still_prevails(entries):
    from eii_custodian.publicdata.fetch.transport import metadata_limit

    entry = entries["bldg_wsf3d"]

    def unread():
        pytest.fail("oversize declared body was read")
        yield b"abc"

    with metadata_limit(2), pytest.raises(large.IntakeError, match="body_bytes"):
        large.receive(entry, stream(entry, unread(), 3), Sink())


@pytest.mark.parametrize(
    "declared,body,reason",
    [
        (4, [b"abc"], "length_mismatch"),
        (None, [b""], "empty_body"),
        (True, [b"a"], "declared_length"),
        (-1, [b"a"], "declared_length"),
        (None, ["text"], "stream_chunk"),
    ],
)
def test_stream_refusals(entries, declared, body, reason):
    entry = entries["bldg_wsf3d"]
    with pytest.raises(large.IntakeError, match=reason):
        large.receive(entry, stream(entry, body, declared), Sink())


@pytest.mark.parametrize(
    "text", ["{}", "[{},]", "[{}]x", "[{},", "[true]", '[{"x":', '[{"x":"bad\n"}]']
)
def test_portal_row_stream_refuses_invalid_array(text):
    with pytest.raises(large.IntakeError, match="portal_json"):
        list(large.json_rows(io.StringIO(text)))


def test_portal_row_stream_handles_chunk_boundaries(monkeypatch):
    monkeypatch.setattr(large, "JSON_CHUNK_CHARS", 1)
    rows = [{"text": 'SYN-ع\\"},['}, {"nested": {"list": [1, None]}}]
    assert list(large.json_rows(io.StringIO(json.dumps(rows)))) == rows


@pytest.mark.parametrize("chunk", [1, 65536])
def test_portal_row_limit_is_named(monkeypatch, chunk):
    monkeypatch.setattr(large, "JSON_ROW_CHARS", 8)
    monkeypatch.setattr(large, "JSON_CHUNK_CHARS", chunk)
    source = io.StringIO('[{"long":"SYN-too-long"}]')
    with pytest.raises(large.IntakeError, match="portal_row_bytes"):
        list(large.json_rows(source))
    if chunk == 1:
        assert source.tell() <= 11


def meta(entry):
    return Response(
        entry.url.removesuffix("/exports/json"),
        json.dumps(
            {
                "metas": {
                    "default": {
                        "publisher": entry.publisher,
                        "license": "CC BY",
                        "license_url": "https://creativecommons.org/licenses/by/4.0/",
                        "modified": "2026-11-18",
                    }
                }
            }
        ).encode(),
        (),
    )


def test_imports_archive_exact_bytes_and_validate_every_row(entries, tmp_path):
    entry = replace(
        entries["cus_imp_2019"],
        columns=(("value", "number"),),
        row_count_min=2,
        row_count_max=2,
    )
    raw = b'[ {"value": 1}, {"value": 2} ]'
    result = large.fetch_large(
        entry,
        lambda _url: meta(entry),
        stream(entry, [raw], len(raw)),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _s: None,
    )
    snapshot = read_snapshot(tmp_path / entry.key, result.digest)
    assert snapshot.body == raw
    assert snapshot.sidecar["row_count"] == 2
    assert result.digest == hashlib.sha256(raw).hexdigest()
    assert snapshot.sidecar["portal_licence"] == "CC BY"
    assert not list(tmp_path.glob(".large-*"))


@pytest.mark.parametrize(
    "change,raw,reason",
    [
        ({}, b'[{"value":1}]', "row_count"),
        ({}, b'[{"value":1},{"value":"bad"}]', "schema_retyped"),
        (
            {"publisher": "SYN-other"},
            b'[{"value":1},{"value":2}]',
            "publisher_mismatch",
        ),
    ],
)
def test_invalid_imports_never_publish(entries, tmp_path, change, raw, reason):
    entry = replace(
        entries["cus_imp_2019"],
        columns=(("value", "number"),),
        row_count_min=2,
        row_count_max=2,
    )
    response = meta(replace(entry, **change))
    with pytest.raises(large.IntakeError, match=reason):
        large.fetch_large(
            entry,
            lambda _url: response,
            stream(entry, [raw]),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )
    assert not list((tmp_path / entry.key).rglob("*"))
    assert not list(tmp_path.glob(".large-*"))


@pytest.mark.parametrize(
    "key",
    [
        "bldg_wsf3d",
        "places_ovt/part-00014",
        "bldg_ovt/part-00288",
        "bldg_ovt/part-00384",
        "bldg_ovt/part-00385",
    ],
)
def test_binary_publication_and_prior_snapshot_survive_failure(entries, tmp_path, key):
    entry = entries[key]
    tag = None
    if key != "bldg_wsf3d":
        entry = replace(entry, basis_note="recorded_bytes: 3\nrecorded_etag: SYN-tag")
        tag = '"SYN-tag"'
    result = large.fetch_large(
        entry,
        lambda _u: pytest.fail("metadata for binary"),
        stream(entry, [b"SYN"], 3, tag),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _s: None,
    )
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    with pytest.raises(large.IntakeError, match=r"length_mismatch|size_mismatch"):
        large.fetch_large(
            entry,
            lambda _u: pytest.fail("metadata for binary"),
            stream(entry, [b"SYN"], 4, tag),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )
    assert {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before
    assert read_snapshot(tmp_path / key, result.digest).body == b"SYN"


def test_fetch_row_uses_required_stream(entries, tmp_path):
    from eii_custodian.publicdata.fetch.build import fetch_entry

    entry = entries["bldg_wsf3d"]
    failure = fetch_entry(
        entry,
        lambda _u: pytest.fail("whole body read"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _s: None,
        large_stream=stream(entry, [b"SYN"], 3),
    )
    assert failure is None
    assert (
        read_snapshot(tmp_path / entry.key, hashlib.sha256(b"SYN").hexdigest()).body
        == b"SYN"
    )


def test_places_dispatch_uses_stream(entries, tmp_path):
    from eii_custodian.publicdata.places.fetch import fetch_place_file

    entry = replace(
        entries["places_ovt/part-00014"],
        basis_note="recorded_bytes: 3\nrecorded_etag: SYN-tag",
    )
    fetched, failure = fetch_place_file(
        entry,
        lambda _u: pytest.fail("whole body read"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _s: None,
        large_stream=stream(entry, [b"SYN"], 3, '"SYN-tag"'),
    )
    assert failure is None
    assert fetched.digest == hashlib.sha256(b"SYN").hexdigest()


@pytest.mark.parametrize(
    "years,reason",
    [
        (["2014-01-01", "2018-01-01"], None),
        (["2018-01-01", "2014-01-01"], None),
        (["2014-01-01", "2017-01-01"], "period_last"),
        (["2014-01-01", "2018"], "period_form"),
    ],
)
def test_older_imports_keep_planned_card_input_and_strict_period_gate(
    entries, tmp_path, years, reason
):
    entry = replace(
        entries["trade_ext/qatar-imports-2014-2018"],
        columns=(("year", "string"),),
        row_count_min=2,
        row_count_max=2,
    )
    raw = json.dumps([{"year": year} for year in years]).encode()

    def build():
        return large.fetch_large(
            entry,
            lambda _url: meta(entry),
            stream(entry, [raw]),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )

    if reason:
        with pytest.raises(large.IntakeError, match=reason):
            build()
        assert not list((tmp_path / entry.key).rglob("*.json"))
    else:
        result = build()
        stored = read_snapshot(tmp_path / entry.key, result.digest)
        assert stored.body == raw
        assert stored.sidecar["period_first"] == "2014-01-01"
        assert stored.sidecar["period_last"] == "2018-01-01"


def test_build_passes_stream_to_both_dispatches(entries, tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.build import FetchFailure

    seen = []
    sentinel = object()

    def row(*_args, **kwargs):
        seen.append(kwargs.get("large_stream"))
        return None, FetchFailure(1, "SYN", "", "SYN-stop", "", "")

    monkeypatch.setattr(build, "_fetch_row", row)
    build.run_build(
        [entries["bldg_wsf3d"]],
        lambda _u: pytest.fail("network"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _s: None,
        large_stream=sentinel,
    )

    def place(*_args, **kwargs):
        seen.append(kwargs.get("large_stream"))
        return None, FetchFailure(1, "SYN", "", "SYN-stop", "", "")

    monkeypatch.setattr(build, "fetch_place_file", place)
    build.run_build(
        [entries["places_ovt/part-00014"]],
        lambda _u: pytest.fail("network"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _s: None,
        large_stream=sentinel,
    )
    assert seen == [sentinel, sentinel]


def test_command_supplies_real_stream_without_fetching(tmp_path, monkeypatch):
    from commands import build_public
    from eii_custodian.publicdata.fetch.build import BuildOutcome

    monkeypatch.setattr(build_public, "load_registry", lambda: ())
    monkeypatch.setattr(build_public, "load_policies", lambda: {})
    seen = []

    def run(*_a, **kwargs):
        seen.append(kwargs.get("large_stream"))
        return BuildOutcome((), None)

    monkeypatch.setattr(build_public, "run_build", run)
    assert build_public.run(tmp_path, {}, []) == 0
    assert seen == [build_public.open_https_stream]


def test_stream_source_and_hosts_are_closed(entries):
    entry = entries["bldg_wsf3d"]
    with pytest.raises(large.IntakeError, match="stream_source"):
        large.receive(replace(entry, key="SYN-unknown"), stream(entry, [b"x"]), Sink())
    with pytest.raises(large.IntakeError, match="blocked_host"):
        large.receive(
            replace(entry, url="https://unlisted.invalid/SYN"),
            lambda _url: pytest.fail("blocked host was opened"),
            Sink(),
        )
    with pytest.raises(large.IntakeError, match="blocked_host"):
        large.receive(
            entry, stream(entry, [b"x"], final="https://unlisted.invalid/SYN"), Sink()
        )


def test_publication_rehashes_the_whole_staged_body(entries, tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    entry = entries["cus_imp_2019"]
    entry = replace(
        entry, columns=(("value", "number"),), row_count_min=1, row_count_max=1
    )
    check = large._check_imports

    def tamper(e, staged):
        count = check(e, staged)
        staged.write_bytes(staged.read_bytes().replace(b"1", b"2"))
        return count

    monkeypatch.setattr(large, "_check_imports", tamper)
    with pytest.raises(SnapshotError, match="snapshot_hash_mismatch"):
        large.fetch_large(
            entry,
            lambda _url: meta(entry),
            stream(entry, [b'[{"value":1}]']),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )
    assert not list((tmp_path / entry.key).rglob("*.json"))


def test_changed_import_period_contract_refuses(entries, tmp_path):
    entry = replace(entries["cus_imp_2019"], period_field="year", period_last="2026")
    with pytest.raises(large.IntakeError, match="stream_contract_changed"):
        large.fetch_large(
            entry,
            lambda _url: meta(entry),
            stream(entry, [b"[]"]),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )


_JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=20),
    lambda child: (
        st.lists(child, max_size=3)
        | st.dictionaries(st.text(max_size=10), child, max_size=3)
    ),
    max_leaves=12,
)


@given(
    st.lists(
        st.dictionaries(st.text(max_size=10), _JSON_VALUES, max_size=3), max_size=5
    ),
    st.integers(min_value=1, max_value=33),
)
def test_json_rows_matches_stdlib_oracle_for_every_chunk_boundary(rows, chunk_size):
    text = json.dumps(rows)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(large, "JSON_CHUNK_CHARS", chunk_size)
        assert list(large.json_rows(io.StringIO(text))) == json.loads(text)


def test_lower_source_cap_counts_undeclared_body(entries):
    from eii_custodian.publicdata.fetch.transport import metadata_limit

    entry = entries["bldg_wsf3d"]
    sink = Sink()
    with metadata_limit(2), pytest.raises(large.IntakeError, match="body_bytes"):
        large.receive(entry, stream(entry, [b"a", b"bc"]), sink)
    assert sink.count == 1


@pytest.mark.parametrize(
    "tag,reason",
    [(None, "etag_unobserved"), ('W/"SYN-tag"', "etag_weak"), ("SYN-tag", "etag_form")],
)
def test_stream_retains_existing_etag_refusals(entries, tag, reason):
    entry = replace(
        entries["places_ovt/part-00014"],
        basis_note="recorded_bytes: 1\nrecorded_etag: SYN-tag",
    )
    with pytest.raises(large.IntakeError, match=reason):
        large.receive(entry, stream(entry, [b"x"], 1, tag), Sink())


@pytest.mark.parametrize(
    "note,reason", [("", "recorded_size"), ("recorded_bytes: 2", "recorded_etag")]
)
def test_stream_retains_existing_recorded_declaration_refusals(entries, note, reason):
    entry = replace(entries["places_ovt/part-00014"], basis_note=note)
    with pytest.raises(large.IntakeError, match=reason):
        large.receive(entry, stream(entry, [b"xx"], 2), Sink())


def test_undeclared_overture_short_body_refuses(entries):
    entry = replace(
        entries["places_ovt/part-00014"],
        basis_note="recorded_bytes: 2\nrecorded_etag: SYN-tag",
    )
    with pytest.raises(large.IntakeError, match="size_mismatch"):
        large.receive(entry, stream(entry, [b"x"], etag='"SYN-tag"'), Sink())


def test_older_imports_refuse_undeclared_public_split(entries, tmp_path):
    entry = replace(
        entries["trade_ext/qatar-imports-2014-2018"],
        columns=(("year", "string"),),
        row_count_min=1,
        row_count_max=1,
    )
    with pytest.raises(large.IntakeError, match="public_split_undeclared"):
        large.fetch_large(
            entry,
            lambda _url: meta(entry),
            stream(entry, [b'[{"year":"2018-01-01","gender":"SYN"}]']),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )
    assert not list((tmp_path / entry.key).rglob("*.json"))


def test_default_dispatch_keeps_legacy_callback_signatures(
    entries, tmp_path, monkeypatch
):
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.build import FetchFailure

    seen = []

    def old_row(entry, transport, cache, clock, sleep, token, *, registry_entries):
        seen.append("row")
        return None, FetchFailure(1, "SYN", "", "SYN-stop", "", "")

    def old_places(entry, transport, cache, clock, sleep):
        seen.append("places")
        return None, FetchFailure(1, "SYN", "", "SYN-stop", "", "")

    monkeypatch.setattr(build, "_fetch_row", old_row)
    monkeypatch.setattr(build, "fetch_place_file", old_places)
    for key in ("bldg_wsf3d", "places_ovt/part-00014"):
        result = build.run_build(
            [entries[key]],
            lambda _u: pytest.fail("network"),
            tmp_path,
            lambda: "2026-11-18T00:00:00Z",
            lambda _s: None,
        )
        assert result.failure.check == "SYN-stop"
    assert seen == ["row", "places"]
