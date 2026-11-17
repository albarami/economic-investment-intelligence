"""Invented native records: complete metadata, lineage and refusal contracts."""

from dataclasses import asdict, replace
from decimal import Decimal
from typing import Any

import pytest

from eii_custodian.publicdata import trade_reconciliation as tr
from eii_custodian.publicdata.fetch.decimals import DecimalRefusal

from .test_trade_reconciliation_release import cause, obstacle, portal, selection


def refusal(caught, expected):
    assert str(caught.value) == expected


def unchecked(value: Any) -> Any:
    return value


@pytest.mark.parametrize("modified", ["invented-version", None])
@pytest.mark.parametrize("period", ["2020", "2020-01"])
def test_materialize_portal_complete(tmp_path, monkeypatch, modified, period):
    calls = []

    def reader(cache, source, selected):
        calls.append((cache, source, selected))
        rows, receipt = portal(cache, source, selected)
        receipt["source_modified"] = modified
        if rows:
            rows[0]["period"] = period
        return rows, receipt

    monkeypatch.setattr(tr, "read_portal", reader)
    result = tr._materialize(tmp_path, selection(), None)
    assert calls == [
        (tmp_path, "cus_imp_2019", "a" * 64),
        (tmp_path, "cus_imp_2025", "b" * 64),
    ]
    assert len(result) == 1
    assert asdict(result[0]) == {
        "figure": {
            "input_id": "cus_imp_2019:portal:0",
            "source_id": "cus_imp_2019",
            "source_version": "invented-version" if modified else "unknown",
            "role": "portal",
            "partner": "invented-partner",
            "flow": "import",
            "year": 2020,
            "periods": (period,),
            "classification": "unknown",
            "hs_revision": "unknown",
            "product_scope": "invented-product",
            "coverage_key": "invented-coverage",
            "currency": "QAR",
            "unit": "QAR",
            "scale": "1",
            "valuation_basis": "not stated by the source",
            "value": "12.50",
            "lineage": ("a" * 64, "a" * 64, "c" * 64),
            "figure_kind": "published",
        },
        "source_table": "pub_customs_import",
        "source_row_key": "0",
        "selected_hash": "a" * 64,
        "receipt_sha256": "a" * 64,
        "binding_evidence_sha256": "c" * 64,
        "native": {
            "period": period,
            "tariff_code": "invented-product",
            "origin_iso3": "invented-origin",
            "value_qar": "12.50",
            "valuation_basis": "not stated by the source",
        },
    }


@pytest.mark.parametrize("value", [None, Decimal("2.75")])
@pytest.mark.parametrize("receipt_field", ["receipt_sha256", "member_sha256"])
def test_materialize_native_overrides(tmp_path, monkeypatch, value, receipt_field):
    def reader(cache, source, selected):
        rows, receipt = portal(cache, source, selected)
        if rows:
            rows[0].pop("value_qar")
            rows[0].update(value=value, source_version="invented-native-version")
            rows[0][receipt_field] = "d" * 64
        return rows, receipt

    monkeypatch.setattr(tr, "read_portal", reader)
    result = tr._materialize(tmp_path, selection(), None)[0]
    assert result.figure.source_version == "invented-native-version"
    assert result.figure.value == (None if value is None else "2.75")
    assert result.native["value"] == (None if value is None else "2.75")
    assert result.receipt_sha256 == "d" * 64
    assert result.figure.lineage == ("a" * 64, "d" * 64, "c" * 64)


def test_unavailable_first_input_does_not_stop(tmp_path, monkeypatch):
    p = selection()
    missing = replace(p.inputs[1], selected_hash="")
    p = replace(
        p,
        inputs=(missing, p.inputs[0]),
        obstacles=({**obstacle(), "source_id": "cus_imp_2025"},),
    )
    monkeypatch.setattr(tr, "read_portal", portal)
    assert (
        tr._materialize(tmp_path, p, None)[0].figure.input_id == "cus_imp_2019:portal:0"
    )


