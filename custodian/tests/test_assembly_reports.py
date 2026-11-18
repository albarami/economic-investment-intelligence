"""Reports and draw consume stored invented outputs, with value-free summaries."""

import importlib.util
import json
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_io import write_record
from eii_custodian.publicdata.assembly_reports import draw_tables, write_reports


def build(tmp_path: Path):
    row = entry()
    state = context(tmp_path, (row,))
    state.receipts = {row.key: receipt(row)}
    state.table(
        "pub_invented",
        [{"period": "2026", "value": str(i), "cell": i} for i in range(25)],
        (row.key,),
    )
    state.audit = {
        "completeness": [],
        "terms": [],
        "coverage": {},
        "oi03": {"state": "pending"},
        "confirmations": [],
        "investment": [],
    }
    state.record("final_audit", state.audit)
    state.record(
        "gis_property_singles",
        {"tables": state.tables, "source_tables": state.source_tables},
    )
    return state


def test_draw_reads_stored_fields_and_excludes_admin_columns(tmp_path: Path) -> None:
    state = build(tmp_path)
    readers = draw_tables(state)
    assert set(readers) == {"pub_invented"}
    figures = readers["pub_invented"]()
    assert len(figures) == 25
    assert all(f.kind == "count" and "value" in f.figure_id for f in figures)
    assert figures[4].value == "4"
    assert all("cell" not in f.figure_id for f in figures)


def test_removed_or_changed_table_refuses_entire_draw(tmp_path: Path) -> None:
    state = build(tmp_path)
    readers = draw_tables(state)
    path = tmp_path / "assembly/gis_property_singles.json"
    path.write_text("{}")
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        readers["pub_invented"]()


def test_seed_is_durable_before_first_table_read_and_reports_hide_values(
    tmp_path: Path, monkeypatch
) -> None:
    state = build(tmp_path)
    seen = []
    from eii_custodian.publicdata import assembly_reports

    original = assembly_reports.draw_tables

    def readers(s):
        return {
            key: lambda read=read: (
                seen.append(
                    json.loads((tmp_path / "assembly/build.json").read_text())[
                        "figure_seed"
                    ]
                ),
                read(),
            )[1]
            for key, read in original(s).items()
        }

    monkeypatch.setattr(assembly_reports, "draw_tables", readers)
    write_record(tmp_path, "assembly/build.json", {})
    state.draw()
    assert seen == [17]
    outputs = write_reports(state)
    assert len(outputs) == 7
    summary = json.loads((tmp_path / "assembly/s2_t08_draw.json").read_text())
    assert len(summary["figures"]) == 20
    assert all("value" not in figure for figure in summary["figures"])


def test_no_reports_before_audit_or_draw(tmp_path: Path) -> None:
    state = context(tmp_path)
    with pytest.raises(AssemblyError):
        write_reports(state)
    assert not (tmp_path / "assembly/s2_t08_completeness.json").exists()


@pytest.mark.parametrize("measure", [12, "12.5"])
def test_numeric_fields_outside_closed_schema_are_not_silently_omitted(
    tmp_path: Path, measure: object
) -> None:
    state = build(tmp_path)
    state.tables["pub_invented"][0]["novel_measure"] = measure
    state.record(
        "gis_property_singles",
        {"tables": state.tables, "source_tables": state.source_tables},
    )
    with pytest.raises(AssemblyError, match="assembly_draw_field_unknown"):
        draw_tables(state)["pub_invented"]()


