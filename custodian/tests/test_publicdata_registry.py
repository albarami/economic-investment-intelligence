"""Registry completeness, licence basis, nightly flag and the safe loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.allowlist import (
    ALLOWED_HOSTS,
    NAMED_INVESTMENT_HOSTS,
    NAMED_PLACES_HOST,
    NAMED_PORTAL_HOSTS,
    approve,
)
from eii_custodian.publicdata.fetch.registry import (
    BANNED_SOURCE_IDS,
    OWNER_DECISION_SOURCES,
    RegistryError,
    load_registry,
    nightly_blocked,
    registry_path,
    release_refused,
)
from eii_custodian.publicdata.fetch.seam import opener_hits, scan_tree

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
    "busy_gmaps",
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
REPO = Path(__file__).resolve().parents[2]


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
    """Admitted sources name their decision; a none_stated source cannot feed a release."""
    entries = load_registry()
    by_id = {entry.source_id: entry for entry in entries}
    for source_id in OWNER_DECISION_SOURCES:
        entry = by_id[source_id]
        assert entry.licence_basis == "owner_decision"
        assert entry.decision_record in {"0017", "0019"}
    assert by_id["busy_gmaps"].decision_record == "0019"
    assert by_id["fdi_projects"].decision_record == "0017"
    assert by_id["census_zone_sector"].decision_record == "0017"
    assert by_id["bnd_zone_2020"].decision_record == "0017"
    assert by_id["bnd_district_2020"].decision_record == "0017"
    workbook = by_id["census_2020_workbook"]
    assert workbook.licence_basis == "none_stated"
    for slot in ("value", "share", "title", "geometry"):
        assert release_refused(workbook, slot)
    assert release_refused(by_id["census_zone_sector"], "value") is False
    assert release_refused(by_id["busy_gmaps"], "value") is False


def test_nightly_selection_rejects_the_excluded_sources() -> None:
    """A nightly selection that names busy_gmaps or ntl_blackmarble fails."""
    entries = load_registry()
    blocked = nightly_blocked(entries, ("busy_gmaps", "ntl_blackmarble", "lic_active"))
    assert blocked == ("busy_gmaps", "ntl_blackmarble")
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
    """Duplicate keys, an unadmitted owner decision, a bare record and a committed none_stated fail."""

    def duplicate(document: dict[str, object]) -> None:
        rows = document["sources"]
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict) and isinstance(rows[1], dict)
        rows[1]["key"] = rows[0]["key"]

    with pytest.raises(RegistryError, match="duplicate key"):
        load_registry(_mutated(tmp_path, "duplicate.yaml", duplicate))

    def unadmitted(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["licence_basis"] = "owner_decision"
        row["decision_record"] = "0017"

    with pytest.raises(RegistryError, match="not admitted"):
        load_registry(_mutated(tmp_path, "unadmitted.yaml", unadmitted))

    def bare_record(document: dict[str, object]) -> None:
        _row(document, "roads_osm")["decision_record"] = "0017"

    with pytest.raises(RegistryError, match="without owner_decision"):
        load_registry(_mutated(tmp_path, "bare.yaml", bare_record))

    def committed(document: dict[str, object]) -> None:
        _row(document, "census_2020_workbook")["commit_allowed"] = True

    with pytest.raises(RegistryError, match="cannot be committed"):
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
    """Both rows keep the terms page and the owner's words, and do not switch off."""
    by_id = {entry.source_id: entry for entry in load_registry()}
    for source_id in ("fdi_projects", "investqa_pages"):
        entry = by_id[source_id]
        assert entry.terms_url == TERMS_OF_USE
        assert entry.terms_forbid == ()
        assert entry.terms_watch is True
        assert entry.basis_note == OWNER_BASIS_NOTE
        assert entry.licence_basis == "owner_decision"
        assert entry.decision_record == "0017"


def test_loader_refuses_terms_watch_and_terms_forbid_together(tmp_path: Path) -> None:
    """A row cannot both watch the terms page and switch off on a recorded phrase."""

    def both(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_url"] = TERMS_OF_USE
        row["terms_forbid"] = [FORBID_PHRASE]
        row["terms_watch"] = True
        row["basis_note"] = OWNER_BASIS_NOTE

    with pytest.raises(RegistryError, match="terms_watch and terms_forbid together"):
        load_registry(_mutated(tmp_path, "both.yaml", both))


def test_loader_refuses_a_bad_terms_forbid(tmp_path: Path) -> None:
    """terms_forbid must be a non-empty list of non-empty strings, with a terms URL."""

    def empty(document: dict[str, object]) -> None:
        _row(document, "fdi_projects")["terms_forbid"] = []

    with pytest.raises(RegistryError, match="terms_forbid is empty"):
        load_registry(_mutated(tmp_path, "empty.yaml", empty))

    def not_list(document: dict[str, object]) -> None:
        _row(document, "fdi_projects")["terms_forbid"] = FORBID_PHRASE

    with pytest.raises(RegistryError, match="not a list of non-empty strings"):
        load_registry(_mutated(tmp_path, "text.yaml", not_list))

    def blank(document: dict[str, object]) -> None:
        _row(document, "investqa_pages")["terms_forbid"] = [""]

    with pytest.raises(RegistryError, match="not a list of non-empty strings"):
        load_registry(_mutated(tmp_path, "blank.yaml", blank))

    def no_url(document: dict[str, object]) -> None:
        row = _row(document, "roads_osm")
        row["terms_url"] = ""
        row["terms_forbid"] = [FORBID_PHRASE]

    with pytest.raises(RegistryError, match="terms_forbid set without terms_url"):
        load_registry(_mutated(tmp_path, "no-url.yaml", no_url))


def test_loader_uses_the_safe_loader_only() -> None:
    """The registry module calls safe_load and does not call yaml.load."""
    module = (
        REPO
        / "custodian"
        / "src"
        / "eii_custodian"
        / "publicdata"
        / "fetch"
        / "registry.py"
    )
    text = module.read_text(encoding="utf-8")
    assert "safe_load" in text
    assert "yaml.load" not in text


def test_only_the_transport_module_opens_a_connection() -> None:
    """A planted module that opens a connection fails the seam scan."""
    assert scan_tree(REPO) == ()
    planted = {"custodian/src/eii_custodian/planted.py": "import urllib.request\n"}
    assert opener_hits(planted) == ("custodian/src/eii_custodian/planted.py",)


def test_cache_path_is_gitignored() -> None:
    """The public cache path is ignored, so a fetched file is not committed."""
    import subprocess

    done = subprocess.run(
        ["git", "check-ignore", "-q", "--", "data/public_cache"],
        cwd=REPO,
        check=False,
    )
    assert done.returncode == 0
