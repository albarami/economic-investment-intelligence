"""S2-P81, decision 0107 (proposed): a landmark citation page the publisher no
longer serves is a registered SKIP by one closed word; every other FAIL refuses.

Invented hosts only (``*.invalid``); the transport is a stub, so no request can
leave the machine even when a guard is deleted.
"""

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_registry_terms_record import (
    GIS_TERMS_KEYS,
    _assert_gis_terms_reading,
)
from hypothesis import example, given
from hypothesis import strategies as st

import landmark_citation_rows as generator
from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.fetch import allowlist, page_records, registry
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.transport import Response

WORD = "page_not_served"
ROW = (
    "landmark_skyscraperpage_com/"
    "page-a4474c164d99fd530665e2e45c1419e2e7872e9ba8cefe248e372243c595d794"
)
# SHA-256 of the canonical JSON of every committed registry row at base
# 1dba941bcf; this row's two changed fields are restored before hashing, and
# only the reviewed per-row byte ceiling added later by S2-P84
# (`stream_max_bytes`, absent at that base) is left out of every row.
BASE_ROWS_SHA256 = "771b96a4afb3ffca7e914ab783663cfd2fca4542ce0b478aaab48b1627e69593"
LATER_REVIEWED_FIELDS = frozenset({"stream_max_bytes"})
# S2-ABSCAV set one catalogue caveat on each skipped row. The pin restores
# those lists to the empty value it was taken against.
ABSENCE_CAVEAT_KEYS = frozenset(
    {
        "accident",
        "places_fsq",
        "weather_openmeteo",
        "bldg_ovt/part-00288",
        "gis_boundaries",
        "gis_imagery_history",
        "insurance_tables",
        "events_visit_qatar",
        "events_qncc",
        "suppliers_tawteen",
        "manateq_tariffs",
        "monaqasat_classified",
        "schools_private_directory",
        "satellite_cdse_backup",
        "fc_register",
        ROW,
    }
)
BASE_ROW_COUNT = 891
# S2-P86 (ruling L-1724 item 1) rewrote the last sentence of the prop_sales
# basis note after this pin was taken. That row's note must equal the reviewed
# text exactly, and its base text is restored before hashing, so no other byte
# of any row may change.
P86_ROW = "prop_sales"
# S2-P92 reviewed the publisher's revised counts; restore only those two fields
# to their base values before hashing, as for S2-P86's reviewed note.
P92_ROW = "trade_logistics/annual-certificates-of-origin-by-type-and-importing-country"
# S2-GLFILL confirmed cell units and DOI on the 40 file rows of this source
# (its parent row carries neither field); restore both before hashing.
GLFILL_SOURCE = "worldpop_qat_agesex"
P86_BASE_BASIS_NOTE = (
    "Columns are the observed export fields (S2-T08 part B source "
    "review, mismatch 3; "
    "custodian/publicdata/review/s2_t08_source_review.yaml). The shape "
    "pack shows names only: the types of lstkhdm and of the four "
    "numeric fields first declared there await the lead's live run. "
    "Share fields refuse by name until their meaning is confirmed."
)
P86_BASIS_NOTE = (
    "Columns are the observed export fields (S2-T08 part B source "
    "review, mismatch 3; "
    "custodian/publicdata/review/s2_t08_source_review.yaml). The shape "
    "pack shows names only: the types of lstkhdm and of the four "
    "numeric fields first declared there await the lead's live run. "
    "Ruling L-1724 item 1 keeps whole-property deals only; "
    "partial_share_deal and share_fields_inconsistent rows are excluded "
    "and counted per row, never priced; share-field meaning remains "
    "unconfirmed."
)
# S2-CWEB (decision 0076, reviewed in S2-CWEB.rv) added one caveat key to the
# company-web row after this pin was taken. That row's caveat keys must equal
# the reviewed value exactly, and the base value is restored before hashing,
# as for S2-P86 and S2-P92, so no other byte of any row may change.
CWEB_ROW = "company_web"
CWEB_CAVEAT_KEYS = ["company_web_lead_shell_only"]
# S2-OUTFIX D2 reviewed these two places verification lineage declarations.
PLACES_LINEAGE_KEYS = frozenset({"places_ovt", "places_ovt/part-00014"})
BASE_BASIS_NOTE = (
    "Document 04 S2-P53 landmark hand-list placement and citation snapshots; "
    "decision 0093 item 3. Publisher's restriction recorded as a record; "
    "no reuse permission inferred."
)


