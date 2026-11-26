"""Decision 0105: the closed typed-column list of the register token scan."""

import copy
import json
import re
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_registers import capture, commerce, csv_bytes, fc, inputs
from hypothesis import given
from hypothesis import strategies as st

import h3
from eii_custodian.publicdata.registers import contracts, validate
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.bundle import BUNDLE, PIN, load_bundle
from eii_custodian.publicdata.registers.contracts import (
    CARD_COLUMNS,
    REGISTRATION,
    SCHEMAS,
    RegisterError,
)
from eii_custodian.publicdata.registers.parse import parse
from eii_custodian.publicdata.registers.provenance import Frame, digest
from eii_custodian.publicdata.registers.validate import scan_metadata, validate_release

FRAME = Frame(frozenset())
DECISION = (
    repository_root(Path(__file__))
    / "docs/decisions/0105-register-scan-typed-columns.md"
)
# Free-text card fields of the default row hold digits; these hold none, so a
# case isolates the one typed column it names.
PLAIN = dict(building_number="SYN building")
# The free-text (unlisted string) card columns of each source's rows.
FREE_TEXT = {
    "biz_register": [
        name
        for name, kind in SCHEMAS["establishments"].items()
        if name in CARD_COLUMNS and kind.startswith("text")
    ],
    "fc_register": [
        "name_en",
        "name_ar",
        "registered_address",
        "licence_status",
        "event",
    ],
}


def _build(tmp_path, rows, *, fc_files=None, kept=False, **receipt):
    current = capture(files=inputs(rows=rows))
    if receipt:
        current = replace(current, receipt=dict(current.receipt, **receipt))
    centre = capture("fc_register", files=fc_files)
    snapshots = (current, centre) if kept else ()
    return build(tmp_path, "public_only", FRAME, (current, centre), snapshots)


def _cards(source="biz_register", **row):
    if source == "biz_register":
        return parse(source, inputs(rows=[commerce(**PLAIN, **row)]), FRAME)
    return parse(source, inputs(source), FRAME)


def _release(cards, *, licences=(), withheld=()):
    validate_release(
        {"pub_register_company": cards, "pub_register_snapshot": []},
        FRAME,
        licences_by_registration={
            card["registration_number"]: frozenset(licences) for card in cards
        },
        withheld_registrations=frozenset(withheld),
    )


def _notice_files():
    files = inputs("fc_register")
    files["events"] = csv_bytes(
        "events",
        [
            dict(
                qfc_number="65432",
                event="SYN notice",
                notice_expiration_date="2026-12-12",
            )
        ],
    )
    return files


def _drop_from_list(monkeypatch, field):
    assert field in contracts.TYPED_FIELDS
    narrowed = {k: v for k, v in contracts.TYPED_FIELDS.items() if k != field}
    monkeypatch.setattr(validate, "TYPED_FIELDS", narrowed)


def _single_input_pair(call, good, bad, reason):
    """Ruling L-1409: the passing control `call(*good)` and the refused case
    `call(*bad)` differ in exactly one argument (by value or by type)."""
    changed = [a != b or type(a) is not type(b) for a, b in zip(good, bad, strict=True)]
    assert changed.count(True) == 1, "a negative case changes one input"
    call(*good)
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        call(*bad)


def _admitted(number):
    """Independent oracle of owner condition 1: 1-2 digits, or 19xx / 20xx."""
    return len(number) <= 2 or (len(number) == 4 and number[:2] in {"19", "20"})


# --- The closed list -------------------------------------------------------


def test_register_typed_list_equals_decision_0105():
    rows = re.findall(
        r"^ *\| `([a-z_.]+)` \| `([a-z_]+)` \|", DECISION.read_text(), re.MULTILINE
    )
    assert len(rows) == len({name for name, _ in rows}) == 28
    assert dict(rows) == contracts.TYPED_FIELDS


def test_register_typed_formats_are_the_declarations_checked():
    checked = {
        **SCHEMAS["establishments"],
        "notice_expiration_date": SCHEMAS["events"]["notice_expiration_date"],
    }
    for field, kind in contracts.TYPED_FIELDS.items():
        artefact, _, name = field.partition(".")
        if artefact == "pub_register_company":
            assert name in CARD_COLUMNS
            assert checked[name].removesuffix("?") == kind
        elif artefact == "register_company_list":
            assert (name, kind) in {("employee_count", "count"), ("period", "month")}
        elif artefact == "pub_register_snapshot":
            assert (name, kind) == ("period", "month")
        elif artefact == "report":
            assert (name, kind) == ("version", "report_version")
        else:
            assert artefact == "manifest" and kind in MANIFEST_FORMATS
    for name in ("lon", "lat"):
        kind = contracts.TYPED_FIELDS["pub_register_company." + name]
        assert SCHEMAS["geocoded"][name].removesuffix("?") == kind


# --- Short and year-shaped tokens are admitted in a listed column ----------


@pytest.mark.parametrize("kind", ["public_only", "protected"])
def test_register_short_registration_with_its_date_builds(tmp_path, kind):
    row = commerce(registration_number="12", registration_issue_date="2026-11-12")
    source = capture(files=inputs(rows=[row]))
    result = build(tmp_path, kind, FRAME, (source, capture("fc_register")), ())
    card = result.tables["pub_register_company"][0]
    assert card["registration_number"] == "12"
    assert card["registration_issue_date"] == "2026-11-12"


def test_register_short_licence_with_its_latitude_builds(tmp_path):
    result = _build(tmp_path, [commerce(licence_number="25", lat="2.25")])
    assert result.tables["pub_register_company"][0]["lat"] == 2.25


@pytest.mark.parametrize(
    "row",
    [
        dict(registration_number="3", zone="3", **PLAIN),
        dict(licence_number="3", street_number="3", block_en="3", **PLAIN),
        dict(registration_number="05", block_ar="05", **PLAIN),
        dict(registration_number="31", licence_expiry_date="2027-12-31"),
        dict(licence_number="2027", registration_expiry_date="2027-11-03"),
        dict(registration_number="1999", licence_issue_date="1999-01-05"),
        dict(registration_number="2020", tax_classification_year="2020"),
        dict(licence_number="7", tax_registered="yes", block_ar="7", **PLAIN),
    ],
    ids=["zone", "street_block", "lead_zero", "day", "year20", "year19", "tax", "yes"],
)
def test_register_short_identifier_against_typed_card_value_builds(tmp_path, row):
    _build(tmp_path, [commerce(**row)])


def test_register_financial_centre_notice_date_builds(tmp_path):
    files = _notice_files()
    _build(tmp_path, [commerce(registration_number="12")], fc_files=files)


def test_register_short_key_bundle_loads(tmp_path):
    row = commerce(registration_number="12", registration_issue_date="2026-11-12")
    _build(tmp_path / "stage", [row])
    shutil.copytree(tmp_path / "stage/current", tmp_path / BUNDLE)
    body = (tmp_path / BUNDLE / "manifest.json").read_bytes()
    (tmp_path / PIN).write_text(
        json.dumps(dict(version="register_bundle_pin_v1", manifest_sha256=digest(body)))
    )
    bundle = load_bundle(tmp_path / BUNDLE, tmp_path / PIN, FRAME.cells)
    assert bundle.tables["pub_register_company"][0]["registration_number"] == "12"


