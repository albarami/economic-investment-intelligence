"""BACI offline dispatch and complete archive contract."""

from pathlib import Path

import pytest
from custodian.tests.fixtures.baci.invented import entry, metadata, stream

from eii_custodian.publicdata.fetch.build import run_build


def test_baci_complete_archive(tmp_path: Path) -> None:
    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.baci.config import Config
    from eii_custodian.publicdata.baci.contracts import read_selected

    outcome = run_build(
        [entry()],
        metadata,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        stream_transport=stream,
        baci_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is None
    assert outcome.manifests["cepii_baci"]
    release = read_selected(tmp_path, outcome.manifests["cepii_baci"])
    assert len(release.trade) == 3
    assert len(release.country) == 2
    assert len(release.product) == 1
    assert release.trade[0].value == "123456789012.345600"
    assert release.trade[1].quantity is None
    assert release.trade[0].quantity == "0"
    assert release.manifest["excluded"] == 1
    assert len(release.fact_lineage) == 3


def test_baci_stream_hosts():
    import pytest

    from eii_custodian.publicdata.fetch.transport import (
        TransportFault,
        open_https_stream,
    )

    for url in ("https://unlisted.invalid/invented", "http://www.data.gov.qa/invented"):
        with pytest.raises(TransportFault):
            with open_https_stream(url):
                raise AssertionError("unreviewed target opened")


def build(
    tmp_path,
    *,
    config=None,
    source=None,
    byte_transport=metadata,
    stream_transport=stream,
):
    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.baci.config import Config

    return run_build(
        [entry() if source is None else source],
        byte_transport,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        stream_transport=stream_transport,
        baci_config=Config.from_mapping(configuration() if config is None else config),
    )


def test_baci_pending_state(tmp_path):
    from eii_custodian.publicdata.fetch.registry import load_registry

    pending = next(e for e in load_registry() if e.source_id == "cepii_baci")

    def forbidden(_):
        raise AssertionError("pending source requested")

    result = run_build(
        [pending], forbidden, tmp_path, lambda: "2026-11-16T00:00:00Z", lambda _: None
    )
    assert not result.manifests
    assert any("baci_metadata_unconfirmed" in line for line in result.lines)


def test_baci_transport_failure(tmp_path):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from eii_custodian.publicdata.fetch.transport import ATTEMPT_LIMIT

    calls = []
    closes = []

    def chunks():
        yield b"invented-partial"
        raise OSError("invented-response-marker")

    @contextmanager
    def broken(url):
        calls.append(url)
        try:
            yield SimpleNamespace(
                final_url=url, hops=(), declared_length=None, chunks=chunks()
            )
        finally:
            closes.append(True)

    result = build(tmp_path, stream_transport=broken)
    assert result.failure.check == "network_exhausted"
    assert len(calls) == len(closes) == ATTEMPT_LIMIT
    assert not list((tmp_path / "cepii_baci").glob("*.manifest.json"))
    assert not list((tmp_path / "cepii_baci").glob(".stage-*"))
    assert "invented-response-marker" not in repr(result)


def test_baci_safe_failure(tmp_path):
    def broken(_):
        raise RuntimeError("invented-response-marker")

    result = build(tmp_path, byte_transport=broken)
    assert result.failure is not None
    assert "invented-response-marker" not in repr(result)


def test_baci_manifest_atomicity(tmp_path, monkeypatch):
    from eii_custodian.publicdata.baci import fetch
    from eii_custodian.publicdata.baci.contracts import read_selected

    first = build(tmp_path)
    digest = first.manifests["cepii_baci"]
    original = fetch._publish
    for boundary in range(1, 6):
        calls = []

        def interrupted(source, destination, calls=calls, boundary=boundary):
            calls.append(destination)
            if len(calls) == boundary:
                raise OSError("invented-interruption")
            original(source, destination)

        with monkeypatch.context() as patch:
            patch.setattr(fetch, "_publish", interrupted)
            result = build(tmp_path)
        assert result.failure is not None
        assert result.manifests == {}
        assert len(read_selected(tmp_path, digest).trade) == 3
        assert list((tmp_path / "cepii_baci").glob("*.manifest.json")) == [
            tmp_path / "cepii_baci" / f"{digest}.manifest.json"
        ]


def test_baci_command_injection(tmp_path, monkeypatch, capsys):
    from custodian.tests.fixtures.baci.invented import configuration

    import commands.build_public as build_public
    import eii_custodian.publicdata.fetch.build as module
    from eii_custodian.publicdata.baci.config import Config

    monkeypatch.setattr(build_public, "load_registry", lambda: (entry(),))
    monkeypatch.setattr(
        module, "load_config", lambda: Config.from_mapping(configuration())
    )

    def forbidden(_):
        raise AssertionError("real stream selected")

    monkeypatch.setattr(build_public, "open_https_stream", forbidden)
    assert (
        build_public.run(tmp_path, {}, [], transport=metadata, sleep=lambda _: None)
        == 1
    )
    assert "stream_transport_missing" in capsys.readouterr().out
    assert (
        build_public.run(
            tmp_path,
            {},
            [],
            transport=metadata,
            sleep=lambda _: None,
            stream_transport=stream,
        )
        == 0
    )


def test_baci_access_obstacles(tmp_path):
    from custodian.tests.fixtures.baci.invented import configuration

    for obstacle in ("registration", "sign_in", "robot_check", "paid_tier"):
        config = configuration()
        config["access"] = obstacle

        def forbidden(_):
            raise AssertionError("obstacle requested")

        result = build(tmp_path / obstacle, config=config, byte_transport=forbidden)
        assert result.failure.check == "access_obstacle"
        assert result.manifests == {}


def test_baci_terms_state(tmp_path):
    from dataclasses import replace

    for index, words in enumerate(
        ("terms to be read", "invented absent terms", "invented prohibitive terms")
    ):
        result = build(
            tmp_path / str(index), source=replace(entry(), terms_words=words)
        )
        assert result.failure is None
    result = build(
        tmp_path / "changed",
        byte_transport=lambda url: type(metadata(url))(
            url, b"invented changed metadata", ()
        ),
    )
    assert result.failure.check == "metadata_changed_review_needed"


def test_baci_stream_bounds(tmp_path):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from custodian.tests.fixtures.baci.invented import archive, configuration

    body = archive()
    for index, (low, high, declared, payload, reason) in enumerate(
        (
            (len(body), len(body), len(body), body, None),
            (len(body) + 1, len(body) + 1, None, body, "archive_bytes"),
            (1, len(body) - 1, None, body, "archive_bytes"),
            (1, len(body) + 1, len(body) + 1, body, "length_mismatch"),
            (1, len(body), len(body), body[:-1], "length_mismatch"),
        )
    ):
        config = configuration()
        config["archive_bytes"] = [low, high]

        @contextmanager
        def supplied(url, declared=declared, payload=payload):
            yield SimpleNamespace(
                final_url=url, hops=(), declared_length=declared, chunks=iter([payload])
            )

        result = build(tmp_path / str(index), config=config, stream_transport=supplied)
        assert (result.failure.check if result.failure else None) == reason
        if reason:
            assert result.manifests == {}


def test_baci_stream_target_metadata(tmp_path):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from custodian.tests.fixtures.baci.invented import archive

    for index, (final, hops) in enumerate(
        (
            ("https://unlisted.invalid/invented", ()),
            (entry().url, ("https://unlisted.invalid/invented",)),
            ("http://www.data.gov.qa/invented", ()),
        )
    ):

        @contextmanager
        def supplied(_, final=final, hops=hops):
            yield SimpleNamespace(
                final_url=final,
                hops=hops,
                declared_length=None,
                chunks=iter([archive()]),
            )

        result = build(tmp_path / str(index), stream_transport=supplied)
        assert result.failure.check == "blocked_host"
        assert result.manifests == {}


def test_baci_credential_address_is_refused_before_opener(monkeypatch):
    import pytest

    import eii_custodian.publicdata.fetch.transport as transport

    def forbidden(*args):
        raise AssertionError("opener constructed")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)
    address = "https://" + "invented-user" + "@www.data.gov.qa/invented"
    with pytest.raises(transport.TransportFault):
        with transport.open_https_stream(address):
            raise AssertionError("unsafe address opened")


