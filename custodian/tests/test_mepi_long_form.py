"""S2-T08 part B, mismatch class 6: the MEPI export in its published long form.

The live shape pack's Mismatches item 6 shows the publisher serving the machinery
and equipment price index as 100 long-form records (``year``, ``half_year``,
``nsf_lsn``, ``group_code``, ``group``, ``lmjmw``, ``weight``, ``index_value``)
instead of the ten wide rows the registry declared (LR-P7). The row now declares
the long columns and the exact reviewed count of 100, the convention every
portal row of the registry uses; no wider range is admitted. Half-year and group
labels stay as published and no canonical period is made from them. Every
record below is invented.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root
from custodian.tests.test_publicdata_behaviour import (
    _clock,
    _ok,
    _portal_meta,
    _sidecar,
    _sleep,
)

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.checks import CLOSED_SHAPE_KEYS, schema_failure
from eii_custodian.publicdata.fetch.registry import Entry, load_registry

REPO = repository_root(Path(__file__))
KEY = "price_ext/machinery-and-equipment-price-index-mepi"
LONG = (
    ("year", "string"),
    ("half_year", "string"),
    ("nsf_lsn", "string"),
    ("group_code", "string"),
    ("group", "string"),
    ("lmjmw", "string"),
    ("weight", "number"),
    ("index_value", "number"),
)
WIDE = ("code", "group_desc_ar", "group_desc_en", "h1_20", "h2_24")
COUNT = 100


def _mepi() -> Entry:
    return next(
        e
        for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
        if e.key == KEY
    )


def _record(number: int, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "year": "2024",
        "half_year": "SYN-H1" if number % 2 else "SYN-H2",
        "nsf_lsn": "SYN-HALF-AR",
        "group_code": f"SYN-G{number}",
        "group": "SYN group",
        "lmjmw": "SYN group AR",
        "weight": 1.5,
        "index_value": 100.25,
    }
    record.update(changes)
    return record


def _records(count: int = COUNT) -> list[dict[str, object]]:
    return [_record(number) for number in range(count)]


def _fetch(tmp_path: Path, records: list[dict[str, object]]):
    entry = _mepi()
    meta = json.dumps(
        _portal_meta(
            entry.publisher,
            licence="CC BY",
            licence_url="https://creativecommons.org/licenses/by/4.0/",
        )
    ).encode()

    def transport(url: str):
        return _ok(
            url,
            json.dumps(records).encode() if url.endswith("/exports/json") else meta,
        )

    return fetch_entry(entry, transport, tmp_path, _clock, _sleep)


def test_registry_declares_the_long_form_and_the_exact_reviewed_count() -> None:
    entry = _mepi()
    assert entry.columns == LONG
    assert entry.row_count_min == entry.row_count_max == COUNT
    # No canonical period is made from year and half-year labels.
    assert (entry.period_field, entry.period_first, entry.period_last) == ("", "", "")
    assert "long form" in entry.basis_note
    assert "H1-20" not in entry.basis_note


def test_the_long_form_is_admitted_with_its_labels(tmp_path: Path) -> None:
    assert _fetch(tmp_path, _records()) is None
    receipt = _sidecar(tmp_path)
    assert [c["name"] for c in receipt["columns"]] == [name for name, _ in LONG]
    (body,) = [
        p
        for p in tmp_path.rglob(f"{receipt['sha256']}.json")
        if p.is_file() and p.parent.name[4:5] == "-"
    ]
    labels = {row["half_year"] for row in json.loads(body.read_bytes())}
    assert labels == {"SYN-H1", "SYN-H2"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("group", 7),
        ("group_code", 7),
        ("half_year", 1),
        ("year", 2024),
        ("index_value", "100.25"),
        ("weight", "1.5"),
    ],
    ids=[
        "group_int",
        "group_code_int",
        "half_int",
        "year_int",
        "index_text",
        "weight_text",
    ],
)
def test_a_retyped_field_is_refused(tmp_path: Path, field: str, value: object) -> None:
    records = _records()
    records[3] = _record(3, **{field: value})
    failure = _fetch(tmp_path, records)
    assert failure is not None
    assert failure.check == "schema_retyped"
    assert failure.expected == f"{field}:{dict(LONG)[field]}"
    assert not list(tmp_path.rglob("*.meta.json"))


@pytest.mark.parametrize(
    ("count", "check"), [(10, "row_count"), (COUNT, "extra_field")]
)
def test_the_old_wide_shape_is_refused(tmp_path: Path, count: int, check: str) -> None:
    wide = [
        {
            "code": f"SYN-G{n}",
            "group_desc_ar": "SYN group AR",
            "group_desc_en": "SYN group",
            "weight": 1.5,
            **{f"h{h}_{y}": 100.0 for y in range(20, 25) for h in (1, 2)},
        }
        for n in range(count)
    ]
    failure = _fetch(tmp_path, wide)
    assert failure is not None
    assert failure.check == check
    assert not list(tmp_path.rglob("*.meta.json"))


@pytest.mark.parametrize("position", [0, COUNT - 1], ids=["first", "last"])
def test_an_unknown_field_is_refused(tmp_path: Path, position: int) -> None:
    records = _records()
    records[position] = _record(position, syn_extra="invented")
    failure = _fetch(tmp_path, records)
    assert failure is not None
    assert (failure.check, failure.expected, failure.observed) == (
        "extra_field",
        "declared",
        "syn_extra",
    )
    assert not list(tmp_path.rglob("*.meta.json"))


def test_only_the_reviewed_row_refuses_an_undeclared_field() -> None:
    # The closed shape is this row's reviewed correction, not a registry-wide
    # change: another portal row keeps its existing behaviour.
    assert CLOSED_SHAPE_KEYS == frozenset({KEY})
    other = replace(_mepi(), key="price_ext/invented-other")
    rows: list[object] = [{**_record(n), "syn_extra": "x"} for n in range(COUNT)]
    assert schema_failure(other, rows, "https://invented.test") is None


@pytest.mark.parametrize("count", [COUNT - 1, COUNT + 1, 10])
def test_a_count_other_than_the_reviewed_count_is_refused(
    tmp_path: Path, count: int
) -> None:
    failure = _fetch(tmp_path, _records(count))
    assert failure is not None
    assert (failure.check, failure.expected, failure.observed) == (
        "row_count",
        f"{COUNT}..{COUNT}",
        str(count),
    )
    assert not list(tmp_path.rglob("*.meta.json"))


def test_review_record_holds_the_correction() -> None:
    review = yaml.safe_load(
        (REPO / "custodian/publicdata/review/s2_t08_source_review.yaml").read_text(
            encoding="utf-8"
        )
    )
    (row,) = [r for r in review["rows"] if r["mismatch"] == 6]
    assert row["key"] == KEY
    assert row["export_sha256"].startswith("4a0ed7f7")
    assert len(row["export_sha256"]) == 64
    assert row["change"]["row_count"] == {"from": "10..10", "to": "100..100"}
    assert set(row["change"]["columns"]["removed"]) >= set(WIDE)