# --- Owner condition 3, plant 1: free text keeps the full scan --------------


@pytest.mark.parametrize("column", FREE_TEXT["biz_register"])
@pytest.mark.parametrize(
    "licences,withheld,value",
    [(("25",), (), "SYN 25"), ((), ("12",), "SYN 12")],
    ids=["licence", "withheld"],
)
def test_register_short_number_in_free_text_refuses(column, licences, withheld, value):
    cards = _cards()
    _release(cards, licences=licences, withheld=withheld)
    cards[0][column] = value
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(cards, licences=licences, withheld=withheld)


@pytest.mark.parametrize("column", FREE_TEXT["fc_register"])
@pytest.mark.parametrize(
    "licences,withheld,value",
    [(("25",), (), "SYN 25"), ((), ("12",), "SYN 12")],
    ids=["licence", "withheld"],
)
def test_register_short_number_in_centre_free_text_refuses(
    column, licences, withheld, value
):
    cards = _cards("fc_register")
    _release(cards, licences=licences, withheld=withheld)
    cards[0][column] = value
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(cards, licences=licences, withheld=withheld)


def _withheld_rows(key, **row):
    """Two commerce rows publishing `key` (withheld at intake) and a third
    row, keyed 54322, holding `row`."""
    return [
        commerce(**PLAIN, registration_number=key),
        commerce(**PLAIN, row_key="c" * 20, registration_number=key),
        commerce(**PLAIN, row_key="d" * 20, registration_number="54322", **row),
    ]


@pytest.mark.parametrize(
    "rows",
    [
        [commerce(licence_number="25", name_en="SYN 25")],
        [commerce(licence_number="25", building_number="25")],
        # Decision 0119: re-pointed from a released key to a withheld one.
        _withheld_rows("12", name_ar="SYN 12"),
        _withheld_rows("12", district_en="SYN 12"),
    ],
    ids=["licence_name", "licence_building", "withheld_name", "withheld_text"],
)
def test_register_identifier_in_free_text_build_refuses(tmp_path, rows):
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path, rows)
    assert not (tmp_path / "current").exists()


@pytest.mark.parametrize(
    "row",
    [
        dict(registration_number="12", name_ar="SYN 12"),
        dict(registration_number="12", district_en="SYN 12", **PLAIN),
    ],
    ids=["key_name", "key_text"],
)
def test_register_released_key_in_free_text_build_publishes(tmp_path, row):
    """Decision 0119: a released registration in free text is published."""
    _build(tmp_path, [commerce(**row)])
    assert (tmp_path / "current" / "manifest.json").exists()


def test_register_withheld_number_in_free_text_build_refuses(tmp_path):
    rows = [
        commerce(registration_number="12"),
        commerce(row_key="c" * 20, registration_number="12"),
        commerce(row_key="d" * 20, registration_number="54322", name_en="SYN 12"),
    ]
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path, rows)


def test_register_other_company_licence_in_financial_centre_address_builds(tmp_path):
    """Decision 0123: the commerce licence is not the centre's own licence."""
    files = inputs("fc_register", rows=[fc(registered_address="SYN Office 12")])
    row = commerce(registration_number="12")
    _build(tmp_path / "pass", [row], fc_files=files)
    _build(tmp_path / "other", [{**row, "licence_number": "12"}], fc_files=files)


@pytest.mark.parametrize(
    "column,value", [("zone", "25"), ("lat", 2.25), ("registration_issue_date", "25")]
)
def test_register_typed_name_in_another_table_refuses(column, value):
    cards = _cards()
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            {
                "pub_register_company": cards,
                "pub_register_snapshot": [],
                "source_registry": [{column: value}],
            },
            FRAME,
            withheld_registrations=frozenset({"25"}),
        )


# --- Owner condition 3, plant 2: three or more digits refuse in every column


LONG_TYPED = [
    ("125", "zone", "125"),
    ("007", "zone", "007"),
    ("125", "street_number", "125"),
    ("4521", "block_en", "4521"),
    ("125436", "block_ar", "125436"),
    ("1899", "registration_issue_date", "1899-01-05"),
    ("2100", "registration_expiry_date", "2100-01-05"),
    ("1899", "licence_issue_date", "1899-01-05"),
    ("3000", "licence_expiry_date", "3000-01-05"),
    ("2126", "tax_classification_year", "2126"),
]


@pytest.mark.parametrize("number,column,value", LONG_TYPED)
@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_long_number_in_typed_column_refuses(role, number, column, value):
    cards = _cards(registration_number="54321", **{column: value})
    _release(cards)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(
            cards,
            licences=(number,) if role == "licence" else (),
            withheld=(number,) if role == "withheld" else (),
        )


@pytest.mark.parametrize("number,column,value", LONG_TYPED)
def test_register_long_released_number_in_typed_column_builds(number, column, value):
    """Decision 0119: the former `registration` role of the test above; a
    released registration equal to a typed value is published."""
    _release(_cards(registration_number=number, **{column: value}))


@pytest.mark.parametrize("column,value", [("lon", "1.125"), ("lat", "2.1899")])
@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_long_number_in_typed_coordinate_refuses(role, column, value):
    number = value.split(".")[1]
    cards = _cards(**{column: value})
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(
            cards,
            licences=(number,) if role == "licence" else (),
            withheld=(number,) if role == "withheld" else (),
        )


def test_register_long_licence_build_refuses(tmp_path):
    """Decision 0119: re-pointed from the released key 125 (which now builds)
    to the licence 125; the pair differs only in the licence."""
    row = commerce(registration_number="125", zone="125", **PLAIN)
    _build(tmp_path / "pass", [row])
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path / "refuse", [{**row, "licence_number": "125"}])
    assert not (tmp_path / "refuse" / "current").exists()


@pytest.mark.parametrize("column", ["zone", "street_number", "block_en", "block_ar"])
def test_register_typed_integer_keeps_digit_run_guard(tmp_path, column):
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        _build(tmp_path, [commerce(**{column: "1234" + "5678"})])


# --- Owner condition 3, plant 3: a value failing its format refuses ---------


