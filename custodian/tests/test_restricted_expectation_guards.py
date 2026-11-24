"""Restricted-finding contracts proved exclusively on invented temporary inputs."""

import ast
import hashlib
import inspect
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.layers import COUNTS, SCHEMAS
from eii_custodian.publicdata.review.activity import SpineError

ROOT = Path(__file__).resolve().parents[2]


def modules():
    from custodian.data_tests import local_expectations as local
    from custodian.data_tests import restricted_cases as inventory

    return local, inventory


def fixture(cache):
    from custodian.tests.test_method_cache import _write_cached_source

    local, inventory = modules()
    case = inventory.case_by_id("PUB-71")
    pins = {}
    for source in case.source_ids:
        features = []
        for zone in (69, 70):
            attrs = {}
            for field, kinds in SCHEMAS[source].items():
                attrs[field] = "invented" if str in kinds else 0
            attrs.update(ZONE_NO=zone, MUNICIPAL_CODE="invented")
            if source == "census_zone_sector":
                attrs.update(Total_Economic_active___15=100, Private=40)
            else:
                attrs[COUNTS[source][1]] = 100
            features.append({"attributes": attrs, "geometry": {"rings": []}})
        # The generic fixture writer accepts JSON payloads; no real cache is read.
        pins[source] = _write_cached_source(
            cache, source, {"count": len(features), "features": features}
        )
    (cache / "method_pins.json").write_text(json.dumps(pins))
    expected = {
        "national_private": "80",
        "national_all": "200",
        "national_1dp": "40.0",
        "zone_69_0dp": "40",
        "zone_70_0dp": "40",
    }
    folder = cache / "local_expectations"
    folder.mkdir(exist_ok=True)
    (folder / "PUB-71.json").write_text(json.dumps(expected))
    record = {
        "method": case.method,
        "version": case.version,
        "period": case.period,
        "geography": list(case.geography),
        "units": case.units,
        "expectation_origin": "independent invented worksheet",
        "source_shas": pins,
        "record_sha256": hashlib.sha256(local.canonical(expected)).hexdigest(),
        "precision": local.precision(case),
        "tolerance": dict.fromkeys(expected, "0"),
    }
    companion = {"version": "restricted.v1", "cases": {case.case_id: record}}
    save(cache, companion)
    return case, companion


def save(cache, companion):
    (cache / "local_expectations/restricted_cases.json").write_text(
        json.dumps(companion)
    )


def test_restricted_replay_and_lineage(tmp_path):
    local, _ = modules()
    case, _ = fixture(tmp_path)
    result = local.replay(tmp_path, case)
    assert result.values == {
        "national_private": "80",
        "national_all": "200",
        "national_1dp": "40.0",
        "zone_69_0dp": "40",
        "zone_70_0dp": "40",
    }
    local.check_case(tmp_path, case)
    for chain in result.lineage:
        source_chain = chain.source_chain()
        assert source_chain.table == "pub_census_zone"
        assert source_chain.method == case.method
        assert source_chain.version == case.version
        assert source_chain.dataset
        assert source_chain.retrieved == "2026-11-14"


def coverage_fixture(cache, *zones, private=None, total=None):
    from custodian.tests.test_method_cache import _write_cached_source

    case, companion = fixture(cache)
    pins = json.loads((cache / "method_pins.json").read_text())
    for source in case.source_ids:
        payload = json.loads((cache / source / (pins[source] + ".json")).read_text())
        features = payload["features"]
        for zone in zones:
            feature = next(
                (row for row in features if row["attributes"]["ZONE_NO"] == zone),
                None,
            )
            if feature is None:
                feature = {
                    "attributes": dict(features[0]["attributes"]),
                    "geometry": {"rings": []},
                }
                features.append(feature)
            attrs = feature["attributes"]
            attrs["ZONE_NO"] = zone
            if source == "census_zone_sector":
                attrs.update(Private=private, Total_Economic_active___15=total)
            elif total is None:
                attrs.update(dict.fromkeys(COUNTS[source][1:-1]))
        payload["count"] = len(features)
        pins[source] = _write_cached_source(cache, source, payload)
    (cache / "method_pins.json").write_text(json.dumps(pins))
    companion["cases"][case.case_id]["source_shas"] = pins
    save(cache, companion)
    return case


