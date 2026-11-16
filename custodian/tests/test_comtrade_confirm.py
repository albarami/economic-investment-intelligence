"""Confirmation fixes for the Comtrade adapter. Invented responses only."""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

import pytest
from custodian.tests.fixtures.comtrade.invented import (
    CHAPTER,
    MARKER,
    body_for,
    invented_entry,
    invented_policy,
    trusted_source,
)

from eii_custodian.publicdata.comtrade.assemble import assemble
from eii_custodian.publicdata.comtrade.fetch import fetch_source
from eii_custodian.publicdata.comtrade.parse import ParseError, parse_body
from eii_custodian.publicdata.comtrade.partition import initial_partitions
from eii_custodian.publicdata.comtrade.policy import (
    PolicyError,
    SafeRefusal,
)
from eii_custodian.publicdata.comtrade.state import fresh, write_ledger
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    PreparedRequest,
    SlotSecrets,
    perform,
)

PRIMARY = "primary-marker"
ESCAPED = "\\u0069" + MARKER[1:]


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


def _stored(cache: Path) -> str:
    folder = cache / "un_comtrade"
    if not folder.exists():
        return ""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    )


def _reporter(policy: object):
    cell = next(
        item for item in initial_partitions(policy) if item.series_role == "reporter"
    )
    return cell.descriptor(policy, "keyed")


def _perform_hidden(policy: object, planted: object, check: str) -> None:
    opened: list[int] = []

    def opener(_request: PreparedRequest) -> AttemptResult:
        opened.append(1)
        return AttemptResult("ok", b"")

    with pytest.raises(SafeRefusal) as caught:
        perform(policy, planted, MARKER, opener)
    try:
        perform(policy, planted, MARKER, opener)
    except SafeRefusal:
        rendered = traceback.format_exc()
    else:
        raise AssertionError("refusal")
    encoded = quote(MARKER, safe="")
    visible = "\n".join((str(caught.value), repr(caught.value), rendered))
    assert caught.value.check == check
    assert MARKER not in visible
    assert encoded not in visible
    assert opened == []


def test_direction_refusal_hides_a_marker_in_the_descriptor() -> None:
    """A direction refusal does not render a credential placed in a selector."""
    policy = invented_policy()
    planted = replace(_reporter(policy), reporter_code=MARKER)
    _perform_hidden(policy, planted, "mirror_direction")


def test_forbidden_family_refusal_hides_a_marker_in_the_descriptor() -> None:
    """A forbidden-family refusal does not render a credential placed in a selector."""
    policy = invented_policy()
    planted = replace(_reporter(policy), endpoint_family="deliver", chapter=MARKER)
    _perform_hidden(policy, planted, "forbidden_endpoint")


def test_host_refusal_hides_a_marker_in_the_descriptor() -> None:
    """A host refusal does not render a credential placed in a selector."""
    policy = invented_policy()
    planted = replace(_reporter(policy), endpoint_family="preview", chapter=MARKER)
    _perform_hidden(policy, planted, "blocked_host")


def _escaped_body(request: PreparedRequest, field: str) -> bytes:
    text = body_for(request).decode("utf-8")
    if field == "flag":
        text = text.replace('"flag": ""', f'"flag": "{ESCAPED}"', 1)
    else:
        text = text.replace("{", '{"note": "' + ESCAPED + '", ', 1)
    raw = text.encode("utf-8")
    assert MARKER.encode("utf-8") not in raw
    return raw


