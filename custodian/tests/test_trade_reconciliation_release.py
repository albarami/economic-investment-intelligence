"""Offline selected releases, comparison lineage and tampering plants."""

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata import trade_reconciliation as tr


def selection():
    return tr.Selection.from_mapping(
        {
            "confirmed": True,
            "partners": ["invented-partner", "invented-absent"],
            "years": [2020, 2021],
            "flows": ["import"],
            "scopes": ["invented-product"],
            "inputs": [
                {
                    "source_id": "cus_imp_2019",
                    "role": "portal",
                    "selected_hash": "a" * 64,
                },
                {
                    "source_id": "cus_imp_2025",
                    "role": "portal",
                    "selected_hash": "b" * 64,
                },
            ],
            "bindings": [
                {
                    "source_id": "cus_imp_2019",
                    "role": "portal",
                    "row_key": "0",
                    "partner": "invented-partner",
                    "flow": "import",
                    "year": 2020,
                    "product_scope": "invented-product",
                    "coverage_key": "invented-coverage",
                    "currency": "QAR",
                    "scale": "1",
                    "hs_revision": "unknown",
                    "classification": "unknown",
                    "evidence_sha256": "c" * 64,
                }
            ],
            "causes": [],
            "obstacles": [],
        }
    )


def portal(cache, source_id, selected):
    rows = (
        [
            {
                "period": "2020",
                "tariff_code": "invented-product",
                "origin_iso3": "invented-origin",
                "value_qar": "12.50",
                "valuation_basis": "not stated by the source",
            }
        ]
        if source_id == "cus_imp_2019"
        else []
    )
    return rows, {
        "sha256": selected,
        "publisher": "invented-publisher",
        "source_modified": "invented-version",
        "licence_basis": "owner_decision",
        "retrieved_utc": "2026-11-16T00:00:00Z",
    }


def test_selection_closed():
    p = asdict(selection())
    for plant in (
        {**p, "unknown": True},
        {**p, "years": []},
        {
            **p,
            "inputs": [
                {
                    "source_id": "fdi_projects",
                    "role": "portal",
                    "selected_hash": "a" * 64,
                }
            ],
        },
        {**p, "confirmed": False},
    ):
        with pytest.raises(ValueError):
            tr.Selection.from_mapping(plant)


def test_release_roundtrip_all_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    p = selection()
    digest = tr.build_reconciliation(tmp_path, p)
    release = tr.read_reconciliation(tmp_path, digest)
    assert len(release.inputs) == 1
    assert len(release.comparisons) == 4
    assert all(r.gap is None for r in release.comparisons)
    assert {(r.partner, r.year) for r in release.comparisons} == {
        (p, y) for p in selection().partners for y in selection().years
    }
    assert all(r.unknown_cause for r in release.comparisons)
    assert release.inputs[0].figure.value == "12.50"
    assert release.manifest["commit_allowed"] is False


@pytest.mark.parametrize("plant", ["output", "input", "binding", "cause"])
def test_reconciliation_tamper(tmp_path, monkeypatch, plant):
    monkeypatch.setattr(tr, "read_portal", portal)
    digest = tr.build_reconciliation(tmp_path, selection())
    directory = tmp_path / "trade_reconciliation"
    manifest = json.loads((directory / f"{digest}.manifest.json").read_text())
    if plant == "input":
        monkeypatch.setattr(tr, "read_portal", lambda *args: ([], {}))
    elif plant == "binding":
        manifest["selection"]["bindings"][0]["partner"] = "invented-other"
    elif plant == "cause":
        manifest["selection"]["causes"] = [{"code": "valuation", "evidence_sha256": ""}]
    else:
        data = json.loads((directory / f"{manifest['output_sha256']}.json").read_text())
        data["inputs"][0]["figure"]["value"] = "99"
        raw = json.dumps(data).encode()
        changed = hashlib.sha256(raw).hexdigest()
        (directory / f"{changed}.json").write_bytes(raw)
        manifest["output_sha256"] = changed
    raw = json.dumps(manifest).encode()
    selected = hashlib.sha256(raw).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(raw)
    with pytest.raises(ValueError):
        tr.read_reconciliation(tmp_path, selected)


