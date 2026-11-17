"""Invented draw edge cases, with every log confined to pytest tmp_path."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_figure_draw import figures

from eii_custodian.publicdata.draw import draw, reviewer_sheet, sample, validate_figure


def malformed(value: Any) -> Any:
    return value


def assert_message(error, expected):
    assert str(error.value) == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("figure_id", ""),
        ("source_id", ""),
        ("url", ""),
        ("filter", " "),
        ("value", ""),
        ("value", "not a decimal"),
        ("value", "NaN"),
        ("value", "Infinity"),
        ("provenance", "Synthetic"),
        ("kind", "invented unknown"),
        ("url", "http://example.org/invented"),
        ("source_id", None),
    ],
)
def test_exact_invalid_figure_refusal(field, value):
    with pytest.raises(ValueError) as error:
        validate_figure(replace(figures()[0], **{field: malformed(value)}))
    assert_message(error, "figure_invalid")


def test_exact_sample_boundary_and_duplicate_refusal():
    ids = [f"invented-{i}" for i in range(20)]
    assert sorted(sample(ids, 17)) == sorted(ids)
    for duplicated in ([*ids, ids[0]], [ids[0], ids[0]]):
        with pytest.raises(ValueError) as error:
            sample(duplicated, 17)
        assert_message(error, "figure_identity_duplicate")


def test_key_and_other_administrative_rows_do_not_stop_enumeration(tmp_path):
    rows = figures()[:20]
    administrative = [
        replace(rows[0], figure_id=f"invented-{kind}", kind=kind)
        for kind in ("administrative_count", "hash", "key")
    ]
    selected = draw(
        {"invented": lambda: [*administrative, *rows]}, 17, tmp_path / "log.json"
    )
    assert sorted(f.figure_id for f in selected) == sorted(
        f"invented-{i}" for i in range(20)
    )


def test_duplicate_draw_refuses_with_exact_text(tmp_path):
    with pytest.raises(ValueError) as error:
        draw(
            {"invented": lambda: [*figures(), figures()[0]]}, 17, tmp_path / "log.json"
        )
    assert_message(error, "figure_identity_duplicate")


def test_reviewer_sheet_has_exact_seed_and_only_links():
    assert reviewer_sheet(17, figures()[:1]) == {
        "seed": 17,
        "figures": [
            {
                "figure_id": "invented-0",
                "source_id": "invented",
                "url": "https://example.org/source",
                "filter": "invented filter",
            }
        ],
    }


class DifferentDefaultEncodingPath(type(Path())):
    """Caller-supplied Path whose unspecified text codec is deliberately UTF-16."""

    def read_text(self, encoding=None, errors=None, newline=None):
        if encoding is None:
            encoding = "utf-16"
        return super().read_text(encoding, errors, newline)

    def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "b" not in mode and encoding in (None, "locale"):
            encoding = "utf-16"
        return super().open(mode, buffering, encoding, errors, newline)


def test_draw_uses_explicit_utf8_with_a_different_default_codec(tmp_path):
    log = DifferentDefaultEncodingPath(tmp_path / "log.json")
    log.write_bytes(b'{"z_invented": "kept", "a_invented": "kept"}')
    observed = []

    def read():
        observed.append(log.read_bytes())
        assert observed == [
            b'{"a_invented": "kept", "figure_seed": 17, "z_invented": "kept"}\n'
        ]
        raise OSError("invented read stops after observing durable log")

    with pytest.raises(ValueError) as error:
        draw({"invented": read}, 17, log)
    assert_message(error, "figure_table_unreachable:invented")
    assert len(observed) == 1


def test_sorted_seed_log_bytes_are_observable_before_first_table(tmp_path):
    log = tmp_path / "log.json"
    log.write_text('{"z_invented": "kept", "a_invented": "kept"}', encoding="utf-8")

    def read():
        assert (
            log.read_bytes()
            == b'{"a_invented": "kept", "figure_seed": 17, "z_invented": "kept"}\n'
        )
        return figures()[:20]

    assert len(draw({"invented": read}, 17, log)) == 20
    assert json.loads(log.read_text(encoding="utf-8"))["figure_seed"] == 17