@pytest.fixture(autouse=True)
def no_real_opener(monkeypatch):
    import eii_custodian.publicdata.fetch.transport as transport

    def forbidden(*args, **kwargs):
        raise AssertionError("BACI test attempted real opener")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)


def test_baci_dispatch_isolated(tmp_path):
    from dataclasses import replace

    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.baci.config import Config
    from eii_custodian.publicdata.fetch.transport import Response

    other = replace(
        entry(),
        source_id="invented_other",
        key="invented_other",
        url="https://www.data.gov.qa/invented-other",
        row_count_min=1,
        row_count_max=1,
        columns=(),
        period_field="",
        terms_url="",
    )

    def combined(url):
        return Response(url, b"[{}]", ()) if url == other.url else metadata(url)

    alone = run_build(
        [other],
        combined,
        tmp_path / "alone",
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
    )
    joined = run_build(
        [other, entry()],
        combined,
        tmp_path / "joined",
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        stream_transport=stream,
        baci_config=Config.from_mapping(configuration()),
    )
    assert alone.failure is joined.failure is None
    assert [line for line in alone.lines if "invented_other" in line] == [
        line for line in joined.lines if "invented_other" in line
    ]
    files = sorted(
        p for p in (tmp_path / "alone/invented_other").rglob("*") if p.is_file()
    )
    assert files
    for path in files:
        assert (
            path.read_bytes()
            == (
                tmp_path
                / "joined/invented_other"
                / path.relative_to(tmp_path / "alone/invented_other")
            ).read_bytes()
        )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("publisher", "invented-other", "publisher"),
        ("licence_basis", "", "licence_basis"),
        ("terms_read_on", "2026-99-99", "terms_date"),
        ("terms_words", "", "terms_metadata"),
        ("commit_allowed", True, "registry_policy"),
        ("nightly_live_fetch", False, "registry_policy"),
        ("row_count_min", 3, "raw_bounds"),
        ("period_first", "2090", "period_bounds"),
        ("landing_url", "", "page"),
        ("fetch_host", "unlisted.invalid", "blocked_host"),
        ("release_tables", (), "release_contract"),
    ],
)
def test_baci_entry_plants(tmp_path, field, value, reason):
    from dataclasses import replace

    result = build(tmp_path, source=replace(entry(), **{field: value}))
    assert result.failure.check == reason
    assert not result.manifests