@pytest.mark.parametrize(
    "source,column,value,reason",
    [
        ("biz_register", "registration_issue_date", "2026-11-1x", "malformed_date"),
        ("biz_register", "registration_expiry_date", "12", "malformed_date"),
        ("biz_register", "licence_issue_date", "2026-13-01", "malformed_date"),
        ("biz_register", "licence_expiry_date", "2026-02-30", "malformed_date"),
        ("fc_register", "notice_expiration_date", "12-Dec-2026", "malformed_date"),
        ("biz_register", "zone", "3x", "integer_format"),
        ("biz_register", "street_number", "-3", "integer_format"),
        ("biz_register", "block_en", "3 12", "integer_format"),
        ("biz_register", "block_ar", "", "integer_format"),
        ("biz_register", "lon", "1.25", "release_type"),
        ("biz_register", "lat", 95.0, "coordinate_format"),
        ("fc_register", "lon", 12, "release_type"),
        ("biz_register", "tax_classification_year", "20201", "integer_format"),
        ("biz_register", "tax_registered", "12", "tax_registered_format"),
    ],
)
def test_register_typed_value_outside_format_refuses(source, column, value, reason):
    cards = _cards(source)
    _release(cards, licences=("12",))
    cards[0][column] = value
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        _release(cards, licences=("12",))


# --- Owner condition 3, plant 4: a column missing from the list is free text


@pytest.mark.parametrize(
    "column,row,licence",
    [
        ("registration_issue_date", dict(registration_issue_date="2026-11-12"), "12"),
        ("registration_expiry_date", dict(registration_expiry_date="2027-11-12"), "12"),
        ("licence_issue_date", dict(licence_issue_date="2026-11-12"), "12"),
        ("licence_expiry_date", dict(licence_expiry_date="2027-11-12"), "12"),
        ("zone", dict(zone="12"), "12"),
        ("street_number", dict(street_number="12"), "12"),
        ("block_en", dict(block_en="12"), "12"),
        ("block_ar", dict(block_ar="12"), "12"),
        ("lon", dict(lon="1.12"), "12"),
        ("lat", dict(lat="2.12"), "12"),
        ("capital_qar", dict(capital_qar="12"), "12"),
        ("tax_classification_year", dict(tax_classification_year="2020"), "2020"),
    ],
)
def test_register_column_missing_from_list_is_free_text(
    monkeypatch, column, row, licence
):
    cards = _cards(**row)
    _release(cards, licences=(licence,))
    _drop_from_list(monkeypatch, "pub_register_company." + column)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(cards, licences=(licence,))


def test_register_centre_notice_missing_from_list_is_free_text(monkeypatch):
    cards = parse("fc_register", _notice_files(), FRAME)
    _release(cards, licences=("12",))
    _drop_from_list(monkeypatch, "pub_register_company.notice_expiration_date")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(cards, licences=("12",))


# --- The owner's a2: listed manifest fields (decision 0105 item 5) ---------

FIXED = {"manifest_version", "receipt_version", "report_version"}
MANIFEST_FORMATS = {"timestamp", "date_or_pending", "month", "count", *FIXED}
# Per format: a valid value, a short key equal to one of its tokens, a value
# failing the format, and a valid value holding the long token 2126 or 125. A
# fixed text (the owner's a3) has one valid value and so no long sample.
SAMPLES = {
    "timestamp": ("2026-11-23T00:00:00Z", "23", "2026-11-23", "2126-11-23T00:00:00Z"),
    "date_or_pending": ("2026-11-23", "23", "2026-11-31", "2126-11-23"),
    "month": ("2026-07", "07", "2026-13", "2126-07"),
    "count": (37, "37", -1, 125),
    "manifest_version": ("v2", "2", "v3", None),
    "receipt_version": ("register_input_v1", "1", "register_input_v2", None),
    "report_version": ("v2", "2", "v3", None),
}
MANIFEST_FIELDS = sorted(
    field for field in contracts.TYPED_FIELDS if field.startswith("manifest.")
)
# The owner's a3 and the advisor's note of 2026-11-23 (report.version): each
# version field and its one fixed text, written out here independently of
# `contracts`.
VERSION_TEXTS = {
    "manifest.receipts.receipt.version": "register_input_v1",
    "manifest.version": "v2",
    "report.version": "v2",
}
VERSION_FIELDS = sorted(VERSION_TEXTS)
PERIOD_FIELDS = ["pub_register_snapshot.period", "register_company_list.period"]


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    """A published manifest holding every listed manifest field."""
    files = inputs("fc_register")
    notice = dict(qfc_number="65432", event="SYN", notice_expiration_date="12-Dec-202")
    files["events"] = csv_bytes("events", [notice])
    current = capture(files=inputs(rows=[commerce()]))
    current = replace(
        current, receipt=dict(current.receipt, terms_read_on="2026-11-19")
    )
    centre = capture("fc_register", files=files)
    built = build(
        tmp_path_factory.mktemp("manifest"),
        "public_only",
        FRAME,
        (current, centre),
        (capture(), centre),
    )
    return built.manifest


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    """The published build report, as `build.py` writes it."""
    output = tmp_path_factory.mktemp("report")
    _build(output, [commerce(**PLAIN)], kept=True)
    return json.loads((output / "current" / "build_report.json").read_bytes())


def _artefact(manifest, report, field, value):
    """The artefact a listed metadata field belongs to, with the field set."""
    name = field.partition(".")[0]
    return _with(manifest if name == "manifest" else report, field, value, whole=True)


def _set(manifest, field, value, whole):
    """Set the first occurrence of a listed manifest field (or its first month)."""
    *parents, last = field.split(".")[1:]
    node = manifest
    for name in parents:
        node = node[name]
        node = node[0] if isinstance(node, list) else node
    if isinstance(node[last], list) and not whole:
        node[last][0] = value
    else:
        node[last] = value


def _with(manifest, field, value, *, whole=False):
    body = copy.deepcopy(manifest)
    _set(body, field, value, whole)
    return body


def test_register_manifest_fixture_holds_every_listed_field(manifest):
    assert len(MANIFEST_FIELDS) == 10
    for field in MANIFEST_FIELDS:
        _with(manifest, field, "probe")  # raises KeyError or IndexError if absent
    scan_metadata(manifest, frozenset({"54321", "65432"}), "manifest")


@pytest.mark.parametrize("field", MANIFEST_FIELDS)
def test_register_manifest_typed_field_admits_short_key(manifest, field):
    good, short, _, _ = SAMPLES[contracts.TYPED_FIELDS[field]]
    scan_metadata(_with(manifest, field, good), frozenset({short}), "manifest")


@pytest.mark.parametrize("field", MANIFEST_FIELDS)
def test_register_manifest_typed_value_outside_format_refuses(manifest, field):
    good, _, bad, _ = SAMPLES[contracts.TYPED_FIELDS[field]]
    scan_metadata(_with(manifest, field, good), frozenset(), "manifest")
    with pytest.raises(RegisterError, match=r"^typed_field_format$"):
        scan_metadata(_with(manifest, field, bad), frozenset(), "manifest")


@pytest.mark.parametrize("field", MANIFEST_FIELDS)
@pytest.mark.parametrize(
    "bad", [None, True, b"2026", ["SYN"], {"k": "2026-11"}, "2026-11-23T00:00:00"]
)
def test_register_manifest_typed_value_of_wrong_shape_refuses(manifest, field, bad):
    with pytest.raises(RegisterError, match=r"^typed_field_format$"):
        scan_metadata(_with(manifest, field, bad), frozenset(), "manifest")


