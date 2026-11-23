"""S2-P71 round 3: letter-spelled row identities, activity reasons, row namespace."""

from dataclasses import replace

import pytest
from custodian.tests.test_registers import (
    capture,
    commerce,
    inputs,
    row_identity_oracle,
)
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.activity_check import register_activity_check
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import ROW_KEY, RegisterError
from eii_custodian.publicdata.registers.parse import parse
from eii_custodian.publicdata.registers.provenance import Frame
from eii_custodian.publicdata.registers.validate import validate_release
from eii_custodian.publicdata.review.activity import ActivityRow, IsicClass, ReviewRow

# The verdict's reproduction: an exactly eight-digit and an exactly eleven-digit
# run inside a published twenty-character hexadecimal row key. Runs are joined
# at run time so no source line holds one (DAT-15).
EIGHT = "1234" + "5678"
ELEVEN = EIGHT + "901"
EIGHT_RUN = "a" + EIGHT + "b" + "c" * 10
ELEVEN_RUN = "a" + ELEVEN + "b" + "c" * 7
HEX = "0123456789abcdef"


@pytest.mark.parametrize("kind", ["public_only", "protected"])
@pytest.mark.parametrize(
    "key,identity",
    [
        (EIGHT_RUN, "ROW-ahijklmnob" + "c" * 10),
        (ELEVEN_RUN, "ROW-ahijklmnopghb" + "c" * 7),
        ("0" * 20, "ROW-" + "g" * 20),
    ],
    ids=["eight", "eleven", "all_digits"],
)
def test_register_row_key_digit_run_builds(tmp_path, kind, key, identity):
    source = capture(files=inputs(rows=[commerce(registration_number="", row_key=key)]))
    result = build(
        tmp_path, kind, Frame(frozenset()), (source, capture("fc_register")), (source,)
    )
    for rows in result.tables.values():
        assert [row["registration_number"] for row in rows].count(identity) == 1
    assert (tmp_path / "current/manifest.json").is_file()


@pytest.mark.parametrize("run", [EIGHT, ELEVEN], ids=["eight", "eleven"])
def test_register_digit_run_elsewhere_still_refuses(tmp_path, run):
    source = capture(
        files=inputs(
            rows=[
                commerce(
                    registration_number="", row_key=EIGHT_RUN, name_en="SYN " + run
                )
            ]
        )
    )
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        build(
            tmp_path,
            "public_only",
            Frame(frozenset()),
            (source, capture("fc_register")),
            (),
        )
    assert not (tmp_path / "current").exists()


@given(
    st.lists(
        st.text(alphabet=HEX, min_size=20, max_size=20),
        min_size=1,
        max_size=6,
        unique=True,
    )
)
def test_register_row_identity_is_lossless_letters(row_keys):
    frame = Frame(frozenset())
    rows = [commerce(row_key=key, registration_number="") for key in row_keys]
    cards = parse("biz_register", inputs(rows=rows), frame)
    identities = sorted(str(card["registration_number"]) for card in cards)
    assert identities == sorted(row_identity_oracle(key) for key in row_keys)
    assert all(ROW_KEY.fullmatch(identity) for identity in identities)
    assert not any(character.isdigit() for item in identities for character in item)
    inverse = dict(zip("ghijklmnop", "0123456789", strict=True))
    assert sorted(
        "".join(inverse.get(c, c) for c in identity.removeprefix("ROW-"))
        for identity in identities
    ) == sorted(row_keys)
    validate_release(
        {"pub_register_company": cards, "pub_register_snapshot": []}, frame
    )


@pytest.mark.parametrize(
    "key",
    ["ROW-" + "a" * 19 + "0", "ROW-" + "a" * 19 + "q", "ROW-" + EIGHT_RUN],
    ids=["digit", "past_p", "raw_hex"],
)
def test_register_unspelled_row_identity_refuses(key):
    frame = Frame(frozenset())
    rows = parse("biz_register", inputs(), frame)
    rows[0]["registration_number"] = key
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        validate_release(
            {"pub_register_company": rows, "pub_register_snapshot": []}, frame
        )


@pytest.mark.parametrize(
    "key",
    ["g" * 20, "a" * 19 + "p", "a" * 19 + "A", "a" * 19, "a" * 21],
    ids=["spelled_g", "spelled_p", "upper", "short", "long"],
)
def test_register_source_row_key_outside_hex_refuses(key):
    # g-p spell digits in the identity; a raw one would make two keys collide.
    with pytest.raises(RegisterError, match=r"^row_key_format$"):
        parse(
            "biz_register",
            inputs(rows=[commerce(registration_number="", row_key=key)]),
            Frame(frozenset()),
        )


def _snapshot(source_id):
    return dict(
        registration_number="ROW-" + "a" * 20,
        period="2026-11",
        source_id=source_id,
        registered_cell=None,
    )


def test_register_row_identity_on_commerce_snapshot_passes():
    frame = Frame(frozenset())
    cards = parse("fc_register", inputs("fc_register"), frame)
    validate_release(
        {
            "pub_register_company": cards,
            "pub_register_snapshot": [_snapshot("biz_register")],
        },
        frame,
    )


def test_register_row_identity_on_financial_centre_snapshot_refuses():
    frame = Frame(frozenset())
    cards = parse("fc_register", inputs("fc_register"), frame)
    with pytest.raises(RegisterError, match=r"^registration_format$"):
        validate_release(
            {
                "pub_register_company": cards,
                "pub_register_snapshot": [_snapshot("fc_register")],
            },
            frame,
        )


ACTIVITY = ActivityRow("5610101", "SYN activity", 1, 0)
CLASSES = {
    "5610": IsicClass("5610", "SYN class", ""),
    "5630": IsicClass("5630", "SYN other class", ""),
}
REVIEW = ReviewRow(
    ACTIVITY.code,
    7,
    ACTIVITY.name_ar,
    "5610",
    "mapped",
    "reviewer_approved",
    "fixture reviewer",
    "2026-11-01",
)


def test_register_activity_signed_review_baseline():
    assert register_activity_check(ACTIVITY, CLASSES, REVIEW) == {
        "status": "mapped",
        "reason": "reviewer_approved",
    }


@pytest.mark.parametrize(
    "change",
    [
        dict(reviewed_by_role=""),
        dict(reviewed_on="2026-02-30"),
        dict(reason="guessed"),
        dict(name_ar="SYN other name"),
        dict(status="guessed"),
        dict(status="not_mappable_rejected"),
    ],
    ids=["no_role", "bad_date", "reason", "name", "status", "rejected_reason"],
)
def test_register_activity_review_invalid(change):
    with pytest.raises(RegisterError, match=r"^activity_review_invalid$"):
        register_activity_check(ACTIVITY, CLASSES, replace(REVIEW, **change))


@pytest.mark.parametrize(
    "change",
    [dict(isic_class="5630"), dict(isic_class="5630", reviewed_by_role="")],
    ids=["signed", "unsigned"],
)
def test_register_activity_mapped_class_mismatch(change):
    with pytest.raises(RegisterError, match=r"^activity_code_mismatch$"):
        register_activity_check(ACTIVITY, CLASSES, replace(REVIEW, **change))
