"""Visible-text fingerprints of watched terms pages.

A previous build log that records a raw-byte digest has no
``terms_fingerprint`` of ``visible_text``. The TERMS line compares only
fingerprints of that kind, so the first run after this change does not treat
a raw-byte digest as a changed terms page.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from eii_custodian.publicdata.fetch.build import BuildOutcome, run_build
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response

PAGE = "https://fdiprojects.invest.qa/"
TERMS = "https://fdiprojects.invest.qa/terms"
VISIBLE = "Invented terms sentence for a caf\u00e9."
CHANGED = "Invented terms sentence for a caf\u00e9 now differs."
_SPACE = re.compile(r"\s+")


def _clock() -> str:
    return "2026-11-13T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _ok(url: str, body: bytes) -> Response:
    return Response(final_url=url, body=body, hops=())


def _visible_sha256(text: str) -> str:
    """Oracle: NFC of collapsed visible text, then SHA-256."""
    collapsed = _SPACE.sub(" ", text).strip()
    normalised = unicodedata.normalize("NFC", collapsed)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _page(*, token: str, nonce: str, sentence: str) -> bytes:
    """Invented terms HTML. The sentence is the only visible text."""
    html = (
        "<html><head>"
        f'<meta name="csrf-token" content="{token}">'
        f'<script nonce="{nonce}">var unused = 1;</script>'
        "<style>body { color: red; }</style>"
        "</head><body>"
        "<!-- planted comment -->"
        f"{sentence}"
        "</body></html>"
    )
    return html.encode("utf-8")


def _watched() -> Entry:
    return Entry(
        key="watched_source",
        source_id="watched_source",
        slug="watched-slug",
        kind="terms_page",
        title_en="Planted watched page",
        publisher="Planted publisher",
        licence_id="CC-BY-4.0",
        licence_basis="owner_decision",
        decision_record="0017",
        fetch_host="fdiprojects.invest.qa",
        url=PAGE,
        terms_url=TERMS,
        nightly_live_fetch=False,
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
        extension="html",
        landing_url=PAGE,
        terms_watch=True,
        basis_note="planted watch",
    )


def _build(cache: Path, terms: bytes) -> tuple[object, dict[str, object]]:
    watched = _watched()

    def transport(url: str) -> Response:
        if url == TERMS:
            return _ok(url, terms)
        if url == PAGE:
            return _ok(url, b"<html>invented dashboard</html>")
        raise AssertionError(url)

    outcome = run_build((watched,), transport, cache, _clock, _sleep)
    loaded = json.loads((cache / "build-log.json").read_text(encoding="utf-8"))
    return outcome, loaded


def test_token_nonce_and_whitespace_keep_one_fingerprint(tmp_path: Path) -> None:
    """A meta token, a script nonce or white space does not print TERMS."""
    noisy = _page(
        token="token-one",
        nonce="nonce-one",
        sentence="  Invented   terms&nbsp;sentence for a cafe\u0301.  ",
    )
    quiet = _page(token="token-two", nonce="nonce-two", sentence=VISIBLE)
    first, first_log = _build(tmp_path, noisy)
    second, second_log = _build(tmp_path, quiet)
    expected = _visible_sha256(VISIBLE)
    assert first.failure is None
    assert second.failure is None
    assert not any(line.startswith("TERMS ") for line in first.lines)
    assert not any(line.startswith("TERMS ") for line in second.lines)
    assert first_log["terms"][0]["terms_sha256"] == expected
    assert second_log["terms"][0]["terms_sha256"] == expected
    assert first_log["terms"][0]["terms_sha256"] != sha256_hex(noisy)
    assert second_log["terms"][0].get("terms_fingerprint") == "visible_text"


def test_changed_terms_sentence_prints_the_terms_line(tmp_path: Path) -> None:
    """A changed terms sentence has a new fingerprint and prints TERMS."""
    watched = _watched()
    _build(tmp_path, _page(token="token-one", nonce="nonce-one", sentence=VISIBLE))
    outcome, loaded = _build(
        tmp_path, _page(token="token-one", nonce="nonce-one", sentence=CHANGED)
    )
    notice = f"TERMS {watched.key} changed since the last build ({watched.terms_url})"
    assert outcome.failure is None
    assert notice in outcome.lines
    assert loaded["terms"][0]["terms_sha256"] == _visible_sha256(CHANGED)
    assert loaded["terms"][0]["terms_sha256"] != _visible_sha256(VISIBLE)


SERVED_GOV = "https://www.data.gov.qa/invented-page"
SERVED_QA = "https://www.data.qa/invented-page"
PAGE_ALPHA = b"<html>invented dashboard alpha</html>"
PAGE_BETA = b"<html>invented dashboard beta</html>"
STAMP_FIRST = "2026-11-13T08:00:00Z"
STAMP_SECOND = "2026-11-13T09:00:00Z"


def test_second_build_names_its_own_page_host_and_terms(tmp_path: Path) -> None:
    """Two cached receipts cannot decide the later PASS line, host or terms."""
    _expect_second_receipt(
        tmp_path / "alpha-then-beta",
        earlier=(SERVED_GOV, PAGE_ALPHA, VISIBLE, STAMP_FIRST),
        later=(SERVED_QA, PAGE_BETA, CHANGED, STAMP_SECOND),
    )
    _expect_second_receipt(
        tmp_path / "beta-then-alpha",
        earlier=(SERVED_QA, PAGE_BETA, CHANGED, STAMP_FIRST),
        later=(SERVED_GOV, PAGE_ALPHA, VISIBLE, STAMP_SECOND),
    )


def _expect_second_receipt(
    cache: Path,
    *,
    earlier: tuple[str, bytes, str, str],
    later: tuple[str, bytes, str, str],
) -> None:
    """The second run's page, host, terms hash and retrieval time are the ones named."""
    watched = _watched()
    _run_pair(cache, earlier)
    outcome = _run_pair(cache, later)
    served, page, sentence, stamp = later
    digest = sha256_hex(page)
    host = served.split("/", 3)[2]
    notice = f"TERMS {watched.key} changed since the last build ({watched.terms_url})"
    passed = f"PASS {watched.key} sha256={digest} host={host}"
    loaded = json.loads((cache / "build-log.json").read_text(encoding="utf-8"))
    metas = sorted(
        path.name
        for path in (cache / watched.key).iterdir()
        if path.name.endswith(".meta.json")
    )
    assert metas == sorted(
        (
            f"{sha256_hex(earlier[1])}.meta.json",
            f"{digest}.meta.json",
        )
    )
    assert [line for line in outcome.lines if line.startswith("PASS ")] == [passed]
    assert notice in outcome.lines
    assert [line for line in loaded["lines"] if line.startswith("PASS ")] == [passed]
    assert notice in loaded["lines"]
    assert loaded["terms"] == [
        {
            "key": watched.key,
            "retrieved_utc": stamp,
            "terms_sha256": _visible_sha256(sentence),
            "terms_fingerprint": "visible_text",
            "terms_url": watched.terms_url,
        }
    ]


