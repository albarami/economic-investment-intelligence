"""S2-T08 part B, pass 3: the review command line of ``scripts/figures_review.py``.

Its grammar is three paths, the stored draw, the reviewer's values and the
verdict to write. Misuse writes nothing, reads nothing and exits 2. A refused
input exits 1 with one closed reason and writes nothing. Output, on screen and
in the verdict file, is metadata only: figure IDs, addresses and match status,
never a value. Every figure below is invented.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from custodian.tests.test_figures_review import figure, load_script

SECRET = "98765.4321"


def _files(tmp_path: Path, *, count: int = 20, value: str = SECRET):
    stored, reviewer, output = (
        tmp_path / name for name in ("draw.json", "reviewer.json", "verdict.json")
    )
    figures = [
        replace(figure(), figure_id=f"invented-{i}", value=value, kind="money")
        for i in range(count)
    ]
    stored.write_text(json.dumps([asdict(f) for f in figures]), encoding="utf-8")
    reviewer.write_text(
        json.dumps({f.figure_id: value for f in figures}), encoding="utf-8"
    )
    return stored, reviewer, output


def _main(argv: list[str]) -> int:
    return load_script().main(argv)


@pytest.mark.parametrize(
    "shape",
    ["none", "one", "two", "four", "option", "help", "output_is_stored"],
)
def test_misuse_exits_2_and_reads_and_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    shape: str,
) -> None:
    stored, reviewer, output = _files(tmp_path)
    paths = [str(stored), str(reviewer), str(output)]
    argv = {
        "none": [],
        "one": paths[:1],
        "two": paths[:2],
        "four": [*paths, str(tmp_path / "extra.json")],
        "option": ["--seed", "7", *paths],
        "help": ["--help"],
        "output_is_stored": [paths[0], paths[1], paths[0]],
    }[shape]
    script = load_script()
    monkeypatch.setattr(
        script, "run", lambda *_a: pytest.fail("misuse must not reach a read")
    )
    before = stored.read_bytes()
    assert script.main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: figures_review.py STORED REVIEWER OUTPUT")
    assert not output.exists()
    assert stored.read_bytes() == before


def test_a_matching_review_exits_0_and_prints_metadata_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stored, reviewer, output = _files(tmp_path)
    assert _main([str(stored), str(reviewer), str(output)]) == 0
    out = capsys.readouterr()
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert [set(row) for row in verdict] == [{"figure_id", "url", "result"}] * 20
    assert out.out.splitlines() == [
        f"invented-{i} https://example.org match" for i in range(20)
    ]
    assert SECRET not in out.out + out.err + output.read_text(encoding="utf-8")


def test_a_mismatch_exits_1_with_its_status_and_no_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stored, reviewer, output = _files(tmp_path)
    values = json.loads(reviewer.read_text(encoding="utf-8"))
    values["invented-3"] = "12345.6789"
    reviewer.write_text(json.dumps(values), encoding="utf-8")
    assert _main([str(stored), str(reviewer), str(output)]) == 1
    out = capsys.readouterr()
    assert "invented-3 https://example.org no match" in out.out.splitlines()
    text = out.out + out.err + output.read_text(encoding="utf-8")
    assert SECRET not in text and "12345.6789" not in text


@pytest.mark.parametrize(
    ("plant", "reason"),
    [
        ("count", "figure_review_count_invalid"),
        ("stored_schema", "figure_schema_invalid"),
        ("reviewer_schema", "reviewer_schema_invalid"),
        ("ids", "reviewer_ids_mismatch"),
        ("stored_value", "figure_invalid"),
        ("not_json", "review_input_unreadable"),
        ("missing", "review_input_unreadable"),
    ],
)
def test_a_refused_input_exits_1_with_a_closed_reason_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], plant: str, reason: str
) -> None:
    stored, reviewer, output = _files(tmp_path, count=19 if plant == "count" else 20)
    if plant == "stored_schema":
        rows = json.loads(stored.read_text(encoding="utf-8"))
        rows[0]["unknown"] = SECRET
        stored.write_text(json.dumps(rows), encoding="utf-8")
    elif plant == "reviewer_schema":
        reviewer.write_text(json.dumps({"invented-0": 1}), encoding="utf-8")
    elif plant == "ids":
        values = json.loads(reviewer.read_text(encoding="utf-8"))
        values["invented-extra"] = SECRET
        reviewer.write_text(json.dumps(values), encoding="utf-8")
    elif plant == "stored_value":
        rows = json.loads(stored.read_text(encoding="utf-8"))
        rows[0]["value"] = "SYN " + SECRET
        stored.write_text(json.dumps(rows), encoding="utf-8")
    elif plant == "not_json":
        reviewer.write_text("{" + SECRET, encoding="utf-8")
    elif plant == "missing":
        reviewer.unlink()
    assert _main([str(stored), str(reviewer), str(output)]) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == f"figures_review: {reason}\n"
    assert not output.exists()


def test_an_unlisted_error_text_is_never_printed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored, reviewer, output = _files(tmp_path)
    script = load_script()

    def leaking(*_args: object) -> int:
        raise ValueError("SYN upstream text " + SECRET)

    monkeypatch.setattr(script, "run", leaking)
    assert script.main([str(stored), str(reviewer), str(output)]) == 1
    out = capsys.readouterr()
    assert out.err == "figures_review: review_input_invalid\n"
    assert SECRET not in out.out + out.err
