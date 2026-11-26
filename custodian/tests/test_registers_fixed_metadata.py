"""Decision 0124 / L-2139: exact metadata checks, invented inputs only."""

import copy
from dataclasses import replace

import pytest
from custodian.tests.test_registers import capture, commerce, inputs
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers import validate
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.provenance import Frame

FRAME = Frame(frozenset())
COMPANY = "Cedar Lantern Trading WLL"  # Invented, never a real-register input.


@pytest.fixture
def bundle(tmp_path):
    current = (
        capture(files=inputs(rows=[commerce(name_en=COMPANY)])),
        capture("fc_register"),
    )
    built = build(tmp_path, "public_only", FRAME, current, (capture(),))
    context = validate.MetadataInputs(current, (capture(),), built.tables)
    return built, context


def check(body, context, path="manifest", keys=frozenset(), content=frozenset()):
    validate.scan_metadata(body, keys, path, inputs=context, content=content)
    validate.scan_content(body, content, path, inputs=context)


def receipt(manifest):
    return manifest["receipts"][0]["receipt"]


def test_register_m1_control(bundle):
    built, context = bundle
    check(built.manifest, context)
    check(
        {"source_status": "validated", "missing_snapshot_reason": "snapshot_not_kept"},
        context,
        "report",
    )


def test_register_m1_owner_label_absent_from_cards(tmp_path):
    item = capture()
    build(
        tmp_path / "control", "public_only", FRAME, (item, capture("fc_register")), ()
    )
    changed = replace(
        item, receipt={**item.receipt, "publisher": "Publisher " + COMPANY}
    )
    with pytest.raises(RegisterError, match=r"^metadata_fixed_text_mismatch$"):
        build(
            tmp_path / "plant",
            "public_only",
            FRAME,
            (changed, capture("fc_register")),
            (),
        )
    assert not (tmp_path / "plant/current").exists()


def test_register_m1_owner_label_present_in_cards(tmp_path):
    item = capture(files=inputs(rows=[commerce(name_en=COMPANY)]))
    build(
        tmp_path / "control", "public_only", FRAME, (item, capture("fc_register")), ()
    )
    changed = replace(
        item, receipt={**item.receipt, "publisher": "Publisher " + COMPANY}
    )
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        build(
            tmp_path / "plant",
            "public_only",
            FRAME,
            (changed, capture("fc_register")),
            (),
        )


@pytest.mark.parametrize(
    "in_cards,reason",
    [(False, "metadata_key_not_schema"), (True, "register_content_egress")],
)
def test_register_m1_owner_column_key(bundle, in_cards, reason):
    built, context = bundle
    # Inspect column-name slots only; actual card content belongs in the tables.
    body = {
        table: [dict.fromkeys(row) for row in rows]
        for table, rows in built.tables.items()
    }
    names = frozenset(
        row["name_en"] for row in built.tables["pub_register_company"] if row["name_en"]
    )
    content = names if in_cards else frozenset()
    check(body, context, "released", content=content)
    row = body["pub_register_company"][0]
    row[COMPANY] = row.pop("name_en")
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        check(body, context, "released", content=content)


@pytest.mark.parametrize("role", ["establishments", "companies", "geocoded", "events"])
def test_register_m1_owner_file_count(bundle, role):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    side = next(e["receipt"] for e in body["receipts"] if role in e["receipt"]["files"])
    side["files"][role]["bytes"] += 1
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(body, context)


def test_register_m1_owner_table_count(bundle):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    body["tables"][0]["rows"] += 1
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(body, context)


def test_register_m1_owner_eight_digit_count(bundle):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    receipt(body)["files"]["establishments"]["bytes"] = int("8" * 8)
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        check(body, context)


@pytest.mark.parametrize("field", ["publisher", "dataset", "basis_note"])
@pytest.mark.parametrize("source", ["biz_register", "fc_register"])
def test_register_m1_each_approved_label_is_exact(bundle, source, field):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    side = next(
        e["receipt"] for e in body["receipts"] if e["receipt"]["source_id"] == source
    )
    side[field] += " altered"
    with pytest.raises(RegisterError, match=r"^metadata_fixed_text_mismatch$"):
        check(body, context)


