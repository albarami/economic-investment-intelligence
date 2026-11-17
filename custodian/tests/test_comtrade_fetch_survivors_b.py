"""Bounds, counts and exact archive text for the Comtrade fetch survivors."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from custodian.tests.fixtures.comtrade.invented import body_for
from custodian.tests.test_comtrade_fetch_survivors import (
    DAY,
    HEADER,
    KEYED_HOST,
    PUBLIC_HOST,
    PUBLISHER,
    _entry,
    _full,
    _message,
    _ok,
    _policy,
    _run,
    _shape,
    _stopped,
    _url,
)

from eii_custodian.publicdata.comtrade.state import read_ledger, write_ledger
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    PreparedRequest,
    SlotSecrets,
)

MIRROR_KEY = (
    "role=mirror|partner=ZZA|frequency=annual|period=2099|"
    "flow=flow-in|chapter=ch-a|sub="
)
REPORTER_KEY = (
    "role=reporter|partner=ZZA|frequency=annual|period=2099|"
    "flow=flow-in|chapter=ch-a|sub="
)


class _Back:
    """Return one day, then the day before, after the first cell is stored."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= 3:
            return DAY
        return "2026-11-15T08:00:00Z"


def _folder(cache: Path) -> Path:
    return cache / "un_comtrade"


def _complete(tmp_path: Path):
    policy = _policy()
    result = _run(tmp_path, _entry(policy), _ok, SlotSecrets(HEADER, ""))
    assert result.failure is None
    return policy


def test_selection_change_stops_with_the_first_host(tmp_path: Path) -> None:
    """A second selection keeps the refusal on the first template host."""
    policy = _policy()
    cache = tmp_path / "cache"
    assert _run(cache, _entry(policy), _ok, SlotSecrets(HEADER, "")).failure is None
    changed = _policy(periods=["2098"])
    result = _run(cache, _entry(changed), _ok, SlotSecrets(HEADER, ""))
    _shape(result, _stopped("selection_changed"), PUBLIC_HOST, 0, 0, 0)


def test_tampered_child_on_resume_uses_the_keyed_host(tmp_path: Path) -> None:
    """A changed receipt is refused with the keyed host, not the first template."""
    _complete(tmp_path)
    folder = _folder(tmp_path)
    meta = next(path for path in folder.glob("*.meta.json"))
    meta.write_bytes(meta.read_bytes() + b"\n")
    result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message("receipt_hash", f"https://{PUBLIC_HOST}/refused", "receipt_hash"),
        KEYED_HOST,
        2,
        2,
        0,
    )


def test_clock_moving_backward_is_stale_state(tmp_path: Path) -> None:
    """A later call on an earlier day is stale and keeps the keyed host."""
    result = _run(
        tmp_path,
        _entry(_policy()),
        _ok,
        SlotSecrets(HEADER, ""),
        clock=_Back(),
    )
    _shape(
        result,
        _message("stale_state", f"https://{PUBLIC_HOST}/refused", "stale_state"),
        KEYED_HOST,
        2,
        1,
        1,
    )


def test_unknown_pending_key_is_stale_state(tmp_path: Path) -> None:
    """A pending key outside the closed tree is stale."""
    _complete(tmp_path)
    folder = _folder(tmp_path)
    ledger = read_ledger(folder / "state.json")
    write_ledger(folder, replace(ledger, pending=("role=missing|sub=",), completed=()))
    result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message("stale_state", f"https://{PUBLIC_HOST}/refused", "stale_state"),
        KEYED_HOST,
        2,
        0,
        2,
    )


def test_second_accept_of_one_cell_is_duplicate_partition(tmp_path: Path) -> None:
    """A pending key that is already complete is duplicate_partition."""
    _complete(tmp_path)
    folder = _folder(tmp_path)
    ledger = read_ledger(folder / "state.json")
    write_ledger(folder, replace(ledger, pending=(MIRROR_KEY,)))
    result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message(
            "duplicate_partition",
            f"https://{PUBLIC_HOST}/refused",
            "duplicate_partition",
        ),
        KEYED_HOST,
        2,
        2,
        0,
    )


def test_count_above_the_maximum_blocks_the_manifest(tmp_path: Path) -> None:
    """Two stored rows are above a maximum of zero."""
    policy = _policy(count_bounds={"minimum": 0, "maximum": 0})
    result = _run(tmp_path, _entry(policy), _ok, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message("count_bounds", f"https://{PUBLIC_HOST}/refused", "count_bounds"),
        KEYED_HOST,
        2,
        2,
        0,
    )
    assert not (_folder(tmp_path) / "manifest.json").exists()


