"""S2-P71: invented records matching the lead's observed register shapes."""

from dataclasses import replace

import pytest
from custodian.tests.test_registers import (
    ROW_IDENTITY_FIXTURE,
    capture,
    commerce,
    csv_bytes,
    inputs,
    row_identity_oracle,
)
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.activity_check import register_activity_check
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.parse import parse, parse_value
from eii_custodian.publicdata.registers.provenance import Frame
from eii_custodian.publicdata.registers.validate import (
    RELEASE_TABLES,
    scan_artefact,
    validate_release,
)
from eii_custodian.publicdata.review.activity import ActivityRow, IsicClass, ReviewRow
from eii_custodian.publicdata.review.cache_fixture import read_parquet


@pytest.mark.parametrize("kind", ["public_only", "protected"])
def test_register_restoration_uses_row_key_and_withholds_licence(tmp_path, kind):
    frame = Frame(frozenset())
    source = capture(files=inputs(rows=[commerce(registration_number="")]))
    result = build(tmp_path, kind, frame, (source, capture("fc_register")), (source,))
    for table, rows in result.tables.items():
        assert any(row["registration_number"] == ROW_IDENTITY_FIXTURE for row in rows)
        assert all("licence_number" not in row for row in rows)
        stored = read_parquet(
            (tmp_path / "current/tables" / (table + ".parquet")).read_bytes()
        )
        assert list(stored) == rows
    card = result.tables["pub_register_company"][1]
    assert card["business_type"] is None
    assert card["registration_status"] is None
    assert card["registration_issue_date"] == "2026-11-03"


def test_register_licence_equal_to_registration_passes_intake(tmp_path):
    result = build(
        tmp_path,
        "public_only",
        Frame(frozenset()),
        (
            capture(files=inputs(rows=[commerce(licence_number="65432")])),
            capture("fc_register"),
        ),
        (),
    )
    assert all(
        "licence_number" not in row for row in result.tables["pub_register_company"]
    )


@pytest.mark.parametrize("flag", ["yes", "no"])
def test_register_lowercase_tax_flag(flag):
    assert parse_value(flag, "yes_no") == flag


@pytest.mark.parametrize("flag", ["Yes", "No", "YES", "", "y"])
def test_register_tax_flag_closed_set(flag):
    with pytest.raises(RegisterError, match=r"^tax_registered_format$"):
        parse_value(flag, "yes_no")


@given(st.text(alphabet="0123456789/abc", max_size=16))
def test_register_registration_shape_oracle(value):
    parts = value.split("/")
    valid = (
        len(parts) in (1, 2)
        and 1 <= len(parts[0]) <= 6
        and all(c in "0123456789" for c in parts[0])
        and (
            len(parts) == 1
            or (1 <= len(parts[1]) <= 3 and all(c in "0123456789" for c in parts[1]))
        )
    )
    if valid:
        assert parse_value(value, "registration") == value
    else:
        with pytest.raises(RegisterError, match=r"^registration_format$"):
            parse_value(value, "registration")


@pytest.mark.parametrize(
    "number", ["1", "12", "123", "1234", "12345/123", "123456/123"]
)
def test_register_observed_registration_shapes(number):
    assert parse_value(number, "registration") == number


@pytest.mark.parametrize("number", ["1234567", "123/1234", "12//3", "abc"])
def test_register_outside_observed_shapes(number):
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        parse_value(number, "registration")


