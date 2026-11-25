"""Proposed decision 0123: own-company licences, invented inputs only."""

import json
import re

import pytest
from custodian.tests.test_registers import (
    capture,
    commerce,
    fc,
    inputs,
    row_identity_oracle,
)
from custodian.tests.test_registers_input_only_scan import (
    COLUMNS,
    FRAME,
    KEY,
    PLACE,
    PLAIN,
    _tables,
)
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.parse import InputAudit, parse
from eii_custodian.publicdata.registers.validate import (
    _scan_release_row,
    validate_release,
)

OWN = "54321"
OTHER = "54322"


def _scan(tables, own=(), other=(), withheld=(), owner=OWN):
    return validate_release(
        tables,
        FRAME,
        licences_by_registration={owner: frozenset(own), OTHER: frozenset(other)},
        withheld_registrations=frozenset(withheld),
    )


@pytest.mark.parametrize(
    "column", ["street_number", "building_number", "capital_qar", "registered_address"]
)
def test_register_other_company_licence_builds(tmp_path, column):
    """Only the published value changes from the valid build control."""
    rows = [
        commerce(**PLAIN),
        commerce(
            **PLAIN, registration_number=OTHER, row_key="c" * 20, licence_number=KEY
        ),
    ]
    centre_rows = [fc()]

    def current():
        return (
            capture(files=inputs(rows=rows)),
            capture("fc_register", files=inputs("fc_register", rows=centre_rows)),
        )

    build(tmp_path / "control", "public_only", FRAME, current(), ())
    if column == "registered_address":
        centre_rows[0][column] = "SYN address " + KEY
    else:
        rows[0][column] = KEY
    result = build(tmp_path / "plant", "public_only", FRAME, current(), ())
    assert len(result.tables["pub_register_company"]) == 3
    metadata = json.dumps(result.manifest)
    assert "licences_by_registration" not in metadata
    assert "licence_number" not in metadata


@pytest.mark.parametrize("source,column", COLUMNS)
def test_register_own_licence_in_each_card_column_refuses(source, column):
    tables = _tables(source, column)
    owner = OWN if source == "biz_register" else "65432"
    _scan(tables, other=(KEY,), owner=owner)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, own=(KEY,), other=(KEY,), owner=owner)


@pytest.mark.parametrize("column", ["name_en", "street_number"])
def test_register_withheld_duplicate_in_other_company_refuses(column):
    tables = _tables("biz_register", column)
    _scan(tables, other=(KEY,))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, other=(KEY,), withheld=(KEY,))


def test_register_intake_licences_follow_row_identity():
    rows = [
        commerce(**PLAIN),
        commerce(**PLAIN, row_key="c" * 20, registration_number="", licence_number=KEY),
        commerce(
            **PLAIN,
            row_key="d" * 20,
            registration_number="97531",
            licence_number="97532",
        ),
        commerce(
            **PLAIN,
            row_key="e" * 20,
            registration_number="97531",
            licence_number="97533",
        ),
    ]
    audit = InputAudit()
    cards = parse("biz_register", inputs(rows=rows), FRAME, audit=audit)
    assert audit.licences_by_registration == {
        OWN: {"97003"},
        row_identity_oracle("c" * 20): {KEY},
        row_identity_oracle("d" * 20): {"97532"},
        row_identity_oracle("e" * 20): {"97533"},
    }
    assert audit.licences == {"97003", KEY, "97532", "97533"}
    assert len(cards) == 4


@pytest.mark.parametrize("registration", ["", "97531"])
def test_register_numberless_row_own_licence_build_refuses(tmp_path, registration):
    rows = [commerce(**PLAIN, registration_number=registration)]
    if registration:
        rows.append(
            commerce(
                **PLAIN,
                registration_number=registration,
                row_key="c" * 20,
                licence_number="97532",
            )
        )
    build(
        tmp_path / "control",
        "public_only",
        FRAME,
        (capture(files=inputs(rows=rows)), capture("fc_register")),
        (),
    )
    rows[0]["name_en"] = "SYN 97003"
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path / "plant",
            "public_only",
            FRAME,
            (capture(files=inputs(rows=rows)), capture("fc_register")),
            (),
        )
    assert not (tmp_path / "plant" / "current").exists()