def test_absent_expected_period_blocks_the_manifest(tmp_path: Path) -> None:
    """A last period that no stored row carries blocks the manifest."""
    policy = _policy(expected_last_periods=["2098"])
    result = _run(tmp_path, _entry(policy), _ok, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message("missing_period", f"https://{PUBLIC_HOST}/refused", "missing_period"),
        KEYED_HOST,
        2,
        2,
        0,
    )


def test_same_product_under_two_chapters_is_a_duplicate_key(tmp_path: Path) -> None:
    """Two chapters that store one product code are one duplicate key."""
    policy = _policy(
        chapters=["ch", "ch-a"],
        subdivision_values={"product": ["ch-a-1"]},
        chapter_products={"ch": ["ch-a-1"], "ch-a": ["ch-a-1"]},
        keyed_record_limit=2,
        daily_calls=20,
    )

    def opener(request: PreparedRequest) -> AttemptResult:
        from urllib.parse import parse_qsl, urlsplit

        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    result = _run(tmp_path, _entry(policy), opener, SlotSecrets(HEADER, ""))
    assert result.failure is not None
    assert result.host == KEYED_HOST
    assert result.failure.check == "duplicate_key"
    _full(
        result.failure,
        _message("duplicate_key", f"https://{PUBLIC_HOST}/refused", "duplicate_key"),
    )


def test_dropped_completed_cell_is_a_coverage_gap(tmp_path: Path) -> None:
    """An empty pending list with one cell unfinished is a coverage gap."""
    _complete(tmp_path)
    folder = _folder(tmp_path)
    ledger = read_ledger(folder / "state.json")
    kept = tuple(pair for pair in ledger.child_sha256 if pair[0] != MIRROR_KEY)
    write_ledger(
        folder,
        replace(
            ledger,
            pending=(),
            completed=tuple(item for item in ledger.completed if item != MIRROR_KEY),
            child_sha256=kept,
        ),
    )
    result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    _shape(
        result,
        _message("coverage_gap", f"https://{PUBLIC_HOST}/refused", "coverage_gap"),
        KEYED_HOST,
        2,
        1,
        1,
    )
    coverage = json.loads((folder / "coverage.json").read_text(encoding="utf-8"))
    assert coverage["requested_cells"] == 2
    assert coverage["present_cells"] == 1
    assert coverage["gap_cells"] == 1
    assert coverage["missing"] == [MIRROR_KEY]
    assert coverage["source_id"] == "un_comtrade"
    assert coverage["price_amount"] == "9.50"
    assert coverage["price_currency"] == "XXX"
    assert coverage["price_retrieved_on"] == "2026-11-16"
    assert coverage["price_source"] == "invented-price-page"
    assert coverage["price_unavailable_reason"] == ""


def test_child_receipt_fields_and_manifest_bytes(tmp_path: Path) -> None:
    """Receipts and the manifest use the closed names, order and compact text."""
    policy = _policy()
    result = _run(tmp_path, _entry(policy), _ok, SlotSecrets(HEADER, ""))
    assert result.failure is None
    assert result.host == KEYED_HOST
    assert result.requested_cells == 2
    assert result.present_cells == 2
    assert result.gap_cells == 0
    folder = _folder(tmp_path)
    manifest = (folder / "manifest.json").read_text(encoding="utf-8")
    assert " " not in manifest
    assert manifest.endswith("\n")
    loaded = json.loads(manifest)
    assert [item["key"] for item in loaded["children"]] == [MIRROR_KEY, REPORTER_KEY]
    assert loaded["complete"] is True
    assert loaded["present_cells"] == 2
    assert loaded["requested_cells"] == 2
    assert loaded["gap_cells"] == 0
    assert loaded["source_id"] == "un_comtrade"
    assert loaded["parser_method"] == "comtrade.parse"
    assert loaded["parser_version"] == "1"
    assert result.digest == sha256_hex(manifest.encode("utf-8"))
    terms = terms_text_sha256(b"terms to be read")
    for path in folder.glob("*.meta.json"):
        raw = path.read_text(encoding="utf-8")
        side = json.loads(raw)
        assert raw.startswith('{"api_class":')
        assert "\\u00e9" in raw
        assert "é" not in raw
        assert side["api_class"] == "keyed"
        assert side["applied_limit"] == 3
        assert side["count"] == 1
        assert side["parent_key"] == ""
        assert side["source_version"] == "invented-1"
        assert side["budget_period"] == "2026-11-16"
        assert side["publisher"] == PUBLISHER
        assert side["fetch_host"] == KEYED_HOST
        assert side["source_modified"] is None
        assert side["terms_sha256"] == terms
        assert side["row_count"] == 1
        assert side["partition_key"] in {MIRROR_KEY, REPORTER_KEY}
        assert side["fetch_url"] == _url(
            "mirror" if side["partition_key"] == MIRROR_KEY else "reporter"
        )
    mirror = json.loads(
        next(
            path.read_text(encoding="utf-8")
            for path in folder.glob("*.meta.json")
            if json.loads(path.read_text(encoding="utf-8"))["partition_key"]
            == MIRROR_KEY
        )
    )
    assert mirror["daily_counts"] == {"primary": 1, "secondary": 0}
    reporter = json.loads(
        next(
            path.read_text(encoding="utf-8")
            for path in folder.glob("*.meta.json")
            if json.loads(path.read_text(encoding="utf-8"))["partition_key"]
            == REPORTER_KEY
        )
    )
    assert reporter["daily_counts"] == {"primary": 2, "secondary": 0}
    manifest_meta = next((folder / "manifests").glob("*.meta.json"))
    side = json.loads(manifest_meta.read_text(encoding="utf-8"))
    assert side["fetch_url"] == f"https://{KEYED_HOST}/data/v1/get"
    assert side["fetch_host"] == KEYED_HOST
    assert side["publisher"] == PUBLISHER
    assert side["source_modified"] == "invented-1"
    assert side["terms_sha256"] is None
    assert side["row_count"] is None
    assert side["sha256"] == result.digest
    coverage_meta = next((folder / "coverage").glob("*/*.meta.json"))
    retained = json.loads(coverage_meta.read_text(encoding="utf-8"))
    assert retained["fetch_url"] == f"https://{KEYED_HOST}/data/v1/get"
    assert retained["source_modified"] == "invented-1"


