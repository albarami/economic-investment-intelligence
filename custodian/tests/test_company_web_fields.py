"""Company-only contract plants and declared-parser controls (F4/F8/F9/F12)."""

import json

import pytest
from custodian.tests.company_web_fixture import (
    NAME,
    URL,
    body,
    offline_network,  # noqa: F401
    receipt,
)

from eii_custodian.publicdata.company_web.contracts import Company, WebError, safe_text
from eii_custodian.publicdata.company_web.parse import extract

COMPANY = Company("syn-a", NAME, "register", {})


@pytest.mark.parametrize("field", ["person", "job_title", "salary", "unknown"])
def test_personal_or_unknown_field_refused(field: str) -> None:
    with pytest.raises(WebError):
        safe_text(field, "Invented value")


@pytest.mark.parametrize("size", [8, 11])
@pytest.mark.parametrize("field", ["name", "address", "website", "activity"])
def test_identifier_runs_refused_everywhere(field: str, size: int) -> None:
    with pytest.raises(WebError):
        safe_text(field, "https://invented.example.test/" + "6" * size)


@pytest.mark.parametrize(
    "value",
    [
        "Telephone: none",
        "Fax: none",
        "Mr. Invented",
        "Chief Executive",
        "salary band",
        "person",
        "x" + "@" + "example.test",
        "%36" * 8,
    ],
)
def test_contact_person_and_encoded_digit_plants(value: str) -> None:
    with pytest.raises(WebError):
        safe_text("address", value)


def test_jsonld_full_page_fragment_and_absence() -> None:
    data = body()
    result = extract(data, COMPANY, receipt(data))
    assert result.status == "matched"
    assert {c.field for c in result.candidates} == {
        "name",
        "address",
        "website",
        "activity",
    }
    assert b"Unrelated mixed content" not in result.fragment
    data = body(address=None, description=None, url=None)
    result = extract(data, COMPANY, receipt(data))
    assert [c.field for c in result.candidates] == ["name"]


@pytest.mark.parametrize(
    "updates,status",
    [
        ({"name": "Velquorra Tools"}, "name_mismatch"),
        ({"name": NAME + " LLC"}, "ambiguous"),
        ({"name": NAME + " W.L.L."}, "ambiguous"),
    ],
)
def test_match_only_inside_declared_block(
    updates: dict[str, object], status: str
) -> None:
    data = body(**updates) + NAME.encode()
    result = extract(data, COMPANY, receipt(data))
    assert result.status == status
    assert not result.candidates


def test_no_declared_block() -> None:
    data = b"<html><p>Invented page without a company block</p></html>"
    assert extract(data, COMPANY, receipt(data)).status == "no_declared_block"


@pytest.mark.parametrize("kind", ["Person", "Employee"])
def test_organization_nested_in_person_refused(kind: str) -> None:
    block = {"@type": kind, "worksFor": {"@type": "Organization", "name": NAME}}
    data = (
        '<script type="application/ld+json">' + json.dumps(block) + "</script>"
    ).encode()
    with pytest.raises(WebError):
        extract(data, COMPANY, receipt(data))


def test_multiple_organizations_ambiguous() -> None:
    data = body() + body(name="Velquorra Tools")
    result = extract(data, COMPANY, receipt(data))
    assert result.status == "ambiguous" and not result.candidates


def test_microdata() -> None:
    data = f'<div itemscope itemtype="https://schema.org/Organization"><span itemprop="name">{NAME}</span><div itemprop="address" itemscope itemtype="https://schema.org/PostalAddress"><span itemprop="streetAddress">SYN street</span></div><a itemprop="url" href="{URL}">web</a><span itemprop="isicV4">SYN-class</span></div>'.encode()
    result = extract(data, COMPANY, receipt(data))
    assert result.status == "matched" and len(result.candidates) == 4


def test_reviewed_selector_positive_and_unreviewed_refusal() -> None:
    data = f'<section id="company"><b>{NAME}</b><p>SYN activity</p></section>'.encode()
    selection = {"block": "section#company", "fields": {"name": "b", "activity": "p"}}
    with pytest.raises(WebError):
        extract(data, COMPANY, receipt(data), selectors=selection)
    result = extract(
        data, COMPANY, receipt(data), selectors=selection, selectors_reviewed=True
    )
    assert result.status == "matched"


@pytest.mark.parametrize(
    "field",
    ["sha256", "retrieved_utc", "fetch_url", "publisher", "licence_basis", "method"],
)
def test_missing_lineage_refused(field: str) -> None:
    data = body()
    meta = receipt(data)
    del meta[field]
    with pytest.raises(WebError):
        extract(data, COMPANY, meta)


def test_projection_cannot_substitute_for_upstream_body() -> None:
    data = body()
    with pytest.raises(WebError):
        extract(b"{}", COMPANY, receipt(data))


def test_duplicate_json_properties_are_not_silently_selected() -> None:
    data = (
        '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Velquorra Tools","name":"'
        + NAME
        + '"}</script>'
    ).encode()
    with pytest.raises(WebError):
        extract(data, COMPANY, receipt(data))


@pytest.mark.parametrize(
    "schema",
    ["https://outside.example.test", "https://outside.example.test/Organization"],
)
def test_foreign_vocabulary_is_not_schema_org(schema: str) -> None:
    data = body(**{"@context": schema, "@type": "Organization"})
    result = extract(data, COMPANY, receipt(data))
    assert not result.candidates


@pytest.mark.parametrize("size", [8, 11])
def test_address_metadata_digit_plant_is_not_proposed(size: int) -> None:
    data = body(address={"@type": "PostalAddress", "postalCode": "6" * size})
    with pytest.raises(WebError):
        extract(data, COMPANY, receipt(data))
