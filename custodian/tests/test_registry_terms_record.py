"""Audit committed terms records without making unread terms a fetch gate."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.registry import (
    LICENCE_BASIS_PENDING,
    TERMS_WORDS_PENDING,
    RegistryError,
    load_registry,
    read_yaml,
    registry_path,
)
from eii_custodian.publicdata.fetch.transport import Response


def _assert_terms_records(path: Path) -> None:
    # Reuse the loader's closed vocabulary and real-calendar-date checks.
    # Decision 0059 keeps incomplete readings loadable by the production reader.
    entries = load_registry(path)
    document = read_yaml(path)
    assert isinstance(document, dict)
    failures = []
    for row, entry in zip(document["sources"], entries, strict=True):
        basis = entry.licence_basis
        if basis == LICENCE_BASIS_PENDING:
            continue
        words = row.get("terms_words", "")
        if words == TERMS_WORDS_PENDING:
            # These are local-use/provider records, not claims of an open
            # dataset grant. Their unread terms remain usable (0059 item 1).
            if basis not in {"owner_decision", "provider_terms"}:
                failures.append((row["key"], "unread terms claim an open basis"))
            continue
        for field in ("terms_url", "terms_words", "terms_read_on"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append((row["key"], field))
        if row["terms_read_on"] == "pending":
            failures.append((row["key"], "terms_read_on"))
    assert not failures, failures


def test_committed_terms_records() -> None:
    _assert_terms_records(registry_path())


def _assert_baci_terms_reading(pack: str) -> None:
    """Require BACI's own terms-table row, including its supplied page digest."""
    rows = [
        line
        for line in pack.splitlines()
        if line.startswith("| `cepii_baci` |") and len(line.split("|")) == 7
    ]
    assert len(rows) == 1, "BACI terms-reading row missing or duplicated"
    cells = [cell.strip() for cell in rows[0].split("|")[1:-1]]
    assert cells[1] == '"Licence: Etalab 2.0"'
    assert cells[2] == "2026-11-20"
    assert cells[3] == "`dataset`"
    assert (
        "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37" in cells[4]
    )
    # Supplied lead reading, reproduced in document 04; not an archive hash.
    assert (
        "0689cf69a963eb0ca6ef05731482b04898bcef215a90127edeb2a78ff4990c60" in cells[4]
    )


def test_baci_publisher_terms_reading_is_recorded() -> None:
    pack = repository_root(Path(__file__)) / "docs" / "04_PUBLIC_DATA_PACK.md"
    _assert_baci_terms_reading(pack.read_text(encoding="utf-8"))


def test_planted_removal_of_baci_terms_reading_is_detected() -> None:
    pack = repository_root(Path(__file__)) / "docs" / "04_PUBLIC_DATA_PACK.md"
    text = pack.read_text(encoding="utf-8")
    _assert_baci_terms_reading(text)
    planted = "\n".join(
        line
        for line in text.splitlines()
        if not (line.startswith("| `cepii_baci` |") and len(line.split("|")) == 7)
    )
    # The quote elsewhere in the pack cannot mask removal of this table row.
    planted += '\n"Licence: Etalab 2.0"\n'
    with pytest.raises(AssertionError, match="BACI terms-reading row missing"):
        _assert_baci_terms_reading(planted)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("terms_url", ""),
        ("terms_url", " \t "),
        ("terms_words", ""),
        ("terms_words", " \t "),
        ("terms_read_on", ""),
        ("terms_read_on", " \t "),
        ("terms_read_on", "2026-02-30"),
        ("terms_read_on", "pending"),
        ("licence_basis", "invented_basis"),
        ("terms_words", "terms to be read"),
    ],
)
def test_planted_incomplete_or_malformed_record_is_detected(
    tmp_path: Path, field: str, value: str
) -> None:
    document = read_yaml(registry_path())
    assert isinstance(document, dict)
    row = document["sources"][0]
    document = {"sources": [row]}
    row.update(
        licence_basis="dataset",
        terms_url="https://example.invalid/terms",
        terms_words="Invented terms for a synthetic guard plant.",
        terms_read_on="2026-11-19",
    )
    row[field] = value
    path = tmp_path / "planted.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises((AssertionError, RegistryError)):
        _assert_terms_records(path)


