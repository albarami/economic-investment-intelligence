"""Industry, trade and logistics parsers. Fixtures are invented."""

from __future__ import annotations

import csv
from dataclasses import replace
from decimal import ROUND_DOWN, Context, Decimal, localcontext
from pathlib import Path

import duckdb
import pytest
import yaml
from hypothesis import example, given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.additions.build import parsers
from eii_custodian.publicdata.additions.common import (
    AdditionError,
    Coverage,
    FamilyParse,
    require_lineage,
)
from eii_custodian.publicdata.additions.industry import (
    _crosswalk,
    parse_establishment_size,
    parse_logistics,
    parse_manufacturing,
    parse_trade,
)
from eii_custodian.publicdata.additions.storage import write_parquet
from eii_custodian.publicdata.fetch.registry import Entry, load_registry

REVIEW = Path(__file__).resolve().parents[1] / "publicdata" / "review"
RECEIPT = {
    "retrieved_utc": "2026-03-04T05:06:07Z",
    "sha256": "ab" * 32,
    "source_modified": "2099-01-01",
}
TWO = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-two"
)
WHOLESALE = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-wholesale-and-retail-trade-four-digits"
)
TRANSPORT = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-transport"
)
SOCIAL = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-social-and-personal-services-two-digits"
)
ENERGY = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-energy"
)
ONE = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-one"
)
BUSINESS = (
    "establishments-employees-and-compensation-of-employees-"
    "by-economic-activity-business-services"
)
METALS = "manufacture-of-basic-metals"
TEXTILES = "manufacture-of-textiles"
PHARMA = "manufacture-of-basic-pharmaceutical-products-and-pharmaceutical-preparations"
COMPUTER = "manufacture-of-computer-electronic-and-optical-products"
WOOD = (
    "manufacture-of-manufacture-of-wood-and-of-products-of-wood-"
    "and-cork-except-furniture-manufacture"
)
PRODUCTS = "main-manufacturing-products"
TRADE = (
    "purchases-sales-and-stocks-during-the-year-by-type-of-trade-"
    "wholesale-and-retail-trade-all"
)
CERTIFICATES = "annual-certificates-of-origin-by-type-and-importing-country"
PREVIOUS = (
    "arriving-vessels-gross-and-net-tonnage-by-type-of-vessel-"
    "and-country-of-previous-port"
)
HAMAD = (
    "arriving-vessels-gross-and-net-tonnage-by-type-of-vessel-"
    "and-country-of-registration-hamad-port0"
)
S2_LARGE = "Establishments with 10 Employees and More"
S2_LARGE_AR = "المنشآت 10 مشتغلين فأكثر"
S1_LARGE = "10 Employees and more"
S1_LARGE_AR = "10 مشتغلين فأكثر"
S3_LARGE = "Establishments with 10+ Employee"
WALK = (
    {"published_label": "SYN Land", "iso3": "SLL"},
    {"published_label": "SYN Port", "iso3": "SPT"},
)
EST_METHOD = "eii_custodian.publicdata.additions.industry.parse_establishment_size@1"
MFG_METHOD = "eii_custodian.publicdata.additions.industry.parse_manufacturing@1"
TRADE_METHOD = "eii_custodian.publicdata.additions.industry.parse_trade@1"
LOG_METHOD = "eii_custodian.publicdata.additions.industry.parse_logistics@1"