@pytest.mark.parametrize(
    "plant,expected",
    [
        ("unbound", "native_row_binding_missing"),
        ("currency", "binding_currency"),
        ("negative", "decimal_format"),
    ],
)
def test_materialize_refusals(tmp_path, monkeypatch, plant, expected):
    p = selection()
    if plant == "unbound":
        p = replace(p, bindings=())
    elif plant == "currency":
        p = replace(p, bindings=(replace(p.bindings[0], currency="invented-currency"),))

    def reader(cache, source, selected):
        rows, receipt = portal(cache, source, selected)
        if rows and plant == "negative":
            rows[0]["value_qar"] = "-1"
        return rows, receipt

    monkeypatch.setattr(tr, "read_portal", reader)
    with pytest.raises(DecimalRefusal if plant == "negative" else ValueError) as caught:
        tr.build_reconciliation(tmp_path, p)
    refusal(caught, expected)


@pytest.mark.parametrize("source", ["cus_imp_2019", "cus_imp_2025"])
def test_portal_reader_pipeline(tmp_path, monkeypatch, source):
    from types import SimpleNamespace

    entry = SimpleNamespace(source_id=source)
    other = SimpleNamespace(source_id="invented-other")
    raw, confirmed, contracted = (
        [{"invented": "raw"}],
        [{"invented": "confirmed"}],
        [{"invented": "contracted"}],
    )
    receipt = {"invented": "receipt"}
    monkeypatch.setattr(tr, "load_registry", lambda: (other, entry))

    def selected(cache, selected_entry, digest):
        assert (cache, selected_entry, digest) == (tmp_path, entry, "a" * 64)
        return raw, receipt

    def confirm(selected_entry, rows):
        assert selected_entry is entry and rows is raw
        return confirmed

    def contract(source_id, rows):
        assert source_id == source and rows is confirmed
        return contracted

    monkeypatch.setattr(tr, "selected_source", selected)
    monkeypatch.setattr(tr, "confirmed_rows", confirm)
    monkeypatch.setattr(tr, "contract_rows", contract)
    assert tr.read_portal(tmp_path, source, "a" * 64) == (contracted, receipt)


@pytest.mark.parametrize("kind", ["baci", "comtrade", "portal"])
def test_reader_selection_message(tmp_path, kind):
    with pytest.raises(ValueError) as caught:
        if kind == "baci":
            tr.read_baci(tmp_path, "invented")
        elif kind == "portal":
            tr.read_portal(tmp_path, "cus_imp_2019", "invented")
        else:
            tr.read_comtrade(
                tmp_path,
                unchecked(object()),
                manifest_sha256="invented",
                publisher="invented",
                licence_basis="invented",
                terms_sha256="a" * 64,
            )
    refusal(caught, "selection")


def test_comtrade_reader_arguments(tmp_path, monkeypatch):
    policy = object()
    sentinel = object()

    def assemble(cache, source, supplied_policy, **kwargs):
        assert (cache, source, supplied_policy) == (tmp_path, "un_comtrade", policy)
        assert kwargs == {
            "manifest_sha256": "a" * 64,
            "publisher": "invented-publisher",
            "licence_basis": "invented-basis",
            "terms_sha256": "b" * 64,
        }
        return sentinel

    monkeypatch.setattr(tr, "assemble", assemble)
    assert (
        tr.read_comtrade(
            tmp_path,
            unchecked(policy),
            manifest_sha256="a" * 64,
            publisher="invented-publisher",
            licence_basis="invented-basis",
            terms_sha256="b" * 64,
        )
        is sentinel
    )


