"""Exact receipt and sampling contracts on invented award rows (S2-T29)."""

import copy
import random

import pytest
from custodian.tests.test_s2_t29_awards import URL, profile, proof_row, row

from eii_custodian.publicdata.fetch import award_checks as checks


def test_name_normalisation_and_invalid_comparison():
    assert checks.normalise_name("  \uff33\uff39\uff2e\tCompany!  ") == "syn company"
    assert checks._same(row(), {}, profile()) is False
    assert checks._same(row(), dict(proof_row(), syn_value="bad"), profile()) is False
    assert checks._same(row(), dict(proof_row(), syn_value=None), profile()) is False


@pytest.mark.parametrize("seed", [None, True, "73", 1.5])
def test_seed_closed_refusal(seed):
    with pytest.raises(checks.AwardError, match=r"^award_seed_pending$"):
        checks.check_awards([], profile(), seed, lambda _: pytest.fail("proof"))


def test_blank_links_do_not_stop_the_frame():
    result = checks.check_awards(
        [{}, dict(row(), report_url="  "), row()], profile(), 73, lambda _: proof_row()
    )
    assert result == {
        "seed": 73,
        "distinct_frame_count": 1,
        "selected_count": 1,
        "matched": 1,
        "matched_name_not_compared": 0,
        "intake_value_absent": 0,
        "proof_value_absent": 0,
        "proof_mismatch": 0,
        "mismatched": 0,
        "failed_fetches": 0,
        "match_rate": "1",
        "incomplete": True,
        "status": "award_check_incomplete",
        "results": [
            {"report_url": URL + "0", "result": "matched", "reason": "matched"}
        ],
    }


@pytest.mark.parametrize("count", [30, 31])
def test_frame_boundary_and_order(count):
    rows = [row(i) for i in range(count)]
    eligible = sorted(r["report_url"] for r in rows)
    selected = eligible if count == 30 else random.Random(73).sample(eligible, 30)
    result = checks.check_awards(rows, profile(), 73, lambda _: proof_row())
    assert result == {
        "seed": 73,
        "distinct_frame_count": count,
        "selected_count": 30,
        "matched": 30,
        "matched_name_not_compared": 0,
        "intake_value_absent": 0,
        "proof_value_absent": 0,
        "proof_mismatch": 0,
        "mismatched": 0,
        "failed_fetches": 0,
        "match_rate": "1",
        "incomplete": False,
        "status": "sample_recorded",
        "results": [
            {"report_url": url, "result": "matched", "reason": "matched"}
            for url in selected
        ],
    }


@pytest.mark.parametrize("error", ["award", "os"])
def test_failed_fetches_keep_every_result(error):
    def proof(_):
        if error == "award":
            raise checks.AwardError("proof_fetch_failed")
        raise OSError("SYN unavailable")

    result = checks.check_awards([row(0), row(1)], profile(), 73, proof)
    assert result == {
        "seed": 73,
        "distinct_frame_count": 2,
        "selected_count": 2,
        "matched": 0,
        "matched_name_not_compared": 0,
        "intake_value_absent": 0,
        "proof_value_absent": 0,
        "proof_mismatch": 0,
        "mismatched": 0,
        "failed_fetches": 2,
        "match_rate": "0",
        "incomplete": True,
        "status": "award_check_incomplete",
        "results": [
            {
                "report_url": URL + str(i),
                "result": "fetch_failed",
                "reason": "proof_fetch_failed" if error == "award" else "unreachable",
            }
            for i in range(2)
        ],
    }


def test_one_failure_in_full_sample_is_incomplete():
    def proof(url):
        if url == URL + "0":
            raise OSError("SYN unavailable")
        return proof_row()

    result = checks.check_awards([row(i) for i in range(30)], profile(), 73, proof)
    assert result["incomplete"] is True
    assert result["failed_fetches"] == 1
    assert result["status"] == "award_check_incomplete"


@pytest.mark.parametrize("proof", [[], [None], ["SYN invalid"]])
def test_empty_or_nonmapping_proof_refuses(proof):
    with pytest.raises(checks.AwardError, match=r"^schema_missing$"):
        checks.check_awards([row()], profile(), 73, lambda _: proof)


def test_mixed_result_labels():
    result = checks.check_awards(
        [row(i) for i in range(2)],
        profile(),
        73,
        lambda url: (
            dict(proof_row(), syn_value="0.00") if url.endswith("/1") else proof_row()
        ),
    )
    assert result["results"] == [
        {"report_url": URL + "0", "result": "matched", "reason": "matched"},
        {"report_url": URL + "1", "result": "mismatched", "reason": "proof_mismatch"},
    ]
    assert (result["matched"], result["mismatched"]) == (1, 1)


def receipt(count=30, failed=0):
    urls = [row(i) for i in range(count)]

    def proof(url):
        if url == URL + "0" and failed:
            raise OSError("SYN unavailable")
        return proof_row()

    return {
        "source_id": "awards_owner_scrape",
        "award_check": checks.check_awards(urls, profile(), 73, proof),
    }


@pytest.mark.parametrize("count,failed", [(0, 0), (29, 0), (30, 0), (31, 0), (30, 1)])
def test_valid_receipt_boundaries(count, failed):
    assert checks.validate_check_receipt(receipt(count, failed)) is None


@pytest.mark.parametrize(
    "plant",
    [
        "source",
        "extra",
        "seed",
        "negative",
        "boolean",
        "selected",
        "sum",
        "rate",
        "incomplete",
        "status",
        "results_type",
        "results_length",
    ],
)
def test_receipt_independent_fields_refuse(plant):
    value = copy.deepcopy(receipt())
    check = value["award_check"]
    if plant == "source":
        value["source_id"] = "SYN-wrong"
    elif plant == "extra":
        check["SYN-extra"] = None
    else:
        key, bad = {
            "seed": ("seed", True),
            "negative": ("distinct_frame_count", -1),
            "boolean": ("failed_fetches", False),
            "selected": ("selected_count", 29),
            "sum": ("mismatched", 1),
            "rate": ("match_rate", "0"),
            "incomplete": ("incomplete", True),
            "status": ("status", "SYN-wrong"),
            "results_type": ("results", tuple(check["results"])),
            "results_length": ("results", check["results"][:-1]),
        }[plant]
        check[key] = bad
    with pytest.raises(checks.AwardError, match=r"^award_check_metadata_missing$"):
        checks.validate_check_receipt(value)


@pytest.mark.parametrize(
    "missing", ["registration", "name", "award_registration", "award_company"]
)
def test_missing_register_fields_never_match(missing):
    award = dict(row(), syn_reg="XXXX", syn_company="XXXX")
    register = {"registration": "XXXX", "name": "XXXX"}
    if missing.startswith("award_"):
        award.pop(profile()[missing.removeprefix("award_")])
    else:
        register.pop(missing)
    result = checks.match_register([award], profile(), [register])
    assert result == {
        "matched": 0,
        "unmatched": 1,
        "rows": [
            {
                "original": award,
                "reason": "name_mismatch"
                if missing in {"name", "award_company"}
                else "registration_unmatched",
            }
        ],
    }


def test_multiple_register_matches_retain_rows_and_reasons():
    rows = [row(0), row(1)]
    result = checks.match_register(
        rows, profile(), [{"registration": "SYN-reg", "name": "SYN Company"}]
    )
    assert result == {
        "matched": 2,
        "unmatched": 0,
        "rows": [{"original": r, "reason": "matched"} for r in rows],
    }
