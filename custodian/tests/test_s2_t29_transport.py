"""Invented host, pin and capture plants; no source connection."""

import hashlib
import ssl
from dataclasses import replace

import pytest

from eii_custodian.publicdata.fetch.transport import TransportFault

URL = "https://www.data.gov.qa/syn-page"
STAMP = "2024-02-03T00:00:00Z"


def pin():
    from eii_custodian.publicdata.fetch.certificate_pins import Pin

    der = b"SYN-intermediate"
    return Pin("www.data.gov.qa", hashlib.sha256(der).hexdigest(), der, True)


def test_pin_wrong_host_first():
    from eii_custodian.publicdata.fetch.certificate_pins import verified_context

    with pytest.raises(ValueError, match="certificate_host_mismatch"):
        verified_context("www.data.qa", pin())


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("wrong", "certificate_chain_incomplete"),
        ("absent", "certificate_chain_incomplete"),
        ("approval", "certificate_review_pending"),
        ("disabled", "tls_verification_disabled"),
    ],
)
def test_tls_pin_contract(plant, reason):
    from eii_custodian.publicdata.fetch.certificate_pins import verified_context

    value = pin()
    context = ssl.create_default_context()
    if plant == "wrong":
        value = replace(value, der=b"SYN-wrong")
    if plant == "absent":
        value = replace(value, sha256="[LEAD: evidence 2]")
    if plant == "approval":
        value = replace(value, approved=False)
    if plant == "disabled":
        context.check_hostname = False
    with pytest.raises(ValueError, match=reason):
        verified_context(value.host, value, context=context)


def test_verified_context_loads_der(monkeypatch):
    from eii_custodian.publicdata.fetch.certificate_pins import verified_context

    loaded = []

    class Context:
        verify_mode = ssl.CERT_REQUIRED
        check_hostname = True
        verify_flags = 0

        def load_verify_locations(self, *, cadata):
            loaded.append(cadata)

    context = Context()
    assert verified_context(pin().host, pin(), context=context) is context
    assert loaded == [ssl.DER_cert_to_PEM_cert(pin().der)]


def capture(body=b"SYN-page"):
    from eii_custodian.publicdata.fetch.certificate_pins import Capture

    return Capture(
        body,
        URL,
        URL,
        (),
        "SYN-browser",
        STAMP,
        hashlib.sha256(body).hexdigest(),
        pin(),
        True,
        "visitor",
    )


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("hash", "capture_hash_mismatch"),
        ("date", "snapshot_date_missing"),
        ("tool", "capture_evidence_missing"),
        ("pin", "certificate_chain_incomplete"),
        ("redirect", "certificate_host_mismatch"),
        ("offhost", "blocked_host"),
        ("disabled", "tls_verification_disabled"),
        ("login", "unavailable"),
        ("paywall", "unavailable"),
        ("robot check", "unavailable"),
        ("keyed", "unavailable"),
    ],
)
def test_capture_refusals(monkeypatch, plant, reason):
    from eii_custodian.publicdata.fetch import certificate_pins as module

    monkeypatch.setattr(
        module,
        "verified_context",
        lambda host, item, **kw: module.validate_pin(host, item),
    )
    value = capture()
    changes = {
        "hash": {"body": b"SYN-tamper"},
        "date": {"captured_utc": ""},
        "tool": {"tool": ""},
        "pin": {"pin": replace(pin(), der=b"")},
        "redirect": {"hops": ("https://www.data.qa/syn-page",)},
        "offhost": {"final_url": "https://example.invalid/syn-page"},
        "disabled": {"tls_verified": False},
    }
    value = replace(value, **changes.get(plant, {"access": plant}))
    with pytest.raises(ValueError, match=reason):
        module.admit_capture(value, URL)


def test_capture_success(monkeypatch):
    from eii_custodian.publicdata.fetch import certificate_pins as module

    monkeypatch.setattr(
        module,
        "verified_context",
        lambda host, item, **kw: module.validate_pin(host, item),
    )
    response, evidence = module.admit_capture(capture(), URL)
    assert response.body == b"SYN-page"
    assert evidence["initial_url"] == URL
    assert evidence["tool"] == "SYN-browser"
    assert evidence["intermediate_sha256"] == pin().sha256