def test_output_causes_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    p = replace(selection(), causes=(cause(),), obstacles=(obstacle(),))
    _, pairs = tr._outputs(tmp_path, p, None)
    assert [(r.known_cause_codes, r.cause_evidence_refs) for r in pairs] == [
        (("publication_timing",), ("d" * 64,)),
        ((), ()),
        ((), ()),
        ((), ()),
    ]
    assert tr.owner_report(p, pairs[:1]) == {
        "obstacles": [obstacle()],
        "causes": [cause()],
        "unknown_cause": True,
        "coverage_gaps": [
            {
                "partner": "invented-partner",
                "year": 2020,
                "flow": "import",
                "scope": "invented-product",
                "left_source": "cus_imp_2019",
                "right_source": "cus_imp_2025",
                "mismatch_codes": ["missing_side"],
            }
        ],
    }


def test_canonical_encoding():
    assert (
        tr._encoded({"z": ["invented", None], "a": True})
        == b'{"a":true,"z":["invented",null]}'
    )


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("invented_extra", True, "selection_schema"),
        ("confirmed", False, "selection_pending"),
        ("partners", [], "selection_scope"),
        ("partners", ["invented-partner"] * 2, "selection_scope"),
        ("partners", "invented", "selection_scope"),
        ("inputs", [{}], "selection_schema"),
        ("inputs", [], "selection_inputs"),
        ("causes", [{}], "cause_schema"),
    ],
)
def test_selection_messages(field, value, expected):
    data = asdict(selection())
    data[field] = value
    with pytest.raises(ValueError) as caught:
        tr.Selection.from_mapping(data)
    refusal(caught, expected)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "invented-other"),
        ("role", "mirror"),
        ("partner", "invented-other"),
        ("year", 2022),
        ("flow", "export"),
        ("product_scope", "invented-other"),
        ("evidence_sha256", "invented"),
    ],
)
def test_selection_binding_message(field, value):
    data = asdict(selection())
    data["bindings"][0][field] = value
    with pytest.raises(ValueError) as caught:
        tr.Selection.from_mapping(data)
    refusal(caught, "binding")


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "invented-other"),
        ("role", "mirror"),
        ("selected_hash", "invented"),
    ],
)
def test_selection_input_message(field, value):
    data = asdict(selection())
    data["inputs"][0][field] = value
    with pytest.raises(ValueError) as caught:
        tr.Selection.from_mapping(data)
    refusal(caught, "selection_inputs")


@pytest.mark.parametrize("year", [1000, 9999])
def test_selection_inclusive_year_and_flow_set(year):
    data = asdict(selection())
    data["years"] = [year]
    data["bindings"][0]["year"] = year
    data["flows"] = ["import", "export"]
    assert tr.Selection.from_mapping(data).years == (year,)


@pytest.mark.parametrize(
    "reason",
    [
        "registration",
        "sign_in",
        "robot_check",
        "paid_tier",
        "free_plan_gap",
        "unavailable",
    ],
)
def test_obstacle_closed_values(reason):
    data = asdict(selection())
    data["obstacles"] = [{**obstacle(), "reason": reason}]
    assert tr.Selection.from_mapping(data).obstacles[0]["reason"] == reason


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("price_amount", None, "price_evidence"),
        ("price_currency", None, "price_evidence"),
        ("price_amount", "-1", "price_evidence"),
        ("price_amount", "1234567.12345", "price_evidence"),
        ("price_amount", "1234567890123", "price_evidence"),
        ("price_currency", "QARA", "price_evidence"),
        ("price_currency", "QÁR", "price_evidence"),
        ("source_id", "invented-other", "obstacle_evidence"),
        ("reason", "invented", "obstacle_evidence"),
        ("evidence_sha256", "invented", "obstacle_evidence"),
    ],
)
def test_obstacle_refusal_messages(field, value, expected):
    data = asdict(selection())
    data["obstacles"] = [{**obstacle(), field: value}]
    with pytest.raises(ValueError) as caught:
        tr.Selection.from_mapping(data)
    refusal(caught, expected)


def test_missing_input_message():
    data = asdict(selection())
    data["inputs"][1]["selected_hash"] = ""
    with pytest.raises(ValueError) as caught:
        tr.Selection.from_mapping(data)
    refusal(caught, "missing_input_evidence")