def _invented(monkeypatch, skip_reason=""):
    output = generator.generate(
        {
            "publishers": [
                {
                    "publisher": "SYN Publisher",
                    "terms_url": None,
                    "terms_words": "SYN all rights reserved",
                    "checked_on": "2026-11-24",
                    "note": "SYN reading only",
                }
            ],
            "landmarks": [
                {
                    "page_url": "https://syn.example.invalid/one",
                    "publisher": "SYN Publisher",
                }
            ],
        }
    )
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS | set(output["hosts"])
    )
    row = dict(output["sources"][0], skip_reason=skip_reason)
    declaration = output["declarations"][row["key"]]
    monkeypatch.setattr(
        page_records,
        "load_declaration",
        lambda key, *_args: declaration if key == row["key"] else pytest.fail(key),
    )
    return row


def _build(tmp_path: Path, entry: registry.Entry):
    cache = tmp_path / "data" / "public_cache"
    cache.mkdir(parents=True)
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        assert url.startswith("https://syn.example.invalid/")
        return Response(url, b"<p>SYN not found</p>", (), status=404)

    # The fetch seam that assembly's fetch_archive calls.
    outcome = run_build(
        (entry,),
        transport,
        cache,
        lambda: "2026-11-24T04:00:00Z",
        lambda _s: None,
        _fetch_only=True,
    )
    return outcome, seen


def _assembly(tmp_path: Path, outcome):
    build = context(tmp_path / "assembly")
    build.fetcher = lambda: outcome
    return build


def test_row_with_the_word_parses_and_is_reported_skip(tmp_path, monkeypatch):
    entry = registry._entry(_invented(monkeypatch, WORD))
    assert entry.skip_reason == WORD
    outcome, seen = _build(tmp_path, entry)
    assert seen == []
    assert outcome.failure is None
    assert outcome.lines == (f"SKIP {entry.key} {WORD}",)
    build = _assembly(tmp_path, outcome)
    build.fetch_archive()
    assert build.lines == [f"SKIP {entry.key} {WORD}"]
    assert (tmp_path / "assembly/assembly/fetch_archive.json").is_file()


def test_same_404_without_the_word_fails_and_refuses_assembly(tmp_path, monkeypatch):
    entry = registry._entry(_invented(monkeypatch))
    assert entry.skip_reason == ""
    outcome, seen = _build(tmp_path, entry)
    assert seen == [entry.url]
    assert outcome.failure is not None
    assert outcome.failure.check == "http_status"
    assert outcome.lines[-1].startswith(f"FAIL {entry.key} ")
    assert "http_status" in outcome.lines[-1]
    build = _assembly(tmp_path, outcome)
    with pytest.raises(AssemblyError, match=r"^assembly_fetch_refused$"):
        build.fetch_archive()


@given(st.text(min_size=1, max_size=40).filter(lambda word: word != WORD))
@example("page_not_served ")
@example("Page_not_served")
@example("page_not_served;page_not_served")
@example("publisher_or_schema_unconfirmed")
@example("schema_unconfirmed")
@example("page_gone")
def test_unknown_word_on_a_citation_row_is_refused(word):
    with pytest.MonkeyPatch.context() as monkeypatch:
        row = _invented(monkeypatch)
        assert registry._entry(row).skip_reason == ""
        row["skip_reason"] = word
        with pytest.raises(
            registry.RegistryError,
            match=r"^(citation_skip_reason|skip_reason names a licence or terms)$",
        ):
            registry._entry(row)


def test_closed_set_holds_exactly_one_word():
    assert registry.CITATION_SKIP_REASONS == frozenset({WORD})
    assert WORD not in registry.TECHNICAL_SKIP_REASONS


def _canonical_rows(rows) -> str:
    return sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _glfill_confirmed(row) -> bool:
    return (
        row["source_id"] == GLFILL_SOURCE
        and row.get("cell_units") == "people_per_cell"
        and row.get("doi_confirmed") is True
    )