def test_restricted_null_coverage_zone(tmp_path):
    local, _ = modules()
    case = coverage_fixture(tmp_path, 71)
    expected = local.load_expectation(tmp_path, case)
    local.compare(case, local.replay(tmp_path, case).values, expected)
    local.check_case(tmp_path, case)


def test_restricted_half_null_row(tmp_path):
    local, _ = modules()
    # Paired control: both null is coverage, exactly one null is invalid.
    case = coverage_fixture(tmp_path, 71)
    local.check_case(tmp_path, case)
    for private, total in ((None, 100), (40, None)):
        case = coverage_fixture(tmp_path, 71, private=private, total=total)
        with pytest.raises(local.ExpectationError, match=r"^PUB-71:source_invalid$"):
            local.replay(tmp_path, case)
        with pytest.raises(pytest.fail.Exception, match=r"^PUB-71:source_invalid$"):
            local.check_case(tmp_path, case)


def test_restricted_target_zone_null_coverage(tmp_path):
    local, _ = modules()
    for zones in ((69,), (70,), (69, 70)):
        case = coverage_fixture(tmp_path, *zones)
        with pytest.raises(local.ExpectationError, match=r"^PUB-71:zone_missing$"):
            local.replay(tmp_path, case)
        with pytest.raises(pytest.fail.Exception, match=r"^PUB-71:zone_missing$"):
            local.check_case(tmp_path, case)
        assert local.summary_reasons(
            "FAILED invented.py::test_one - Failed: PUB-71:zone_missing\n"
            "1 failed in 0.10s",
            1,
        ) == {"PUB-71:zone_missing"}


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("missing_record", "missing_record"),
        ("unknown_case", "record_invalid"),
        ("unknown_field", "record_invalid"),
        ("missing_origin", "record_invalid"),
        ("empty_origin", "record_invalid"),
        ("nan", "record_invalid"),
        ("malformed", "record_invalid"),
        ("checksum", "record_checksum_mismatch"),
        ("source", "source_pin_mismatch"),
        ("version", "record_invalid"),
        ("precision", "record_invalid"),
        ("precision_text", "record_invalid"),
        ("tolerance", "record_invalid"),
        ("precision_bool", "record_invalid"),
        ("expected_extra", "record_invalid"),
        ("expected_missing", "record_invalid"),
        ("nontext", "record_invalid"),
        ("duplicate", "record_invalid"),
        ("companion_missing", "missing_record"),
        ("companion_extra", "record_invalid"),
        ("companion_version", "record_invalid"),
        ("companion_shape", "record_invalid"),
        ("record_missing", "missing_record"),
        ("invalid_json", "record_invalid"),
        ("pins_missing", "missing_record"),
        ("pins_digest", "source_pin_mismatch"),
        ("symlink", "path_refused"),
        ("folder_symlink", "path_refused"),
    ],
)
def test_restricted_record_plants(tmp_path, plant, reason):
    local, _ = modules()
    cache = tmp_path / "cache"
    cache.mkdir()
    case, companion = fixture(cache)
    record = companion["cases"][case.case_id]
    path = cache / "local_expectations/PUB-71.json"
    if plant == "missing_record":
        path.unlink()
    elif plant == "unknown_case":
        companion["cases"]["invented-unknown"] = record
    elif plant == "unknown_field":
        record["extra"] = "invented"
    elif plant == "missing_origin":
        del record["expectation_origin"]
    elif plant == "empty_origin":
        record["expectation_origin"] = " "
    elif plant in {"nan", "malformed"}:
        expected = json.loads(path.read_text())
        expected["national_all"] = "NaN" if plant == "nan" else "1e2"
        path.write_text(json.dumps(expected))
    elif plant == "checksum":
        record["record_sha256"] = "0" * 64
    elif plant == "source":
        record["source_shas"][case.source_key] = "0" * 64
    elif plant == "version":
        record["version"] = "invented-wrong-version"
    elif plant == "precision":
        record["precision"]["national_1dp"] = 0
    elif plant == "precision_text":
        expected = json.loads(path.read_text())
        expected["national_1dp"] = "40"
        path.write_text(json.dumps(expected))
        record["record_sha256"] = hashlib.sha256(local.canonical(expected)).hexdigest()
    elif plant == "precision_bool":
        record["precision"]["national_1dp"] = True
    elif plant in {"expected_extra", "expected_missing", "nontext", "duplicate"}:
        expected = json.loads(path.read_text())
        if plant == "expected_extra":
            expected["invented_extra"] = "1"
        elif plant == "expected_missing":
            del expected["national_all"]
        elif plant == "nontext":
            expected["national_all"] = 200
        else:
            path.write_text(json.dumps(expected)[:-1] + ',"national_all":"200"}')
        if plant != "duplicate":
            path.write_text(json.dumps(expected))
        if plant in {"expected_extra", "expected_missing"}:
            record["tolerance"] = dict.fromkeys(expected, "0")
            record["record_sha256"] = hashlib.sha256(
                local.canonical(expected)
            ).hexdigest()
    elif plant == "tolerance":
        record["tolerance"]["national_1dp"] = "1"
    elif plant == "companion_extra":
        companion["invented_extra"] = "invented"
    elif plant == "companion_version":
        companion["version"] = "invented_version"
    elif plant == "companion_shape":
        companion["cases"] = []
    elif plant == "record_missing":
        del companion["cases"][case.case_id]
    elif plant == "pins_missing":
        (cache / "method_pins.json").unlink()
    elif plant == "pins_digest":
        (cache / "method_pins.json").write_text(
            json.dumps({case.source_key: "invented_digest"})
        )
    elif plant in {"companion_missing", "invalid_json"}:
        pass
    elif plant == "symlink":
        target = tmp_path / "invented_record.json"
        path.rename(target)
        path.symlink_to(target)
    else:
        folder = cache / "local_expectations"
        target = tmp_path / "invented_folder"
        folder.rename(target)
        folder.symlink_to(target, target_is_directory=True)
    save(cache, companion)
    if plant == "companion_missing":
        (cache / "local_expectations/restricted_cases.json").unlink()
    elif plant == "invalid_json":
        path.write_text("{invented-invalid-json")
    with pytest.raises(local.ExpectationError, match=f"^PUB-71:{reason}$"):
        local.load_expectation(cache, case)


