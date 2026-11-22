"""L-1423 source shapes, with invented companies, registrations and amounts only."""

import copy
from decimal import Decimal

import pytest
from custodian.tests.test_s2_t29_live_awards import report
from custodian.tests.test_s2_t29_live_shapes import entry
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import award_checks as checks
from eii_custodian.publicdata.fetch.award_links import (
    check_all_awards,
    sample_from_links,
    validate_links_receipt,
)
from eii_custodian.publicdata.fetch.page_records import parse_body

PROFILE = {
    "company": "Company Name",
    "registration": "Commercial Registration Number",
    "value": "Approved Value",
}
URL = "https://www.data.gov.qa/syn-proof/"


def intake(index=0, **changes):
    return {
        "Company Name": "SYN Example",
        "Commercial Registration Number": "SYN/17 | SYN/23",
        "Approved Value": "1,007.00 QAR",
        "report_url": URL + str(index),
        **changes,
    }


def proof(**changes):
    return {
        "Company Name": "SYN Example",
        "Commercial Registration Number": "SYN/23 | SYN/17",
        "Approved Value": "1007.00",
        **changes,
    }


def reason(left=None, right=None):
    return check_all_awards(
        [intake() if left is None else left],
        PROFILE,
        lambda _: proof() if right is None else right,
    )["results"][0]["reason"]


def test_real_shapes_match_on_exact_registration_sets_and_currency_value():
    assert reason() == "matched"
    assert (
        reason(right=proof(**{"Company Name": "شركة مبتكرة"}))
        == "matched_name_not_compared"
    )


@pytest.mark.parametrize("value", ["", "QAR", " QAR ", "   "])
def test_intake_blank_is_absent_never_zero(value):
    assert reason(intake(**{"Approved Value": value})) == "intake_value_absent"


@pytest.mark.parametrize("value", ["", "   "])
def test_canonical_proof_blank_is_absent(value):
    assert reason(right=proof(**{"Approved Value": value})) == "proof_value_absent"


@pytest.mark.parametrize(
    "value",
    [
        "1007.00",
        "1,00.00 QAR",
        "+1007.00 QAR",
        "1e3 QAR",
        "NaN QAR",
        "\u0661\u0660\u0660\u0667.\u0660\u0660 QAR",
        "1007.0 QAR",
        "1007.000 QAR",
        "1007.00 qar",
        "1007.00 QAR\n",
    ],
)
def test_malformed_intake_is_mismatch_not_absence_or_source_refusal(value):
    assert reason(intake(**{"Approved Value": value})) == "proof_mismatch"


@pytest.mark.parametrize(
    "value", ["NaN", "Infinity", "-1007.00", "1e3", "1,007.00", "1007.00 رق", "1007.0"]
)
def test_nondeclared_canonical_proof_is_mismatch(value):
    assert reason(right=proof(**{"Approved Value": value})) == "proof_mismatch"


@pytest.mark.parametrize(
    "registration",
    [
        "SYN/17",
        "SYN/99",
        "SYN/17 | SYN/99",
        "",
        "  ",
        " | ",
        "syn/17 | SYN/23",
        "SYN/17|SYN/23",
    ],
)
def test_registration_requires_nonempty_equal_token_sets(registration):
    assert (
        reason(right=proof(**{"Commercial Registration Number": registration}))
        == "proof_mismatch"
    )


def test_number_column_is_not_used_by_the_proof_compare():
    """Row S4: the intake number column is recorded only; the text column decides."""
    left = intake(**{"Approved Value Number": "9.00"})
    assert reason(left) == "matched"
    assert reason(left, proof(**{"Approved Value": "9.00"})) == "proof_mismatch"


def test_registration_digit_slash_tokens_compare_as_sets():
    """Row S7: the digits/digits token form, in reversed order, matches as a set."""
    left = intake(**{"Commercial Registration Number": "17/23 | SYN/17"})
    assert (
        reason(left, proof(**{"Commercial Registration Number": "SYN/17 | 17/23"}))
        == "matched"
    )
    assert (
        reason(left, proof(**{"Commercial Registration Number": "SYN/17 | 17/24"}))
        == "proof_mismatch"
    )