def test_school_reset_dated_failure(tmp_path):
    from custodian.tests.test_s2_t29_pages import page_entry, review

    from eii_custodian.publicdata.fetch.page_records import PageError, fetch_page

    calls = []

    def reset(url):
        calls.append(url)
        raise TransportFault("unreachable", url)

    row = replace(
        page_entry(),
        source_id="schools_private_directory",
        key="schools_private_directory",
    )
    with pytest.raises(PageError, match="access_failed"):
        fetch_page(
            row,
            reset,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=review(row),
            pin=pin(),
        )
    import json

    records = list((tmp_path / row.key / "failures").rglob("*.json"))
    assert records
    record = next(
        json.loads(p.read_text())
        for p in records
        if "attempted_utc" in json.loads(p.read_text())
    )
    assert record["attempted_utc"] == STAMP
    assert record["reason"] == "access_failed"
    assert calls and all(url == URL for url in calls)
    assert not list((tmp_path / row.key).glob("index/*"))


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("login", "unavailable"),
        ("paywall", "unavailable"),
        ("robot check", "unavailable"),
        ("keyed", "unavailable"),
        ("hash", "capture_hash_mismatch"),
        ("date", "snapshot_date_missing"),
        ("tls", "tls_verification_disabled"),
        ("pin", "certificate_chain_incomplete"),
    ],
)
def test_school_capture_keeps_typed_failure(tmp_path, plant, reason):
    import json

    from custodian.tests.test_s2_t29_pages import page_entry, review

    from eii_custodian.publicdata.fetch.page_records import PageError, fetch_page

    row = replace(
        page_entry(),
        source_id="schools_private_directory",
        key="schools_private_directory",
    )
    changes = {
        "hash": {"body": b"SYN-tamper"},
        "date": {"captured_utc": ""},
        "tls": {"tls_verified": False},
        "pin": {"pin": replace(pin(), der=b"")},
    }
    captured = replace(capture(), **changes.get(plant, {"access": plant}))

    def reset(url):
        raise TransportFault("unreachable", url)

    with pytest.raises(PageError, match=f"^{reason}$"):
        fetch_page(
            row,
            reset,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=review(row),
            pin=pin(),
            capture=captured,
        )
    records = [
        json.loads(path.read_text())
        for path in (tmp_path / row.key / "failures").rglob("*.json")
    ]
    failure = next(record for record in records if "attempted_utc" in record)
    assert failure["reason"] == reason
    assert failure["attempted_utc"] == STAMP
    assert not (tmp_path / row.key / "raw").exists()
    assert not (tmp_path / row.key / "index").exists()


def test_pin_other_host_redirect_before_send(monkeypatch):
    from email.message import Message
    from urllib.request import Request

    from eii_custodian.publicdata.fetch import transport as module
    from eii_custodian.publicdata.fetch.certificate_pins import page_transport

    guard = module._redirect_guard([])()
    with page_transport(pin()):
        with pytest.raises(ValueError, match="certificate_host_mismatch"):
            guard.redirect_request(
                Request(URL), None, 302, "", Message(), "https://www.data.qa/syn-page"
            )


def test_browser_agent_and_bounded_normal_seam(monkeypatch):
    from eii_custodian.publicdata.fetch import transport as module
    from eii_custodian.publicdata.fetch.certificate_pins import page_transport

    captured = []

    class Body:
        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def geturl(self):
            return URL

        def read(self, limit=None):
            captured.append(limit)
            return b"SYN-body"

    class Opener:
        def open(self, request, timeout):
            captured.append(request.get_header("User-agent"))
            assert not request.has_header("Authorization")
            return Body()

    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *args: Opener())
    with page_transport(None, browser=True), module.metadata_limit(9):
        assert module.open_https(URL).body == b"SYN-body"
    assert captured == ["Mozilla/5.0", 10]