@pytest.mark.parametrize("column", ["name_en", "street_number"])
@pytest.mark.parametrize("target", ["earlier", "later"])
def test_register_historical_licence_map_is_unioned_before_scan(
    tmp_path, column, target
):
    first = capture(files=inputs(rows=[commerce(licence_number="97532", **PLAIN)]))
    later = capture(
        period="2026-12", files=inputs(rows=[commerce(licence_number=KEY, **PLAIN)])
    )
    current = (capture(period="2026-12"), capture("fc_register", period="2026-12"))
    build(tmp_path / "control", "public_only", FRAME, current, (first, later))
    own, leaked = ("97532", KEY) if target == "earlier" else (KEY, "97532")
    rows = [commerce(licence_number=own, **PLAIN)]
    rows[0][column] = "SYN " + leaked if column == "name_en" else leaked
    if target == "earlier":
        first = capture(files=inputs(rows=rows))
    else:
        later = capture(period="2026-12", files=inputs(rows=rows))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(tmp_path / "plant", "public_only", FRAME, current, (first, later))
    assert not (tmp_path / "plant" / "current").exists()


@given(
    number=st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True).filter(
        lambda n: n not in {OWN, OTHER, "65432"}
    ),
    own=st.sets(st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True), max_size=5),
    other=st.sets(st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True), max_size=5),
    role=st.sampled_from(["own", "other", "withheld", "none"]),
    column=st.sampled_from(["name_en", "street_number", "capital_qar"]),
)
def test_register_row_licence_map_property(number, own, other, role, column):
    # Remove unrelated fixture tokens so the single planted token decides.
    own = own - {"1", "2", "3", "11", "25", "2026", "2027", OWN, "65432"}
    own.discard(number)
    withheld = set()
    if role == "own":
        own.add(number)
    elif role == "other":
        other.add(number)
    elif role == "withheld":
        withheld.add(number)
    tables = _tables(None, None)
    row = tables["pub_register_company"][0]
    row[column] = (
        int(number)
        if column == "capital_qar"
        else ("SYN " + number if column == "name_en" else number)
    )
    admitted_shape = len(number) <= 2 or (
        len(number) == 4 and number[:2] in {"19", "20"}
    )
    tokens = set(re.findall(r"[0-9]+(?:/[0-9]+)?", str(row[column])))
    refused = bool(tokens & (own | withheld)) and not (
        column != "name_en" and admitted_shape
    )
    if refused:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _scan(tables, own, other, withheld)
    else:
        _scan(tables, own, other, withheld)


@pytest.mark.parametrize("plant", PLACE.values(), ids=PLACE.keys())
def test_register_own_licence_recursive_scan_boundary_refuses(plant):
    """Exercise the row scanner alone: card schemas reject container/extra
    columns before reaching it; their release_type/release_schema guards stay.
    The real scanner must nevertheless protect every recursive value shape.
    """
    row = {"registration_number": OWN, **plant}
    _scan_release_row(
        "pub_register_company", row, {OTHER: frozenset({KEY})}, frozenset()
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan_release_row(
            "pub_register_company",
            row,
            {OTHER: frozenset({KEY}), OWN: frozenset({KEY})},
            frozenset(),
        )


@pytest.mark.parametrize("registration", [None, "", "54323"])
def test_register_no_licence_for_row_meets_only_withheld(registration):
    row = {"value": KEY}
    if registration is not None:
        row["registration_number"] = registration
    _scan_release_row(
        "pub_register_company", row, {OTHER: frozenset({KEY})}, frozenset()
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan_release_row(
            "pub_register_company", row, {OTHER: frozenset({KEY})}, frozenset({KEY})
        )


def test_register_overlapping_company_licences_still_refuse_for_owner():
    tables = _tables("biz_register", "name_en")
    _scan(tables, other=(KEY,))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, own=(KEY,), other=(KEY,))


@pytest.mark.parametrize(
    "column,value", [("street_number", "12"), ("capital_qar", 2020)]
)
def test_register_own_licence_keeps_typed_short_and_year_admission(column, value):
    tables = _tables(None, None)
    tables["pub_register_company"][0][column] = value
    _scan(tables, own=(str(value),))
    tables["pub_register_company"][0]["name_en"] = "SYN " + str(value)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, own=(str(value),))