# --- Round 6: every typed field's shape is checked before any traversal ----

# One valid value per format; `capital_qar` is a stored integer (decision 0105).
VALID = {
    "date": "2026-11-12",
    "integer": "3",
    "longitude": 1.25,
    "latitude": 2.25,
    "year": "2020",
    "yes_no": "yes",
    **{kind: sample[0] for kind, sample in SAMPLES.items()},
}


# A stored integer capital, and a snapshot month no earlier than the first kept.
GOOD = {"pub_register_company.capital_qar": 12, PERIOD_FIELDS[0]: "2026-11"}


def _shape_reason(field):
    """A manifest field refuses `typed_field_format`; a release column refuses
    with decision 0105 item 1's written reason for a value of another type."""
    if field.startswith(("manifest.", "report.")):
        return "typed_field_format"
    if field in PERIOD_FIELDS:
        return "snapshot_month"
    if field.startswith("register_company_list."):
        return "release_count"
    return "release_type"


def typed_shape_cases():
    """Every typed field x each shape; the reason is None only where the value
    is the field's declared shape holding valid elements."""
    for field, kind in sorted(contracts.TYPED_FIELDS.items()):
        good = GOOD.get(field, VALID[kind])
        sequence = field in contracts.TYPED_SEQUENCES
        shapes = {
            "empty_list": ([], sequence),
            "empty_tuple": ((), sequence),
            "list": ([good], sequence),
            "tuple": ((good,), sequence),
            "nested_list": ([[good]], False),
            "nested_tuple": (((good,),), False),
            "mapping": ({"k": good}, False),
            "true": (True, False),
            "float_of_integer": (2.0, kind in {"longitude", "latitude"}),
            "scalar": (good, not sequence),
        }
        for name, (value, admitted) in shapes.items():
            reason = None if admitted else _shape_reason(field)
            yield pytest.param(field, value, reason, id=f"{field}-{name}")


def _apply_typed(manifest, report, field, value):
    artefact, _, column = field.partition(".")
    if artefact in ("manifest", "report"):
        body = _artefact(manifest, report, field, value)
        scan_metadata(body, frozenset(), artefact)
    elif field in PERIOD_FIELDS:
        validate_release(_periods(field, value), FRAME)
    elif artefact == "register_company_list":
        validate_release(_listed(value), FRAME)
    else:
        source = "biz_register"
        if column == "notice_expiration_date":
            source = "fc_register"
        cards = _cards(source)
        cards[0][column] = value
        _release(cards)


def test_register_typed_sequences_are_the_coverage_lists(manifest):
    coverage = {
        f"manifest.snapshot_coverage.{name}" for name in manifest["snapshot_coverage"]
    }
    assert contracts.TYPED_SEQUENCES == coverage
    assert contracts.TYPED_SEQUENCES <= contracts.TYPED_FIELDS.keys()


@pytest.mark.parametrize("field,value,reason", list(typed_shape_cases()))
def test_register_typed_shape_cases(manifest, report, field, value, reason):
    if reason is None:
        _apply_typed(manifest, report, field, value)
    else:
        with pytest.raises(RegisterError, match="^" + reason + "$"):
            _apply_typed(manifest, report, field, value)


@pytest.mark.parametrize("rows", [[37], (37,), [], (), [[37]]])
def test_register_manifest_count_in_container_refuses(rows):
    """The review's trace: a valid count wrapped in a list is no count."""
    scan_metadata({"tables": [{"rows": 37}]}, frozenset({"37"}), "manifest")
    with pytest.raises(RegisterError, match=r"^typed_field_format$"):
        scan_metadata({"tables": [{"rows": rows}]}, frozenset({"37"}), "manifest")


_MONTH = re.compile(r"(?!0000)[0-9]{4}-(?:0[1-9]|1[0-2])")
_SHAPES = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(-5, 3000)
    | st.floats(allow_nan=False)
    | st.text(max_size=8)
    | st.sampled_from(["2026-11", "2026-07", "pending", "2026-11-23T00:00:00Z"]),
    lambda inner: (
        st.lists(inner, max_size=3)
        | st.lists(inner, max_size=3).map(tuple)
        | st.dictionaries(st.text(max_size=3), inner, max_size=2)
    ),
    max_leaves=6,
)


@given(st.sampled_from(MANIFEST_FIELDS), _SHAPES)
def test_register_manifest_typed_shape_property(field, value):
    """Independent oracle: a coverage field admits exactly a list or tuple of
    real months; any other listed field refuses every non-scalar value."""
    if field not in contracts.TYPED_SEQUENCES and type(value) in (str, int):
        return  # one scalar: its format is checked by the tests above
    admitted = (
        field in contracts.TYPED_SEQUENCES
        and isinstance(value, list | tuple)
        and all(type(item) is str and _MONTH.fullmatch(item) for item in value)
    )
    body = value
    for name in reversed(field.split(".")[1:]):
        body = {name: body}
    if admitted:
        scan_metadata(body, frozenset(), "manifest")
    else:
        with pytest.raises(RegisterError, match=r"^typed_field_format$"):
            scan_metadata(body, frozenset(), "manifest")


@pytest.mark.parametrize(
    "field", [f for f in MANIFEST_FIELDS if contracts.TYPED_FIELDS[f] not in FIXED]
)
def test_register_manifest_long_key_in_typed_field_refuses(manifest, field):
    _, _, _, long = SAMPLES[contracts.TYPED_FIELDS[field]]
    key = "125" if contracts.TYPED_FIELDS[field] == "count" else "2126"
    body = _with(manifest, field, long)
    scan_metadata(body, frozenset({"54321"}), "manifest")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(body, frozenset({key}), "manifest")


@pytest.mark.parametrize("field", MANIFEST_FIELDS)
def test_register_manifest_field_missing_from_list_is_free_text(
    manifest, monkeypatch, field
):
    good, short, _, _ = SAMPLES[contracts.TYPED_FIELDS[field]]
    body = _with(manifest, field, good)
    scan_metadata(body, frozenset({short}), "manifest")
    _drop_from_list(monkeypatch, field)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(body, frozenset({short}), "manifest")


@pytest.mark.parametrize(
    "path,value",
    [
        (("receipts", 0, "receipt", "files", "establishments", "bytes"), 37),
        (("receipts", 0, "receipt", "basis_note"), "SYN 37"),
        (("receipts", 0, "receipt", "licence_id"), "SYN-37"),
        (("receipts", 0, "use"), "37"),
        (("field_absences", 0, "reason"), "SYN 37"),
        (("release_kind",), "37"),
        (("period",), "2026-37"),
        (("snapshot_coverage", "37"), []),
    ],
    ids=lambda item: ".".join(map(str, item)) if isinstance(item, tuple) else None,
)
def test_register_unlisted_manifest_field_short_match_refuses(manifest, path, value):
    body = copy.deepcopy(manifest)
    node = body
    for name in path[:-1]:
        node = node[name]
    scan_metadata(body, frozenset({"37"}), "manifest")
    node[path[-1]] = value
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(body, frozenset({"37"}), "manifest")


