"""S2-P45: the landing page of an investment source may answer through a
same-host redirect. The ordinary fetch stores the final address in the
landing receipt (build.py keeps ``final_url``), while the evidence manifest
names the requested URL. Assembly accepts that one shape for the landing page
only, bound to the entry's own key and host and to the pinned identity; a
sub-page keeps its exact URL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from custodian.tests import test_investment_build as fixture
from custodian.tests.test_production_adapters import context

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.fetch.transport import Response

REDIRECTED = "SYN-landing"


def _redirecting(row, bodies, target_for):
    def transport(url: str) -> Response:
        if url == row.terms_url:
            return Response(final_url=url, body=fixture.TERMS_BODY, hops=())
        if url == row.url:
            return Response(final_url=target_for(url), body=bodies[url], hops=())
        if url in bodies:
            return Response(final_url=url, body=bodies[url], hops=())
        raise AssertionError(url)

    return transport


def _selected(tmp_path, monkeypatch, row, bodies, target_for, pages=None):
    transport = _redirecting(row, bodies, target_for)
    assert fixture._execute(tmp_path, monkeypatch, row, transport, pages) == 0
    pointer, manifest, table = fixture._batch(tmp_path, row.source_id)
    cache = tmp_path / "data/public_cache"
    landing = manifest["pages"][0]
    assert landing["url"] == row.url
    (cache / "snapshot_pins.json").write_text(
        json.dumps(
            {
                row.key: landing["sha256"],
                row.key + "/evidence": pointer["manifest_sha256"],
            }
        )
    )
    return cache, manifest, table


def _fdi(tmp_path, monkeypatch, target_for):
    row = fixture._fdi_entry()
    return row, *_selected(
        tmp_path, monkeypatch, row, {row.url: fixture.dashboard_page()}, target_for
    )


def _agency(tmp_path, monkeypatch, target_for):
    from custodian.tests.test_investment_bilingual import bilingual

    pages, originals = bilingual()
    originals = {
        url: body.replace(b"<body>", b'<head><meta charset="utf-8"></head><body>')
        for url, body in originals.items()
    }
    row = fixture._agency_entry()
    originals.setdefault(row.url, b"<html>Invented landing.</html>")
    return row, *_selected(tmp_path, monkeypatch, row, originals, target_for, pages)


@pytest.mark.parametrize(
    "source", [_fdi, _agency], ids=["fdi_projects", "investqa_pages"]
)
def test_same_host_landing_redirect_reaches_the_release_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source
) -> None:
    row, cache, manifest, table = source(
        tmp_path, monkeypatch, lambda u: u + REDIRECTED
    )
    landing = manifest["pages"][0]
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    stored = read_snapshot(cache / row.key, landing["sha256"]).sidecar["fetch_url"]
    assert stored == row.url + REDIRECTED  # the real shape: final address kept
    state = context(cache, (row,))
    state.reviewed_selections()
    name = "fdi_projects" if row.source_id == "fdi_projects" else "pub_investqa_record"
    assert state.tables[name] == table["rows"]


@pytest.mark.parametrize(
    "source", [_fdi, _agency], ids=["fdi_projects", "investqa_pages"]
)
def test_landing_redirect_to_another_host_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source
) -> None:
    def elsewhere(url: str) -> str:
        return "https://other.invalid/" + REDIRECTED

    row, cache, _manifest, _table = source(tmp_path, monkeypatch, elsewhere)
    with pytest.raises(AssemblyError, match=r"^assembly_investment_refused$"):
        context(cache, (row,)).reviewed_selections()


def _receipt(**changes: object) -> dict[str, object]:
    row = fixture._agency_entry()
    receipt: dict[str, object] = {"key": row.key, "fetch_url": row.url + REDIRECTED}
    receipt.update(changes)
    return receipt


@pytest.mark.parametrize(
    "receipt,page,expected",
    [
        ({}, "landing", True),
        ({"fetch_url": "SAME"}, "sub", True),
        ({}, "sub", False),
        ({"fetch_url": "https://other.invalid/" + REDIRECTED}, "landing", False),
        ({"key": "SYN-other-key"}, "landing", False),
        ({"fetch_url": None}, "landing", False),
    ],
    ids=[
        "landing-redirect",
        "exact",
        "sub-page-redirect",
        "other-host",
        "other-key",
        "no-address",
    ],
)
def test_fetched_from_changes_one_input(receipt, page, expected) -> None:
    from eii_custodian.publicdata.assembly_native import _fetched_from

    row = fixture._agency_entry()
    page_url = row.url if page == "landing" else fixture.SECTOR_URL
    changed = _receipt(**receipt)
    if changed["fetch_url"] == "SAME":
        changed["fetch_url"] = page_url
    assert _fetched_from(changed, page_url, row) is expected


def test_entry_without_host_never_accepts_a_redirect() -> None:
    from dataclasses import replace

    from eii_custodian.publicdata.assembly_native import _fetched_from

    row = replace(fixture._agency_entry(), url="SYN-relative/")
    receipt = {"key": row.key, "fetch_url": "SYN-relative/" + REDIRECTED}
    assert _fetched_from(receipt, row.url, row) is False
