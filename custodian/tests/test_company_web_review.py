"""Independent exact review and no register disclosure (F1/F11/F12/F13)."""

from dataclasses import replace

import pytest
from custodian.tests.company_web_fixture import (
    IDENTITY,
    NAME,
    REVIEWER,
    body,
    offline_network,  # noqa: F401
    receipt,
)

from eii_custodian.publicdata.company_web.contracts import Company, WebError
from eii_custodian.publicdata.company_web.names import contribution
from eii_custodian.publicdata.company_web.parse import extract
from eii_custodian.publicdata.company_web.review import accept, record, reviewer_bundle
from eii_custodian.publicdata.name_inventory import check_inventory


def candidate():
    data = body()
    return extract(
        data, Company("syn-a", NAME, "register", {}), receipt(data)
    ).candidates[0]


def test_pending_rejected_and_independent_acceptance() -> None:
    item = candidate()
    assert accept(item, None, IDENTITY) is None
    signed = record(item, REVIEWER, "accepted")
    assert accept(item, signed, IDENTITY) == item
    assert accept(item, record(item, REVIEWER, "rejected"), IDENTITY) is None


@pytest.mark.parametrize(
    "maker", ["Builder", " builder ", "B U I L D E R", "\uff22uilder"]
)
def test_same_maker_relabel_refused(maker: str) -> None:
    item = candidate()
    with pytest.raises(WebError):
        accept(item, record(item, dict(REVIEWER, maker=maker), "accepted"), IDENTITY)


@pytest.mark.parametrize(
    "field,value",
    [
        ("company_key", "syn-other"),
        ("field", "activity"),
        ("value", "Velquorra Tools"),
        ("page_sha256", "b" * 64),
        ("fragment_sha256", "c" * 64),
        ("parser", "company_web@v2"),
    ],
)
def test_review_replay_refused(field: str, value: str) -> None:
    item = candidate()
    signed = record(item, REVIEWER, "accepted")
    with pytest.raises(WebError):
        accept(replace(item, **{field: value}), signed, IDENTITY)


@pytest.mark.parametrize("field", ["tool", "model", "run_id", "maker"])
def test_missing_reviewer_identity_refused(field: str) -> None:
    who = dict(REVIEWER)
    who[field] = ""
    with pytest.raises(WebError):
        record(candidate(), who, "accepted")


def test_reviewer_bundle_cannot_disclose_register_row() -> None:
    data = body()
    result = extract(
        data,
        Company("syn-a", NAME, "register", {"address": "SYN different address"}),
        receipt(data),
    )
    bundle = reviewer_bundle(NAME, result)
    assert set(bundle) == {
        "company_name",
        "fragment",
        "fragment_sha256",
        "page_sha256",
        "url",
        "parser",
        "candidates",
    }
    assert "register_fields" not in str(bundle) and "syn-a" not in str(bundle)
    assert "SYN different address" not in str(bundle)
    with pytest.raises(WebError):
        reviewer_bundle({"register_row": NAME}, result)


def test_register_web_conflict_and_name_inventory() -> None:
    data = body()
    company = Company("syn-a", NAME, "register", {"address": "SYN other address"})
    result = extract(data, company, receipt(data))
    address = next(c for c in result.candidates if c.field == "address")
    assert address.conflict
    assert company.register_fields["address"] == "SYN other address"
    item = result.candidates[0]
    with pytest.raises(WebError):
        contribution([item], {}, IDENTITY)
    inventory = contribution(
        [item], {item.digest: record(item, REVIEWER, "accepted")}, IDENTITY
    )
    assert inventory.names == (NAME,)
    assert not check_inventory(["SYN " + NAME], [inventory], 1).ok


def test_review_replay_into_another_extraction_run_refused() -> None:
    item = candidate()
    with pytest.raises(WebError):
        accept(
            item,
            record(item, REVIEWER, "accepted"),
            dict(IDENTITY, run_id="syn-other-run"),
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"person": "Invented"},
        {"job_title": "Invented"},
        {"salary": "Invented"},
        {"workbook": "Invented"},
    ],
)
def test_extra_register_fields_cannot_be_disclosed(extra) -> None:
    with pytest.raises(WebError):
        Company("syn-a", NAME, "register", extra)


def test_reviewer_can_bind_decision_without_a_register_key() -> None:
    data = body()
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    bundle = reviewer_bundle(NAME, result)
    item = result.candidates[0]
    visible = bundle["candidates"][0]
    assert visible["candidate_digest"] == item.digest
    assert "company_key" not in visible and "company_digest" not in visible
    reconstructed = {
        key: visible[key]
        for key in (
            "candidate_digest",
            "field",
            "value_sha256",
            "page_sha256",
            "fragment_sha256",
            "parser",
            "extractor_sha256",
        )
    }
    reconstructed.update(reviewer=REVIEWER, decision="accepted")
    assert accept(item, reconstructed, IDENTITY) == item


def test_inventory_build_fails_on_a_retained_web_name_collision() -> None:
    from eii_custodian.publicdata.company_web.names import build_inventory

    item = candidate()
    reviews = {item.digest: record(item, REVIEWER, "accepted")}
    with pytest.raises(WebError, match="name_collision"):
        build_inventory(["SYN " + NAME], [item], reviews, IDENTITY, (), 1)


def test_register_file_object_is_not_a_reviewer_input() -> None:
    from pathlib import Path

    data = body()
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    with pytest.raises(WebError):
        reviewer_bundle(Path("invented-register.csv"), result)
