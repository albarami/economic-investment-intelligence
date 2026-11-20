"""Invented BACI and Comtrade native rows, preserving their distinct contracts."""

from dataclasses import asdict, replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from eii_custodian.publicdata import trade_reconciliation as tr
from eii_custodian.publicdata.baci.contracts import Country, Trade
from eii_custodian.publicdata.comtrade.parse import TradeRow

from .test_trade_reconciliation_release import native_selection, portal
from .test_trade_reconciliation_survivors import refusal, unchecked


@pytest.mark.parametrize("flow", ["import", "export"])
def test_baci_native_metadata(tmp_path, monkeypatch, flow):
    p = native_selection("cepii_baci", "baci")
    binding = replace(
        p.bindings[0],
        target_code="invented-target",
        partner_code="invented-partner-code",
        flow=flow,
        currency="invented-currency",
        hs_revision="invented-revision",
    )
    p = replace(p, flows=(flow,), bindings=(binding,))
    item = Trade(
        source_version="invented-native-version",
        hs_revision="invented-revision",
        year=2020,
        exporter_code="invented-partner-code"
        if flow == "import"
        else "invented-target",
        importer_code="invented-target"
        if flow == "import"
        else "invented-partner-code",
        hs_code="invented-product",
        value="2.75",
        quantity=None,
        value_unit="invented-unit",
        quantity_unit="invented-mass",
        currency="invented-currency",
        valuation_basis="invented-basis",
        quantity_status="source_missing",
        source_id="cepii_baci",
        member_sha256="f" * 64,
    )
    countries = tuple(
        Country("cepii_baci", "invented-native-version", code, "invented-name", None)
        for code in ("invented-target", "invented-partner-code")
    )

    def reader(cache, selected):
        assert (cache, selected) == (tmp_path, "a" * 64)
        return SimpleNamespace(trade=(item,), country=countries, source_registry={})

    monkeypatch.setattr(tr, "read_baci", reader)
    monkeypatch.setattr(tr, "read_portal", portal)
    result = tr._materialize(tmp_path, p, None)[0]
    assert result.source_table == "pub_baci_trade"
    assert result.source_row_key == "0"
    assert result.selected_hash == "a" * 64
    assert result.receipt_sha256 == "f" * 64
    assert result.binding_evidence_sha256 == "c" * 64
    assert result.native == asdict(item)
    assert result.figure.source_version == "invented-native-version"
    assert result.figure.input_id == "cepii_baci:baci:0"
    assert result.figure.lineage == ("a" * 64, "f" * 64, "c" * 64)
    assert result.figure.unit == "invented-unit"
    assert result.figure.value == "2.75"
    assert result.figure.flow == flow
    wrong = replace(binding, flow="export" if flow == "import" else "import")
    with pytest.raises(ValueError) as caught:
        tr.build_reconciliation(
            tmp_path, replace(p, flows=(wrong.flow,), bindings=(wrong,))
        )
    refusal(caught, "binding_direction")


