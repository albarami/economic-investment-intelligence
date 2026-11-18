"""Round-3 confirmation plants. Invented responses only."""

from __future__ import annotations

import os
import traceback
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

import pytest
from custodian.tests.fixtures.comtrade.invented import (
    MARKER,
    body_for,
    invented_entry,
    invented_policy,
)

from eii_custodian.publicdata.comtrade.fetch import fetch_source
from eii_custodian.publicdata.comtrade.parse import ParseError, parse_body
from eii_custodian.publicdata.comtrade.partition import initial_partitions
from eii_custodian.publicdata.comtrade.policy import policy_sha256
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    PreparedRequest,
    SlotSecrets,
)

ESCAPED = "\\u0069" + MARKER[1:]
PRIMARY = "primary-marker"


def _clock() -> str:
    return "2026-11-16T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _narrow(**overrides: object):
    base: dict[str, object] = {
        "frequencies": ["annual"],
        "periods": ["2099"],
        "flows": ["flow-in"],
        "daily_calls": 8,
    }
    base.update(overrides)
    return invented_policy(**base)


def _written(cache: Path) -> str:
    folder = cache / "un_comtrade"
    if not folder.exists():
        return ""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    )


def _visible(failure: BaseException) -> str:
    trace = "".join(
        traceback.format_exception(type(failure), failure, failure.__traceback__)
    )
    return "\n".join((str(failure), repr(failure), trace))


def _reporter(policy: object):
    cell = next(
        item for item in initial_partitions(policy) if item.series_role == "reporter"
    )
    return cell.descriptor(policy, "keyed")


def _record(descriptor: object, product: str) -> dict[str, object]:
    return {
        "reporterCode": descriptor.reporter_code,
        "partnerCode": descriptor.partner_code,
        "partner2Code": None,
        "period": descriptor.period,
        "flowCode": descriptor.flow_code,
        "cmdCode": product,
        "primaryValue": "1.25",
        "qty": None,
        "flag": "",
        "classificationCode": "HS-INVENTED",
        "classificationRevision": descriptor.classification_revision,
        "aggregationLevel": 2,
        "customsCode": "customs-invented",
        "transportCode": "mode-invented",
        "valuationBasis": "value-invented",
    }


def _duplicate_body(
    request: PreparedRequest, field: str, first: str, second: str
) -> bytes:
    text = body_for(request).decode("utf-8")
    if field == "flag":
        text = text.replace(
            '"flag": ""',
            f'"flag": "{first}", "flag": "{second}"',
            1,
        )
    else:
        text = text.replace(
            "{",
            '{"' + field + '": "' + first + '", "' + field + '": "' + second + '", ',
            1,
        )
    raw = text.encode("utf-8")
    if first == ESCAPED:
        assert MARKER.encode("utf-8") not in raw
    return raw


def _fetch_duplicate(tmp_path: Path, field: str, first: str, second: str):
    def opener(request: PreparedRequest) -> AttemptResult:
        return AttemptResult("ok", _duplicate_body(request, field, first, second))

    raised: Exception | None = None
    try:
        result = fetch_source(
            invented_entry(_narrow()),
            tmp_path,
            _clock,
            _sleep,
            opener,
            SlotSecrets(MARKER, ""),
        )
    except Exception as exc:
        raised = exc
        rendered = traceback.format_exc()
        result = None
    else:
        assert result.failure is not None
        rendered = _visible(result.failure)
    for needle in (MARKER, ESCAPED, quote(MARKER, safe="")):
        assert needle not in rendered
        assert needle not in _written(tmp_path)
    assert raised is None
    assert result is not None
    assert result.failure is not None
    assert result.failure.check == "duplicate_member"
    folder = tmp_path / "un_comtrade"
    assert not (folder / "manifest.json").exists()
    assert not list(folder.glob("*.meta.json"))
    return result


def test_duplicate_ordinary_field_hides_an_escaped_marker(tmp_path: Path) -> None:
    """An escaped marker in an overwritten flag is refused and is not stored."""
    _fetch_duplicate(tmp_path, "flag", ESCAPED, "")


def test_duplicate_ignored_field_hides_an_escaped_marker(tmp_path: Path) -> None:
    """An escaped marker in an overwritten ignored field is refused and is not stored."""
    _fetch_duplicate(tmp_path, "note", ESCAPED, "")


def test_duplicate_member_without_a_marker_is_refused(tmp_path: Path) -> None:
    """A duplicate member with no marker is refused before acceptance."""
    _fetch_duplicate(tmp_path, "note", "alpha", "beta")


