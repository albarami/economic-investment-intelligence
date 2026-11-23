"""Same-run pin supply through the plain CLI; all source bytes are invented."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.frame.invented import invented_layer
from custodian.tests.fixtures.places.invented import place_row, write_places
from custodian.tests.method_card_pin_fixtures import (
    case,
    digest,
    methods_document,
    pending,
    write_yaml,
)
from custodian.tests.repository_root import repository_root
from custodian.tests.test_production_adapters import context
from custodian.tests.test_property_quarter import USE_MAP, _frame, _rows

from commands import build_public
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.assembly_io import write_record
from eii_custodian.publicdata.assembly_method_pins import (
    PIN_ARTIFACT_NAME,
    PIN_CONFIG_NAME,
)
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.frame.census import census_rows
from eii_custodian.publicdata.frame.layers import layer_rows
from eii_custodian.publicdata.gate_report import method_pin_gate
from eii_custodian.publicdata.method_card_validation import (
    CONFIGURATION_PINS,
    S7_DEFERRED_PINS,
    completion_evidence,
)
from eii_custodian.publicdata.review.cache_fixture import write_cached
from eii_custodian.publicdata.series.figures import contract_rows

CONFIG = "custodian/publicdata/review/s2_t09_generation_config.json"
PRIOR = [f"2024-{m:02}" for m in range(1, 13)]
LATEST = [f"2025-{m:02}" for m in range(1, 13)]
LINE = "5610:SYN input"


def _cli_diagnostic(reason):
    detail = (
        reason
        if reason == "pin_configuration_missing"
        else f"assembly  {reason} expected=verified ordered outputs observed=NO_DATA"
    )
    return (
        f"FAIL build-public: {detail}\n"
        "eii: exit 1: A check or step failed; the printed `FAIL` lines say which\n"
    )


def _assert_cli_diagnostic(diagnostic, reason):
    assert diagnostic == _cli_diagnostic(reason)


@pytest.mark.parametrize(
    "reason",
    [
        "pin_configuration_missing",
        "pin_customs_window_missing",
        "pin_c14_snapshot_missing",
        "pin_c5_basket_empty",
    ],
)
@pytest.mark.parametrize("extra", ["_secondary", "\nFAIL secondary error"])
def test_cli_diagnostic_rejects_longer_or_secondary_errors(reason, extra):
    diagnostic = _cli_diagnostic(reason).replace(reason, reason + extra, 1)
    with pytest.raises(AssertionError):
        _assert_cli_diagnostic(diagnostic, reason)


def supplied_build(tmp_path):
    root = tmp_path / "root"
    review = root / "custodian/publicdata/review"
    review.mkdir(parents=True)
    cache = root / "cache"
    entries = tuple(
        e
        for e in load_registry()
        if e.key
        in {
            "cus_imp_2019",
            "cus_imp_2025",
            "places_ovt/part-00014",
            "census_district_pop",
            "prop_sales",
        }
    )
    assert len(entries) == 5
    build = replace(
        context(cache, entries), root=root, review=review, pin_auto_supply=True
    )
    _stage_sources(build)
    _frame(review)
    shutil.copy(USE_MAP, review / "property_use_map.csv")
    build.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    build.gis_property_singles()
    _write_basket(review)
    config = _generation_config()
    write_record(root, CONFIG, config)
    return build, config


def _customs_body(source):
    raw = json.loads(
        (
            repository_root(Path(__file__))
            / "custodian/tests/fixtures/series/confirmed_shapes.json"
        ).read_bytes()
    )
    old = source == "cus_imp_2019"
    row = raw[source][0]
    row["lsn_year" if old else "year"] = "2024" if old else "2025"
    row["hs8" if old else "harmonized_system_code"] = (
        "19.02.00.00".replace(".", "") if old else 190200000001
    )
    row["value_qr" if old else "value_in_qatari_riyals"] = 10 if old else 20
    row["country_of_origin"] = None
    return json.dumps(
        [{**row, "lshhr_month" if old else "month": month} for month in range(1, 13)]
    ).encode()


def _sales_body():
    rows = []
    for year in ("2024", "2025"):
        for row in _rows("c14_worked_example.json"):
            rows.append(
                {
                    **row,
                    "registration_date": year + row["registration_date"][4:],
                    "encrypted_transaction_number": row["encrypted_transaction_number"]
                    + "-"
                    + year,
                }
            )
    return json.dumps(rows).encode()


def _stage_sources(build):
    for entry in build.entries:
        source = entry.source_id
        if source.startswith("cus_imp_"):
            body = _customs_body(source)
        elif source == "prop_sales":
            body = _sales_body()
        elif source == "census_district_pop":
            layer = invented_layer(source)
            layer["features"][0]["attributes"]["POP2020"] = 70
            body = json.dumps(layer).encode()
        else:
            place = build.root / "SYN-places.parquet"
            write_places(place, [place_row()])
            body = place.read_bytes()
        path = write_cached(build.cache, entry, body)
        build.selected[entry.key] = path.stem
        if source == "places_ovt":
            build.receipts[entry.key] = read_snapshot(
                build.cache / entry.key, path.stem
            ).sidecar
            continue
        payload = build.raw(entry)
        if source.startswith("cus_imp_"):
            build.tables.setdefault("pub_customs_import", []).extend(
                contract_rows(source, payload)
            )
            build.table_sources.setdefault("pub_customs_import", set()).add(entry.key)
        elif source == "census_district_pop":
            value = layer_rows(source, payload)[0]["POP2020"]
            rows, _ = census_rows(
                entry,
                [
                    {
                        "district_key": "SYN-district",
                        "period": "2020",
                        "indicator": "residents",
                        "value": value,
                        "unit": "persons",
                    }
                ],
                "2026-11-18T00:00:00Z",
                "pub_census_district",
            )
            build.table("pub_census_district", rows, (entry.key,))


def _write_basket(review):
    (review / "baskets.yaml").write_text(
        json.dumps(
            {
                "activities": [
                    {
                        "activity": activity,
                        "inputs": [
                            {
                                "name": "SYN input",
                                "lines": [
                                    {
                                        "code": "1902.00.00.0001",
                                        "description_en": "SYN input",
                                        "description_ar": "تجريبي",
                                    }
                                ],
                                "inclusion_reason": "SYN review",
                                "excluded_lines": [],
                                "supplier_isic": "SYN-isic",
                                "reviewer_role": "SYN reviewer",
                                "review_date": "2026-11-18",
                                "source_sha256": "a" * 64,
                            }
                        ]
                        if activity == "5610"
                        else [],
                    }
                    for activity in ("5610", "5630", "5510")
                ]
            }
        )
    )


def _generation_config():
    config = {"schema_version": 1, "pins": {}}
    for pin in CONFIGURATION_PINS:
        config["pins"][pin] = {
            "value": "SYN setting:" + pin,
            "anchor": "SYN reviewed setting",
        }
    for pin in ("c5.hhi", "c5.prior12", "c5.latest12", "c5.trend"):
        config["pins"][pin] = {
            "prior_months": PRIOR,
            "latest_months": LATEST,
            "lines": {
                LINE: {"parent_contains_excluded": False, "parent_treatment": "clean"}
            },
        }
    config["pins"]["c6.release_sha256"] = {"source_key": "places_ovt/part-00014"}
    config["pins"]["c7.district_weights"] = {
        "period": "2020",
        "indicator": "residents",
        "unit": "persons",
    }
    for year in ("2024", "2025"):
        config["pins"]["c14.medians_" + year] = {
            "crosswalk_name": "SYN North",
            "period": year,
        }
    for pin in S7_DEFERRED_PINS:
        config["pins"][pin] = {"pending_reason": "OI-283: " + pin}
    return config


def expected_rows(build, config):
    def lineage(keys, method):
        return [
            {
                **{
                    field: build.receipts[key][field]
                    for field in (
                        "source_id",
                        "sha256",
                        "publisher",
                        "licence_id",
                        "retrieved_utc",
                    )
                },
                "method_id": method,
            }
            for key in sorted(keys)
        ]

    result = []
    for pin in sorted(config["pins"]):
        refs = []
        if pin in CONFIGURATION_PINS:
            values = {"value": config["pins"][pin]["value"]}
        elif pin in S7_DEFERRED_PINS:
            values = {}
        elif pin.startswith("c5."):
            values = {
                LINE: {
                    "c5.hhi": "10000",
                    "c5.prior12": "120",
                    "c5.latest12": "240",
                    "c5.trend": "1",
                }[pin]
            }
            refs = lineage(
                ["cus_imp_2019"]
                if pin == "c5.prior12"
                else ["cus_imp_2025"]
                if pin in {"c5.hhi", "c5.latest12"}
                else ["cus_imp_2019", "cus_imp_2025"],
                "C5.supplier_metrics@v1",
            )
        elif pin == "c6.release_sha256":
            values = {"value": build.selected["places_ovt/part-00014"]}
            refs = lineage(["places_ovt/part-00014"], "C6.selected_release@v1")
        elif pin == "c7.district_weights":
            values = {"SYN-district": "70"}
            refs = lineage(["census_district_pop"], "C7.census_weights@v1")
        else:
            values = {
                "syn_north:residential:median_qar_per_m2": "15.00",
                "syn_north:residential:deal_count": 2,
            }
            refs = lineage(["prop_sales"], "C14.sale_aggregates@v1")
        result.append({"pin_id": pin, "values": values, "source_lineage": refs})
    return result


def review_expected(build, config):
    _paths, record, _, _ = case(build.root / "case")
    rows = {row["pin_id"]: row for row in expected_rows(build, config)}
    for entry in record["pins"]:
        pin = entry["pin_id"]
        if pin in S7_DEFERRED_PINS:
            pending(entry)
            entry["unpinned_reason"] = "OI-283: " + pin
        else:
            entry.update(rows[pin])
            entry["settings_sha256"] = digest((build.root / CONFIG).read_bytes())
    write_yaml(build.review / "s2_t09_source_checks.yaml", record)
    methods = build.root / "docs/07_ECONOMIC_METHODS.md"
    methods.parent.mkdir(parents=True)
    methods.write_text(methods_document(record["pins"]))
    return (
        build.review / "s2_t09_source_checks.yaml",
        build.cache / PIN_ARTIFACT_NAME,
        build.cache / PIN_CONFIG_NAME,
        methods,
    )


def plain_cli(build, monkeypatch):
    seen = []

    def run(actual):
        actual.review = build.review
        actual.selected = build.selected
        actual.receipts = build.receipts
        actual.tables = build.tables
        actual.table_sources = build.table_sources
        actual.method_pins()
        seen.append(actual)
        return ()

    monkeypatch.setattr(build_public, "load_registry", lambda: build.entries)
    monkeypatch.setattr(build_public, "CACHE_RELATIVE", "cache")
    monkeypatch.setattr(Production, "run", run)
    return build_public.run(
        build.root, {}, [], transport=lambda _: pytest.fail("network called")
    ), seen


def test_plain_cli_produces_receipt_bound_rows_and_completes_s2(tmp_path, monkeypatch):
    build, config = supplied_build(tmp_path)
    paths = review_expected(build, config)
    code, seen = plain_cli(build, monkeypatch)
    assert code == 0
    assert len(seen) == 1
    artifact = json.loads(paths[1].read_bytes())
    assert [
        {key: row[key] for key in ("pin_id", "values", "source_lineage")}
        for row in artifact["pins"]
    ] == expected_rows(build, config)
    assert json.loads(paths[2].read_bytes()) == config
    assert (
        method_pin_gate(*paths, build.entries, build.receipts)["completion_evidence"]
        is True
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("config_missing", "pin_configuration_missing"),
        ("customs_window", "pin_customs_window_missing"),
        ("c14_snapshot", "pin_c14_snapshot_missing"),
        ("empty_basket", "pin_c5_basket_empty"),
    ],
)
def test_supply_one_change_refusals(tmp_path, monkeypatch, capsys, change, reason):
    build, config = supplied_build(tmp_path)
    review_expected(build, config)
    if change == "config_missing":
        (build.root / CONFIG).unlink()
    elif change == "customs_window":
        build.tables["pub_customs_import"] = [
            r for r in build.tables["pub_customs_import"] if r["period"] != "2024-12"
        ]
    elif change == "c14_snapshot":
        del build.selected["prop_sales"]
    else:
        baskets = json.loads((build.review / "baskets.yaml").read_bytes())
        baskets["activities"][0]["inputs"] = []
        (build.review / "baskets.yaml").write_text(json.dumps(baskets))
    code, _ = plain_cli(build, monkeypatch)
    assert code == 1
    captured = capsys.readouterr()
    _assert_cli_diagnostic(captured.err, reason)
    assert captured.out == (
        ""
        if change == "config_missing"
        else f"FAIL assembly {reason} expected=verified ordered outputs observed=NO_DATA\n"
        "build-log: cache/build-log.json\n"
    )
    assert not (build.cache / PIN_ARTIFACT_NAME).exists()


@pytest.mark.parametrize(
    "change,reason",
    [
        ("config_edited", "pin_settings_hash_mismatch"),
        ("unknown_receipt", "pin_lineage_receipt_missing"),
        ("deferred_value", "pin_pending_value_forbidden"),
    ],
)
def test_consumer_one_change_refusals(tmp_path, monkeypatch, change, reason):
    build, config = supplied_build(tmp_path)
    paths = review_expected(build, config)
    if change == "config_edited":
        config["pins"]["c6.radius_m"]["anchor"] = "SYN changed after review"
        write_record(build.root, CONFIG, config)
    assert plain_cli(build, monkeypatch)[0] == 0
    if change == "config_edited":
        pass  # Only the tracked settings were edited, before this run loaded them.
    elif change == "unknown_receipt":
        del build.receipts["prop_sales"]
    else:
        value = json.loads(paths[1].read_bytes())
        next(row for row in value["pins"] if row["pin_id"] == "c6.expected_p")[
            "values"
        ] = {"value": "SYN stand-in"}
        paths[1].write_text(json.dumps(value))
    with pytest.raises(ValueError, match="^" + reason + "$"):
        completion_evidence(
            *paths, gate="S2", registry=build.entries, receipts=build.receipts
        )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("customs_source", "pin_customs_window_missing"),
        ("receipt_absent", "pin_lineage_receipt_missing"),
        ("selection_mismatch", "pin_lineage_selection_mismatch"),
        ("c5_settings", "pin_c5_settings_mismatch"),
        ("parent_review", "pin_c5_parent_review_mismatch"),
        ("c14_table_source", "pin_c14_snapshot_missing"),
        ("c14_year", "pin_c14_medians_missing"),
        ("c14_duplicate", "pin_c14_medians_duplicate"),
        ("c7_missing", "pin_c7_weights_missing"),
        ("c7_duplicate", "pin_c7_weights_duplicate"),
    ],
)
def test_adapter_refusal_branches(tmp_path, change, reason):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    assert collect_pin_rows(build, config) == expected_rows(build, config)
    if change == "customs_source":
        build.table_sources["pub_customs_import"].remove("cus_imp_2019")
    elif change == "receipt_absent":
        del build.receipts["cus_imp_2019"]
    elif change == "selection_mismatch":
        build.selected["cus_imp_2019"] = "f" * 64
    elif change == "c5_settings":
        config["pins"]["c5.trend"] = {}
    elif change == "parent_review":
        path = build.review / "baskets.yaml"
        basket = json.loads(path.read_bytes())
        basket["activities"][0]["inputs"][0]["excluded_lines"] = [
            {"code": "1902.00.00.0002", "reason": "SYN excluded"}
        ]
        path.write_text(json.dumps(basket))
    elif change == "c14_table_source":
        build.table_sources["pub_property_sale"] = set()
    elif change == "c14_year":
        build.tables["pub_property_sale"] = [
            row for row in build.tables["pub_property_sale"] if row["period"] != "2024"
        ]
    elif change == "c14_duplicate":
        build.tables["pub_property_sale"].append(
            build.tables["pub_property_sale"][0].copy()
        )
    elif change == "c7_missing":
        build.tables["pub_census_district"] = []
    else:
        build.tables["pub_census_district"].append(
            build.tables["pub_census_district"][0].copy()
        )
    with pytest.raises(AssemblyError, match="^" + reason + "$"):
        collect_pin_rows(build, config)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("schema", "pin_schema_version"),
        ("missing_pin", "pin_configuration_pins"),
        ("unknown_pin", "pin_configuration_pins"),
        ("setting_type", "pin_record_mapping"),
        ("json", "pin_json_invalid"),
        ("shape", "pin_record_fields"),
        ("whitespace", "pin_configuration_not_canonical"),
    ],
)
def test_configuration_refusal_branches(tmp_path, change, reason):
    from eii_custodian.publicdata.method_pin_config import load_generation_config

    config = _generation_config()
    path = tmp_path / CONFIG
    if change == "schema":
        config["schema_version"] = True
    elif change == "missing_pin":
        del config["pins"]["wilson.period"]
    elif change == "unknown_pin":
        config["pins"]["SYN.unknown"] = {}
    elif change == "setting_type":
        config["pins"]["wilson.period"] = []
    elif change == "shape":
        config["SYN extra"] = True
    write_record(tmp_path, CONFIG, config)
    if change == "json":
        path.write_bytes(b'{"pins":')
    elif change == "whitespace":
        path.write_bytes(path.read_bytes() + b" \n")
    with pytest.raises(ValueError, match="^" + reason + "$"):
        load_generation_config(tmp_path)


def test_tracked_configuration_withholds_missing_pack_choices(tmp_path):
    from eii_custodian.publicdata.method_pin_config import load_generation_config

    repo = repository_root(Path(__file__))
    config = load_generation_config(repo)
    build = context(tmp_path)
    build.pin_auto_supply = True
    build.pin_generation_config = config
    assert build.method_pins() == {}
    assert build.pin_pending_reason == "pin_configuration_pending"
    assert not (tmp_path / PIN_ARTIFACT_NAME).exists()
    assert {
        pin for pin, settings in config["pins"].items() if "pending_reason" in settings
    } == {
        "wilson.period",
        "c5.hhi",
        "c5.prior12",
        "c5.latest12",
        "c5.trend",
        "c6.seed",
        "c6.category_ids",
        "c6.candidate_set",
        "c7.coordinates",
        "c7.modes",
        "c7.cutoffs",
        "c7.speed_regime",
        *S7_DEFERRED_PINS,
    }


def test_automatic_rows_are_collected_again_on_the_next_invocation(tmp_path):
    from eii_custodian.publicdata.assembly import AssemblyError

    build, config = supplied_build(tmp_path)
    build.pin_generation_config = config
    build.method_pins()
    assert build.pin_rows == ()
    del build.selected["prop_sales"]
    with pytest.raises(AssemblyError, match=r"^pin_c14_snapshot_missing$"):
        build.method_pins()


@pytest.mark.parametrize(
    "change,reason",
    [
        ("c6_source", "pin_c6_release_source"),
        ("c14_period", "pin_c14_period_mismatch"),
        ("c7_indicator", "pin_c7_weight_settings"),
    ],
)
def test_card_specific_source_and_period_contracts(tmp_path, change, reason):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    if change == "c6_source":
        config["pins"]["c6.release_sha256"]["source_key"] = "cus_imp_2019"
    elif change == "c14_period":
        config["pins"]["c14.medians_2024"]["period"] = "2025"
    else:
        config["pins"]["c7.district_weights"]["indicator"] = "households"
    with pytest.raises(AssemblyError, match="^" + reason + "$"):
        collect_pin_rows(build, config)


def test_duplicate_basket_names_cannot_overwrite_a_line(tmp_path):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    path = build.review / "baskets.yaml"
    basket = json.loads(path.read_bytes())
    basket["activities"][0]["inputs"].append(
        basket["activities"][0]["inputs"][0].copy()
    )
    path.write_text(json.dumps(basket))
    with pytest.raises(AssemblyError, match=r"^pin_c5_basket_duplicate$"):
        collect_pin_rows(build, config)


@pytest.mark.parametrize("treatment", ["includes excluded lines", "withheld"])
def test_no_data_preserves_the_reviewed_parent_treatment(tmp_path, treatment):
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    path = build.review / "baskets.yaml"
    basket = json.loads(path.read_bytes())
    basket["activities"][0]["inputs"][0]["excluded_lines"] = [
        {"code": "1902.00.00.0002", "reason": "SYN excluded"}
    ]
    path.write_text(json.dumps(basket))
    for row in build.tables["pub_customs_import"]:
        if row["period"] in LATEST:
            row["value_qar"] = 0
    for pin in ("c5.hhi", "c5.prior12", "c5.latest12", "c5.trend"):
        config["pins"][pin]["lines"][LINE] = {
            "parent_contains_excluded": True,
            "parent_treatment": treatment,
        }
    rows = {row["pin_id"]: row["values"] for row in collect_pin_rows(build, config)}
    assert rows["c5.hhi"][LINE] == "NO_DATA:no_denominator"
    assert rows["c5.latest12"][LINE] == "0"
    for pin, value in (("c5.prior12", "120"), ("c5.trend", "-1")):
        assert rows[pin][LINE] == (
            "NO_DATA:includes excluded lines"
            if treatment == "withheld"
            else value + ";caveat=includes excluded lines"
        )


def test_order_and_zero_weights_do_not_change_pin_values(tmp_path):
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    before = collect_pin_rows(build, config)
    for rows in build.tables.values():
        rows.reverse()
    for row in build.tables["pub_customs_import"]:
        row["weight_kg"] = 0
    assert collect_pin_rows(build, config) == before


@pytest.mark.parametrize(
    "automatic,pending_setting", [(True, False), (True, True), (False, False)]
)
def test_automatic_phase_declares_outputs_only_when_settings_are_ready(
    tmp_path, automatic, pending_setting
):
    from eii_custodian.publicdata.assembly_inventory import INVENTORY

    build = context(tmp_path)
    build.pin_auto_supply = automatic
    build.pin_generation_config = _generation_config()
    if pending_setting:
        build.pin_generation_config["pins"]["wilson.period"] = {
            "pending_reason": "OI-283: SYN missing period"
        }
    item = next(item for item in INVENTORY if item.name == "method_pins")
    assert build._declared_outputs(item) == (
        item.outputs if automatic and not pending_setting else ()
    )


def test_empty_lineage_key_set_is_refused(tmp_path):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.method_pin_rows import source_lineage

    build, _ = supplied_build(tmp_path)
    with pytest.raises(AssemblyError, match=r"^pin_lineage_receipt_missing$"):
        source_lineage(build, (), "C5.supplier_metrics@v1")


def test_duplicate_json_setting_is_not_a_reviewed_canonical_file(tmp_path):
    from eii_custodian.publicdata.method_pin_config import load_generation_config

    write_record(tmp_path, CONFIG, _generation_config())
    path = tmp_path / CONFIG
    body = path.read_text()
    path.write_text(
        body.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    )
    with pytest.raises(ValueError, match=r"^pin_configuration_not_canonical$"):
        load_generation_config(tmp_path)


def test_absent_basket_line_data_keeps_parent_withholding(tmp_path):
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    path = build.review / "baskets.yaml"
    basket = json.loads(path.read_bytes())
    basket["activities"][0]["inputs"][0]["excluded_lines"] = [
        {"code": "1902.00.00.0002", "reason": "SYN excluded"}
    ]
    path.write_text(json.dumps(basket))
    for row in build.tables["pub_customs_import"]:
        if row["period"] in LATEST:
            row["tariff_code"] = "190200000002"
    for pin in ("c5.hhi", "c5.prior12", "c5.latest12", "c5.trend"):
        config["pins"][pin]["lines"][LINE] = {
            "parent_contains_excluded": True,
            "parent_treatment": "withheld",
        }
    rows = {row["pin_id"]: row["values"] for row in collect_pin_rows(build, config)}
    assert rows["c5.latest12"][LINE] == "NO_DATA:no_denominator"
    assert rows["c5.prior12"][LINE] == "NO_DATA:includes excluded lines"
    assert rows["c5.trend"][LINE] == "NO_DATA:includes excluded lines"


def test_zero_census_weight_and_missing_median_copy_producer_status(tmp_path):
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    build.tables["pub_census_district"][0]["value"] = 0
    row = next(
        row for row in build.tables["pub_property_sale"] if row["period"] == "2024"
    )
    row["median_price_per_m2"] = None
    row["deal_count"] = 0
    rows = {row["pin_id"]: row["values"] for row in collect_pin_rows(build, config)}
    assert rows["c7.district_weights"] == {"SYN-district": "0"}
    assert rows["c14.medians_2024"] == {
        "syn_north:residential:median_qar_per_m2": "NO_DATA",
        "syn_north:residential:deal_count": 0,
    }


@pytest.mark.parametrize("link", ["settings", "root"])
def test_tracked_configuration_refuses_symlinks(tmp_path, link):
    from eii_custodian.publicdata.method_pin_config import load_generation_config

    root = tmp_path / "SYN-root"
    write_record(root, CONFIG, _generation_config())
    if link == "settings":
        path = root / CONFIG
        target = tmp_path / "SYN-same-settings.json"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    else:
        alias = tmp_path / "SYN-root-alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    with pytest.raises(ValueError, match=r"^root_escape$"):
        load_generation_config(root)


def test_zero_prior_is_a_no_data_trend_in_the_pin_row(tmp_path):
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    for row in build.tables["pub_customs_import"]:
        if row["period"] in PRIOR:
            row["value_qar"] = 0
    rows = {row["pin_id"]: row["values"] for row in collect_pin_rows(build, config)}
    assert rows["c5.prior12"][LINE] == "0"
    assert rows["c5.latest12"][LINE] == "240"
    assert rows["c5.hhi"][LINE] == "10000"
    assert rows["c5.trend"][LINE] == "NO_DATA:no_denominator"


def test_c5_trend_windows_follow_its_exact_selected_receipts(tmp_path, monkeypatch):
    from eii_custodian.publicdata import method_pin_supplier as supplier
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    calculated = []
    serialize = supplier._calculated_values

    def capture(result):
        calculated.append(result["trend"])
        return serialize(result)

    monkeypatch.setattr(supplier, "_calculated_values", capture)
    pins = {row["pin_id"]: row for row in collect_pin_rows(build, config)}
    prior, prior_chain, _ = supplier._window_rows(build, PRIOR, "cus_imp_2019")
    latest, latest_chain, _ = supplier._window_rows(build, LATEST, "cus_imp_2025")
    (fact,) = calculated
    latest_periods = sorted({row["period"] for row in latest})
    prior_periods = sorted({row["period"] for row in prior})
    assert fact.period == latest_periods[0] + ".." + latest_periods[-1]
    assert fact.base_period == prior_periods[0] + ".." + prior_periods[-1]
    assert set(fact.sources) == {prior_chain, latest_chain}
    assert {ref["sha256"] for ref in pins["c5.trend"]["source_lineage"]} == {
        build.receipts[key]["sha256"] for key in ("cus_imp_2019", "cus_imp_2025")
    }


@pytest.mark.parametrize("window", [PRIOR, LATEST])
def test_c5_refuses_a_declared_window_missing_from_its_receipt_rows(tmp_path, window):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.method_pin_rows import collect_pin_rows

    build, config = supplied_build(tmp_path)
    next(
        row for row in build.tables["pub_customs_import"] if row["period"] == window[-1]
    )["period"] = "2023-12"
    with pytest.raises(AssemblyError, match=r"^pin_customs_window_missing$"):
        collect_pin_rows(build, config)
