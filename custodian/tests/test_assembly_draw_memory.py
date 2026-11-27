"""Invented phase envelopes: parse bounds, stored-row proof and draw parity."""

import gc
import json
import weakref
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest
from custodian.tests.test_assembly_reports import _multisource_build, build
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata import assembly_reports
from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_io import write_record

PHASES = ("frame", "gis_property_singles", "series_stage")


def phases(tmp_path: Path, *, held: bool, rows: int = 25):
    state = context(tmp_path)
    source = entry()
    state.receipts[source.key] = receipt(source)
    for index, phase in enumerate(PHASES):
        names = (f"pub_a{index}", f"pub_z{index}")
        for name in names:
            state.table(
                name,
                [{"value": str(i), "share": "0.5"} for i in range(rows)],
                (source.key,),
            )
        payload = {"tables": {name: state.tables[name] for name in names}}
        if held:
            state.record(phase, payload)
        else:
            state.files.update(
                write_record(tmp_path, f"assembly/{phase}.json", payload)
            )
    write_record(tmp_path, "assembly/build.json", {})
    return state


@pytest.mark.parametrize("held", [False, True])
def test_draw_parses_each_unheld_phase_once_and_no_held_phase(
    tmp_path: Path, monkeypatch, held: bool
) -> None:
    state = phases(tmp_path, held=held, rows=2500)
    calls = Counter()
    original = assembly_reports.read_object

    def counted(root, name):
        calls[name] += 1
        return original(root, name)

    monkeypatch.setattr(assembly_reports, "read_object", counted)
    state.draw()
    expected = {} if held else {f"assembly/{phase}.json": 1 for phase in PHASES}
    assert calls == expected


def test_draw_refuses_a_held_row_changed_after_write(tmp_path: Path) -> None:
    state = build(tmp_path)
    state.tables["pub_invented"][0]["value"] = "999"
    with pytest.raises(AssemblyError, match=r"^assembly_draw_held_rows_changed$"):
        state.draw()


@pytest.mark.parametrize("held", [False, True])
def test_draw_binds_phase_bytes_before_using_rows(tmp_path: Path, held: bool) -> None:
    state = phases(tmp_path, held=held)
    path = tmp_path / "assembly/gis_property_singles.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        state.draw()


def test_draw_releases_parsed_phase_before_reading_next(
    tmp_path: Path, monkeypatch
) -> None:
    state = phases(tmp_path, held=False)
    alive = []
    original = assembly_reports.read_object

    class Phase(dict):
        pass

    class Rows(list):
        pass

    def tracked(root, name):
        gc.collect()
        assert not any(ref() is not None for ref in alive), "parsed phases overlap"
        result = Phase(original(root, name))
        alive.append(weakref.ref(result))
        for table, rows in result["tables"].items():
            result["tables"][table] = Rows(Phase(row) for row in rows)
            alive.append(weakref.ref(result["tables"][table]))
            alive.extend(weakref.ref(row) for row in result["tables"][table])
        return result

    monkeypatch.setattr(assembly_reports, "read_object", tracked)
    state.draw()
    gc.collect()
    assert len(alive) == len(PHASES) * (1 + 2 * (1 + 25))
    assert all(ref() is None for ref in alive)


@pytest.mark.parametrize("held", [False, True])
def test_interleaved_table_names_keep_identical_draw_bytes(
    tmp_path: Path, held: bool
) -> None:
    state = phases(tmp_path / "actual", held=held)
    control = phases(tmp_path / "control", held=False)
    state.draw()
    control.draw()
    for name in ("draw", "draw_values", "draw_review_values"):
        relative = f"assembly/{name}.json"
        assert (state.cache / relative).read_bytes() == (
            control.cache / relative
        ).read_bytes()


def test_duplicate_gazetteer_prefix_remains_required(tmp_path: Path) -> None:
    state = phases(tmp_path, held=True)
    state.table("gazetteer", [{"name": "SYN first"}], ("invented",))
    state.record("frame", {"tables": {"gazetteer": state.tables["gazetteer"]}})
    state.tables["gazetteer"] = [{"name": "SYN other"}]
    state.record("gis_property_singles", {"tables": state.tables})
    with pytest.raises(AssemblyError, match=r"^assembly_table_duplicate$"):
        state.draw()