@pytest.mark.parametrize(
    "body",
    [
        {"receipts.receipt": {"period": "2026-11"}},
        {"receipts": [{"receipt.period": "2026-11"}]},
        {"snapshot_coverage.biz_register": ["2026-11"]},
    ],
    ids=["fused_two", "fused_last", "fused_coverage"],
)
def test_register_fused_manifest_key_is_free_text(body):
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(body, frozenset({"11"}), "manifest")


def test_register_manifest_typed_count_keeps_digit_run_guard():
    scan_metadata({"tables": [{"rows": int("9" * 7)}]}, frozenset(), "manifest")
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        scan_metadata({"tables": [{"rows": int("9" * 8)}]}, frozenset(), "manifest")


def test_register_unknown_manifest_format_refuses(monkeypatch):
    def scan(value):
        scan_metadata({"x": value}, frozenset({"11"}), "manifest")

    monkeypatch.setattr(validate, "TYPED_FIELDS", {"manifest.x": "month"})
    _single_input_pair(scan, ("2026-11",), ("2026",), "typed_field_format")
    monkeypatch.setattr(validate, "TYPED_FIELDS", {"manifest.x": "free"})
    with pytest.raises(RegisterError, match=r"^typed_field_format$"):
        scan("2026-11")


def test_register_report_and_other_artefact_roots_are_free_text():
    body = {"receipts": [{"receipt": {"period": "2026-11"}}]}
    scan_metadata(body, frozenset({"11"}), "manifest")
    for root in ("report", "manifest.receipts", "", "log"):
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            scan_metadata(body, frozenset({"11"}), root)


@pytest.mark.parametrize(
    "receipt,key",
    [
        (dict(), "20"),  # the fixture's receipt time is ...-20T00:00:00Z
        (dict(terms_read_on="2026-11-19"), "19"),
        (dict(), "2026"),  # the receipt period and the receipt time
        (dict(), "11"),
    ],
    ids=["receipt_time", "terms_date", "period_year", "period_month"],
)
@pytest.mark.parametrize("role", ["registration", "licence"])
def test_register_short_key_in_manifest_typed_field_builds(
    tmp_path, receipt, key, role
):
    row = (
        dict(registration_number=key)
        if role == "registration"
        else dict(licence_number=key)
    )
    result = _build(tmp_path, [commerce(**PLAIN, **row)], **receipt)
    assert result.manifest["receipts"][0]["receipt"]["period"] == "2026-11"


@pytest.mark.parametrize("role", ["registration", "licence"])
def test_register_long_key_in_manifest_receipt_time_build_refuses(tmp_path, role):
    stamp = dict(retrieved_utc="2026-11-20T00:00:00.125Z")
    row = dict(registration_number="125", licence_number="97003")
    if role == "licence":
        row = dict(licence_number="125")
    _build(tmp_path / "pass", [commerce(**PLAIN)], **stamp)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path / "refuse", [commerce(**PLAIN, **row)], **stamp)
    assert not (tmp_path / "refuse" / "current").exists()


def test_register_exact_table_count_survives_typed_list_removal(tmp_path, monkeypatch):
    # One card per source gives the storage-added count 2, also the token of the
    # unlisted `version` "v2"; three commerce cards give the count 4 instead.
    rows = [
        commerce(**PLAIN, licence_number="4"),
        commerce(
            **PLAIN,
            row_key="c" * 20,
            registration_number="54322",
            licence_number="97004",
        ),
        commerce(
            **PLAIN,
            row_key="d" * 20,
            registration_number="54323",
            licence_number="97005",
        ),
    ]
    _build(tmp_path / "pass", rows)
    _drop_from_list(monkeypatch, "manifest.tables.rows")
    # Decision 0124 / L-2141 F3: the separate exact-count list still validates it.
    result = _build(tmp_path / "exact", rows)
    company = next(
        t for t in result.manifest["tables"] if t["name"] == "pub_register_company"
    )
    assert company["rows"] == len(result.tables["pub_register_company"]) == 4
    # Matching negative: removing its exact-count authority makes it unlisted.
    monkeypatch.setattr(
        validate,
        "FIXED_METADATA",
        {
            path: rule
            for path, rule in contracts.FIXED_METADATA.items()
            if path != "manifest.tables.rows"
        },
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path / "refuse", rows)


def test_register_short_key_in_listed_versions_builds(tmp_path):
    # Round 9: both versions are listed fixed texts, so "v2" no longer stops
    # the key 2 (unlisted, it does: the report.version plant above).
    _build(tmp_path / "three", [commerce(**PLAIN, licence_number="3")])
    _build(tmp_path / "two", [commerce(**PLAIN, licence_number="2")])


@pytest.mark.parametrize("field", ["publisher", "dataset", "basis_note"])
def test_register_identifier_in_receipt_text_refuses(tmp_path, field):
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path, [commerce(licence_number="25")], **{field: "SYN 25"})


# --- Item B: number-typed columns meet input-only keys (decision 0119) ------

NUMBER_COLUMNS = [
    ("capital_qar", "126", "125"),
    ("lon", "1.126", "1.125"),
    ("lat", "2.126", "2.125"),
]


@pytest.mark.parametrize("column,other,equal", NUMBER_COLUMNS)
def test_register_licence_in_number_column_refuses(column, other, equal):
    """Decision 0119: re-pointed from the released key 125 to the licence 125."""
    _release(_cards(**{column: other}), licences=("125",))
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(_cards(**{column: equal}), licences=("125",))


@pytest.mark.parametrize("column,other,equal", NUMBER_COLUMNS)
def test_register_released_key_in_number_column_builds(column, other, equal):
    _release(_cards(registration_number="125", **{column: equal}))


def _listed(count, registration="125", period="2026-11"):
    return {
        "pub_register_company": _cards(registration_number=registration),
        "pub_register_snapshot": [],
        "register_company_list": [
            dict(
                registration_number=registration,
                period=period,
                employee_count=count,
                suppression_reason_code=None,
            )
        ],
    }


def test_register_licence_in_employee_count_refuses():
    """Decision 0119: re-pointed from the released key 125 to the licence 125."""
    licences = frozenset({"125"})
    validate_release(
        _listed(126, "54321"), FRAME, licences_by_registration={"54321": licences}
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            _listed(125, "54321"), FRAME, licences_by_registration={"54321": licences}
        )


def test_register_released_key_in_employee_count_builds():
    validate_release(_listed(125), FRAME)


OTHER_NUMBERS = [125, 2.125, {"k": [125]}, (1.0, 125)]


@pytest.mark.parametrize("value", OTHER_NUMBERS)
def test_register_withheld_in_number_of_other_table_refuses(value):
    """Decision 0119: re-pointed from the released key 125 to a withheld 125."""
    tables = {"pub_register_company": _cards(), "pub_register_snapshot": []}
    withheld = frozenset({"125"})
    validate_release(
        {**tables, "source_registry": [{"value": 126}]},
        FRAME,
        withheld_registrations=withheld,
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            {**tables, "source_registry": [{"value": value}]},
            FRAME,
            withheld_registrations=withheld,
        )