def test_build_public_joined_dispatch(tmp_path, monkeypatch):
    from commands import build_public
    from eii_custodian.publicdata.fetch.registry import load_registry

    # The real joined command omits an Earthdata granule without a token, then
    # refuses an unbound Comtrade adapter. No lazy slot can be read on injection.
    entries = load_registry()
    granule = next(
        e for e in entries if e.source_id == "ntl_blackmarble" and "/" in e.key
    )
    trade = next(e for e in entries if e.source_id == "un_comtrade")
    monkeypatch.setattr(
        build_public,
        "load_registry",
        lambda: (replace(granule, skip_reason=""), replace(trade, skip_reason="")),
    )

    class Environment(dict):
        def __getitem__(self, key):
            if "COMTRADE" in key:
                pytest.fail("injected transport read a slot")
            return super().__getitem__(key)

    def forbidden(url):
        pytest.fail("unbound command made a request")

    assert (
        build_public.run(
            tmp_path, Environment(), [], transport=forbidden, sleep=lambda _: None
        )
        == 1
    )
    import json

    log = json.loads((tmp_path / "data/public_cache/build-log.json").read_text())
    assert any("OMIT ntl_blackmarble" in line for line in log["lines"])
    assert any("transport_uninjected" in line for line in log["lines"])


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("pending", "certificate_chain_incomplete"),
        ("escape", "intake_path_refused"),
        ("approval", "certificate_review_pending"),
        ("wrong", "certificate_chain_incomplete"),
    ],
)
def test_reviewed_pin_intake(tmp_path, plant, reason):
    from eii_custodian.publicdata.fetch.certificate_pins import load_pin

    folder = tmp_path / "intake" / "monaqasat_classified"
    folder.mkdir(parents=True)
    (folder / "syn.der").write_bytes(pin().der)
    config = {
        "host": pin().host,
        "sha256": pin().sha256,
        "file": "syn.der",
        "security_review": "APPROVED",
    }
    if plant == "pending":
        config = "[LEAD: evidence 2]"
    if plant == "escape":
        config["file"] = "../syn.der"
    if plant == "approval":
        config["security_review"] = "PENDING"
    if plant == "wrong":
        config["sha256"] = "SYN-wrong"
    with pytest.raises(ValueError, match=reason):
        load_pin(tmp_path, "monaqasat_classified", config)


def test_pin_requires_root_chain(monkeypatch):
    from eii_custodian.publicdata.fetch.certificate_pins import verified_context

    class Context:
        verify_mode = ssl.CERT_REQUIRED
        check_hostname = True
        verify_flags = ssl.VERIFY_X509_PARTIAL_CHAIN

        def load_verify_locations(self, *, cadata):
            pass

    context = Context()
    verified_context(pin().host, pin(), context=context)
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


@pytest.mark.parametrize("source", ["baci", "gravity", "atlas"])
@pytest.mark.parametrize("plant", ["none", "config", "stream"])
def test_build_public_joined_trade_bindings(
    tmp_path, monkeypatch, capsys, source, plant
):
    """T18 keeps the real command closure, dispatch and source parsers."""
    from custodian.tests.test_gravity_atlas_review import CLOCK, modules

    from commands import build_public as command
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.transport import Response

    m = modules(source)
    entry = m.fixture.entry()
    config = m.config.Config.from_mapping(m.fixture.configuration())
    loader = "load_config" if source == "baci" else "load_" + source + "_config"
    error = getattr(m.config, source.capitalize() + "Error")
    calls = []

    def load():
        if plant == "config":
            raise error("SYN-configuration-secret")
        return config

    def metadata(url, *, reviewed_urls=None, **kwargs):
        assert reviewed_urls == config.reviewed_urls
        assert url in reviewed_urls
        calls.append(("metadata", url))
        response = m.fixture.metadata(url)
        return Response(url, response.body, ())

    def stream(url, *, reviewed_urls):
        assert reviewed_urls == config.reviewed_urls
        assert url in reviewed_urls
        calls.append(("stream", url))
        return m.fixture.stream(url)

    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    monkeypatch.setattr(command, "utc_now", lambda: CLOCK)
    monkeypatch.setattr(command, "load_policies", lambda: {})
    monkeypatch.setattr(command, loader, load)
    monkeypatch.setattr(build, loader, load)
    monkeypatch.setattr(command, "open_https", metadata)
    monkeypatch.setattr(command, "open_https_stream", stream)
    # Injecting a byte seam deliberately leaves the stream/config unbound;
    # run_build loads the invented config and must refuse before any request.
    code = command.run(
        tmp_path,
        {},
        [],
        transport=metadata if plant == "stream" else None,
        sleep=lambda _: None,
    )
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "SYN-configuration-secret" not in output
    cache = tmp_path / "data/public_cache"
    if plant == "none":
        # The source fixture fetches successfully; a whole assembly still
        # refuses because this fixture supplies no reviewed snapshot pins.
        assert code == 1
        assert "snapshot_selection_invalid" in output
        assert any(kind == "metadata" for kind, _ in calls)
        assert any(kind == "stream" for kind, _ in calls)
        assert list(cache.rglob("*.manifest.json"))
        assert f"PASS {entry.key}" in output
    else:
        assert code == 1
        reason = (
            "configuration_unreadable"
            if plant == "config"
            else "stream_transport_missing"
        )
        assert reason in output
        assert calls == []
        assert not list(cache.rglob("*.manifest.json"))
        assert not list(cache.rglob("index/*.json"))


