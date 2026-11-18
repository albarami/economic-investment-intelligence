"""Tests killing mutation survivors in investment_contracts.py."""

from __future__ import annotations

from eii_custodian.publicdata.investment_contracts import (
    PROVENANCE_PUBLIC,
    SourceEnvelope,
    accept_project_slot,
    https_url,
    parse_announced,
    parse_decimal,
    period_is_future,
    retrieval_year,
    snake_key,
)


def test_missing_lineage_fields() -> None:
    envelope = SourceEnvelope(
        source_id="src",
        publisher="",
        page_url="https://a.b",
        licence_id="l",
        licence_basis="b",
        decision_record="d",
        terms_sha256="sha",
        terms_url="https://t.c",
        retrieved_utc="2026-11-18T00:00:00Z",
        page_sha256="sha",
        method="m",
        method_version="v",
    )
    assert envelope.missing() == "publisher"


def test_missing_terms_url() -> None:
    envelope = SourceEnvelope(
        source_id="src",
        publisher="p",
        page_url="https://a.b",
        licence_id="l",
        licence_basis="b",
        decision_record="d",
        terms_sha256="sha",
        terms_url="",
        retrieved_utc="2026-11-18T00:00:00Z",
        page_sha256="sha",
        method="m",
        method_version="v",
    )
    assert envelope.missing() == "terms_url"


def test_fail_default_and_fields() -> None:
    envelope = SourceEnvelope(
        source_id="src_1",
        publisher="p",
        page_url="https://page.invalid",
        licence_id="l",
        licence_basis="b",
        decision_record="d",
        terms_sha256="sha",
        terms_url="https://terms.invalid",
        retrieved_utc="2026-11-18T00:00:00Z",
        page_sha256="sha",
        method="m",
        method_version="v",
    )
    from eii_custodian.publicdata.investment_contracts import fail

    failure = fail(envelope, "SYN-check", "SYN-expected", "SYN-observed")
    assert failure.code == 1
    assert failure.source_id == "src_1"
    assert failure.url == "https://page.invalid"


def test_parse_decimal_signed() -> None:
    # 12: signed defaults to False
    assert parse_decimal("-1.0", precision=18, scale=2) is None
    # 13: body = text[2:] instead of [1:]
    assert parse_decimal("-1.0", precision=18, scale=2, signed=True) == "-1.0"
    # 14: if body == "" and _DECIMAL.fullmatch(body) is None:
    assert parse_decimal("SYN-A", precision=18, scale=2) is None


def test_parse_announced_month() -> None:
    # 17: int(text[6:7]) converts "2026-13" to 3, which is <= 12
    assert parse_announced("2026-13") is None
    # 19, 20: 2 <= month, 1 < month
    assert parse_announced("2026-01") == "2026-01"
    # 21: month < 12
    assert parse_announced("2026-12") == "2026-12"
    # 22: month <= 13
    assert parse_announced("2026-13") is None


def test_snake_key_mutations() -> None:
    # 23-27, 30, 31
    assert snake_key("syn_key") == "syn_key"
    # 28, 29: replace("XX-XX", "_"), replace("-", "XX_XX")
    assert snake_key("syn-key") == "syn_key"


def test_https_url_mutations() -> None:
    assert https_url("https://a.b") is True
    assert https_url("http://a.b") is False


def test_accept_project_slot_mutations() -> None:
    # 36-43: Invalid provenance
    failure1 = accept_project_slot("SYN_PROV", "")
    assert failure1 is not None
    assert failure1.code == 1
    assert failure1.source_id == "fdi_projects"
    assert failure1.url == ""
    assert failure1.check == "provenance"
    assert failure1.expected == PROVENANCE_PUBLIC
    assert failure1.observed == "SYN_PROV"

    # 44-55: Invalid join key
    failure2 = accept_project_slot(PROVENANCE_PUBLIC, "SYN_JOIN")
    assert failure2 is not None
    assert failure2.code == 1
    assert failure2.source_id == "fdi_projects"
    assert failure2.url == ""
    assert failure2.check == "prohibited_join"
    assert failure2.expected == "no join"
    assert failure2.observed == "joined"


def test_retrieval_year_mutations() -> None:
    # 56, 57: length checks
    assert retrieval_year("2026") == 2026


def test_period_is_future_mutations() -> None:
    # 58, 59: period[:5]
    assert period_is_future("2027-11", "2026-11-18") is True
    # 60: >= year
    assert period_is_future("2026-11", "2026-11-18") is False
