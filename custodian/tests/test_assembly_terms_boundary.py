"""OI-211: INVENTED rows across the assembly boundary, never live-source proof."""

import json
from collections import defaultdict
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_io import bound_files, read_object, write_record
from eii_custodian.publicdata.assembly_reports import require_complete
from eii_custodian.publicdata.fetch.registry import (
    LICENCE_BASES,
    TERMS_READ_ON_PENDING,
    TERMS_WORDS_PENDING,
    load_registry,
)
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.review.cache_fixture import write_cached

TERMS_CASES = (
    ("INVENTED unrestricted reuse", "2026-11-20"),
    ("INVENTED reuse prohibited; permission required", "2026-11-20"),
    (TERMS_WORDS_PENDING, TERMS_READ_ON_PENDING),
    ("", ""),
)
BASES = tuple(sorted(LICENCE_BASES))


@pytest.fixture
def boundary_registry(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import registry

    rows = load_registry()
    # This boundary fixture has no forecast-series confirmation. Leave that
    # unrelated gate pending instead of claiming a held live-series selection.
    write_record(tmp_path, "INVENTED_registry.json", {"forecast_series": []})
    monkeypatch.setattr(
        registry, "registry_path", lambda: tmp_path / "INVENTED_registry.json"
    )
    return rows


def terms_fields(basis, words, read_on):
    return dict(
        licence_basis=basis,
        decision_record="0026" if basis == "owner_decision" else "",
        terms_words=words,
        terms_read_on=read_on,
    )


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize(("words", "read_on"), TERMS_CASES)
def test_every_admitted_registry_slot_reaches_assembly_whatever_terms(
    tmp_path: Path, boundary_registry, basis, words, read_on
) -> None:
    # Keep only registry identities/contracts. No publisher, terms, source value
    # or real receipt is copied into this INVENTED boundary input.
    originals = boundary_registry
    rows = tuple(
        entry(
            source=row.source_id,
            key=row.key,
            slug=row.slug,
            kind=row.kind,
            release_tables=row.release_tables,
            caveat_keys=row.caveat_keys,
            skip_reason=row.skip_reason,
            **terms_fields(basis, words, read_on),
        )
        for row in originals
    )
    state = context(tmp_path, rows)
    expected = defaultdict(list)
    sources = defaultdict(list)
    admitted = {row.key for row in rows if not row.skip_reason}
    assert admitted
    for row in rows:
        if row.key not in admitted:
            continue
        state.receipts[row.key] = receipt(row)
        if row.kind == "citation_only":
            state.receipts[row.key]["sha256"] = "CITATION_ONLY"
        for table in row.release_tables:
            expected[table].append(
                {"source_key": row.key, "name": "INVENTED complete payload"}
            )
            sources[table].append(row.key)
    for table, payload in expected.items():
        state.table(table, payload, sources[table])
    from custodian.tests.test_s2_t29_awards import profile
    from custodian.tests.test_s2_t29_awards import row as award_row

    from eii_custodian.publicdata.fetch.award_checks import check_awards

    awards = [award_row(index) for index in range(30)]
    lookup = {item["report_url"]: item for item in awards}
    state.receipts["awards_owner_scrape"].update(
        award_check=check_awards(awards, profile(), state.seed, lookup.__getitem__),
        registration_double_space_only=0,
    )
    outputs = state.record(
        "gis_property_singles",
        {"tables": state.tables, "source_tables": state.source_tables},
    )
    outputs.update(state.final_audit())
    bound_files(tmp_path, outputs)
    stored = read_object(tmp_path, "assembly/gis_property_singles.json")
    assert stored["tables"] == dict(expected)
    assert set(stored["source_chain"]) == admitted
    audit = read_object(tmp_path, "assembly/final_audit.json")
    assert {
        row["id"] for row in audit["completeness"] if row["state"] == "in use"
    } == admitted
    # These invented boundary rows do not satisfy the unrelated live evidence,
    # missing table contracts or missing absence caveats. Preserve the gate.
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        require_complete(audit)
    for row in rows:
        if row.key in admitted:
            assert set(stored["source_tables"].get(row.key, ())) == set(
                row.release_tables
            )
        assert next(term for term in audit["terms"] if term["id"] == row.key) == {
            "id": row.key,
            **terms_fields(basis, words, read_on),
            "own_words_state": "pending",
        }


def bank_assembly(tmp_path, basis, words, read_on, *, absent=None):
    row = entry(
        source="bank_credit_act",
        release_tables=("pub_bank_credit",),
        **terms_fields(basis, words, read_on),
    )
    # INVENTED source-shaped inputs go through the actual credit parser,
    # selected snapshot reader, assembly adapter, draw and report writer.
    raw = [
        {
            "year": "2026",
            "economic_activity": f"INVENTED activity {index}",
            "lnsht_lqtsdy": "INVENTED activity",
            "value": index,
        }
        for index in range(25)
    ]
    write_cached(tmp_path, row, json.dumps(raw).encode())
    state = context(tmp_path, (row,) if absent is None else (row, absent))
    state.reviewed_selections()
    state.frame_result = FrameResult({"grid_cell": []}, [], {})
    state.gis_property_singles()
    state.final_audit()
    write_record(tmp_path, "assembly/build.json", {"figure_seed": state.seed})
    state.draw()
    outputs = state.reports()
    bound_files(tmp_path, outputs)
    return state, row, raw


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize(("words", "read_on"), TERMS_CASES)
def test_actual_producer_rows_and_terms_survive_through_final_reports(
    tmp_path: Path, boundary_registry, basis, words, read_on
) -> None:
    state, row, raw = bank_assembly(tmp_path, basis, words, read_on)
    stored = read_object(tmp_path, "assembly/gis_property_singles.json")
    assert stored["tables"]["pub_bank_credit"] == [
        {
            "activity_key": item["economic_activity"],
            "period": item["year"],
            "value": f"{item['value']}.00",
            "unit": None,
        }
        for item in raw
    ]
    assert stored["source_chain"][row.key]["sha256"] == state.selected[row.key]
    complete = json.loads((tmp_path / "assembly/s2_t08_completeness.json").read_text())
    assert [item for item in complete if item["id"] == row.key] == [
        {"id": row.key, "state": "in use", "reason": ""}
    ]
    terms = json.loads((tmp_path / "assembly/s2_t08_terms.json").read_text())
    assert terms == [
        {
            "id": row.key,
            **terms_fields(basis, words, read_on),
            "own_words_state": "pending",
        }
    ]
    figures = read_object(tmp_path, "assembly/draw_values.json")["figures"]
    assert len(figures) == 20
    for figure in figures:
        index = int(figure["figure_id"].split(":")[1])
        assert figure["source_id"] == row.source_id
        assert figure["value"] == f"{raw[index]['value']}.00"
        assert "snapshot=" + state.selected[row.key] in figure["filter"]


@pytest.mark.parametrize(
    "reason",
    (
        "not_fetched",
        "file_unconfirmed",
        "direct_url_unconfirmed",
        "schema_unconfirmed",
        "check_failed",
        "visitor_access_unavailable",
        "partition_byte_bound_unconfirmed",
    ),
)
def test_technical_absence_reaches_final_report_with_exact_reason_and_caveat(
    tmp_path: Path, boundary_registry, reason
) -> None:
    absent = entry(
        source="gis_zoning",
        release_tables=("pub_zoning",),
        caveat_keys=("INVENTED_technical_caveat",),
        skip_reason=reason,
        **terms_fields("owner_decision", TERMS_WORDS_PENDING, TERMS_READ_ON_PENDING),
    )
    state, _, _ = bank_assembly(
        tmp_path,
        "owner_decision",
        TERMS_WORDS_PENDING,
        TERMS_READ_ON_PENDING,
        absent=absent,
    )
    complete = json.loads((tmp_path / "assembly/s2_t08_completeness.json").read_text())
    assert [item for item in complete if item["id"] == absent.key] == [
        {
            "id": absent.key,
            "state": "NO_DATA",
            "reason": reason,
            "caveat": "INVENTED_technical_caveat",
        }
    ]
    assert absent.key not in state.receipts
    assert absent.key not in state.source_tables
    assert "pub_zoning" not in state.tables
    stored = read_object(tmp_path, "assembly/gis_property_singles.json")
    assert absent.key not in stored["source_chain"]
    assert "pub_zoning" not in stored["tables"]
    terms = json.loads((tmp_path / "assembly/s2_t08_terms.json").read_text())
    assert next(item for item in terms if item["id"] == absent.key) == {
        "id": absent.key,
        **terms_fields("owner_decision", TERMS_WORDS_PENDING, TERMS_READ_ON_PENDING),
        "own_words_state": "pending",
    }


@pytest.mark.parametrize(
    ("reason", "caveats", "failure"),
    (
        ("schema_unconfirmed", (), "source_absence_reason_missing"),
        (
            "INVENTED terms prohibit reuse",
            ("INVENTED_technical_caveat",),
            "source_absence_terms_forbidden",
        ),
    ),
)
def test_absence_without_caveat_or_based_on_terms_still_fails_the_report(
    tmp_path: Path, boundary_registry, reason, caveats, failure
) -> None:
    absent = entry(
        source="gis_zoning",
        release_tables=("pub_zoning",),
        skip_reason=reason,
        caveat_keys=caveats,
    )
    state, _, _ = bank_assembly(
        tmp_path, "dataset", "INVENTED terms", "2026-11-20", absent=absent
    )
    complete = json.loads((tmp_path / "assembly/s2_t08_completeness.json").read_text())
    assert [item for item in complete if item["id"] == absent.key] == [
        {"id": absent.key, "state": "failed", "reason": failure}
    ]
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        require_complete(state.audit)
