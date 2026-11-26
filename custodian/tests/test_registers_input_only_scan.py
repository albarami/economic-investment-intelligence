"""Decision 0119 (option B): published non-key values meet input-only keys only.

Proposed decision 0123 narrows intake licences to each row's own company;
withheld duplicates still meet every row, and released registrations do not. The key slot keeps its own check against
withheld registrations only. Every value here is invented; no run of exactly
eight or eleven digits is used.
"""

import pytest
from custodian.tests.test_registers import capture, commerce, fc, inputs
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import (
    CARD_COLUMNS,
    FORMAT_ONLY_NUMBER,
    SCHEMAS,
    TYPED_FIELDS,
    RegisterError,
)
from eii_custodian.publicdata.registers.parse import parse
from eii_custodian.publicdata.registers.provenance import Frame
from eii_custodian.publicdata.registers.validate import validate_release

FRAME = Frame(frozenset())
# One invented number of four digits, not of the 19xx or 20xx shape, so even a
# listed typed column never admits it by format (decision 0105 item 2).
KEY = "2126"
# The free-text card fields of the default commerce row hold digits; these hold
# none, so a case isolates the one column it names.
PLAIN = dict(building_number="SYN building")
# Every published non-key column of each source, with a valid value carrying
# the token KEY. `tax_registered` (yes/no) and `source_id` (a closed name) can
# carry no digit; `registered_cell` is computed from the frame and is covered by
# decision 0105's cell-key test; `branches` is empty-only.
TEXT = "SYN " + KEY
DATE = KEY + "-01-05"
BIZ = {
    "name_ar": TEXT,
    "name_en": TEXT,
    "establishment_type": TEXT,
    "establishment_subtype": TEXT,
    "legal_form": TEXT,
    "business_type": TEXT,
    "business_category": TEXT,
    "classification": TEXT,
    "registration_status": TEXT,
    "registration_issue_date": DATE,
    "registration_expiry_date": DATE,
    "licence_status": TEXT,
    "licence_issue_date": DATE,
    "licence_expiry_date": DATE,
    "municipality": TEXT,
    "zone": KEY,
    "lon": float("1." + KEY),
    "lat": float("2." + KEY),
    "tax_registration_number": TEXT,
    "tax_classification_year": KEY,
    "tax_type": TEXT,
    "capital_qar": int(KEY),
    "establishment_nationality": TEXT,
    "street_number": KEY,
    "building_number": TEXT,
    "establishment_type_ar": TEXT,
    "establishment_subtype_ar": TEXT,
    "legal_form_ar": TEXT,
    "classification_ar": TEXT,
    "registration_status_ar": TEXT,
    "licence_status_ar": TEXT,
    "municipality_ar": TEXT,
    "district_en": TEXT,
    "district_ar": TEXT,
    "block_en": KEY,
    "block_ar": KEY,
    "establishment_nationality_ar": TEXT,
}
CENTRE = {
    "name_en": TEXT,
    "name_ar": TEXT,
    "registered_address": TEXT,
    "licence_status": TEXT,
    "event": TEXT,
    "notice_expiration_date": DATE,
    "lon": float("1." + KEY),
    "lat": float("2." + KEY),
}
COLUMNS = [("biz_register", name) for name in BIZ] + [
    ("fc_register", name) for name in CENTRE
]
# Values of another release table, nested, typed or in a column name.
PLACE = {
    "text": {"name_en": "SYN copied " + KEY},
    "number": {"count": int(KEY)},
    "float": {"share": float("0." + KEY)},
    "list": {"value": ["SYN", KEY]},
    "mapping": {"value": {"k": KEY}},
    "mapping_key": {"value": {KEY: None}},
    "bytes": {"value": KEY.encode()},
    "nested": {"value": {"k": ([KEY.encode()], 1)}},
    "column_name": {"SYN " + KEY: "SYN"},
}


