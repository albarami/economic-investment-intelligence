"""LR3 selected-series survivors, using existing invented cache builders."""

import json
import sys

import pytest
from custodian.tests.test_pub67 import (
    FRAME,
    LOCAL,
    active_rows,
    build,
    selected_fixture,
)
from custodian.tests.test_public_series import series_cache
from custodian.tests.test_series_figures_survivors import _shapes

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.review.activity import entry_by_key
from eii_custodian.publicdata.review.cache_fixture import write_cached
from eii_custodian.publicdata.series import figures
from eii_custodian.publicdata.series.parse import Municipality
from eii_custodian.publicdata.stage import StageResult


def _whole_text(found: object, literal: str) -> None:
    assert str(found) == literal


def test_classes_required_whole_refusal(tmp_path):
    entries, _ = selected_fixture(tmp_path)
    with pytest.raises(ValueError) as caught:
        figures.compute_checks(
            {"lic_active": active_rows()},
            municipalities=FRAME,
            activity_entry=entry_by_key(entries, "lic_active"),
        )
    _whole_text(caught.value, "PUB-67 ISIC classes required")


def test_review_path_uses_module_root(tmp_path, monkeypatch):
    from custodian.tests.test_pub67 import classes

    module = tmp_path / "src/eii_custodian/publicdata/series/figures.py"
    module.parent.mkdir(parents=True)
    review = tmp_path / "publicdata/review"
    review.mkdir(parents=True)
    (review / "municipality_names.csv").write_text(
        "name,municipality_code\nبلدية تجريبية,5\n", encoding="utf-8"
    )
    monkeypatch.setattr(figures, "__file__", str(module))
    entries, _ = selected_fixture(tmp_path)
    rows = active_rows()
    for row in rows:
        row["lbldy"] = "بلدية تجريبية"
    result = figures.compute_checks(
        {"lic_active": rows},
        municipalities=(Municipality("SYN-FRAME", "بلدية تجريبية"),),
        isic_classes=classes(),
        activity_entry=entry_by_key(entries, "lic_active"),
    )
    assert result["PUB-67"] == {**LOCAL, "al_daayen_5610101": "6"}


def test_source_specific_gap_and_oserror_are_retained(tmp_path, monkeypatch):
    entry, digest = series_cache(tmp_path, "util_elec", _shapes()["util_elec"])
    monkeypatch.setattr(
        figures,
        "mapping_gaps",
        lambda source: ("SYN-gap",) if source == "util_elec" else (),
    )

    def unavailable(group, *, receipts=None):
        raise OSError("SYN unavailable")

    monkeypatch.setattr(figures, "compute_checks", unavailable)
    result = figures.build_series(tmp_path, [entry], {"util_elec": digest})
    assert result["blocked"] == {"util_elec": ("SYN-gap", "regression: OSError")}


def test_missing_active_frame_keeps_later_checks(tmp_path):
    shapes = _shapes()
    entries, selected = [], {}
    for source in ("lic_active", "util_elec"):
        entry, digest = series_cache(tmp_path, source, shapes[source])
        entries.append(entry)
        selected[source] = digest
    result = figures.build_series(tmp_path, entries, selected)
    assert result["blocked"] == {"lic_active": ("municipality_frame_not_supplied",)}
    assert result["checks"] == {
        "PUB-62": {
            "zone_69_2021": "12",
            "zone_69_2025": "30",
            "ratio_2dp": "2.50",
            "sum_ratio_2dp": "2.50",
        }
    }