def test_store_readback_failure_is_write_failed(tmp_path: Path) -> None:
    """A receipt whose bytes do not match its name is write_failed."""
    real = Path.read_bytes

    def boom(self: Path) -> bytes:
        if self.parent.name == "un_comtrade" and self.name.endswith(".meta.json"):
            return b"not-the-receipt"
        return real(self)

    Path.read_bytes = boom
    try:
        result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    finally:
        Path.read_bytes = real
    _shape(
        result,
        _message("write_failed", f"https://{PUBLIC_HOST}/refused", "write_failed"),
        KEYED_HOST,
        2,
        0,
        2,
    )


def test_manifest_replace_failure_is_write_failed_on_the_keyed_host(
    tmp_path: Path,
) -> None:
    """A failed manifest replace removes the partial and names write_failed."""
    real = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("manifest.json"):
            raise OSError("interrupted")
        real(src, dst)

    os.replace = boom
    try:
        result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    finally:
        os.replace = real
    _shape(
        result,
        _message("write_failed", f"https://{PUBLIC_HOST}/refused", "write_failed"),
        KEYED_HOST,
        2,
        2,
        0,
    )
    folder = _folder(tmp_path)
    assert not (folder / "manifest.json").exists()
    assert not (folder / ".manifest.json.partial").exists()


def test_ledger_replace_failure_uses_the_first_host(tmp_path: Path) -> None:
    """A failed ledger replace stops before a run and uses the first host."""
    real = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("state.json"):
            raise OSError("interrupted")
        real(src, dst)

    os.replace = boom
    try:
        result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    finally:
        os.replace = real
    _shape(result, _stopped("write_failed"), PUBLIC_HOST, 0, 0, 0)


def test_lock_release_failure_uses_the_first_host(tmp_path: Path) -> None:
    """A failed lock release is write_failed and keeps the first host."""
    real = Path.unlink

    def boom(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == "state.lock":
            raise OSError("busy")
        real(self, *args, **kwargs)

    Path.unlink = boom
    try:
        result = _run(tmp_path, _entry(_policy()), _ok, SlotSecrets(HEADER, ""))
    finally:
        Path.unlink = real
    _shape(result, _stopped("write_failed"), PUBLIC_HOST, 0, 0, 0)
    assert (_folder(tmp_path) / "state.lock").is_file()


def test_tamper_between_cells_is_the_final_verification(tmp_path: Path) -> None:
    """A receipt changed after the first cell fails the final verification."""
    calls = {"n": 0}

    def opener(request: PreparedRequest) -> AttemptResult:
        calls["n"] += 1
        if calls["n"] == 2:
            folder = _folder(tmp_path)
            meta = next(path for path in folder.glob("*.meta.json"))
            meta.write_bytes(meta.read_bytes() + b"\n")
        return _ok(request)

    result = _run(tmp_path, _entry(_policy()), opener, SlotSecrets(HEADER, ""))
    assert result.failure is not None
    assert result.failure.check == "receipt_hash"
    assert result.host == KEYED_HOST