def test_registration_order_duplicates_and_token_edge_spaces_are_irrelevant():
    assert (
        reason(
            right=proof(
                **{"Commercial Registration Number": " SYN/23 | SYN/17 | SYN/17 "}
            )
        )
        == "matched"
    )


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("SYN Example", "syn example!", "matched"),
        ("SYN Example", "SYN Other", "proof_mismatch"),
        ("شركة مبتكرة", "شركة مختلفة", "proof_mismatch"),
        ("SYN شركة", "SYN شركة", "matched"),
        ("SYN شركة", "SYN مختلفة", "proof_mismatch"),
        ("SYN Example", "شركة مبتكرة", "matched_name_not_compared"),
        ("SYN Example", "SYN شركة", "matched_name_not_compared"),
        ("", "", "matched_name_not_compared"),
        ("123 !", "SYN Example", "matched_name_not_compared"),
        ("Ж", "Ж", "matched"),
    ],
)
def test_script_gate(left, right, expected):
    assert (
        reason(intake(**{"Company Name": left}), proof(**{"Company Name": right}))
        == expected
    )


def test_reason_precedence_before_other_disagreements():
    assert (
        reason(
            intake(**{"Approved Value": "QAR"}),
            proof(**{"Approved Value": "", "Company Name": "SYN Other"}),
        )
        == "intake_value_absent"
    )
    assert (
        reason(
            intake(**{"Approved Value": "SYN malformed"}),
            proof(**{"Approved Value": ""}),
        )
        == "proof_value_absent"
    )


def test_proof_suffix_only_is_nullable_through_the_real_awards_parser():
    dec, body = report()
    body = body.replace("1,007.00 رق".encode(), "رق".encode())
    rows = parse_body(body, entry(dec, "awards_owner_scrape"), dec)
    assert rows[0]["SYN amount"] is None
    assert rows[1]["SYN amount"] == "9.00"


@pytest.mark.parametrize(
    "value", ["1,00.00 رق", "1007.0 رق", "1007.00", "رق SYN", "NaN رق", "1007.00 QAR"]
)
def test_malformed_proof_currency_refuses_schema_missing(value):
    dec, body = report()
    body = body.replace("1,007.00 رق".encode(), value.encode())
    with pytest.raises(ValueError, match=r"^schema_missing$"):
        parse_body(body, entry(dec, "awards_owner_scrape"), dec)


def test_closed_reasons_totals_sample_and_gate_summary():
    from eii_custodian.publicdata.assembly_reports import awards_evidence

    rows = [intake(i) for i in range(30)]
    rows[1]["Company Name"] = "شركة مبتكرة"
    rows[2]["Approved Value"] = "QAR"

    def reader(url):
        return proof(
            **{
                "Approved Value": "" if url == URL + "3" else "1007.00",
                "Commercial Registration Number": "SYN/99"
                if url == URL + "4"
                else "SYN/23 | SYN/17",
            }
        )

    full = check_all_awards(rows, PROFILE, reader)
    assert {
        key: full[key]
        for key in (
            "matched",
            "matched_name_not_compared",
            "intake_value_absent",
            "proof_value_absent",
            "proof_mismatch",
        )
    } == {
        "matched": 27,
        "matched_name_not_compared": 1,
        "intake_value_absent": 1,
        "proof_value_absent": 1,
        "proof_mismatch": 1,
    }
    assert full["match_rate"] == "0.9"
    sample = sample_from_links(full, 73)
    assert sample == checks.check_awards(rows, PROFILE, 73, reader)
    receipt = {
        "source_id": "awards_owner_scrape",
        "award_check_scope": "sample",
        "award_links": full,
        "award_check": sample,
        "sha256": "SYN-hash",
        "registration_double_space_only": 0,
    }
    validate_links_receipt(receipt, rows)
    summary = awards_evidence(receipt, 73)
    assert summary["award_links"]["matched_name_not_compared"] == 1
    assert "results" not in summary["award_links"]
    for key in (
        "matched_name_not_compared",
        "intake_value_absent",
        "proof_value_absent",
        "proof_mismatch",
    ):
        bad = copy.deepcopy(receipt)
        bad["award_links"][key] += 1
        with pytest.raises(checks.AwardError, match=r"^award_links_metadata_missing$"):
            validate_links_receipt(bad)


