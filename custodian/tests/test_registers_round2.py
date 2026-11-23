"""L-1586: invented registration absences, duplicate rows and closed egress."""

import json
import shutil

import pytest
from custodian.tests.test_registers import (
    ROW_IDENTITY_FIXTURE,
    capture,
    commerce,
    inputs,
    row_identity_oracle,
)
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.bundle import BUNDLE, PIN, load_bundle
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.parse import InputAudit, _rows, parse
from eii_custodian.publicdata.registers.provenance import Frame, digest
from eii_custodian.publicdata.registers.validate import validate_release


@pytest.mark.parametrize("value", ["a", "AbCdE", "ABCDEFGHIJ"])
def test_register_letters_only_is_null_at_intake(value):
    audit = InputAudit()
    rows = _rows(
        inputs(rows=[commerce(registration_number=value)])["establishments"],
        "establishments",
        audit,
    )
    assert rows[0]["registration_number"] is None
    assert audit.non_registration_absences == 1
    cards = parse(
        "biz_register",
        inputs(rows=[commerce(registration_number=value)]),
        Frame(frozenset()),
    )
    assert cards[0]["registration_number"] == ROW_IDENTITY_FIXTURE


@pytest.mark.parametrize(
    "value", ["ABCDEFGHIJK", "abc1", "a/b", " abc", "abc ", "é", "\uff21", "a\nb"]
)
def test_register_non_registration_other_shapes_refuse(value):
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        parse(
            "biz_register",
            inputs(rows=[commerce(registration_number=value)]),
            Frame(frozenset()),
        )


@given(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        min_size=1,
        max_size=10,
    )
)
def test_register_letters_only_property(value):
    audit = InputAudit()
    rows = _rows(
        inputs(rows=[commerce(registration_number=value)])["establishments"],
        "establishments",
        audit,
    )
    assert rows[0]["registration_number"] is None
    assert audit.non_registration_absences == 1


@given(
    st.lists(
        st.one_of(
            st.just(""),
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                min_size=1,
                max_size=10,
            ),
            st.tuples(
                st.text(alphabet="0123456789", min_size=1, max_size=6),
                st.one_of(
                    st.just(""),
                    st.text(alphabet="0123456789", min_size=1, max_size=3).map(
                        lambda part: "/" + part
                    ),
                ),
            ).map(lambda parts: "".join(parts)),
        ),
        min_size=1,
        max_size=4,
    ).flatmap(lambda pool: st.lists(st.sampled_from(pool), max_size=12))
)
def test_register_duplicate_partition_property(numbers):
    source = [
        commerce(row_key=f"{index:020x}", registration_number=number)
        for index, number in enumerate(numbers)
    ]
    audit = InputAudit()
    files = (
        inputs(rows=source)
        if source
        else {"establishments": inputs()["establishments"].splitlines(keepends=True)[0]}
    )
    cards = parse("biz_register", files, Frame(frozenset()), audit=audit)
    expected = {
        (
            row_identity_oracle(row["row_key"])
            if (not number or number.isalpha()) or numbers.count(number) > 1
            else number
        )
        for row, number in zip(source, numbers, strict=True)
    }
    assert {row["registration_number"] for row in cards} == expected
    assert len(cards) == len(source)
    assert audit.duplicate_absences == sum(
        (bool(number) and not number.isalpha()) and numbers.count(number) > 1
        for number in numbers
    )
    assert audit.non_registration_absences == sum(
        number.isalpha() for number in numbers
    )
    assert audit.duplicate_registrations == {
        number
        for number in numbers
        if (bool(number) and not number.isalpha()) and numbers.count(number) > 1
    }
    assert cards == parse(
        "biz_register",
        inputs(rows=list(reversed(source))) if source else files,
        Frame(frozenset()),
    )


@pytest.mark.parametrize("kind", ["public_only", "protected"])
def test_register_round2_absences_survive_bundle(tmp_path, kind):
    frame = Frame(frozenset())
    rows = [
        commerce(),
        commerce(row_key="c" * 20),
        commerce(row_key="d" * 20, registration_number="AbCdE"),
    ]
    source = capture(files=inputs(rows=rows))
    result = build(
        tmp_path / "stage", kind, frame, (source, capture("fc_register")), (source,)
    )
    expected = [
        dict(
            source_id="biz_register",
            period="2026-11",
            use=use,
            field="registration_number",
            reason=reason,
            count=count,
        )
        for use in ("current", "snapshot")
        for reason, count in (
            ("published_non_registration_value", 1),
            ("published_duplicate_registration", 2),
        )
    ]
    assert result.manifest["field_absences"] == expected
    assert {
        row["registration_number"] for row in result.tables["pub_register_company"]
    } == {"65432", ROW_IDENTITY_FIXTURE, *("ROW-" + letter * 20 for letter in "cd")}
    shutil.copytree(tmp_path / "stage/current", tmp_path / BUNDLE)
    body = (tmp_path / BUNDLE / "manifest.json").read_bytes()
    (tmp_path / PIN).write_text(
        json.dumps(dict(version="register_bundle_pin_v1", manifest_sha256=digest(body)))
    )
    bundle = load_bundle(tmp_path / BUNDLE, tmp_path / PIN, frame.cells)
    assert bundle.manifest["field_absences"] == expected