@pytest.mark.parametrize("value", OTHER_NUMBERS)
def test_register_released_key_in_number_of_other_table_builds(value):
    tables = {
        "pub_register_company": _cards(registration_number="125"),
        "pub_register_snapshot": [],
    }
    validate_release({**tables, "source_registry": [{"value": value}]}, FRAME)


def test_register_short_withheld_in_unlisted_number_refuses():
    """Decision 0119: re-pointed from the released key 12 to a withheld 12."""
    tables = {"pub_register_company": _cards(), "pub_register_snapshot": []}
    withheld = frozenset({"12"})
    validate_release(
        {**tables, "pub_place": [{"count": 13}]}, FRAME, withheld_registrations=withheld
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            {**tables, "pub_place": [{"count": 12}]},
            FRAME,
            withheld_registrations=withheld,
        )


@pytest.mark.parametrize(
    "number,column,value",
    [
        ("12", "capital_qar", "12"),
        ("2020", "capital_qar", "2020"),
        ("1999", "capital_qar", "1999"),
        ("12", "lat", "2.12"),
        ("05", "lon", "1.05"),
    ],
)
def test_register_short_registration_in_listed_number_builds(
    tmp_path, number, column, value
):
    _build(tmp_path, [commerce(registration_number=number, **{column: value}, **PLAIN)])


@pytest.mark.parametrize("count", [12, 2020])
def test_register_short_registration_in_employee_count_passes(count):
    validate_release(_listed(count, str(count)), FRAME)


def test_register_employee_count_missing_from_list_is_free_text(monkeypatch):
    """Decision 0119: the short collision is with the licence 12."""
    licences = frozenset({"12"})
    validate_release(
        _listed(12, "54321"), FRAME, licences_by_registration={"54321": licences}
    )
    _drop_from_list(monkeypatch, "register_company_list.employee_count")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            _listed(12, "54321"), FRAME, licences_by_registration={"54321": licences}
        )


@given(st.floats(-90, 90), st.floats(-180, 180), st.sampled_from([8, 9]))
def test_register_cell_key_cannot_equal_a_registration(lat, lng, resolution):
    """A cell key is one token of 18 or 19 digits; a registration has at most 6."""
    token = str(h3.str_to_int(h3.latlng_to_cell(lat, lng, resolution)))
    assert len(token) in {18, 19}
    assert REGISTRATION.fullmatch(token) is None


@pytest.mark.parametrize("table", ["pub_register_company", "pub_register_snapshot"])
def test_register_licence_equal_to_cell_key_refuses(table):
    cell = h3.str_to_int(h3.latlng_to_cell(2.25, 1.25, 8))
    frame = Frame(frozenset({cell}))
    cards = parse("biz_register", inputs(rows=[commerce(**PLAIN)]), frame)
    assert cards[0]["registered_cell"] == cell
    snapshot = [
        dict(
            registration_number=cards[0]["registration_number"],
            period="2026-11",
            source_id="biz_register",
            registered_cell=cell,
        )
    ]
    if table == "pub_register_company":
        snapshot = []
    tables = {"pub_register_company": cards, "pub_register_snapshot": snapshot}
    validate_release(
        tables, frame, licences_by_registration={"54321": frozenset({str(cell + 1)})}
    )
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            tables, frame, licences_by_registration={"54321": frozenset({str(cell)})}
        )


@pytest.mark.parametrize(
    "registration,column,value",
    [
        ("65432", "lat", 2.65432),
        ("54321", "capital_qar", 54321),
    ],
)
def test_register_base_collision_values_refuse_input_only(registration, column, value):
    """The values the base tests admitted (L-1288): decision 0119 publishes
    them against the released registration and refuses them against the same
    number as a licence; the pair differs only in the licence set."""
    cards = _cards(registration_number=registration)
    cards[0][column] = value
    _release(cards)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(cards, licences=(registration,))


# --- Generators over the input space ---------------------------------------


@given(st.from_regex(r"[0-9]{1,6}", fullmatch=True))
def test_register_licence_in_typed_integer_property(number):
    """Decision 0119: re-pointed from the released key to the licence; the
    same number as the released key publishes in every case."""
    licences = (number,)
    cards = _cards(street_number=number)
    if _admitted(number):
        _release(cards, licences=licences)
    else:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _release(cards, licences=licences)
    cards[0]["street_number"] = "0"
    _release(cards, licences=licences)
    cards[0]["name_en"] = "SYN " + number
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _release(cards, licences=licences)
    released = _cards(registration_number=number, street_number=number)
    released[0]["name_en"] = "SYN " + number
    _release(released)


@given(st.from_regex(r"[0-9]{1,7}", fullmatch=True), st.integers(1, 28))
def test_register_licence_in_typed_values_property(number, day):
    cards = _cards(
        licence_number=number,
        licence_issue_date=f"2026-11-{day:02d}",
        block_en=number,
        lat="2." + number,
    )
    if _admitted(number):
        _release(cards, licences=(number,))
    else:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _release(cards, licences=(number,))


def _collides(number, values):
    """Independent oracle of token equality: digit runs split on any non-digit."""
    return any(number in re.findall(r"[0-9]+", str(value)) for value in values)


@given(st.from_regex(r"[0-9]{1,6}", fullmatch=True))
def test_register_licence_in_number_columns_property(number):
    """Decision 0119: re-pointed from the released key to the licence."""
    cards = _cards(capital_qar=number, lat="2." + number)
    numbers = (cards[0]["capital_qar"], cards[0]["lat"])
    if _collides(number, numbers) and not _admitted(number):
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _release(cards, licences=(number,))
    else:
        _release(cards, licences=(number,))
    _release(_cards(registration_number=number, capital_qar=number, lat="2." + number))


@given(st.integers(0, 10**6 - 1), st.sampled_from(["field_absences", "tables"]))
def test_register_manifest_count_property(count, artefact):
    name = "count" if artefact == "field_absences" else "rows"
    key = frozenset({str(count)})
    typed = {artefact: [{name: count}]}
    if _admitted(str(count)):
        scan_metadata(typed, key, "manifest")
    else:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            scan_metadata(typed, key, "manifest")
    unlisted = {"receipts": [{"receipt": {"files": {"r": {"bytes": count}}}}]}
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(unlisted, key, "manifest")


@given(
    st.datetimes(min_value=datetime(1000, 1, 1), max_value=datetime(9999, 12, 31)),
    st.data(),
)
def test_register_manifest_timestamp_property(moment, data):
    value = moment.isoformat() + "Z"
    key = data.draw(st.sampled_from(re.findall(r"[0-9]+", value)))
    body = {"receipts": [{"receipt": {"retrieved_utc": value}}]}
    if _admitted(key):
        scan_metadata(body, frozenset({key}), "manifest")
    else:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            scan_metadata(body, frozenset({key}), "manifest")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata({"basis_note": value}, frozenset({key}), "manifest")