@pytest.mark.parametrize("plant", ["table", "licence", "version", "receipt", "input"])
def test_restricted_lineage_and_bytes_plants(tmp_path, plant):
    local, _ = modules()
    case, _ = fixture(tmp_path)
    entry = next(e for e in load_registry() if e.key == case.source_key)
    if plant in {"table", "licence", "version"}:
        result = local.replay(tmp_path, case)
        chain = result.lineage[0]
        with pytest.raises(ValueError):
            local.validate_lineage(
                replace(
                    chain,
                    **(
                        {"release_table": "invented_table"}
                        if plant == "table"
                        else {"licence_id": "invented_licence"}
                        if plant == "licence"
                        else {"version": "invented_version"}
                    ),
                ),
                entry,
                case,
            )
    else:
        digest = json.loads((tmp_path / "method_pins.json").read_text())[entry.key]
        suffix = ".meta.json" if plant == "receipt" else ".json"
        path = tmp_path / entry.key / (digest + suffix)
        if plant == "receipt":
            data = json.loads(path.read_text())
            data["licence_basis"] = "dataset"
            path.write_text(json.dumps(data))
        else:
            path.write_text("[]")
        with pytest.raises(local.ExpectationError, match=r"^PUB-71:source_invalid$"):
            local.replay(tmp_path, case)