@given(
    st.lists(
        st.sampled_from(
            [
                "matched",
                "matched_name_not_compared",
                "intake_value_absent",
                "proof_value_absent",
                "proof_mismatch",
                "fetch_failed",
            ]
        ),
        max_size=50,
    )
)
@example([])
@example(["matched_name_not_compared"])
def test_rate_and_reason_partition_oracle(outcomes):
    rows = [intake(i) for i in range(len(outcomes))]
    for item, outcome in zip(rows, outcomes, strict=True):
        if outcome == "intake_value_absent":
            item["Approved Value"] = "QAR"

    def reader(url):
        outcome = outcomes[int(url.rsplit("/", 1)[1])]
        if outcome == "fetch_failed":
            raise OSError("SYN offline failure")
        return proof(
            **{
                "Company Name": "شركة مبتكرة"
                if outcome == "matched_name_not_compared"
                else "SYN Example",
                "Approved Value": "" if outcome == "proof_value_absent" else "1007.00",
                "Commercial Registration Number": "SYN/99"
                if outcome == "proof_mismatch"
                else "SYN/17 | SYN/23",
            }
        )

    full = check_all_awards(rows, PROFILE, reader)
    numerator = sum(
        item in {"matched", "matched_name_not_compared"} for item in outcomes
    )
    assert full["matched"] == numerator
    assert full["match_rate"] == (
        str(Decimal(numerator) / Decimal(len(outcomes))) if outcomes else None
    )
    for key in (
        "matched_name_not_compared",
        "intake_value_absent",
        "proof_value_absent",
        "proof_mismatch",
    ):
        assert full[key] == outcomes.count(key)
    assert full["mismatched"] == sum(
        outcomes.count(key)
        for key in ("intake_value_absent", "proof_value_absent", "proof_mismatch")
    )
    assert sample_from_links(full, 73) == checks.check_awards(rows, PROFILE, 73, reader)


@pytest.mark.parametrize(
    "value,script",
    [
        ("syn", "latin"),
        ("شركة", "arabic"),
        ("syn شركة", "mixed"),
        ("Ж", "mixed"),
        ("123 +", "none"),
        ("\u0301", "none"),
    ],
)
def test_closed_script_classes(value, script):
    assert checks.name_script(value) == script


@pytest.mark.parametrize(
    "field", ["Company Name", "Commercial Registration Number", "Approved Value"]
)
def test_missing_fields_have_closed_reasons(field):
    left, right = intake(), proof()
    left.pop(field)
    right.pop(field)
    assert (
        reason(left, right)
        == {
            "Company Name": "matched_name_not_compared",
            "Commercial Registration Number": "proof_mismatch",
            "Approved Value": "intake_value_absent",
        }[field]
    )


def test_values_must_be_equal_even_when_names_are_not_compared():
    assert reason(right=proof(**{"Approved Value": "1007.01"})) == "proof_mismatch"
    assert (
        reason(
            right=proof(**{"Company Name": "شركة مبتكرة", "Approved Value": "1007.01"})
        )
        == "proof_mismatch"
    )


def test_multiwinner_and_candidate_reason_precedence_is_order_independent():
    from itertools import permutations

    a = intake()
    b = intake(**{"Company Name": "شركة مبتكرة"})
    bad = proof(**{"Approved Value": ""})
    for winners in permutations([a, b]):
        for candidates in permutations([bad, proof()]):
            check = check_all_awards(
                winners, PROFILE, lambda _, candidates=candidates: candidates
            )
            assert check["results"][0]["reason"] == "matched_name_not_compared"
    for winners in permutations([a, intake(**{"Approved Value": "QAR"})]):
        check = check_all_awards(winners, PROFILE, lambda _: [bad])
        assert check["results"][0]["reason"] == "intake_value_absent"
    # An exact same-script candidate earns the stricter match even if another
    # candidate agrees on registration/value with an incomparable name.
    assert (
        reason(right=[proof(**{"Company Name": "شركة مبتكرة"}), proof()]) == "matched"
    )