# --- The owner's a3: the two version texts and the period columns ----------


def _periods(field, period, registration="54321"):
    """Release tables whose one snapshot or list row holds `period`."""
    if field == PERIOD_FIELDS[1]:
        return _listed(0, registration, period)
    row = dict(
        registration_number=registration,
        period=period,
        source_id="biz_register",
        registered_cell=None,
    )
    return {
        "pub_register_company": _cards(registration_number=registration),
        "pub_register_snapshot": [row],
    }


def test_register_fixed_texts_are_what_the_build_writes(manifest, report):
    assert contracts.FIXED_TEXTS == {
        "manifest_version": "v2",
        "receipt_version": "register_input_v1",
        "report_version": "v2",
    }
    assert report["version"] == contracts.FIXED_TEXTS["report_version"]
    for field, text in VERSION_TEXTS.items():
        assert contracts.FIXED_TEXTS[contracts.TYPED_FIELDS[field]] == text
    assert manifest["version"] == contracts.FIXED_TEXTS["manifest_version"]
    assert {item["receipt"]["version"] for item in manifest["receipts"]} == {
        contracts.FIXED_TEXTS["receipt_version"]
    }
    assert {contracts.TYPED_FIELDS[field] for field in VERSION_FIELDS} == FIXED
    assert {contracts.TYPED_FIELDS[field] for field in PERIOD_FIELDS} == {"month"}


class _Text(str):
    """A string subclass: equal to the fixed text, but not a plain string."""


def _version_cases():
    wrong = {
        "manifest.version": ["v1", "v3", "v20", "register_input_v1", ""],
        "manifest.receipts.receipt.version": [
            "register_input_v2",
            "register_input_v0",
            "register_input_v",
            "v2",
            "",
        ],
        "report.version": ["v3", "v1", "v20", "123", "register_input_v1", ""],
    }
    for field in VERSION_FIELDS:
        text = VERSION_TEXTS[field]
        for value in wrong[field]:
            yield pytest.param(field, value, id=f"{field}-wrong-{value!r}")
        extra = {
            "suffix_space": text + " ",
            "prefix_space": " " + text,
            "newline": text + "\n",
            "nul": text + "\x00",
            "zero_width": text + "\u200b",
            "digit_doubled": text + text[-1],
            "letter": text + "x",
            "leading_letter": "x" + text,
        }
        for name, value in extra.items():
            yield pytest.param(field, value, id=f"{field}-extra-{name}")
        other = {
            "upper": text.upper(),
            "fullwidth_digit": text[:-1] + chr(0xFF10 + int(text[-1])),
            "bytes": text.encode(),
            "subclass": _Text(text),
            "number": int(text[-1]),
        }
        for name, value in other.items():
            yield pytest.param(field, value, id=f"{field}-other-{name}")


@pytest.mark.parametrize("field,value", list(_version_cases()))
def test_register_version_other_than_its_fixed_text_refuses(
    manifest, report, field, value
):
    """Owner's a3 and the advisor's report.version, plants 1 and 2: a wrong
    version text, or the right text with one extra character, refuses
    `typed_field_format` (no key is in play)."""
    name = field.partition(".")[0]

    def scan(version, keys):
        scan_metadata(_artefact(manifest, report, field, version), keys, name)

    keys = frozenset({"1", "2", "11"})
    good, bad = (VERSION_TEXTS[field], keys), (value, keys)
    _single_input_pair(scan, good, bad, "typed_field_format")


@given(
    st.sampled_from(VERSION_FIELDS),
    st.text(max_size=3),
    st.text(max_size=3),
    st.booleans(),
)
def test_register_version_fixed_text_property(field, before, after, wrapped):
    """Independent oracle: a version field admits exactly its one text."""
    text = VERSION_TEXTS[field]
    value = before + text + after if wrapped else before + after
    artefact, *names = field.split(".")

    def scan(version, keys):
        body = version
        for name in reversed(names):
            body = {name: body}
        scan_metadata(body, keys, artefact)

    keys = frozenset({text[-1]})
    if value == text:
        scan(value, keys)
    else:
        _single_input_pair(scan, (text, keys), (value, keys), "typed_field_format")


# Each compares at or after the first kept snapshot month, so only the month
# format can refuse it in either table.
NOT_A_MONTH = {
    "day": "2026-11-01",
    "one_digit_month": "2027-1",
    "no_hyphen": "202611",
    "slash": "2026/11",
    "month_13": "2026-13",
    "month_00": "2027-00",
    "trailing_space": "2026-11 ",
    "newline": "2026-11\n",
    "letter": "2026-11x",
    "fullwidth_year": "\uff12\uff10\uff12\uff16-11",
    "arabic_indic": "\u0662\u0660\u0662\u0666-\u0661\u0661",
    "bytes": b"2026-11",
    "integer": 202611,
}


@pytest.mark.parametrize("field", PERIOD_FIELDS)
@pytest.mark.parametrize("value", NOT_A_MONTH.values(), ids=NOT_A_MONTH.keys())
def test_register_period_column_not_a_month_refuses(field, value):
    """Owner's a3, plant 3: a period column holding anything but YYYY-MM."""
    validate_release(_periods(field, "2026-11", "11"), FRAME)
    with pytest.raises(RegisterError, match=r"^snapshot_month$"):
        validate_release(_periods(field, value, "11"), FRAME)


@given(
    st.sampled_from(PERIOD_FIELDS),
    st.one_of(
        st.text(max_size=9),
        st.from_regex(r"[0-9]{4}-[0-9]{2}", fullmatch=True),
        st.builds(
            "{}{}{}".format,
            st.text(max_size=1),
            st.from_regex(r"20[2-9][0-9]-1[12]", fullmatch=True),
            st.text(max_size=1),
        ),
    ),
)
def test_register_period_column_month_property(field, value):
    """Independent oracle: a period column admits a real month (a snapshot one
    no earlier than 2026-11), its short month token equal to a key included."""
    admitted = _MONTH.fullmatch(value) is not None
    if field == PERIOD_FIELDS[0]:
        admitted = admitted and value >= "2026-11"
    key = "11"
    if admitted:
        validate_release(_periods(field, value, key), FRAME)
    else:
        with pytest.raises(RegisterError, match=r"^snapshot_month$"):
            validate_release(_periods(field, value, key), FRAME)


@pytest.mark.parametrize("field", PERIOD_FIELDS)
def test_register_period_column_missing_from_list_is_free_text(monkeypatch, field):
    """Owner's a3, plant 4: unlisted, the real-shaped month 2026-11 meets the
    licence 11 by the full scan (decision 0119: an input-only key)."""
    tables = _periods(field, "2026-11")
    licences = frozenset({"11"})
    validate_release(tables, FRAME, licences_by_registration={"54321": licences})
    _drop_from_list(monkeypatch, field)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(tables, FRAME, licences_by_registration={"54321": licences})


