"""A deferred file is evidence of selection, never an active comparison source."""

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from eii_custodian.publicdata import trade_reconciliation as tr

from .test_trade_reconciliation_release import portal, selection


def deferred():
    return {
        "source_id": "cus_imp_2025",
        "role": "portal",
        "selected_hash": "d" * 64,
        "year": 2025,
        "reason": "international_coverage_and_reviewed_bindings_required",
    }


def test_owner_deferred_file_is_outside_active_inputs():
    chosen = tr.load_selection()
    assert chosen is not None
    assert all(i.source_id != "cus_imp_2025" for i in chosen.inputs)
    assert len(chosen.deferred_inputs) == 1
    assert asdict(chosen.deferred_inputs[0]) == {
        **deferred(),
        "selected_hash": "69ba1b8bd1e2db1ca3e9052a378eb08faa83870ef3a9f594534e71369e89e4c0",
    }


def test_resolved_owner_selection_never_reads_or_pairs_deferred_file(
    tmp_path, monkeypatch
):
    chosen = tr.load_selection()
    assert chosen is not None
    data = asdict(chosen)
    data.update(
        partners=["invented-partner"],
        scopes=["invented-product"],
        bindings=asdict(selection())["bindings"],
    )
    for item in data["inputs"]:
        item.update(selected_hash="a" * 64, pending_fetch=False)
    resolved = tr.Selection.from_mapping(data)
    assert resolved.comparison_block_reason() is None
    calls = []

    def deferred_reader(*args):
        # A nonempty deferred file would need an out-of-window binding.
        rows = [{"period": "2025", "value_qar": "12.50"}]
        assert rows
        pytest.fail("nonempty deferred portal reader called")

    def active_reader(cache, source, digest):
        calls.append(source)
        if source == "cus_imp_2025":
            return deferred_reader(cache, source, digest)
        return portal(cache, source, digest)

    monkeypatch.setattr(tr, "read_portal", active_reader)
    monkeypatch.setattr(tr, "read_comtrade", lambda *a, **kw: SimpleNamespace(rows=()))
    monkeypatch.setattr(
        tr,
        "read_baci",
        lambda *a: SimpleNamespace(trade=(), country=(), source_registry={}),
    )
    digest = tr.build_reconciliation(tmp_path, resolved, comtrade_policy=object())
    result = tr.read_reconciliation(tmp_path, digest, comtrade_policy=object())
    assert calls and set(calls) == {"cus_imp_2019"}
    assert result.comparisons
    assert all(
        p.left_source != "cus_imp_2025" and p.right_source != "cus_imp_2025"
        for p in result.comparisons
    )
    assert all(p.year in chosen.years for p in result.comparisons)
    assert result.manifest["selection"]["deferred_inputs"] == list(
        data["deferred_inputs"]
    )


@pytest.mark.parametrize(
    "plant",
    [
        "unknown",
        "missing",
        "duplicate",
        "active",
        "year",
        "active_year",
        "year_type",
        "source",
        "role",
        "hash",
        "hash_type",
        "reason",
        "container",
    ],
)
def test_deferred_record_is_closed_and_inactive(plant):
    data = asdict(selection())
    data["inputs"] = [
        data["inputs"][0],
        {"source_id": "cepii_baci", "role": "baci", "selected_hash": "a" * 64},
    ]
    data["deferred_inputs"] = [deferred()]
    assert tr.Selection.from_mapping(data).deferred_inputs
    record = data["deferred_inputs"][0]
    if plant == "unknown":
        record["extra"] = "invented"
    elif plant == "missing":
        del record["year"]
    elif plant == "duplicate":
        data["deferred_inputs"].append(dict(record))
    elif plant == "active":
        data["inputs"].append(
            {k: record[k] for k in ("source_id", "role", "selected_hash")}
        )
    elif plant == "year":
        record["year"] = 2020
    elif plant == "active_year":
        data["years"] = [*data["years"], 2025]
    elif plant == "year_type":
        record["year"] = "2025"
    elif plant == "source":
        record["source_id"] = "un_comtrade"
    elif plant == "role":
        record["role"] = "mirror"
    elif plant == "hash":
        record["selected_hash"] = ""
    elif plant == "hash_type":
        record["selected_hash"] = 1
    elif plant == "container":
        data["deferred_inputs"] = "invented"
    else:
        record["reason"] = "invented"
    with pytest.raises(ValueError, match=r"^deferred_input_schema$"):
        tr.Selection.from_mapping(data)
