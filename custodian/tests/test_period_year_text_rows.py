"""S2-T08 part B, mismatch class 2: annual text under a declared period rule.

The live shape pack's Mismatches item 2 names 44 portal rows whose ``year`` field
is four-digit text while their registry rule declared ``form=date``. Only those
rows move to the existing ``year_text`` form. S2-P38 adds the import export on
the lead's separate format evidence. Date parsing is not broadened: the
form list is closed and every other row keeps its strict form. All rows below are
invented; no fetched value is copied.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.transport import Response

REPO = repository_root(Path(__file__))
REGISTRY = REPO / "custodian/publicdata/sources.yaml"
REVIEW = REPO / "custodian/publicdata/review/s2_t08_source_review.yaml"
YEAR_TEXT = "sit=row;form=year_text;field=year"
DATE_RULE = "sit=row;form=date;field=year"
# The closed list of Mismatches item 2, typed from the shape pack's per-source
# rows that were refused with period_form. Nothing derives it from the registry.
EVIDENCED = frozenset(
    {
        "bank_credit_act/local-banks-credit-by-economic-activity",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-daayen-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-khor-and-al-thakhira",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-rayyan-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-shamal-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-wakrah-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-doha-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-umm-slal-municipality0",
        "coverage_ext/electricity-network-coverage",
        "coverage_ext/electricity-network-coverage-by-municipality",
        "coverage_ext/proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender",
        "coverage_ext/proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender-and-municipality",
        "coverage_ext/sdg-9-c-1-proportion-of-population-covered-by-a-mobile-network-by-technology",
        "coverage_ext/water-supply-coverage",
        "coverage_ext/water-supply-coverage-by-municipality",
        "dcool_capacity/design-cooling-capacity-by-status-municipality-and-sector-tr",
        "fdi_stats/sdg-17-3-1-foreign-direct-investment-inflows",
        "hotel_ext/number-of-hotel-beds-by-hotel-class",
        "hotel_ext/number-of-hotel-guests-and-nights-of-stay-by-nationality",
        "hotel_ext/number-of-hotel-rooms-by-hotel-class",
        "hotel_ext/number-of-hotels-by-hotel-class",
        "hotel_ext/number-of-hotels-rooms-and-beds-by-hotel-type",
        "jobseekers/qatari-unemployed-15-by-gender-and-willingness-to-work-quarterly",
        "jobseekers/qatari-unemployed-15-not-willing-to-work-by-reason-quarterly",
        "jobseekers/qatari-unemployed-15-with-secondary-education-and-training-quarterly",
        "jobseekers/unemployed-qataris-15-years-and-above-by-gender-and-whether-offered-work-in-private-sector",
        "jobseekers/unemployed-qataris-15-years-and-above-by-gender-and-willingness-to-work-in-private-sector",
        "jobseekers/unemployed-qataris-15-years-and-above-with-secondary-education-who-attended-training-programs-by",
        "jobseekers/unemployed-qataris-less-than-secondary-by-gender-and-readiness-to-train-for-craft-work0",
        "jobseekers/unemployed-qataris-not-willing-to-work-in-the-private-sector-by-gender-and-reasons",
        "jobseekers/unemployed-qataris-with-secondary-education-and-training-courses-refusing-work-in-private-sector-by",
        "price_ext/producer-price-index-ppi",
        "price_ext/producer-price-index-ppi-by-activity-monthly",
        "talent_ext/education-statistics-number-of-graduates-on-scholarships-abroad-by-field-of-study-and-gender",
        "talent_ext/trainees-at-the-private-training-centers-by-employment-status-gender-nationality-and-field-of",
        "talent_ext/trainees-at-the-private-training-centers-by-field-of-training-gender-nationality-and-age-groups",
        "trade_ext/imports-by-nature-of-items-and-year",
        "trade_ext/imports-by-utilization-of-items-and-year",
        "trade_ext/qatar-export-statistics-2019-2024",
        "utilities_ext/operational-peak-district-cooling-load",
        "utilities_ext/sectoral-electricity-consumption-mwh",
        "utilities_ext/total-electricity-consumption-by-sectors",
        "utilities_ext/total-water-consumption-by-sectors",
    }
)
# S2-P38: .overnight/IN/lead-probe.txt (2026-11-21) evidences the import
# JSON export as four-digit year text. Keep the original hashed shape-pack
# review's EVIDENCED set separate; that review did not evidence this export.
YEAR_TEXT_KEYS = EVIDENCED | {"trade_ext/qatar-imports-2014-2018"}
# The remaining export passed under the strict date form.
STRICT = frozenset(
    {
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-shahhaniya-municipality",
    }
)


def _entries() -> dict[str, Entry]:
    return {entry.key: entry for entry in load_registry(REGISTRY)}


def _transport(entry: Entry, records: list[dict[str, object]]):
    def transport(url: str) -> Response:
        if url == entry.url:
            payload: object = records
        else:
            payload = {
                "metas": {
                    "default": {
                        "publisher": entry.publisher,
                        "license": "CC BY",
                        "license_url": "https://creativecommons.org/licenses/by/4.0/",
                        "modified": "2030-01-01",
                    }
                }
            }
        return Response(final_url=url, body=json.dumps(payload).encode(), hops=())

    return transport


def _invented(entry: Entry, years: list[object]) -> list[dict[str, object]]:
    rows = []
    for year in years:
        row: dict[str, object] = {
            name: {"string": "invented", "number": 2.5, "integer": 2}.get(kind, {})
            for name, kind in entry.columns
        }
        row["year"] = year
        rows.append(row)
    return rows


def _fetch(tmp_path: Path, entry: Entry, years: list[object]):
    sized = replace(
        entry,
        row_count_min=len(years),
        row_count_max=len(years),
        terms_url="",
    )
    return fetch_entry(
        sized,
        _transport(sized, _invented(sized, years)),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda _: None,
    )


def test_exactly_the_evidenced_rows_declare_annual_text() -> None:
    entries = _entries()
    assert len(EVIDENCED) == 44
    assert YEAR_TEXT_KEYS <= set(entries)
    for key in sorted(YEAR_TEXT_KEYS):
        entry = entries[key]
        assert entry.period_field == YEAR_TEXT, key
        assert len(entry.period_first) == 4 and entry.period_first.isdigit(), key
        assert len(entry.period_last) == 4 and entry.period_last.isdigit(), key
        assert entry.period_first <= entry.period_last, key
        if key in EVIDENCED:
            assert "mismatch 2" in entry.basis_note, key
    for key in sorted(STRICT):
        assert entries[key].period_field == DATE_RULE, key
        assert entries[key].period_last.endswith("-01-01"), key


def test_bounds_keep_the_reviewed_years() -> None:
    # The old date bounds were January-first dates of the same years; the
    # correction keeps the year and drops the invented day, nothing else.
    old = {
        "bank_credit_act/local-banks-credit-by-economic-activity": ("2012", "2022"),
        "fdi_stats/sdg-17-3-1-foreign-direct-investment-inflows": ("1990", "2024"),
        "price_ext/producer-price-index-ppi": ("2020", "2026"),
        "utilities_ext/sectoral-electricity-consumption-mwh": ("2023", "2024"),
    }
    entries = _entries()
    for key, bounds in old.items():
        assert (entries[key].period_first, entries[key].period_last) == bounds


def test_review_record_lists_every_corrected_row_and_no_other() -> None:
    review = yaml.safe_load(REVIEW.read_text(encoding="utf-8"))
    rows = [row for row in review["rows"] if row["mismatch"] == 2]
    assert {row["key"] for row in rows} == EVIDENCED
    assert len(rows) == len(EVIDENCED)
    for row in rows:
        assert row["change"]["period_field"] == {"from": DATE_RULE, "to": YEAR_TEXT}
        assert len(row["export_sha256"]) == 64
        int(row["export_sha256"], 16)


def test_annual_text_is_admitted_with_its_years(tmp_path: Path) -> None:
    entry = _entries()["bank_credit_act/local-banks-credit-by-economic-activity"]
    assert _fetch(tmp_path, entry, ["2012", "2022"]) is None
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert (receipt["period_first"], receipt["period_last"]) == ("2012", "2022")


@pytest.mark.parametrize(
    "year",
    # "\u0662\u0660\u0662\u0662" is the year in Arabic-Indic digits: \d alone
    # would admit it, and it would then sort after every ASCII year.
    [
        "2022-01-01",
        None,
        "22",
        "2022 ",
        " 2022",
        "2022\n",
        "\u0662\u0660\u0662\u0662",
        "\uff12\uff10\uff12\uff12",
        "2022a",
        "20220",
    ],
)
def test_other_text_forms_are_refused_under_annual_text(
    tmp_path: Path, year: object
) -> None:
    entry = _entries()["bank_credit_act/local-banks-credit-by-economic-activity"]
    failure = _fetch(tmp_path, entry, ["2012", year])
    assert failure is not None
    assert failure.check == "period_form"
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize("year", [2022, 2022.0, True])
def test_numeric_years_are_refused_by_the_declared_text_column(
    tmp_path: Path, year: object
) -> None:
    # The column stays declared string, so a number is refused before the rule.
    entry = _entries()["bank_credit_act/local-banks-credit-by-economic-activity"]
    failure = _fetch(tmp_path, entry, ["2012", year])
    assert failure is not None
    assert (failure.check, failure.expected) == ("schema_retyped", "year:string")
    assert not list(tmp_path.rglob("*.json"))


def test_annual_text_earlier_than_the_last_year_is_refused(tmp_path: Path) -> None:
    entry = _entries()["bank_credit_act/local-banks-credit-by-economic-activity"]
    failure = _fetch(tmp_path, entry, ["2012", "2021"])
    assert failure is not None
    assert (failure.check, failure.expected, failure.observed) == (
        "period_last",
        "2022",
        "2021",
    )


def test_strict_date_rows_still_refuse_annual_text(tmp_path: Path) -> None:
    key = next(iter(sorted(STRICT)))
    entry = _entries()[key]
    failure = _fetch(tmp_path, entry, ["2019", "2023"])
    assert failure is not None
    assert failure.check == "period_form"
    assert _fetch(tmp_path / "date", entry, ["2019-01-01", "2023-01-01"]) is None


@pytest.mark.parametrize(
    "year",
    [
        "\u0662\u0660\u0662\u0662",
        "\uff12\uff10\uff12\uff12",
        "\u09e8\u09e6\u09e8\u09e8",
    ],
)
def test_year_text_admits_ascii_digits_only(year: str) -> None:
    from eii_custodian.publicdata.additions.common import (
        AdditionError,
        parse_period_value,
    )

    assert parse_period_value("2022", "year_text") == "2022"
    with pytest.raises(AdditionError) as refused:
        parse_period_value(year, "year_text")
    assert refused.value.name == "period_form"
