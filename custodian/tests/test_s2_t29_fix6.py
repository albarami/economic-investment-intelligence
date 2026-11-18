"""Fix-six plants: refusal metadata, school envelopes and unscoped pin hosts."""

import ast
import hashlib
import json
import shutil
import ssl
from copy import deepcopy
from dataclasses import replace
from http.client import HTTPMessage
from importlib.util import resolve_name
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest
from custodian.tests.test_s2_t29_live_acquire import school, school_transport
from custodian.tests.test_s2_t29_live_shapes import STAMP, embedded, entry

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.certificate_pins import (
    PinError,
    current_pin,
    page_transport,
)
from eii_custodian.publicdata.fetch.page_acquire import validate_entry
from eii_custodian.publicdata.fetch.page_records import fetch_page, load_declaration
from eii_custodian.publicdata.fetch.page_requests import PIN_HOSTS, active
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import (
    Response,
    TransportFault,
    _redirect_guard,
    open_https,
)
from eii_custodian.publicdata.singles import tenders


def test_only_four_page_pin_hosts_remain():
    assert PIN_HOSTS == {
        "www.qcb.gov.qa",
        "monaqasat.mof.gov.qa",
        "www.edu.gov.qa",
        "myschools.edu.gov.qa",
    }
    assert not approve("https://www.tawteen.com.qa/SYN").ok
    assert not approve("https://icv.qa/SYN").ok


@pytest.mark.parametrize("host", ["icv.qa", "syn-refusal.invalid"])
def test_off_list_refusal_loads_and_normal_dispatch_never_fetches(tmp_path, host):
    row = next(r for r in load_registry() if r.source_id == "suppliers_tawteen")
    dec = deepcopy(load_declaration(row.source_id))
    url = "https://" + host + "/SYN-refusal"
    terms = "https://" + host + "/SYN-terms"
    row = replace(row, url=url, terms_url=terms, fetch_host=host)
    dec.update(url=url, reviewed_urls=[url, terms])
    assert not approve(url).ok and not approve(terms).ok
    validate_entry(row, dec)
    calls = []

    def transport(address):
        calls.append(address)
        pytest.fail("refusal metadata must never fetch data or terms")

    with patch(
        "eii_custodian.publicdata.fetch.page_records.load_declaration", return_value=dec
    ):
        outcome = run_build((row,), transport, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is None
    assert any(line.startswith(f"SKIP {row.key}") for line in outcome.lines)
    receipts = list((tmp_path / row.key / "failures" / "index").glob("*.json"))
    assert len(receipts) == 1
    recorded = b"".join(
        p.read_bytes() for p in (tmp_path / row.key / "failures").rglob("*.json")
    )
    assert dec["shape"]["observed_utc"].encode() in recorded
    assert dec["shape"]["reason"].encode() in recorded
    assert calls == []
    # Clearing the dispatch hold still records the refusal without a connection.
    with pytest.raises(ValueError, match=r"^anonymous_access_not_approved$"):
        fetch_page(
            row, transport, tmp_path, lambda: STAMP, lambda _: None, declaration=dec
        )
    assert calls == []


def test_off_list_fetching_row_refuses_without_transport(tmp_path):
    dec, _, _ = embedded()
    url = "https://syn-refusal.invalid/SYN-fetch"
    dec.update(url=url, reviewed_urls=[url])
    row = entry(dec)
    calls = []
    with patch(
        "eii_custodian.publicdata.fetch.page_records.load_declaration", return_value=dec
    ):
        outcome = run_build(
            (row,), lambda u: calls.append(u), tmp_path, lambda: STAMP, lambda _: None
        )
    assert outcome.failure is not None and outcome.failure.check == "blocked_host"
    assert calls == []
    assert not (tmp_path / row.key).exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://syn-refusal.invalid/SYN",
        "https://syn-refusal.invalid/SYN?token=SYN",
        "https://SYN:SYN" + "@" + "syn-refusal.invalid/SYN",
        "https://syn-refusal.invalid/SYN#SYN",
    ],
)
def test_refusal_exemption_preserves_scheme_and_credential_checks(url):
    row = next(r for r in load_registry() if r.source_id == "suppliers_tawteen")
    dec = deepcopy(load_declaration(row.source_id))
    row = replace(row, url=url)
    dec.update(url=url, reviewed_urls=[url])
    with pytest.raises(ValueError, match=r"^blocked_host$"):
        validate_entry(row, dec)