def test_baci_empty_userinfo_rejected():
    from eii_custodian.publicdata.baci.config import safe_url

    assert not safe_url("https://" + "@www.data.gov.qa/invented")


def test_baci_stream_stops_at_upper_bound(tmp_path):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from custodian.tests.fixtures.baci.invented import configuration

    config = configuration()
    config["archive_bytes"] = [1, 200]

    def chunks():
        yield b"x" * 201
        raise AssertionError("consumed beyond declared maximum")

    @contextmanager
    def supplied(url):
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=None, chunks=chunks()
        )

    result = build(tmp_path, config=config, stream_transport=supplied)
    assert result.failure.check == "archive_bytes"


def test_baci_redirect_exact_review_before_contact(monkeypatch):
    from http.client import HTTPMessage
    from io import BytesIO

    import eii_custodian.publicdata.fetch.transport as transport

    reviewed = (entry().url,)

    def forbidden(*args):
        raise AssertionError("redirect target contacted")

    monkeypatch.setattr(
        transport.urllib.request.HTTPRedirectHandler, "redirect_request", forbidden
    )
    guard = transport._redirect_guard([], strict=True, reviewed_urls=reviewed)()
    request = transport.urllib.request.Request(entry().url)
    with pytest.raises(transport.TransportFault):
        guard.redirect_request(
            request,
            BytesIO(),
            302,
            "invented",
            HTTPMessage(),
            "https://www.data.gov.qa/unreviewed-invented",
        )


def test_baci_production_transports_bind_reviewed_urls(tmp_path, monkeypatch):
    from custodian.tests.fixtures.baci.invented import configuration

    import commands.build_public as build_public
    from eii_custodian.publicdata.baci.config import Config

    config = Config.from_mapping(configuration())
    observed = []

    def byte(url, *, reviewed_urls):
        observed.append(reviewed_urls)
        return metadata(url)

    def chunks(url, *, reviewed_urls):
        observed.append(reviewed_urls)
        return stream(url)

    monkeypatch.setattr(build_public, "load_registry", lambda: (entry(),))
    monkeypatch.setattr(build_public, "load_config", lambda: config)
    monkeypatch.setattr(build_public, "open_https", byte)
    monkeypatch.setattr(build_public, "open_https_stream", chunks)
    assert build_public.run(tmp_path, {}, [], sleep=lambda _: None) == 0
    assert observed == [config.reviewed_urls, config.reviewed_urls]


def test_baci_incomplete_http_read_is_bounded(tmp_path):
    from contextlib import contextmanager
    from http.client import IncompleteRead
    from types import SimpleNamespace

    from eii_custodian.publicdata.fetch.transport import ATTEMPT_LIMIT

    attempts = []

    def chunks():
        yield b"invented"
        raise IncompleteRead(b"invented-partial")

    @contextmanager
    def incomplete(url):
        attempts.append(url)
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=None, chunks=chunks()
        )

    result = build(tmp_path, stream_transport=incomplete)
    assert result.failure.check == "network_exhausted"
    assert len(attempts) == ATTEMPT_LIMIT


