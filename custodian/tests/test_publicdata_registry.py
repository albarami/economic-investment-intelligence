"""Registry completeness, licence basis, nightly flag and the safe loader."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root

import eii_custodian.publicdata.fetch.registry as registry_module
from eii_custodian.publicdata.fetch.allowlist import (
    ALLOWED_HOSTS,
    NAMED_INVESTMENT_HOSTS,
    NAMED_PLACES_HOST,
    NAMED_PORTAL_HOSTS,
    approve,
)
from eii_custodian.publicdata.fetch.registry import (
    BANNED_SOURCE_IDS,
    Entry,
    RegistryError,
    load_registry,
    nightly_blocked,
    read_yaml,
    registry_path,
)
from eii_custodian.publicdata.fetch.seam import SCAN_ROOTS, opener_hits, scan_tree

FAMILY_COUNTS = {
    "prop_resi_units": 1,
    "visits_museum": 1,
    "visits_phcc": 1,
    "permits_muni": 10,
    "est_size_act": 7,
    "mfg_industry": 21,
    "trade_wr": 1,
    "pop_muni_age": 1,
    "hotels_muni": 1,
    "trade_logistics": 3,
    "est_census_2015_muni": 1,
    "lf_muni_sex": 4,
    "pop_muni_age_sex": 2,
    "active_sex_age_act": 2,
    "active_nat_occ_act": 6,
    "comp_nat_act": 10,
    "students_muni": 1,
    "visitors_markets": 4,
}
DECISION_0019 = {
    "ntl_blackmarble",
    "worldpop_qat_agesex",
    "weather_openmeteo",
    "busy_besttime",
    "places_fsq",
}
CITATIONS = {
    "ref_min_wage",
    "ref_wps_report",
    "ref_expansion_method",
    "ref_gov_hours",
    "ref_friday_closure",
    "ref_transit_hours",
    "ref_summer_work",
    "ref_truck_hours",
    "ref_ramadan_public_hours",
    "ref_ramadan_private_hours",
    "ref_ramadan_transit_hours",
    "ref_traffic_index",
}
REPO = repository_root(Path(__file__))


def test_registry_holds_every_required_input_and_no_traffic_row() -> None:
    """Citation rows, the five decision-0019 rows and the 77 slugs are present."""
    entries = load_registry()
    ids = {entry.source_id for entry in entries}
    assert DECISION_0019 <= ids
    assert CITATIONS <= ids
    assert ids.isdisjoint(BANNED_SOURCE_IDS)
    for family, count in FAMILY_COUNTS.items():
        found = [entry for entry in entries if entry.source_id == family]
        assert len(found) == count
        assert all("/" in entry.key and entry.slug for entry in found)
    assert sum(FAMILY_COUNTS.values()) == 77
    citations = [entry for entry in entries if entry.source_id in CITATIONS]
    assert all(entry.kind == "citation_only" for entry in citations)
    assert all(entry.nightly_live_fetch is False for entry in citations)


def test_owner_decision_and_validation_only() -> None:
    """owner_decision names record 0026; every other basis names no record."""
    entries = load_registry()
    by_id = {entry.source_id: entry for entry in entries}
    assert by_id["busy_besttime"].licence_basis == "provider_terms"
    assert by_id["busy_besttime"].decision_record == ""
    for source_id in (
        "fdi_projects",
        "census_zone_sector",
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_2020_workbook",
    ):
        entry = by_id[source_id]
        assert entry.licence_basis == "owner_decision"
        assert entry.decision_record == "0026"
        assert entry.terms_words.strip()
        assert _DATE_TEXT.fullmatch(entry.terms_read_on)
    assert by_id["lic_active"].licence_basis == "dataset"
    assert by_id["lic_active"].decision_record == ""
    assert by_id["bnd_muni_2025"].licence_basis == "portal_terms"
    assert by_id["weather_openmeteo"].licence_basis == "provider_terms"


def test_nightly_selection_rejects_the_excluded_sources() -> None:
    """A nightly selection that names busy_besttime or ntl_blackmarble fails."""
    entries = load_registry()
    blocked = nightly_blocked(
        entries, ("busy_besttime", "ntl_blackmarble", "lic_active")
    )
    assert blocked == ("busy_besttime", "ntl_blackmarble")
    assert nightly_blocked(entries, ("lic_active",)) == ()


def test_allow_list_holds_the_named_hosts() -> None:
    """Both portal hosts, both investment hosts and the places host are listed."""
    assert NAMED_PORTAL_HOSTS <= ALLOWED_HOSTS
    assert NAMED_INVESTMENT_HOSTS <= ALLOWED_HOSTS
    assert NAMED_PLACES_HOST in ALLOWED_HOSTS
    assert approve("https://www.data.qa/api").ok
    assert approve("https://www.data.gov.qa/api").ok
    refused = approve("https://evil.example/planted")
    assert refused.ok is False
    assert refused.reason == "host_refused"
    assert approve("http://www.data.gov.qa/api").ok is False
    assert (
        approve("s3://overturemaps-us-west-2/release/planted").reason
        == "scheme_refused"
    )


def _mutated(tmp_path: Path, name: str, mutate: object) -> Path:
    import yaml

    document = yaml.safe_load(registry_path().read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    if not callable(mutate):
        raise AssertionError("mutate")
    mutate(document)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _row(document: dict[str, object], source_id: str) -> dict[str, object]:
    rows = document["sources"]
    assert isinstance(rows, list)
    for row in rows:
        if isinstance(row, dict) and row.get("source_id") == source_id:
            return row
    raise AssertionError(source_id)


_BASES = frozenset({"dataset", "portal_terms", "provider_terms", "owner_decision"})
_DECISION_0026 = "0026"
_DATE_TEXT = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
_MARKER = "terms to be read"


def test_committed_registry_follows_decision_0026() -> None:
    """Every committed row names one of the four bases, its record and its terms."""
    for entry in load_registry():
        assert entry.licence_basis in _BASES, entry.source_id
        if entry.licence_basis == "owner_decision":
            assert entry.decision_record == _DECISION_0026
        else:
            assert entry.decision_record == ""
        assert entry.terms_words.strip()
        if entry.kind == "register_file":
            # S2-T49: declarations contain no invented reading. Decision 0059
            # permits pending terms; the lead supplies the actual file receipt.
            assert entry.key in {"biz_register", "fc_register/file"}
            assert entry.terms_words == _MARKER
            assert entry.terms_read_on == "pending"
            assert entry.commit_allowed is False
        else:
            assert _DATE_TEXT.fullmatch(entry.terms_read_on)


def test_none_stated_basis_is_refused(tmp_path: Path) -> None:
    """A planted none_stated row is not a basis of use."""

    def none_stated(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["licence_basis"] = "none_stated"

    with pytest.raises(RegistryError, match="unknown licence_basis"):
        load_registry(_mutated(tmp_path, "none-stated.yaml", none_stated))


def test_invented_owner_decision_with_record_0026_loads(tmp_path: Path) -> None:
    """owner_decision admits any source id when the record is 0026."""

    def invented(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["key"] = "planted_source"
        row["source_id"] = "planted_source"
        row["licence_basis"] = "owner_decision"
        row["decision_record"] = _DECISION_0026

    entries = load_registry(_mutated(tmp_path, "invented.yaml", invented))
    planted = [entry for entry in entries if entry.source_id == "planted_source"]
    assert len(planted) == 1
    assert planted[0].licence_basis == "owner_decision"
    assert planted[0].decision_record == _DECISION_0026


def test_dataset_commit_allowed_loads(tmp_path: Path) -> None:
    """A dataset row may be committed. Any other spelling of that basis is refused."""

    def committed(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["commit_allowed"] = True

    loaded = load_registry(_mutated(tmp_path, "dataset-commit.yaml", committed))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert len(roads) == 1
    assert roads[0].licence_basis == "dataset"
    assert roads[0].commit_allowed is True


def test_commit_allowed_on_owner_decision_is_refused(tmp_path: Path) -> None:
    """commit_allowed is refused unless the basis is dataset."""

    def committed(document: dict[str, object]) -> None:
        _row(document, "fdi_projects")["commit_allowed"] = True

    with pytest.raises(RegistryError, match=r"^cannot be committed$"):
        load_registry(_mutated(tmp_path, "committed-owner.yaml", committed))


def test_unknown_field_and_planted_traffic_row_are_refused(tmp_path: Path) -> None:
    """The loader rejects an unknown field and a traffic-provider row."""
    text = registry_path().read_text(encoding="utf-8")
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text(
        text.replace("sources:", "sources:\n  - planted_field: true", 1),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="unknown field"):
        load_registry(unknown)
    planted = tmp_path / "traffic.yaml"
    planted.write_text(
        text.replace(
            'source_id: "lic_active"', 'source_id: "traffic_tomtom_flow"', 1
        ).replace('key: "lic_active"', 'key: "traffic_tomtom_flow"', 1),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="traffic"):
        load_registry(planted)


def test_loader_refuses_planted_breaks(tmp_path: Path) -> None:
    """Duplicate keys, a generic owner decision, a bare record and a non-dataset commit fail."""

    def duplicate(document: dict[str, object]) -> None:
        rows = document["sources"]
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict) and isinstance(rows[1], dict)
        rows[1]["key"] = rows[0]["key"]

    with pytest.raises(RegistryError, match="duplicate key"):
        load_registry(_mutated(tmp_path, "duplicate.yaml", duplicate))

    def admitted(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["licence_basis"] = "owner_decision"
        row["decision_record"] = "0026"

    admitted_rows = load_registry(_mutated(tmp_path, "admitted.yaml", admitted))
    roads = [entry for entry in admitted_rows if entry.source_id == "roads_osm"]
    assert len(roads) == 1
    assert roads[0].licence_basis == "owner_decision"
    assert roads[0].decision_record == "0026"

    def bare_record(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["decision_record"] = "0017"

    with pytest.raises(RegistryError, match="without owner_decision"):
        load_registry(_mutated(tmp_path, "bare.yaml", bare_record))

    def committed(document: dict[str, object]) -> None:
        _row(document, "census_2020_workbook")["commit_allowed"] = True

    with pytest.raises(RegistryError, match=r"^cannot be committed$"):
        load_registry(_mutated(tmp_path, "committed.yaml", committed))

    def column(document: dict[str, object]) -> None:
        _row(document, "lic_active")["columns"] = [{"name": "zone", "type": "date"}]

    with pytest.raises(RegistryError, match="unknown column type"):
        load_registry(_mutated(tmp_path, "column.yaml", column))


LAYER_IDS = {
    "census_zone_sector": 0,
    "census_zone_occ": 0,
    "census_zone_hh": 0,
    "census_zone_lab": 0,
    "census_district_pop": 0,
    "bnd_zone_2020": 0,
    "bnd_district_2020": 12,
    # S2-T19 B2 / LA-2: exact layer declarations, with two absent paths.
    "gis_land_price": 0,
    "gis_rail": 2,
    "gis_phcc": 1,
    "gis_landmarks": 0,
    "gis_zoning": 1,
    "gis_address": 0,
    "gis_parcels": 0,
    "gis_poi_comm": 0,
    "gis_context": 0,
    "gis_boundaries": None,
    "gis_imagery_history": None,
}


def test_paged_layer_rows_state_their_layer_id() -> None:
    """Each paged_layer row names its ArcGIS layer id, and no other kind has one."""
    import yaml

    document = yaml.safe_load(registry_path().read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    rows = document["sources"]
    assert isinstance(rows, list)
    found: dict[str, object] = {}
    for row in rows:
        assert isinstance(row, dict)
        if row.get("kind") == "paged_layer":
            found[str(row.get("source_id"))] = row.get("layer")
        else:
            assert "layer" not in row
    assert found == LAYER_IDS
    loaded = {
        entry.source_id: entry.layer
        for entry in load_registry()
        if entry.kind == "paged_layer"
    }
    assert loaded == LAYER_IDS


def test_loader_refuses_a_bad_layer(tmp_path: Path) -> None:
    """A paged_layer needs a non-negative integer layer; any other kind refuses one."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "bnd_district_2020").pop("layer", None)

    with pytest.raises(RegistryError, match="paged_layer requires layer"):
        load_registry(_mutated(tmp_path, "missing.yaml", missing))

    def as_text(document: dict[str, object]) -> None:
        _row(document, "bnd_zone_2020")["layer"] = "0"

    with pytest.raises(RegistryError, match="layer is not an integer"):
        load_registry(_mutated(tmp_path, "text.yaml", as_text))

    def as_bool(document: dict[str, object]) -> None:
        _row(document, "bnd_zone_2020")["layer"] = True

    with pytest.raises(RegistryError, match="layer is not an integer"):
        load_registry(_mutated(tmp_path, "bool.yaml", as_bool))

    def as_float(document: dict[str, object]) -> None:
        _row(document, "census_district_pop")["layer"] = 1.5

    with pytest.raises(RegistryError, match="layer is not an integer"):
        load_registry(_mutated(tmp_path, "float.yaml", as_float))

    def negative(document: dict[str, object]) -> None:
        _row(document, "bnd_zone_2020")["layer"] = -1

    with pytest.raises(RegistryError, match="layer is negative"):
        load_registry(_mutated(tmp_path, "negative.yaml", negative))

    def other_kind(document: dict[str, object]) -> None:
        _row(document, "lic_active")["layer"] = 0

    with pytest.raises(RegistryError, match="layer on a row that is not paged_layer"):
        load_registry(_mutated(tmp_path, "other.yaml", other_kind))


