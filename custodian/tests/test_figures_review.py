"""Value-free comparison and thin entry on invented tmp_path files only."""

import json
from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata.draw import Figure
from eii_custodian.publicdata.figures_review import compare, validate_record


def figure():
    return Figure(
        "invented",
        "invented",
        "https://example.org",
        "invented filter",
        "23.40",
        "ratio",
    )


@pytest.mark.parametrize(
    "kind,observed,result",
    [
        ("ratio", "23.404", "match"),
        ("ratio", "23.406", "no match"),
        ("money", "23.401", "no match"),
        ("money", "23.400", "match"),
        ("count", "24", "no match"),
        ("ratio", "NaN", "no match"),
        ("ratio", "Infinity", "no match"),
        ("ratio", "invalid", "no match"),
    ],
)
def test_comparison_at_stated_precision(kind, observed, result):
    record = compare([replace(figure(), kind=kind)], {"invented": observed})
    assert record == [
        {"figure_id": "invented", "url": "https://example.org", "result": result}
    ]


def test_reviewer_identity_set_must_match_and_stored_values_are_valid():
    for values in ({}, {"extra": "23.40"}, {"invented": "23.40", "extra": "1"}):
        with pytest.raises(ValueError, match="reviewer_ids_mismatch"):
            compare([figure()], values)
    for value in ("NaN", "bad", "Infinity"):
        with pytest.raises(ValueError, match="figure_invalid"):
            compare([replace(figure(), value=value)], {"invented": "1"})


@pytest.mark.parametrize("kind", ["draw", "verdict"])
def test_review_records_have_no_values(kind):
    row = (
        {
            "figure_id": "invented",
            "source_id": "invented",
            "url": "https://example.org",
            "filter": "invented",
        }
        if kind == "draw"
        else {"figure_id": "invented", "url": "https://example.org", "result": "match"}
    )
    validate_record([row], kind)
    for field in ("value", "observed", "difference", "nested"):
        with pytest.raises(ValueError, match="committed_source_value"):
            validate_record([{**row, field: "23.40"}], kind)


def test_ratio_uses_the_stored_exponent_without_an_invented_precision_floor():
    assert (
        compare([replace(figure(), value="1E+2")], {"invented": "123"})[0]["result"]
        == "match"
    )


def test_script_emits_only_value_free_verdict(tmp_path, capsys):
    from scripts.figures_review import run

    stored, reviewer, output = [
        tmp_path / name for name in ("draw.json", "reviewer.json", "verdict.json")
    ]
    stored.write_text(json.dumps([asdict(figure())]))
    reviewer.write_text(json.dumps({"invented": "23.40"}))
    assert run(stored, reviewer, output) == 0
    assert "23.40" not in output.read_text() + capsys.readouterr().out
    reviewer.write_text(json.dumps({"invented": "24"}))
    assert run(stored, reviewer, output) == 1
    assert json.loads(output.read_text())[0]["result"] == "no match"
    stored.write_text(json.dumps([{**asdict(figure()), "unknown": "secret stand-in"}]))
    with pytest.raises(ValueError, match="figure_schema_invalid"):
        run(stored, reviewer, output)