def _map() -> dict[str, object]:
    loaded = yaml.safe_load(
        (REVIEW / "additions_industry.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(loaded, dict)
    return loaded


def _with_countries(rows: tuple[dict[str, str], ...]) -> dict[str, object]:
    loaded = _map()
    loaded["country_crosswalk"] = [dict(row) for row in rows]
    return loaded


def _entry(source_id: str, slug: str) -> Entry:
    return next(
        entry
        for entry in load_registry()
        if entry.source_id == source_id and entry.slug == slug
    )


def _coverage(parsed: FamilyParse, reason: str) -> int:
    return sum(item.count for item in parsed.coverage if item.reason == reason)


def _lineage(source_key: str, publisher: str, method: str) -> dict[str, object]:
    return {
        "source_key": source_key,
        "publisher": publisher,
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "retrieved_utc": "2026-03-04T05:06:07Z",
        "sha256": "ab" * 32,
        "method": method,
    }


def test_est_size_period_rules_name_year_and_leave_other_families() -> None:
    """The seven size bulletins name the year field.

    The clause on the lf_muni_sex rows is gone: this test asserts only its own
    seven rows.
    """
    entries = load_registry()
    size = [entry for entry in entries if entry.source_id == "est_size_act"]
    assert len(size) == 7
    for entry in size:
        assert entry.period_field == "sit=row;form=year_text;field=year"


def test_a_missing_broken_or_non_utf8_industry_review_stops(tmp_path: Path) -> None:
    """A review file that cannot be opened, decoded or parsed stops by name."""
    entry = _entry("est_size_act", TWO)
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(AdditionError) as absent:
        parse_establishment_size(entry, [], RECEIPT, {}, {"review": missing})
    assert absent.value.name == "field_map_unreadable"
    syntax = tmp_path / "syntax"
    syntax.mkdir()
    (syntax / "additions_industry.yaml").write_text("slugs: [\n", encoding="utf-8")
    with pytest.raises(AdditionError) as broken:
        parse_establishment_size(entry, [], RECEIPT, {}, {"review": syntax})
    assert broken.value.name == "field_map_unreadable"
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "additions_industry.yaml").write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(AdditionError) as decoded:
        parse_establishment_size(entry, [], RECEIPT, {}, {"review": raw})
    assert decoded.value.name == "field_map_unreadable"


def test_industry_parsers_are_registered_by_source_id() -> None:
    """Pass A loads this module's PARSERS by source id."""
    found = parsers()
    assert found["est_size_act"] is parse_establishment_size
    assert found["mfg_industry"] is parse_manufacturing
    assert found["trade_wr"] is parse_trade
    assert found["trade_logistics"] is parse_logistics


def test_size_bulletin_keeps_its_own_class_and_its_own_years() -> None:
    """Size labels are not renamed, and the observed years are the file's years."""
    large = {
        "year": "2015",
        "activity_code": "11",
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "size_of_establishment": S2_LARGE,
        "hjm_lmnsh": S2_LARGE_AR,
        "indicator": "Employees",
        "lbyn": "SYN-IND",
        "value": 14,
    }
    small = {
        "year": "2022",
        "activity_code": "11",
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "size_of_establishment": "Establishments with Less than 10 Employees",
        "hjm_lmnsh": "المنشآت أقل من 10 مشتغلين",
        "indicator": "Establishments",
        "lbyn": "SYN-IND",
        "value": 0,
    }
    parsed = parse_establishment_size(
        _entry("est_size_act", TWO), [large, small], RECEIPT, _map(), {}
    )
    key = f"est_size_act/{TWO}"
    expected = (
        {
            "table_code": TWO,
            "activity_key": "11",
            "size_class": S2_LARGE,
            "period": "2015",
            "indicator": "employees",
            "value": Decimal("14.00"),
            "unit": "to_be_confirmed",
            **_lineage(key, "National Planning Council", EST_METHOD),
        },
        {
            "table_code": TWO,
            "activity_key": "11",
            "size_class": "Establishments with Less than 10 Employees",
            "period": "2022",
            "indicator": "establishments",
            "value": Decimal("0.00"),
            "unit": "to_be_confirmed",
            **_lineage(key, "National Planning Council", EST_METHOD),
        },
    )
    assert parsed.rows == expected
    assert parsed.table == "pub_establishment_size"
    assert parsed.period_first == "2015"
    assert parsed.period_last == "2022"
    assert parsed.questions == ()
    assert "municipality_code" not in parsed.rows[0]
    assert "sex" not in parsed.rows[0]
    assert "nationality" not in parsed.rows[0]
    assert parsed.rows[0]["value"].as_tuple().exponent == -2


def test_bulletins_do_not_share_a_size_class_or_a_last_year() -> None:
    """S1, S2 and S3 stay as published, and transport does not inherit 2022."""
    energy = parse_establishment_size(
        _entry("est_size_act", ENERGY),
        [
            {
                "year": "2018",
                "activity_code": "B",
                "main_economic_activity": "SYN Activity",
                "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                "establishment_size": S1_LARGE,
                "hjm_lmnsh": S1_LARGE_AR,
                "indicator": "Number of Employees",
                "lbyn": "SYN-IND",
                "value": 10,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    transport = parse_establishment_size(
        _entry("est_size_act", TRANSPORT),
        [
            {
                "year": "2014",
                "activity_code": "4911",
                "main_economic_activity": "SYN Activity",
                "main_economic_activity_ar": "SYN-AR",
                "establishment_size": S3_LARGE,
                "establishment_size_ar": "SYN-AR",
                "item_type": "Employee",
                "item_type_ar": "SYN-IND",
                "value": 4,
            },
            {
                "year": "2019",
                "activity_code": "4911",
                "main_economic_activity": "SYN Activity",
                "main_economic_activity_ar": "SYN-AR",
                "establishment_size": S3_LARGE,
                "establishment_size_ar": "SYN-AR",
                "item_type": "Establishment",
                "item_type_ar": "SYN-IND",
                "value": 2,
            },
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert energy.rows[0]["size_class"] == S1_LARGE
    assert energy.rows[0]["indicator"] == "employees"
    assert transport.rows[0]["size_class"] == S3_LARGE
    assert transport.rows[0]["period"] == "2014"
    assert transport.rows[0]["indicator"] == "employees"
    assert transport.rows[1]["indicator"] == "establishments"
    assert transport.period_first == "2014"
    assert transport.period_last == "2019"
    assert energy.rows[0]["size_class"] != transport.rows[0]["size_class"]


def test_energy_levels_are_kept_and_not_summed() -> None:
    """A section, a division and a class stay three rows. Their values are not added."""
    rows = [
        _energy("B", 10),
        _energy("06", 6),
        _energy("0610", 4),
    ]
    parsed = parse_establishment_size(
        _entry("est_size_act", ENERGY), rows, RECEIPT, _map(), {}
    )
    found = {(row["activity_key"], row["value"]) for row in parsed.rows}
    assert found == {
        ("B", Decimal("10.00")),
        ("06", Decimal("6.00")),
        ("0610", Decimal("4.00")),
    }
    assert Decimal("20.00") not in {row["value"] for row in parsed.rows}


def test_a_three_digit_activity_code_on_the_mixed_bulletin_stops() -> None:
    """Mixed levels are the three stated forms. A three-digit code is neither."""
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", ENERGY),
            [_energy("061", 1)],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "activity_code_form"


def test_wholesale_uses_its_own_size_field_and_four_digit_codes() -> None:
    """The wholesale file's size field is establishment_size, and the code is four digits."""
    parsed = parse_establishment_size(
        _entry("est_size_act", WHOLESALE),
        [
            {
                "year": "2016",
                "activity_code": "4711",
                "main_economic_activity": "SYN Activity",
                "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                "establishment_size": S2_LARGE,
                "hjm_lmnsh": S2_LARGE_AR,
                "indicator": "Employees",
                "lbyn": "SYN-IND",
                "value": 9,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.rows[0]["activity_key"] == "4711"
    assert parsed.rows[0]["table_code"] == WHOLESALE
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", WHOLESALE),
            [
                {
                    "year": "2016",
                    "activity_code": "47",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "establishment_size": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 9,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "activity_code_form"


def test_section_letters_of_the_one_bulletin_are_closed() -> None:
    """The bulletin of section letters accepts J to N and refuses another letter."""
    parsed = parse_establishment_size(
        _entry("est_size_act", ONE),
        [
            {
                "year": "2017",
                "activity_code": "J",
                "main_economic_activity": "SYN Activity",
                "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                "size_of_establishment": S2_LARGE,
                "hjm_lmnsh": S2_LARGE_AR,
                "indicator": "Establishments",
                "lbyn": "SYN-IND",
                "value": 3,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.rows[0]["activity_key"] == "J"
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", ONE),
            [
                {
                    "year": "2017",
                    "activity_code": "A",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Establishments",
                    "lbyn": "SYN-IND",
                    "value": 3,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "activity_code_unlisted"


def test_social_keeps_code_45_and_refuses_unlisted_activity() -> None:
    """The confirmed bulletin retains its own closed activity codes."""
    parsed = parse_establishment_size(
        _entry("est_size_act", SOCIAL), [_social("45")], RECEIPT, _map(), {}
    )
    assert parsed.rows[0]["activity_key"] == "45"
    with pytest.raises(AdditionError) as unlisted:
        parse_establishment_size(
            _entry("est_size_act", SOCIAL), [_social("99")], RECEIPT, _map(), {}
        )
    assert unlisted.value.name == "activity_code_unlisted"


def test_unconfirmed_indicator_labels_still_refuse_an_invented_bulletin() -> None:
    """Confirming one source does not bypass the pending-label guard."""
    loaded = _map()
    slugs = loaded["slugs"]
    assert isinstance(slugs, dict)
    slug = "SYN-unconfirmed-size-bulletin"
    slugs[slug] = {**slugs[SOCIAL], "indicators": "to_be_confirmed"}
    entry = replace(
        _entry("est_size_act", SOCIAL), slug=slug, key=f"est_size_act/{slug}"
    )
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(entry, [_social("45")], RECEIPT, loaded, {})
    assert caught.value.name == "indicator_labels_unconfirmed"


@pytest.mark.parametrize(
    ("label", "arabic", "indicator"),
    [
        ("Employees", "مشتغلون", "employees"),
        ("Establishments", "منشآت", "establishments"),
    ],
)
@pytest.mark.parametrize(
    ("size", "size_ar"),
    [
        (S2_LARGE, S2_LARGE_AR),
        ("Establishments with Less than 10 Employees", "المنشآت أقل من 10 مشتغلين"),
    ],
)
def test_social_confirmed_labels_parse_with_lineage(
    label: str, arabic: str, indicator: str, size: str, size_ar: str
) -> None:
    """Invented integer cells use the exact keys and closed labels supplied in IN."""
    row = _social("45")
    row.update(indicator=label, lbyn=arabic, establishment_size=size, hjm_lmnsh=size_ar)
    entry = _entry("est_size_act", SOCIAL)
    parsed = parse_establishment_size(entry, [row], RECEIPT, _map(), {})
    assert parsed.rows == (
        {
            "table_code": SOCIAL,
            "activity_key": "45",
            "size_class": size,
            "period": "2018",
            "indicator": indicator,
            "value": Decimal("1.00"),
            "unit": "to_be_confirmed",
            **_lineage(entry.key, entry.publisher, EST_METHOD),
        },
    )
    assert parsed.coverage == ()


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("indicator", "SYN-unknown", "unknown_indicator"),
        ("lbyn", "", "arabic_twin_missing"),
        ("hjm_lmnsh", "المنشآت أقل من 10 مشتغلين", "arabic_twin_mismatch"),
    ],
)
def test_social_one_changed_label_refuses(field: str, value: str, reason: str) -> None:
    """Each negative changes one field of an otherwise valid source-shaped row."""
    row = _social("45")
    row[field] = value
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", SOCIAL), [row], RECEIPT, _map(), {}
        )
    assert caught.value.name == reason


@given(suffix=st.text(max_size=100))
def test_social_unlisted_indicator_words_never_become_facts(suffix: str) -> None:
    """An invented prefix keeps generated words outside both confirmed labels."""
    row = _social("45")
    row["indicator"] = "SYN-" + suffix
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", SOCIAL), [row], RECEIPT, _map(), {}
        )
    assert caught.value.name == "unknown_indicator"


def test_business_services_has_no_size_class_and_all_is_not_filled() -> None:
    """A missing size class leaves the row out. Group is not stored as a size class."""
    parsed = parse_establishment_size(
        _entry("est_size_act", BUSINESS),
        [
            {
                "year": "2018",
                "activity_code": "62",
                "economic_activity": "SYN Activity",
                "lnsht_lqtsdy": "SYN-AR",
                "indicator": "Compensation of Employees",
                "lbyn": "SYN-IND",
                "group": "SYN Section",
                "lmjmw": "SYN-AR",
                "value": 80,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "missing_size_class") == 1
    assert parsed.questions[0].inventory == (
        "the business-services slug has no size class; it has a field group"
    )
    assert (
        parsed.questions[0].change
        == "keep those rows out; do not fill size_class with ALL"
    )
    assert parsed.period_first == "2018"
    assert parsed.period_last == "2018"


def test_a_null_measure_is_not_zero_and_other_text_stops() -> None:
    """Null drops that key. A dash is not on the missing list and stops the build."""
    base = {
        "year": "2018",
        "activity_code": "11",
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "size_of_establishment": S2_LARGE,
        "hjm_lmnsh": S2_LARGE_AR,
        "indicator": "Employees",
        "lbyn": "SYN-IND",
    }
    missing = parse_establishment_size(
        _entry("est_size_act", TWO),
        [base | {"value": None}],
        RECEIPT,
        _map(),
        {},
    )
    assert missing.rows == ()
    assert _coverage(missing, "measure_missing") == 1
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [base | {"value": "-"}],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "measure_unparsed"


def test_an_unknown_size_or_a_mismatched_arabic_twin_stops() -> None:
    """Size classes are a closed list, and the Arabic twin is the paired label."""
    entry = _entry("est_size_act", TWO)
    with pytest.raises(AdditionError) as unknown:
        parse_establishment_size(
            entry,
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": "SYN Size",
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 1,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert unknown.value.name == "unknown_size_class"
    with pytest.raises(AdditionError) as mismatched:
        parse_establishment_size(
            entry,
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": "SYN-AR",
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 1,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert mismatched.value.name == "arabic_twin_mismatch"


def test_unknown_fields_and_a_year_held_as_a_number_stop() -> None:
    """A field the map does not name is refused, and a numeric year is not year text."""
    entry = _entry("est_size_act", TWO)
    row = {
        "year": "2018",
        "activity_code": "11",
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "size_of_establishment": S2_LARGE,
        "hjm_lmnsh": S2_LARGE_AR,
        "indicator": "Employees",
        "lbyn": "SYN-IND",
        "value": 1,
        "extra_name": "SYN",
    }
    with pytest.raises(AdditionError) as extra:
        parse_establishment_size(entry, [row], RECEIPT, _map(), {})
    assert extra.value.name == "unknown_source_field"
    row.pop("extra_name")
    row["year"] = 2018
    with pytest.raises(AdditionError) as period:
        parse_establishment_size(entry, [row], RECEIPT, _map(), {})
    assert period.value.name == "period_form"


def test_duplicate_size_keys_and_an_empty_file_stop() -> None:
    """Two rows with one contract key stop the build. An empty file has no period."""
    row = {
        "year": "2018",
        "activity_code": "11",
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "size_of_establishment": S2_LARGE,
        "hjm_lmnsh": S2_LARGE_AR,
        "indicator": "Employees",
        "lbyn": "SYN-IND",
        "value": 1,
    }
    with pytest.raises(AdditionError) as duplicate:
        parse_establishment_size(
            _entry("est_size_act", TWO), [row, dict(row)], RECEIPT, _map(), {}
        )
    assert duplicate.value.name == "duplicate_key"
    with pytest.raises(AdditionError) as empty:
        parse_establishment_size(_entry("est_size_act", TWO), [], RECEIPT, _map(), {})
    assert empty.value.name == "period_absent"


def test_manufacturing_licence_rows_keep_cumulative_investment() -> None:
    """Three measures stay three rows. Investment is the published million figure."""
    parsed = parse_manufacturing(
        _entry("mfg_industry", METALS),
        [
            _metals("2019", 4, "10.5", 7),
            _metals("2020", 4, "16", 7),
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.table == "pub_manufacturing"
    assert parsed.period_first == "2019"
    assert parsed.period_last == "2020"
    key = f"mfg_industry/{METALS}"
    assert parsed.rows == (
        _mfg_row(METALS, "2019", "firms", Decimal("4.000000"), "to_be_confirmed", key),
        _mfg_row(
            METALS, "2019", "investment", Decimal("10.500000"), "qar_million", key
        ),
        _mfg_row(METALS, "2019", "labour", Decimal("7.000000"), "to_be_confirmed", key),
        _mfg_row(METALS, "2020", "firms", Decimal("4.000000"), "to_be_confirmed", key),
        _mfg_row(
            METALS, "2020", "investment", Decimal("16.000000"), "qar_million", key
        ),
        _mfg_row(METALS, "2020", "labour", Decimal("7.000000"), "to_be_confirmed", key),
    )
    assert parsed.rows[1]["value"].as_tuple().exponent == -6
    assert Decimal("5.500000") not in {row["value"] for row in parsed.rows}
    assert "plants" not in {row["indicator"] for row in parsed.rows}


def test_a_null_labour_cell_is_omitted_and_a_fraction_on_an_integer_stops() -> None:
    """Null labour is not stored as zero. A fractional labour count stops on an integer field."""
    parsed = parse_manufacturing(
        _entry("mfg_industry", METALS),
        [_metals("2019", 4, "0", None)],
        RECEIPT,
        _map(),
        {},
    )
    indicators = {row["indicator"] for row in parsed.rows}
    assert indicators == {"firms", "investment"}
    assert _coverage(parsed, "measure_missing") == 1
    assert Decimal("0.000000") == next(
        row["value"] for row in parsed.rows if row["indicator"] == "investment"
    )
    with pytest.raises(AdditionError) as caught:
        parse_manufacturing(
            _entry("mfg_industry", METALS),
            [_metals("2019", 4, "1", 2.5)],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "measure_not_integral"


def test_textiles_labour_may_be_fractional_and_uses_the_a2_investment_field() -> None:
    """Textiles labour is a float. The investment field name is the A2 name."""
    parsed = parse_manufacturing(
        _entry("mfg_industry", TEXTILES),
        [
            {
                "year": "2021",
                "license_type": "Industrial License",
                "nw_ltrkhys": "SYN-AR",
                "number_of_firms": 2,
                "investment_in_million_qatari_riyals": "3.25",
                "number_of_labour": "2.5",
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    labour = next(row for row in parsed.rows if row["indicator"] == "labour")
    assert labour["value"] == Decimal("2.500000")
    assert labour["breakdown_key"] == "licence_type=Industrial License"


def test_schema_b_has_no_arabic_licence_field_and_computer_has_one_licence() -> None:
    """Schema B does not invent an Arabic field. Computer does not invent a second licence."""
    parsed = parse_manufacturing(
        _entry("mfg_industry", PHARMA),
        [
            {
                "year": "2022",
                "license_type": "Industrial Registration",
                "no_of_firms": 1,
                "investment_qar_mil": "8",
                "no_of_labour": 3,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert len(parsed.rows) == 3
    with pytest.raises(AdditionError) as extra:
        parse_manufacturing(
            _entry("mfg_industry", PHARMA),
            [
                {
                    "year": "2022",
                    "license_type": "Industrial Registration",
                    "nw_ltrkhys": "SYN-AR",
                    "no_of_firms": 1,
                    "investment_qar_mil": "8",
                    "no_of_labour": 3,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert extra.value.name == "unknown_source_field"
    with pytest.raises(AdditionError) as licence:
        parse_manufacturing(
            _entry("mfg_industry", COMPUTER),
            [
                {
                    "year": "2022",
                    "license_type": "Industrial Registration",
                    "nw_ltrkhys": "SYN-AR",
                    "number_of_firms": 1,
                    "investment_in_million_qatari_riyals": "1",
                    "number_of_labour": 1,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert licence.value.name == "unknown_licence_type"


def test_extra_investment_precision_stops() -> None:
    """A figure finer than decimal(18,6) is not rounded into the table."""
    with pytest.raises(AdditionError) as caught:
        parse_manufacturing(
            _entry("mfg_industry", METALS),
            [_metals("2019", 1, "1.2345678", 1)],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "measure_precision"


def test_quantize_is_unchanged_when_the_caller_context_changes() -> None:
    """14.00, 10.500000 and the precision refusal do not follow the caller context."""
    with localcontext(Context(prec=1, rounding=ROUND_DOWN)):
        parsed = parse_establishment_size(
            _entry("est_size_act", TWO),
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 14,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
        assert parsed.rows[0]["value"] == Decimal("14.00")
        manufactured = parse_manufacturing(
            _entry("mfg_industry", METALS),
            [_metals("2019", 1, "10.5", 1)],
            RECEIPT,
            _map(),
            {},
        )
        investment = next(
            row for row in manufactured.rows if row["indicator"] == "investment"
        )
        assert investment["value"] == Decimal("10.500000")
        with pytest.raises(AdditionError) as caught:
            parse_manufacturing(
                _entry("mfg_industry", METALS),
                [_metals("2019", 1, "1.2345678", 1)],
                RECEIPT,
                _map(),
                {},
            )
        assert caught.value.name == "measure_precision"


def test_the_doubled_manufacture_prefix_is_the_table_code() -> None:
    """The wood slug keeps the repeated manufacture-of prefix."""
    parsed = parse_manufacturing(
        _entry("mfg_industry", WOOD),
        [
            {
                "year": "2020",
                "license_type": "Industrial License",
                "no_of_firms": 2,
                "investment_qar_mil": "1",
                "no_of_labour": 2,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.rows[0]["table_code"] == WOOD


def test_product_units_stay_as_published() -> None:
    """The two production unit labels are not harmonised."""
    parsed = parse_manufacturing(
        _entry("mfg_industry", PRODUCTS),
        [
            _product("Urea", "Thousand Tons (TN '000)", 9),
            _product("Ammonia", "Thousand Metric Tons (MT '000)", 4),
        ],
        RECEIPT,
        _map(),
        {},
    )
    units = {row["breakdown_key"]: row["unit"] for row in parsed.rows}
    assert units == {
        "category=Fertilizers|product=Ammonia": "Thousand Metric Tons (MT '000)",
        "category=Fertilizers|product=Urea": "Thousand Tons (TN '000)",
    }
    assert parsed.rows[0]["publisher"] == "National Planning Council"
    assert all(row["indicator"] == "production" for row in parsed.rows)


def test_a_separator_inside_a_breakdown_value_stops() -> None:
    """A value that contains the pair separator is not written into the key."""
    spec = _map()
    slugs = spec["slugs"]
    assert isinstance(slugs, dict)
    metals = dict(slugs[METALS])
    metals["licence_types"] = ["Industrial|License"]
    slugs[METALS] = metals
    with pytest.raises(AdditionError) as caught:
        parse_manufacturing(
            _entry("mfg_industry", METALS),
            [_metals("2019", 1, "1", 1, licence="Industrial|License")],
            RECEIPT,
            spec,
            {},
        )
    assert caught.value.name == "breakdown_unencodable"


def test_trade_breakdowns_are_not_folded_into_the_indicator() -> None:
    """Two parts of one measure are not summed and are not stored as one indicator."""
    parsed = parse_trade(
        _entry("trade_wr", TRADE),
        [
            _trade("Purchases", "Imported", 3),
            _trade("Purchases", "Local", 5),
        ],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.table == "pub_trade_wr"
    assert parsed.rows == ()
    assert _coverage(parsed, "breakdown_not_in_key") == 2
    assert parsed.questions[0].contract == (
        "pub_trade_wr is keyed by trade_type, period and indicator, "
        "and indicator is purchases, sales or stocks"
    )
    assert parsed.questions[0].change == (
        "add breakdown to the primary key and keep indicator as the measure"
    )
    assert parsed.period_first == "2018"
    assert parsed.period_last == "2018"


def test_an_unknown_trade_breakdown_stops_and_a_null_is_not_a_blocked_row() -> None:
    """An unlisted breakdown stops. A null measure is missing, not a zero and not a sum."""
    with pytest.raises(AdditionError) as caught:
        parse_trade(
            _entry("trade_wr", TRADE),
            [_trade("Sales", "SYN Part", 1)],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "unknown_breakdown"
    parsed = parse_trade(
        _entry("trade_wr", TRADE),
        [_trade("Stock for Sale", "End of Year", None)],
        RECEIPT,
        _map(),
        {},
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "measure_missing") == 1
    assert _coverage(parsed, "breakdown_not_in_key") == 0


def test_country_crosswalk_is_an_exact_label_match() -> None:
    """A published label matches one reviewed row. A prefix, a case change and a near label do not."""
    parsed = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [_certificate("SYN Land", "Certificates of Origin", 6)],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    row = parsed.rows[0]
    assert row["breakdown_key"] == (
        "certificate_type=Certificates of Origin|importing_country=SLL"
    )
    assert row["indicator"] == "certificates"
    assert row["value"] == Decimal("6.00")
    assert row["unit"] == "to_be_confirmed"
    assert row["publisher"] == "Qatar Chamber of Commerce & Industry"
    assert row["method"] == LOG_METHOD
    assert "\u00a0" not in str(row["breakdown_key"])
    for label in ("SYN", "syn land", "SYN Lands", "SYN Land "):
        with pytest.raises(AdditionError) as caught:
            parse_logistics(
                _entry("trade_logistics", CERTIFICATES),
                [_certificate(label, "Certificates of Origin", 6)],
                RECEIPT,
                _with_countries(WALK),
                {},
            )
        assert caught.value.name == "country_unreviewed"


def test_the_committed_crosswalk_stops_on_a_label_it_has_no_row_for() -> None:
    """With the committed crosswalk, a label without a reviewed row stops by name."""
    with pytest.raises(AdditionError) as caught:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 6)],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "country_unreviewed"


def test_the_committed_crosswalk_loads_with_one_iso_code_per_label() -> None:
    """Every committed row loads, no label repeats, and every code is in the ISO list."""
    review = _map()
    rows = review["country_crosswalk"]
    assert isinstance(rows, list)
    labels = [row["published_label"] for row in rows]
    assert len(labels) == len(set(labels))
    walk = _crosswalk(review)
    assert len(walk) == len(rows)
    with (REVIEW / "country_iso3.csv").open(encoding="utf-8", newline="") as stream:
        iso = {row["iso3"] for row in csv.DictReader(stream)}
    assert set(walk.values()) <= iso
    regions = review["regions_not_countries"]
    assert isinstance(regions, list)
    assert not set(walk) & set(regions)


def test_an_unpublished_certificate_type_is_omitted() -> None:
    """The token #N/A is not a certificate type. Another unknown type stops the build."""
    parsed = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [_certificate("SYN Land", "#N/A", 2)],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "certificate_type_unpublished") == 1
    with pytest.raises(AdditionError) as caught:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "SYN Mystery", 2)],
            RECEIPT,
            _with_countries(WALK),
            {},
        )
    assert caught.value.name == "unknown_certificate_type"


def test_arabic_country_spelling_is_not_a_second_key() -> None:
    """Two Arabic spellings of one English label are one country, so the key repeats."""
    with pytest.raises(AdditionError) as caught:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [
                _certificate("SYN Land", "Certificates of Origin", 6, arabic="SYN-A"),
                _certificate(
                    "SYN Land",
                    "Certificates of Origin",
                    6,
                    arabic="SYN-B\u00a0",
                ),
            ],
            RECEIPT,
            _with_countries(WALK),
            {},
        )
    assert caught.value.name == "duplicate_key"


def test_previous_port_regions_are_not_written_as_iso_countries() -> None:
    """A region is left out. A label that is only a prefix of a region is not treated as that region."""
    parsed = parse_logistics(
        _entry("trade_logistics", PREVIOUS),
        [
            _previous("African Countries", "Oil Tanker", "Gross Tonnage", 12),
            _previous("SYN Land", "Bulk", "Net Tonnage", 1.25),
        ],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    assert len(parsed.rows) == 1
    assert parsed.rows[0]["breakdown_key"] == (
        "country_of_previous_port=SLL|vessel_type=Bulk"
    )
    assert parsed.rows[0]["indicator"] == "net_tonnage"
    assert parsed.rows[0]["value"] == Decimal("1.25")
    assert _coverage(parsed, "region_not_country") == 1
    assert parsed.questions[0].inventory == (
        "country of previous port is ten regions, not countries, and a region has no ISO code"
    )
    with pytest.raises(AdditionError) as caught:
        parse_logistics(
            _entry("trade_logistics", PREVIOUS),
            [_previous("African", "Bulk", "Number of Vessels", 1)],
            RECEIPT,
            _with_countries(WALK),
            {},
        )
    assert caught.value.name == "country_unreviewed"


def _with_region(label: str) -> dict[str, object]:
    review = _with_countries(WALK)
    regions = review["regions_not_countries"]
    assert isinstance(regions, list)
    review["regions_not_countries"] = [*regions, label]
    return review


def test_a_listed_region_is_left_out_of_certificates_and_counted() -> None:
    """A listed region is not an importing country. It is counted, not written."""
    parsed = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [
            _certificate("SYN Region", "Certificates of Origin", 3),
            _certificate("SYN Land", "Certificates of Origin", 6),
        ],
        RECEIPT,
        _with_region("SYN Region"),
        {},
    )
    assert [row["breakdown_key"] for row in parsed.rows] == [
        "certificate_type=Certificates of Origin|importing_country=SLL"
    ]
    assert _coverage(parsed, "region_not_country") == 1
    assert parsed.questions == ()


def test_a_listed_region_is_left_out_of_registration_and_counted() -> None:
    """A listed region is not a country of registration. Its row is counted once."""
    region = _hamad(oil_tankers=4)
    region["country_of_registration"] = "SYN Region"
    parsed = parse_logistics(
        _entry("trade_logistics", HAMAD),
        [region, _hamad(oil_tankers=4)],
        RECEIPT,
        _with_region("SYN Region"),
        {},
    )
    assert len(parsed.rows) == 9
    assert all("=SLL|" in str(row["breakdown_key"]) for row in parsed.rows)
    assert _coverage(parsed, "region_not_country") == 1
    assert parsed.questions == ()


def test_an_unlisted_non_country_label_still_stops_each_parser() -> None:
    """Only a listed region is skipped. A near or unlisted label stops by name."""
    review = _with_region("SYN Region")
    for label in ("SYN Elsewhere", "SYN Region ", "syn region", "SYN"):
        with pytest.raises(AdditionError) as certificate:
            parse_logistics(
                _entry("trade_logistics", CERTIFICATES),
                [_certificate(label, "Certificates of Origin", 3)],
                RECEIPT,
                review,
                {},
            )
        assert certificate.value.name == "country_unreviewed"
        row = _hamad()
        row["country_of_registration"] = label
        with pytest.raises(AdditionError) as registration:
            parse_logistics(
                _entry("trade_logistics", HAMAD), [row], RECEIPT, review, {}
            )
        assert registration.value.name == "country_unreviewed"


def test_a_malformed_region_list_stops_certificates_and_registration() -> None:
    """A region list that is not a list of text stops both parsers by name."""
    for bad in (5, None, ["SYN Region", 7]):
        review = _with_countries(WALK)
        review["regions_not_countries"] = bad
        with pytest.raises(AdditionError) as certificate:
            parse_logistics(
                _entry("trade_logistics", CERTIFICATES),
                [_certificate("SYN Land", "Certificates of Origin", 3)],
                RECEIPT,
                review,
                {},
            )
        assert certificate.value.name == "field_map_unreadable"
        with pytest.raises(AdditionError) as registration:
            parse_logistics(
                _entry("trade_logistics", HAMAD), [_hamad()], RECEIPT, review, {}
            )
        assert registration.value.name == "field_map_unreadable"


def test_the_committed_registration_group_label_is_a_listed_region() -> None:
    """The published group label of the registration file is skipped, not mapped."""
    review = _map()
    regions = review["regions_not_countries"]
    assert isinstance(regions, list)
    assert "OTHER EUROPEAN COUNTRIES" in regions
    row = _hamad(oil_tankers=4)
    row["country_of_registration"] = "OTHER EUROPEAN COUNTRIES"
    parsed = parse_logistics(
        _entry("trade_logistics", HAMAD), [row], RECEIPT, review, {}
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "region_not_country") == 1


_LABEL_MAP = _map()
_LABEL_ENTRIES = {
    slug: _entry("trade_logistics", slug) for slug in (CERTIFICATES, HAMAD)
}


@given(
    label=st.text(min_size=1, max_size=12),
    listed=st.booleans(),
    mapped=st.booleans(),
    layout=st.sampled_from((CERTIFICATES, HAMAD)),
)
@example(label="Kosovo", listed=False, mapped=False, layout=CERTIFICATES)
@example(label="Kosovo", listed=False, mapped=True, layout=CERTIFICATES)
def test_a_label_is_skipped_only_when_listed_and_mapped_only_by_exact_row(
    label: str, listed: bool, mapped: bool, layout: str
) -> None:
    """Over any label: listed is skipped, else an exact row maps it, else it stops."""
    review = dict(_LABEL_MAP)
    review["country_labels_withheld"] = []
    review["regions_not_countries"] = [label] if listed else []
    review["country_crosswalk"] = (
        [{"published_label": label, "iso3": "SLL"}] if mapped else []
    )
    if layout == CERTIFICATES:
        row = _certificate(label, "Certificates of Origin", 3)
    else:
        row = _hamad(oil_tankers=4)
        row["country_of_registration"] = label
    entry = _LABEL_ENTRIES[layout]
    if not listed and not mapped:
        with pytest.raises(AdditionError) as caught:
            parse_logistics(entry, [row], RECEIPT, review, {})
        assert caught.value.name == "country_unreviewed"
        return
    parsed = parse_logistics(entry, [row], RECEIPT, review, {})
    if listed:
        assert parsed.rows == ()
        assert _coverage(parsed, "region_not_country") == 1
    else:
        assert parsed.rows
        assert all("SLL" in str(item["breakdown_key"]) for item in parsed.rows)
        assert _coverage(parsed, "region_not_country") == 0


def test_an_unknown_vessel_indicator_stops() -> None:
    """An indicator outside the bulletin's closed list stops the build."""
    with pytest.raises(AdditionError) as caught:
        parse_logistics(
            _entry("trade_logistics", PREVIOUS),
            [_previous("SYN Land", "Bulk", "Headcount", 1)],
            RECEIPT,
            _with_countries(WALK),
            {},
        )
    assert caught.value.name == "unknown_indicator"


def test_a_null_tonnage_is_not_zero() -> None:
    """The one null vessel measure is omitted. It is not written as zero."""
    parsed = parse_logistics(
        _entry("trade_logistics", PREVIOUS),
        [_previous("SYN Land", "Containers", "Number of Vessels", None)],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "measure_missing") == 1


def test_hamad_columns_keep_a_zero_and_drop_a_null() -> None:
    """Vessel type is the column name. A zero stays. A null does not become zero."""
    parsed = parse_logistics(
        _entry("trade_logistics", HAMAD),
        [_hamad(passengers_vessels=0, oil_tankers=4, gas_tankers=None)],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    found = {row["breakdown_key"]: row["value"] for row in parsed.rows}
    assert found["country_of_registration=SLL|vessel_type=oil_tankers"] == Decimal(
        "4.00"
    )
    assert found[
        "country_of_registration=SLL|vessel_type=passengers_vessels"
    ] == Decimal("0.00")
    assert found["country_of_registration=SLL|vessel_type=others"] == Decimal("0.00")
    assert len(found) == 8
    assert _coverage(parsed, "measure_missing") == 1
    assert all("gas_tankers" not in key for key in found)
    assert all("Oil Tanker" not in row["breakdown_key"] for row in parsed.rows)
    assert {row["indicator"] for row in parsed.rows} == {"vessels"}


def test_a_bad_crosswalk_row_stops_at_load() -> None:
    """An ISO code that is not three letters, or a repeated label, is not a crosswalk."""
    short = _with_countries(({"published_label": "SYN Land", "iso3": "SL"},))
    with pytest.raises(AdditionError) as iso:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 1)],
            RECEIPT,
            short,
            {},
        )
    assert iso.value.name == "country_crosswalk"
    repeated = _with_countries(
        (
            {"published_label": "SYN Land", "iso3": "SLL"},
            {"published_label": "SYN Land", "iso3": "SPT"},
        )
    )
    with pytest.raises(AdditionError) as duplicate:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 1)],
            RECEIPT,
            repeated,
            {},
        )
    assert duplicate.value.name == "country_crosswalk"


def test_lineage_fields_are_refused_one_at_a_time() -> None:
    """Removing source, period, retrieval, method, licence or hash refuses the figure."""
    parsed = parse_establishment_size(
        _entry("est_size_act", TWO),
        [
            {
                "year": "2018",
                "activity_code": "11",
                "main_economic_activity": "SYN Activity",
                "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                "size_of_establishment": S2_LARGE,
                "hjm_lmnsh": S2_LARGE_AR,
                "indicator": "Employees",
                "lbyn": "SYN-IND",
                "value": 5,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    for field in (
        "source_key",
        "period",
        "retrieved_utc",
        "method",
        "licence_id",
        "sha256",
    ):
        broken = dict(parsed.rows[0])
        broken[field] = ""
        with pytest.raises(AdditionError) as caught:
            require_lineage(broken)
        assert caught.value.name == "lineage_incomplete"
    with pytest.raises(AdditionError) as missing:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 5,
                }
            ],
            {"sha256": "ab" * 32},
            _map(),
            {},
        )
    assert missing.value.name == "lineage_incomplete"


def test_an_unmapped_slug_stops() -> None:
    """A slug with no review block is not given another bulletin's fields."""
    entry = replace(
        _entry("est_size_act", TWO),
        slug="invented-bulletin",
        key="est_size_act/invented-bulletin",
    )
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(entry, [], RECEIPT, _map(), {})
    assert caught.value.name == "slug_unmapped"


def test_a_missing_field_and_an_empty_arabic_twin_stop() -> None:
    """A required field that is absent, and an empty Arabic twin, each stop the build."""
    entry = _entry("est_size_act", TWO)
    row = {
        "year": "2018",
        "activity_code": "11",
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "size_of_establishment": S2_LARGE,
        "hjm_lmnsh": S2_LARGE_AR,
        "indicator": "Employees",
        "lbyn": "SYN-IND",
        "value": 1,
    }
    absent = dict(row)
    del absent["value"]
    with pytest.raises(AdditionError) as missing:
        parse_establishment_size(entry, [absent], RECEIPT, _map(), {})
    assert missing.value.name == "source_field_absent"
    row["lbyn"] = ""
    with pytest.raises(AdditionError) as empty:
        parse_establishment_size(entry, [row], RECEIPT, _map(), {})
    assert empty.value.name == "arabic_twin_missing"


def test_an_activity_code_held_as_a_number_stops() -> None:
    """The activity code is text. A number is not given a guessed width."""
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [
                {
                    "year": "2018",
                    "activity_code": 11,
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 1,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "activity_code_form"


def test_a_null_product_and_a_null_certificate_are_not_zero() -> None:
    """A null production and a null certificate count are omitted, not stored as zero."""
    products = parse_manufacturing(
        _entry("mfg_industry", PRODUCTS),
        [_product("Urea", "Thousand Tons (TN '000)", None)],
        RECEIPT,
        _map(),
        {},
    )
    assert products.rows == ()
    assert _coverage(products, "measure_missing") == 1
    certificates = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [_certificate("SYN Land", "Certificates of Origin", None)],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    assert certificates.rows == ()
    assert _coverage(certificates, "measure_missing") == 1


def test_a_parser_refuses_a_layout_and_a_family_it_does_not_own() -> None:
    """Each parser accepts only its own layout, and a slug stays in its family."""
    with pytest.raises(AdditionError) as layout:
        parse_establishment_size(
            _entry("mfg_industry", METALS), [], RECEIPT, _map(), {}
        )
    assert layout.value.name == "slug_unmapped"
    with pytest.raises(AdditionError) as trade:
        parse_trade(_entry("est_size_act", TWO), [], RECEIPT, _map(), {})
    assert trade.value.name == "slug_unmapped"
    spec = _map()
    slugs = spec["slugs"]
    assert isinstance(slugs, dict)
    block = dict(slugs[TWO])
    block["family"] = "mfg_industry"
    slugs[TWO] = block
    with pytest.raises(AdditionError) as family:
        parse_establishment_size(_entry("est_size_act", TWO), [], RECEIPT, spec, {})
    assert family.value.name == "slug_unmapped"


def test_the_review_file_is_read_when_the_passed_map_is_not_the_industry_map(
    tmp_path: Path,
) -> None:
    """Pass A's build passes its own field map. This parser then reads its review file."""
    review = tmp_path / "review"
    review.mkdir()
    (review / "additions_industry.yaml").write_text(
        (REVIEW / "additions_industry.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    parsed = parse_establishment_size(
        _entry("est_size_act", TWO),
        [
            {
                "year": "2018",
                "activity_code": "11",
                "main_economic_activity": "SYN Activity",
                "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                "size_of_establishment": S2_LARGE,
                "hjm_lmnsh": S2_LARGE_AR,
                "indicator": "Employees",
                "lbyn": "SYN-IND",
                "value": 14,
            }
        ],
        RECEIPT,
        {"unit_types": {}},
        {"review": review},
    )
    assert parsed.rows[0]["value"] == Decimal("14.00")
    bad = _map()
    bad["version"] = 2
    with pytest.raises(AdditionError) as version:
        parse_establishment_size(_entry("est_size_act", TWO), [], RECEIPT, bad, {})
    assert version.value.name == "field_map_unreadable"
    written = (review / "additions_industry.yaml").read_text(encoding="utf-8")
    (review / "additions_industry.yaml").write_text(
        written.replace("version: 1\n", "version: 2\n", 1), encoding="utf-8"
    )
    with pytest.raises(AdditionError) as loaded:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [],
            RECEIPT,
            {"unit_types": {}},
            {"review": review},
        )
    assert loaded.value.name == "field_map_unreadable"
    with pytest.raises(AdditionError) as not_path:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [],
            RECEIPT,
            {"unit_types": {}},
            {"review": "not-a-path"},
        )
    assert not_path.value.name == "field_map_unreadable"


def test_an_unconfirmed_period_field_stops_before_a_row_is_written() -> None:
    """A period field still marked to_be_confirmed stops. No year is guessed."""
    entry = replace(
        _entry("est_size_act", TWO),
        period_field="sit=row;form=year_text;field=to_be_confirmed",
    )
    with pytest.raises(AdditionError) as caught:
        parse_establishment_size(
            entry,
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 1,
                }
            ],
            RECEIPT,
            _map(),
            {},
        )
    assert caught.value.name == "period_field_unconfirmed"


def test_a_corrupt_review_cell_stops_by_name() -> None:
    """A review cell that is not the declared shape stops as an unreadable map or crosswalk."""
    row = _metals("2018", 1, "10.5", 2)
    entry = _entry("mfg_industry", METALS)

    def manufacturing(spec: dict[str, object], name: str) -> None:
        with pytest.raises(AdditionError) as caught:
            parse_manufacturing(entry, [row], RECEIPT, spec, {})
        assert caught.value.name == name

    schema = _map()
    schemas = schema["schemas"]
    assert isinstance(schemas, dict)
    schemas["a1"] = "broken"
    manufacturing(schema, "field_map_unreadable")

    measures = _map()
    slugs = measures["slugs"]
    assert isinstance(slugs, dict)
    block = dict(slugs[METALS])
    block["measures"] = ["labour"]
    slugs[METALS] = block
    manufacturing(measures, "field_map_unreadable")

    blank_name = _map()
    named = blank_name["slugs"]
    assert isinstance(named, dict)
    licence = dict(named[METALS])
    licence["licence_field"] = ""
    named[METALS] = licence
    manufacturing(blank_name, "field_map_unreadable")

    blank_field = _map()
    fields = blank_field["slugs"]
    assert isinstance(fields, dict)
    measure = dict(fields[METALS])
    measure["measures"] = [
        {"indicator": "firms", "field": "", "unit": "to_be_confirmed", "integral": True}
    ]
    fields[METALS] = measure
    manufacturing(blank_field, "field_map_unreadable")

    blank_unit = _map()
    units = blank_unit["slugs"]
    assert isinstance(units, dict)
    unit = dict(units[METALS])
    unit["measures"] = [
        {
            "indicator": "firms",
            "field": "number_of_firms",
            "unit": "",
            "integral": True,
        }
    ]
    units[METALS] = unit
    manufacturing(blank_unit, "field_map_unreadable")

    not_list = _map()
    listed = not_list["slugs"]
    assert isinstance(listed, dict)
    fields_cell = dict(listed[METALS])
    fields_cell["fields"] = "year"
    listed[METALS] = fields_cell
    manufacturing(not_list, "field_map_unreadable")

    not_dict = _map()
    not_dict["slugs"] = ["not-a-slug-map"]
    with pytest.raises(AdditionError) as slugs_cell:
        parse_establishment_size(_entry("est_size_act", TWO), [], RECEIPT, not_dict, {})
    assert slugs_cell.value.name == "field_map_unreadable"

    indicators = _map()
    indicator_slugs = indicators["slugs"]
    assert isinstance(indicator_slugs, dict)
    two = dict(indicator_slugs[TWO])
    two["indicators"] = ["Employees"]
    indicator_slugs[TWO] = two
    with pytest.raises(AdditionError) as indicator_cell:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 1,
                }
            ],
            RECEIPT,
            indicators,
            {},
        )
    assert indicator_cell.value.name == "field_map_unreadable"

    walk = _map()
    walk["country_crosswalk"] = [{"published_label": "SYN Land", "iso3": 123}]
    with pytest.raises(AdditionError) as iso:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 1)],
            RECEIPT,
            walk,
            {},
        )
    assert iso.value.name == "country_crosswalk"


def test_an_empty_licence_twin_and_a_blank_unit_stop() -> None:
    """An empty Arabic licence twin, a blank unit, and a measure list that is not a list stop."""
    row = _metals("2018", 1, "10.5", 2)
    row["nw_ltrkhys"] = ""
    with pytest.raises(AdditionError) as twin:
        parse_manufacturing(_entry("mfg_industry", METALS), [row], RECEIPT, _map(), {})
    assert twin.value.name == "arabic_twin_missing"

    blank = _map()
    slugs = blank["slugs"]
    assert isinstance(slugs, dict)
    two = dict(slugs[TWO])
    two["unit"] = ""
    slugs[TWO] = two
    with pytest.raises(AdditionError) as unit:
        parse_establishment_size(
            _entry("est_size_act", TWO),
            [
                {
                    "year": "2018",
                    "activity_code": "11",
                    "main_economic_activity": "SYN Activity",
                    "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                    "size_of_establishment": S2_LARGE,
                    "hjm_lmnsh": S2_LARGE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 1,
                }
            ],
            RECEIPT,
            blank,
            {},
        )
    assert unit.value.name == "field_map_unreadable"

    measures = _map()
    measure_slugs = measures["slugs"]
    assert isinstance(measure_slugs, dict)
    metals = dict(measure_slugs[METALS])
    metals["measures"] = 5
    measure_slugs[METALS] = metals
    with pytest.raises(AdditionError) as measure_list:
        parse_manufacturing(
            _entry("mfg_industry", METALS),
            [_metals("2018", 1, "10.5", 2)],
            RECEIPT,
            measures,
            {},
        )
    assert measure_list.value.name == "field_map_unreadable"

    walk = _map()
    walk["country_crosswalk"] = 5
    with pytest.raises(AdditionError) as crosswalk:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 1)],
            RECEIPT,
            walk,
            {},
        )
    assert crosswalk.value.name == "country_crosswalk"


def test_a_crosswalk_row_that_is_not_a_mapping_stops() -> None:
    """A crosswalk cell that is not a label and an ISO code stops at load."""
    spec = _map()
    spec["country_crosswalk"] = ["SYN Land"]
    with pytest.raises(AdditionError) as caught:
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 1)],
            RECEIPT,
            spec,
            {},
        )
    assert caught.value.name == "country_crosswalk"


def test_a_size_row_round_trips_through_parquet(tmp_path: Path) -> None:
    """One establishment figure writes and reads back at decimal(18,2)."""
    parsed = parse_establishment_size(
        _entry("est_size_act", TWO),
        [
            {
                "year": "2018",
                "activity_code": "11",
                "main_economic_activity": "SYN Activity",
                "lnsht_lqtsdy_lry_ysy": "SYN-AR",
                "size_of_establishment": S2_LARGE,
                "hjm_lmnsh": S2_LARGE_AR,
                "indicator": "Employees",
                "lbyn": "SYN-IND",
                "value": 14,
            }
        ],
        RECEIPT,
        _map(),
        {},
    )
    row = parsed.rows[0]
    columns = (
        ("table_code", "VARCHAR"),
        ("activity_key", "VARCHAR"),
        ("size_class", "VARCHAR"),
        ("period", "VARCHAR"),
        ("indicator", "VARCHAR"),
        ("value", "DECIMAL(18,2)"),
        ("unit", "VARCHAR"),
    )
    path = tmp_path / "pub_establishment_size.parquet"
    write_parquet(
        path,
        columns,
        (
            tuple(
                row[name]
                for name in (
                    "table_code",
                    "activity_key",
                    "size_class",
                    "period",
                    "indicator",
                    "value",
                    "unit",
                )
            ),
        ),
    )
    found = duckdb.sql(
        f"select value, indicator, unit from read_parquet('{path.as_posix()}')"
    ).fetchall()
    assert len(found) == 1
    assert Decimal(str(found[0][0])) == Decimal("14.00")
    assert found[0][1] == "employees"
    assert found[0][2] == "to_be_confirmed"


def _energy(code: str, value: int) -> dict[str, object]:
    return {
        "year": "2018",
        "activity_code": code,
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "establishment_size": S1_LARGE,
        "hjm_lmnsh": S1_LARGE_AR,
        "indicator": "Number of Establishments",
        "lbyn": "SYN-IND",
        "value": value,
    }


def _social(code: str) -> dict[str, object]:
    return {
        "year": "2018",
        "activity_code": code,
        "main_economic_activity": "SYN Activity",
        "lnsht_lqtsdy_lry_ysy": "SYN-AR",
        "establishment_size": S2_LARGE,
        "hjm_lmnsh": S2_LARGE_AR,
        "indicator": "Employees",
        "lbyn": "مشتغلون",
        "value": 1,
    }


def _metals(
    year: str,
    firms: int,
    investment: str,
    labour: object,
    licence: str = "Industrial License",
) -> dict[str, object]:
    return {
        "year": year,
        "license_type": licence,
        "nw_ltrkhys": "SYN-AR",
        "number_of_firms": firms,
        "investment_million_qatari_riyals": investment,
        "number_of_labour": labour,
    }


def _mfg_row(
    slug: str,
    period: str,
    indicator: str,
    value: Decimal,
    unit: str,
    source_key: str,
) -> dict[str, object]:
    return {
        "table_code": slug,
        "period": period,
        "breakdown_key": "licence_type=Industrial License",
        "indicator": indicator,
        "value": value,
        "unit": unit,
        **_lineage(source_key, "Ministry of Commerce and Industry", MFG_METHOD),
    }


def _product(product: str, unit: str, value: int) -> dict[str, object]:
    return {
        "year": "2018",
        "category": "Fertilizers",
        "lfy": "SYN-AR",
        "product": product,
        "lmntj": "SYN-AR",
        "production": value,
        "unit": unit,
        "lwhd": "SYN-AR",
    }


def _trade(measure: str, breakdown: str, value: object) -> dict[str, object]:
    return {
        "year": "2018",
        "type_of_trade": "SYN Retail Group",
        "nw_ltjr": "SYN-AR",
        "measure": measure,
        "lmw_shr": "SYN-AR",
        "breakdown": breakdown,
        "ltfsyl": "SYN-AR",
        "value": value,
    }


def _certificate(
    country: str, kind: str, value: int, arabic: str = "SYN-AR"
) -> dict[str, object]:
    return {
        "year": "2020",
        "type_of_certificate": kind,
        "nw_lshhd": arabic,
        "importing_country": country,
        "ldwl_lmstwrd": "SYN-AR",
        "number_of_issued_certificates": value,
    }


def _previous(
    country: str, vessel: str, indicator: str, number: object
) -> dict[str, object]:
    return {
        "year": "2018",
        "country_of_previous_port": country,
        "bld_lmyn_lsbq": "SYN-AR",
        "vessel_type": vessel,
        "nw_lsfyn": "SYN-AR",
        "indicator": indicator,
        "lbyn": "SYN-AR",
        "number": number,
    }


def _hamad(**measures: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2021",
        "country_of_registration": "SYN Land",
        "bld_ltsjyl": "SYN-AR",
        "number_tonnage": "No. of Vessels",
        "l_dd_wlhmwl": "SYN-AR",
        "others": 0,
        "passengers_vessels": 0,
        "vehicles_vessels": 0,
        "live_sheep": 0,
        "loose_materials": 0,
        "containers": 0,
        "generals_goods": 0,
        "gas_tankers": 0,
        "oil_tankers": 0,
    }
    row.update(measures)
    return row


# S2-ADDF: invented cells, with column names supplied by ADDF-SWEEP.md.
_ACTIVITY_NAMES = {
    BUSINESS: ("economic_activity", "lnsht_lqtsdy"),
    TRANSPORT: ("main_economic_activity", "main_economic_activity_ar"),
    **{
        slug: ("main_economic_activity", "lnsht_lqtsdy_lry_ysy")
        for slug in (TWO, WHOLESALE, SOCIAL, ENERGY, ONE)
    },
}
_WITHHELD_LABELS = (
    "Antigua",
    "Congo",
    "Grand Cayman Islands",
    "Kosovo",
    "Macedonia",
    "Mordovia",
    "NOT STATED",
    "Pretoria",
    "Scotland",
    "Tahiti",
    "Taipei",
    "Tasmania",
    "Trinidad",
)
_REGION_LABELS = ("Caribbean", "Central Africa", "New Guinea", "Timor")
_CERTIFICATE_ALIASES = {
    "Certificate of Origin Under Preferential System": "Certificate of Origin under Preferential System",
    "Gulf Cooperation Council Certificates": "GCC Certificates",
    "Unified Gulf Cooperation Council Certificate of Origin with European Free Trade Association Countries": "Unified GCC Certificate of Origin with EFTA Countries",
    "Unified Gulf Cooperation Council Certificate of Origin with Singapore": "Unified GCC Certificate of Origin with Singapore",
}


def _published_establishment(slug: str) -> dict[str, object]:
    # Source names are independently pinned above, not derived from the review map.
    if slug == SOCIAL:
        return _social("45")
    spec = _map()["slugs"][slug]
    row = {
        "year": "2018",
        "activity_code": "11",
        "value": 1,
        spec["indicator_field"]: "Employees",
        spec["indicator_ar"]: "SYN-IND",
    }
    if slug == ENERGY:
        row["indicator"] = "Number of Employees"
    if slug == ONE:
        row["activity_code"] = "J"
    if slug in (TRANSPORT, WHOLESALE):
        row["activity_code"] = "4911"
    if slug == TRANSPORT:
        row["item_type"] = "Employee"
    if "size_field" in spec:
        row[spec["size_field"]] = spec["size_classes"][0]
        row[spec["size_ar"]] = spec.get("size_pairs", {}).get(
            spec["size_classes"][0], "SYN-AR"
        )
    else:
        row.update(group="SYN Group", lmjmw="SYN-AR")
    english, arabic = _ACTIVITY_NAMES[slug]
    row.update({english: "SYN Activity", arabic: "SYN-AR"})
    return row


@pytest.mark.parametrize("slug", tuple(_ACTIVITY_NAMES))
def test_published_activity_name_columns_are_declared_but_not_released(
    slug: str,
) -> None:
    row = _published_establishment(slug)
    entry = _entry("est_size_act", slug)
    parsed = parse_establishment_size(entry, [row], RECEIPT, _map(), {})
    if slug == BUSINESS:
        assert parsed.rows == ()
        assert _coverage(parsed, "missing_size_class") == 1
    else:
        assert parsed.rows[0]["activity_key"] == row["activity_code"]
        assert not set(_ACTIVITY_NAMES[slug]) & set(parsed.rows[0])


@pytest.mark.parametrize("slug", tuple(_ACTIVITY_NAMES))
def test_published_activity_names_do_not_admit_another_column(slug: str) -> None:
    row = _published_establishment(slug)
    row["SYN_unknown_column"] = "SYN"
    with pytest.raises(AdditionError, match="unknown_source_field"):
        parse_establishment_size(
            _entry("est_size_act", slug), [row], RECEIPT, _map(), {}
        )


@pytest.mark.parametrize("label", _WITHHELD_LABELS + _REGION_LABELS)
def test_sweep_country_labels_are_withheld_and_counted(label: str) -> None:
    parsed = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [_certificate(label, "Certificates of Origin", 1)],
        RECEIPT,
        _map(),
        {},
    )
    reason = (
        "region_not_country" if label in _REGION_LABELS else "country_label_withheld"
    )
    assert parsed.rows == ()
    assert parsed.coverage == (Coverage(reason, 1),)
    assert label not in _crosswalk(_map())


def test_bosnia_maps_to_one_bih_row() -> None:
    with (REVIEW / "country_iso3.csv").open(encoding="utf-8", newline="") as stream:
        reference = [
            row for row in csv.DictReader(stream) if "Bosnia" in row["name_en"]
        ]
    assert reference == [
        {"name_en": "Bosnia and Herzegovina", "iso3": "BIH", "human_reviewed": "false"}
    ]
    review = _map()
    assert "Bosnia" not in review["country_labels_withheld"]
    assert "Bosnia" not in review["regions_not_countries"]
    assert _crosswalk(review)["Bosnia"] == "BIH"
    parsed = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [_certificate("Bosnia", "Certificates of Origin", 1)],
        RECEIPT,
        review,
        {},
    )
    assert len(parsed.rows) == 1
    assert parsed.rows[0]["breakdown_key"] == (
        "certificate_type=Certificates of Origin|importing_country=BIH"
    )
    assert parsed.coverage == ()


@pytest.mark.parametrize("alias, canonical", tuple(_CERTIFICATE_ALIASES.items()))
def test_published_certificate_spelling_has_one_canonical_series(
    alias: str, canonical: str
) -> None:
    entry = _entry("trade_logistics", CERTIFICATES)
    row = _certificate("SYN Land", alias, 1)
    parsed = parse_logistics(entry, [row], RECEIPT, _with_countries(WALK), {})
    assert (
        parsed.rows[0]["breakdown_key"]
        == f"certificate_type={canonical}|importing_country=SLL"
    )
    row["type_of_certificate"] = canonical
    with pytest.raises(AdditionError, match="duplicate_key"):
        parse_logistics(
            entry,
            [_certificate("SYN Land", alias, 1), row],
            RECEIPT,
            _with_countries(WALK),
            {},
        )


def test_agricultural_certificate_is_a_new_type() -> None:
    kind = "Certificate for Agricultural and Animal Products"
    parsed = parse_logistics(
        _entry("trade_logistics", CERTIFICATES),
        [_certificate("SYN Land", kind, 1)],
        RECEIPT,
        _with_countries(WALK),
        {},
    )
    assert (
        parsed.rows[0]["breakdown_key"]
        == f"certificate_type={kind}|importing_country=SLL"
    )


@pytest.mark.parametrize(
    "kind", ("Gulf Cooperation Council Certificates ", "SYN Unknown", "")
)
def test_certificate_alias_lookup_remains_closed(kind: str) -> None:
    with pytest.raises(
        AdditionError,
        match="measure_unparsed" if not kind else "unknown_certificate_type",
    ):
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", kind, 1)],
            RECEIPT,
            _with_countries(WALK),
            {},
        )


@pytest.mark.parametrize("bad", ({"toString": None}, 7, None, []))
def test_alias_table_hostile_leaf_mutations_refuse(bad: object) -> None:
    for alias in _CERTIFICATE_ALIASES:
        spec = _with_countries(WALK)
        spec["certificate_type_aliases"][alias] = bad
        with pytest.raises(AdditionError, match="unknown_certificate_type"):
            parse_logistics(
                _entry("trade_logistics", CERTIFICATES),
                [_certificate("SYN Land", alias, 1)],
                RECEIPT,
                spec,
                {},
            )


@pytest.mark.parametrize("bad", (None, 7, [7], {}))
def test_withheld_country_list_is_closed_text(bad: object) -> None:
    spec = _with_countries(WALK)
    spec["country_labels_withheld"] = bad
    with pytest.raises(AdditionError, match="field_map_unreadable"):
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", "Certificates of Origin", 1)],
            RECEIPT,
            spec,
            {},
        )


@settings(deadline=None)
@given(units=st.integers(min_value=0, max_value=999999999999999999))
def test_six_place_manufacturing_values_round_trip_exactly(units: int) -> None:
    # An integer in millionths of the published unit; no currency conversion.
    from eii_custodian.publicdata.additions.build import _tables

    value = Decimal(units).scaleb(-6)
    parsed = parse_manufacturing(
        _entry("mfg_industry", METALS),
        [_metals("2019", 1, str(value), 1)],
        RECEIPT,
        _map(),
        {},
    )
    table, columns, rows = _tables([parsed])[0]
    assert table == "pub_manufacturing"
    assert dict(columns)["value"] == "DECIMAL(18,6)"
    index = tuple(name for name, _ in columns).index("value")
    assert next(row[index] for row in rows if "investment" in row) == value
    assert (
        next(row["value"] for row in parsed.rows if row["indicator"] == "investment")
        .as_tuple()
        .exponent
        == -6
    )


@pytest.mark.parametrize("value", ("1.2345678", "0.0000001"))
def test_seven_place_manufacturing_value_still_refuses(value: str) -> None:
    with pytest.raises(AdditionError, match="measure_precision"):
        parse_manufacturing(
            _entry("mfg_industry", METALS),
            [_metals("2019", 1, value, 1)],
            RECEIPT,
            _map(),
            {},
        )


@pytest.mark.parametrize("slug", tuple(_ACTIVITY_NAMES))
@pytest.mark.parametrize("language", (0, 1))
def test_missing_published_activity_column_refuses(slug: str, language: int) -> None:
    row = _published_establishment(slug)
    del row[_ACTIVITY_NAMES[slug][language]]
    with pytest.raises(AdditionError, match="source_field_absent"):
        parse_establishment_size(
            _entry("est_size_act", slug), [row], RECEIPT, _map(), {}
        )


@pytest.mark.parametrize(
    "slug",
    (
        METALS,
        "manufacture-of-beverages",
        COMPUTER,
        "manufacture-of-food-products",
        "manufacture-of-furniture",
        "manufacture-of-motor-vehicles-trailers-and-semi-trailers",
        "manufacture-of-rubber-and-plastics-products",
        TEXTILES,
    ),
)
@pytest.mark.parametrize("value", ("1.23456", "1.234567"))
def test_all_swept_manufacturing_shapes_keep_five_and_six_places(
    slug: str, value: str
) -> None:
    spec = _map()["slugs"][slug]
    row = _metals("2019", 1, value, 1)
    if spec["schema"] == "a2":
        row["investment_in_million_qatari_riyals"] = row.pop(
            "investment_million_qatari_riyals"
        )
    parsed = parse_manufacturing(
        _entry("mfg_industry", slug), [row], RECEIPT, _map(), {}
    )
    investment = next(row for row in parsed.rows if row["indicator"] == "investment")
    assert investment["value"] == Decimal(value)
    assert investment["unit"] == "qar_million"


def test_manufacturing_parquet_keeps_six_places(tmp_path: Path) -> None:
    from eii_custodian.publicdata.additions.build import _tables

    parsed = parse_manufacturing(
        _entry("mfg_industry", METALS),
        [_metals("2019", 1, "1.234567", 1)],
        RECEIPT,
        _map(),
        {},
    )
    _, columns, rows = _tables([parsed])[0]
    path = tmp_path / "manufacturing.parquet"
    write_parquet(path, columns, rows)
    found = duckdb.read_parquet(str(path)).filter("indicator = 'investment'")
    assert found.types[found.columns.index("value")] == duckdb.decimal_type(18, 6)
    assert found.fetchall()[0][found.columns.index("value")] == Decimal("1.234567")


@pytest.mark.parametrize("value", ("1000000000000", "999999999999.999999"))
def test_manufacturing_decimal_integer_boundary(value: str) -> None:
    from eii_custodian.publicdata.additions.build import _tables

    parsed = parse_manufacturing(
        _entry("mfg_industry", METALS),
        [_metals("2019", 1, value, 1)],
        RECEIPT,
        _map(),
        {},
    )
    if value == "1000000000000":
        with pytest.raises(AdditionError, match="value_out_of_column"):
            _tables([parsed])
    else:
        assert _tables([parsed])


@pytest.mark.parametrize("bad", ({"toString": None}, 7, None, []))
def test_alias_table_container_mutations_refuse(bad: object) -> None:
    spec = _with_countries(WALK)
    spec["certificate_type_aliases"] = bad
    # An object with an unlisted string key is still a mapping, but not an alias.
    reason = (
        "unknown_certificate_type" if isinstance(bad, dict) else "field_map_unreadable"
    )
    with pytest.raises(AdditionError, match=reason):
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", next(iter(_CERTIFICATE_ALIASES)), 1)],
            RECEIPT,
            spec,
            {},
        )


def test_alias_target_must_be_a_listed_certificate_type() -> None:
    spec = _with_countries(WALK)
    alias = next(iter(_CERTIFICATE_ALIASES))
    spec["certificate_type_aliases"][alias] = "SYN Unlisted Type"
    with pytest.raises(AdditionError, match="unknown_certificate_type"):
        parse_logistics(
            _entry("trade_logistics", CERTIFICATES),
            [_certificate("SYN Land", alias, 1)],
            RECEIPT,
            spec,
            {},
        )


@settings(deadline=None)
@given(
    label=st.text(min_size=1, max_size=12), copies=st.integers(min_value=1, max_value=8)
)
def test_withheld_label_count_is_exact_and_lookup_is_not_normalized(
    label: str, copies: int
) -> None:
    spec = _with_countries(WALK)
    spec["country_labels_withheld"] = [label]
    spec["regions_not_countries"] = []
    spec["country_crosswalk"] = []
    row = _certificate(label, "Certificates of Origin", 1)
    parsed = parse_logistics(
        _LABEL_ENTRIES[CERTIFICATES], [row] * copies, RECEIPT, spec, {}
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "country_label_withheld") == copies
    row["importing_country"] = label + " "
    with pytest.raises(AdditionError, match="country_unreviewed"):
        parse_logistics(_LABEL_ENTRIES[CERTIFICATES], [row], RECEIPT, spec, {})