def _run_pair(cache: Path, spec: tuple[str, bytes, str, str]) -> BuildOutcome:
    """Fetch one watched page and its terms page, served from spec's host."""
    served, page, sentence, stamp = spec
    terms = _page(token="token-one", nonce="nonce-one", sentence=sentence)

    def transport(url: str) -> Response:
        if url == TERMS:
            return _ok(url, terms)
        if url == PAGE:
            return Response(final_url=served, body=page, hops=())
        raise AssertionError(url)

    return run_build((_watched(),), transport, cache, lambda: stamp, _sleep)


def test_raw_byte_previous_log_does_not_print_a_false_terms_line(
    tmp_path: Path,
) -> None:
    """A raw-byte previous digest is another kind, so it is not compared."""
    watched = _watched()
    earlier = _page(token="token-one", nonce="nonce-one", sentence=VISIBLE)
    later = _page(token="token-two", nonce="nonce-two", sentence=VISIBLE)
    previous = {
        "lines": [],
        "terms": [
            {
                "key": watched.key,
                "retrieved_utc": "2026-11-12T08:00:00Z",
                "terms_sha256": sha256_hex(earlier),
                "terms_url": watched.terms_url,
            }
        ],
    }
    (tmp_path / "build-log.json").write_text(json.dumps(previous), encoding="utf-8")
    outcome, loaded = _build(tmp_path, later)
    assert outcome.failure is None
    assert not any(line.startswith("TERMS ") for line in outcome.lines)
    assert loaded["terms"][0]["terms_sha256"] == _visible_sha256(VISIBLE)
    assert loaded["terms"][0]["terms_sha256"] != sha256_hex(later)
    assert loaded["terms"][0].get("terms_fingerprint") == "visible_text"