def test_pending_gate_evidence_cannot_return_success(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_reports import require_complete

    state = build(tmp_path)
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(state.audit)


def _complete_audit() -> dict[str, object]:
    return {
        "completeness": [{"state": "in use"}],
        "terms": [{"own_words_state": "recorded"}],
        "oi03": {"state": "recorded"},
        "confirmations": [
            {"task": task, "state": "recorded"}
            for task in ("S2-T12", "S2-T13", "S2-T15", "S2-T17", "S2-T19", "S2-T20")
        ],
        "regressions": {"missing": [], "mismatch": ""},
    }


def test_pending_terms_rows_do_not_hold_back_a_complete_build() -> None:
    """Ruling L-1001: every terms row pending, every other gate recorded, passes."""
    from eii_custodian.publicdata.assembly_reports import require_complete

    audit = _complete_audit()
    audit["terms"] = [
        {"id": "invented-a", "own_words_state": "pending"},
        {"id": "invented-b", "own_words_state": "pending"},
    ]
    require_complete(audit)


def test_a_malformed_terms_list_is_still_refused() -> None:
    """The terms list must stay present and well formed; only the state gate drops."""
    from eii_custodian.publicdata.assembly_reports import require_complete

    for planted in (
        [],
        "invented",
        [{"own_words_state": "invented"}],
        [{"id": "invented-a"}],
        ["invented"],
    ):
        audit = _complete_audit()
        audit["terms"] = planted
        with pytest.raises(AssemblyError, match="assembly_gate_pending"):
            require_complete(audit)


def test_each_missing_or_pending_gate_is_refused() -> None:
    from eii_custodian.publicdata.assembly_reports import require_complete

    audit = {
        "completeness": [{"state": "in use"}],
        "terms": [{"own_words_state": "recorded"}],
        "oi03": {"state": "recorded"},
        "confirmations": [
            {"task": task, "state": "recorded"}
            for task in ("S2-T12", "S2-T13", "S2-T15", "S2-T17", "S2-T19", "S2-T20")
        ],
        "regressions": {"missing": [], "mismatch": ""},
    }
    require_complete(audit)
    for key in audit:
        changed = dict(audit)
        changed.pop(key)
        with pytest.raises(AssemblyError, match="assembly_gate_pending"):
            require_complete(changed)


def test_multisource_draw_names_each_input_hash_and_url(tmp_path: Path) -> None:
    state = build(tmp_path)
    second = entry(source="second", url="https://example.org/other")
    state.receipts[second.key] = receipt(second)
    state.table_sources["pub_invented"].add(second.key)
    figures = draw_tables(state)["pub_invented"]()
    assert "https://example.org/other" in figures[0].filter
    assert "https://example.org/source" in figures[0].filter
    assert "a" * 64 in figures[0].filter


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_stored_measure_is_refused(tmp_path: Path, value: str) -> None:
    state = build(tmp_path)
    state.tables["pub_invented"][0]["value"] = value
    state.record(
        "gis_property_singles",
        {"tables": state.tables, "source_tables": state.source_tables},
    )
    with pytest.raises(AssemblyError, match="assembly_draw_value_invalid"):
        draw_tables(state)["pub_invented"]()


def test_duplicate_confirmations_do_not_cover_six_tasks() -> None:
    from eii_custodian.publicdata.assembly_reports import require_complete

    audit = {
        "completeness": [{"state": "in use"}],
        "terms": [{"own_words_state": "recorded"}],
        "oi03": {"state": "recorded"},
        "confirmations": [{"task": "S2-T12", "state": "recorded"}] * 6,
        "regressions": {"missing": [], "mismatch": ""},
    }
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(audit)


def test_reports_refuse_a_changed_draw_envelope(tmp_path: Path) -> None:
    state = build(tmp_path)
    write_record(tmp_path, "assembly/build.json", {})
    state.draw()
    path = tmp_path / "assembly/draw_values.json"
    payload = json.loads(path.read_text())
    payload["figures"][0]["value"] = "999"
    path.write_text(json.dumps(payload))
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        write_reports(state)
    assert not (tmp_path / "assembly/s2_t08_draw.json").exists()


def test_unreachable_registered_table_refuses_whole_draw(tmp_path: Path) -> None:
    state = build(tmp_path)
    key = next(iter(state.receipts))
    state.table("pub_not_indexed", [{"value": 12}], (key,))
    with pytest.raises(AssemblyError, match="figure_table_unreachable"):
        draw_tables(state)


def test_draw_cannot_use_unreceipted_lineage(tmp_path: Path) -> None:
    state = build(tmp_path)
    readers = draw_tables(state)
    state.receipts.clear()
    with pytest.raises(AssemblyError, match="assembly_lineage_missing"):
        readers["pub_invented"]()


def test_reports_refuse_changed_seed_log_after_draw(tmp_path: Path) -> None:
    state = build(tmp_path)
    write_record(tmp_path, "assembly/build.json", {})
    state.draw()
    write_record(tmp_path, "assembly/build.json", {"figure_seed": 99})
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        write_reports(state)


def load_script():
    """Load the review CLI by file path; the runner keeps the repository
    root off sys.path, so the scripts package is never importable."""
    path = repository_root(Path(__file__)) / "scripts" / "figures_review.py"
    spec = importlib.util.spec_from_file_location("figures_review_entry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_draw_has_the_existing_review_cli_input_shape(tmp_path: Path) -> None:
    run = load_script().run

    state = build(tmp_path)
    write_record(tmp_path, "assembly/build.json", {})
    outputs = state.draw()
    stored = tmp_path / "assembly/draw_review_values.json"
    assert stored.relative_to(tmp_path).as_posix() in outputs
    figures = json.loads(stored.read_text())
    assert isinstance(figures, list) and len(figures) == 20
    reviewer = tmp_path / "invented_reviewer.json"
    reviewer.write_text(json.dumps({row["figure_id"]: row["value"] for row in figures}))
    verdict = tmp_path / "invented_verdict.json"
    assert run(stored, reviewer, verdict) == 0
    assert all("value" not in row for row in json.loads(verdict.read_text()))
