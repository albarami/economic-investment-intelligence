"""Registry completeness, licence basis, nightly flag and the safe loader."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
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
        assert entry.terms_read_on == "2026-11-14"
    assert by_id["investqa_pages"].terms_words == _MARKER
    assert by_id["fdi_projects"].terms_words != _MARKER


def test_loader_refuses_a_bad_terms_forbid(tmp_path: Path) -> None:
    """terms_forbid is refused as an unknown field. The together-test name is dropped."""

    def planted(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_forbid"] = [FORBID_PHRASE]

    with pytest.raises(RegistryError, match="unknown field"):
        load_registry(_mutated(tmp_path, "forbid.yaml", planted))


def test_loader_uses_the_safe_loader_only() -> None:
    """The registry module calls safe_load and does not call yaml.load."""
    module = Path(registry_module.__file__)
    text = module.read_text(encoding="utf-8")
    assert "safe_load" in text
    assert "yaml.load" not in text


def test_only_the_transport_module_opens_a_connection() -> None:
    """A planted module that opens a connection fails the seam scan."""
    for name in SCAN_ROOTS:
        folder = REPO / name
        assert folder.is_dir()
        assert any(folder.rglob("*.py"))
    assert scan_tree(REPO) == ()
    planted = {"custodian/src/eii_custodian/planted.py": "import urllib.request\n"}
    assert opener_hits(planted) == ("custodian/src/eii_custodian/planted.py",)


def test_loader_refuses_a_missing_or_unknown_basis(tmp_path: Path) -> None:
    """A row with no basis, and a row with an unknown basis, are refused."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "roads_osm").pop("licence_basis")

    with pytest.raises(RegistryError, match="missing field"):
        load_registry(_mutated(tmp_path, "missing-basis.yaml", missing))

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


def test_terms_words_must_be_present_text(tmp_path: Path) -> None:
    """Missing, empty or blank terms_words are refused. The marker loads."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "roads_osm").pop("terms_words")

    with pytest.raises(RegistryError, match="missing field"):
        load_registry(_mutated(tmp_path, "missing-words.yaml", missing))

    def empty(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_words"] = ""

    with pytest.raises(RegistryError, match=r"^terms_words is empty$"):
        load_registry(_mutated(tmp_path, "empty-words.yaml", empty))

    def spaces(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["terms_words"] = "   "

    with pytest.raises(RegistryError, match=r"^terms_words is empty$"):
        load_registry(_mutated(tmp_path, "space-words.yaml", spaces))

    def marker(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_words"] = _MARKER
        row["terms_read_on"] = "2026-11-01"

    loaded = load_registry(_mutated(tmp_path, "marker.yaml", marker))
    roads = [entry for entry in loaded if entry.source_id == "roads_osm"]
    assert roads[0].terms_words == _MARKER
    assert roads[0].terms_read_on == "2026-11-01"


def test_terms_read_on_must_be_a_real_text_date(tmp_path: Path) -> None:
    """A missing, impossible, non-ISO or unquoted date is refused."""

    def missing(document: dict[str, object]) -> None:
        _row(document, "roads_osm").pop("terms_read_on")

    with pytest.raises(RegistryError, match="missing field"):
        load_registry(_mutated(tmp_path, "missing-date.yaml", missing))

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
    entries = load_registry()
    assert len(entries) == 143
    assert not any(entry.licence_basis == "none_stated" for entry in entries)
    owners = [entry for entry in entries if entry.licence_basis == "owner_decision"]
    assert len(owners) == 27
    assert {entry.decision_record for entry in owners} == {"0026"}


def terms_words_absent_from_pack(
    entries: tuple[Entry, ...], pack: str
) -> tuple[str, ...]:
    """Return source ids whose terms words are neither the marker nor in the pack."""
    return tuple(
        entry.source_id
        for entry in entries
        if entry.terms_words != _MARKER and entry.terms_words not in pack
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