def test_unicode_escaped_marker_in_a_flag_is_refused(tmp_path: Path) -> None:
    """A JSON unicode escape of the marker in a flag is refused before storage."""

    def opener(request: PreparedRequest) -> AttemptResult:
        return AttemptResult("ok", _escaped_body(request, "flag"))

    result = fetch_source(
        invented_entry(_narrow()),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(MARKER, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "provider_error"
    assert MARKER not in str(result.failure)
    assert MARKER not in repr(result.failure)
    assert MARKER not in _stored(tmp_path)


def test_unicode_escaped_marker_in_an_ignored_field_is_refused(tmp_path: Path) -> None:
    """A JSON unicode escape of the marker in an ignored field is refused."""

    def opener(request: PreparedRequest) -> AttemptResult:
        return AttemptResult("ok", _escaped_body(request, "note"))

    result = fetch_source(
        invented_entry(_narrow()),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(MARKER, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "provider_error"
    assert MARKER not in str(result.failure)
    assert MARKER not in repr(result.failure)
    assert MARKER not in _stored(tmp_path)


def test_children_fetched_at_different_times_assemble(tmp_path: Path) -> None:
    """Assembly keeps each child's retrieval time and still succeeds."""
    calls = {"n": 0}

    def clock() -> str:
        calls["n"] += 1
        hour = calls["n"]
        return f"2026-11-16T{hour:02d}:00:00Z"

    policy = _narrow()
    result = fetch_source(
        invented_entry(policy),
        tmp_path,
        clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is None
    folder = tmp_path / "un_comtrade"
    times = {
        json.loads(path.read_text(encoding="utf-8"))["retrieved_utc"]
        for path in folder.glob("*.meta.json")
    }
    assert len(times) > 1
    assembled = assemble(
        tmp_path,
        "un_comtrade",
        policy,
        manifest_sha256=result.digest,
        **trusted_source(),
    )
    assert assembled.rows
    assert set(assembled.child_retrieved_utc) >= times or times <= {
        item[1] for item in assembled.child_retrieved_utc
    }


def test_identical_bodies_keep_distinct_receipts(tmp_path: Path) -> None:
    """Two empty answers share bytes and still keep two receipts."""
    policy = _narrow(count_bounds={"minimum": 0, "maximum": 8})
    fetch_source(
        invented_entry(policy),
        tmp_path,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request, count=0)),
        SlotSecrets(PRIMARY, ""),
    )
    folder = tmp_path / "un_comtrade"
    metas = list(folder.glob("*.meta.json"))
    assert len(metas) == 2
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in metas]
    assert {item["partition_key"] for item in loaded} != {loaded[0]["partition_key"]}
    assert len({item["sha256"] for item in loaded}) == 1


def _complete(tmp_path: Path, name: str):
    policy = _narrow()
    cache = tmp_path / name
    result = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is None
    return policy, cache, result


def _rewrite(folder: Path, field: str, value: object) -> str:
    """Change one receipt field and pin the new receipt hash."""
    ledger_path = folder / "state.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    pairs: list[list[str]] = []
    for key, old_receipt in ledger["child_sha256"]:
        side_path = folder / f"{old_receipt}.meta.json"
        body_path = folder / f"{old_receipt}.json"
        loaded = json.loads(side_path.read_text(encoding="utf-8"))
        loaded[field] = value
        text = json.dumps(loaded, sort_keys=True, ensure_ascii=True) + "\n"
        new_receipt = sha256_hex(text.encode("utf-8"))
        body = body_path.read_bytes()
        (folder / f"{new_receipt}.meta.json").write_text(text, encoding="utf-8")
        (folder / f"{new_receipt}.json").write_bytes(body)
        if new_receipt != old_receipt:
            side_path.unlink()
            body_path.unlink()
        pairs.append([key, new_receipt])
    ledger["child_sha256"] = pairs
    ledger_path.write_text(
        json.dumps(ledger, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        return ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_key = {key: receipt for key, receipt in pairs}
    for child in manifest["children"]:
        receipt = by_key[child["key"]]
        side = json.loads((folder / f"{receipt}.meta.json").read_text(encoding="utf-8"))
        child["sha256"] = side["sha256"]
        child["receipt_sha256"] = receipt
    text = json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    manifest_path.write_text(text, encoding="utf-8")
    return sha256_hex(text.encode("utf-8"))


def test_resume_refuses_a_tampered_count(tmp_path: Path) -> None:
    """A receipt count that the body does not hold does not change completion."""
    policy, cache, _result = _complete(tmp_path, "count")
    _rewrite(cache / "un_comtrade", "count", 100)
    again = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is not None
    assert again.failure.check == "receipt_count"


def test_resume_refuses_a_tampered_publisher(tmp_path: Path) -> None:
    """Resume checks the publisher against the registry row."""
    policy, cache, _result = _complete(tmp_path, "publisher")
    _rewrite(cache / "un_comtrade", "publisher", "Other publisher")
    again = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is not None
    assert again.failure.check == "lineage_missing"


def test_resume_refuses_a_tampered_licence(tmp_path: Path) -> None:
    """Resume checks the licence basis against the registry row."""
    policy, cache, _result = _complete(tmp_path, "licence")
    _rewrite(cache / "un_comtrade", "licence_basis", "other_basis")
    again = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is not None
    assert again.failure.check == "lineage_missing"


def test_resume_refuses_a_tampered_terms_hash(tmp_path: Path) -> None:
    """Resume checks the terms hash against the registry terms."""
    policy, cache, _result = _complete(tmp_path, "terms")
    _rewrite(cache / "un_comtrade", "terms_sha256", "cd" * 32)
    again = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is not None
    assert again.failure.check == "lineage_missing"


def test_resume_refuses_a_tampered_host(tmp_path: Path) -> None:
    """Resume checks the host against the policy template."""
    policy, cache, _result = _complete(tmp_path, "host")
    _rewrite(cache / "un_comtrade", "fetch_host", "other.example")
    again = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is not None
    assert again.failure.check == "lineage_missing"


def test_resume_refuses_a_tampered_receipt_hash(tmp_path: Path) -> None:
    """Resume refuses a receipt whose bytes no longer match the pinned hash."""
    policy, cache, _result = _complete(tmp_path, "hash")
    folder = cache / "un_comtrade"
    path = next(folder.glob("*.meta.json"))
    path.write_text(path.read_text(encoding="utf-8").replace("{", '{"planted": 1, ', 1))
    again = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is not None
    assert again.failure.check == "receipt_hash"


def _assemble_tamper(tmp_path: Path, field: str, value: object) -> None:
    policy, cache, _result = _complete(tmp_path, field)
    digest = _rewrite(cache / "un_comtrade", field, value)
    with pytest.raises(SafeRefusal) as caught:
        assemble(
            cache,
            "un_comtrade",
            policy,
            manifest_sha256=digest,
            **trusted_source(),
        )
    assert caught.value.check == "lineage_missing"


def test_assembly_refuses_a_tampered_publisher(tmp_path: Path) -> None:
    """Assembly checks the publisher against the registry row."""
    _assemble_tamper(tmp_path, "publisher", "Other publisher")


def test_assembly_refuses_a_tampered_licence(tmp_path: Path) -> None:
    """Assembly checks the licence basis against the registry row."""
    _assemble_tamper(tmp_path, "licence_basis", "other_basis")


def test_assembly_refuses_a_tampered_terms_hash(tmp_path: Path) -> None:
    """Assembly checks the terms hash against the registry terms."""
    _assemble_tamper(tmp_path, "terms_sha256", "cd" * 32)


def test_assembly_refuses_a_tampered_host(tmp_path: Path) -> None:
    """Assembly checks the host against the policy template."""
    _assemble_tamper(tmp_path, "fetch_host", "other.example")


def test_assembly_refuses_a_tampered_count(tmp_path: Path) -> None:
    """Assembly recomputes the count from the body."""
    policy, cache, _result = _complete(tmp_path, "assemble-count")
    digest = _rewrite(cache / "un_comtrade", "count", 100)
    with pytest.raises(SafeRefusal) as caught:
        assemble(
            cache,
            "un_comtrade",
            policy,
            manifest_sha256=digest,
            **trusted_source(),
        )
    assert caught.value.check == "receipt_count"


def test_assembly_refuses_a_tampered_receipt_hash(tmp_path: Path) -> None:
    """Assembly refuses a receipt whose bytes no longer match the pinned hash."""
    policy, cache, result = _complete(tmp_path, "assemble-hash")
    path = next((cache / "un_comtrade").glob("*.meta.json"))
    path.write_text(path.read_text(encoding="utf-8").replace("{", '{"planted": 1, ', 1))
    with pytest.raises(SafeRefusal) as caught:
        assemble(
            cache,
            "un_comtrade",
            policy,
            manifest_sha256=result.digest,
            **trusted_source(),
        )
    assert caught.value.check == "receipt_hash"


def test_empty_last_period_is_not_observed(tmp_path: Path) -> None:
    """An empty answer for the required last period is not an observed period."""
    policy = _narrow(
        periods=["2098", "2099"],
        expected_last_periods=["2099"],
        count_bounds={"minimum": 1, "maximum": 64},
    )

    def opener(request: PreparedRequest) -> AttemptResult:
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 0 if query.get("period") == "2099" else 1
        return AttemptResult("ok", body_for(request, count=count))

    result = fetch_source(
        invented_entry(policy),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "missing_period"
    assert not (tmp_path / "un_comtrade" / "manifest.json").exists()


def test_unreviewed_subdivision_field_is_refused_at_activation() -> None:
    """A subdivision field without a reviewed mapping is refused before a fetch."""
    with pytest.raises(PolicyError) as caught:
        invented_policy(
            subdivision_fields=["band"],
            subdivision_values={"band": ["b1", "b2"]},
        )
    assert caught.value.detail == "subdivision_fields"


def test_nonempty_wrong_subdivision_is_refused() -> None:
    """A non-product subdivision value is refused even when the row matches the chapter."""
    policy = invented_policy()
    descriptor = replace(_reporter(policy), subdivision=(("band", "b1"),))
    record = {
        "reporterCode": descriptor.reporter_code,
        "partnerCode": descriptor.partner_code,
        "partner2Code": None,
        "period": descriptor.period,
        "flowCode": descriptor.flow_code,
        "cmdCode": CHAPTER,
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
    with pytest.raises(ParseError) as caught:
        parse_body(
            json.dumps(
                {"count": 1, "truncated": False, "error": None, "data": [record]}
            ).encode("utf-8"),
            policy,
            descriptor,
            source_version=policy.version,
            receipt_sha256="",
        )
    assert caught.value.check == "product_membership"


def test_product_child_of_the_wrong_chapter_is_refused() -> None:
    """A product in the reviewed list is refused when it is not a child of the chapter."""
    policy = invented_policy()
    descriptor = replace(
        _reporter(policy),
        chapter="ch-b",
        subdivision=(("product", "ch-a-1"),),
    )
    record = {
        "reporterCode": descriptor.reporter_code,
        "partnerCode": descriptor.partner_code,
        "partner2Code": None,
        "period": descriptor.period,
        "flowCode": descriptor.flow_code,
        "cmdCode": "ch-a-1",
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
    with pytest.raises(ParseError) as caught:
        parse_body(
            json.dumps(
                {"count": 1, "truncated": False, "error": None, "data": [record]}
            ).encode("utf-8"),
            policy,
            descriptor,
            source_version=policy.version,
            receipt_sha256="",
        )
    assert caught.value.check == "product_membership"


def test_duplicate_row_across_two_leaves_is_refused(tmp_path: Path) -> None:
    """Two chapters that both accept one product code do not both enter the table."""
    policy = _narrow(
        chapters=["ch", "ch-a"],
        subdivision_values={"product": ["ch-a-1"]},
        chapter_products={"ch": ["ch-a-1"], "ch-a": ["ch-a-1"]},
        keyed_record_limit=2,
        daily_calls=20,
    )

    def opener(request: PreparedRequest) -> AttemptResult:
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    result = fetch_source(
        invented_entry(policy),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "duplicate_key"
    assert not (tmp_path / "un_comtrade" / "manifest.json").exists()


def test_lock_acquire_failure_is_a_safe_refusal(tmp_path: Path) -> None:
    """A filesystem failure while creating the lock is a fixed refusal."""
    real_open = os.open

    def boom(path: str | os.PathLike[str], flags: int, *args: object) -> int:
        if str(path).endswith("state.lock"):
            raise OSError("disk")
        return real_open(path, flags, *args)

    os.open = boom
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
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    assert "disk" not in str(result.failure)


def test_ledger_write_failure_removes_the_partial(tmp_path: Path) -> None:
    """A failed ledger write removes the partial and refuses the run."""
    real_write = Path.write_text

    def boom(self: Path, text: str, *args: object, **kwargs: object) -> int:
        if self.name == ".state.json.partial":
            real_write(self, text, *args, **kwargs)
            raise OSError("full")
        return real_write(self, text, *args, **kwargs)

    Path.write_text = boom
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
        Path.write_text = real_write
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    folder = tmp_path / "un_comtrade"
    assert not (folder / ".state.json.partial").exists()
    assert not (folder / "manifest.json").exists()
    assert "full" not in str(result.failure)


def test_ledger_replace_failure_removes_the_partial(tmp_path: Path) -> None:
    """A failed ledger replace removes the partial and refuses the run."""
    real = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("state.json"):
            raise OSError("interrupted")
        real(src, dst)

    os.replace = boom
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
        os.replace = real
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    folder = tmp_path / "un_comtrade"
    assert not (folder / ".state.json.partial").exists()
    assert not (folder / "manifest.json").exists()


def test_lock_release_failure_keeps_ownership(tmp_path: Path) -> None:
    """A failed lock release is a fixed refusal and the lock file remains."""
    real_unlink = Path.unlink

    def boom(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == "state.lock":
            raise OSError("busy")
        real_unlink(self, *args, **kwargs)

    Path.unlink = boom
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
        Path.unlink = real_unlink
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    assert (tmp_path / "un_comtrade" / "state.lock").exists()
    assert "busy" not in str(result.failure)


def test_direct_ledger_replace_failure_removes_the_partial(tmp_path: Path) -> None:
    """write_ledger itself removes a partial left by a failed replace."""
    ledger = fresh("a" * 64, "b" * 64, ("cell",), "2026-11-16")
    directory = tmp_path / "ledger"
    real = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("state.json"):
            raise OSError("interrupted")
        real(src, dst)

    os.replace = boom
    try:
        with pytest.raises(OSError, match="interrupted"):
            write_ledger(directory, ledger)
    finally:
        os.replace = real
    assert not (directory / ".state.json.partial").exists()