@pytest.mark.parametrize("basis", ["pending", ""])
def test_pending_basis_remains_loadable_and_auditable(
    tmp_path: Path, basis: str
) -> None:
    document = read_yaml(registry_path())
    assert isinstance(document, dict)
    row = document["sources"][0]
    document = {"sources": [row]}
    row.update(licence_basis=basis, terms_url="", terms_words="", terms_read_on="")
    path = tmp_path / "pending.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    _assert_terms_records(path)
    assert load_registry(path)[0].licence_basis == "pending"


GIS_TERMS_KEYS = frozenset(
    {
        "gis_address",
        "gis_boundaries",
        "gis_context",
        "gis_imagery_history",
        "gis_land_price",
        "gis_landmarks",
        "gis_locator",
        "gis_parcels",
        "gis_phcc",
        "gis_poi_comm",
        "gis_rail",
        "gis_zoning",
    }
)
# S2-LIC.b2 saved rendered home page, read on 2026-11-27 Qatar time:
# SHA-256 860d736387422a279c41d6a79640e36196d0850961638b68a879462aa234e82a.
# Site-wide reservation only; no reuse permission or licence inferred.
GIS_TERMS_READING = {
    "terms_url": "https://www.gisqatar.org.qa/ar/home",
    "terms_words": "© جميع الحقوق محفوظة 2024 @ CGIS Qatar",
    "terms_read_on": "2026-11-27",
    "licence_id": "",
    "licence_basis": "owner_decision",
}


def _assert_gis_terms_reading(rows: list[dict]) -> None:
    selected = [row for row in rows if row["key"] in GIS_TERMS_KEYS]
    assert len(selected) == len(GIS_TERMS_KEYS)
    assert {row["key"] for row in selected} == GIS_TERMS_KEYS
    for row in selected:
        assert {
            field: row[field] for field in GIS_TERMS_READING
        } == GIS_TERMS_READING, ("GIS terms reading differs", row["key"])


def test_gis_site_wide_terms_reading_is_recorded() -> None:
    document = read_yaml(registry_path())
    _assert_gis_terms_reading(document["sources"])


def test_planted_gis_reading_change_is_detected() -> None:
    rows = [dict(key=key, **GIS_TERMS_READING) for key in GIS_TERMS_KEYS]
    _assert_gis_terms_reading(rows)
    rows[0]["terms_words"] += "!"
    with pytest.raises(AssertionError, match="GIS terms reading differs"):
        _assert_gis_terms_reading(rows)


def test_gis_terms_build_records_advisory_without_request(tmp_path: Path) -> None:
    committed = next(e for e in load_registry() if e.key == "gis_boundaries")
    # Real terms URL, invented source addresses and cache; no live transport.
    entry = replace(
        committed,
        url="https://syn.example.invalid/layer",
        landing_url="https://syn.example.invalid/layer",
    )
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        raise AssertionError("no request for the skipped GIS row or its terms")

    cache = tmp_path / "public_cache"
    cache.mkdir()
    outcome = run_build(
        (entry,),
        transport,
        cache,
        lambda: "2026-11-27T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
    )
    assert seen == []
    assert outcome.failure is None
    advisory = (
        "TERMS gis_boundaries not read: host www.gisqatar.org.qa "
        "is not on the allow-list (https://www.gisqatar.org.qa/ar/home)"
    )
    assert [line for line in outcome.lines if line.startswith("TERMS ")] == [advisory]
    log = json.loads((cache / "build-log.json").read_text())
    assert log["terms"] == []
    assert log["terms_attempts"] == [
        {
            "key": "gis_boundaries",
            "terms_url": GIS_TERMS_READING["terms_url"],
            "terms_attempted_utc": "2026-11-27T00:00:00Z",
            "terms_unread_reason": "host_not_allow_listed",
            "terms_read_on": "2026-11-27",
            "terms_words": GIS_TERMS_READING["terms_words"],
        }
    ]