def test_held_rows_use_stored_json_types_and_field_order(tmp_path: Path) -> None:
    from datetime import date

    from hypothesis import given, settings
    from hypothesis import strategies as st

    @settings(deadline=None)
    @given(st.decimals(allow_nan=False, allow_infinity=False, places=3))
    def check(value):
        state = build(tmp_path)
        state.tables["pub_invented"][0].update(
            value=value, as_of=date(2026, 1, 1), geometry=(1, 2), share="0.5"
        )
        state.record("gis_property_singles", {"tables": state.tables})
        figures = assembly_reports.draw_tables(state)["pub_invented"]()
        stored = json.loads(
            (tmp_path / "assembly/gis_property_singles.json").read_text()
        )
        first = stored["tables"]["pub_invented"][0]
        assert [f.figure_id for f in figures[:2]] == [
            "pub_invented:0:share",
            "pub_invented:0:value",
        ]
        assert figures[1].value == first["value"]

    check()


@pytest.mark.parametrize(
    "variant,digests",
    [
        (
            "single",
            (
                "48c5c2f8098784b21c4f1070efdbd363df8604206206f6fd6e570ccb9d786b03",
                "ef670bbf0b1e7cec9e233fa220698aeae36c5d3e4652b2bac2930e8903925e73",
                "dd5f04c2f20411603ad6c6ced099ef2e64fde21b16059b5e19082791664a4e3d",
            ),
        ),
        (
            "multi",
            (
                "900586dda31a0a3950be8919b9deca36d2e6970bdf30c8d3accc35e52a2a88d9",
                "116f2ae3e7fb2fbd30fb8f9f9235bae872c641f535d680feb3b43dad0fe89660",
                "5109935b08b4c1c662e2a78bb26a061b7302bc4d862f9598490b487ea3dd3b18",
            ),
        ),
        (
            "series",
            (
                "095ae7655036e064675c95055b7434f0363577db1c27445f4319b0a6c6b476bf",
                "3a3136b94fa2ca7c5bb78ec9a9bb42ba81e749c89e6f3f0efb478d315df00a0c",
                "5109935b08b4c1c662e2a78bb26a061b7302bc4d862f9598490b487ea3dd3b18",
            ),
        ),
    ],
)
def test_existing_draw_bytes_match_base_commit(
    tmp_path: Path, variant: str, digests: tuple[str, ...]
) -> None:
    """Captured before production edits, at a3efa045; no refreshed expectations."""
    state = (
        build(tmp_path)
        if variant == "single"
        else _multisource_build(tmp_path, series=variant == "series")
    )
    write_record(tmp_path, "assembly/build.json", {})
    state.draw()
    for name, digest in zip(
        ("draw", "draw_values", "draw_review_values"), digests, strict=True
    ):
        assert (
            sha256((tmp_path / f"assembly/{name}.json").read_bytes()).hexdigest()
            == digest
        )