@given(
    st.lists(
        st.text(alphabet="0123456789abcdef", min_size=20, max_size=20),
        min_size=1,
        max_size=5,
        unique=True,
    ),
    st.one_of(st.just(""), st.text(alphabet="0123456789", min_size=1, max_size=7)),
)
@example(row_keys=["f" * 20], licence="")
@example(row_keys=["f" * 20], licence="97009")
def test_register_missing_number_key_is_independent_of_licence(row_keys, licence):
    frame = Frame(frozenset())
    rows = [
        commerce(row_key=key, registration_number="", licence_number=licence)
        for key in row_keys
    ]
    rows.append(commerce(row_key="f" * 20))
    if licence == "":
        with pytest.raises(RegisterError, match=r"^integer_format$"):
            parse("biz_register", inputs(rows=rows), frame)
        return
    if "f" * 20 in row_keys:
        with pytest.raises(RegisterError, match=r"^duplicate_row_key$"):
            parse("biz_register", inputs(rows=rows), frame)
        return
    first = parse("biz_register", inputs(rows=rows), frame)
    second = parse(
        "biz_register",
        inputs(rows=[dict(row, licence_number="97009") for row in rows]),
        frame,
    )
    assert first == second
    assert {row["registration_number"] for row in first} == {
        row_identity_oracle(key) for key in row_keys
    } | {"54321"}
    validate_release(
        {"pub_register_company": first, "pub_register_snapshot": []}, frame
    )


@pytest.mark.parametrize(
    ("licence", "reason"), [("", "integer_format"), ("97009", "duplicate_row_key")]
)
def test_register_row_key_collision_reason_by_licence(licence, reason):
    rows = [
        commerce(row_key="f" * 20, registration_number="", licence_number=licence),
        commerce(row_key="f" * 20),
    ]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        parse("biz_register", inputs(rows=rows), Frame(frozenset()))


@pytest.mark.parametrize(
    "key", ["row-" + "a" * 20, "ROW-" + "a" * 19, "ROW-" + "z" * 20, "SYN-F-key"]
)
def test_register_invalid_restored_key_refuses(key):
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    rows[0]["registration_number"] = key
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        validate_release(
            {"pub_register_company": rows, "pub_register_snapshot": []}, frame
        )


@pytest.mark.parametrize("field", ["name_en", "building_number"])
def test_register_licence_leak_refuses(tmp_path, field):
    source = capture(files=inputs(rows=[commerce(**{field: "97003"})]))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path,
            "public_only",
            Frame(frozenset()),
            (source, capture("fc_register")),
            (),
        )
    assert not (tmp_path / "current").exists()


def test_register_licence_column_refuses():
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    rows[0]["licence_number"] = "97003"
    with pytest.raises(RegisterError, match=r"^release_schema$"):
        validate_release(
            {"pub_register_company": rows, "pub_register_snapshot": []}, frame
        )


@pytest.mark.parametrize("date", ["12-Abc-345", "99-Xyz-000"])
def test_register_notice_shape_is_counted_absence(tmp_path, date):
    files = inputs("fc_register")
    files["events"] = csv_bytes(
        "events",
        [dict(qfc_number="65432", event="SYN notice", notice_expiration_date=date)],
    )
    result = build(
        tmp_path,
        "public_only",
        Frame(frozenset()),
        (capture(), capture("fc_register", files=files)),
        (),
    )
    card = next(
        row
        for row in result.tables["pub_register_company"]
        if row["source_id"] == "fc_register"
    )
    assert card["notice_expiration_date"] is None
    assert result.manifest["field_absences"] == [
        {
            "source_id": "fc_register",
            "period": "2026-11",
            "use": "current",
            "field": "notice_expiration_date",
            "reason": "published_non_iso_notice_shape",
            "count": 1,
        }
    ]


@pytest.mark.parametrize(
    "date", ["12-ABC-345", "12-Abc-3456", "1-Abc-345", "2026-02-30", "12-abc-345"]
)
def test_register_other_notice_shapes_refuse(date):
    files = inputs("fc_register")
    files["events"] = csv_bytes(
        "events",
        [dict(qfc_number="65432", event="SYN notice", notice_expiration_date=date)],
    )
    with pytest.raises(RegisterError, match=r"^malformed_date$"):
        parse("fc_register", files, Frame(frozenset()))


@pytest.mark.parametrize("field", ["publisher", "dataset"])
def test_register_licence_in_manifest_refuses(tmp_path, field):
    source = capture()
    source = replace(source, receipt=dict(source.receipt, **{field: "SYN 97003"}))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path,
            "public_only",
            Frame(frozenset()),
            (source, capture("fc_register")),
            (),
        )


