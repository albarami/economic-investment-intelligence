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
# SHA-256 of the canonical JSON of (key, skip_reason, basis_note) for every
# committed registry row, computed at base 1dba941bcf; this row's two changed
# fields are restored before hashing. Missing optional notes are empty strings.
BASE_PROJECTION_SHA256 = (
    "d17073ec9da4f03806d6222f18ccd9e54fcff3e9d1bcb595315b94c3497d1e30"
)
BASE_ROW_COUNT = 891
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
    restored = [
        dict(item, skip_reason="", basis_note=BASE_BASIS_NOTE)
        if item["key"] == ROW
        else item
        for item in rows
    ]
    projection = [
        {
            "key": item["key"],
            "skip_reason": item.get("skip_reason", ""),
            "basis_note": item.get("basis_note", ""),
        }
        for item in restored
    ]
    assert _canonical_rows(projection) == BASE_PROJECTION_SHA256
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
