"""S2-T08 part B, OI-277: count award names unmatched only by a double space.

The ruled normalisation (compatibility form, case fold, whitespace collapse,
then punctuation removal) leaves "Al - Rayyan" with a double space, so such a
name is counted unmatched, in the safe direction. The first live match counts
those names; matching itself, the ruled order and the registration gate are
unchanged. Only a count is recorded, never a name. Every name is invented.
"""

from __future__ import annotations

from custodian.tests.test_awards_survivors_3 import fetch, setup
from custodian.tests.test_s2_t29_awards import profile, row

from eii_custodian.publicdata.fetch.award_checks import (
    double_space_only,
    match_register,
    normalise_name,
)

REG = "SYN-reg"


def _register(name: str, registration: str = REG) -> dict[str, str]:
    return {"registration": registration, "name": name}


def _count(company: str, register: list[dict[str, str]]) -> tuple[int, str]:
    rows = [dict(row(), syn_company=company)]
    match = match_register(rows, profile(), register)
    return double_space_only(match, profile(), register), match["rows"][0]["reason"]


def test_the_ruled_normalisation_is_unchanged() -> None:
    assert normalise_name("SYN - Rayyan") == "syn  rayyan"
    assert normalise_name("SYN Rayyan") == "syn rayyan"


def test_a_name_differing_only_by_a_double_space_stays_unmatched_and_is_counted() -> (
    None
):
    assert _count("SYN - Rayyan", [_register("SYN Rayyan")]) == (1, "name_mismatch")
    assert _count("SYN Rayyan", [_register("SYN - Rayyan")]) == (1, "name_mismatch")


def test_other_unmatched_names_are_not_counted() -> None:
    # A different word, a missing registration and an ambiguous registration
    # are not double-space differences.
    assert _count("SYN - Rayyon", [_register("SYN Rayyan")]) == (0, "name_mismatch")
    assert _count("SYN - Rayyan", [_register("SYN Rayyan", "SYN-other")]) == (
        0,
        "registration_unmatched",
    )
    ambiguous = [_register("SYN Rayyan"), _register("SYN Rayyan")]
    assert _count("SYN - Rayyan", ambiguous) == (0, "registration_ambiguous")
    # A name that does not reduce to the same words is not counted.
    assert _count("SYN-Rayyan", [_register("SYN Rayyan")]) == (0, "name_mismatch")


def test_a_matched_name_is_not_counted() -> None:
    assert _count("SYN Rayyan!", [_register("SYN Rayyan")]) == (0, "matched")


def test_several_rows_are_counted_once_each() -> None:
    register = [_register("SYN Rayyan"), _register("SYN Wakra", "SYN-reg-2")]
    rows = [
        dict(row(0), syn_company="SYN - Rayyan"),
        dict(row(1), syn_company="SYN Rayyan"),
        dict(row(2), syn_company="SYN / Wakra", syn_reg="SYN-reg-2"),
        dict(row(3), syn_company="SYN Other"),
    ]
    match = match_register(rows, profile(), register)
    assert match["matched"] == 1
    assert double_space_only(match, profile(), register) == 2


def test_the_receipt_records_the_count_and_no_name(tmp_path, monkeypatch) -> None:
    entry, _, body = setup(tmp_path, monkeypatch, version=1)
    result = fetch(entry, tmp_path, body)
    count = result.sidecar["registration_double_space_only"]
    assert type(count) is int and count == 0