@pytest.mark.parametrize("plant", ["none", "primary", "query", "secret", "opener"])
def test_build_public_joined_comtrade(tmp_path, monkeypatch, capsys, plant):
    from custodian.tests.fixtures.comtrade.invented import (
        body_for,
        invented_entry,
        invented_policy,
    )

    from commands import build_public as command
    from eii_custodian.publicdata.fetch.transport import AttemptResult, OpenerFault

    secret = "SYN-header-marker"
    policy = (
        invented_policy(reporter_key=secret) if plant == "query" else invented_policy()
    )
    entry = invented_entry(policy)
    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    monkeypatch.setattr(command, "load_policies", lambda: {})
    monkeypatch.setattr(command, "utc_now", lambda: "2026-11-16T08:00:00Z")
    reads, calls = [], []

    class Environment(dict):
        def __getitem__(self, name):
            reads.append(name)
            assert name == command.PRIMARY_ENV
            return super().__getitem__(name)

    def opener(request):
        calls.append(request.url)
        assert request.header_value == secret
        if plant == "secret":
            raise OpenerFault("SYN-error-marker " + secret)
        return AttemptResult("ok", body_for(request))

    def forbidden(*args, **kwargs):
        pytest.fail("non-Comtrade transport requested")

    monkeypatch.setattr(command, "open_attempt", opener)
    monkeypatch.setattr(command, "open_https", forbidden)
    env = Environment({} if plant == "primary" else {command.PRIMARY_ENV: secret})
    code = command.run(
        tmp_path,
        env,
        [],
        transport=forbidden if plant == "opener" else None,
        sleep=lambda _: None,
    )
    captured = capsys.readouterr()
    output = captured.out + captured.err
    cache = tmp_path / "data/public_cache"
    if plant == "none":
        assert code == 1 and calls and reads
        assert "snapshot_selection_invalid" in output
        assert f"PASS {entry.key}" in output
        assert list(cache.rglob("manifest.json"))
    else:
        assert code == 1
        reason = {
            "primary": "primary_absent",
            "query": "query_key",
            "secret": "provider_error",
            "opener": "transport_uninjected",
        }[plant]
        assert reason in output
        assert not list(cache.rglob("manifest.json"))
        if plant != "secret":
            assert calls == []
        if plant == "opener":
            assert reads == []
    assert secret not in output and "SYN-error-marker" not in output
    for path in cache.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
            assert b"SYN-error-marker" not in path.read_bytes()