@pytest.mark.parametrize("role", ["reporter", "mirror"])
def test_comtrade_native_metadata(tmp_path, monkeypatch, role):
    p = native_selection("un_comtrade", role)
    binding = replace(
        p.bindings[0],
        target_code="invented-target",
        partner_code="invented-partner-code",
        native_flow="invented-flow",
        currency="invented-currency",
        hs_revision="invented-revision",
        classification="invented-class",
    )
    p = replace(p, bindings=(binding,))
    item = TradeRow(
        "un_comtrade",
        role,
        "invented-target" if role == "reporter" else "invented-partner-code",
        "invented-partner-code" if role == "reporter" else "invented-target",
        "invented-second",
        "A",
        "2020",
        "invented-flow",
        "invented-class",
        "invented-revision",
        "invented-product",
        2,
        "invented-customs",
        "invented-mode",
        "invented-basis",
        "invented-measure",
        Decimal("2.75"),
        "invented-unit",
        "invented-flag",
        "invented-native-version",
        "f" * 64,
    )
    policy = object()

    def reader(cache, supplied_policy, **kwargs):
        assert cache == tmp_path and supplied_policy is policy
        assert kwargs == {
            "manifest_sha256": "a" * 64,
            "publisher": "invented-publisher",
            "licence_basis": "owner_decision",
            "terms_sha256": "b" * 64,
        }
        return SimpleNamespace(
            rows=(item, replace(item, series_role="invented-excluded"))
        )

    monkeypatch.setattr(tr, "read_comtrade", reader)
    monkeypatch.setattr(tr, "read_portal", portal)
    result = tr._materialize(tmp_path, p, unchecked(policy))
    assert len(result) == 1
    value = result[0]
    assert value.source_table == "pub_comtrade_trade"
    assert value.figure.source_version == "invented-native-version"
    assert value.figure.role == role
    assert value.figure.value == "2.75"
    assert value.figure.unit == "invented-unit"
    assert value.figure.lineage == ("a" * 64, "f" * 64, "c" * 64)
    assert value.native == {**asdict(item), "value": "2.75"}
    assert value.receipt_sha256 == "f" * 64
    bad = replace(p, bindings=(replace(binding, partner_code="invented-wrong"),))
    with pytest.raises(ValueError) as caught:
        tr.build_reconciliation(tmp_path, bad, comtrade_policy=unchecked(policy))
    refusal(caught, "binding_direction")


@pytest.mark.parametrize(
    "code", ["valuation", "classification", "coverage", "revision"]
)
def test_cause_code_values(code):
    from .test_trade_reconciliation_release import cause, selection

    data = asdict(selection())
    data["causes"] = [{**cause(), "code": code}]
    assert tr.Selection.from_mapping(data).causes[0]["code"] == code


def test_unused_binding_message(tmp_path, monkeypatch):
    from .test_trade_reconciliation_release import selection

    monkeypatch.setattr(tr, "read_portal", lambda *args: ([], {}))
    with pytest.raises(ValueError) as caught:
        tr.build_reconciliation(tmp_path, selection())
    refusal(caught, "unused_binding")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1" * 1001, "decimal_total_digits"),
        ("0." + "1" * 1001, "decimal_fractional_digits"),
    ],
)
def test_native_decimal_limits(tmp_path, monkeypatch, value, expected):
    from eii_custodian.publicdata.fetch.decimals import DecimalRefusal

    from .test_trade_reconciliation_release import selection

    def reader(cache, source, selected):
        rows, receipt = portal(cache, source, selected)
        if rows:
            rows[0]["value_qar"] = value
        return rows, receipt

    monkeypatch.setattr(tr, "read_portal", reader)
    with pytest.raises(DecimalRefusal) as caught:
        tr.build_reconciliation(tmp_path, selection())
    refusal(caught, expected)


def test_default_selection():
    selected = tr.load_selection()
    assert selected is not None
    assert selected.confirmed is True
    assert selected.comparison_block_reason() == "comparison_input_pending_fetch"


def test_utf8_selection_under_ascii_locale(tmp_path):
    import locale

    import yaml

    from .test_trade_reconciliation_release import selection

    data = asdict(selection())
    data["partners"] = ["invented-é"]
    data["bindings"][0]["partner"] = "invented-é"
    path = tmp_path / "invented.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    previous = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, "C")
        assert tr.load_selection(path).partners == ("invented-é",)
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)


def test_default_selection_layout(tmp_path, monkeypatch):
    package = tmp_path / "invented-package"
    directory = package / "publicdata"
    directory.mkdir(parents=True)
    (directory / "trade_reconciliation.yaml").write_text(
        "confirmed: false\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        tr,
        "__file__",
        str(package / "src/eii_custodian/publicdata/trade_reconciliation.py"),
    )
    assert tr.load_selection() is None