@pytest.mark.parametrize("field", PERIOD_FIELDS)
def test_register_period_column_long_key_refuses(field):
    """Owner condition 1: a year token of three or more digits that is not of
    the 19xx or 20xx shape still refuses in a listed period column."""
    validate_release(_periods(field, "2126-11"), FRAME)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            _periods(field, "2126-11"),
            FRAME,
            licences_by_registration={"54321": frozenset({"2126"})},
        )


@pytest.mark.parametrize("field", PERIOD_FIELDS)
def test_register_period_year_equal_to_registration_admitted(field):
    """Owner condition 1 admits year-shaped values (19xx, 20xx) by format: the
    period 2026-11 against the registration 2026 passes."""
    validate_release(_periods(field, "2026-11", "2026"), FRAME)


@pytest.mark.parametrize("field", PERIOD_FIELDS)
def test_register_period_year_outside_year_shape_withheld_refuses(field):
    """Owner condition 1: the year 2126 is not of the 19xx or 20xx shape, so
    the period 2126-11 against the withheld 2126 refuses (decision 0119:
    re-pointed from the registration 2126, which now publishes)."""
    validate_release(_periods(field, "2126-11"), FRAME)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        validate_release(
            _periods(field, "2126-11"),
            FRAME,
            withheld_registrations=frozenset({"2126"}),
        )
    validate_release(_periods(field, "2126-11", "2126"), FRAME)


@given(st.sampled_from(PERIOD_FIELDS), st.integers(1000, 9999))
def test_register_period_year_against_licence_property(field, year):
    """Independent oracle: a period year equal to a licence is admitted
    exactly when it is of the 19xx or 20xx shape (owner condition 1); equal
    to the released registration it is always admitted (decision 0119)."""
    period = f"{year}-12"
    tables = _periods(field, period)
    licences = frozenset({str(year)})
    if field == PERIOD_FIELDS[0] and period < "2026-11":
        with pytest.raises(RegisterError, match=r"^snapshot_month$"):
            validate_release(
                tables, FRAME, licences_by_registration={"54321": licences}
            )
        return
    if str(year)[:2] in ("19", "20"):
        validate_release(tables, FRAME, licences_by_registration={"54321": licences})
    else:
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            validate_release(
                tables, FRAME, licences_by_registration={"54321": licences}
            )
    validate_release(_periods(field, period, str(year)), FRAME)


def _role_rows(role, key, **row):
    """Decision 0119: the input-only roles are a licence and a withheld
    duplicate registration (the former `registration_number` role)."""
    if role == "withheld":
        return _withheld_rows(key, **row)
    return [commerce(**PLAIN, **{role: key}, **row)]


@pytest.mark.parametrize("key", ["1", "11"])
@pytest.mark.parametrize("role", ["withheld", "licence_number"])
def test_register_a3_short_key_builds_and_free_text_refuses(tmp_path, role, key):
    """The receipt version holds the token 1; every period, the snapshot
    table's included, holds 11. Neither stops the build; free text does."""
    result = _build(tmp_path / "pass", _role_rows(role, key), kept=True)
    assert {r["period"] for r in result.tables["pub_register_snapshot"]} == {"2026-11"}
    assert result.manifest["receipts"][0]["receipt"]["version"] == "register_input_v1"
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(
            tmp_path / "refuse", _role_rows(role, key, name_en="SYN " + key), kept=True
        )
    assert not (tmp_path / "refuse" / "current").exists()


@pytest.mark.parametrize("role", ["withheld", "licence_number"])
def test_register_a3_key_two_meets_only_the_report_version(tmp_path, role):
    """Round 9 (advisor, report.version): with the report's `version` listed as
    the fixed text v2, a build with the key 2 passes end to end, both versions
    holding v2; a free-text 2 still refuses (PO-S2-P71-12)."""
    result = _build(tmp_path / "pass", _role_rows(role, "2"), kept=True)
    published = tmp_path / "pass" / "current" / "build_report.json"
    assert result.manifest["version"] == "v2"
    assert json.loads(published.read_bytes())["version"] == "v2"
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path / "refuse", _role_rows(role, "2", name_en="SYN 2"), kept=True)


@pytest.mark.parametrize("key", ["1", "2", "11"])
def test_register_a3_short_released_key_in_free_text_builds(tmp_path, key):
    """Decision 0119: the former `registration_number` role of the two tests
    above; a released key in free text is published."""
    row = commerce(**PLAIN, registration_number=key, name_en="SYN " + key)
    _build(tmp_path, [row], kept=True)
    assert (tmp_path / "current" / "build_report.json").exists()


@pytest.mark.parametrize("role", ["registration_number", "licence_number"])
def test_register_report_version_missing_from_list_refuses_key_two(
    tmp_path, monkeypatch, role
):
    """Advisor's plant 3: unlisted, the report's v2 meets the key 2 by the full
    scan and the build refuses with nothing published."""
    row = commerce(**PLAIN, **{role: "2"})
    _build(tmp_path / "pass", [row], kept=True)
    _drop_from_list(monkeypatch, "report.version")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _build(tmp_path / "refuse", [row], kept=True)
    assert not (tmp_path / "refuse" / "current").exists()


def test_register_report_other_fields_keep_full_scan(report):
    """Condition 1 is unchanged in the rest of the report: the 3-digit
    non-year value 123 equal to a registration refuses in each other field."""
    others = sorted(set(report) - {"version"})
    assert others
    scan_metadata(report, frozenset({"123"}), "report")
    for field in others:
        body = {**report, field: "SYN 123"}
        scan_metadata(body, frozenset({"54321"}), "report")
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            scan_metadata(body, frozenset({"123"}), "report")


def test_register_a3_short_keys_in_published_manifest_pass(manifest):
    """The real built manifest holds v2, register_input_v1 and 2026-11; the
    short keys 1, 2 and 11 meet none of them, while an unlisted field still
    refuses each."""

    def scan(body, keys):
        scan_metadata(body, keys, "manifest")

    keys = frozenset({"1", "2", "11"})
    for key in keys:
        body = copy.deepcopy(manifest)
        body["receipts"][0]["receipt"]["basis_note"] = "SYN " + key
        _single_input_pair(scan, (manifest, keys), (body, keys), "registration_egress")


def test_register_single_input_pair_refuses_two_changed_inputs():
    """Planted violation of the helper: a pair changing two inputs (the class
    of p2rv2 finding 2 and p2cf2 finding 1) fails before either call runs."""
    with pytest.raises(AssertionError, match="changes one input"):
        _single_input_pair(print, ("v2", {"1"}), ("v3", set()), "typed_field_format")
    with pytest.raises(AssertionError, match="changes one input"):
        _single_input_pair(print, ("v2", {"1"}), ("v2", {"1"}), "typed_field_format")
    # A change of type alone (an equal string subclass) is one changed input.
    _single_input_pair(
        lambda v: scan_metadata({"version": v}, frozenset(), "report"),
        ("v2",),
        (_Text("v2"),),
        "typed_field_format",
    )