def test_unbound_row_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    with pytest.raises(ValueError, match="binding"):
        tr.build_reconciliation(tmp_path, replace(selection(), bindings=()))


def test_evidenced_causes_and_owner_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    data = asdict(selection())
    data["causes"] = [
        {
            "left_source": "cus_imp_2019",
            "right_source": "cus_imp_2025",
            "partner": "invented-partner",
            "year": 2020,
            "code": "publication_timing",
            "evidence_sha256": "d" * 64,
        }
    ]
    data["obstacles"] = [
        {
            "source_id": "cus_imp_2025",
            "reason": "free_plan_gap",
            "evidence_sha256": "e" * 64,
            "price_amount": None,
            "price_currency": None,
        }
    ]
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p)
    release = tr.read_reconciliation(tmp_path, digest)
    report = release.manifest["owner_report"]
    assert report["obstacles"] == data["obstacles"]
    assert report["causes"] == data["causes"]
    assert all(r.unknown_cause for r in release.comparisons)
    assert report["unknown_cause"] is True
    assert report["coverage_gaps"]


@pytest.mark.parametrize(
    "plant", ["missing_evidence", "invented_reason", "secret_price"]
)
def test_cause_obstacle_evidence_required(plant):
    data = asdict(selection())
    data["obstacles"] = [
        {
            "source_id": "cus_imp_2025",
            "reason": "registration",
            "evidence_sha256": "e" * 64,
            "price_amount": None,
            "price_currency": None,
        }
    ]
    if plant == "missing_evidence":
        data["obstacles"][0]["evidence_sha256"] = ""
    elif plant == "invented_reason":
        data["obstacles"][0]["reason"] = "invented-key-like-secret"
    else:
        data["obstacles"][0]["price_amount"] = "invented-key-like-secret"
    with pytest.raises(ValueError) as exc:
        tr.Selection.from_mapping(data)
    assert "invented-key-like-secret" not in str(exc.value)


def test_native_baci_direction_and_units(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from eii_custodian.publicdata.baci.contracts import Country, Trade

    data = asdict(selection())
    data["inputs"] = list(data["inputs"])
    data["inputs"][0] = {
        "source_id": "cepii_baci",
        "role": "baci",
        "selected_hash": "a" * 64,
    }
    data["bindings"][0].update(
        source_id="cepii_baci",
        role="baci",
        currency="invented-currency",
        hs_revision="invented-revision",
        classification="HS",
        target_code="invented-target",
        partner_code="invented-other",
    )
    item = Trade(
        "invented-version",
        "invented-revision",
        2020,
        "invented-other",
        "invented-target",
        "invented-product",
        "12.50",
        None,
        "invented-unit",
        "invented-mass",
        "invented-currency",
        "invented-basis",
        "source_missing",
        "cepii_baci",
        "f" * 64,
    )
    countries = tuple(
        Country("cepii_baci", "invented-version", c, "invented-name", None)
        for c in ("invented-target", "invented-other")
    )
    monkeypatch.setattr(tr, "read_portal", portal)
    monkeypatch.setattr(
        tr.baci_contracts,
        "read_selected",
        lambda *args: SimpleNamespace(
            trade=(item,), country=countries, source_registry={}
        ),
    )
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p)
    release = tr.read_reconciliation(tmp_path, digest)
    assert release.inputs[0].figure.unit == "invented-unit"
    data["bindings"][0]["flow"] = "export"
    data["flows"] = ["export"]
    with pytest.raises(ValueError, match="direction"):
        tr.build_reconciliation(tmp_path, tr.Selection.from_mapping(data))