def test_restricted_replay_independence(tmp_path):
    local, _ = modules()
    case, companion = fixture(tmp_path)
    before = local.replay(tmp_path, case)
    companion["cases"][case.case_id]["expectation_origin"] = "changed invented"
    save(tmp_path, companion)
    (tmp_path / "local_expectations/PUB-71.json").write_text("{}")
    assert local.replay(tmp_path, case) == before
    shutil.rmtree(tmp_path / "local_expectations")
    assert local.replay(tmp_path, case) == before
    assert tuple(inspect.signature(local.replay).parameters) == ("cache", "case")
    with pytest.raises(AssertionError, match="replay_signature"):
        replay_signature(lambda cache, case, record: None)


def replay_signature(function):
    assert tuple(inspect.signature(function).parameters) == ("cache", "case"), (
        "replay_signature"
    )


@pytest.mark.parametrize(
    "plant",
    [
        "case_id",
        "source_key",
        "method",
        "version",
        "publisher",
        "dataset",
        "fetch_url",
        "retrieved",
        "sha256",
        "licence_basis",
    ],
)
def test_restricted_lineage_required_fields(tmp_path, plant):
    local, _ = modules()
    case, _ = fixture(tmp_path)
    chain = local.replay(tmp_path, case).lineage[0]
    with pytest.raises(ValueError):
        replace(chain, **{plant: ""})
    for updates in (
        {"fetch_url": "invented-invalid-url"},
        {"retrieved": "2026-02-30"},
        {"sha256": "invented-invalid-digest"},
    ):
        with pytest.raises(ValueError):
            replace(chain, **updates)


def test_restricted_counters():
    local, _ = modules()
    from eii_custodian.publicdata.gis.layers import _parse_body

    body = json.dumps(
        {
            "layers": [
                {
                    "layer_id": 0,
                    "layer_name": "invented",
                    "geometry": "polygon",
                    "features": [{"attributes": {}}],
                }
            ]
        }
    ).encode()
    parsed = _parse_body(body)
    assert local.boundary_finding_counts(parsed) == {0: 1}
    with pytest.raises(ValueError):
        local.boundary_finding_counts((*parsed, *parsed))
    rows = [
        {
            "accident_year": "invented-period",
            "accident_time": "invented-hour",
            "total": 3,
        },
        {"accident_year": "invented-period", "accident_time": "other-hour", "total": 7},
        {
            "accident_year": "other-period",
            "accident_time": "invented-hour",
            "total": 100,
        },
    ]
    assert local.h2_hour_counts(
        rows, period="invented-period", hours=("invented-hour",), weight="total"
    ) == (3, 10)
    assert local.h2_hour_counts(
        rows, period="invented-period", hours=("invented-hour",), weight=None
    ) == (1, 2)
    with pytest.raises(ValueError):
        local.h2_hour_counts(
            [dict(rows[0], total=None)],
            period="invented-period",
            hours=("invented-hour",),
            weight="total",
        )


def test_restricted_gis_verified_bytes_and_truthful_lineage(tmp_path):
    from custodian.tests.test_method_cache import _write_cached_source

    local, inventory = modules()
    case = inventory.case_by_id("GIS-ZONES")
    digest = _write_cached_source(
        tmp_path,
        case.source_key,
        {
            "layers": [
                {
                    "layer_id": 0,
                    "layer_name": "invented",
                    "geometry": "polygon",
                    "features": [],
                }
            ]
        },
    )
    (tmp_path / "method_pins.json").write_text(json.dumps({case.source_key: digest}))
    parsed, chain = local.read_gis(tmp_path, case)
    assert local.boundary_finding_counts(parsed) == {0: 0}
    assert chain.licence_id == ""
    assert chain.release_table is None
    assert chain.dataset == "gis_boundaries"
    assert chain.sha256 == digest
    with pytest.raises(ValueError):
        chain.source_chain()
    path = tmp_path / case.source_key / (digest + ".meta.json")
    receipt = json.loads(path.read_text())
    receipt["licence_id"] = "invented-substitution"
    path.write_text(json.dumps(receipt))
    with pytest.raises(local.ExpectationError, match=r"^GIS-ZONES:source_invalid$"):
        local.read_gis(tmp_path, case)