@pytest.mark.parametrize(
    "path,field",
    [
        ("report", "source_status"),
        ("report", "missing_snapshot_reason"),
        ("absence", "field"),
        ("absence", "reason"),
    ],
)
def test_register_m1_code_labels_are_exact(bundle, path, field):
    _, context = bundle
    if path == "report":
        body = {
            "source_status": "validated",
            "missing_snapshot_reason": "snapshot_not_kept",
        }
        target = body
    else:
        body = {
            "field_absences": [{"field": "event", "reason": "published_event_conflict"}]
        }
        target = body["field_absences"][0]
    root = "report" if path == "report" else "manifest"
    check(body, context, root)
    target[field] += " altered"
    with pytest.raises(RegisterError, match=r"^metadata_fixed_text_mismatch$"):
        check(body, context, root)


@pytest.mark.parametrize(
    "value,reason",
    [(COMPANY, "register_content_egress"), ("SYN 97003", "registration_egress")],
)
def test_register_m1_unlisted_field_keeps_scans(bundle, value, reason):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context, keys=frozenset({"97003"}), content=frozenset({COMPANY}))
    body["extra"] = value
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        check(body, context, keys=frozenset({"97003"}), content=frozenset({COMPANY}))


def test_register_m1_terms_are_exempt_only(bundle):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    receipt(body)["terms_words"] = "Supplied prohibitive terms remain a record"
    check(body, context)
    receipt(body)["terms_words"] = COMPANY
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        check(body, context, content=frozenset({COMPANY}))


def test_register_m1_unknown_source_has_no_approved_wording(bundle):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    receipt(body)["source_id"] = "unknown"
    with pytest.raises(RegisterError, match=r"^metadata_fixed_text_mismatch$"):
        check(body, context)


def test_register_m1_counts_do_not_approve_themselves(bundle):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    # Only actual file bytes change: the old manifest count must now refuse.
    item = context.current[0]
    changed = replace(
        item, files={"establishments": item.files["establishments"] + b"\n"}
    )
    changed_context = replace(context, current=(changed, context.current[1]))
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(body, changed_context)


def test_register_m1_schema_keys_only_exempt_keys(bundle):
    built, context = bundle
    body = copy.deepcopy(built.tables)
    # A card substring equal to a schema key must not collide with that key.
    validate.scan_content(body, frozenset({"name_en"}), "released", inputs=context)
    body["pub_register_company"][0]["name_en"] = "name_en"
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        validate.scan_content(body, frozenset({"name_en"}), "released", inputs=context)


def test_register_m1_schema_key_in_other_mapping_is_scanned(bundle):
    _, context = bundle
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        check({"other": {"name_en": None}}, context, content=frozenset({"name_en"}))


@given(
    st.integers(min_value=0, max_value=100000), st.integers(min_value=1, max_value=100)
)
def test_register_m1_row_count_equality_property(count, delta):
    # Quantities count rows, not bytes; no declared count is its own oracle.
    rows = [{}] * count
    context = validate.MetadataInputs((), (), {"pub_register_company": rows})
    body = {"tables": [{"name": "pub_register_company", "rows": count}]}
    check(body, context)
    body["tables"][0]["rows"] = count + delta
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(body, context)


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=30))
def test_register_m1_fixed_text_has_no_suffix_channel(suffix):
    context = validate.MetadataInputs((), (), {})
    body = {"source_status": "validated"}
    check(body, context, "report")
    body["source_status"] += suffix
    with pytest.raises(RegisterError, match=r"^metadata_fixed_text_mismatch$"):
        check(body, context, "report")


@pytest.mark.parametrize("field", ["publisher", "dataset", "basis_note"])
def test_register_m1_changed_label_keeps_licence_scan(bundle, field):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context, keys=frozenset({"97003"}))
    receipt(body)[field] = "SYN 97003"
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        check(body, context, keys=frozenset({"97003"}))


@pytest.mark.parametrize("role", ["establishments", "companies", "geocoded", "events"])
@pytest.mark.parametrize("value", [True, 1.0, -1, "1", [], {}])
def test_register_m1_file_count_requires_integer(bundle, role, value):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    side = next(e["receipt"] for e in body["receipts"] if role in e["receipt"]["files"])
    side["files"][role]["bytes"] = value
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(body, context)