def test_register_activity_without_code_is_not_proved(tmp_path):
    result = build(
        tmp_path,
        "public_only",
        Frame(frozenset()),
        (capture(), capture("fc_register")),
        (),
    )
    assert result.manifest["activity_check"] == {
        "status": "not_proved",
        "reason": "register_publishes_no_code",
    }


def test_register_activity_mismatch_and_legacy():
    activity = ActivityRow("5610101", "SYN activity", 1, 0)
    classes = {"5610": IsicClass("5610", "SYN class", "")}
    review = ReviewRow(
        activity.code,
        7,
        activity.name_ar,
        "5610",
        "mapped",
        "reviewer_approved",
        "fixture reviewer",
        "2026-11-01",
    )
    assert register_activity_check(activity, classes, review) == {
        "status": "mapped",
        "reason": "reviewer_approved",
    }
    with pytest.raises(RegisterError, match=r"^activity_code_mismatch$"):
        register_activity_check(activity, classes, replace(review, isic_class="5630"))
    legacy = replace(activity, code="561000")
    assert register_activity_check(
        legacy, classes, replace(review, code=legacy.code, code_length=6)
    ) == {"status": "not_mappable_legacy", "reason": "legacy_code_length"}


def test_register_duplicate_number_becomes_distinct_row_cards():
    rows = parse(
        "biz_register",
        inputs(rows=[commerce(), commerce(row_key="c" * 20)]),
        Frame(frozenset()),
    )
    assert {row["registration_number"] for row in rows} == {
        ROW_IDENTITY_FIXTURE,
        "ROW-" + "c" * 20,
    }


def test_register_duplicate_numberless_row_still_refuses():
    with pytest.raises(RegisterError, match=r"^duplicate_registration_key$"):
        parse(
            "biz_register",
            inputs(
                rows=[
                    commerce(registration_number=""),
                    commerce(registration_number="", licence_number="97009"),
                ]
            ),
            Frame(frozenset()),
        )


def test_register_row_namespace_preserves_distinct_companies():
    rows = parse(
        "biz_register",
        inputs(
            rows=[
                commerce(registration_number=""),
                commerce(registration_number="97003", row_key="c" * 20),
            ]
        ),
        Frame(frozenset()),
    )
    assert {row["registration_number"] for row in rows} == {
        ROW_IDENTITY_FIXTURE,
        "97003",
    }


@pytest.mark.parametrize(
    "field,reason",
    [
        ("name_ar", "required_text"),
        ("licence_status", "required_text"),
        ("registration_issue_date", "malformed_date"),
        ("licence_number", "integer_format"),
    ],
)
def test_register_numberless_row_does_not_fill_required_fields(field, reason):
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        parse(
            "biz_register",
            inputs(rows=[commerce(registration_number="", **{field: ""})]),
            Frame(frozenset()),
        )


def test_register_restored_key_leak_refuses():
    """Decision 0119: re-pointed from the released `ROW-` identity (which now
    publishes) to the withheld duplicate number that a row identity replaces."""
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(rows=[commerce(registration_number="")]), frame)
    tables = {"pub_register_company": rows, "pub_register_snapshot": []}
    rows[0]["name_en"] = "SYN " + rows[0]["registration_number"]
    validate_release(tables, frame)
    rows[0]["name_en"] = "SYN 97531"
    validate_release(tables, frame)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(tables, frame, withheld_registrations=frozenset({"97531"}))


@pytest.mark.parametrize(
    "table",
    sorted(
        RELEASE_TABLES
        - {"pub_register_company", "pub_register_snapshot", "register_company_list"}
    ),
)
@pytest.mark.parametrize("token", ["54321", "97003", "97531", "ROW-" + "a" * 20])
def test_register_every_released_table_keeps_identifier_scan(table, token):
    """Decision 0123: only withheld keys refuse in rows with no company key;
    other-company licences and released keys publish."""
    frame = Frame(frozenset())
    rows = parse(
        "biz_register",
        inputs(
            rows=[commerce(), commerce(registration_number="", row_key="a" * 19 + "b")]
        ),
        frame,
    )
    # Use the restored company's actual key, retaining the same valid baseline.
    if token.startswith("ROW-"):
        token = "ROW-" + "a" * 19 + "b"
    tables = {
        "pub_register_company": rows,
        "pub_register_snapshot": [],
        table: [{"value": token}],
    }
    keys = dict(
        licences_by_registration={"54321": frozenset({"97003"})},
        withheld_registrations=frozenset({"97531"}),
    )
    if token != "97531":
        released = validate_release(tables, frame, **keys)
        if token != "97003":
            assert token in released
        return
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(tables, frame, **keys)