def _tables(source, column, registration="54321"):
    """Both sources' cards; `column` of `source`'s card holds the token KEY."""
    cards = parse(
        "biz_register",
        inputs(rows=[commerce(**PLAIN, registration_number=registration)]),
        FRAME,
    ) + parse("fc_register", inputs("fc_register"), FRAME)
    if column is not None:
        index = 0 if source == "biz_register" else 1
        if column in ("lon", "lat"):
            cards[index].update(lon=1.25, lat=2.25)  # a coordinate is a pair
        cards[index][column] = (BIZ if index == 0 else CENTRE)[column]
    return {"pub_register_company": cards, "pub_register_snapshot": []}


def _scan(tables, licences=(), withheld=()):
    return validate_release(
        tables,
        FRAME,
        licences_by_registration={
            row["registration_number"]: frozenset(licences)
            for row in tables["pub_register_company"]
        },
        withheld_registrations=frozenset(withheld),
    )


def _input_only(role):
    return dict(licences=(KEY,)) if role == "licence" else dict(withheld=(KEY,))


def test_register_every_published_card_column_is_covered():
    """The column lists above are every published non-key card column."""
    unscanned = {"registration_number", "registered_cell", "source_id"}
    biz = set(SCHEMAS["establishments"]) & set(CARD_COLUMNS)
    assert set(BIZ) == biz - unscanned - {"tax_registered", "branches"}
    centre = set(SCHEMAS["companies"]) & set(CARD_COLUMNS)
    centre |= {"event", "notice_expiration_date", "lon", "lat"}
    assert set(CENTRE) == centre - unscanned


@pytest.mark.parametrize("source,column", COLUMNS)
@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_input_only_key_in_published_column_refuses(source, column, role):
    """A licence or a withheld duplicate in any published column refuses; the
    passing control differs only in the input-only set."""
    tables = _tables(source, column)
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, **_input_only(role))


@pytest.mark.parametrize("source,column", COLUMNS)
def test_register_released_key_in_published_column_builds(source, column):
    """Option B: a value equal to a registration being released is published."""
    assert KEY in _scan(_tables(source, column, registration=KEY))


@pytest.mark.parametrize("plant", PLACE.values(), ids=PLACE.keys())
@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_input_only_key_in_unkeyed_table_follows_c1(plant, role):
    tables = {**_tables(None, None), "pub_place": [plant]}
    _scan(tables)
    if role == "licence":
        # No registration on this row: no own-company licences (decision 0123).
        _scan(tables, **_input_only(role))
    else:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _scan(tables, **_input_only(role))


@pytest.mark.parametrize("plant", PLACE.values(), ids=PLACE.keys())
def test_register_released_key_in_other_table_builds(plant):
    tables = {**_tables(None, None, registration=KEY), "pub_place": [plant]}
    assert KEY in _scan(tables)


def _list_and_snapshot(registration, count, period):
    tables = _tables(None, None, registration=registration)
    tables["pub_register_snapshot"] = [
        dict(
            registration_number=registration,
            period=period,
            source_id="biz_register",
            registered_cell=None,
        )
    ]
    tables["register_company_list"] = [
        dict(
            registration_number=registration,
            period=period,
            employee_count=count,
            suppression_reason_code=None,
        )
    ]
    return tables


@pytest.mark.parametrize(
    "count,period", [(int(KEY), "2026-11"), (3, KEY + "-11")], ids=["count", "period"]
)
@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_input_only_key_in_list_and_snapshot_refuses(count, period, role):
    tables = _list_and_snapshot("54321", count, period)
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, **_input_only(role))


@pytest.mark.parametrize(
    "count,period", [(int(KEY), "2026-11"), (3, KEY + "-11")], ids=["count", "period"]
)
def test_register_released_key_in_list_and_snapshot_builds(count, period):
    assert KEY in _scan(_list_and_snapshot(KEY, count, period))


# --- The key slot is unchanged ---------------------------------------------


def test_register_withheld_number_in_key_slot_still_refuses():
    tables = _tables(None, None, registration=KEY)
    _scan(tables, withheld=("54321",))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, withheld=(KEY,))


def test_register_licence_equal_to_released_key_slot_builds():
    """Brief item 2: licences do not join the key slot check, which would be a
    refusal the owner did not ask for; a licence equal to a published
    registration still passes, as before."""
    assert KEY in _scan(_tables(None, None, registration=KEY), licences=(KEY,))


