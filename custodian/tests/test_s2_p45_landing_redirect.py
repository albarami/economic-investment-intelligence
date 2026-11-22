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
from eii_custodian.publicdata.fetch.allowlist import host_of
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


def _agency(tmp_path, monkeypatch, target_for, bodies=None, prior=None):
    """The live agency shape (rows R2 to R4): one landing, fifty-four sub-pages."""
    from custodian.tests.test_investment_bilingual import bilingual_utf8

    pages, originals = bilingual_utf8(copies=6)
    pages = pages[:54]
    row = fixture._agency_entry()
    originals.setdefault(row.url, b"<html>Invented landing.</html>")
    originals.update(bodies or {})
    if prior:
        prior(row, _redirecting(row, originals, target_for))
    row, cache, manifest, table = (
        row,
        *_selected(tmp_path, monkeypatch, row, originals, target_for, pages),
    )
    assert len(manifest["pages"]) == 55
    return row, cache, manifest, table


def _differing(cache, row, manifest):
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    return [
        page["url"]
        for page in manifest["pages"]
        if read_snapshot(cache / row.key, page["sha256"]).sidecar["fetch_url"]
        != page["url"]
    ]


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
    assert _differing(cache, row, manifest) == [row.url]  # rows R2 and R3
    digests = [page["sha256"] for page in manifest["pages"]]
    assert len(set(digests)) == len(digests)  # row R2: no digest names two urls
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


def test_landing_with_a_sub_page_body_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The archive keeps a body's first receipt: a landing answering with the
    bytes of a sub-page archived earlier carries that sub-page's receipt."""
    from custodian.tests.test_investment_bilingual import bilingual_utf8

    from eii_custodian.publicdata.fetch.allowlist import HostDecision
    from eii_custodian.publicdata.investment_build import _fetch_page

    _pages, copied = bilingual_utf8(copies=6)
    chosen = fixture.SECTOR_URL.replace("agency.invalid/", "agency.invalid/c0/en/")
    row = fixture._agency_entry()

    def earlier(entry, transport):
        monkeypatch.setattr(
            "eii_custodian.publicdata.fetch.kinds.approve",
            lambda u: HostDecision(True, host_of(u), "https", ""),
        )
        fetched = _fetch_page(
            entry,
            tmp_path / "data/public_cache",
            chosen,
            transport,
            lambda _: None,
            lambda: "2026-11-13T08:00:00Z",
            "SYN-terms",
        )
        assert isinstance(fetched, tuple)

    row, cache, manifest, _table = _agency(
        tmp_path,
        monkeypatch,
        lambda u: u + REDIRECTED,
        bodies={row.url: copied[chosen]},
        prior=earlier,
    )
    landing = manifest["pages"][0]
    assert sum(page["sha256"] == landing["sha256"] for page in manifest["pages"]) == 2
    with pytest.raises(AssemblyError, match=r"^assembly_investment_refused$"):
        context(cache, (row,)).reviewed_selections()


LANDING = "SYN-landing-digest"
PAGES = (
    {"url": fixture._agency_entry().url, "sha256": LANDING},
    {"url": fixture.SECTOR_URL, "sha256": "SYN-sector-digest"},
)


def _receipt(**changes: object) -> dict[str, object]:
    row = fixture._agency_entry()
    receipt: dict[str, object] = {
        "key": row.key,
        "fetch_url": row.url + REDIRECTED,
        "sha256": LANDING,
    }
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
        ({"fetch_url": 123}, "landing", False),
        ({"fetch_url": True}, "landing", False),
        ({"fetch_url": ["SYN"]}, "landing", False),
        ({"fetch_url": fixture.SECTOR_URL}, "landing", False),
        ({"shared": True}, "landing", False),
    ],
    ids=[
        "landing-redirect",
        "exact",
        "sub-page-redirect",
        "other-host",
        "other-key",
        "no-address",
        "number-address",
        "boolean-address",
        "list-address",
        "address-names-a-page",
        "digest-of-another-page",
    ],
)
def test_fetched_from_changes_one_input(receipt, page, expected) -> None:
    from eii_custodian.publicdata.assembly_native import _fetched_from

    row = fixture._agency_entry()
    page_url = row.url if page == "landing" else fixture.SECTOR_URL
    changed = _receipt(**receipt)
    if changed["fetch_url"] == "SAME":
        changed["fetch_url"] = page_url
    pages = PAGES
    if changed.pop("shared", False):
        pages = (PAGES[0], {**PAGES[1], "sha256": LANDING})
    assert _fetched_from(changed, page_url, row, pages) is expected


def test_entry_without_host_never_accepts_a_redirect() -> None:
    from dataclasses import replace

    from eii_custodian.publicdata.assembly_native import _fetched_from

    row = replace(fixture._agency_entry(), url="SYN-relative/")
    receipt = {"key": row.key, "fetch_url": "SYN-relative/" + REDIRECTED}
    pages = ({"url": row.url, "sha256": None},)
    assert _fetched_from(receipt, row.url, row, pages) is False
