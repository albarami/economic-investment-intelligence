"""Exact company scopes, immutable archive, access obstacles and pace (F3/F5/F10)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from custodian.tests.company_web_fixture import (
    OTHER,
    URL,
    body,
    manifest,
    offline_network,  # noqa: F401
    receipt,
)

from eii_custodian.publicdata.company_web.contracts import WebError
from eii_custodian.publicdata.company_web.fetch import Pacer, archive_page, load_page
from eii_custodian.publicdata.company_web.scope import Manifest, company_requests
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.transport import (
    Response,
    TransportFault,
    open_https,
)


def test_manifest_hash_pins_review(tmp_path: Path) -> None:
    data = json.dumps(manifest()).encode()
    path = tmp_path / "hosts.json"
    path.write_bytes(data)
    assert Manifest.load(path, sha256_hex(data)).sha256 == sha256_hex(data)
    path.write_bytes(data + b" ")
    with pytest.raises(WebError):
        Manifest.load(path, sha256_hex(data))


@pytest.mark.parametrize(
    "target", [OTHER, "https://outside.example.test/about", URL + "?unexpected=yes"]
)
def test_outside_another_company_and_query_refused_before_open(target: str) -> None:
    with company_requests(Manifest.from_data(manifest()), "syn-a"):
        with patch("urllib.request.build_opener") as opener:
            with pytest.raises(TransportFault):
                open_https(target)
            opener.assert_not_called()


def test_scope_does_not_escape() -> None:
    with pytest.raises(TransportFault), patch("urllib.request.build_opener") as opener:
        open_https(URL)
    opener.assert_not_called()


def test_archive_complete_mixed_page_and_explicit_read(tmp_path: Path) -> None:
    data = body()
    page = archive_page(
        tmp_path,
        "syn-a",
        Response(URL, data, (), body_sha256=sha256_hex(data)),
        receipt(data),
    )
    assert page.body == data
    assert load_page(tmp_path, "syn-a", page.identity).body == data
    page.snapshot.path.write_bytes(b"projection")
    with pytest.raises(ValueError):
        load_page(tmp_path, "syn-a", page.identity)


@pytest.mark.parametrize("field", ["sha256", "retrieved_utc", "original_url"])
def test_missing_archive_lineage_refused(tmp_path: Path, field: str) -> None:
    data = body()
    meta = receipt(data)
    del meta[field]
    with pytest.raises(WebError):
        archive_page(
            tmp_path,
            "syn-a",
            Response(URL, data, (), body_sha256=sha256_hex(data)),
            meta,
        )


def test_no_block_is_archived(tmp_path: Path) -> None:
    data = b"<html><body>Empty invented page</body></html>"
    page = archive_page(
        tmp_path,
        "syn-a",
        Response(URL, data, (), body_sha256=sha256_hex(data)),
        receipt(data),
    )
    assert page.body == data


def test_pace_cannot_be_skipped() -> None:
    tick = [0.0]

    def sleep(seconds: float) -> None:
        tick[0] += seconds

    pace = Pacer(sleep, lambda: tick[0])
    pace.wait(2)
    pace.wait(2)
    assert tick[0] == 2
    bad = Pacer(lambda _: None, lambda: 0)
    bad.wait(2)
    with pytest.raises(WebError):
        bad.wait(2)


def test_auth_not_permitted_in_company_context() -> None:
    with company_requests(Manifest.from_data(manifest()), "syn-a"):
        with (
            pytest.raises(TransportFault),
            patch("urllib.request.build_opener") as opener,
        ):
            open_https(URL, token="invented-token")
        opener.assert_not_called()


def test_redirect_guard_and_final_url_are_checked_without_network() -> None:
    import io
    from http.client import HTTPMessage
    from types import SimpleNamespace
    from urllib.request import Request

    from eii_custodian.publicdata.fetch import transport

    class Upstream(io.BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.headers = {}

        def geturl(self):
            return OTHER

    with company_requests(Manifest.from_data(manifest()), "syn-a"):
        handler = transport._redirect_guard([], strict=True, reviewed_urls=(URL,))()
        with pytest.raises(TransportFault):
            handler.redirect_request(
                Request(URL), None, 302, "SYN", HTTPMessage(), OTHER
            )
        with patch(
            "urllib.request.build_opener",
            return_value=SimpleNamespace(open=lambda *a, **k: Upstream(b"SYN body")),
        ):
            with pytest.raises(TransportFault):
                open_https(URL)


def test_scope_resets_after_exception_and_manifest_mutation_is_refused() -> None:
    plan = Manifest.from_data(manifest())
    with pytest.raises(RuntimeError), company_requests(plan, "syn-a"):
        raise RuntimeError("invented")
    with pytest.raises(TransportFault), patch("urllib.request.build_opener"):
        open_https(URL)
    plan.data["companies"]["syn-a"] = [OTHER]
    with pytest.raises(WebError):
        with company_requests(plan, "syn-a"):
            pass


@pytest.mark.parametrize(
    "plant",
    [
        "missing_access",
        "extra_host",
        "eleven_companies",
        "four_pages",
        "too_fast",
        "keyed",
        "unreadable",
        "wrong_robots_path",
        "unbound_selector",
    ],
)
def test_manifest_guards_have_plants(plant: str) -> None:
    data = manifest()
    if plant == "missing_access":
        del data["access"]["zorvella.example.test"]
    elif plant == "extra_host":
        data["access"]["outside.example.test"] = {
            "terms_url": "",
            "robots_url": "",
            "delay_seconds": 2,
        }
    elif plant == "eleven_companies":
        data["companies"] = {"syn-" + str(i): [] for i in range(11)}
    elif plant == "four_pages":
        data["companies"]["syn-a"] = [URL + "/" + str(i) for i in range(4)]
    elif plant == "too_fast":
        data["access"]["zorvella.example.test"]["delay_seconds"] = 1
    elif plant == "keyed":
        data["provider"]["keyless"] = False
    elif plant == "unreadable":
        data["provider"]["visitor_readable"] = False
    elif plant == "wrong_robots_path":
        data["access"]["zorvella.example.test"]["robots_url"] = URL
    else:
        data["selectors"]["outside.example.test"] = {
            "block": "section",
            "fields": {"name": "b"},
        }
    with pytest.raises(WebError):
        Manifest.from_data(data)


def test_access_none_found_records_and_robots_slower_pace(tmp_path: Path) -> None:
    from custodian.tests.company_web_fixture import NAME, STAMP

    from eii_custodian.publicdata.company_web.contracts import Company
    from eii_custodian.publicdata.company_web.fetch import Access

    value = manifest()
    value["access"]["zorvella.example.test"] = {
        "terms_url": "",
        "robots_url": "https://zorvella.example.test/robots.txt",
        "delay_seconds": 2,
    }
    tick, sent = [0.0], []

    def send(url):
        sent.append((url, tick[0]))
        data = (
            b"User-agent: *\nCrawl-delay: 4\n" if url.endswith("robots.txt") else body()
        )
        return Response(url, data, (), body_sha256=sha256_hex(data))

    def sleep(seconds):
        tick[0] += seconds

    access = Access(
        Manifest.from_data(value),
        send,
        tmp_path,
        lambda: STAMP,
        Pacer(sleep, lambda: tick[0]),
    )
    page = access.page(Company("syn-a", NAME, "register", {}), URL)
    assert page.body == body()
    assert sent[1][1] - sent[0][1] >= 4
    assert any(
        b'"terms": "none found"' in p.read_bytes()
        for p in (tmp_path / "company_web" / "access").rglob("*.json")
    )


@pytest.mark.parametrize("obstruction", [b"sign in", b"robot check", b"paywall"])
def test_access_obstacles_stop_host_without_retry(
    tmp_path: Path, obstruction: bytes
) -> None:
    from custodian.tests.company_web_fixture import NAME, STAMP

    from eii_custodian.publicdata.company_web.contracts import Company
    from eii_custodian.publicdata.company_web.fetch import Access

    calls = []

    def send(url):
        calls.append(url)
        return Response(url, obstruction, (), body_sha256=sha256_hex(obstruction))

    access = Access(
        Manifest.from_data(manifest()),
        send,
        tmp_path,
        lambda: STAMP,
        Pacer(lambda _: None, lambda: 0),
    )
    company = Company("syn-a", NAME, "register", {})
    with pytest.raises(WebError, match="obstacle"):
        access.page(company, URL)
    with pytest.raises(WebError, match="obstacle"):
        access.page(company, URL)
    assert len(calls) == 1


def test_snapshot_interruption_never_yields_a_readable_page(tmp_path: Path) -> None:
    data = body()
    with patch(
        "eii_custodian.publicdata.fetch.snapshots._publish", side_effect=OSError
    ):
        with pytest.raises(ValueError):
            archive_page(
                tmp_path,
                "syn-a",
                Response(URL, data, (), body_sha256=sha256_hex(data)),
                receipt(data),
            )
    assert not tuple(tmp_path.rglob("index/*.json"))


def test_equal_page_recheck_does_not_overwrite(tmp_path: Path) -> None:
    data = body()
    response = Response(URL, data, (), body_sha256=sha256_hex(data))
    first = archive_page(tmp_path, "syn-a", response, receipt(data))
    original = first.snapshot.receipt_path.read_bytes()
    second = archive_page(tmp_path, "syn-a", response, receipt(data))
    assert (
        second.identity == first.identity
        and first.snapshot.receipt_path.read_bytes() == original
    )


def test_obstacle_body_is_archived_before_host_stops(tmp_path: Path) -> None:
    from custodian.tests.company_web_fixture import NAME, STAMP

    from eii_custodian.publicdata.company_web.contracts import Company
    from eii_custodian.publicdata.company_web.fetch import Access

    data = b"<html>robot check</html>"
    access = Access(
        Manifest.from_data(manifest()),
        lambda u: Response(u, data, (), body_sha256=sha256_hex(data)),
        tmp_path,
        lambda: STAMP,
        Pacer(lambda _: None, lambda: 0),
    )
    with pytest.raises(WebError, match="obstacle"):
        access.page(Company("syn-a", NAME, "register", {}), URL)
    assert any(p.read_bytes() == data for p in tmp_path.rglob("*.html"))


def test_nested_scope_may_only_narrow() -> None:
    plan = Manifest.from_data(manifest())
    with company_requests(plan, "syn-a"):
        with pytest.raises(WebError):
            with company_requests(plan, "syn-b"):
                pass


def test_obstacle_stops_only_its_host_not_other_results(tmp_path: Path) -> None:
    from custodian.tests.company_web_fixture import NAME, STAMP

    from eii_custodian.publicdata.company_web.contracts import Company
    from eii_custodian.publicdata.company_web.fetch import Access

    value = manifest()
    value["companies"]["syn-a"] = [URL, OTHER]
    tick = [0.0]

    def sleep(seconds):
        tick[0] += seconds

    def send(url):
        data = b"robot check" if url == URL else body()
        return Response(url, data, (), body_sha256=sha256_hex(data))

    access = Access(
        Manifest.from_data(value),
        send,
        tmp_path,
        lambda: STAMP,
        Pacer(sleep, lambda: tick[0]),
    )
    company = Company("syn-a", NAME, "register", {})
    with pytest.raises(WebError, match="obstacle"):
        access.page(company, URL)
    assert access.page(company, OTHER).body == body()


def test_streams_cannot_use_the_company_scope() -> None:
    from eii_custodian.publicdata.fetch.transport import open_https_stream

    with (
        company_requests(Manifest.from_data(manifest()), "syn-a"),
        patch("urllib.request.build_opener") as opener,
    ):
        with pytest.raises(TransportFault):
            with open_https_stream(URL):
                pass
    opener.assert_not_called()


@pytest.mark.parametrize("body_kind", ["blocked", "missing", "unread_terms"])
def test_robots_and_unavailable_terms_have_distinct_outcomes(
    tmp_path: Path, body_kind: str
) -> None:
    from custodian.tests.company_web_fixture import NAME, STAMP

    from eii_custodian.publicdata.company_web.contracts import Company
    from eii_custodian.publicdata.company_web.fetch import Access

    value = manifest()
    host = "zorvella.example.test"
    value["access"][host]["robots_url"] = "https://" + host + "/robots.txt"
    value["access"][host]["terms_url"] = "https://" + host + "/terms"
    tick, sent = [0.0], []

    def sleep(seconds):
        tick[0] += seconds

    def send(url):
        sent.append(url)
        if url.endswith("terms") and body_kind == "unread_terms":
            raise TransportFault("unreachable", url)
        if url.endswith("robots.txt") and body_kind == "missing":
            raise TransportFault("unreachable", url)
        data = (
            b"User-agent: *\nDisallow: /about\n"
            if url.endswith("robots.txt") and body_kind == "blocked"
            else b"User-agent: *\nAllow: /\n"
            if url.endswith("robots.txt")
            else body()
        )
        return Response(url, data, (), body_sha256=sha256_hex(data))

    access = Access(
        Manifest.from_data(value),
        send,
        tmp_path,
        lambda: STAMP,
        Pacer(sleep, lambda: tick[0]),
    )
    if body_kind == "unread_terms":
        assert access.page(Company("syn-a", NAME, "register", {}), URL).body == body()
    else:
        with pytest.raises(
            WebError, match="obstacle" if body_kind == "blocked" else "unavailable"
        ):
            access.page(Company("syn-a", NAME, "register", {}), URL)
        assert URL not in sent


@pytest.mark.parametrize("fault", ["redirect", "blocked_host"])
def test_unread_terms_never_masks_a_security_refusal(
    tmp_path: Path, fault: str
) -> None:
    from custodian.tests.company_web_fixture import NAME, STAMP

    from eii_custodian.publicdata.company_web.contracts import Company
    from eii_custodian.publicdata.company_web.fetch import Access

    value = manifest()
    value["access"]["zorvella.example.test"]["terms_url"] = (
        "https://zorvella.example.test/terms"
    )
    tick, sent = [0.0], []

    def sleep(seconds):
        tick[0] += seconds

    def send(url):
        sent.append(url)
        if url.endswith("terms"):
            if fault == "blocked_host":
                raise TransportFault("blocked_host", "")
            return Response(OTHER, b"Invented terms", ())
        return Response(url, body(), (), body_sha256=sha256_hex(body()))

    access = Access(
        Manifest.from_data(value),
        send,
        tmp_path,
        lambda: STAMP,
        Pacer(sleep, lambda: tick[0]),
    )
    with pytest.raises(WebError):
        access.page(Company("syn-a", NAME, "register", {}), URL)
    assert URL not in sent