TERMS_OF_USE = "https://www.invest.qa/en/terms-and-conditions?tab=terms-of-use"
FORBID_PHRASE = (
    "should not be copied or modified or re-produced in whole or in part without"
)


OWNER_BASIS_NOTE = (
    "Owner decision of 2026-11-12: "
    '"This is a personal internal project: use both sources fully, '
    'no permission needed."'
)


def test_investment_sources_record_the_owner_decision_and_watch_terms() -> None:
    """Both rows keep the terms page, record 0026 and the terms fields."""
    by_id = {entry.source_id: entry for entry in load_registry()}
    for source_id in ("fdi_projects", "investqa_pages"):
        entry = by_id[source_id]
        assert entry.terms_url == TERMS_OF_USE
        assert entry.terms_watch is True
        assert entry.basis_note == OWNER_BASIS_NOTE
        assert entry.licence_basis == "owner_decision"
        assert entry.decision_record == "0026"
        assert entry.terms_words.strip()
        expected_date = "2026-11-19" if source_id == "investqa_pages" else "2026-11-14"
        assert entry.terms_read_on == expected_date
    assert by_id["investqa_pages"].terms_words != _MARKER
    assert by_id["fdi_projects"].terms_words != _MARKER


def test_loader_refuses_a_bad_terms_forbid(tmp_path: Path) -> None:
    """terms_forbid is refused as an unknown field. The together-test name is dropped."""

    def planted(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_forbid"] = [FORBID_PHRASE]

    with pytest.raises(RegistryError, match="unknown field"):
        load_registry(_mutated(tmp_path, "forbid.yaml", planted))


def _assert_c_safe_loader_only(text: str) -> None:
    """Allow direct C-safe calls, a plain module import and the error boundary."""
    assert not re.search(
        r"\b(?:C?FullLoader|C?UnsafeLoader|CLoader|unsafe_load|full_load|load_all)\b"
        r"|\byaml\s*\.\s*(?:Loader|unsafe\w*)\b",
        text,
    ), "forbidden YAML spelling"
    tree = ast.parse(text)
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    calls = []
    for node in ast.walk(tree):
        parent = parents.get(node)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "yaml" or alias.asname == "yaml":
                    assert alias.name == "yaml" and alias.asname is None, (
                        "plain import yaml required"
                    )
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "yaml", (
                "plain import yaml required"
            )
            assert all(
                alias.asname != "yaml" and alias.name != "yaml" for alias in node.names
            ), "plain import yaml required"
        if isinstance(node, ast.Name) and node.id == "yaml":
            assert (
                isinstance(node.ctx, ast.Load)
                and isinstance(parent, ast.Attribute)
                and parent.value is node
            ), "yaml module must be used directly"
        if isinstance(node, ast.arg):
            assert node.arg != "yaml", "plain import yaml required"
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler),
        ):
            assert node.name != "yaml", "plain import yaml required"
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "yaml":
                assert isinstance(node.ctx, ast.Load), (
                    "YAML members must be used directly"
                )
                assert node.attr in {"load", "CSafeLoader", "YAMLError"}, (
                    "unsupported YAML member"
                )
                if node.attr == "load":
                    assert isinstance(parent, ast.Call) and parent.func is node, (
                        "yaml.load must be called directly"
                    )
                elif node.attr == "CSafeLoader":
                    call = parents.get(parent)
                    assert (
                        isinstance(parent, ast.keyword)
                        and parent.arg == "Loader"
                        and isinstance(call, ast.Call)
                        and ast.unparse(call.func) == "yaml.load"
                    ), "YAML members must be used directly"
                else:
                    assert (
                        isinstance(parent, ast.ExceptHandler) and parent.type is node
                    ), "YAML members must be used directly"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "yaml" and node.func.attr == "load":
                    calls.append(node)
                    loaders = [kw.value for kw in node.keywords if kw.arg == "Loader"]
                    assert len(loaders) == 1, "explicit C safe loader required"
                    assert ast.unparse(loaders[0]) == "yaml.CSafeLoader", (
                        "explicit C safe loader required"
                    )
    assert calls, "no approved YAML call"