@pytest.mark.parametrize(
    "payload",
    [97003, 97003.0, {"97003": None}, {"value": [{"nested": "prefix97003suffix"}]}],
)
def test_register_withheld_nested_and_typed_values_refuse(payload):
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            {
                "pub_register_company": rows,
                "pub_register_snapshot": [],
                "source_registry": [{"value": payload}],
            },
            frame,
            withheld_registrations=frozenset({"97003"}),
        )


@pytest.mark.parametrize("channel", ["manifest", "report"])
def test_register_licence_artefact_scan(channel):
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_artefact({channel: "SYN 97003"}, frozenset({"97003"}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("count", 0),
        ("count", -1),
        ("count", True),
        ("count", "1"),
        ("field", "event"),
        ("reason", "guessed"),
        ("source_id", "biz_register"),
        ("period", []),
        ("use", []),
        ("period", "2026-10"),
        ("use", "snapshot"),
    ],
)
def test_register_absence_metadata_field_refuses(tmp_path, field, value):
    from custodian.tests.test_register_tables import _rewrite_manifest, _stage

    from eii_custodian.publicdata.registers.bundle import BUNDLE, PIN, load_bundle

    frame = Frame(frozenset())
    _stage(tmp_path, tmp_path / "stage", frame)
    baseline = dict(
        source_id="fc_register",
        period="2026-11",
        use="current",
        field="notice_expiration_date",
        reason="published_non_iso_notice_shape",
        count=1,
    )
    _rewrite_manifest(
        tmp_path,
        lambda m: m.__setitem__("field_absences", [dict(baseline, **{field: value})]),
    )
    with pytest.raises(RegisterError, match=r"^register_bundle_absence$"):
        load_bundle(tmp_path / BUNDLE, tmp_path / PIN, frame.cells)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        ["bad"],
        [{}],
        [
            dict(
                source_id="fc_register",
                period="2026-11",
                use="current",
                field="notice_expiration_date",
                reason="published_non_iso_notice_shape",
                count=1,
            )
        ]
        * 2,
    ],
)
def test_register_absence_metadata_structure_refuses(tmp_path, raw):
    from custodian.tests.test_register_tables import _rewrite_manifest, _stage

    from eii_custodian.publicdata.registers.bundle import BUNDLE, PIN, load_bundle

    frame = Frame(frozenset())
    _stage(tmp_path, tmp_path / "stage", frame)
    _rewrite_manifest(tmp_path, lambda m: m.__setitem__("field_absences", raw))
    with pytest.raises(RegisterError, match=r"^register_bundle_absence$"):
        load_bundle(tmp_path / BUNDLE, tmp_path / PIN, frame.cells)


def test_register_activity_metadata_cannot_claim_proved(tmp_path):
    from custodian.tests.test_register_tables import _rewrite_manifest, _stage

    from eii_custodian.publicdata.registers.bundle import BUNDLE, PIN, load_bundle

    frame = Frame(frozenset())
    _stage(tmp_path, tmp_path / "stage", frame)
    _rewrite_manifest(
        tmp_path, lambda m: m["activity_check"].__setitem__("status", "proved")
    )
    with pytest.raises(RegisterError, match=r"^register_bundle_activity$"):
        load_bundle(tmp_path / BUNDLE, tmp_path / PIN, frame.cells)


def test_register_historical_licence_leak_refuses(tmp_path):
    source = capture(files=inputs(rows=[commerce(name_en="SYN 97003")]))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path,
            "public_only",
            Frame(frozenset()),
            (capture(), capture("fc_register")),
            (source,),
        )


