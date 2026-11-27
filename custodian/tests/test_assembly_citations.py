"""Citation receipt handoff at the assembly/completeness consumer, invented only."""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, receipt
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata import completeness as c
from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_io import local
from eii_custodian.publicdata.fetch.receipts import cache_directory, commit_citation
from eii_custodian.publicdata.review.cache_fixture import write_cached


def fixture(tmp_path):
    row = entry("invented_citation", kind="citation_only", release_tables=())
    anchor = entry("invented_snapshot")
    digest = write_cached(tmp_path, anchor, b"[]").stem
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({anchor.key: digest}))
    sidecar = {**receipt(row), "sha256": "CITATION_ONLY"}
    assert local(tmp_path, row.key + "/citation.json") == (
        cache_directory(tmp_path, row.key) / "citation.json"
    )
    commit_citation(cache_directory(tmp_path, row.key), sidecar)
    return row, sidecar, context(tmp_path, (anchor, row))


def check(row, receipts):
    return c.check(
        entries=(row,),
        pack=c.Pack({row.source_id: ()}, frozenset()),
        inventory={row.source_id: ()},
        catalogue=set(),
        receipts=receipts,
        outputs={},
        absences={},
        cached_source_ids=(),
    )


def missing(row, receipts):
    assert {
        "id": row.source_id,
        "state": "failed",
        "reason": "source_receipt_missing: missing or invalid receipt",
    } in check(row, receipts)


def test_valid_citation_reaches_completeness_unchanged(tmp_path):
    row, sidecar, state = fixture(tmp_path)
    missing(row, {})
    state.reviewed_selections()
    assert state.receipts[row.key] == sidecar
    assert {"id": row.source_id, "state": "in use", "reason": ""} in check(
        row, {row.key: state.receipts[row.key]}
    )


def test_licence_drift_is_registered_but_still_refused(tmp_path):
    row, sidecar, state = fixture(tmp_path)
    sidecar["licence_id"] = "Invented different licence"
    commit_citation(cache_directory(tmp_path, row.key), sidecar)
    state.reviewed_selections()
    assert state.receipts[row.key] == sidecar
    missing(row, {row.key: state.receipts[row.key]})


def test_absent_citation_keeps_existing_completeness_failure(tmp_path):
    row, _, state = fixture(tmp_path)
    (cache_directory(tmp_path, row.key) / "citation.json").unlink()
    state.reviewed_selections()
    assert row.key not in state.receipts
    missing(row, {})


@pytest.mark.parametrize("field", ["key", "source_id"])
def test_wrong_lineage_refuses_exact_reason(tmp_path, field):
    row, sidecar, state = fixture(tmp_path)
    sidecar[field] = "invented_other"
    commit_citation(cache_directory(tmp_path, row.key), sidecar)
    with pytest.raises(AssemblyError, match=r"^assembly_lineage_missing$"):
        state.reviewed_selections()


@pytest.mark.parametrize("body", [b"{", b"[]", b"\xff"])
def test_unreadable_object_refuses_exact_reason(tmp_path, body):
    row, _, state = fixture(tmp_path)
    (cache_directory(tmp_path, row.key) / "citation.json").write_bytes(body)
    with pytest.raises(AssemblyError, match=r"^assembly_citation_invalid$"):
        state.reviewed_selections()


@pytest.mark.parametrize(
    "change", [{"kind": "besttime"}, {"skip_reason": "page_not_served"}]
)
def test_excluded_rows_never_read_citation(tmp_path, change, monkeypatch):
    row, _, state = fixture(tmp_path)
    state.entries = (state.entries[0], replace(row, **change))
    from eii_custodian.publicdata import assembly_adapters

    original = assembly_adapters.read_object

    def read(root, name):
        assert name != "citation.json", "excluded citation was read"
        return original(root, name)

    monkeypatch.setattr(assembly_adapters, "read_object", read)
    state.reviewed_selections()
    assert row.key not in state.receipts


@settings(deadline=None)
@given(
    st.one_of(
        st.none(), st.booleans(), st.integers(), st.text(), st.lists(st.integers())
    )
)
def test_every_non_object_json_refuses(tmp_path_factory, value):
    root = tmp_path_factory.mktemp("citation")
    row, _, state = fixture(root)
    (cache_directory(root, row.key) / "citation.json").write_text(json.dumps(value))
    with pytest.raises(AssemblyError, match=r"^assembly_citation_invalid$"):
        state.reviewed_selections()


def test_unreadable_file_refuses_exact_reason(tmp_path):
    row, _, state = fixture(tmp_path)
    path = cache_directory(tmp_path, row.key) / "citation.json"
    path.unlink()
    path.mkdir()
    with pytest.raises(AssemblyError, match=r"^assembly_citation_invalid$"):
        state.reviewed_selections()
