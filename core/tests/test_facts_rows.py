"""S3-T06 survivor regressions; all identities and sources are invented."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from method_rows import chain
from test_facts_model import chain_rows, identity_inputs

from eii_core.calc.facts import SourceChain
from eii_core.facts import fact_id, validate_chain


def unchecked(value: object) -> Any:
    """Pass an intentionally ill-typed caller value without suppressing checks."""
    return value


def refusal(call: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError) as caught:
        call()
    assert str(caught.value) == message


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"metric_key": "SYN-unknown"}, "metric_unknown"),
        ({"qualifiers": {"SYN-unknown": "SYN-a"}}, "qualifier_unknown"),
        ({"qualifiers": {"activity": 1}}, "qualifier_unknown"),
    ],
)
def test_identity_refusals(changes, message):
    args = dict(identity_inputs(), **changes)
    refusal(lambda: fact_id(**unchecked(args)), message)


def test_canonical_identity_bytes():
    # Independent SHA-256 vector over this literal UTF-8 preimage, first 32 hex:
    # {"geography":{"kind":"national"},"metric_key":"licence_density",
    # "period":"2025","qualifiers":{"activity":"SYN-ع"},
    # "release_id":"SYN-release"} (joined without whitespace/newlines).
    args = dict(
        identity_inputs(),
        release_id="SYN-release",
        qualifiers={"activity": "SYN-ع"},
    )
    assert fact_id(**args) == ("f_9e0429929ccc245a96b3517e" + "0519" + "1202")


def test_nonfinite_identity_refusal():
    args = dict(identity_inputs(), release_id=unchecked(float("nan")))
    refusal(
        lambda: fact_id(**args),
        "Out of range float values are not JSON compliant: nan",
    )


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("table_name", "", "lineage_table_missing"),
        ("table_name", 1, "lineage_table_missing"),
        ("table_name", "SYN-other", "lineage_table_mismatch"),
        ("transform", "", "lineage_transform_missing"),
        ("input_class", "synthetic", "lineage_class_invalid"),
    ],
)
def test_line_refusals(field, value, message):
    lines, sources = chain_rows()
    lines[0][field] = value
    assert validate_chain("lin_pub_licence_active", lines, sources) == message


@pytest.mark.parametrize(
    "field,message",
    [
        ("publisher", "source_publisher_missing"),
        ("title", "source_title_missing"),
        ("licence", "source_licence_missing"),
        ("url", "source_url_missing"),
        ("sha256", "source_hash_missing"),
        ("retrieved_on", "source_retrieval_missing"),
    ],
)
def test_source_refusals(field, message):
    lines, sources = chain_rows()
    sources[0][field] = ""
    assert validate_chain("lin_pub_licence_active", lines, sources) == message


def test_missing_line_refusal():
    _, sources = chain_rows()
    assert validate_chain("lin_pub_licence_active", [], sources) == "lineage_missing"


def test_missing_source_refusal():
    lines, _ = chain_rows()
    assert validate_chain("lin_pub_licence_active", lines, []) == "source_missing"


def test_numerator_refusal_and_match():
    lines, sources = chain_rows()
    assert (
        validate_chain(
            "lin_pub_licence_active", lines, sources, numerator_table="SYN-other"
        )
        == "lineage_numerator_mismatch"
    )
    assert (
        validate_chain(
            "lin_pub_licence_active",
            lines,
            sources,
            numerator_table="pub_licence_active",
        )
        is None
    )


def test_suffixed_lineage_and_uppercase_transform():
    lines, sources = chain_rows()
    lines[0]["lineage_id"] = "lin_pub_licence_active_SYN"
    lines[0]["transform"] = "SYN.Module@v1"
    assert validate_chain("lin_pub_licence_active_SYN", lines, sources) is None


def required_source() -> SourceChain:
    # Reuse the invented registry fixture and chain builder, no external reads.
    _, sources = chain_rows()
    source = sources[0]
    return replace(
        chain(),
        publisher=source["publisher"],
        dataset=source["title"],
        url=source["url"],
        licence=source["licence"],
        retrieved="2025-01-01",
        sha256=source["sha256"],
    )


def test_required_source_matches():
    lines, sources = chain_rows()
    assert (
        validate_chain(
            "lin_pub_licence_active",
            lines,
            sources,
            required_sources=(required_source(),),
        )
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"publisher": "SYN-other"},
        {"dataset": "SYN-other"},
        {"url": "https://example.invalid/SYN-other"},
        {"licence": "SYN-other"},
        {"retrieved": "2025-01-02"},
        {"sha256": "b" * 64},
    ],
)
def test_required_source_mismatch(changes):
    lines, sources = chain_rows()
    assert (
        validate_chain(
            "lin_pub_licence_active",
            lines,
            sources,
            required_sources=(replace(required_source(), **changes),),
        )
        == "lineage_inputs_incomplete"
    )