def test_register_later_capture_licence_leak_refuses(tmp_path):
    current = capture(files=inputs(rows=[commerce(name_en="SYN 97009")]))
    source = capture(files=inputs(rows=[commerce(licence_number="97009")]))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        build(
            tmp_path,
            "public_only",
            Frame(frozenset()),
            (current, capture("fc_register")),
            (source,),
        )


def test_register_card_restored_key_guard():
    from eii_custodian.publicdata.registers.parse import validate_card

    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    rows[0]["registration_number"] = "row-" + "a" * 20
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        validate_card(rows[0], frame)


def test_register_missing_financial_centre_key_guard():
    from eii_custodian.publicdata.registers.parse import _keyed

    with pytest.raises(RegisterError, match=r"^missing_registration_key$"):
        _keyed([{"qfc_number": None}], "qfc_number")


def test_register_licence_column_in_other_table_refuses():
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    with pytest.raises(RegisterError, match=r"^release_identifier_column$"):
        validate_release(
            {
                "pub_register_company": rows,
                "pub_register_snapshot": [],
                "source_registry": [{"licence_number": "SYN sentinel"}],
            },
            frame,
        )


def register_count_rows():
    """The unchanged 124-row invented control of decision 0124 / L-2141 F1."""
    return [
        commerce(
            row_key=f"{index:020x}",
            registration_number=str(50000 + index),
            licence_number="125",
        )
        for index in range(124)
    ]


def test_register_storage_manifest_exact_count_is_not_scanned(tmp_path):
    # Decision 0124 supersedes 0105 item 5 for exact recomputed counts only.
    result = build(
        tmp_path,
        "public_only",
        Frame(frozenset()),
        (capture(files=inputs(rows=register_count_rows())), capture("fc_register")),
        (),
    )
    company = next(
        t for t in result.manifest["tables"] if t["name"] == "pub_register_company"
    )
    assert company["rows"] == len(result.tables["pub_register_company"]) == 125


def test_register_storage_altered_count_equal_to_key_still_refuses(tmp_path):
    from copy import deepcopy

    from eii_custodian.publicdata.registers.validate import (
        MetadataInputs,
        scan_metadata,
    )

    # Keep F1's current rows. An earlier capture supplies the other key, 126.
    current = (
        capture(files=inputs(rows=register_count_rows())),
        capture("fc_register"),
    )
    snapshots = (capture(files=inputs(rows=[commerce(licence_number="126")])),)
    result = build(tmp_path, "public_only", Frame(frozenset()), current, snapshots)
    context = MetadataInputs(current, snapshots, result.tables)
    keys = frozenset({"125", "126"})
    scan_metadata(result.manifest, keys, "manifest", inputs=context)
    changed = deepcopy(result.manifest)
    company = next(t for t in changed["tables"] if t["name"] == "pub_register_company")
    company["rows"] = 126
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(changed, keys, "manifest", inputs=context)


def test_register_snapshot_restored_key_guard():
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    snapshot = dict(
        registration_number="row-" + "a" * 20,
        period="2026-11",
        source_id="biz_register",
        registered_cell=None,
    )
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        validate_release(
            {"pub_register_company": rows, "pub_register_snapshot": [snapshot]}, frame
        )


def test_register_notice_assembly_retains_capture_absences(tmp_path):
    import json

    from custodian.tests.test_register_tables import _production

    files = inputs("fc_register")
    files["events"] = csv_bytes(
        "events",
        [
            dict(
                qfc_number="65432",
                event="SYN notice",
                notice_expiration_date="12-Abc-345",
            )
        ],
    )
    state = _production(
        tmp_path,
        Frame(frozenset()),
        (capture("fc_register", files=files),),
        fc_files=files,
    )
    state.register_tables()
    record = json.loads((tmp_path / "assembly/register_tables.json").read_bytes())
    absences = record["field_absences"]
    assert {entry["use"] for entry in absences} == {"current", "snapshot"}
    assert len(absences) == 2
    assert all(
        entry["count"] == 1 and entry["reason"] == "published_non_iso_notice_shape"
        for entry in absences
    )
    assert record["activity_check"]["status"] == "not_proved"
