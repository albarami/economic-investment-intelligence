"""The load receipt is counted, atomic and free of protected-window fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eii_product.store.receipt import (
    PROTECTED_RECEIPT_FIELDS,
    RECEIPT_NAME,
    ReceiptRefusal,
    read_receipt,
    refuse_public_only_freeze,
    write_receipt,
)

IDENTITY = "ab" * 32


def test_receipt_fields_of_a_public_only_load(tmp_path: Path) -> None:
    write_receipt(
        tmp_path,
        IDENTITY,
        {"pub_place": ("a",)},
        {"pub_place": "cd" * 32},
        {"postgres": 3},
    )
    parsed = read_receipt(tmp_path, IDENTITY)
    assert parsed["state"] == "complete"
    assert parsed["release_id"] == IDENTITY
    assert parsed["engines"] == ["embedded", "postgres"]
    assert parsed["tables"] == ["pub_place"]
    assert parsed["row_counts"] == {"pub_place": 1}
    assert parsed["digests"] == {"pub_place": "cd" * 32}
    assert parsed["durations_ms"] == {"postgres": 3}
    for field in PROTECTED_RECEIPT_FIELDS:
        assert field not in parsed


def test_each_protected_window_field_is_absent(tmp_path: Path) -> None:
    assert PROTECTED_RECEIPT_FIELDS == (
        "parameter_set",
        "protected_sha256",
        "rules_version_id",
        "window_key",
    )
    write_receipt(
        tmp_path,
        IDENTITY,
        {"pub_place": ("a",)},
        {"pub_place": "cd" * 32},
        {"postgres": 1},
    )
    original = (tmp_path / RECEIPT_NAME).read_text(encoding="utf-8")
    for field in PROTECTED_RECEIPT_FIELDS:
        parsed = json.loads(original)
        parsed[field] = "invented"
        (tmp_path / RECEIPT_NAME).write_text(json.dumps(parsed), encoding="utf-8")
        with pytest.raises(ReceiptRefusal) as caught:
            read_receipt(tmp_path, IDENTITY)
        assert caught.value.reason == "receipt_forbidden_field"


def test_missing_pending_and_foreign_receipts_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ReceiptRefusal) as missing:
        read_receipt(tmp_path, IDENTITY)
    assert missing.value.reason == "receipt_missing"
    (tmp_path / RECEIPT_NAME).write_text(
        json.dumps({"release_id": IDENTITY, "state": "pending"}),
        encoding="utf-8",
    )
    with pytest.raises(ReceiptRefusal) as pending:
        read_receipt(tmp_path, IDENTITY)
    assert pending.value.reason == "receipt_not_complete"
    (tmp_path / RECEIPT_NAME).write_text(
        json.dumps({"release_id": "cd" * 32, "state": "complete"}),
        encoding="utf-8",
    )
    with pytest.raises(ReceiptRefusal) as foreign:
        read_receipt(tmp_path, IDENTITY)
    assert foreign.value.reason == "receipt_release_mismatch"


def test_write_is_atomic(tmp_path: Path) -> None:
    def fail() -> None:
        message = "rename refused"
        raise OSError(message)

    with pytest.raises(OSError):
        write_receipt(
            tmp_path,
            IDENTITY,
            {"pub_place": ("a",)},
            {"pub_place": "cd" * 32},
            {"postgres": 1},
            before_rename=fail,
        )
    assert not (tmp_path / RECEIPT_NAME).exists()
    assert list(tmp_path.iterdir()) == []


def test_counts_are_counted_not_supplied(tmp_path: Path) -> None:
    write_receipt(
        tmp_path,
        IDENTITY,
        {"pub_place": ("a", "b", "c")},
        {"pub_place": "cd" * 32},
        {"postgres": 1},
    )
    parsed = read_receipt(tmp_path, IDENTITY)
    assert parsed["row_counts"] == {"pub_place": 3}


def test_public_only_freeze_is_refused() -> None:
    assert (
        refuse_public_only_freeze({"release_kind": "public_only"})
        == "freeze_refused_public_only"
    )
    assert refuse_public_only_freeze({"release_kind": "protected_window"}) is None
