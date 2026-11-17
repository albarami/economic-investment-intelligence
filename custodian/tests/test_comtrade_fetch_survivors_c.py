"""Transport classes, splits and quoted secrets for the Comtrade fetch survivors."""

from __future__ import annotations

import json
import locale
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from custodian.tests.fixtures.comtrade.invented import body_for
from custodian.tests.test_comtrade_fetch_survivors import (
    HEADER,
    KEYED_HOST,
    PUBLIC_HOST,
    UNCONFIRMED_URL,
    _endpoint,
    _entry,
    _keyed,
    _message,
    _ok,
    _policy,
    _run,
    _shape,
    _url,
)
from custodian.tests.test_comtrade_fetch_survivors_b import (
    MIRROR_KEY,
    REPORTER_KEY,
    _folder,
)

from eii_custodian.publicdata.comtrade.fetch import (
    _atomic_text,
    _host_for,
    _write_coverage,
    _write_manifest,
)
from eii_custodian.publicdata.comtrade.state import fresh
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    PreparedRequest,
    SlotSecrets,
)


def test_auth_throttle_and_status_keep_the_descriptor(tmp_path: Path) -> None:
    """Transport classes keep the closed URL and hide a descriptor secret."""

    def opener(request: PreparedRequest) -> AttemptResult:
        return AttemptResult(category, b"{}")

    category = "auth"
    auth = _run(tmp_path / "auth", _entry(_policy()), opener, SlotSecrets("keyed", ""))
    _shape(
        auth,
        _message("authentication", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    category = "throttle"
    throttled = _run(
        tmp_path / "throttle", _entry(_policy()), opener, SlotSecrets("keyed", "")
    )
    _shape(
        throttled,
        _message("throttled", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    category = "other"
    status = _run(
        tmp_path / "status", _entry(_policy()), opener, SlotSecrets(HEADER, "")
    )
    _shape(status, _keyed("http_status"), KEYED_HOST, 2, 0, 2)
    hidden = _run(
        tmp_path / "status-hidden", _entry(_policy()), opener, SlotSecrets("keyed", "")
    )
    _shape(
        hidden,
        _message("http_status", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )


def test_header_echo_and_error_text_are_provider_errors(tmp_path: Path) -> None:
    """An echoed header and an error string are provider errors with the closed URL."""
    echoed = _run(
        tmp_path / "echo",
        _entry(_policy()),
        lambda _request: AttemptResult("ok", b"{}", header_echo="echoed"),
        SlotSecrets("keyed", ""),
    )
    _shape(
        echoed,
        _message("provider_error", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    faulted = _run(
        tmp_path / "fault",
        _entry(_policy()),
        lambda _request: AttemptResult("ok", b"{}", error_text="invented-fault"),
        SlotSecrets("keyed", ""),
    )
    _shape(
        faulted,
        _message("provider_error", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    plain = _run(
        tmp_path / "plain-fault",
        _entry(_policy()),
        lambda _request: AttemptResult("ok", b"{}", error_text="invented-fault"),
        SlotSecrets(HEADER, ""),
    )
    _shape(plain, _keyed("provider_error"), KEYED_HOST, 2, 0, 2)


def test_parse_failure_keeps_the_parser_check(tmp_path: Path) -> None:
    """A body that is not an object keeps the parser check and the closed URL."""
    hidden = _run(
        tmp_path / "hidden",
        _entry(_policy()),
        lambda _request: AttemptResult("ok", b"[]"),
        SlotSecrets("keyed", ""),
    )
    _shape(
        hidden,
        _message("metadata_unreadable", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    plain = _run(
        tmp_path / "plain",
        _entry(_policy()),
        lambda _request: AttemptResult("ok", b"[]"),
        SlotSecrets(HEADER, ""),
    )
    _shape(plain, _keyed("metadata_unreadable"), KEYED_HOST, 2, 0, 2)


def test_truncation_and_an_indivisible_leaf_keep_their_checks(tmp_path: Path) -> None:
    """A count past the cap, and a leaf with no split, keep their checks."""
    over = _run(
        tmp_path / "over",
        _entry(_policy()),
        lambda request: AttemptResult("ok", body_for(request, count=4)),
        SlotSecrets(HEADER, ""),
    )
    _shape(over, _keyed("truncation"), KEYED_HOST, 2, 0, 2)
    over_hidden = _run(
        tmp_path / "over-hidden",
        _entry(_policy()),
        lambda request: AttemptResult("ok", body_for(request, count=4)),
        SlotSecrets("keyed", ""),
    )
    _shape(
        over_hidden,
        _message("truncation", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    leaf = _policy(subdivision_fields=[], subdivision_values={}, keyed_record_limit=1)
    exact = _run(
        tmp_path / "leaf",
        _entry(leaf),
        lambda request: AttemptResult("ok", body_for(request, count=1)),
        SlotSecrets(HEADER, ""),
    )
    _shape(exact, _keyed("unresolved_truncation"), KEYED_HOST, 2, 0, 2)
    exact_hidden = _run(
        tmp_path / "leaf-hidden",
        _entry(leaf),
        lambda request: AttemptResult("ok", body_for(request, count=1)),
        SlotSecrets("keyed", ""),
    )
    _shape(
        exact_hidden,
        _message("unresolved_truncation", UNCONFIRMED_URL, "redacted"),
        KEYED_HOST,
        2,
        0,
        2,
    )


def test_public_limit_is_the_public_cap(tmp_path: Path) -> None:
    """Three public rows are past the public cap of two."""
    policy = _policy(public_record_limit=2, keyed_record_limit=4)

    def opener(request: PreparedRequest) -> AttemptResult:
        return AttemptResult("ok", body_for(request, count=3))

    result = _run(tmp_path, _entry(policy), opener, None, api_class="public")
    _shape(
        result,
        _message(
            "truncation",
            _url("mirror", api="public"),
            _endpoint("mirror", api="public"),
        ),
        PUBLIC_HOST,
        2,
        0,
        2,
    )


def test_slash_secret_uses_the_fully_quoted_form(tmp_path: Path) -> None:
    """A slash in the header is matched only in its fully quoted form."""
    marker = "a/b"
    encoded = "a%2Fb"

    def opener(request: PreparedRequest) -> AttemptResult:
        payload = json.loads(body_for(request))
        payload["data"][0]["flag"] = encoded
        return AttemptResult("ok", json.dumps(payload).encode())

    refused = _run(
        tmp_path / "quoted", _entry(_policy()), opener, SlotSecrets(marker, "")
    )
    _shape(refused, _keyed("provider_error"), KEYED_HOST, 2, 0, 2)
    plain = _run(tmp_path / "plain", _entry(_policy()), _ok, SlotSecrets(marker, ""))
    assert plain.failure is None


def test_product_split_puts_the_reviewed_child_on_the_url(tmp_path: Path) -> None:
    """A response at the cap is replaced by the reviewed product children."""
    policy = _policy(keyed_record_limit=2, daily_calls=12)
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.url)
        if len(seen) > 10:
            return AttemptResult("other", b"")
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    result = _run(tmp_path, _entry(policy), opener, SlotSecrets(HEADER, ""))
    assert result.failure is None
    assert _url("mirror", product="ch-a-1") in seen
    assert _url("reporter", product="ch-a-2") in seen
    folder = tmp_path / "un_comtrade"
    applied = []
    for path in folder.glob("*.meta.json"):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        applied.append(loaded["applied_limit"])
    assert applied
    assert all(item == 2 for item in applied)


def test_child_at_the_cap_stays_unresolved(tmp_path: Path) -> None:
    """A product child at the cap cannot split again."""
    policy = _policy(keyed_record_limit=1, daily_calls=12)
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.url)
        if len(seen) > 6:
            return AttemptResult("other", b"")
        return AttemptResult("ok", body_for(request, count=1))

    result = _run(tmp_path, _entry(policy), opener, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message(
            "unresolved_truncation",
            _url("mirror", product="ch-a-1"),
            _endpoint("mirror", product="ch-a-1"),
        ),
        KEYED_HOST,
        2,
        0,
        2,
    )
    assert len(seen) == 3


def test_absent_template_host_is_the_first_template() -> None:
    """A class with no template resolves to the first template host."""
    assert _host_for(_policy(), "absent") == PUBLIC_HOST


def test_partial_name_is_dot_name_dot_partial(tmp_path: Path) -> None:
    """The partial is the dotted name, and a missed write still raises the original."""
    target = tmp_path / "coverage.json"
    seen: list[str] = []
    real = Path.write_text

    def spy(self: Path, text: str, *args: object, **kwargs: object) -> int:
        seen.append(self.name)
        return real(self, text, *args, **kwargs)

    Path.write_text = spy
    try:
        _atomic_text(target, "invented\n")
    finally:
        Path.write_text = real
    assert seen == [".coverage.json.partial"]
    assert target.read_text(encoding="utf-8") == "invented\n"
    assert not (tmp_path / ".coverage.json.partial").exists()

    def fail(self: Path, text: str, *args: object, **kwargs: object) -> int:
        if self.name.endswith(".partial"):
            raise OSError("full")
        return real(self, text, *args, **kwargs)

    Path.write_text = fail
    try:
        try:
            _atomic_text(tmp_path / "again.json", "invented\n")
        except OSError as exc:
            assert str(exc) == "full"
        else:
            raise AssertionError("write")
    finally:
        Path.write_text = real


def test_partial_write_uses_utf8_for_a_non_ascii_text(tmp_path: Path) -> None:
    """A non-ASCII partial is written as UTF-8 even when the locale is ASCII."""
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        _atomic_text(tmp_path / "note.json", "invented-é\n")
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert (tmp_path / "note.json").read_bytes() == "invented-é\n".encode()


def test_coverage_on_a_stop_records_zero_present_cells(tmp_path: Path) -> None:
    """A stop before any accept records the price fields and zero present cells."""
    result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets("", ""))
    _shape(
        result,
        _message("primary_absent", f"https://{PUBLIC_HOST}/refused", "primary_absent"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    coverage = json.loads(
        (_folder(tmp_path) / "coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["present_cells"] == 0
    assert coverage["gap_cells"] == 2
    assert coverage["missing"] == [MIRROR_KEY, REPORTER_KEY]
    assert coverage["price_amount"] == "9.50"
    text = (_folder(tmp_path) / "coverage.json").read_text(encoding="utf-8")
    assert text.index('"gap_cells"') < text.index('"missing"')
    assert text.index('"price_amount"') < text.index('"price_source"')
    assert text.index('"source_id"') > text.index('"requested_cells"')


def test_supplied_missing_list_is_what_coverage_records(tmp_path: Path) -> None:
    """A supplied gap list is kept. Public callers only pass the recomputed list."""
    policy = _policy()
    directory = tmp_path / "coverage-supplied"
    directory.mkdir()
    _write_coverage(
        directory,
        policy,
        (),
        fresh("invented-policy", "invented-selection", (), "2026-11-16"),
        ("role=kept|sub=",),
        entry=_entry(policy),
        retrieved="2026-11-16T08:00:00Z",
    )
    coverage = json.loads((directory / "coverage.json").read_text(encoding="utf-8"))
    assert coverage["missing"] == ["role=kept|sub="]
    assert coverage["gap_cells"] == 1


def test_manifest_reads_planted_sidecar_bytes(tmp_path: Path) -> None:
    """The manifest read uses UTF-8 and keeps a non-object sidecar empty."""
    policy = _policy()
    directory = tmp_path / "manifest-planted"
    directory.mkdir()
    (directory / "note-e.meta.json").write_bytes(b'{"sha256":"invented-\xc3\xa9"}')
    (directory / "note-list.meta.json").write_text("[]\n", encoding="utf-8")
    ledger = replace(
        fresh("invented-policy", "invented-selection", (), "2026-11-16"),
        child_sha256=(
            ("role=a|sub=", "note-e"),
            ("role=b|sub=", "note-list"),
        ),
    )
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        _write_manifest(
            directory,
            policy,
            (),
            ledger,
            (),
            entry=_entry(policy),
            retrieved="2026-11-16T08:00:00Z",
        )
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    loaded = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    by_key = {item["key"]: item["sha256"] for item in loaded["children"]}
    assert by_key["role=a|sub="] == "invented-é"
    assert by_key["role=b|sub="] == ""
