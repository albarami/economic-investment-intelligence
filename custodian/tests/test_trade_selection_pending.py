"""Confirmed selection is distinct from fetched, bound comparison evidence."""

from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata import trade_reconciliation as tr

from .test_trade_reconciliation_release import portal, selection


def pending_mapping():
    data = asdict(selection())
    data["inputs"][1].update(selected_hash="", pending_fetch=True)
    return data


def test_selected_pending_fetch_roundtrip():
    selected = tr.Selection.from_mapping(pending_mapping())
    assert selected.confirmed is True
    assert selected.inputs[1].pending_fetch is True
    assert selected.inputs[1].selected_hash == ""
    assert selected.obstacles == ()
    assert tr.Selection.from_mapping(asdict(selected)) == selected


@pytest.mark.parametrize("value", ["true", 1, None])
def test_pending_flag_is_boolean(value):
    data = pending_mapping()
    data["inputs"][1]["pending_fetch"] = value
    with pytest.raises(ValueError, match=r"^selection_inputs$"):
        tr.Selection.from_mapping(data)


@pytest.mark.parametrize("plant", ["hash", "binding", "obstacle"])
def test_pending_fetch_cannot_claim_evidence(plant):
    data = pending_mapping()
    if plant == "hash":
        data["inputs"][1]["selected_hash"] = "f" * 64
    elif plant == "binding":
        data["bindings"] = [
            *data["bindings"],
            {**data["bindings"][0], "source_id": "cus_imp_2025"},
        ]
    else:
        data["obstacles"] = [
            {
                "source_id": "cus_imp_2025",
                "reason": "unavailable",
                "evidence_sha256": "e" * 64,
                "price_amount": None,
                "price_currency": None,
            }
        ]
    with pytest.raises(ValueError, match=r"^pending_input_evidence$"):
        tr.Selection.from_mapping(data)


@pytest.mark.parametrize("entrypoint", ["build", "materialize", "report"])
def test_pending_fetch_never_reads_compares_or_reports(
    tmp_path, monkeypatch, entrypoint
):
    selected = tr.Selection.from_mapping(pending_mapping())

    def forbidden(*args, **kwargs):
        pytest.fail("pending input reached a reader or comparison")

    monkeypatch.setattr(tr, "read_portal", forbidden)
    monkeypatch.setattr(tr, "read_comtrade", forbidden)
    monkeypatch.setattr(tr, "read_baci", forbidden)
    monkeypatch.setattr(tr, "all_pairs", forbidden)
    with pytest.raises(ValueError, match=r"^comparison_input_pending_fetch$"):
        if entrypoint == "build":
            tr.build_reconciliation(tmp_path, selected)
        elif entrypoint == "materialize":
            tr._materialize(tmp_path, selected, None)
        else:
            tr.owner_report(selected, ())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("plant", [{"size_cut": 1}, {"ranking": "descending_value"}])
def test_selection_refuses_size_cut_and_ranking(plant):
    with pytest.raises(ValueError, match=r"^selection_schema$"):
        tr.Selection.from_mapping({**asdict(selection()), **plant})


def test_missing_partner_year_is_never_filled(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    digest = tr.build_reconciliation(tmp_path, selection())
    result = tr.read_reconciliation(tmp_path, digest)
    assert len(result.comparisons) == 4
    assert all(row.gap is None for row in result.comparisons)
    assert all("missing_side" in row.mismatch_codes for row in result.comparisons)
    assert any(
        row.left_input_id is None and row.right_input_id is None
        for row in result.comparisons
    )


def test_owner_selection_is_confirmed_but_pending():
    selected = tr.load_selection()
    assert selected is not None
    assert selected.confirmed is True
    assert selected.years == (2019, 2020, 2021, 2022, 2023, 2024)
    assert selected.flows == ("import",)
    assert selected.partners == ("pending:all_common_partners_per_year",)
    assert selected.scopes == ("TOTAL", "pending:all_present_hs2")
    assert {
        (i.source_id, i.role): (i.selected_hash, i.pending_fetch)
        for i in selected.inputs
    } == {
        ("cus_imp_2019", "portal"): (
            "4bc253946b41f065d33e0d8431a36dd27251353aa1d35987b6985a432258924b",
            False,
        ),
        ("cus_imp_2025", "portal"): (
            "69ba1b8bd1e2db1ca3e9052a378eb08faa83870ef3a9f594534e71369e89e4c0",
            False,
        ),
        ("un_comtrade", "reporter"): ("", True),
        ("un_comtrade", "mirror"): ("", True),
        ("cepii_baci", "baci"): ("", True),
    }
    assert selected.bindings == selected.causes == selected.obstacles == ()


@pytest.mark.parametrize("field", ["partners", "scopes"])
def test_scope_directive_never_becomes_a_compared_cell(tmp_path, monkeypatch, field):
    selected = replace(
        selection(),
        bindings=(),
        **{
            field: ("pending:all_common_partners_per_year",)
            if field == "partners"
            else ("pending:all_present_hs2",)
        },
    )
    monkeypatch.setattr(
        tr, "read_portal", lambda *args: pytest.fail("unresolved scope read")
    )
    with pytest.raises(ValueError, match=r"^comparison_scope_pending_review$"):
        tr.build_reconciliation(tmp_path, selected)
    assert list(tmp_path.iterdir()) == []


def test_pending_dispatch_records_no_comparison(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.build import LOG_NAME, run_build

    selected = tr.Selection.from_mapping(pending_mapping())
    monkeypatch.setattr(tr, "read_portal", lambda *args: pytest.fail("pending read"))
    outcome = run_build(
        (),
        lambda _: pytest.fail("no network"),
        tmp_path,
        lambda: "2026-11-20T00:00:00Z",
        lambda _: None,
        reconciliation_selection=selected,
    )
    assert outcome.failure is None
    assert "trade_reconciliation" not in outcome.manifests
    assert (
        "NO_DATA trade_reconciliation comparison_input_pending_fetch" in outcome.lines
    )
    assert "comparison_input_pending_fetch" in (tmp_path / LOG_NAME).read_text()
    assert not (tmp_path / "trade_reconciliation").exists()


def test_pending_assembly_records_no_compared_output(tmp_path, monkeypatch):
    from .test_production_adapters import context

    monkeypatch.setattr(
        tr, "load_selection", lambda: tr.Selection.from_mapping(pending_mapping())
    )
    state = context(tmp_path)
    state.trade_reconciliation()
    assert not any(name.startswith("trade_reconciliation/") for name in state.files)
    import json

    record = json.loads((tmp_path / "assembly/trade_reconciliation.json").read_text())
    assert record["state"] == "NO_DATA"
    assert record["reason"] == "comparison_input_pending_fetch"
