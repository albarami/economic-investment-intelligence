"""Pins the arrival-row fields and period refusals the splits campaign left alive."""

from __future__ import annotations

from decimal import Decimal

import pytest

from eii_custodian.publicdata.additions import splits as split_parse
from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.additions.splits import (
    _month_of,
    _Role,
    _trends,
    _wide,
    _wide_shared,
)
from eii_custodian.publicdata.fetch.registry import Entry

_MODES = {"modes": ["Air", "Land", "Sea"]}
_REGIONS = {"regions": ["Europe"]}


def _role(kind: str, table_code: str | None) -> _Role:
    return _Role(
        kind,
        None,
        None,
        None,
        "number",
        False,
        False,
        table_code,
        None,
        None,
    )


def _entry() -> Entry:
    return Entry(
        key="visitors_markets/invented-arrivals",
        source_id="visitors_markets",
        slug="invented-arrivals",
        kind="portal_dataset",
        title_en="invented arrivals",
        publisher="National Planning Council",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host="www.data.gov.qa",
        url="https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/invented/exports/json",
        terms_url="",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_visitor_markets",),
        caveat_keys=(),
        columns=(("mode_of_entry", "string"),),
        row_count_min=1,
        row_count_max=1,
        period_first="2024-06",
        period_last="2024-06",
        period_field="sit=columns;form=month_name_year",
        reconciliation="none",
        skip_reason="",
        extension="json",
        landing_url="https://www.data.gov.qa/explore/dataset/invented/",
        licence_url="https://www.data.gov.qa/pages/license/annexes",
    )


def test_a_missing_table_code_is_an_empty_string() -> None:
    """An arrival role with no table code stores an empty code, not a filler."""
    trends = _trends(
        {"mode_of_transportation": "Air", "number": "3"},
        _role("arrivals_trends", None),
        _MODES,
        {},
    )
    assert trends == {
        "table_code": "",
        "nationality_group": "all",
        "breakdown_key": "mode_of_transportation=Air",
        "indicator": "arrivals",
        "value": Decimal("3"),
        "unit": "to_be_confirmed",
    }
    mode = _wide_shared(
        {"mode_of_entry": "Air"},
        _role("arrivals_mode", None),
        _MODES,
    )
    assert mode == {
        "table_code": "",
        "nationality_group": "all",
        "breakdown_key": "mode_of_entry=Air",
        "indicator": "arrivals",
        "unit": "to_be_confirmed",
    }
    region = _wide_shared(
        {"region": "Europe"},
        _role("arrivals_region", None),
        _REGIONS,
    )
    assert region == {
        "table_code": "",
        "nationality_group": "Europe",
        "breakdown_key": "ALL",
        "indicator": "arrivals",
        "unit": "to_be_confirmed",
    }


def test_a_non_text_column_name_is_refused() -> None:
    """A wide row whose column name is not text is a period-form refusal."""
    source: dict[object, object] = {"mode_of_entry": "Air", 7: "1"}
    with pytest.raises(AdditionError) as caught:
        _wide(
            _entry(),
            source,
            _role("arrivals_mode", "arrivals_by_mode"),
            _MODES,
            {},
            {"retrieved_utc": "2026-01-02T03:04:05Z", "sha256": "abc"},
        )
    assert caught.value.name == "period_form"


def test_unequal_month_bounds_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two different bounds from one column name are a period-form refusal."""

    def bounds(rows: list[object], rule: object) -> tuple[str, str]:
        return ("2024-06", "2024-07")

    monkeypatch.setattr(split_parse, "observe_period_bounds", bounds)
    with pytest.raises(AdditionError) as caught:
        _month_of("june_2024")
    assert caught.value.name == "period_form"
