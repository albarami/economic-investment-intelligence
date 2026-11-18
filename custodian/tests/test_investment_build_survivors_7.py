"""Publication lineage and active-process text encoding regression plants."""

from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_investment_build import (
    _agency_entry,
    _agency_transport_bodies,
    _batch,
    _fdi_entry,
    _run,
)
from custodian.tests.test_investment_build_survivors import _failure, _spec

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.investment_contracts import DashboardShape


def test_dashboard_rejects_missing_field_before_reading_cache(tmp_path: Path) -> None:
    # PUB-07 requires every mapped field; capex_value is deliberately absent.
    shape = DashboardShape(
        "fdi-dashboard-v2",
        frozenset(
            {
                "announced",
                "business_function",
                "capex_value",
                "company",
                "jobs",
                "location_text",
                "project_type",
                "sector",
                "source_country",
                "sub_sector",
            }
        )
        - {"capex_value"},
        {
            "company": "investing_company_name",
            "source_country": "src_country_name",
            "sector": "sector_name",
            "sub_sector": "sub_sector_name",
            "business_function": "function_name",
            "project_type": "project_type_name",
            "capex_value": "capex",
            "jobs": "jobs",
            "announced": "project_date",
            "location_text": "project_address",
        },
        {},
        {},
        {},
    )
    result = build._publish_dashboard(
        _fdi_entry(),
        replace(_spec(), dashboard=shape),
        tmp_path,
        "SYN-missing-page",
        lambda: "2026-01-03T04:05:06Z",
    )
    _failure(result, "1|fdi_projects||confirmation_fields|mapped fields|capex_value")
    assert list(tmp_path.iterdir()) == []


def test_agency_parsed_evidence_keeps_landing_page_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # PUB-04's receipt identifies the source of both aggregate evidence objects.
    entry = _agency_entry()
    assert _run(tmp_path, monkeypatch, entry, _agency_transport_bodies()) == 0
    pointer, manifest, _ = _batch(tmp_path, entry.source_id)
    evidence = tmp_path / "data/public_cache" / entry.source_id / "evidence"
    for identity in (
        manifest["table_snapshot_identity"],
        pointer["evidence_manifest_identity"],
    ):
        snapshot = read_snapshot(evidence, identity)
        assert snapshot.sidecar["fetch_url"] == "https://agency.invalid/"


@pytest.fixture
def ascii_default_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make unspecified text encodings ASCII without restarting the tested code.

    Path text I/O uses io.text_encoding to resolve its default. Overriding only
    that default exercises the active mutation even under Python UTF-8 mode;
    explicit codec arguments retain their real behavior. An exec subprocess
    would lose pytest's source path and the mutation runner's active function.
    """
    text_encoding = io.text_encoding

    def encoding_or_ascii(encoding: str | None, stacklevel: int = 2) -> str:
        return "ascii" if encoding is None else text_encoding(encoding, stacklevel)

    monkeypatch.setattr(io, "text_encoding", encoding_or_ascii)


def test_read_json_uses_utf8_with_ascii_default(
    tmp_path: Path, ascii_default_encoding: None
) -> None:
    source = tmp_path / "SYN-input.json"
    source.write_bytes(b'{"SYN-text": "caf\xc3\xa9"}')
    # Pin the simulated default without relying on an implicit-encoding read.
    assert io.text_encoding(None) == "ascii"
    assert source.read_text(encoding="utf-8") == '{"SYN-text": "caf\u00e9"}'
    assert build._read_json(source) == {"SYN-text": "caf\u00e9"}


def test_atomic_write_uses_utf8_with_ascii_default(
    tmp_path: Path, ascii_default_encoding: None
) -> None:
    default_path = tmp_path / "SYN-default.txt"
    assert io.text_encoding(None) == "ascii"
    default_path.write_text("caf\u00e9", encoding="utf-8")
    assert default_path.read_bytes() == b"caf\xc3\xa9"
    destination = tmp_path / "SYN-nested/SYN-output.txt"
    build._atomic_write(destination, "caf\u00e9\n")
    assert destination.read_bytes() == b"caf\xc3\xa9\n"
    assert sorted(path.name for path in destination.parent.iterdir()) == [
        "SYN-output.txt"
    ]