@pytest.mark.parametrize("value", [True, 2.0, -1, "2", [], {}])
def test_register_m1_row_count_keeps_old_format_reason(bundle, value):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    body["tables"][0]["rows"] = value
    with pytest.raises(RegisterError, match=r"^typed_field_format$"):
        check(body, context)


def test_register_m1_actual_table_change_invalidates_count(bundle):
    built, context = bundle
    body = copy.deepcopy(built.manifest)
    check(body, context)
    changed = dict(context.tables)
    changed["pub_register_company"] = [*changed["pub_register_company"], {}]
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(body, replace(context, tables=changed))


def test_register_m1_exact_large_file_count_bypasses_digit_scan():
    # A real byte length, independent of the receipt, has eight digits.
    body = b"x" * 10_000_000
    item = capture(files={"establishments": body})
    context = validate.MetadataInputs((item,), (), {})
    manifest = {"receipts": [{"use": "current", "receipt": item.receipt}]}
    check(manifest, context, keys=frozenset({str(len(body))}))
    changed = copy.deepcopy(manifest)
    receipt(changed)["files"]["establishments"]["bytes"] += 1
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        check(changed, context, keys=frozenset({str(len(body))}))


def test_register_m1_unlisted_mapping_key_keeps_scans(bundle):
    _, context = bundle
    check({"other": {"plain": None}}, context, content=frozenset({COMPANY}))
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        check({"other": {COMPANY: None}}, context, content=frozenset({COMPANY}))


@given(st.binary(max_size=5000), st.integers(min_value=1, max_value=100))
def test_register_m1_file_count_equality_property(body, delta):
    item = capture(files={"establishments": body})
    context = validate.MetadataInputs((item,), (), {})
    manifest = {"receipts": [{"use": "current", "receipt": item.receipt}]}
    check(manifest, context)
    changed = copy.deepcopy(manifest)
    receipt(changed)["files"]["establishments"]["bytes"] += delta
    with pytest.raises(RegisterError, match=r"^metadata_count_mismatch$"):
        check(changed, context)


@pytest.mark.parametrize("value", [None, True, 1, [], {}, b"validated"])
def test_register_m1_fixed_text_rejects_non_string(bundle, value):
    _, context = bundle
    check({"source_status": "validated"}, context, "report")
    with pytest.raises(RegisterError, match=r"^metadata_fixed_text_mismatch$"):
        check({"source_status": value}, context, "report")


@pytest.mark.parametrize(
    "name,reason",
    [("97003", "registration_egress"), ("8" * 8, "identifier_digit_run")],
)
def test_register_m1_unknown_schema_key_scanned_before_mismatch(bundle, name, reason):
    _, context = bundle
    check(
        {"name_en": None},
        context,
        "released.pub_register_company",
        keys=frozenset({"97003"}),
    )
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        check(
            {name: None},
            context,
            "released.pub_register_company",
            keys=frozenset({"97003"}),
        )


@given(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ ", min_size=1, max_size=40))
def test_register_m1_schema_key_equality_property(name):
    # Every generated label is outside the lowercase schema-key vocabulary.
    context = validate.MetadataInputs((), (), {})
    check({"name_en": None}, context, "released.pub_register_company")
    with pytest.raises(RegisterError, match=r"^metadata_key_not_schema$"):
        check({name: None}, context, "released.pub_register_company")


@pytest.mark.parametrize("wrapper", [list, tuple])
@pytest.mark.parametrize("field", ["source_status", "terms_words"])
def test_register_m1_wrapped_approved_text_keeps_full_scan(bundle, wrapper, field):
    _, context = bundle
    if field == "source_status":
        text = "validated"
        root = "report"
        body = {field: text}
        target = body
    else:
        text = "terms to be read"
        root = "manifest"
        body = {"receipts": [{"receipt": {field: text}}]}
        target = body["receipts"][0]["receipt"]
    content = frozenset({text})
    check(body, context, root, content=content)
    target[field] = wrapper([text])
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        check(body, context, root, content=content)