def test_register_released_key_and_licence_in_one_column_refuses():
    """The same token released and input-only: the input-only key decides."""
    tables = _tables("biz_register", "name_en", registration=KEY)
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, licences=(KEY,))


# --- Builds end to end -------------------------------------------------------


def test_register_released_key_in_free_text_build_publishes(tmp_path):
    centre = capture(
        "fc_register",
        files=inputs("fc_register", [fc(registered_address="SYN Office 54321")]),
    )
    rows = [commerce(**PLAIN, name_en="SYN Plaza 65432", street_number="54321")]
    result = build(
        tmp_path, "public_only", FRAME, (capture(files=inputs(rows=rows)), centre), ()
    )
    assert {
        card["registration_number"] for card in result.tables["pub_register_company"]
    } == {"54321", "65432"}
    assert (tmp_path / "current" / "manifest.json").exists()


@pytest.mark.parametrize("column", ["name_en", "street_number"])
def test_register_withheld_duplicate_in_column_build_refuses(tmp_path, column):
    rows = [
        commerce(**PLAIN, registration_number="97531"),
        commerce(**PLAIN, row_key="c" * 20, registration_number="97531"),
        commerce(**PLAIN, row_key="d" * 20, registration_number="54322"),
    ]
    build(
        tmp_path / "pass",
        "public_only",
        FRAME,
        (capture(files=inputs(rows=rows)), capture("fc_register")),
        (),
    )
    rows[2][column] = "97531" if column == "street_number" else "SYN 97531"
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path / "refuse",
            "public_only",
            FRAME,
            (capture(files=inputs(rows=rows)), capture("fc_register")),
            (),
        )
    assert not (tmp_path / "refuse" / "current").exists()


# --- A generator over the input space ---------------------------------------

_PLANTS = {
    "free_text": lambda n: ("pub_register_company", "name_en", "SYN " + n),
    "listed_integer": lambda n: ("pub_register_company", "street_number", n),
    "listed_number": lambda n: ("pub_register_company", "capital_qar", int(n)),
    "unlisted_number": lambda n: ("pub_place", "count", int(n)),
    "nested": lambda n: ("pub_place", "value", {"k": ["SYN " + n]}),
    # Decision 0119 item 6: a digest-shaped string outside a digest field.
    "digest_shaped": lambda n: ("pub_register_company", "name_en", n.rjust(64, "a")),
    "digest_shaped_nested": lambda n: ("pub_place", "value", [n.rjust(64, "e")]),
}


def _oracle_refuses(role, table, column, number):
    """Decisions 0119 and proposed 0123: a keyed row meets its own licences,
    an unkeyed row only withheld keys; typed short/year admission is unchanged."""
    if role == "released" or (role == "licence" and table == "pub_place"):
        return False
    listed = f"{table}.{column}" in TYPED_FIELDS
    short = len(number) <= 2 or (len(number) == 4 and number[:2] in {"19", "20"})
    return not (listed and short)


@given(
    st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True),
    st.sampled_from(sorted(_PLANTS)),
    st.sampled_from(["released", "licence", "withheld"]),
)
def test_register_input_only_scan_property(number, plant, role):
    assert bool(FORMAT_ONLY_NUMBER.fullmatch(number)) == (
        len(number) <= 2 or (len(number) == 4 and number[:2] in {"19", "20"})
    )
    table, column, value = _PLANTS[plant](number)
    registration = number if role == "released" else "54321"
    tables = _tables(None, None, registration=registration)
    if table == "pub_register_company":
        tables["pub_register_company"][0][column] = value
    else:
        tables[table] = [{column: value}]
    sets = {
        "released": {},
        "licence": dict(licences=(number,)),
        "withheld": dict(withheld=(number,)),
    }[role]
    if number in {"54321", "65432"}:
        return  # a key slot itself (withheld) or a cross-source key, tested above
    if _oracle_refuses(role, table, column, number):
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _scan(tables, **sets)
    else:
        _scan(tables, **sets)