def test_only_this_row_changes_and_only_by_the_word_and_its_note():
    rows = registry.read_yaml(registry.registry_path())["sources"]
    assert len(rows) == BASE_ROW_COUNT
    matches = [row for row in rows if row["key"] == ROW]
    assert len(matches) == 1
    row = matches[0]
    assert row["skip_reason"] == WORD
    assert row["basis_note"].startswith(BASE_BASIS_NOTE + " ")
    assert "2026-11-24" in row["basis_note"]
    assert "0107" in row["basis_note"]
    p86 = [row for row in rows if row["key"] == P86_ROW]
    assert len(p86) == 1
    assert p86[0]["basis_note"] == P86_BASIS_NOTE
    p92 = [row for row in rows if row["key"] == P92_ROW]
    assert len(p92) == 1
    assert p92[0]["row_count_min"] == 1142
    assert p92[0]["row_count_max"] == 1142
    cweb = [row for row in rows if row["key"] == CWEB_ROW]
    assert len(cweb) == 1
    assert cweb[0]["caveat_keys"] == CWEB_CAVEAT_KEYS
    for key in PLACES_LINEAGE_KEYS:
        places = [row for row in rows if row["key"] == key]
        assert len(places) == 1
        assert places[0]["release_tables"] == ["pub_place", "pub_place_verification"]
        places[0]["release_tables"] = ["pub_place"]
    # S2-LICREC: check reviewed values before restoring only these base fields.
    _assert_gis_terms_reading(rows)
    rows = [
        dict(
            item,
            terms_url="",
            terms_words="terms to be read",
            terms_read_on="2026-11-15",
        )
        if item["key"] in GIS_TERMS_KEYS
        else item
        for item in rows
    ]
    assert sum(_glfill_confirmed(row) for row in rows) == 40
    restored = [
        {
            field: value
            for field, value in (
                dict(
                    item,
                    skip_reason="",
                    basis_note=BASE_BASIS_NOTE,
                    caveat_keys=[],
                )
                if item["key"] == ROW
                else dict(item, basis_note=P86_BASE_BASIS_NOTE)
                if item["key"] == P86_ROW
                else dict(item, row_count_min=1162, row_count_max=1162)
                if item["key"] == P92_ROW
                else dict(item, caveat_keys=[])
                if item["key"] == CWEB_ROW or item["key"] in ABSENCE_CAVEAT_KEYS
                else dict(item, cell_units="unconfirmed", doi_confirmed=False)
                if _glfill_confirmed(item)
                else item
            ).items()
            if field not in LATER_REVIEWED_FIELDS
        }
        for item in rows
    ]
    assert _canonical_rows(restored) == BASE_ROWS_SHA256
    entries = registry.load_registry()
    assert len(entries) == BASE_ROW_COUNT
    landmark = [e for e in entries if e.source_id.startswith("landmark_")]
    assert [e.key for e in landmark if e.skip_reason] == [ROW]


def test_committed_row_is_reported_skip_without_a_request(tmp_path):
    committed = next(e for e in registry.load_registry() if e.key == ROW)
    # Invented address: a deleted skip guard can never reach the real host.
    entry = replace(
        committed,
        url="https://syn.example.invalid/one",
        landing_url="https://syn.example.invalid/one",
        terms_url="",
    )

    def transport(url: str) -> Response:
        raise AssertionError("no request for a registered skip")

    cache = tmp_path / "data" / "public_cache"
    cache.mkdir(parents=True)
    outcome = run_build(
        (entry,),
        transport,
        cache,
        lambda: "2026-11-24T04:00:00Z",
        lambda _s: None,
        _fetch_only=True,
    )
    assert outcome.failure is None
    assert outcome.lines == (f"SKIP {ROW} {WORD}",)


def test_retained_snapshot_of_a_skipped_page_refuses_its_height(tmp_path, monkeypatch):
    """S2-P81.rv1 finding 1: a valid snapshot kept from an earlier build cannot
    carry a height once the cited page's registry row is skipped."""
    from custodian.tests.test_publicdata_heights import _cited_page

    from eii_custodian.publicdata.heights import landmarks
    from eii_custodian.publicdata.heights.model import HeightError

    cache, row, _digest, rows, verify = _cited_page(tmp_path, monkeypatch)
    verify()  # positive control: the unskipped row and its snapshot verify
    skipped = replace(row, skip_reason=WORD)
    monkeypatch.setattr(landmarks, "_registry_by_url", lambda: {row.url: skipped})
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, rows)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "registry_skipped",
    )
