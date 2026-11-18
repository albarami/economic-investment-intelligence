"""Closed investment specifications on invented bounds and reserved addresses."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from custodian.tests.test_investment_build_survivors import _failure

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.investment_contracts import Bounds, Confirmation, KindRule


def _confirmation() -> dict[str, object]:
    return {
        "inventory_recorded": True,
        "field_coverage_recorded": True,
        "fixture_comparison_recorded": True,
        "live_page_compared": False,
    }


def _dashboard(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    # Measured public bounds are replaced by a wholly invented test specification.
    for name, value in (
        ("MEASURED_ROW_MIN", 2),
        ("MEASURED_ROW_MAX", 9),
        ("MEASURED_PERIOD_FIRST", "2001"),
        ("MEASURED_PERIOD_LAST", "2003"),
    ):
        monkeypatch.setattr(build, name, value)
    return {
        "confirmation": _confirmation(),
        "row_count_min": 2,
        "row_count_max": 9,
        "period_field": "announced",
        "period_first": "2001",
        "period_last": "2003",
        "confirmed": True,
        "mapping": {
            "company": "investing_company_name",
            "source_country": "src_country_name",
            "sector": "sector_name",
            "sub_sector": "sub_sector_name",
            "business_function": "function_name",
            "project_type": "project_type_name",
            "capex_value": "capex",
            "jobs": "jobs",
            "announced": "project_date",
            "location_text": "project_address",
        },
        "further_fields": [
            "tech_level_id",
            "src_state_name",
            "freezone_name",
            "city_id",
            "city_name",
            "world_region_id",
            "state_name",
            "src_country_id",
            "src_world_region_name",
            "lat",
            "fdi_sector_id",
            "src_world_region_id",
            "src_state_id",
            "country_name",
            "description",
            "parent_company_name",
            "tags",
            "naics_sub_sector_name",
            "project_year",
            "src_city_name",
            "function_id",
            "state_abbr",
            "src_city_id",
            "capex_currency",
            "sector_id",
            "world_region_name",
            "project_id",
            "parent_company_website",
            "lng",
            "state_id",
            "fdi_sector_name",
            "jobs",
            "country_id",
            "parent_company_id",
            "project_type_id",
            "province",
            "project_month",
        ],
        "caveats": {
            "announced_estimates": "estimates of publicly announced projects",
            "incomplete_coverage": "does not capture all investment projects",
        },
        "capex_unit": "Mn USD",
        "capex_label_words": ["Capex", "Mn", "USD"],
        "location_precision": "location_text",
        "snapshot_identity": "page_sha256",
        "shape_id": "fdi-dashboard-v2",
        "country_iso3": {"SYN-country": "SYN"},
        "municipality_code": {"SYN-area": "SYN-area-AA-0001"},
        "place_key": {"SYN-place": "SYN-place-AA-0001"},
    }


def _rule() -> dict[str, object]:
    return {
        "page_kind": "SYN-page",
        "block_kind": "SYN-block",
        "h3_under_h4": "SYN-under",
        "leading_level": 2,
        "minimum_blocks": 3,
        "minimum_paragraphs": 4,
        "level_kinds": {2: "SYN-level"},
    }


def _agency() -> dict[str, object]:
    return {
        "confirmation": _confirmation(),
        "row_count_min": 2,
        "row_count_max": 9,
        "period_field": "period",
        "period_last": "2003",
        "confirmed": True,
        "snapshot_identity": "aggregate_manifest",
        "furniture_classes": ["SYN-furniture"],
        "kind_rules": {
            kind: _rule()
            for kind in ("sector", "opportunity", "incentive", "setup", "law")
        },
        "pages": [
            {"kind": kind, "url": f"https://syn.invalid/{kind}"}
            for kind in ("sector", "opportunity", "incentive", "setup", "law")
        ],
    }


def _load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str, row: dict[str, object]
) -> object:
    # Use the registry reader's YAML writer so integer heading keys retain type.
    import yaml

    path = tmp_path / "SYN-pages.yaml"
    path.write_text(yaml.safe_dump({"sources": {source: row}}), encoding="utf-8")
    monkeypatch.setattr(build, "_PAGES", path)
    return build.load_source_spec(source, url="https://syn.invalid/page")


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        (
            "confirmation",
            None,
            "1|fdi_projects|https://syn.invalid/page|confirmation_inventory|recorded|missing",
        ),
        (
            "row_count_min",
            "2",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|bounds|incomplete",
        ),
        (
            "cache_only",
            [],
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|cache-only fields|present",
        ),
        (
            "mapping",
            {},
            "1|fdi_projects|https://syn.invalid/page|confirmation_fields|mapped fields|incomplete",
        ),
        (
            "further_fields",
            None,
            "1|fdi_projects|https://syn.invalid/page|confirmation_fields|further fields|incomplete",
        ),
        (
            "further_fields",
            [],
            "1|fdi_projects|https://syn.invalid/page|confirmation_fields|further fields|incomplete",
        ),
        (
            "caveats",
            {},
            "1|fdi_projects|https://syn.invalid/page|missing_caveat|fdi_estimates|incomplete",
        ),
        (
            "capex_unit",
            "SYN-wrong-unit",
            "1|fdi_projects|https://syn.invalid/page|capex_label|Mn USD|missing",
        ),
        (
            "capex_label_words",
            [],
            "1|fdi_projects|https://syn.invalid/page|capex_label|Capex Mn USD|missing",
        ),
        (
            "location_precision",
            "SYN-point",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|location_text|missing",
        ),
        (
            "snapshot_identity",
            "SYN-latest",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|page_sha256|missing",
        ),
        (
            "shape_id",
            "SYN-shape",
            "1|fdi_projects|https://syn.invalid/page|shape_mismatch|fdi-dashboard-v2|missing",
        ),
        (
            "row_count_min",
            3,
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|measured bounds|incomplete",
        ),
        (
            "row_count_max",
            10,
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|measured bounds|incomplete",
        ),
        (
            "period_last",
            "2004",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|measured bounds|incomplete",
        ),
        (
            "period_first",
            "2002",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|measured bounds|incomplete",
        ),
    ],
)
def test_dashboard_spec_reaches_every_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    expected: str,
) -> None:
    row = _dashboard(monkeypatch)
    row[field] = value
    _failure(_load(tmp_path, monkeypatch, "fdi_projects", row), expected)


def test_dashboard_spec_retains_every_contract_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _dashboard(monkeypatch)
    spec = _load(tmp_path, monkeypatch, "fdi_projects", row)
    assert isinstance(spec, build.SourceSpec)
    assert spec.source_id == "fdi_projects"
    assert spec.bounds == Bounds(2, 9, "announced", "2003", True)
    assert spec.confirmation == Confirmation(True, True, True, False)
    assert spec.snapshot_identity == "page_sha256"
    assert spec.currency_rule == "Mn USD"
    assert spec.location_precision == "location_text"
    assert spec.pages == ()
    assert spec.parameter_units == {}
    assert spec.activity_keys == {}
    assert spec.furniture == frozenset()
    assert spec.kind_rules == {}
    assert spec.dashboard is not None
    assert spec.dashboard.shape_id == "fdi-dashboard-v2"
    assert spec.dashboard.fields == frozenset(
        {
            "announced",
            "business_function",
            "capex_value",
            "company",
            "jobs",
            "location_text",
            "project_type",
            "sector",
            "source_country",
            "sub_sector",
        }
    )
    assert spec.dashboard.column_from == {
        "company": "investing_company_name",
        "source_country": "src_country_name",
        "sector": "sector_name",
        "sub_sector": "sub_sector_name",
        "business_function": "function_name",
        "project_type": "project_type_name",
        "capex_value": "capex",
        "jobs": "jobs",
        "announced": "project_date",
        "location_text": "project_address",
    }
    assert spec.dashboard.country_iso3 == {"SYN-country": "SYN"}
    assert spec.dashboard.municipality_code == {"SYN-area": "SYN-area-AA-0001"}
    assert spec.dashboard.place_key == {"SYN-place": "SYN-place-AA-0001"}


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        (
            "confirmation",
            None,
            "1|investqa_pages|https://syn.invalid/page|confirmation_inventory|recorded|missing",
        ),
        (
            "row_count_max",
            "9",
            "1|investqa_pages|https://syn.invalid/page|unconfirmed|bounds|incomplete",
        ),
        (
            "snapshot_identity",
            "SYN-page",
            "1|investqa_pages|https://syn.invalid/page|unconfirmed|aggregate_manifest|missing",
        ),
        (
            "furniture_classes",
            None,
            "1|investqa_pages|https://syn.invalid/page|unconfirmed|furniture|missing",
        ),
        (
            "kind_rules",
            None,
            "1|investqa_pages|https://syn.invalid/page|unconfirmed|kind rules|missing",
        ),
        (
            "pages",
            None,
            "1|investqa_pages|https://syn.invalid/page|missing_page|page family|missing",
        ),
    ],
)
def test_agency_spec_reaches_every_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    expected: str,
) -> None:
    row = _agency()
    row[field] = value
    _failure(_load(tmp_path, monkeypatch, "investqa_pages", row), expected)


def test_agency_spec_preserves_defaults_and_explicit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _agency()
    row["pages"] = [
        {"kind": "sector", "url": "https://syn.invalid/sector"},
        {
            "kind": "law",
            "url": "https://syn.invalid/law",
            "minimum_blocks": 0,
            "minimum_paragraphs": 0,
        },
    ]
    spec = _load(tmp_path, monkeypatch, "investqa_pages", row)
    assert isinstance(spec, build.SourceSpec)
    assert spec.source_id == "investqa_pages"
    assert spec.bounds == Bounds(2, 9, "period", "2003", True)
    assert spec.confirmation == Confirmation(True, True, True, False)
    assert spec.snapshot_identity == "aggregate_manifest"
    assert spec.currency_rule == ""
    assert spec.location_precision == ""
    assert spec.dashboard is None
    assert spec.pages == (
        build.PageSpec("sector", "https://syn.invalid/sector", 3, 4),
        build.PageSpec("law", "https://syn.invalid/law", 0, 0),
    )
    assert spec.parameter_units == {}
    assert spec.activity_keys == {}
    assert spec.furniture == frozenset({"SYN-furniture"})
    assert spec.kind_rules == {
        kind: KindRule("SYN-page", "SYN-block", {2: "SYN-level"}, "SYN-under", 2, 3, 4)
        for kind in ("sector", "opportunity", "incentive", "setup", "law")
    }


@pytest.mark.parametrize(
    "pages",
    [
        None,
        [],
        {},
        [None],
        [{}],
        [{"kind": 3, "url": "https://syn.invalid/page"}],
        [{"kind": "sector", "url": 3}],
        [{"kind": "SYN-unknown", "url": "https://syn.invalid/page"}],
        [{"kind": "sector", "url": "https://syn.invalid/page", "minimum_blocks": True}],
        [
            {
                "kind": "sector",
                "url": "https://syn.invalid/page",
                "minimum_paragraphs": False,
            }
        ],
        [{"kind": "sector", "url": "https://syn.invalid/page", "minimum_blocks": "3"}],
        [
            {
                "kind": "sector",
                "url": "https://syn.invalid/page",
                "minimum_paragraphs": "4",
            }
        ],
    ],
)
def test_pages_type_and_family_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pages: object
) -> None:
    row = _agency()
    row["pages"] = pages
    result = _load(tmp_path, monkeypatch, "investqa_pages", row)
    if pages in (None, [], {}):
        _failure(
            result,
            "1|investqa_pages|https://syn.invalid/page|missing_page|page family|missing",
        )
    else:
        _failure(
            result,
            "1|investqa_pages|https://syn.invalid/page|missing_page|page family|unreadable",
        )


@pytest.mark.parametrize("rules", [None, [], {}, {"sector": None}])
def test_kind_rules_refuse_incomplete_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rules: object
) -> None:
    row = _agency()
    row["kind_rules"] = rules
    _failure(
        _load(tmp_path, monkeypatch, "investqa_pages", row),
        "1|investqa_pages|https://syn.invalid/page|unconfirmed|kind rules|missing",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("page_kind", None),
        ("page_kind", ""),
        ("block_kind", 3),
        ("h3_under_h4", 3),
        ("level_kinds", None),
        ("level_kinds", {True: "SYN-level"}),
        ("level_kinds", {"2": "SYN-level"}),
        ("level_kinds", {2: 3}),
        ("leading_level", True),
        ("leading_level", "2"),
        ("minimum_blocks", False),
        ("minimum_blocks", "3"),
        ("minimum_paragraphs", True),
        ("minimum_paragraphs", "4"),
    ],
)
def test_one_rule_refuses_bad_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    row = _agency()
    rules = {
        kind: _rule() for kind in ("sector", "opportunity", "incentive", "setup", "law")
    }
    rules["law"][field] = value
    row["kind_rules"] = rules
    _failure(
        _load(tmp_path, monkeypatch, "investqa_pages", row),
        "1|investqa_pages|https://syn.invalid/page|unconfirmed|kind rules|unreadable",
    )


def test_one_rule_defaults_and_integer_heading_mapping() -> None:
    # Optional fields are absent through the normal loader as well; isolate defaults.
    assert build._one_rule(
        {
            "page_kind": "SYN-page",
            "leading_level": 0,
            "minimum_blocks": 0,
            "minimum_paragraphs": 0,
        },
        "https://syn.invalid/page",
    ) == KindRule("SYN-page", "", {}, "", 0, 0, 0)
    assert build._level_kinds({2: "SYN-two", 4: "SYN-four"}) == {
        2: "SYN-two",
        4: "SYN-four",
    }


@pytest.mark.parametrize(
    "field",
    [
        "inventory_recorded",
        "field_coverage_recorded",
        "fixture_comparison_recorded",
        "live_page_compared",
    ],
)
@pytest.mark.parametrize("value", [None, 1, "true"])
def test_confirmation_requires_each_literal_boolean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    row = _agency()
    flags = _confirmation()
    flags[field] = value
    row["confirmation"] = flags
    expected = {
        "inventory_recorded": "1|investqa_pages|https://syn.invalid/page|confirmation_inventory|inventory_recorded|missing",
        "field_coverage_recorded": "1|investqa_pages|https://syn.invalid/page|confirmation_inventory|field_coverage_recorded|missing",
        "fixture_comparison_recorded": "1|investqa_pages|https://syn.invalid/page|confirmation_inventory|fixture_comparison_recorded|missing",
        "live_page_compared": "1|investqa_pages|https://syn.invalid/page|confirmation_inventory|live_page_compared|missing",
    }
    _failure(_load(tmp_path, monkeypatch, "investqa_pages", row), expected[field])


@pytest.mark.parametrize(
    "field",
    ["row_count_min", "row_count_max", "period_field", "period_last", "confirmed"],
)
def test_spec_bounds_complete_failure_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    row = _agency()
    del row[field]
    _failure(
        _load(tmp_path, monkeypatch, "investqa_pages", row),
        "1|investqa_pages|https://syn.invalid/page|unconfirmed|bounds|incomplete",
    )


def test_spec_helpers_filter_maps_without_mutating_input() -> None:
    # Public load paths use all three maps; malformed entries must not survive.
    values = {"SYN-good": "SYN-kept", 3: "SYN-drop", "SYN-number": 4}
    original = copy.deepcopy(values)
    assert build._string_map(values) == {"SYN-good": "SYN-kept"}
    assert values == original
    assert build._string_list(["SYN-a", "SYN-b"]) == ("SYN-a", "SYN-b")
    assert build._string_list(["SYN-a", 3]) is None
