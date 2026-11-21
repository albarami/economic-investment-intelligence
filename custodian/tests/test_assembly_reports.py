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
            for task in (
                "S2-T09",
                "S2-T12",
                "S2-T13",
                "S2-T15",
                "S2-T17",
                "S2-T19",
                "S2-T20",
            )
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
            for task in (
                "S2-T09",
                "S2-T12",
                "S2-T13",
                "S2-T15",
                "S2-T17",
                "S2-T19",
                "S2-T20",
            )
        ],
        "regressions": {"missing": [], "mismatch": ""},
    }
    require_complete(audit)
    for key in audit:
        changed = dict(audit)
        changed.pop(key)
        with pytest.raises(AssemblyError, match="assembly_gate_pending"):
            require_complete(changed)


def _multisource_build(tmp_path: Path, *, series: bool = False):
    state = build(tmp_path)
    second = entry(
        source="second",
        key="second/key" if series else "second",
        url="https://example.org/other",
    )
    state.receipts[second.key] = {**receipt(second), "sha256": "c" * 64}
    state.table_sources["pub_invented"].add(second.key)
    keys = ["invented"] * 24 + [second.source_id if series else second.key]
    payload = {"tables": state.tables}
    if series:
        (tmp_path / "assembly/gis_property_singles.json").unlink()
        payload["row_sources"] = {"pub_invented": keys}
        state.record("series_stage", payload)
    else:
        for row, key in zip(state.tables["pub_invented"], keys, strict=True):
            row["source_key"] = key
        state.record("gis_property_singles", payload)
    return state


def test_multisource_draw_names_each_input_hash_and_url(tmp_path: Path) -> None:
    state = _multisource_build(tmp_path)
    figures = draw_tables(state)["pub_invented"]()
    links = [
        {
            key: state.receipts[source][key]
            for key in ("source_id", "fetch_url", "sha256")
        }
        for source in ("invented", "second")
    ]
    for index, figure in enumerate(figures):
        source = "second" if index == 24 else "invented"
        own = state.receipts[source]
        assert figure.source_id == own["source_id"]
        assert figure.url == own["fetch_url"]
        assert figure.filter == (
            "snapshot="
            + own["sha256"]
            + ";table=pub_invented;row="
            + str(index)
            + ";field=value;inputs="
            + json.dumps(links, sort_keys=True)
        )


@pytest.mark.parametrize("series", [False, True])
def test_multisource_draw_names_the_row_source(tmp_path: Path, series: bool) -> None:
    state = _multisource_build(tmp_path, series=series)
    figure = draw_tables(state)["pub_invented"]()[-1]
    assert figure.source_id == "second"
    assert figure.url == "https://example.org/other"
    assert figure.filter.split(";", 1)[0] == "snapshot=" + "c" * 64


def test_untagged_multisource_table_is_excluded_and_recorded(tmp_path: Path) -> None:
    state = _multisource_build(tmp_path)
    for row in state.tables["pub_invented"]:
        row.pop("source_key")
    state.table("pub_checkable", [{"value": i} for i in range(25)], ("invented",))
    state.record("gis_property_singles", {"tables": state.tables})
    assert set(draw_tables(state)) == {"pub_checkable"}
    write_record(tmp_path, "assembly/build.json", {})
    state.draw()
    record = json.loads((tmp_path / "assembly/draw.json").read_text())
    assert record["excluded_tables"] == [
        {
            "table": "pub_invented",
            "sources": ["invented", "second"],
            "reason": "assembly_draw_lineage_ambiguous",
        }
    ]
    assert all(key.startswith("pub_checkable:") for key in record["figure_ids"])


@pytest.mark.parametrize("series", [False, True])
def test_empty_multisource_table_is_excluded_as_empty(
    tmp_path: Path, series: bool
) -> None:
    state = _multisource_build(tmp_path, series=series)
    state.tables["pub_invented"] = []
    state.table("pub_checkable", [{"value": i} for i in range(25)], ("invented",))
    state.record(
        "series_stage" if series else "gis_property_singles",
        {"tables": state.tables, "row_sources": {"pub_invented": []}},
    )
    assert set(draw_tables(state)) == {"pub_checkable"}
    write_record(tmp_path, "assembly/build.json", {})
    state.draw()
    record = json.loads((tmp_path / "assembly/draw.json").read_text())
    assert record["excluded_tables"] == [
        {
            "table": "pub_invented",
            "sources": ["invented", "second/key" if series else "second"],
            "reason": "assembly_draw_table_empty",
        }
    ]
    assert all(key.startswith("pub_checkable:") for key in record["figure_ids"])


@pytest.mark.parametrize("series", [False, True])
def test_partly_tagged_multisource_table_refuses(tmp_path: Path, series: bool) -> None:
    state = _multisource_build(tmp_path, series=series)
    if series:
        state.record(
            "series_stage",
            {
                "tables": state.tables,
                "row_sources": {"pub_invented": ["invented"] * 24},
            },
        )
    else:
        state.tables["pub_invented"][-1].pop("source_key")
        state.record("gis_property_singles", {"tables": state.tables})
    with pytest.raises(AssemblyError, match="assembly_draw_lineage_ambiguous"):
        readers = draw_tables(state)
        readers["pub_invented"]()


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


def test_pending_method_pin_blocks_otherwise_complete_audit() -> None:
    from eii_custodian.publicdata.assembly_reports import require_complete

    audit = {
        "completeness": [{"state": "in use"}],
        "terms": [{"own_words_state": "recorded"}],
        "oi03": {"state": "recorded"},
        "confirmations": [
            {"task": task, "state": "recorded" if task != "S2-T09" else "pending"}
            for task in (
                "S2-T09",
                "S2-T12",
                "S2-T13",
                "S2-T15",
                "S2-T17",
                "S2-T19",
                "S2-T20",
            )
        ],
        "regressions": {"missing": [], "mismatch": ""},
    }
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(audit)


