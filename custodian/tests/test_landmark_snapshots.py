"""Citation acquisition through the real build dispatch, on invented pages only."""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_s2_t29_live_shapes import declaration, entry

from eii_custodian.publicdata.fetch import allowlist, page_records
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response

URL = "https://syn.example.invalid/page-a"
STAMP = "2026-11-21T01:02:03Z"
BODY = b"<html><body><p>Roof: 123.40 m</p></body></html>"


def citation_setup(monkeypatch):
    dec = declaration("citation_snapshot", {}, [])
    dec.update(url=URL, reviewed_urls=[URL])
    row = replace(
        entry(dec, "landmark_syn_publisher"),
        key="landmark_syn_publisher/page-a",
        publisher="SYN Publisher",
        fetch_host="syn.example.invalid",
        release_tables=(),
        landing_url=URL,
    )
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS | {"syn.example.invalid"}
    )
    monkeypatch.setattr(page_records, "load_declaration", lambda key: dec)
    return row, dec


def test_build_public_fetch_entry_archives_citation_and_receipt(tmp_path, monkeypatch):
    row, _ = citation_setup(monkeypatch)
    result = run_build(
        (row,),
        lambda u: Response(u, BODY, ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        _fetch_only=True,
    )
    assert result.failure is None, result.lines
    parsed = read_snapshot(tmp_path / row.key, result.manifests[row.key])
    payload = json.loads(parsed.body)
    assert payload["rows"] == []
    raw = read_snapshot(
        tmp_path / row.key / "inputs/input-0", payload["inputs"][0]["identity"]
    )
    assert raw.body == BODY
    assert raw.sidecar["key"] == row.key
    assert raw.sidecar["retrieved_utc"] == STAMP
    assert raw.sidecar["commit_allowed"] is False


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("columns", "schema_missing"),
        ("release_tables", "schema_missing"),
        ("source_kind", "schema_missing"),
        ("period_fields", "schema_missing"),
        ("shape", "schema_missing"),
        ("commit", "commit_refused"),
        ("offhost", "blocked_host"),
    ],
)
def test_citation_contract_refusals(tmp_path, monkeypatch, plant, reason):
    row, dec = citation_setup(monkeypatch)
    if plant == "columns":
        row = replace(row, columns=(("SYN", "string"),))
        dec["columns"] = [["SYN", "string"]]
    elif plant == "release_tables":
        row = replace(row, release_tables=("pub_SYN",))
    elif plant == "source_kind":
        row = replace(row, source_id="events_visit_qatar")
    elif plant == "period_fields":
        dec["period_fields"] = ["SYN"]
    elif plant == "shape":
        dec["shape"] = {"SYN": "extra"}
    elif plant == "commit":
        row = replace(row, commit_allowed=True)
    elif plant == "offhost":
        dec["reviewed_urls"].append("https://syn-other.invalid/no")
    with pytest.raises(page_records.PageError, match=f"^{reason}$"):
        page_records.fetch_page(
            row,
            lambda u: Response(u, BODY, ()),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
        )
    assert not list(tmp_path.rglob("index/*.json"))


def test_generic_user_agent_has_no_contact_detail(monkeypatch):
    from unittest.mock import MagicMock

    from eii_custodian.publicdata.fetch.transport import open_https

    citation_setup(monkeypatch)
    opener = MagicMock()
    response = opener.open.return_value.__enter__.return_value
    response.geturl.return_value = URL
    response.read.side_effect = [BODY, b""]
    response.headers = {}
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: opener)
    open_https(URL)
    request = opener.open.call_args.args[0]
    assert request.get_header("User-agent") == "EII-Public-Citation-Client/1.0"


def test_citation_parser_has_no_rows(monkeypatch):
    row, dec = citation_setup(monkeypatch)
    assert page_records.parse_body(BODY, row, dec) == []


def test_one_publisher_has_distinct_page_keys(tmp_path, monkeypatch):
    import yaml

    real_load = page_records.load_declaration
    row, dec = citation_setup(monkeypatch)
    other = replace(
        row, key="landmark_syn_publisher/page-b", url=URL + "-b", landing_url=URL + "-b"
    )
    second = dict(dec, url=other.url, reviewed_urls=[other.url])
    path = tmp_path / "declarations.yaml"
    path.write_text(yaml.safe_dump({"sources": {row.key: dec, other.key: second}}))
    seen = []

    def load(key):
        seen.append(key)
        return real_load(key, path)

    monkeypatch.setattr(page_records, "load_declaration", load)
    result = run_build(
        (row, other),
        lambda u: Response(u, BODY, ()),
        tmp_path / "cache",
        lambda: STAMP,
        lambda _: None,
        _fetch_only=True,
    )
    assert result.failure is None
    assert set(result.manifests) == {row.key, other.key}
    assert seen == [row.key, other.key]
    assert row.source_id == other.source_id