def test_native_comtrade_retains_unit_not_api_price(tmp_path, monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    from eii_custodian.publicdata.comtrade.parse import TradeRow

    data = asdict(selection())
    data["inputs"] = list(data["inputs"])
    data["inputs"][0] = {
        "source_id": "un_comtrade",
        "role": "reporter",
        "selected_hash": "a" * 64,
        "publisher": "invented-publisher",
        "licence_basis": "owner_decision",
        "terms_sha256": "b" * 64,
    }
    data["bindings"][0].update(
        source_id="un_comtrade",
        role="reporter",
        currency="invented-currency",
        hs_revision="invented-revision",
        classification="invented-class",
        target_code="invented-target",
        partner_code="invented-other",
        native_flow="invented-import",
    )
    item = TradeRow(
        "un_comtrade",
        "reporter",
        "invented-target",
        "invented-other",
        "invented-second",
        "A",
        "2020",
        "invented-import",
        "invented-class",
        "invented-revision",
        "invented-product",
        2,
        "invented-customs",
        "invented-mode",
        "invented-basis",
        "invented-measure",
        Decimal("12.50"),
        "invented-unit",
        "invented-flag",
        "invented-version",
        "f" * 64,
    )
    calls = []

    def assemble(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(rows=(item,), price_currency="invented-api-currency")

    monkeypatch.setattr(tr, "assemble", assemble)
    monkeypatch.setattr(tr, "read_portal", portal)
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p, comtrade_policy=object())
    release = tr.read_reconciliation(tmp_path, digest, comtrade_policy=object())
    assert calls
    assert release.inputs[0].figure.currency == "invented-currency"
    assert release.inputs[0].figure.unit == "invented-unit"
    data["bindings"][0]["partner_code"] = "invented-wrong"
    with pytest.raises(ValueError, match="direction"):
        tr.build_reconciliation(
            tmp_path, tr.Selection.from_mapping(data), comtrade_policy=object()
        )


def test_pending_selection_and_dispatch(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.build import run_build

    assert tr.load_selection() is None
    monkeypatch.setattr(tr, "read_portal", portal)
    outcome = run_build(
        (),
        lambda _: pytest.fail("no network"),
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        reconciliation_selection=selection(),
    )
    assert outcome.failure is None
    assert "trade_reconciliation" in outcome.manifests
    assert tr.read_reconciliation(
        tmp_path, outcome.manifests["trade_reconciliation"]
    ).inputs


def test_unavailable_input_has_evidence_and_no_reader(tmp_path, monkeypatch):
    data = asdict(selection())
    data["inputs"][1]["selected_hash"] = ""
    data["obstacles"] = [
        {
            "source_id": "cus_imp_2025",
            "reason": "free_plan_gap",
            "evidence_sha256": "e" * 64,
            "price_amount": None,
            "price_currency": None,
        }
    ]

    def available(cache, source, selected):
        assert source != "cus_imp_2025"
        return portal(cache, source, selected)

    monkeypatch.setattr(tr, "read_portal", available)
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p)
    result = tr.read_reconciliation(tmp_path, digest)
    assert len(result.comparisons) == 4
    assert result.manifest["owner_report"]["obstacles"][0]["reason"] == "free_plan_gap"
    data["obstacles"] = []
    with pytest.raises(ValueError):
        tr.Selection.from_mapping(data)


def native_selection(source, role):
    data = asdict(selection())
    data["inputs"] = list(data["inputs"])
    data["inputs"][0] = {
        "source_id": source,
        "role": role,
        "selected_hash": "a" * 64,
        "publisher": "invented-publisher",
        "licence_basis": "owner_decision",
        "terms_sha256": "b" * 64,
    }
    data["bindings"][0].update(source_id=source, role=role)
    return tr.Selection.from_mapping(data)


@pytest.mark.parametrize("plant", ["comtrade", "baci", "decimal"])
def test_dispatch_reader_failure(tmp_path, monkeypatch, plant):
    from eii_custodian.publicdata.fetch.build import LOG_NAME, run_build

    from .fixtures.comtrade.invented import invented_entry

    def forbidden(*args):
        pytest.fail("invented reconciliation contacted transport")

    entries = ()
    p = selection()
    if plant == "comtrade":
        # The native assembler is real; dispatch skips acquisition, not assembly.
        entries = (replace(invented_entry(), skip_reason="invented-cache-input"),)
        p = native_selection("un_comtrade", "reporter")
    elif plant == "baci":
        p = native_selection("cepii_baci", "baci")
        directory = tmp_path / "cepii_baci"
        directory.mkdir()
        body = b"not json"
        digest = hashlib.sha256(body).hexdigest()
        (directory / f"{digest}.manifest.json").write_bytes(body)
        p = replace(p, inputs=(replace(p.inputs[0], selected_hash=digest), p.inputs[1]))
    else:
        monkeypatch.setattr(tr, "read_portal", portal)
        assert (
            tr.read_reconciliation(tmp_path, tr.build_reconciliation(tmp_path, p))
            .inputs[0]
            .figure.value
            == "12.50"
        )

        def malformed(cache, source, selected):
            rows, receipt = portal(cache, source, selected)
            if rows:
                rows[0]["value_qar"] = "invented"
            return rows, receipt

        monkeypatch.setattr(tr, "read_portal", malformed)
    result = run_build(
        entries,
        forbidden,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        forbidden,
        reconciliation_selection=p,
    )
    assert result.failure is not None
    assert result.failure.check == "comparison_invalid"
    assert result.failure.observed == "NO_DATA"
    expected = (
        "FAIL trade_reconciliation comparison_invalid "
        "expected=verified inputs observed=NO_DATA"
    )
    assert expected in result.lines
    assert "trade_reconciliation" not in result.manifests
    assert json.loads((tmp_path / LOG_NAME).read_text())["lines"] == list(result.lines)


@pytest.mark.parametrize("body", [b"not json", b"\xff"], ids=["json", "unicode"])
def test_reconciliation_decoder(tmp_path, monkeypatch, body):
    monkeypatch.setattr(tr, "read_portal", portal)
    selected = tr.build_reconciliation(tmp_path, selection())
    assert tr.read_reconciliation(tmp_path, selected).inputs
    digest = hashlib.sha256(body).hexdigest()
    (tmp_path / "trade_reconciliation" / f"{digest}.manifest.json").write_bytes(body)
    with pytest.raises(
        ValueError, match=r"^trade_reconciliation selected_manifest_invalid$"
    ):
        tr.read_reconciliation(tmp_path, digest)


def cause():
    return {
        "left_source": "cus_imp_2019",
        "right_source": "cus_imp_2025",
        "partner": "invented-partner",
        "year": 2020,
        "code": "publication_timing",
        "evidence_sha256": "d" * 64,
    }


def obstacle():
    return {
        "source_id": "cus_imp_2019",
        "reason": "paid_tier",
        "evidence_sha256": "e" * 64,
        "price_amount": "1.50",
        "price_currency": "QAR",
    }


SELECTION_PLANTS = [
    ("year_low", ("years",), [999], "selection_year"),
    ("year_high", ("years",), [10000], "selection_year"),
    ("year_type", ("years",), ["2020"], "selection_year"),
    ("flow", ("flows",), ["transit"], "selection_flow"),
    ("cause_same", ("causes", 0, "right_source"), "cus_imp_2019", "cause_evidence"),
    ("cause_source", ("causes", 0, "left_source"), "invented-other", "cause_evidence"),
    ("cause_partner", ("causes", 0, "partner"), "invented-other", "cause_evidence"),
    ("cause_year", ("causes", 0, "year"), 2022, "cause_evidence"),
    ("cause_code", ("causes", 0, "code"), "invented", "cause_evidence"),
    ("cause_hash", ("causes", 0, "evidence_sha256"), "z" * 64, "cause_evidence"),
    ("obstacle_schema", ("obstacles", 0), {}, "obstacle_schema"),
    ("price_decimal", ("obstacles", 0, "price_amount"), "invented", "price_evidence"),
    ("price_currency", ("obstacles", 0, "price_currency"), "qar", "price_evidence"),
    (
        "unavailable_binding",
        ("inputs", 0, "selected_hash"),
        "",
        "unavailable_input_binding",
    ),
]


@pytest.mark.parametrize(
    "case,path,value,reason", SELECTION_PLANTS, ids=[p[0] for p in SELECTION_PLANTS]
)
def test_selection_plants(case, path, value, reason):
    data = asdict(selection())
    data["causes"] = [cause()]
    data["obstacles"] = [obstacle()]
    tr.Selection.from_mapping(data)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        tr.Selection.from_mapping(data)


def test_duplicate_binding_plant():
    data = asdict(selection())
    tr.Selection.from_mapping(data)
    data["bindings"] = (*data["bindings"], data["bindings"][0])
    with pytest.raises(ValueError, match=r"^duplicate_binding$"):
        tr.Selection.from_mapping(data)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("period", "2021", "binding_period"),
        ("tariff_code", "invented-other", "binding_product"),
        ("currency", "invented-other", "binding_currency"),
        ("hs_revision", "invented-other", "binding_revision"),
        ("classification", "invented-other", "binding_classification"),
        ("receipt_sha256", "xyz", "input_receipt"),
    ],
    ids=["period", "product", "currency", "revision", "classification", "receipt"],
)
def test_native_binding_plants(tmp_path, monkeypatch, field, value, reason):
    monkeypatch.setattr(tr, "read_portal", portal)
    p = selection()
    assert tr.read_reconciliation(tmp_path, tr.build_reconciliation(tmp_path, p)).inputs

    def mutated(cache, source, selected):
        rows, receipt = portal(cache, source, selected)
        if rows:
            rows[0][field] = value
        return rows, receipt

    monkeypatch.setattr(tr, "read_portal", mutated)
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        tr.build_reconciliation(tmp_path, p)