def test_loader_uses_the_safe_loader_only() -> None:
    """Replace the text guard under decision 0053 with C safe-loader guards."""
    _assert_c_safe_loader_only(
        (REPO / "custodian/src/eii_custodian/publicdata/fetch/registry.py").read_text(
            encoding="utf-8"
        )
    )


def test_loader_passes_only_c_safe_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live loader argument is the C safe loader, even in a mutation copy."""
    path = tmp_path / "invented.yaml"
    path.write_text("planted: safe\n", encoding="utf-8")
    real_load = yaml.load
    loaders: list[object] = []
    forwarded: list[object] = []

    def load_spy(text, *, Loader):
        loaders.append(Loader)
        result = real_load(text, Loader=Loader)
        forwarded.append(result)
        return result

    monkeypatch.setattr(yaml, "load", load_spy)

    def assert_c_loader(reader):
        loaders.clear()
        forwarded.clear()
        result = reader(path)
        assert result == {"planted": "safe"}
        assert len(forwarded) == 1
        assert result is forwarded[0]
        assert len(loaders) == 1
        assert loaders[0] is yaml.CSafeLoader

    assert_c_loader(read_yaml)

    def planted_reader(path):
        return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)

    with pytest.raises(AssertionError):
        assert_c_loader(planted_reader)


_APPROVED_YAML_CALL = "yaml.load(text, Loader=yaml.CSafeLoader)"


@pytest.mark.parametrize(
    ("forbidden", "reason"),
    [
        ("yaml.load(text, Loader=yaml.Loader)", "forbidden YAML spelling"),
        ("yaml.full_load(text)", "forbidden YAML spelling"),
        ("yaml.load_all(text, Loader=yaml.CSafeLoader)", "forbidden YAML spelling"),
        ("yaml.load(text, Loader=yaml.FullLoader)", "forbidden YAML spelling"),
        ("yaml.load(text, Loader=yaml.UnsafeLoader)", "forbidden YAML spelling"),
        ("yaml.unsafe_load(text)", "forbidden YAML spelling"),
        ("yaml.unsafe(text)", "forbidden YAML spelling"),
        ("from yaml import FullLoader", "forbidden YAML spelling"),
        ("f = yaml.load", "yaml.load must be called directly"),
        ('getattr(yaml, "load")', "yaml module must be used directly"),
        ("import yaml as y", "plain import yaml required"),
        ("from yaml import load", "plain import yaml required"),
        ("from yaml import Loader as L", "plain import yaml required"),
        ("y = yaml", "yaml module must be used directly"),
        ("L = yaml.CSafeLoader", "YAML members must be used directly"),
        ("E = yaml.YAMLError", "YAML members must be used directly"),
        ("f(Loader=yaml.CSafeLoader)", "YAML members must be used directly"),
        ("yaml.load = f", "YAML members must be used directly"),
        ("yaml = other", "yaml module must be used directly"),
        ("def f(yaml): pass", "plain import yaml required"),
        ("def yaml(): pass", "plain import yaml required"),
        ("import other as yaml", "plain import yaml required"),
        ("from other import module as yaml", "plain import yaml required"),
        ("yaml.scan(text)", "unsupported YAML member"),
    ],
)
def test_loader_text_guard_refuses_planted_unsafe_calls(
    forbidden: str, reason: str
) -> None:
    """Each forbidden construct fails its own guard beside one approved call."""
    with pytest.raises(AssertionError, match=re.escape(reason)):
        _assert_c_safe_loader_only(_APPROVED_YAML_CALL + "\n" + forbidden)


def test_loader_text_guard_accepts_approved_call_alone() -> None:
    """An approved call needs no unrelated construct to satisfy the guard."""
    _assert_c_safe_loader_only(_APPROVED_YAML_CALL)
    _assert_c_safe_loader_only("import yaml\n" + _APPROVED_YAML_CALL)


@pytest.mark.parametrize("text", ["", "yaml.load(text)"])
def test_loader_text_guard_refuses_missing_or_loaderless_call(text: str) -> None:
    """Missing and loader-less calls are separate from independent plants."""
    with pytest.raises(AssertionError):
        _assert_c_safe_loader_only(text)


_COMMITTED_READER_YAML = (
    "custodian/publicdata/sources.yaml",  # load_registry in fetch/registry.py
    "custodian/publicdata/investment_pages.yaml",  # investment_build.load_source_spec
)


def _assert_committed_yaml_forms(text: str) -> None:
    """Keep the committed inputs out of the differing tab/surrogate forms."""
    assert "\t" not in text, "tab in committed YAML"
    assert not re.search(r"\\u[dD][89a-fA-F][0-9a-fA-F]{2}", text), (
        "surrogate escape in committed YAML"
    )


@pytest.mark.parametrize("relative", _COMMITTED_READER_YAML)
def test_committed_reader_yaml_has_no_differing_forms(relative: str) -> None:
    _assert_committed_yaml_forms((REPO / relative).read_text(encoding="utf-8"))


@pytest.mark.parametrize("plant", ["\t", r"\ud800"])
def test_committed_yaml_forms_guard_refuses_planted_copy(
    tmp_path: Path, plant: str
) -> None:
    """A copy with one forbidden form fails the very same text check."""
    text = (REPO / _COMMITTED_READER_YAML[0]).read_text(encoding="utf-8")
    path = tmp_path / "planted.yaml"
    path.write_text(text + "\n# planted: " + plant + "\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_committed_yaml_forms(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a: [\t1]\n", {"a": [1]}),
        ("a: [1,\t2]\n", {"a": [1, 2]}),
        ("a: {\tb: 1}\n", {"a": {"b": 1}}),
        ("a:\t1\n", {"a": 1}),
    ],
    ids=["D1-flow-start", "D1-flow-comma", "D1-flow-map", "D2-block-colon"],
)
def test_loader_tab_differences_are_pinned(
    tmp_path: Path, text: str, expected: object
) -> None:
    """SafeLoader refuses tabs that the current libyaml accepts."""
    path = tmp_path / "tabs.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(yaml.scanner.ScannerError):
        yaml.load(text, Loader=yaml.SafeLoader)
    assert read_yaml(path) == expected


@pytest.mark.parametrize("depth", [200, 5000], ids=["D3-shallow", "D3-deep"])
def test_loader_nesting_difference_is_pinned(tmp_path: Path, depth: int) -> None:
    """At exactly 5000 levels the old reader leaks RecursionError; C loads."""
    text = "a: " + "[" * depth + "0" + "]" * depth + "\n"
    path = tmp_path / "nested.yaml"
    path.write_text(text, encoding="utf-8")
    if depth == 5000:
        with pytest.raises(RecursionError) as error:
            yaml.load(text, Loader=yaml.SafeLoader)
        assert not isinstance(error.value, yaml.YAMLError)
    else:
        expected = yaml.load(text, Loader=yaml.SafeLoader)
        assert read_yaml(path) == expected
    loaded = read_yaml(path)
    assert isinstance(loaded, dict)
    value = loaded["a"]
    for _ in range(depth):
        assert isinstance(value, list) and len(value) == 1
        value = value[0]
    assert value == 0


def test_loader_surrogate_difference_is_pinned(tmp_path: Path) -> None:
    """D4: SafeLoader loads a lone surrogate; C wraps ScannerError."""
    text = 'a: "\\ud800"\n'
    path = tmp_path / "surrogate.yaml"
    path.write_text(text, encoding="utf-8")
    assert yaml.load(text, Loader=yaml.SafeLoader) == {"a": chr(0xD800)}
    with pytest.raises(RegistryError, match=r"^malformed yaml$") as error:
        read_yaml(path)
    assert isinstance(error.value.__cause__, yaml.scanner.ScannerError)


@pytest.mark.parametrize("tag", ["python/object/apply", "python/name"])
def test_loader_refuses_unsafe_tags_without_constructing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tag: str
) -> None:
    """Invented callable and name tags cannot construct or return an object."""
    constructed = []

    def planted_target() -> object:
        constructed.append("constructed")
        return object()

    monkeypatch.setattr(
        registry_module, "planted_target", planted_target, raising=False
    )
    path = tmp_path / "unsafe.yaml"
    target = f"{registry_module.__name__}.planted_target"
    suffix = " []" if tag == "python/object/apply" else ""
    path.write_text(f"!!{tag}:{target}{suffix}\n", encoding="utf-8")
    try:
        with pytest.raises(RegistryError, match=r"^malformed yaml$"):
            read_yaml(path)
    finally:
        assert constructed == []


def _assert_libyaml_available() -> None:
    assert yaml.__with_libyaml__ is True
    assert callable(yaml.CSafeLoader)


def test_locked_environment_has_libyaml(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment guard refuses a planted missing libyaml or C loader."""
    _assert_libyaml_available()
    with monkeypatch.context() as missing_libyaml:
        missing_libyaml.setattr(yaml, "__with_libyaml__", False)
        with pytest.raises(AssertionError):
            _assert_libyaml_available()
    with monkeypatch.context() as missing_loader:
        missing_loader.delattr(yaml, "CSafeLoader")
        with pytest.raises(AttributeError):
            _assert_libyaml_available()