@pytest.mark.parametrize("scope", ["award_links", "award_check"])
@pytest.mark.parametrize(
    "change", ["reason", "result", "extra", "url", "count", "boolean", "rate"]
)
def test_each_receipt_consumer_refuses_one_changed_field(scope, change):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.assembly_reports import awards_evidence

    rows = [intake(i) for i in range(30)]
    rows[0]["Company Name"] = "شركة مبتكرة"
    full = check_all_awards(rows, PROFILE, lambda _: proof())
    receipt = {
        "source_id": "awards_owner_scrape",
        "award_check_scope": "sample",
        "award_links": full,
        "award_check": sample_from_links(full, 73),
        "sha256": "SYN-hash",
        "registration_double_space_only": 0,
    }
    check = receipt[scope]
    if change in {"reason", "result", "extra", "url"}:
        field, value = {
            "reason": ("reason", "SYN unknown"),
            "result": ("result", "mismatched"),
            "extra": ("SYN extra", "SYN text"),
            "url": ("report_url", "https://example.invalid/syn-proof"),
        }[change]
        check["results"][0][field] = value
    else:
        field, value = {
            "count": ("matched_name_not_compared", 2),
            "boolean": ("matched_name_not_compared", True),
            "rate": ("match_rate", "0"),
        }[change]
        check[field] = value
    validator = (
        checks.validate_check_receipt
        if scope == "award_check"
        else validate_links_receipt
    )
    with pytest.raises(checks.AwardError, match=f"^{scope}_metadata_missing$"):
        validator(receipt)
    with pytest.raises(AssemblyError, match=r"^assembly_t29_refused$"):
        awards_evidence(receipt, 73)


@given(
    st.integers(min_value=0, max_value=999999),
    st.integers(min_value=0, max_value=99),
    st.booleans(),
    st.permutations(["SYN/17", "SYN/23"]),
)
@example(0, 0, False, ["SYN/17", "SYN/23"])
@example(1000, 1, True, ["SYN/23", "SYN/17"])
def test_currency_and_registration_permutation_property(whole, cents, grouped, tokens):
    amount = f"{whole:,}" if grouped else str(whole)
    left = intake(**{"Approved Value": f"{amount}.{cents:02d} QAR"})
    right = proof(
        **{
            "Approved Value": f"{whole}.{cents:02d}",
            "Commercial Registration Number": " | ".join(tokens),
        }
    )
    assert checks._same(left, right, PROFILE)
    # One cent of disagreement must defeat a match, including zero amounts.
    right["Approved Value"] = f"{whole}.{(cents + 1) % 100:02d}"
    assert reason(left, right) == "proof_mismatch"


def test_two_empty_registration_sets_never_match():
    assert (
        reason(
            intake(**{"Commercial Registration Number": " | "}),
            proof(**{"Commercial Registration Number": " | "}),
        )
        == "proof_mismatch"
    )


@pytest.mark.parametrize(
    "item",
    [
        None,
        [],
        {"report_url": URL, "result": "matched"},
        {"report_url": URL, "result": "matched", "reason": 1},
        {"report_url": "", "result": "matched", "reason": "matched"},
        {
            "report_url": "https://example.invalid/syn",
            "result": "matched",
            "reason": "matched",
        },
        {"report_url": URL, "result": "SYN unknown", "reason": "matched"},
        {"report_url": URL, "result": "matched", "reason": "proof_mismatch"},
    ],
)
def test_closed_result_schema_rejects_one_invalid_field(item):
    from eii_custodian.publicdata.fetch.award_links import valid_result

    assert valid_result(item) is False


@pytest.mark.parametrize("field", ["result", "reason"])
def test_result_schema_rejects_unhashable_field(field):
    from eii_custodian.publicdata.fetch.award_links import valid_result

    item = {"report_url": URL, "result": "matched", "reason": "matched"}
    item[field] = []
    assert valid_result(item) is False


def test_sample_receipt_refuses_a_single_duplicate_result_url():
    sample = checks.check_awards(
        [intake(i) for i in range(30)], PROFILE, 73, lambda _: proof()
    )
    sample["results"][0]["report_url"] = sample["results"][1]["report_url"]
    with pytest.raises(checks.AwardError, match=r"^award_check_metadata_missing$"):
        checks.validate_check_receipt(
            {"source_id": "awards_owner_scrape", "award_check": sample}
        )
