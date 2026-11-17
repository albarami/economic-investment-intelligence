"""Invented figure tables; log fixtures are confined to pytest tmp_path."""

import json
from dataclasses import replace
from random import Random

import pytest

from eii_custodian.publicdata.draw import Figure, draw, reviewer_sheet, sample


def figures():
    return [
        Figure(
            f"invented-{i}",
            "invented",
            "https://example.org/source",
            "invented filter",
            str(i),
            "count",
        )
        for i in range(40)
    ]


def test_uniform_reproducible_draw():
    ids = [f.figure_id for f in figures()]
    assert sample(ids, 17) == Random(17).sample(sorted(ids), 20)
    assert sample(ids, 17) == sample(list(reversed(ids)), 17)
    assert len(set(sample(ids, 17))) == 20
    assert sample(ids, 17) != sample(ids, 18)
    for bad in (ids[:19], [*ids[:19], ids[0]]):
        with pytest.raises(ValueError):
            sample(bad, 17)


def test_seed_is_durable_before_table_read_and_preserves_log(tmp_path):
    log = tmp_path / "build-log.json"
    log.write_text(json.dumps({"lines": ["invented existing line"]}))

    def read():
        assert json.loads(log.read_text()) == {
            "lines": ["invented existing line"],
            "figure_seed": 17,
        }
        return [
            *figures(),
            replace(figures()[0], figure_id="admin", kind="administrative_count"),
            replace(figures()[0], figure_id="hash", kind="hash"),
        ]

    selected = draw({"pub_invented": read}, 17, log)
    assert len(selected) == 20
    assert {f.figure_id for f in selected}.isdisjoint({"admin", "hash"})
    assert json.loads(log.read_text())["figure_ids"] == [f.figure_id for f in selected]
    sheet = reviewer_sheet(17, selected)
    assert all(
        set(row) == {"figure_id", "source_id", "url", "filter"}
        for row in sheet["figures"]
    )
    assert all("value" not in row for row in sheet["figures"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", ""),
        ("url", ""),
        ("filter", ""),
        ("value", "NaN"),
        ("provenance", "Synthetic"),
    ],
)
def test_invalid_eligible_figure_refuses(tmp_path, field, value):
    rows = figures()
    rows[0] = replace(rows[0], **{field: value})
    with pytest.raises(ValueError):
        draw({"pub_invented": lambda: rows}, 17, tmp_path / "log.json")


def test_unreachable_table_refuses_without_reduced_universe(tmp_path):
    def unavailable():
        raise OSError("invented unavailable table")

    with pytest.raises(ValueError, match="figure_table_unreachable:pub_missing"):
        draw(
            {"pub_invented": figures, "pub_missing": unavailable},
            17,
            tmp_path / "log.json",
        )


def test_duplicate_figure_identity_refuses(tmp_path):
    with pytest.raises(ValueError, match="figure_identity_duplicate"):
        draw(
            {"pub_invented": lambda: figures() + figures()[:1]},
            17,
            tmp_path / "log.json",
        )


def test_flush_failure_prevents_any_table_read(tmp_path, monkeypatch):
    import os

    called = []

    def failed_flush(fd):
        raise OSError("invented flush failure")

    monkeypatch.setattr(os, "fsync", failed_flush)
    with pytest.raises(OSError, match="invented flush failure"):
        draw({"invented": lambda: called.append(True)}, 17, tmp_path / "log.json")
    assert not called