@pytest.mark.parametrize("same_number", [False, True])
def test_register_duplicate_row_key_still_refuses(same_number):
    with pytest.raises(
        RegisterError,
        match=(
            r"^duplicate_registration_key$" if same_number else r"^duplicate_row_key$"
        ),
    ):
        parse(
            "biz_register",
            inputs(
                rows=[
                    commerce(),
                    commerce(registration_number="54321" if same_number else "54322"),
                ]
            ),
            Frame(frozenset()),
        )


@pytest.mark.parametrize("field", ["name_en", "building_number", "capital_qar"])
@pytest.mark.parametrize("historical", [False, True])
def test_register_duplicate_registration_leak_refuses(tmp_path, field, historical):
    source = capture(
        files=inputs(rows=[commerce(**{field: "54321"}), commerce(row_key="c" * 20)])
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path,
            "public_only",
            Frame(frozenset()),
            (
                capture(files=inputs(rows=[commerce(registration_number="54322")])),
                capture("fc_register"),
            )
            if historical
            else (source, capture("fc_register")),
            (source,) if historical else (),
        )
    assert not (tmp_path / "current").exists()


@pytest.mark.parametrize(
    "channel", ["earlier_card", "later_card", "manifest", "snapshot", "storage_count"]
)
def test_register_duplicate_registration_cross_capture_leak_refuses(tmp_path, channel):
    duplicates = capture(
        files=inputs(
            rows=[
                commerce(
                    registration_number="4" if channel == "storage_count" else "54321"
                ),
                commerce(
                    row_key="c" * 20,
                    registration_number="4" if channel == "storage_count" else "54321",
                ),
            ]
        )
    )
    if channel == "storage_count":
        duplicates = capture(
            files=inputs(
                rows=[
                    # Decision 0105 item 5: a 3-digit count still meets the key.
                    commerce(registration_number="125"),
                    commerce(row_key="c" * 20, registration_number="125"),
                    *(
                        commerce(
                            row_key=f"{i:020x}", registration_number=str(50000 + i)
                        )
                        for i in range(122)
                    ),
                ]
            )
        )
    centre = capture("fc_register")
    current = (duplicates, centre)
    snapshots = ()
    if channel == "earlier_card":
        current, snapshots = (capture(), centre), (duplicates,)
    elif channel == "later_card":
        current, snapshots = (duplicates, centre), (capture(),)
    elif channel == "manifest":
        from dataclasses import replace

        duplicates = replace(
            duplicates, receipt=dict(duplicates.receipt, publisher="SYN 54321")
        )
        current = (duplicates, centre)
    elif channel == "snapshot":
        current, snapshots = (duplicates, centre), (capture(),)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(tmp_path, "public_only", Frame(frozenset()), current, snapshots)


@pytest.mark.parametrize(
    "value",
    ["54321", 54321, 54321.0, {"54321": None}, ["prefix54321suffix"]],
    ids=["text", "integer", "float", "key", "nested"],
)
def test_register_duplicate_registration_all_fields_refuse(value):
    frame = Frame(frozenset())
    cards = parse("biz_register", inputs(), frame)
    cards[0]["registration_number"] = "ROW-" + "a" * 20
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            {
                "pub_register_company": cards,
                "pub_register_snapshot": [],
                "source_registry": [{"value": value}],
            },
            frame,
            withheld_registrations=frozenset({"54321"}),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", []),
        ("field", []),
        ("reason", []),
        ("source_id", "fc_register"),
        ("field", "notice_expiration_date"),
        ("reason", "published_non_iso_notice_shape"),
    ],
)
def test_register_round2_absence_closed_combination_refuses(tmp_path, field, value):
    from custodian.tests.test_register_tables import _rewrite_manifest, _stage

    frame = Frame(frozenset())
    _stage(tmp_path, tmp_path / "stage", frame)
    entry = dict(
        source_id="biz_register",
        period="2026-11",
        use="current",
        field="registration_number",
        reason="published_non_registration_value",
        count=1,
    )
    _rewrite_manifest(
        tmp_path,
        lambda manifest: manifest.__setitem__(
            "field_absences", [dict(entry, **{field: value})]
        ),
    )
    with pytest.raises(RegisterError, match=r"^register_bundle_absence$"):
        load_bundle(tmp_path / BUNDLE, tmp_path / PIN, frame.cells)


def test_register_round2_absence_duplicate_refuses(tmp_path):
    from custodian.tests.test_register_tables import _rewrite_manifest, _stage

    frame = Frame(frozenset())
    _stage(tmp_path, tmp_path / "stage", frame)
    entry = dict(
        source_id="biz_register",
        period="2026-11",
        use="current",
        field="registration_number",
        reason="published_duplicate_registration",
        count=2,
    )
    _rewrite_manifest(
        tmp_path,
        lambda manifest: manifest.__setitem__("field_absences", [entry, dict(entry)]),
    )
    with pytest.raises(RegisterError, match=r"^register_bundle_absence$"):
        load_bundle(tmp_path / BUNDLE, tmp_path / PIN, frame.cells)
