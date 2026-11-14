"""Fetch engine: an unlisted host is refused before any byte is read."""

from __future__ import annotations

from pathlib import Path

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.transport import Response


def test_refuses_unlisted_host(tmp_path: Path) -> None:
    """A fixture that would return bytes for an outside host is not called."""
    called = False

    def transport(url: str) -> Response:
        nonlocal called
        called = True
        return Response(final_url=url, body=b"planted-bytes", hops=())

    entry = Entry(
        key="planted_outside",
        source_id="planted_outside",
        slug="",
        kind="https_file",
        title_en="Planted outside host",
        publisher="Planted publisher",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host="evil.example",
        url="https://evil.example/planted.bin",
        terms_url="",
        nightly_live_fetch=True,
        public_splits=(),
        commit_allowed=False,
        release_tables=(),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="bin",
        landing_url="",
    )
    failure = fetch_entry(entry, transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "blocked_host"
    assert called is False
    assert list(tmp_path.iterdir()) == []


def test_paged_layer_count_address_uses_the_layer_id(tmp_path: Path) -> None:
    """District count queries layer 12; zone count queries layer 0."""
    by_id = {entry.source_id: entry for entry in load_registry()}
    district = _layer_urls(by_id["bnd_district_2020"], tmp_path / "district")
    zone = _layer_urls(by_id["bnd_zone_2020"], tmp_path / "zone")
    assert district[0].split("?", 1)[0].endswith("/FeatureServer/12/query")
    assert "/FeatureServer/12/query?" in district[0]
    assert zone[0].split("?", 1)[0].endswith("/FeatureServer/0/query")
    assert "/FeatureServer/0/query?" in zone[0]
    assert district[1].split("?", 1)[0].endswith("/FeatureServer/12/query")
    assert zone[1].split("?", 1)[0].endswith("/FeatureServer/0/query")
    assert by_id["bnd_district_2020"].layer == 12
    assert by_id["bnd_zone_2020"].layer == 0


def _layer_urls(entry: Entry, cache: Path) -> tuple[str, str]:
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if "returnCountOnly" in url:
            return Response(final_url=url, body=b'{"count": 1}', hops=())
        return Response(
            final_url=url, body=b'{"features": [{"attributes": {}}]}', hops=()
        )

    failure = fetch_entry(entry, transport, cache, _clock, _sleep)
    assert failure is None
    counts = [url for url in seen if "returnCountOnly" in url]
    pages = [url for url in seen if "returnCountOnly" not in url]
    assert len(counts) == 1
    assert len(pages) == 1
    return counts[0], pages[0]


def _clock() -> str:
    return "2026-11-13T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None
