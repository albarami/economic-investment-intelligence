"""Portal licence statement: the portal's own words and URL, not the registry id."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from eii_custodian.publicdata.fetch.build import fetch_entry, run_build
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response, Transport

KEY_NAMES = ("EARTHDATA_API_KEY", "TOMTOM_API_KEY")

PORTAL = "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/planted-slug/exports/json"
META = PORTAL[: -len("/exports/json")]
CC_BY_TEXT = "CC BY"
CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"


def _clock() -> str:
    return "2026-11-13T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _entry() -> Entry:
    return Entry(
        key="planted",
        source_id="planted",
        slug="planted-slug",
        kind="portal_dataset",
        title_en="Planted portal dataset",
        publisher="Planted publisher",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host="www.data.gov.qa",
        url=PORTAL,
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
        extension="json",
        landing_url=PORTAL,
        licence_url="https://www.data.gov.qa/pages/license/annexes",
    )


def _ok(url: str, body: bytes) -> Response:
    return Response(final_url=url, body=body, hops=())


def _meta(
    licence: str, licence_url: str, publisher: str = "Planted publisher"
) -> bytes:
    """Hand-written Explore API metadata: metas.default.license and license_url."""
    payload = {
        "metas": {
            "default": {
                "publisher": publisher,
                "license": licence,
                "license_url": licence_url,
                "modified": "2026-08-04",
            }
        }
    }
    return json.dumps(payload).encode("utf-8")


def _sidecar(folder: Path) -> dict[str, object]:
    found = list(folder.rglob("*.meta.json"))
    assert len(found) == 1
    loaded = json.loads(found[0].read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_cc_by_4_accepts_only_the_portal_statement_and_records_it(
    tmp_path: Path,
) -> None:
    """CC-BY-4.0 passes only for license CC BY with the CC BY 4.0 URL, and the sidecar keeps both."""
    assert (
        fetch_entry(
            _entry(),
            _transport(CC_BY_TEXT, CC_BY_URL),
            tmp_path,
            _clock,
            _sleep,
        )
        is None
    )
    side = _sidecar(tmp_path)
    assert side["licence_id"] == "CC-BY-4.0"
    assert side["portal_licence"] == CC_BY_TEXT
    assert side["portal_licence_url"] == CC_BY_URL


def test_cc_by_4_rejects_any_other_portal_statement(tmp_path: Path) -> None:
    """Any licence text or URL other than the portal's CC BY pair fails and stores nothing."""
    statements = (
        ("CC BY 4.0", ""),
        ("CC BY", ""),
        ("CC BY", "https://creativecommons.org/licenses/by/3.0/"),
        ("CC-BY", CC_BY_URL),
        ("cc by", CC_BY_URL),
    )
    for index, (text, url) in enumerate(statements):
        cache = tmp_path / str(index)
        failure = fetch_entry(_entry(), _transport(text, url), cache, _clock, _sleep)
        assert failure is not None, (text, url)
        assert failure.check == "licence_mismatch", (text, url)
        assert [path for path in cache.rglob("*") if path.is_file()] == []


def test_fail_line_names_check_expected_and_observed(tmp_path: Path) -> None:
    """A planted mismatch is named on the FAIL line and in the build log, with no key."""
    observed_url = "https://example.invalid/licence"
    cache = tmp_path / "licence"
    outcome = run_build(
        (_entry(),),
        _transport("closed", observed_url),
        cache,
        _clock,
        _sleep,
    )
    line = _one_fail(outcome.lines)
    assert "licence_mismatch" in line
    assert (
        f"expected=text:{CC_BY_TEXT} url:{CC_BY_URL} "
        f"observed=text:closed url:{observed_url}"
    ) in line
    logged = _logged_lines(cache)
    assert line in logged
    for name in KEY_NAMES:
        assert name not in line
        assert name not in "\n".join(logged)

    publisher = tmp_path / "publisher"
    publisher_line = _one_fail(
        run_build(
            (_entry(),),
            _transport(CC_BY_TEXT, CC_BY_URL, publisher="Other"),
            publisher,
            _clock,
            _sleep,
        ).lines
    )
    assert "publisher_mismatch" in publisher_line
    assert "expected=Planted publisher" in publisher_line
    assert "observed=Other" in publisher_line

    counted = replace(_entry(), row_count_min=2, row_count_max=2)
    count_line = _one_fail(
        run_build((counted,), _rows(b"[{}]"), tmp_path / "count", _clock, _sleep).lines
    )
    assert "row_count" in count_line
    assert "expected=2..2" in count_line
    assert "observed=1" in count_line

    typed = replace(_entry(), columns=(("zone", "integer"),))
    field_line = _one_fail(
        run_build(
            (typed,),
            _rows(b'[{"zone": "text"}]'),
            tmp_path / "field",
            _clock,
            _sleep,
        ).lines
    )
    assert "schema_retyped" in field_line
    assert "expected=zone:integer" in field_line
    assert "observed=string" in field_line

    dated = replace(_entry(), period_field="year", period_last="2025")
    period_line = _one_fail(
        run_build(
            (dated,),
            _rows(b'[{"year": "2020"}]'),
            tmp_path / "period",
            _clock,
            _sleep,
        ).lines
    )
    assert "period_last" in period_line
    assert "expected=2025" in period_line
    assert "observed=2020" in period_line


def test_publisher_folds_case_and_space_and_names_a_different_publisher(
    tmp_path: Path,
) -> None:
    """The same name in another case or spacing passes; another publisher is named."""
    entry = replace(_entry(), publisher="Kahramaa")
    folded = tmp_path / "folded"
    assert (
        fetch_entry(
            entry,
            _transport(CC_BY_TEXT, CC_BY_URL, publisher="KAHRAMAA"),
            folded,
            _clock,
            _sleep,
        )
        is None
    )
    assert _sidecar(folded)["publisher"] == "KAHRAMAA"

    spaced = tmp_path / "spaced"
    assert (
        fetch_entry(
            _entry(),
            _transport(CC_BY_TEXT, CC_BY_URL, publisher="Planted   publisher"),
            spaced,
            _clock,
            _sleep,
        )
        is None
    )
    assert _sidecar(spaced)["publisher"] == "Planted   publisher"

    line = _one_fail(
        run_build(
            (entry,),
            _transport(CC_BY_TEXT, CC_BY_URL, publisher="Planted other publisher"),
            tmp_path / "other",
            _clock,
            _sleep,
        ).lines
    )
    assert "publisher_mismatch" in line
    assert "expected=Kahramaa" in line
    assert "observed=Planted other publisher" in line


def _transport(
    licence: str, licence_url: str, publisher: str = "Planted publisher"
) -> Transport:
    def transport(url: str) -> Response:
        if url == META:
            return _ok(url, _meta(licence, licence_url, publisher))
        return _ok(url, b'[{"zone": 1}]')

    return transport


def _rows(body: bytes) -> Transport:
    def transport(url: str) -> Response:
        if url == META:
            return _ok(url, _meta(CC_BY_TEXT, CC_BY_URL))
        return _ok(url, body)

    return transport


def _one_fail(lines: tuple[str, ...]) -> str:
    found = [line for line in lines if line.startswith("FAIL ")]
    assert len(found) == 1
    return found[0]


def _logged_lines(cache: Path) -> list[str]:
    loaded = json.loads((cache / "build-log.json").read_text(encoding="utf-8"))
    lines = loaded["lines"]
    assert isinstance(lines, list)
    return [line for line in lines if isinstance(line, str)]