def test_prefix_product_outside_reviewed_children_is_refused() -> None:
    """A product that only shares the chapter digits is not a reviewed child."""
    policy = invented_policy(
        subdivision_values={"product": ["ch-a-1", "ch-a-9"]},
        chapter_products={"ch-a": ["ch-a-1"]},
    )
    descriptor = replace(_reporter(policy), subdivision=(("product", "ch-a-9"),))
    with pytest.raises(ParseError) as caught:
        parse_body(
            _body(descriptor, "ch-a-9"),
            policy,
            descriptor,
            source_version=policy.version,
            receipt_sha256="",
        )
    assert caught.value.check == "product_membership"


def test_product_under_the_wrong_chapter_is_refused() -> None:
    """A product reviewed under another chapter is refused for this chapter."""
    policy = invented_policy(
        chapters=["a", "ab"],
        subdivision_values={"product": ["ab-1", "a-9"]},
        chapter_products={"a": ["a-9"], "ab": ["ab-1"]},
    )
    descriptor = replace(
        _reporter(policy),
        chapter="a",
        subdivision=(("product", "ab-1"),),
    )
    with pytest.raises(ParseError) as caught:
        parse_body(
            _body(descriptor, "ab-1"),
            policy,
            descriptor,
            source_version=policy.version,
            receipt_sha256="",
        )
    assert caught.value.check == "product_membership"


def test_pending_chapter_mapping_refuses_product_subdivision(tmp_path: Path) -> None:
    """Product subdivision stays refused while the reviewed mapping is pending."""
    opened: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        opened.append(request.url)
        return AttemptResult("ok", body_for(request))

    result = fetch_source(
        invented_entry(_narrow(chapter_products=None)),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "chapter_products_pending"
    assert opened == []
    assert not (tmp_path / "un_comtrade").exists()


def test_children_follow_the_reviewed_chapter_mapping(tmp_path: Path) -> None:
    """A split requests only the chapter's reviewed products."""
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.url)
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    result = fetch_source(
        invented_entry(
            _narrow(
                keyed_record_limit=2,
                subdivision_values={"product": ["ch-a-1", "ch-a-9"]},
                chapter_products={"ch-a": ["ch-a-1"]},
            )
        ),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is None
    assert any("product=ch-a-1" in url for url in seen)
    assert all("ch-a-9" not in url for url in seen)


def test_chapter_mapping_changes_the_policy_hash() -> None:
    """A reviewed mapping change changes the policy hash on its own."""
    original = policy_sha256(invented_policy())
    changed = policy_sha256(
        invented_policy(chapter_products={"ch-a": ["ch-a-1", "ch-a-3"]})
    )
    assert changed != original


def test_lock_directory_failure_is_a_safe_refusal(tmp_path: Path) -> None:
    """A directory-creation failure is a fixed refusal and creates no lock."""
    real_mkdir = Path.mkdir

    def boom(self: Path, *args: object, **kwargs: object) -> None:
        raise OSError("disk")

    Path.mkdir = boom
    try:
        result = fetch_source(
            invented_entry(_narrow()),
            tmp_path,
            _clock,
            _sleep,
            lambda request: AttemptResult("ok", body_for(request)),
            SlotSecrets(PRIMARY, ""),
        )
    finally:
        Path.mkdir = real_mkdir
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    assert "disk" not in str(result.failure)
    assert "disk" not in repr(result.failure)
    folder = tmp_path / "un_comtrade"
    assert not (folder / "state.lock").exists()
    assert not (folder / "manifest.json").exists()
    assert not (folder / "state.json").exists()


def test_lock_close_failure_keeps_ownership(tmp_path: Path) -> None:
    """A close failure after the lock is created keeps the lock and writes nothing usable."""
    real_open = os.open
    real_close = os.close
    lock_fds: list[int] = []

    def tracking_open(path: str | os.PathLike[str], flags: int, *args: object) -> int:
        fd = real_open(path, flags, *args)
        if str(path).endswith("state.lock"):
            lock_fds.append(fd)
        return fd

    def boom_close(fd: int) -> None:
        if fd in lock_fds:
            raise OSError("closed")
        real_close(fd)

    os.open = tracking_open
    os.close = boom_close
    try:
        result = fetch_source(
            invented_entry(_narrow()),
            tmp_path,
            _clock,
            _sleep,
            lambda request: AttemptResult("ok", body_for(request)),
            SlotSecrets(PRIMARY, ""),
        )
    finally:
        os.open = real_open
        os.close = real_close
        for fd in lock_fds:
            try:
                real_close(fd)
            except OSError:
                pass
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    assert "closed" not in str(result.failure)
    assert "closed" not in repr(result.failure)
    folder = tmp_path / "un_comtrade"
    assert (folder / "state.lock").is_file()
    assert not (folder / "manifest.json").exists()
    assert not (folder / "state.json").exists()


def _body(descriptor: object, product: str) -> bytes:
    import json

    payload = {
        "count": 1,
        "truncated": False,
        "error": None,
        "data": [_record(descriptor, product)],
    }
    return json.dumps(payload).encode("utf-8")