def test_baci_cache_creation_failure_is_safe(tmp_path, monkeypatch):
    original = Path.mkdir

    def refuse(path, *args, **kwargs):
        if path.name == "cepii_baci":
            raise OSError("invented-write-error")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", refuse)
    result = build(tmp_path)
    assert result.failure.check == "write_or_stream_failed"
    assert "invented-write-error" not in repr(result)


@pytest.mark.parametrize("phase", ["metadata", "archive"])
def test_baci_transport_refusal_is_not_retried(tmp_path, phase):
    from eii_custodian.publicdata.fetch.transport import TransportFault

    calls = []

    def blocked(url):
        calls.append(url)
        raise TransportFault("blocked_host", "")

    result = build(
        tmp_path,
        byte_transport=blocked if phase == "metadata" else metadata,
        stream_transport=blocked if phase == "archive" else stream,
    )
    assert result.failure.check == "blocked_host"
    assert len(calls) == 1


def _baci_refused_fetch(
    tmp_path,
    reason,
    *,
    source=None,
    config=None,
    byte_transport=metadata,
    stream_transport=stream,
    clock=lambda: "2026-11-16T00:00:00Z",
    payload=b"Invented publisher page",
):
    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.fetch import fetch_baci

    source = entry() if source is None else source
    config = Config.from_mapping(configuration() if config is None else config)
    directory = tmp_path / "cepii_baci"
    before = {p.name: p.read_bytes() for p in directory.glob("*.manifest.json")}
    with pytest.raises(BaciError, match=f"^{reason}$") as caught:
        fetch_baci(
            source,
            config,
            byte_transport,
            stream_transport,
            tmp_path,
            clock,
            lambda _: None,
        )
    assert str(caught.value) == reason
    assert "invented-secret-marker" not in repr(caught.value)
    assert payload.decode() not in repr(caught.value)
    assert {p.name: p.read_bytes() for p in directory.glob("*.manifest.json")} == before
    # A different source id cannot enter BACI dispatch; exercise it directly above.
    if source.source_id == "cepii_baci":
        result = run_build(
            [source],
            byte_transport,
            tmp_path,
            clock,
            lambda _: None,
            stream_transport=stream_transport,
            baci_config=config,
        )
        assert result.failure is not None
        assert result.failure.check == reason
        assert result.manifests == {}
        assert "invented-secret-marker" not in repr(result)
        assert payload.decode() not in repr(result)
        assert {
            p.name: p.read_bytes() for p in directory.glob("*.manifest.json")
        } == before
    assert not list(directory.glob(".stage-*"))


@pytest.mark.parametrize("field", ["source_id", "key"])
def test_baci_entry_source_id_guard(tmp_path, field):
    from dataclasses import replace

    source = replace(entry(), **{field: "invented-other"})
    _baci_refused_fetch(tmp_path, "source_id", source=source)


@pytest.mark.parametrize("basis,record", [("owner_decision", ""), ("dataset", "0026")])
def test_baci_entry_decision_record_guard(tmp_path, basis, record):
    from dataclasses import replace

    _baci_refused_fetch(
        tmp_path,
        "licence_basis",
        source=replace(entry(), licence_basis=basis, decision_record=record),
    )


def test_baci_entry_terms_url_guard(tmp_path):
    from dataclasses import replace

    source = replace(entry(), terms_url=entry().url + "-unreviewed")

    def forbidden(_):
        raise AssertionError("metadata requested before terms URL approval")

    _baci_refused_fetch(
        tmp_path, "blocked_host", source=source, byte_transport=forbidden
    )


def test_baci_metadata_bytes_guard(tmp_path):
    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.fetch.transport import Response

    config = configuration()
    payload = b"invented-secret-marker " + b"x" * config["archive_bytes"][1]
    _baci_refused_fetch(
        tmp_path,
        "metadata_bytes",
        byte_transport=lambda url: Response(url, payload, ()),
        payload=payload,
    )


@pytest.mark.parametrize(
    "marker", ["registration required", "sign in", "robot check", "paid tier"]
)
def test_baci_metadata_response_obstacle_guard(tmp_path, marker):
    from hashlib import sha256

    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.fetch.transport import Response

    config = configuration()
    payload = f"Invented {marker.upper()} invented-secret-marker".encode()
    config["page_sha256"] = sha256(payload).hexdigest()
    _baci_refused_fetch(
        tmp_path,
        "access_obstacle",
        config=config,
        byte_transport=lambda url: Response(url, payload, ()),
        payload=payload,
    )


