"""S2-T08 part B, mismatch class 9: an unread terms page keeps its advisory and
its attempt, apart from the recorded reading date.

The live shape pack's Mismatches item 9 shows a terms host off the allow-list
and a terms page that answered 403. The advisory lines stay; the build log adds
one attempt record with the attempt time and the reason, and the row's recorded
``terms_read_on`` and own words stay exactly as the registry holds them. The
data still passes, nothing is fingerprinted, and no reading date is made from
the attempt. The heights manifest carries the attempt beside, never in place
of, the recorded reading date. Every address and text below is invented.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.heights import invented
from custodian.tests.test_publicdata_behaviour import (
    _FILE_TERMS,
    FILE_URL,
    _clock,
    _entry,
    _ok,
    _sidecar,
    _sleep,
    _stored_page,
)

from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.report import terms_attempt_record
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.heights.step import build_heights

ATTEMPTED = _clock()
UNLISTED = "https://evil.example/planted-terms"


def _log(folder: Path) -> dict[str, object]:
    return json.loads((folder / "build-log.json").read_text(encoding="utf-8"))


def _refusing(url: str) -> Response:
    if url == _FILE_TERMS:
        raise TransportFault("http", url)
    if url == FILE_URL:
        return _ok(url, b"invented-bytes")
    raise AssertionError(url)


@pytest.mark.parametrize("read_on", ["", "2026-01-02"], ids=["unread", "recorded"])
@pytest.mark.parametrize(
    ("terms_url", "reason", "advisory"),
    [
        (
            UNLISTED,
            "host_not_allow_listed",
            f"not read: host evil.example is not on the allow-list ({UNLISTED})",
        ),
        (_FILE_TERMS, "http_status", f"not read: http_status ({_FILE_TERMS})"),
    ],
    ids=["unlisted_host", "http_403"],
)
def test_an_unread_terms_page_is_recorded_as_an_attempt_only(
    tmp_path: Path, terms_url: str, reason: str, advisory: str, read_on: str
) -> None:
    entry = replace(
        _entry(),
        terms_url=terms_url,
        terms_read_on=read_on,
        terms_words="invented pending own words",
    )
    outcome = run_build((entry,), _refusing, tmp_path, _clock, _sleep)
    # The data is still admitted and the advisory line is unchanged.
    assert outcome.failure is None
    assert f"TERMS {entry.key} {advisory}" in outcome.lines
    assert _stored_page(tmp_path, entry.key).read_bytes() == b"invented-bytes"
    log = _log(tmp_path)
    assert log["terms"] == []
    assert log["terms_attempts"] == [
        {
            "key": entry.key,
            "terms_url": terms_url,
            "terms_attempted_utc": ATTEMPTED,
            "terms_unread_reason": reason,
            "terms_read_on": read_on,
            "terms_words": "invented pending own words",
        }
    ]
    # No reading date is made from the attempt.
    side = _sidecar(tmp_path)
    assert side["terms_read_on"] == read_on
    assert side["terms_sha256"] is None


def test_a_read_terms_page_records_no_attempt(tmp_path: Path) -> None:
    entry = replace(_entry(), terms_url=_FILE_TERMS)

    def transport(url: str) -> Response:
        return _ok(url, b"<p>Invented terms.</p>" if url == _FILE_TERMS else b"x")

    assert run_build((entry,), transport, tmp_path, _clock, _sleep).failure is None
    log = _log(tmp_path)
    assert log["terms_attempts"] == []
    assert len(log["terms"]) == 1


def test_the_attempt_record_keeps_the_recorded_date_apart() -> None:
    entry = replace(_entry(), terms_url=UNLISTED, terms_read_on="")
    record = terms_attempt_record(entry, "host_not_allow_listed", ATTEMPTED)
    assert record["terms_read_on"] == ""
    assert record["terms_attempted_utc"] == ATTEMPTED
    assert set(record) == {
        "key",
        "terms_url",
        "terms_attempted_utc",
        "terms_unread_reason",
        "terms_read_on",
        "terms_words",
    }


def _heights(tmp_path: Path, attempts: tuple[dict[str, object], ...]) -> dict:
    buildings, globfp, wsf = invented.card_fixture(tmp_path)
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
    wsf_row = invented.entry("bldg_wsf3d", extension="tif")
    cache = tmp_path / "data" / "public_cache"
    invented.store(cache, globfp_row, globfp)
    invented.store(cache, wsf_row, wsf)
    path = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buildings)
    out_dir = tmp_path / "data" / "assets" / "heights"
    build_heights(
        cache,
        (globfp_row, wsf_row),
        path,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
        terms_attempts=attempts,
    )
    return json.loads((out_dir / "manifest.heights.json").read_text())


def test_the_heights_manifest_carries_the_attempt_beside_the_recorded_date(
    tmp_path: Path,
) -> None:
    attempt = terms_attempt_record(
        replace(
            invented.entry("bldg_wsf3d", extension="tif"),
            terms_url=UNLISTED,
        ),
        "host_not_allow_listed",
        ATTEMPTED,
    )
    credits = _heights(tmp_path, (attempt,))["credits"]
    wsf = credits["bldg_wsf3d"]
    # The recorded reading date and words are the registry's, not the attempt's.
    assert wsf["terms_read_on"] == "2026-11-14"
    assert wsf["terms_read_on"] != ATTEMPTED[:10]
    assert wsf["terms_attempts"] == [attempt]
    assert credits["bldg_3dglobfp"]["terms_attempts"] == []


def test_the_heights_manifest_without_attempts_names_none(tmp_path: Path) -> None:
    credits = _heights(tmp_path, ())["credits"]
    assert credits["bldg_wsf3d"]["terms_attempts"] == []
    assert credits["bldg_3dglobfp"]["terms_attempts"] == []