def test_restricted_count_record_and_missing_record(tmp_path):
    local, inventory = modules()
    pub, companion = fixture(tmp_path)
    case = inventory.case_by_id("COUNT-census_zone_sector")
    record = dict(companion["cases"][pub.case_id])
    record.update(
        method=case.method,
        version=case.version,
        period=case.period,
        geography=list(case.geography),
        units=case.units,
        expected={"rows": "2"},
        precision={"rows": 0},
        tolerance={"rows": "0"},
        source_shas={case.source_key: record["source_shas"][case.source_key]},
        record_sha256=hashlib.sha256(local.canonical({"rows": "2"})).hexdigest(),
    )
    companion["cases"][case.case_id] = record
    save(tmp_path, companion)
    local.check_case(tmp_path, case)
    del companion["cases"][case.case_id]
    save(tmp_path, companion)
    with pytest.raises(
        local.ExpectationError, match=rf"^{case.case_id}:missing_record$"
    ):
        local.load_expectation(tmp_path, case)


def test_restricted_comparator():
    local, inventory = modules()
    case = inventory.case_by_id("COUNT-census_zone_sector")
    local.compare(case, {"rows": "2"}, {"rows": "2"})
    with pytest.raises(
        local.ExpectationError, match=rf"^{case.case_id}:expectation_mismatch$"
    ):
        local.compare(case, {"rows": "3"}, {"rows": "2"})
    with pytest.raises(
        local.ExpectationError, match=rf"^{case.case_id}:expectation_mismatch$"
    ):
        local.compare(case, {"rows": "2.0"}, {"rows": "2"})


def test_restricted_inventory_and_outstanding():
    _, inventory = modules()
    inventory.validate_inventory(inventory.CASES, load_registry())
    assert len({c.case_id for c in inventory.CASES}) == len(inventory.CASES)
    expected = {
        f"{c.case_id}:{c.status}" for c in inventory.CASES if c.status != "ready"
    }
    assert inventory.outstanding() == expected
    from custodian.data_tests import test_restricted_findings as real

    assert real.CASES == inventory.CASES
    assert inventory.case_by_id("C12-MTH-46").owner == "S6-T13"


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("extra", "inventory_shape"),
        ("decimal", "inventory_recipe"),
        ("place", "inventory_identifier"),
        ("status", "inventory_status"),
        ("owner", "inventory_owner"),
        ("missing", "inventory_source"),
        ("dataset", "inventory_basis"),
        ("historical_missing", "inventory_source"),
        ("duplicate", "inventory_identity"),
        ("version", "inventory_metadata"),
    ],
)
def test_restricted_inventory_plants(plant, reason):
    _, inventory = modules()
    rows = [asdict(c) for c in inventory.CASES]
    registry = load_registry()
    if plant == "extra":
        rows[0]["expected"] = "invented"
    elif plant == "decimal":
        rows[0]["recipe"] = ("3.14159",)
    elif plant == "place":
        rows[0]["selectors"] = ("Invented Free Text Place",)
    elif plant == "status":
        rows[0]["status"] = "pass"
    elif plant == "owner":
        rows = [asdict(inventory.case_by_id("C12-MTH-46"))]
        rows[0]["owner"] = ""
    elif plant == "dataset":
        rows[0]["source_ids"] = ("util_elec",)
        rows[0]["source_key"] = "util_elec"
    elif plant == "historical_missing":
        rows = [asdict(inventory.case_by_id("H2"))]
        rows[0]["source_ids"] = ("accident", "invented_missing")
    elif plant == "duplicate":
        rows.append(dict(rows[0]))
    elif plant == "version":
        rows[0]["version"] = "invented_version"
    else:
        rows[0]["source_ids"] = (rows[0]["source_key"], "invented_missing")
    with pytest.raises(ValueError, match=f"^{reason}$"):
        inventory.validate_inventory(rows, registry)


