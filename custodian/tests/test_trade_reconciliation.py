"""Verified trade input selection never discovers a latest file or contacts a source."""

import pytest


def test_selection_requires_manifest_and_closed_sources(tmp_path):
    from eii_custodian.publicdata.trade_reconciliation import read_portal

    with pytest.raises(ValueError, match="selection"):
        read_portal(tmp_path, "cus_imp_2025", "")
    with pytest.raises(ValueError, match="selection"):
        read_portal(tmp_path, "fdi_projects", "a" * 64)


def test_baci_uses_typed_selected_reader(tmp_path, monkeypatch):
    from eii_custodian.publicdata import trade_reconciliation as module

    observed = []
    sentinel = object()

    def reader(cache, selected):
        observed.append((cache, selected))
        return sentinel

    monkeypatch.setattr(module.baci_contracts, "read_selected", reader)
    assert module.read_baci(tmp_path, "a" * 64) is sentinel
    assert observed == [(tmp_path, "a" * 64)]


def test_comtrade_uses_assemble_not_price_currency(tmp_path, monkeypatch):
    from eii_custodian.publicdata import trade_reconciliation as module

    observed = []
    sentinel = object()

    def reader(cache, key, policy, **kwargs):
        observed.append((cache, key, policy, kwargs))
        return sentinel

    monkeypatch.setattr(module, "assemble", reader)
    policy = object()
    assert (
        module.read_comtrade(
            tmp_path,
            policy,
            manifest_sha256="a" * 64,
            publisher="invented-publisher",
            licence_basis="provider_terms",
            terms_sha256="b" * 64,
        )
        is sentinel
    )
    assert observed[0][1] == "un_comtrade"
    assert observed[0][3]["manifest_sha256"] == "a" * 64