def test_evidenced_school_envelope_keeps_all_inputs(tmp_path):
    dec, attrs = school()
    calls = []
    benign = school_transport(attrs, calls)

    def transport(url):
        response = benign(url)
        if "resultOffset" in parse_qs(urlsplit(url).query):
            body = json.loads(response.body)
            body.update(
                objectIdFieldName="objectid",
                hasZ=False,
                hasM=False,
                fields=[{"name": name} for name in dec["shape"]["fields"]],
            )
            return Response(url, json.dumps(body).encode(), ())
        return response

    result = fetch_page(
        entry(dec, "schools_private_directory"),
        transport,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    payload = json.loads(result.body)
    assert len(payload["rows"]) == 2 and len(calls) == 4
    assert len(payload["inputs"]) == 4
    assert all(item["representation"] == "original" for item in payload["inputs"])


@pytest.mark.parametrize("role", ["count", "page"])
def test_school_top_level_owner_refused_without_archive(tmp_path, role):
    dec, attrs = school()
    calls = []
    benign = school_transport(attrs, calls)

    def transport(url):
        response = benign(url)
        query = parse_qs(urlsplit(url).query)
        target = (
            query.get("returnCountOnly") == ["true"]
            if role == "count"
            else "resultOffset" in query
        )
        if target:
            body = json.loads(response.body)
            body["owner"] = "SYN excluded contact"
            return Response(url, json.dumps(body).encode(), ())
        return response

    with pytest.raises(ValueError, match=r"^school_field_refused$"):
        fetch_page(
            entry(dec, "schools_private_directory"),
            transport,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert len(calls) == (2 if role == "count" else 3)
    assert not list(tmp_path.rglob("index/*.json"))
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


@pytest.mark.parametrize("host", sorted(PIN_HOSTS))
@pytest.mark.parametrize("role", ["initial", "redirect"])
def test_unscoped_page_pin_host_refuses_before_send(host, role):
    url = "https://" + host + "/SYN-unscoped"
    initial = "https://www.data.gov.qa/SYN-initial"
    hops = []
    with (
        page_transport(None),
        patch("urllib.request.build_opener") as opener,
        patch("urllib.request.HTTPRedirectHandler.redirect_request") as redirect_base,
    ):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b"SYN response"
        response.geturl.return_value = url
        response.headers = {}
        assert not active() and current_pin() is None
        with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
            if role == "initial":
                open_https(url)
            else:
                _redirect_guard(hops)().redirect_request(
                    Request(initial), None, 302, "SYN", HTTPMessage(), url
                )
        assert opener.call_count == 0
        assert opener.return_value.open.call_count == 0
        assert redirect_base.call_count == 0
        assert hops == []


def test_fix7_legacy_tender_checked_chain_reaches_transport(tmp_path):
    """Invented stand-in proves the adapter seam, not a TLS handshake."""
    raw = b"SYN-invented-chain-stand-in"
    chain = tmp_path / "SYN-chain.pem"
    chain.write_bytes(raw)
    row = next(r for r in load_registry() if r.key == "tenders_pub")
    row = replace(row, chain_intermediate_sha256=hashlib.sha256(raw).hexdigest())
    url = tenders.list_addresses(tenders.TENDER_HOST)[0]
    with (
        page_transport(None),
        patch.object(tenders, "_open_https", wraps=open_https) as seam,
        patch("urllib.request.build_opener") as opener,
    ):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b"SYN-page"
        response.geturl.return_value = url
        response.headers = {}
        result = tenders.tender_https(row, chain_file=chain)(
            tenders.PageCall(url, (), 2, True)
        )
        assert result.body == b"SYN-page"
        assert opener.return_value.open.call_count == 1
        assert (
            seam.call_args.kwargs["legacy_chain_sha256"]
            == row.chain_intermediate_sha256
        )
        context = seam.call_args.kwargs["ssl_context"]
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        assert not active() and current_pin() is None
        assert tenders._TENDER_CHAIN.get() is None


@pytest.mark.parametrize("host", sorted(PIN_HOSTS))
@pytest.mark.parametrize("legacy_pin", [None, "a" * 63, "a" * 65, "z" * 64])
def test_fix7_unscoped_context_needs_well_formed_legacy_pin(host, legacy_pin):
    with page_transport(None), patch("urllib.request.build_opener") as opener:
        with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
            open_https(
                "https://" + host + "/SYN-unscoped",
                ssl_context=ssl.create_default_context(),
                legacy_chain_sha256=legacy_pin,
            )
        assert opener.call_count == 0
        assert opener.return_value.open.call_count == 0


@pytest.mark.parametrize("mode", ["missing", "no-hostname", "no-verify"])
def test_fix7_legacy_pin_requires_verifying_context(mode):
    context = None if mode == "missing" else ssl.create_default_context()
    if context is not None:
        context.check_hostname = False
        if mode == "no-verify":
            context.verify_mode = ssl.CERT_NONE
    error = PinError if context is None else TransportFault
    reason = "certificate_chain_incomplete" if context is None else "unreachable"
    with page_transport(None), patch("urllib.request.build_opener") as opener:
        with pytest.raises(error, match=reason) as caught:
            open_https(
                tenders.list_addresses(tenders.TENDER_HOST)[0],
                ssl_context=context,
                legacy_chain_sha256="a" * 64,
            )
        if context is not None:
            assert caught.value.kind == "unreachable"
        assert opener.call_count == 0
        assert opener.return_value.open.call_count == 0


@pytest.mark.parametrize("mode", ["no-scope", "other-context", "other-host"])
def test_fix7_tender_seam_does_not_share_checked_pin(mode):
    context = ssl.create_default_context()
    supplied = ssl.create_default_context() if mode == "other-context" else context
    url = (
        "https://www.edu.gov.qa/SYN-other-host"
        if mode == "other-host"
        else tenders.list_addresses(tenders.TENDER_HOST)[0]
    )
    scope = None if mode == "no-scope" else (context, "a" * 64)
    token = tenders._TENDER_CHAIN.set(scope)
    try:
        with page_transport(None), patch("urllib.request.build_opener") as opener:
            with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
                tenders.open_https(url, ssl_context=supplied)
            assert opener.call_count == 0
            assert opener.return_value.open.call_count == 0
    finally:
        tenders._TENDER_CHAIN.reset(token)
    assert tenders._TENDER_CHAIN.get() is None


@pytest.mark.parametrize("host", sorted(PIN_HOSTS))
def test_fix7_tender_legacy_bridge_does_not_authorize_redirect(host, tmp_path):
    """The actual opener's guard refuses every unscoped page pin redirect."""
    raw = b"SYN-invented-chain-stand-in"
    chain = tmp_path / "SYN-chain.pem"
    chain.write_bytes(raw)
    row = next(r for r in load_registry() if r.key == "tenders_pub")
    row = replace(row, chain_intermediate_sha256=hashlib.sha256(raw).hexdigest())
    url = tenders.list_addresses(tenders.TENDER_HOST)[0]
    target = "https://" + host + "/SYN-redirect"
    with (
        page_transport(None),
        patch("urllib.request.build_opener") as opener,
        patch("urllib.request.HTTPRedirectHandler.redirect_request") as redirected,
    ):

        def send(request, *, timeout):
            guard = opener.call_args.args[0]
            guard().redirect_request(request, None, 302, "SYN", HTTPMessage(), target)
            pytest.fail("redirect must refuse before a response is read")

        opener.return_value.open.side_effect = send
        with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
            tenders.tender_https(row, chain_file=chain)(
                tenders.PageCall(url, (), 2, True)
            )
        assert opener.call_count == 1
        assert opener.return_value.open.call_count == 1
        assert redirected.call_count == 0
        assert tenders._TENDER_CHAIN.get() is None
        # The refusal happens before even recording a redirect hop.
        assert (
            opener.call_args.args[0].redirect_request.__closure__[0].cell_contents == []
        )


def _fix8_legacy_chain_hits(source):
    """L-927 source boundary; never inspect callers or signatures at runtime."""
    tender = "eii_custodian.publicdata.singles.tenders"
    hits = set()
    for path in sorted(source.rglob("*.py")):
        relative = path.relative_to(source).as_posix()
        if relative == "eii_custodian/publicdata/singles/tenders.py":
            continue
        tree = ast.parse(path.read_text(), filename=relative)
        package = ".".join(path.relative_to(source).parts[:-1])
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    name = item.name if item.asname else item.name.split(".")[0]
                    aliases[item.asname or name] = name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    module = resolve_name("." * node.level + module, package)
                for item in node.names:
                    aliases[item.asname or item.name] = module + "." + item.name
                    if module == tender and item.name in {"open_https", "*"}:
                        hits.add((relative, node.lineno, "tender-wrapper-import"))
                    if item.name == "_TENDER_CHAIN":
                        hits.add((relative, node.lineno, "tender-chain-import"))

        def qualified(node, aliases=aliases):
            if isinstance(node, ast.Name):
                return aliases.get(node.id, node.id)
            if isinstance(node, ast.Attribute):
                return qualified(node.value) + "." + node.attr
            return ""

        for node in ast.walk(tree):
            rule = None
            if isinstance(node, ast.keyword) and node.arg == "legacy_chain_sha256":
                rule = "legacy-chain-keyword"
            elif isinstance(node, ast.Constant) and node.value == "legacy_chain_sha256":
                rule = "legacy-chain-string"
            elif (
                isinstance(node, ast.arg)
                and node.arg == "legacy_chain_sha256"
                and relative != "eii_custodian/publicdata/fetch/transport.py"
            ):
                rule = "legacy-chain-parameter"
            elif isinstance(node, (ast.Name, ast.Attribute)) and "_TENDER_CHAIN" in {
                getattr(node, "id", None),
                getattr(node, "attr", None),
                qualified(node).split(".")[-1],
            }:
                rule = "tender-chain-reference"
            elif isinstance(node, ast.Constant) and node.value == "_TENDER_CHAIN":
                rule = "tender-chain-string"
            elif (
                isinstance(node, ast.Attribute)
                and qualified(node) == tender + ".open_https"
            ):
                rule = "tender-wrapper-attribute"
            elif (
                isinstance(node, ast.Call)
                and {
                    getattr(node.func, "id", None),
                    getattr(node.func, "attr", None),
                    qualified(node.func).split(".")[-1],
                }
                & {"open_https", "_open_https"}
                and any(keyword.arg is None for keyword in node.keywords)
            ):
                rule = "https-keyword-expansion"
            if rule:
                hits.add((relative, node.lineno, rule))
    return sorted(hits)


def _fix7_assert_legacy_chain_callers(source):
    hits = _fix8_legacy_chain_hits(source)
    assert not hits, hits
    callers = []
    for path in sorted(source.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=path.as_posix())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and any(
                keyword.arg == "legacy_chain_sha256" for keyword in node.keywords
            ):
                callers.append(path.relative_to(source).as_posix())
    assert callers == ["eii_custodian/publicdata/singles/tenders.py"], callers


def test_fix7_legacy_chain_argument_has_only_tender_source_caller():
    _fix7_assert_legacy_chain_callers(Path("custodian/src"))


def test_fix7_legacy_chain_source_guard_rejects_second_caller(tmp_path):
    source = tmp_path / "src"
    shutil.copytree(
        "custodian/src", source, ignore=shutil.ignore_patterns("__pycache__")
    )
    _fix7_assert_legacy_chain_callers(source)
    (source / "SYN_second_caller.py").write_text(
        "def syn_call(open_https, url, pin):\n"
        "    return open_https(url, legacy_chain_sha256=pin)\n"
    )
    with pytest.raises(AssertionError, match="SYN_second_caller"):
        _fix7_assert_legacy_chain_callers(source)


def _fix8_assert_second_caller_refused(tmp_path, code):
    source = tmp_path / "src"
    shutil.copytree(
        "custodian/src", source, ignore=shutil.ignore_patterns("__pycache__")
    )
    _fix7_assert_legacy_chain_callers(source)
    (source / "eii_custodian/publicdata/SYN_second_caller.py").write_text(code)
    with pytest.raises(AssertionError, match=r"SYN_second_caller\.py"):
        _fix7_assert_legacy_chain_callers(source)


def test_fix8_literal_dictionary_expansion_refused(tmp_path):
    _fix8_assert_second_caller_refused(
        tmp_path,
        'open_https(url, ssl_context=c, **{"legacy_chain_sha256": pin})\n',
    )


def test_fix8_variable_keyword_expansion_refused(tmp_path):
    _fix8_assert_second_caller_refused(
        tmp_path,
        'kwargs = {"ssl_context": c}\nopen_https(url, **kwargs)\n',
    )


@pytest.mark.parametrize(
    "code",
    [
        "from eii_custodian.publicdata.fetch.transport import open_https as o\n"
        "o(url, **kw)\n",
        "from .fetch.transport import open_https as o\no(url, **kw)\n",
        "import eii_custodian.publicdata.fetch.transport as t\n"
        "t.open_https(url, **kw)\n",
        "client.open_https(url, **kw)\n",
        "client._open_https(url, **kw)\n",
        "_open_https(url, **kw)\n",
        pytest.param(
            "from synthetic import unrelated as open_https\nopen_https(url, **kw)\n",
            id="literal_name_after_import",
        ),
    ],
)
def test_fix8_aliased_keyword_expansion_refused(tmp_path, code):
    _fix8_assert_second_caller_refused(tmp_path, code)


@pytest.mark.parametrize(
    "code",
    [
        "from eii_custodian.publicdata.singles import tenders\n"
        "tenders._TENDER_CHAIN.set((c, h))\ntenders.open_https(url, ssl_context=c)\n",
        "from eii_custodian.publicdata.singles import tenders as t\n"
        "t._TENDER_CHAIN.set((c, h))\n",
        "from eii_custodian.publicdata.singles.tenders import _TENDER_CHAIN as chain\n"
        "chain.set((c, h))\n",
        "_TENDER_CHAIN.set((c, h))\n",
        'getattr(tenders, "_TENDER_CHAIN").set((c, h))\n',
        "from eii_custodian.publicdata.singles import tenders as t\n"
        "exposed = t.open_https\n",
        "import eii_custodian.publicdata.singles.tenders as t\n"
        "exposed = t.open_https\n",
        pytest.param(
            "from synthetic import unrelated as _TENDER_CHAIN\n"
            "_TENDER_CHAIN.set((c, h))\n",
            id="literal_name_after_import",
        ),
    ],
)
def test_fix8_external_tender_chain_or_wrapper_refused(tmp_path, code):
    _fix8_assert_second_caller_refused(tmp_path, code)


@pytest.mark.parametrize(
    "code",
    [
        "from eii_custodian.publicdata.singles.tenders import open_https\n",
        "from eii_custodian.publicdata.singles.tenders import open_https as o\n",
        "from .singles.tenders import open_https as o\n",
        "from eii_custodian.publicdata.singles.tenders import *\n",
    ],
)
def test_fix8_tender_wrapper_import_refused(tmp_path, code):
    _fix8_assert_second_caller_refused(tmp_path, code)


@pytest.mark.parametrize(
    "code",
    [
        'getattr(client, "legacy_chain_sha256")\n',
        'kwargs = dict([("legacy_chain_sha256", pin)])\n',
    ],
)
def test_fix8_runtime_built_legacy_key_refused(tmp_path, code):
    _fix8_assert_second_caller_refused(tmp_path, code)