def test_build_public_joined_grid_headers(tmp_path, monkeypatch, capsys):
    """The real HTTP opener scopes the token to Earthdata, including terms reads."""
    from types import SimpleNamespace

    from commands import build_public as command
    from eii_custodian.publicdata.fetch import transport
    from eii_custodian.publicdata.fetch.registry import load_registry

    entry = next(
        e for e in load_registry() if e.source_id == "ntl_blackmarble" and "/" in e.key
    )
    terms = "https://www.data.gov.qa/syn-terms"
    entry = replace(entry, skip_reason="", terms_url=terms)
    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    monkeypatch.setattr(command, "load_policies", lambda: {})
    sent = []

    class Body:
        def __init__(self, url):
            self.headers = {}
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def geturl(self):
            return self.url

        def read(self, size=-1):
            body = b"SYN-no-day-folder" if not getattr(self, "done", False) else b""
            self.done = True
            return body

    def open_request(request, **kwargs):
        sent.append((request.full_url, request.get_header("Authorization")))
        return Body(request.full_url)

    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *args: SimpleNamespace(open=open_request),
    )
    assert (
        command.run(
            tmp_path, {"EARTHDATA_API_KEY": "SYN-earthdata"}, [], sleep=lambda _: None
        )
        == 1
    )
    assert "day_missing" in capsys.readouterr().out
    assert sent == [(entry.url, None)]
    # A held row preserves the normal terms read while keeping the same token.
    sent.clear()
    monkeypatch.setattr(
        command, "load_registry", lambda: (replace(entry, skip_reason="SYN-held"),)
    )
    assert (
        command.run(
            tmp_path / "held",
            {"EARTHDATA_API_KEY": "SYN-earthdata"},
            [],
            sleep=lambda _: None,
        )
        == 1
    )
    assert "snapshot_selection_invalid" in capsys.readouterr().out
    assert sent == [(terms, None)]
    assert not list((tmp_path / "data/public_cache" / entry.key).rglob("index/*.json"))
    from custodian.tests.fixtures.grids.invented import night_file

    body = night_file(tmp_path / "SYN-grid.h5").read_bytes()
    entry = replace(entry, period="2024-01", tile="h23v06", terms_url="")
    day = entry.url + "001/"
    granule = day + "VNP46A3.A2024001.h23v06.SYN.h5"

    def read_body(self, size=-1):
        if self.url == entry.url:
            answer = b'<a href="001/">SYN-day</a>'
        elif self.url == day:
            answer = b'<a href="VNP46A3.A2024001.h23v06.SYN.h5">SYN-granule</a>'
        else:
            assert self.url == granule
            answer = body
        position = getattr(self, "position", 0)
        result = answer[position:] if size < 0 else answer[position : position + size]
        self.position = position + len(result)
        return result

    monkeypatch.setattr(Body, "read", read_body)
    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    sent.clear()
    assert (
        command.run(
            tmp_path / "complete",
            {"EARTHDATA_API_KEY": "SYN-earthdata"},
            [],
            sleep=lambda _: None,
        )
        == 1
    )
    assert "snapshot_selection_invalid" in capsys.readouterr().out
    assert sent == [(entry.url, None), (day, None), (granule, "Bearer SYN-earthdata")]
    assert list(
        (tmp_path / "complete/data/public_cache" / entry.key / "index").glob("*.json")
    )


def test_build_public_ordinary_run_skips_tenders(tmp_path, monkeypatch, capsys):
    from custodian.tests.singles_entries import tender_entry
    from custodian.tests.test_tenders import _chain

    from commands import build_public as command
    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.singles import tenders

    chain, digest = _chain(tmp_path)
    entry = replace(
        tender_entry(), skip_reason="", chain_intermediate_sha256=digest, terms_url=""
    )
    monkeypatch.setattr(tenders, "CHAIN_PATH", chain)
    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    monkeypatch.setattr(command, "load_policies", lambda: {})
    sent = []

    def open_page(url, *, headers, ssl_context):
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname is True
        sent.append(url)
        return Response(url, b"SYN-invalid-tender-page", ())

    monkeypatch.setattr(tenders, "open_https", open_page)
    monkeypatch.setattr(
        command,
        "open_https",
        lambda *args, **kwargs: pytest.fail("tender reached generic file reader"),
    )
    # Decision 0084: the ordinary run makes no tender list, page or terms
    # request; the source's own run is not part of this command form. This
    # row's changed terms address does not bind the review, so assembly then
    # refuses it rather than recording it as pending.
    assert command.run(tmp_path, {}, [], sleep=lambda _: None) == 1
    assert sent == []
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "SKIP tenders_pub own_run" in output
    assert "FAIL tenders_pub" not in output
    assert "FAIL assembly snapshot_selection_invalid" in output
    assert not list((tmp_path / "data/public_cache" / entry.key).rglob("index/*.json"))
