"""S2-T17 admission agreement; tracked metadata only, never cached data."""

from dataclasses import replace

import pytest
import yaml

from eii_core.calc.forecast_list import DEFINITIONS
from eii_custodian.publicdata.fetch.forecast_series import load_forecast_series
from eii_custodian.publicdata.fetch.registry import load_registry, registry_path


def committed():
    document = yaml.safe_load(registry_path().read_text())
    return load_forecast_series(document["forecast_series"], load_registry())


def assert_agreement(rows):
    assert {r.key: (r.state, r.table) for r in rows} == {
        r.key: (r.state, r.tables[0] if r.tables else "")
        for r in DEFINITIONS
        if r.input_class == "public" and r.state != "conditional"
    }


def test_public_keys_states_tables_agree():
    assert_agreement(committed())
    by_key = {r.key: r for r in DEFINITIONS}
    assert all(
        by_key[r.key].open_reason == r.reason for r in committed() if r.state == "open"
    )
    conditional = tuple(r for r in DEFINITIONS if r.state == "conditional")
    assert tuple(r.key for r in conditional) == ("establishments_by_area",)
    assert conditional[0].tables == ("pub_register_snapshot",)
    assert conditional[0].input_class == "public"


@pytest.mark.parametrize(
    "field,value",
    [("key", "invented"), ("state", "open"), ("table", "pub_licence_cancelled")],
)
def test_metadata_plants(field, value):
    rows = committed()
    planted = (replace(rows[0], **{field: value}), *rows[1:])
    with pytest.raises(AssertionError):
        assert_agreement(planted)


def test_open_key_promotion_and_construction_substitution():
    for key, changes in (
        ("consumer_prices", {"state": "held"}),
        ("imports_by_product", {"state": "held"}),
        ("construction_pipeline", {"table": "pub_building_permit_issues"}),
    ):
        with pytest.raises(AssertionError):
            assert_agreement(
                tuple(replace(r, **changes) if r.key == key else r for r in committed())
            )