def test_loader_fails_loudly_without_c_safe_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planted absent C loader cannot fall back to pure Python."""
    path = tmp_path / "safe.yaml"
    path.write_text("planted: safe\n", encoding="utf-8")
    monkeypatch.delattr(yaml, "CSafeLoader")
    with pytest.raises(AttributeError):
        read_yaml(path)


@pytest.mark.parametrize("relative", _COMMITTED_READER_YAML)
def test_loader_preserves_committed_registry_values(
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    """SafeLoader parity refuses a planted changed registry value."""
    path = REPO / relative
    expected = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    assert read_yaml(path) == expected
    monkeypatch.setattr(
        registry_module, "read_yaml", lambda path: {"planted": "changed"}
    )
    with pytest.raises(AssertionError):
        assert registry_module.read_yaml(path) == expected


def test_only_the_transport_module_opens_a_connection() -> None:
    """A planted module that opens a connection fails the seam scan."""
    for name in SCAN_ROOTS:
        folder = REPO / name
        assert folder.is_dir()
        assert any(folder.rglob("*.py"))
    assert scan_tree(REPO) == ()
    planted = {"custodian/src/eii_custodian/planted.py": "import urllib.request\n"}
    assert opener_hits(planted) == ("custodian/src/eii_custodian/planted.py",)


def test_missing_basis_loads_as_pending_and_unknown_basis_refuses(
    tmp_path: Path,
) -> None:
    """Ruling L-1001: a row with no basis key loads as the pending record;
    a row with an unknown basis value still refuses."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "roads_osm").pop("licence_basis")

    loaded = load_registry(_mutated(tmp_path, "missing-basis.yaml", missing))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].licence_basis == "pending"

    def unknown(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["licence_basis"] = "invented_basis"

    with pytest.raises(RegistryError, match="unknown licence_basis"):
        load_registry(_mutated(tmp_path, "unknown-basis.yaml", unknown))


def test_owner_decision_rejects_an_old_or_empty_record(tmp_path: Path) -> None:
    """owner_decision accepts only the record 0026, on a registry of that one row."""

    def one(record: str, name: str) -> Path:
        def mutate(document: dict[str, object]) -> None:
            row = _row(document, "roads_osm")
            row["licence_basis"] = "owner_decision"
            row["decision_record"] = record
            document["sources"] = [row]

        return _mutated(tmp_path, name, mutate)

    with pytest.raises(RegistryError, match="needs a decision record"):
        load_registry(one("0017", "old-record.yaml"))

    with pytest.raises(RegistryError, match="needs a decision record"):
        load_registry(one("", "empty-record.yaml"))


def test_dataset_row_rejects_a_decision_record(tmp_path: Path) -> None:
    """A decision record on a basis other than owner_decision is refused."""

    def recorded(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["decision_record"] = "0026"

    with pytest.raises(RegistryError, match="without owner_decision"):
        load_registry(_mutated(tmp_path, "dataset-record.yaml", recorded))


def test_terms_words_missing_or_blank_load_as_pending(tmp_path: Path) -> None:
    """Ruling L-1001: a missing key, empty or blank words load as the pending marker."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "roads_osm").pop("terms_words")

    loaded = load_registry(_mutated(tmp_path, "missing-words.yaml", missing))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_words == _MARKER

    def empty(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_words"] = ""

    loaded = load_registry(_mutated(tmp_path, "empty-words.yaml", empty))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_words == _MARKER

    def spaces(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_words"] = "   "

    loaded = load_registry(_mutated(tmp_path, "space-words.yaml", spaces))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_words == _MARKER

    def marker(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_words"] = _MARKER
        row["terms_read_on"] = "2026-11-01"

    loaded = load_registry(_mutated(tmp_path, "marker.yaml", marker))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_words == _MARKER
    assert roads[0].terms_read_on == "2026-11-01"


def test_terms_read_on_must_be_a_real_text_date(tmp_path: Path) -> None:
    """Ruling L-1001: a missing key or empty date loads as the pending value;
    malformed non-empty dates refuse."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "roads_osm").pop("terms_read_on")

    loaded = load_registry(_mutated(tmp_path, "missing-date.yaml", missing))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_read_on == "pending"

    def empty(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_read_on"] = ""

    loaded = load_registry(_mutated(tmp_path, "empty-date.yaml", empty))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_read_on == "pending"

    def impossible(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_read_on"] = "2026-13-01"

    with pytest.raises(RegistryError, match="not a date"):
        load_registry(_mutated(tmp_path, "month.yaml", impossible))

    def slashes(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_read_on"] = "14/11/2026"

    with pytest.raises(RegistryError, match="not a date"):
        load_registry(_mutated(tmp_path, "slashes.yaml", slashes))

    def week(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_read_on"] = "2026-W46-6"

    with pytest.raises(RegistryError, match="not a date"):
        load_registry(_mutated(tmp_path, "week.yaml", week))

    text = registry_path().read_text(encoding="utf-8")
    unquoted = text.replace(
        'terms_read_on: "2026-11-14"', "terms_read_on: 2026-11-14", 1
    )
    path = tmp_path / "unquoted.yaml"
    path.write_text(unquoted, encoding="utf-8")
    with pytest.raises(RegistryError, match="not text"):
        load_registry(path)


def test_pending_terms_fields_load_and_never_commit(tmp_path: Path) -> None:
    """Empty terms fields load as pending values, and a pending basis never commits."""

    def pending(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_words"] = ""
        row["terms_read_on"] = ""
        row["licence_basis"] = ""

    loaded = load_registry(_mutated(tmp_path, "pending.yaml", pending))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_words == _MARKER
    assert roads[0].terms_read_on == "pending"
    assert roads[0].licence_basis == "pending"
    assert roads[0].commit_allowed is False

    def committed(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_words"] = ""
        row["terms_read_on"] = ""
        row["licence_basis"] = ""
        row["commit_allowed"] = True

    with pytest.raises(RegistryError, match="cannot be committed"):
        load_registry(_mutated(tmp_path, "committed.yaml", committed))

    def unknown(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_words"] = ""
        row["terms_read_on"] = ""
        row["licence_basis"] = "invented_basis"

    with pytest.raises(RegistryError, match="unknown licence_basis"):
        load_registry(_mutated(tmp_path, "unknown.yaml", unknown))

    def malformed(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_words"] = ""
        row["terms_read_on"] = "14/11/2026"
        row["licence_basis"] = ""

    with pytest.raises(RegistryError, match="not a date"):
        load_registry(_mutated(tmp_path, "malformed.yaml", malformed))


def test_skip_reason_must_not_name_a_licence_or_terms(tmp_path: Path) -> None:
    """A skip reason that names a licence or terms is refused; a technical one loads."""

    def plant(reason: str) -> object:
        def mutate(document: dict[str, object]) -> None:
            _row(document, "roads_osm")["skip_reason"] = reason

        return mutate

    for reason in (
        "publisher_or_licence_unconfirmed",
        "License_missing",
        "terms_forbid_the_use",
    ):
        with pytest.raises(
            RegistryError, match=r"^skip_reason names a licence or terms$"
        ):
            load_registry(_mutated(tmp_path, f"{reason}.yaml", plant(reason)))

    loaded = load_registry(
        _mutated(
            tmp_path,
            "technical.yaml",
            plant("publisher_or_schema_unconfirmed"),
        )
    )
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].skip_reason == "publisher_or_schema_unconfirmed"


def test_registry_counts_follow_decision_0026() -> None:
    """No none_stated row remains, and every owner_decision row names 0026."""
    from eii_custodian.publicdata.assembly_sources import BLDG_OVT_KEYS

    entries = load_registry()
    stac_item_count = sum(
        key.startswith("bldg_ovt/stac-part-") for key in BLDG_OVT_KEYS
    )
    assert (
        len(entries) == 285 + 4 + 4 + 8 + 1 + 1 + 1 + 2 + 4 + 1 - 3 + stac_item_count
    )  # The fixed non-item count stays; STAC items use the committed closed tuple.
    assert not any(entry.licence_basis == "none_stated" for entry in entries)
    owners = [entry for entry in entries if entry.licence_basis == "owner_decision"]
    # S2-T28 moves exactly these advisor-confirmed CC BY rows to dataset basis.
    confirmed = {"wage_bands_priv", "work_hours_act", "accident"}
    # S2-T21 part B records the two benchmark families' read portal terms.
    # S2-P29 round B: supplied lead page reading records "Licence: Etalab 2.0".
    # S2-P35 moves Gravity and Atlas to dataset basis on the lead's readings.
    assert (
        len(owners) == 26 + 13 + 3 + 4 - 3 + 8 + 1 - 2 - 1 + 2 + 1 - 2
    )  # S2-T49 files; S2-T48 company web.
    assert {
        entry.key
        for entry in entries
        if entry.key in confirmed
        and entry.licence_basis == "dataset"
        and entry.licence_id == "CC-BY-4.0"
        and entry.decision_record == ""
    } == confirmed
    assert {entry.decision_record for entry in owners} == {"0026"}


def terms_words_absent_from_pack(
    entries: tuple[Entry, ...], pack: str
) -> tuple[str, ...]:
    """Return source ids whose terms words are neither the marker nor in the pack."""
    return tuple(
        entry.source_id
        for entry in entries
        if entry.terms_words != _MARKER
        and " ".join(entry.terms_words.split()) not in " ".join(pack.split())
    )


def test_terms_words_other_than_the_marker_are_in_document_04() -> None:
    """Recorded terms words are the publisher's words already quoted in document 04."""
    pack = (REPO / "docs" / "04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    assert terms_words_absent_from_pack(load_registry(), pack) == ()


def test_terms_words_absent_from_document_04_fail_the_guard(tmp_path: Path) -> None:
    """A row whose words are not in document 04 fails the guard."""

    def planted(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_words"] = (
            "invented words the pack never quotes"
        )

    entries = load_registry(_mutated(tmp_path, "words.yaml", planted))
    pack = (REPO / "docs" / "04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    assert "roads_osm" in terms_words_absent_from_pack(entries, pack)


def test_terms_words_parity_normalises_whitespace_only() -> None:
    """L-1153 item 1 permits whitespace runs, preserving words and punctuation."""
    from dataclasses import replace

    entry = replace(load_registry()[0], terms_words="Invented\nlicence\u00a0 words.")
    assert terms_words_absent_from_pack((entry,), "Invented licence  words.") == ()
    for changed in ("invented licence words.", "Invented licence words!"):
        assert terms_words_absent_from_pack((entry,), changed) == (entry.source_id,)


_BUSY_ID = "busy_besttime"


def non_python_files_naming_busy(root: Path) -> tuple[str, ...]:
    """Return non-Python files under root whose text names the busy source id."""
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix == ".py":
            continue
        if "__pycache__" in path.relative_to(root).parts:
            continue
        if _BUSY_ID.encode("utf-8") in path.read_bytes():
            found.append(path.name)
    return tuple(found)


def test_no_non_python_test_file_names_busy_besttime() -> None:
    """No committed test fixture names the busy source id."""
    tests = REPO / "custodian" / "tests"
    assert non_python_files_naming_busy(tests) == ()


def test_planted_json_naming_busy_besttime_fails_the_scan(tmp_path: Path) -> None:
    """A planted JSON file that names the busy source id fails the same scan."""
    planted = tmp_path / "planted.json"
    planted.write_text(
        '{"source_id": "busy_besttime", "values": ["invented-one", "invented-two"]}\n',
        encoding="utf-8",
    )
    assert non_python_files_naming_busy(tmp_path) == ("planted.json",)


def test_bytecode_cache_is_not_scanned_as_a_fixture(tmp_path: Path) -> None:
    """Bytecode that pytest writes is never committed, so the scan skips it."""
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "test_one.cpython-314-pytest-9.2.0.pyc").write_bytes(
        b"\xb6\xbd\xf9j\x00busy_besttime\x00\xff"
    )
    assert non_python_files_naming_busy(tmp_path) == ()


def test_planted_binary_fixture_naming_busy_besttime_fails_the_scan(
    tmp_path: Path,
) -> None:
    """A planted fixture that is not UTF-8 text but names the id still fails."""
    (tmp_path / "planted.bin").write_bytes(b"\xb6\xbd\x00busy_besttime\xff")
    assert non_python_files_naming_busy(tmp_path) == ("planted.bin",)


def test_cache_path_is_gitignored(tmp_path: Path) -> None:
    """The repository gitignore ignores the cache, and a file without that rule does not."""
    import subprocess

    empty = tmp_path / "empty-excludes"
    empty.write_text("", encoding="utf-8")
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=fresh, check=True)
    (fresh / ".gitignore").write_text(
        (REPO / ".gitignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    ignored = subprocess.run(
        [
            "git",
            "-c",
            f"core.excludesFile={empty}",
            "check-ignore",
            "-q",
            "--",
            "data/public_cache",
        ],
        cwd=fresh,
        check=False,
    )
    assert ignored.returncode == 0
    (fresh / ".gitignore").write_text("# planted, no data rule\n", encoding="utf-8")
    open_cache = subprocess.run(
        [
            "git",
            "-c",
            f"core.excludesFile={empty}",
            "check-ignore",
            "-q",
            "--",
            "data/public_cache",
        ],
        cwd=fresh,
        check=False,
    )
    assert open_cache.returncode == 1


def test_baci_registry_pending_and_nightly_policy() -> None:
    """BACI's page is read; archive metadata remains pending and nightly eligible."""
    from dataclasses import replace

    entries = load_registry()
    baci = next(entry for entry in entries if entry.source_id == "cepii_baci")
    assert baci.skip_reason == "baci_metadata_unconfirmed"
    assert baci.commit_allowed is False
    assert baci.url == (
        "https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS17_V202601.zip"
    )
    assert baci.fetch_host == "www.cepii.fr"
    page = "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37"
    assert baci.landing_url == baci.terms_url == page
    assert baci.title_en == "BACI bilateral trade (HS 2017, release 202601)"
    assert baci.licence_id == "Etalab-2.0"
    assert baci.licence_basis == "dataset"
    assert baci.licence_url == (
        "https://www.etalab.gouv.fr/wp-content/uploads/2018/11/open-licence.pdf"
    )
    assert baci.decision_record == ""
    assert baci.terms_words == "Licence: Etalab 2.0"
    assert baci.terms_read_on == "2026-11-20"
    assert baci.extension == "zip"
    assert (baci.period_first, baci.period_last) == ("2017", "2024")
    # Supplied archive reading confirms the native header, but no row counts.
    assert baci.columns == (
        ("t", "integer"),
        ("i", "string"),
        ("j", "string"),
        ("k", "string"),
        ("v", "number"),
        ("q", "number"),
    )
    assert baci.row_count_min is baci.row_count_max is None
    assert baci.period_field == "t"
    assert "row counts remain pending" in baci.basis_note
    assert "publisher-link target" in baci.basis_note
    assert nightly_blocked([replace(baci, skip_reason="")], ("cepii_baci",)) == ()

    def exclusions(rows):
        return {
            e.source_id
            for e in rows
            if not e.nightly_live_fetch and e.kind != "citation_only"
        } | BANNED_SOURCE_IDS

    expected = {
        "company_web",
        "satellite_cdse_backup",
        "biz_register",
        "fc_register",
        "bldg_3dglobfp",
        "bldg_wsf3d",
        "gis_boundaries",
        "gis_imagery_history",
        "tenders_pub",
        "worldpop_qat_agesex",
        "busy_besttime",
        "ntl_blackmarble",
        "traffic_tomtom_flow",
        "traffic_tomtom_range",
        "un_comtrade",
        "insurance_tables",
        "events_visit_qatar",
        "events_qncc",
        "suppliers_tawteen",
        "manateq_tariffs",
        "monaqasat_classified",
        "schools_private_directory",
        "awards_owner_scrape",
        "bldg_gba",
    }
    assert exclusions(entries) == expected
    planted = [
        replace(e, nightly_live_fetch=False) if e.source_id == "cepii_baci" else e
        for e in entries
    ]
    assert exclusions(planted) != expected


def test_gravity_and_atlas_registry_pending_and_nightly_policy() -> None:
    """Pending trade rows stay eligible and do not enlarge the closed exclusion set."""
    from dataclasses import replace

    entries = load_registry()
    expected = {
        "busy_besttime",
        "ntl_blackmarble",
        "traffic_tomtom_flow",
        "traffic_tomtom_range",
    }
    pages = {
        "cepii_gravity": (
            "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=8"
        ),
        "atlas_complexity": "https://atlas.hks.harvard.edu/data-downloads",
    }
    for source_id, reason in (
        ("cepii_gravity", "gravity_metadata_unconfirmed"),
        ("atlas_complexity", "atlas_metadata_unconfirmed"),
    ):
        row = next(entry for entry in entries if entry.source_id == source_id)
        assert row.skip_reason == reason
        assert row.commit_allowed is False
        assert row.nightly_live_fetch is True
        assert row.url == ""
        assert row.landing_url == row.terms_url == pages[source_id]
        assert row.terms_read_on == "2026-11-21"
        assert "no registration, no key, no paid tier" in row.basis_note
        assert nightly_blocked([replace(row, skip_reason="")], (source_id,)) == ()
    planted = [
        replace(entry, nightly_live_fetch=False)
        if entry.source_id in {"cepii_gravity", "atlas_complexity"}
        else entry
        for entry in entries
    ]
    changed = {
        entry.source_id
        for entry in planted
        if not entry.nightly_live_fetch and entry.kind != "citation_only"
    }
    assert changed != expected


def test_bldg_ovt_closed_keys_equal_registry_in_both_directions() -> None:
    from eii_custodian.publicdata.assembly_sources import (
        BLDG_OVT_KEYS,
        SOURCE_COMPONENTS,
    )

    expected = frozenset(
        row.key for row in load_registry() if row.source_id == "bldg_ovt"
    )
    assert len(BLDG_OVT_KEYS) == len(set(BLDG_OVT_KEYS))
    assert frozenset(BLDG_OVT_KEYS) == expected, "bldg_ovt_closed_keys"
    assert SOURCE_COMPONENTS["bldg_ovt"] == expected, "bldg_ovt_component_keys"