def scan(text):
    tree = ast.parse(text)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                aliases[name.asname or name.name.split(".")[0]] = name.name
        elif isinstance(node, ast.ImportFrom):
            for name in node.names:
                aliases[name.asname or name.name] = f"{node.module}.{name.name}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [n.name for n in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                assert not name.startswith(
                    ("requests", "httpx", "urllib", "http.client", "socket", "aiohttp")
                ), "network_import"
                if name.startswith("eii_custodian.publicdata.fetch"):
                    assert name in {
                        "eii_custodian.publicdata.fetch.registry",
                        "eii_custodian.publicdata.fetch.snapshots",
                    }, "acquisition_import"
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "eii_custodian.publicdata.gis.layers"
            ):
                assert not any(n.name == "read_layer" for n in node.names), (
                    "acquisition_import"
                )
        if isinstance(node, ast.Attribute):
            dotted = ast.unparse(node)
            root, _, rest = dotted.partition(".")
            expanded = aliases.get(root, root) + ("." + rest if rest else "")
            assert expanded not in {
                "os.environ",
                "os.getenv",
                "sys.argv",
                "config.getoption",
            }, "cache_override"
            assert not expanded.endswith(".read_layer"), "acquisition_import"
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            assert aliases.get(node.id, node.id) not in {
                "os.environ",
                "os.getenv",
                "sys.argv",
            }, "cache_override"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.name != "pytest_addoption", "cache_override"
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            assert node.id != "CACHE", "cache_override"


def test_restricted_import_and_override_guards():
    modules()
    folder = ROOT / "custodian/data_tests"
    for filename in (
        "restricted_cases.py",
        "local_expectations.py",
        "test_restricted_findings.py",
    ):
        scan((folder / filename).read_text())
    for path in folder.rglob("conftest.py"):
        scan(path.read_text())
    for text, reason in (
        (
            "from eii_custodian.publicdata.gis.layers import read_layer",
            "acquisition_import",
        ),
        ("import os\nCACHE = os.environ['INVENTED']", "cache_override"),
        ("from os import getenv as get\nx = get('INVENTED')", "cache_override"),
        ("import requests", "network_import"),
    ):
        with pytest.raises(AssertionError, match=reason):
            scan(text)
    addopts = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["pytest"][
        "addopts"
    ]
    assert not any("showlocals" in arg or arg == "-l" for arg in addopts)


def selections(args):
    assert not any(
        not arg.startswith("-")
        and Path("custodian/data_tests").is_relative_to(Path(arg))
        for arg in args
    ), "data_tests_selected"


def test_restricted_selection_plants():
    from run_tests import SUITES

    custodian = [s for s in SUITES if s.name.startswith("python-custodian")]
    assert [s.name for s in custodian] == [
        "python-custodian-1",
        "python-custodian-2",
        "python-custodian-3",
        "python-custodian-4",
        "python-custodian-5",
    ]
    for suite in SUITES:
        if suite.kind == "pytest":
            selections(suite.args)
    for plant in ("custodian/data_tests", "custodian"):
        with pytest.raises(AssertionError, match="data_tests_selected"):
            selections((plant,))
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "custodian/data_tests" not in workflow
    assert "./eii test" in workflow