def test_portal_direction_plant(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    p = selection()
    assert tr.build_reconciliation(tmp_path, p)
    # One reviewed direction change, in both its selection and row binding.
    p = replace(p, flows=("export",), bindings=(replace(p.bindings[0], flow="export"),))
    with pytest.raises(ValueError, match=r"^binding_direction$"):
        tr.build_reconciliation(tmp_path, p)


@pytest.mark.parametrize("field", ["target_code", "partner_code"])
def test_country_dictionary_plant(tmp_path, monkeypatch, field):
    from types import SimpleNamespace

    from eii_custodian.publicdata.baci.contracts import Country, Trade

    p = native_selection("cepii_baci", "baci")
    binding = replace(
        p.bindings[0],
        target_code="invented-target",
        partner_code="invented-other",
        currency="invented-currency",
        hs_revision="invented-revision",
    )
    p = replace(p, bindings=(binding,))
    item = Trade(
        "invented-version",
        "invented-revision",
        2020,
        "invented-other",
        "invented-target",
        "invented-product",
        "12.50",
        None,
        "invented-unit",
        "invented-mass",
        "invented-currency",
        "invented-basis",
        "source_missing",
        "cepii_baci",
        "f" * 64,
    )
    countries = tuple(
        Country("cepii_baci", "invented-version", c, "invented-name", None)
        for c in ("invented-target", "invented-other")
    )
    monkeypatch.setattr(tr, "read_portal", portal)
    monkeypatch.setattr(
        tr.baci_contracts,
        "read_selected",
        lambda *args: SimpleNamespace(
            trade=(item,), country=countries, source_registry={}
        ),
    )
    assert tr.build_reconciliation(tmp_path, p)
    p = replace(p, bindings=(replace(binding, **{field: "invented-absent"}),))
    with pytest.raises(ValueError, match=r"^binding_country_dictionary$"):
        tr.build_reconciliation(tmp_path, p)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("selected", "selected_manifest"),
        ("hash", "manifest_hash"),
        ("complete", "manifest_contract"),
        ("commit", "manifest_contract"),
        ("method", "manifest_contract"),
        ("selection", "selection_hash"),
        ("output_digest", "output_hash"),
        ("output_bytes", "output_hash"),
        ("output_missing", "trade_reconciliation selected_manifest_invalid"),
        ("input_count", "output_count"),
        ("comparison_count", "output_count"),
        ("owner", "owner_report"),
        ("missing_key", "trade_reconciliation selected_manifest_invalid"),
    ],
    ids=lambda v: v,
)
def test_reconciliation_reader_plants(tmp_path, monkeypatch, plant, reason):
    monkeypatch.setattr(tr, "read_portal", portal)
    selected = tr.build_reconciliation(tmp_path, selection())
    manifest = tr.read_reconciliation(tmp_path, selected).manifest
    directory = tmp_path / "trade_reconciliation"
    if plant == "selected":
        selected = "invented"
    elif plant == "hash":
        (directory / f"{selected}.manifest.json").write_bytes(b"invented")
    elif plant.startswith("output_") and plant != "output_digest":
        path = directory / f"{manifest['output_sha256']}.json"
        if plant == "output_missing":
            path.unlink()
        else:
            path.write_bytes(b"invented")
    else:
        if plant in {"complete", "commit"}:
            manifest["complete" if plant == "complete" else "commit_allowed"] = (
                plant == "commit"
            )
        elif plant == "method":
            manifest["method"] = "invented"
        elif plant == "selection":
            manifest["selection"]["years"].reverse()
        elif plant == "output_digest":
            manifest["output_sha256"] = "xyz"
        elif plant in {"input_count", "comparison_count"}:
            manifest[plant] += 1
        elif plant == "owner":
            manifest["owner_report"]["unknown_cause"] = False
        else:
            manifest.pop("complete")
        body = json.dumps(manifest).encode()
        selected = hashlib.sha256(body).hexdigest()
        (directory / f"{selected}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        tr.read_reconciliation(tmp_path, selected)


@pytest.mark.parametrize("target", ["output", "manifest"])
def test_publish_conflict_plant(tmp_path, monkeypatch, target):
    monkeypatch.setattr(tr, "read_portal", portal)
    p = selection()
    selected = tr.build_reconciliation(tmp_path, p)
    manifest = tr.read_reconciliation(tmp_path, selected).manifest
    name = (
        f"{manifest['output_sha256']}.json"
        if target == "output"
        else f"{selected}.manifest.json"
    )
    (tmp_path / "trade_reconciliation" / name).write_bytes(b"invented-conflict")
    with pytest.raises(ValueError, match=r"^trade_reconciliation cache_integrity$"):
        tr.build_reconciliation(tmp_path, p)


def test_selection_unreadable_plant(tmp_path):
    import yaml

    path = tmp_path / "invented.yaml"
    path.write_text(yaml.safe_dump(asdict(selection())))
    assert tr.load_selection(path) == selection()
    path.write_text("[")
    with pytest.raises(
        ValueError, match=r"^trade_reconciliation selection_unreadable$"
    ):
        tr.load_selection(path)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("policy", "comtrade_policy_required"),
        ("binding", "binding_period"),
    ],
    ids=["policy", "binding"],
)
def test_dispatch_comparison_invalid(tmp_path, monkeypatch, plant, reason):
    from eii_custodian.publicdata.fetch.build import LOG_NAME, run_build

    monkeypatch.setattr(tr, "read_portal", portal)
    p = (
        native_selection("un_comtrade", "reporter")
        if plant == "policy"
        else selection()
    )
    if plant == "policy":
        from types import SimpleNamespace

        from .fixtures.comtrade.invented import invented_policy

        p = replace(p, bindings=())
        monkeypatch.setattr(
            tr, "assemble", lambda *args, **kwargs: SimpleNamespace(rows=())
        )
        assert tr.build_reconciliation(tmp_path, p, comtrade_policy=invented_policy())
    else:
        assert tr.build_reconciliation(tmp_path, p)
        p = replace(p, bindings=(replace(p.bindings[0], year=2021),))
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        tr.build_reconciliation(tmp_path, p)
    result = run_build(
        (),
        lambda _: pytest.fail("no network"),
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        reconciliation_selection=p,
    )
    assert result.failure is not None
    assert result.failure.check == "comparison_invalid"
    assert result.failure.observed == "NO_DATA"
    assert (
        "FAIL trade_reconciliation comparison_invalid expected=verified inputs observed=NO_DATA"
    ) in result.lines
    assert json.loads((tmp_path / LOG_NAME).read_text())["lines"] == list(result.lines)
