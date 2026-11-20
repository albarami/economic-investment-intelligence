"""Closed deterministic searches and both invented register inputs (F2/F6/F7)."""

from urllib.parse import parse_qs, urlsplit

import pytest
from custodian.tests.company_web_fixture import (
    NAME,
    STAMP,
    URL,
    manifest,
    offline_network,  # noqa: F401
)

from eii_custodian.publicdata.company_web.contracts import Company, WebError
from eii_custodian.publicdata.company_web.scope import Manifest
from eii_custodian.publicdata.company_web.search import companies, request_url, search
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.transport import Response, public_address


def test_both_register_inputs_and_separate_namespaces() -> None:
    result = companies(
        [
            {
                "company_name": NAME,
                "registration_number": "syn-key",
                "licence_number": "",
            },
            {
                "company_name": "Velquorra Tools",
                "registration_number": "",
                "licence_number": "syn-key",
            },
        ],
        ["Fenzavix Systems"],
    )
    assert len({c.key for c in result}) == 3
    assert [c.source for c in result] == ["register", "register", "fc_register"]
    assert result[-1].register_fields == {}


def test_ambiguous_input_not_guessed() -> None:
    with pytest.raises(WebError):
        companies(
            [{"company_name": NAME, "registration_number": "", "licence_number": ""}],
            [],
        )
    with pytest.raises(WebError):
        companies(
            [
                {
                    "company_name": NAME,
                    "registration_number": "syn-key",
                    "licence_number": "",
                }
            ]
            * 2,
            [],
        )


def test_invented_search_returns_addresses_only() -> None:
    company = Company("syn-a", NAME, "register", {})
    plan = Manifest.from_data(manifest())
    sent = []

    def transport(url: str) -> Response:
        sent.append(url)
        return Response(
            url,
            f'<a class="result" href="{URL}">Snippet deliberately not retained</a>'.encode(),
            (),
        )

    result = search(company, plan, transport, lambda: STAMP, lambda _: None)
    assert result.urls == (URL,)
    assert result.company_key == company.key
    assert "Snippet" not in repr(result)
    assert parse_qs(urlsplit(sent[0]).query) == {"q": [NAME + " Qatar"]}
    assert NAME not in public_address(sent[0])
    assert result.request_sha256 == sha256_hex(sent[0].encode())


@pytest.mark.parametrize(
    "name", ["Bad; touch output", "Bad$(id)", "Bad`id`", "Bad\nname"]
)
def test_metacharacter_names_refused(name: str) -> None:
    with pytest.raises(WebError):
        request_url(
            Company("syn-a", name, "register", {}), Manifest.from_data(manifest())
        )


def test_query_cannot_be_changed_or_rebound() -> None:
    plan = Manifest.from_data(manifest())
    url = request_url(Company("syn-a", NAME, "register", {}), plan)
    assert plan.search_allowed(url, NAME)
    assert not plan.search_allowed(url, "Velquorra Tools")
    assert not plan.search_allowed(url.replace("+Qatar", ""), NAME)
    assert not plan.search_allowed(
        url.replace("search.example.test", "outside.example.test"), NAME
    )


def test_no_shell_or_second_opener_in_company_tooling() -> None:
    import ast
    from pathlib import Path

    folder = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "eii_custodian"
        / "publicdata"
        / "company_web"
    )
    forbidden = {
        "subprocess",
        "requests",
        "httpx",
        "socket",
        "urllib.request",
        "http.client",
    }
    for path in folder.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name in forbidden for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "system",
                    "popen",
                    "urlopen",
                    "build_opener",
                }