def child_run(tmp_path, text):
    shutil.copyfile(ROOT / "conftest.py", tmp_path / "conftest.py")
    child = tmp_path / "test_invented_restricted.py"
    child.write_text(text)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(child),
            "-vv",
            "-p",
            "no:cacheprovider",
            "-c",
            str(ROOT / "pyproject.toml"),
            "--rootdir",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_restricted_wrong_value_and_safe_output(tmp_path):
    local, _ = modules()
    cache = tmp_path / "invented_cache"
    cache.mkdir()
    case, companion = fixture(cache)
    code = (
        '"""PYTEST_DONT_REWRITE"""\n'
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path.cwd()))\n"
        "from custodian.data_tests.local_expectations import check_case\n"
        "from custodian.data_tests.restricted_cases import case_by_id\n"
        "def test_invented():\n    check_case(Path(__file__).parent / 'invented_cache', case_by_id('PUB-71'))\n"
    )
    correct = child_run(tmp_path, code)
    assert correct.returncode == 0, correct.stdout + correct.stderr
    expected_path = cache / "local_expectations/PUB-71.json"
    original = expected_path.read_bytes()
    expected = json.loads(original)
    expected["national_private"] = "987654321"
    expected_path.write_text(json.dumps(expected))
    companion["cases"][case.case_id]["record_sha256"] = hashlib.sha256(
        local.canonical(expected)
    ).hexdigest()
    save(cache, companion)
    wrong = child_run(tmp_path, code)
    assert wrong.returncode == 1
    output = wrong.stdout + wrong.stderr
    assert "PUB-71:expectation_mismatch" in output
    assert "987654321" not in output
    assert local.summary_reasons(output, wrong.returncode) == {
        "PUB-71:expectation_mismatch"
    }
    # A calculated-value sentinel reaches the actual comparison boundary.
    computed = "123456789.987654321"
    computed_code = code.replace(
        "def test_invented():",
        "import custodian.data_tests.local_expectations as local\n"
        "original_replay = local.replay\n"
        "def changed(cache, case):\n"
        "    result = original_replay(cache, case)\n"
        f"    result.values['national_private'] = {computed!r}\n"
        "    return result\n"
        "local.replay = changed\n"
        "def test_invented():",
    )
    result = child_run(tmp_path, computed_code)
    assert result.returncode == 1
    assert "PUB-71:expectation_mismatch" in result.stdout + result.stderr
    assert computed not in result.stdout + result.stderr
    # Parser exceptions must also stay absent from the default traceback.
    for injected in ("invented-parser-sentinel",):
        injected_code = code.replace(
            "def test_invented():",
            "import custodian.data_tests.local_expectations as local\n"
            "def broken(*args):\n"
            f"    raise ValueError({injected!r})\n"
            "local.replay = broken\n"
            "def test_invented():",
        )
        result = child_run(tmp_path, injected_code)
        assert result.returncode == 1
        combined = result.stdout + result.stderr
        assert "PUB-71:source_invalid" in combined
        assert injected not in combined


def test_restricted_outstanding_subprocess(tmp_path):
    local, inventory = modules()
    for case in inventory.CASES:
        if case.status != "ready":
            with pytest.raises(
                pytest.fail.Exception, match=f"^{case.case_id}:{case.status}$"
            ):
                local.check_case(tmp_path, case)
    code = (
        '"""PYTEST_DONT_REWRITE"""\nimport sys\nfrom pathlib import Path\n'
        "sys.path.insert(0, str(Path.cwd()))\n"
        "from custodian.data_tests.local_expectations import check_case\n"
        "from custodian.data_tests.restricted_cases import case_by_id\n"
        "def test_outstanding():\n    check_case(Path(__file__).parent, case_by_id('C12-MTH-46'))\n"
    )
    result = child_run(tmp_path, code)
    assert result.returncode == 1
    assert "C12-MTH-46:awaiting_routine" in result.stdout + result.stderr
    assert local.summary_reasons(result.stdout + result.stderr, result.returncode) == {
        "C12-MTH-46:awaiting_routine"
    }