def test_held_row_refusal_keeps_its_closed_log_reason(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    state = build(tmp_path)
    state.tables["pub_invented"][0]["value"] = "999"
    with pytest.raises(AssemblyError, match=r"^assembly_draw_held_rows_changed$"):
        with stage_refusals(state.lines, "draw"):
            state.draw()
    assert state.lines == ["REFUSED draw assembly_draw_held_rows_changed"]


@pytest.mark.parametrize("held", [False, True])
def test_draw_keeps_unindexed_table_refusal(tmp_path: Path, held: bool) -> None:
    state = phases(tmp_path, held=held)
    del state.tables["pub_a0"]
    with pytest.raises(AssemblyError, match=r"^assembly_draw_table_unindexed$"):
        state.draw()


@pytest.mark.parametrize("payload", [{"tables": []}, {"tables": {"pub_a0": [1]}}])
def test_draw_keeps_invalid_output_refusal(tmp_path: Path, payload: dict) -> None:
    state = phases(tmp_path, held=False)
    state.files.update(write_record(tmp_path, "assembly/frame.json", payload))
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        state.draw()


@pytest.mark.parametrize("held", [False, True])
def test_phase_is_hash_bound_before_parsing_or_held_verification(
    tmp_path: Path, monkeypatch, held: bool
) -> None:
    from eii_custodian.publicdata.assembly_io import HeldRecord

    state = phases(tmp_path, held=held)
    bound = set()
    original_bind = assembly_reports.bound_files
    original_read = assembly_reports.read_object
    original_verify = HeldRecord.verify

    def bind(root, files):
        original_bind(root, files)
        bound.update(files)

    def read(root, name):
        assert name in bound, "phase used before hash binding"
        return original_read(root, name)

    def verify(record):
        phase = record.data["method"].removeprefix("public-assembly.")
        assert f"assembly/{phase}.json" in bound, "held phase used before hash binding"
        return original_verify(record)

    monkeypatch.setattr(assembly_reports, "bound_files", bind)
    monkeypatch.setattr(assembly_reports, "read_object", read)
    monkeypatch.setattr(HeldRecord, "verify", verify)
    state.draw()
    assert bound == {f"assembly/{phase}.json" for phase in PHASES}


def test_mixed_held_and_file_only_phases(tmp_path: Path, monkeypatch) -> None:
    state = phases(tmp_path, held=True)
    del state.held_phases["assembly/series_stage.json"]
    calls = Counter()
    original = assembly_reports.read_object

    def counted(root, name):
        calls[name] += 1
        return original(root, name)

    monkeypatch.setattr(assembly_reports, "read_object", counted)
    state.draw()
    assert calls == {"assembly/series_stage.json": 1}


@pytest.mark.parametrize("mutation", ["add_source", "source_id", "fetch_url", "sha256"])
def test_draw_reader_refuses_changed_lineage(tmp_path: Path, mutation: str) -> None:
    state = build(tmp_path)
    reader = assembly_reports.draw_tables(state)["pub_invented"]
    if mutation == "add_source":
        state.receipts["invented_extra"] = dict(state.receipts["invented"])
        state.table_sources["pub_invented"].add("invented_extra")
    else:
        state.receipts["invented"][mutation] += "changed"
    with pytest.raises(AssemblyError, match=r"^assembly_draw_lineage_ambiguous$"):
        reader()


@pytest.mark.parametrize("gis_present", [False, True])
@pytest.mark.parametrize("probe", ["row_sources", "prefix"])
def test_draw_releases_lineage_and_prefix_before_next_phase(
    tmp_path: Path, monkeypatch, probe: str, gis_present: bool
) -> None:
    state = phases(tmp_path, held=False)
    state.table("gazetteer", [{"name": "SYN first"}], ("invented",))
    for phase in ("frame", "gis_property_singles"):
        payload = assembly_reports.read_object(tmp_path, f"assembly/{phase}.json")
        payload["tables"]["gazetteer"] = state.tables["gazetteer"]
        state.files.update(write_record(tmp_path, f"assembly/{phase}.json", payload))
    if not gis_present:
        (tmp_path / "assembly/gis_property_singles.json").unlink()
        for table in ("pub_a1", "pub_z1"):
            del state.tables[table]
    alive = []
    original_read = assembly_reports.read_object
    original_sources = assembly_reports._draw_row_sources
    original_encoder = assembly_reports.record_encoder

    class Sources(list):
        pass

    class Encoded(str):
        pass

    def sources(*args):
        result = Sources(original_sources(*args))
        if probe == "row_sources":
            alive.append(weakref.ref(result))
        return result

    def encoder():
        result = original_encoder()
        original_encode = result.encode

        def encode(value):
            encoded = Encoded(original_encode(value))
            if probe == "prefix" and value == {"name": "SYN first"}:
                alive.append(weakref.ref(encoded))
            return encoded

        result.encode = encode
        return result

    def read(root, name):
        gc.collect()
        if probe == "row_sources" or name == "assembly/series_stage.json":
            assert all(ref() is None for ref in alive), probe + " retained"
        return original_read(root, name)

    monkeypatch.setattr(assembly_reports, "read_object", read)
    monkeypatch.setattr(assembly_reports, "_draw_row_sources", sources)
    monkeypatch.setattr(assembly_reports, "record_encoder", encoder)
    state.draw()
    assert alive
    assert all(ref() is None for ref in alive)


@pytest.mark.parametrize("outcome", ["success", "step_failure", "audit_failure"])
def test_run_releases_held_metadata_on_exit(tmp_path: Path, monkeypatch, outcome: str):
    from eii_custodian.publicdata import assembly_adapters

    state = context(tmp_path)
    alive = []

    def steps(*args, **kwargs):
        state.record("frame", {"tables": {}, "row_sources": {"pub_test": ["invented"]}})
        alive.append(weakref.ref(state.held_phases["assembly/frame.json"]))
        if outcome == "step_failure":
            raise AssemblyError("assembly_output_invalid")
        return ("invented",)

    def complete(audit):
        if outcome == "audit_failure":
            raise AssemblyError("assembly_reports_invalid")

    monkeypatch.setattr(assembly_adapters, "run_steps", steps)
    monkeypatch.setattr(assembly_reports, "require_complete", complete)
    if outcome == "success":
        assert state.run() == ("invented",)
    else:
        reason = (
            "assembly_output_invalid"
            if outcome == "step_failure"
            else "assembly_reports_invalid"
        )
        with pytest.raises(AssemblyError, match="^" + reason + "$"):
            state.run()
    gc.collect()
    assert not state.held_phases
    assert all(ref() is None for ref in alive)