def test_monthly_output_lineage(tmp_path, monkeypatch):
    p = selection()
    p = replace(
        p,
        bindings=tuple(
            replace(
                p.bindings[0],
                row_key=str(m),
                hs_revision="invented-revision",
                classification="invented-class",
            )
            for m in range(12)
        ),
    )

    def reader(cache, source, selected):
        assert cache == tmp_path
        rows, receipt = portal(cache, source, selected)
        if rows:
            rows = [
                {
                    **rows[0],
                    "period": f"2020-{m:02}",
                    "value_qar": "0.1",
                    "hs_revision": "invented-revision",
                    "classification": "invented-class",
                    "valuation_basis": "invented-basis",
                }
                for m in range(1, 13)
            ]
        return rows, receipt

    monkeypatch.setattr(tr, "read_portal", reader)
    inputs, _ = tr._outputs(tmp_path, p, None)
    aggregate = inputs[-1]
    assert len(inputs) == 13
    assert aggregate.figure.value == "1.2"
    identifier = "annual:cus_imp_2019:portal:0:cus_imp_2019:portal:1:cus_imp_2019:portal:2:cus_imp_2019:portal:3:cus_imp_2019:portal:4:cus_imp_2019:portal:5:cus_imp_2019:portal:6:cus_imp_2019:portal:7:cus_imp_2019:portal:8:cus_imp_2019:portal:9:cus_imp_2019:portal:10:cus_imp_2019:portal:11"
    assert aggregate.figure.input_id == aggregate.source_row_key == identifier
    assert aggregate.source_table == "pub_trade_comparison_input"
    assert (
        aggregate.selected_hash
        == aggregate.receipt_sha256
        == aggregate.binding_evidence_sha256
        == ""
    )
    assert aggregate.native == {
        "input_lineage_refs": [
            "cus_imp_2019:portal:0",
            "cus_imp_2019:portal:1",
            "cus_imp_2019:portal:2",
            "cus_imp_2019:portal:3",
            "cus_imp_2019:portal:4",
            "cus_imp_2019:portal:5",
            "cus_imp_2019:portal:6",
            "cus_imp_2019:portal:7",
            "cus_imp_2019:portal:8",
            "cus_imp_2019:portal:9",
            "cus_imp_2019:portal:10",
            "cus_imp_2019:portal:11",
        ]
    }


def test_build_stage_and_nested_cache(tmp_path, monkeypatch):
    cache = tmp_path / "invented-parent" / "invented-cache"
    publish = tr.publish_complete
    seen = []

    def capture(source, target, refuse):
        assert source.parent.parent == cache / "trade_reconciliation"
        assert source.parent.name.startswith(".stage-")
        seen.append(source.name)
        publish(source, target, refuse)

    def reader(supplied_cache, source, selected):
        assert supplied_cache == cache
        return portal(supplied_cache, source, selected)

    monkeypatch.setattr(tr, "publish_complete", capture)
    monkeypatch.setattr(tr, "read_portal", reader)
    digest = tr.build_reconciliation(cache, selection())
    assert seen == ["output.json", "manifest.json"]
    assert len(tr.read_reconciliation(cache, digest).inputs) == 1


def test_recomputed_output_message(tmp_path, monkeypatch):
    import hashlib
    import json

    monkeypatch.setattr(tr, "read_portal", portal)
    digest = tr.build_reconciliation(tmp_path, selection())
    directory = tmp_path / "trade_reconciliation"
    manifest = json.loads((directory / f"{digest}.manifest.json").read_bytes())
    body = b"{}"
    output_hash = hashlib.sha256(body).hexdigest()
    (directory / f"{output_hash}.json").write_bytes(body)
    manifest["output_sha256"] = output_hash
    raw = json.dumps(manifest).encode()
    selected = hashlib.sha256(raw).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(raw)
    with pytest.raises(ValueError) as caught:
        tr.read_reconciliation(tmp_path, selected)
    refusal(caught, "recomputed_output")