def test_checked_method_pin_reaches_require_complete_through_gather_audit(
    tmp_path: Path,
) -> None:
    from custodian.tests.method_pin_gather_fixtures import (
        gathered_s2_t09_confirmation,
        otherwise_complete_audit_with_s2_t09,
        stage_method_pin_gather_build,
    )

    from eii_custodian.publicdata.assembly_reports import require_complete

    build, *_ = stage_method_pin_gather_build(tmp_path)
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "recorded"
    require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


def test_missing_method_pin_record_refused_at_require_complete(
    tmp_path: Path,
) -> None:
    """Only the source-check record is absent; every other S2-T09 input is valid."""
    from custodian.tests.method_card_pin_fixtures import write_yaml
    from custodian.tests.method_pin_gather_fixtures import (
        gathered_s2_t09_confirmation,
        otherwise_complete_audit_with_s2_t09,
        stage_method_pin_gather_build,
    )

    from eii_custodian.publicdata.assembly_reports import require_complete

    build, record, _ = stage_method_pin_gather_build(tmp_path, stage_record=False)
    record_path = build.review / "s2_t09_source_checks.yaml"
    assert not record_path.exists()
    assert (build.cache / "assembly/s2_t09_pin_artifact.json").is_file()
    assert (build.cache / "assembly/s2_t09_pin_generation_config.json").is_file()
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "pending"
    assert s2_t09["reason"] == "confirmation_pending"
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))
    # The same staged inputs pass once the record alone is restored.
    write_yaml(record_path, record)
    restored = gathered_s2_t09_confirmation(build)
    assert restored["state"] == "recorded"
    require_complete(otherwise_complete_audit_with_s2_t09(restored))


def test_missing_method_pin_outputs_refused_at_require_complete(
    tmp_path: Path,
) -> None:
    from custodian.tests.method_pin_gather_fixtures import (
        gathered_s2_t09_confirmation,
        otherwise_complete_audit_with_s2_t09,
        stage_method_pin_gather_build,
    )

    from eii_custodian.publicdata.assembly_reports import require_complete

    build, *_ = stage_method_pin_gather_build(tmp_path, stage_outputs=False)
    assert not (build.cache / "assembly/s2_t09_pin_artifact.json").exists()
    assert not (build.cache / "assembly/s2_t09_pin_generation_config.json").exists()
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "pending"
    assert s2_t09["reason"] == "confirmation_pending"
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


def test_schema_valid_pending_method_pin_refused_at_require_complete(
    tmp_path: Path,
) -> None:
    from custodian.tests.method_card_pin_fixtures import pending
    from custodian.tests.method_pin_gather_fixtures import (
        gathered_s2_t09_confirmation,
        otherwise_complete_audit_with_s2_t09,
        stage_method_pin_gather_build,
    )

    from eii_custodian.publicdata.assembly_reports import require_complete

    build, *_ = stage_method_pin_gather_build(
        tmp_path,
        mutate=lambda _paths, rec, _artifact, _config: pending(rec["pins"][0]),
    )
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "pending"
    assert s2_t09["reason"] == "confirmation_pending"
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


@pytest.mark.parametrize(
    "plant",
    ["corrupt_artifact", "corrupt_receipt"],
)
def test_invalid_method_pin_evidence_refused_at_require_complete(
    tmp_path: Path, plant: str
) -> None:
    from custodian.tests.method_card_pin_fixtures import digest, lineage_context
    from custodian.tests.method_pin_gather_fixtures import (
        gathered_s2_t09_confirmation,
        otherwise_complete_audit_with_s2_t09,
        stage_method_pin_gather_build,
    )

    from eii_custodian.publicdata.assembly_reports import require_complete

    def corrupt_artifact(_paths, _record, artifact, _config):
        artifact["pins"][0]["values"]["value"] = "invented-corrupt"

    mutate = corrupt_artifact if plant == "corrupt_artifact" else None

    build, record, *_ = stage_method_pin_gather_build(tmp_path, mutate=mutate)
    if plant == "corrupt_receipt":
        key = next(iter(lineage_context(record)["receipts"]))
        build.receipts[key] = {**build.receipts[key], "sha256": digest(b"corrupt body")}
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "pending"
    assert s2_t09["reason"] == "confirmation_pending"
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


def test_duplicate_confirmations_do_not_cover_the_confirmation_tasks() -> None:
    """Seven recorded duplicates pass the count; task membership alone refuses."""
    from eii_custodian.publicdata.assembly_reports import require_complete
    from eii_custodian.publicdata.gate_report import CONFIRMATION_TASKS

    def audit(confirmations: list[dict[str, str]]) -> dict[str, object]:
        return {
            "completeness": [{"state": "in use"}],
            "terms": [{"own_words_state": "recorded"}],
            "oi03": {"state": "recorded"},
            "confirmations": confirmations,
            "regressions": {"missing": [], "mismatch": ""},
        }

    assert len(CONFIRMATION_TASKS) == 7
    # Control: one recorded row per task with the same other criteria passes.
    require_complete(
        audit([{"task": task, "state": "recorded"} for task in CONFIRMATION_TASKS])
    )
    duplicates = [{"task": "S2-T12", "state": "recorded"} for _ in CONFIRMATION_TASKS]
    assert len(duplicates) == len(CONFIRMATION_TASKS)
    assert all(row["state"] == "recorded" for row in duplicates)
    with pytest.raises(AssemblyError, match="assembly_gate_pending"):
        require_complete(audit(duplicates))


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
