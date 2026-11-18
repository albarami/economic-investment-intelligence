"""Archive existing tender-reader output, without another fetch."""

import json
from pathlib import Path

import pytest
from custodian.tests.singles_entries import tender_entry

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_tenders import archive_pages
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.singles.tenders import (
    LIST_PATHS,
    ListReading,
    _write_pages,
)


def test_tender_archive_contains_every_list_language_and_named_page(
    tmp_path: Path,
) -> None:
    entry = tender_entry()
    stored = []
    readings = []
    for list_name, _ in LIST_PATHS:
        for language in ("en", "ar"):
            stored.append((list_name, language, 1, b"<html>SYN-page</html>"))
            readings.append(
                ListReading(
                    list_name,
                    language,
                    1,
                    1,
                    "2026-11-18T00:00:00Z",
                    "2026-11-18T00:00:00Z",
                )
            )
    _write_pages(tmp_path / entry.key, stored, readings)
    identity = archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")
    selected = read_snapshot(tmp_path / entry.key, identity)
    payload = json.loads(selected.body)
    assert payload["method"] == "assembly-tender-pages.v1"
    assert len(payload["pages"]) == len(LIST_PATHS) * 2
    assert {p["language"] for p in payload["pages"]} == {"en", "ar"}
    assert selected.sidecar["sha256"] == identity
    (tmp_path / entry.key / "available/en/1.html").unlink()
    # Already published immutable bytes remain readable; capture itself refuses
    # a missing file instead of substituting yesterday's assembled envelope.
    assert read_snapshot(tmp_path / entry.key, identity).sha256 == identity
    with pytest.raises(AssemblyError, match="assembly_tender_pages_incomplete"):
        archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")