@pytest.mark.parametrize("length", [True, "invented-secret-marker"])
def test_baci_declared_length_type_guard(tmp_path, length):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from custodian.tests.fixtures.baci.invented import archive

    @contextmanager
    def supplied(url):
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=length, chunks=iter([archive()])
        )

    _baci_refused_fetch(tmp_path, "declared_length", stream_transport=supplied)


@pytest.mark.parametrize("kind", ["text", "bytearray", "oversized"])
def test_baci_stream_chunk_guard(tmp_path, kind):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from custodian.tests.fixtures.baci.invented import configuration

    payload = b"invented-secret-marker"
    chunk = {
        "text": payload.decode(),
        "bytearray": bytearray(payload),
        "oversized": payload + b"x" * 65536,
    }[kind]
    config = configuration()
    config["archive_bytes"] = [1, 131072]

    @contextmanager
    def supplied(url):
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=None, chunks=iter([chunk])
        )

    _baci_refused_fetch(
        tmp_path,
        "stream_chunk",
        config=config,
        stream_transport=supplied,
        payload=payload,
    )


def test_baci_publish_cache_integrity_guard(tmp_path):
    import json

    from eii_custodian.publicdata.baci.contracts import read_selected

    original = build(tmp_path)
    assert original.failure is None
    selected = original.manifests["cepii_baci"]
    assert len(read_selected(tmp_path, selected).trade) == 3
    directory = tmp_path / "cepii_baci"
    manifest = json.loads((directory / f"{selected}.manifest.json").read_text())
    cached = directory / f"{manifest['archive_sha256']}.zip"
    payload = b"invented-secret-marker invented-cache-payload"
    cached.write_bytes(payload)
    _baci_refused_fetch(tmp_path, "cache_integrity", payload=payload)
    assert cached.read_bytes() == payload


@pytest.mark.parametrize("clock", ["2026-1-16T00:00:00Z", "invented-secret-marker"])
def test_baci_retrieval_clock_guard(tmp_path, clock):
    _baci_refused_fetch(tmp_path, "retrieval_date", clock=lambda: clock)


def test_baci_publisher_archive_checksum_guard(tmp_path):
    from custodian.tests.fixtures.baci.invented import configuration

    config = configuration()
    config["publisher_sha256"] = "f" * 64
    _baci_refused_fetch(tmp_path, "archive_checksum", config=config)


def test_baci_terms_unread_network_path(tmp_path):
    import json
    from dataclasses import replace

    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.baci.contracts import read_selected
    from eii_custodian.publicdata.fetch.transport import ATTEMPT_LIMIT

    source = replace(entry(), terms_url=entry().url + "-terms")
    config = configuration()
    config["reviewed_urls"].append(source.terms_url)
    attempts = []
    payload = "invented-secret-marker invented-terms-payload"

    def unread(url):
        if url == source.terms_url:
            attempts.append(url)
            raise OSError(payload)
        return metadata(url)

    result = build(tmp_path, source=source, config=config, byte_transport=unread)
    assert result.failure is None
    assert len(attempts) == ATTEMPT_LIMIT
    selected = result.manifests["cepii_baci"]
    release = read_selected(tmp_path, selected)
    assert release.manifest["terms_unread"] == "network_exhausted"
    assert release.manifest["receipt"]["terms_sha256"] is None
    assert any("network_exhausted" in line for line in result.lines)
    assert "invented-secret-marker" not in repr(result)
    assert payload not in repr(result)
    assert payload not in json.dumps(release.manifest)
    assert list((tmp_path / "cepii_baci").glob("*.manifest.json")) == [
        tmp_path / "cepii_baci" / f"{selected}.manifest.json"
    ]


def test_baci_terms_unread_refuses_other_errors(tmp_path):
    from dataclasses import replace

    from custodian.tests.fixtures.baci.invented import configuration

    from eii_custodian.publicdata.fetch.transport import Response

    source = replace(entry(), terms_url=entry().url + "-terms")
    config = configuration()
    config["reviewed_urls"].append(source.terms_url)
    payload = b"Invented sign in invented-secret-marker"

    def obstacle(url):
        return Response(url, payload, ()) if url == source.terms_url else metadata(url)

    _baci_refused_fetch(
        tmp_path,
        "access_obstacle",
        source=source,
        config=config,
        byte_transport=obstacle,
        payload=payload,
    )