@pytest.mark.parametrize(
    "plant",
    ["correct", "unparsed", "error", "skipped", "xfailed", "count", "exit", "extra"],
)
def test_restricted_summary_accounting(plant):
    local, _ = modules()
    text = "FAILED invented.py::test_one - Failed: C12-MTH-46:awaiting_routine\n1 failed, 2 passed in 0.01s\n"
    code = 1
    if plant == "correct":
        assert local.summary_reasons(text, code) == {"C12-MTH-46:awaiting_routine"}
        return
    if plant == "unparsed":
        text = text.replace("C12-MTH-46:awaiting_routine", "unparsed failure")
    elif plant == "error":
        text = text.replace(
            "1 failed", "ERROR invented.py::test_two - unparsed error\n1 failed"
        )
    elif plant in {"skipped", "xfailed"}:
        text = text.replace("2 passed", "2 passed, 1 " + plant)
    elif plant == "count":
        text = text.replace("1 failed", "2 failed")
    elif plant == "extra":
        text += "FAILED invented.py::test_extra - unknown:reason\n"
    else:
        code = 0
    with pytest.raises(ValueError):
        local.summary_reasons(text, code)


@pytest.mark.parametrize(
    "line",
    [
        "FAILED invented.py::test_one",
        "FAILED invented.py::test_one - C12-MTH-46:awaiting_routine",
        "FAILED invented.py::test_one - Failed: unknown:awaiting_routine",
        "FAILED invented.py::test_one - Failed: C12-MTH-46:invented_unlisted",
        "ERROR invented.py::test_one - Failed: C12-MTH-46:awaiting_routine",
    ],
    ids=["truncated", "missing_prefix", "unknown_case", "unlisted_reason", "error"],
)
def test_restricted_summary_unparsed(line):
    local, _ = modules()
    with pytest.raises(ValueError, match=r"^summary_unparsed$"):
        local.summary_reasons(line + "\n1 failed, 2 passed in 0.01s\n", 1)


@pytest.mark.parametrize(
    ("error_name", "reason"),
    [("RuntimeError", "source_invalid"), ("SpineError", "spine_refused")],
)
def test_restricted_every_exception_is_closed(tmp_path, error_name, reason):
    local, _ = modules()
    cache = tmp_path / "invented_cache"
    cache.mkdir()
    fixture(cache)
    sentinel = "invented-sentinel-987654321"
    code = (
        '"""PYTEST_DONT_REWRITE"""\n'
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path.cwd()))\n"
        "import custodian.data_tests.local_expectations as local\n"
        "from custodian.data_tests.restricted_cases import case_by_id\n"
        "from eii_custodian.publicdata.review.activity import SpineError\n"
        f"def broken(*args):\n    raise {error_name}({sentinel!r})\n"
        "local.replay = broken\n"
        "def test_invented():\n"
        "    local.check_case(Path(__file__).parent / 'invented_cache', case_by_id('PUB-71'))\n"
    )
    result = child_run(tmp_path, code)
    output = result.stdout + result.stderr
    assert result.returncode == 1, "child_not_failed"
    assert sentinel not in output, "sentinel_leaked"
    assert local.summary_reasons(output, result.returncode) == {f"PUB-71:{reason}"}


@given(
    st.data(),
    st.sampled_from([ValueError, KeyError, TypeError, SpineError, AssertionError]),
)
def test_restricted_reason_map_is_closed(data, kind):
    from custodian.data_tests.cache import closed_reason

    local, _ = modules()
    message = data.draw(
        st.one_of(st.sampled_from(sorted(local.RESTRICTED_REASONS)), st.text())
    )
    reason = closed_reason(kind(message), local.RESTRICTED_REASONS)
    admitted = local.RESTRICTED_REASONS.get(message)
    if kind is SpineError:
        expected = "spine_refused"
    elif kind is ValueError and admitted:
        expected = admitted
    else:
        expected = "source_invalid"
    assert reason == expected
    assert re.fullmatch(r"[a-z_]+", reason)