def test_support_reaches_internal_and_display_tables(tmp_path, monkeypatch):
    entries, selected = selected_fixture(tmp_path)
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    result = build(tmp_path, entries, selected)
    assert result["blocked"] == {}
    for folder in ("internal", "display"):
        envelope = json.loads(
            (tmp_path / "series" / folder / "pub_licence_active.json").read_text()
        )
        assert set(envelope) == {
            "method",
            "method_version",
            "source_chain",
            "release_tables",
            "field_mapping",
            "rows",
            "row_sources",
            "supporting_provenance",
        }
        assert envelope["row_sources"] == ["lic_active"] * 9
        assert envelope["rows"] == [
            {
                "municipality_code": code,
                "activity_code": activity,
                "period": "2025-05",
                "active_count": count,
                "activity_name_ar": "SYN activity " + activity,
            }
            for code, activity, count in (
                ("SYN-TARGET", "5610101", 1),
                ("SYN-TARGET", "5610101", 2),
                ("SYN-OTHER", "5610101", 3),
                ("SYN-TARGET", "1234001", 9),
                ("SYN-TARGET", "9999001", 6),
                ("SYN-TARGET", "561010", 7),
                ("SYN-TARGET", "12345", 4),
                ("SYN-TARGET", "1234" + "5678", 5),
                ("SYN-TARGET", "123", 8),
            )
        ]
        support = envelope["supporting_provenance"]
        assert support["schema"] == "pub67-support.v1"
        assert support["classification"]["sha256"] == selected["cls_isic4"]
        assert [row["sha256"] for row in support["frame"]["upstream"]] == [
            selected["bnd_hdx"],
            selected["bnd_zone_2020"],
        ]


def test_refused_checks_do_not_rewrite_internal_support(tmp_path):
    entries, selected = selected_fixture(tmp_path)
    rows = active_rows()
    rows[0]["lbldy"] = "SYN unmatched"
    body = json.dumps(rows).encode()
    write_cached(tmp_path, entry_by_key(entries, "lic_active"), body)
    selected["lic_active"] = sha256_hex(body)
    result = build(tmp_path, entries, selected)
    assert result["blocked"] == {
        "lic_active": ("regression: PUB-67 unresolved source municipality",)
    }
    envelope = json.loads(
        (tmp_path / "series/internal/pub_licence_active.json").read_text()
    )
    assert set(envelope) == {
        "method",
        "method_version",
        "source_chain",
        "release_tables",
        "field_mapping",
        "rows",
        "row_sources",
    }


@pytest.mark.parametrize("plant", ["registry", "selection"])
def test_caught_support_refusal_whole_text(tmp_path, plant):
    """Trace exception events because finish_build exposes only the error type."""
    entries, selected = selected_fixture(tmp_path)
    lines = [f"PASS {key} sha256={value}" for key, value in selected.items()]
    if plant == "registry":
        entries = [entry for entry in entries if entry.key != "cls_isic4"]
        literal = "supporting registry identity required"
    else:
        lines = [line for line in lines if not line.startswith("PASS cls_isic4 ")]
        literal = "one supporting selected hash required"
    seen = []

    def observe(frame, event, arg):
        # Module identity works for original functions and mutation trampolines.
        if event == "exception" and frame.f_globals.get("__name__") == figures.__name__:
            _, error, _ = arg
            if type(error) is ValueError:
                seen.append(error)
        return observe

    previous = sys.gettrace()
    try:
        sys.settrace(observe)
        result = figures.finish_build(entries, tmp_path, lines)
    finally:
        sys.settrace(previous)
    assert result is not None
    assert result.observed == "ValueError"
    assert seen
    _whole_text(seen[0], literal)


@pytest.mark.parametrize("suffix", [" SYN-host extra=SYN", "\tSYN-host"])
def test_support_selection_keeps_first_space_token(tmp_path, suffix):
    entries, selected = selected_fixture(tmp_path)
    lines = [
        f"PASS {key} sha256={value}" + (suffix if key == "cls_isic4" else "")
        for key, value in selected.items()
    ]
    result = figures.finish_build(entries, tmp_path, lines)
    assert result is not None
    if suffix.startswith(" "):
        assert result.source_id == "PUB-67"
        _whole_text(lines[-1], "FAIL PUB-67 public_data selected-cache check")
        report = json.loads((tmp_path / "series/internal/build.json").read_text())
        assert report["blocked"] == {}
        assert report["checks"] == {"PUB-67": LOCAL}
    else:
        report = json.loads((tmp_path / "series/internal/build.json").read_text())
        assert report["blocked"] == {
            "lic_active": ["regression: invalid selected hash"]
        }
        assert report["checks"] == {}
