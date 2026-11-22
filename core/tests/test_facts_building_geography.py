"""Building namespace, preserving the existing public-feature restrictions."""

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from test_facts_model import candidate

from eii_core.facts import Fact


def building(**changes):
    return candidate(
        **{
            "unit": "metres",
            "geography": {"kind": "public", "public_code": "building:SYN-B-alpha"},
            **changes,
        }
    )


@pytest.mark.parametrize("status", ["observed", "inferred"])
def test_building_recorded_and_fallback(status):
    fact = Fact.model_validate(building(evidence_status=status))
    assert fact.geography["public_code"] == "building:SYN-B-alpha"


@pytest.mark.parametrize(
    "changes,reason",
    [
        (
            {"geography": {"kind": "public", "public_code": "buildings:SYN-B-alpha"}},
            "geography_invalid",
        ),
        ({"evidence_status": "still_to_test"}, "building_status_invalid"),
        ({"provenance": "synthetic"}, "building_status_invalid"),
        ({"input_classes": ["synthetic"]}, "building_status_invalid"),
        ({"unit": "count"}, "building_unit_invalid"),
    ],
)
def test_building_refusal(changes, reason):
    with pytest.raises(ValueError, match=reason):
        Fact.model_validate(building(**changes))


@given(st.text())
@example("")
@example("SYN-B-alpha\nbeta")
@example("SYN-B-عربي:alpha beta")
def test_canonical_id_is_not_rewritten(suffix):
    code = "building:" + suffix
    row = building(geography={"kind": "public", "public_code": code})
    if not suffix or "\n" in suffix:
        with pytest.raises(ValueError, match="geography_invalid"):
            Fact.model_validate(row)
    else:
        assert Fact.model_validate(row).geography["public_code"] == code


@given(
    provenance=st.sampled_from(["public", "synthetic", "simulated", "suppressed"]),
    classes=st.lists(
        st.sampled_from(["public", "synthetic", "simulated", "user_input"])
    ),
    status=st.sampled_from(["observed", "inferred", "still_to_test"]),
    unit=st.one_of(st.just("metres"), st.text()),
)
@example(provenance="public", classes=["public"], status="observed", unit="metres")
@example(provenance="public", classes=["public"], status="inferred", unit="metres")
def test_building_contract_over_its_input_domain(provenance, classes, status, unit):
    row = building(
        provenance=provenance, input_classes=classes, evidence_status=status, unit=unit
    )
    if provenance != "public" or classes != ["public"] or status == "still_to_test":
        reason = "building_status_invalid"
    elif unit != "metres":
        reason = "building_unit_invalid"
    else:
        assert Fact.model_validate(row).geography == row["geography"]
        return
    with pytest.raises(ValueError, match=reason):
        Fact.model_validate(row)


def test_feature_stays_observed_only():
    row = building(geography={"kind": "public", "public_code": "feature:SYN-B-alpha"})
    Fact.model_validate(row)
    row["evidence_status"] = "inferred"
    with pytest.raises(ValueError, match="published_status_invalid"):
        Fact.model_validate(row)
