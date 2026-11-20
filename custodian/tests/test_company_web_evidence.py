"""Complete company/search/page/field reconciliation (F14)."""

from dataclasses import replace

import pytest
from custodian.tests.company_web_fixture import (
    IDENTITY,
    NAME,
    REVIEWER,
    URL,
    body,
    offline_network,  # noqa: F401
    receipt,
)

from eii_custodian.publicdata.company_web.contracts import Company, WebError
from eii_custodian.publicdata.company_web.evidence import (
    Outcome,
    PageOutcome,
    reconcile,
)
from eii_custodian.publicdata.company_web.parse import extract
from eii_custodian.publicdata.company_web.review import record


def outcome():
    data = body()
    fields = extract(
        data, Company("syn-a", NAME, "register", {}), receipt(data)
    ).candidates
    return Outcome(
        "syn-a", "searched", (PageOutcome(URL, "matched", fields, "a" * 64),)
    )


def test_pending_is_never_retained_and_counts_reconcile() -> None:
    item = outcome()
    result = reconcile(("syn-a",), {"syn-a": (URL,)}, (item,), {}, IDENTITY)
    assert result.counts["companies"] == 1
    assert result.counts["pages"] == 1
    assert result.counts["pending"] == 4
    assert result.counts["retained"] == 0
    field = item.pages[0].candidates[0]
    reviews = {field.digest: record(field, REVIEWER, "accepted")}
    result = reconcile(("syn-a",), {"syn-a": (URL,)}, (item,), reviews, IDENTITY)
    assert result.counts["retained"] == 1
    assert result.counts["pending"] == 3


@pytest.mark.parametrize(
    "plant",
    [
        "omitted_company",
        "duplicate_company",
        "omitted_page",
        "duplicate_page",
        "invented_status",
        "missing_fields",
        "duplicate_field",
        "unmatched_with_fields",
        "missing_archive",
    ],
)
def test_omitted_duplicate_and_invented_outcomes_refused(plant: str) -> None:
    item = outcome()
    rows = (item,)
    if plant == "omitted_company":
        rows = ()
    elif plant == "duplicate_company":
        rows = (item, item)
    elif plant == "omitted_page":
        rows = (replace(item, pages=()),)
    elif plant == "duplicate_page":
        rows = (replace(item, pages=item.pages * 2),)
    else:
        page = item.pages[0]
        if plant == "invented_status":
            page = replace(page, status="invented")
        elif plant == "missing_fields":
            page = replace(page, candidates=())
        elif plant == "duplicate_field":
            page = replace(page, candidates=page.candidates * 2)
        elif plant == "unmatched_with_fields":
            page = replace(page, status="name_mismatch")
        else:
            page = replace(page, identity="")
        rows = (replace(item, pages=(page,)),)
    with pytest.raises(WebError):
        reconcile(("syn-a",), {"syn-a": (URL,)}, rows, {}, IDENTITY)


def test_missing_fields_are_counted_without_an_invented_fill() -> None:
    data = body(address=None, description=None, url=None)
    fields = extract(
        data, Company("syn-a", NAME, "register", {}), receipt(data)
    ).candidates
    item = Outcome(
        "syn-a", "searched", (PageOutcome(URL, "matched", fields, "a" * 64),)
    )
    result = reconcile(("syn-a",), {"syn-a": (URL,)}, (item,), {}, IDENTITY)
    assert result.counts["missing"] == 3
    assert result.counts["proposed"] == 1


@pytest.mark.parametrize("status", ["obstacle", "unavailable"])
def test_search_failures_remain_in_company_denominator(status: str) -> None:
    rows = (Outcome("syn-a", status, ()),)
    result = reconcile(("syn-a",), {"syn-a": ()}, rows, {}, IDENTITY)
    assert result.counts["companies"] == 1
    assert result.counts["search_" + status] == 1
    assert result.counts["searched"] == 0


def test_unrelated_review_is_not_counted_as_retained() -> None:
    item = outcome()
    field = item.pages[0].candidates[0]
    with pytest.raises(WebError):
        reconcile(
            ("syn-a",),
            {"syn-a": (URL,)},
            (item,),
            {"b" * 64: record(field, REVIEWER, "accepted")},
            IDENTITY,
        )
