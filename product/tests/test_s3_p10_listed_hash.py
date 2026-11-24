"""S3-P10 round 2 (L-1509): the register file is checked against the release's listed hash.

Every file here is invented. The expected sha256 comes only from the loaded
release (`listed_inputs`, stored as `release_manifest.fc_register_sha256`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from product.tests.test_layers_fc_firms import _features, _get
from product.tests.test_release_check import _document

from eii_core.manifest import listed_inputs_reason
from eii_product.api.app import create_app, listed_fc_register_sha256
from eii_product.register_file import (
    RegisterBundle,
    RegisterRefusal,
    read_fc_register_rows,
)
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.loader import _create_manifest_table
from eii_product.store.registry import PACKAGED
from eii_product.store.release_check import (
    RELEASE_MANIFEST_COLUMNS,
    ReleaseRefusal,
    manifest_rows,
    refuse_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fc_register" / "stand_in_register.json"
IDENTITY = "ef" * 32
ROUTE = "/api/layers/fc_firms_per_tower"
NAME = "EII_FC_REGISTER_FILE"


def _copy(tmp_path: Path) -> Path:
    folder = tmp_path / "INVENTED-secret-place"
    folder.mkdir(exist_ok=True)
    dest = folder / "stand_in_register.json"
    dest.write_bytes(FIXTURE.read_bytes())
    return dest


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(
    monkeypatch: pytest.MonkeyPatch, path: Path, listed: str | None
) -> RegisterBundle | None:
    """Read ``path`` with the setting freshly configured to it."""
    monkeypatch.setenv(NAME, str(path))
    return read_fc_register_rows(str(path), listed_sha256=listed)


def _entry(digest: str) -> dict[str, object]:
    return {"name": "fc_register", "sha256": digest}


# --- register_file: the refusal branches -------------------------------------


def test_an_unlisted_release_refuses_before_the_file_is_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "INVENTED-secret-place" / "absent.json"
    with pytest.raises(RegisterRefusal, match=r"^hash_unlisted$") as caught:
        _read(monkeypatch, missing, None)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_a_valid_file_with_no_listed_hash_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    with pytest.raises(RegisterRefusal, match=r"^hash_unlisted$"):
        _read(monkeypatch, copy, None)


def test_a_mismatched_hash_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    other = hashlib.sha256(b"INVENTED-other-bytes").hexdigest()
    with pytest.raises(RegisterRefusal, match=r"^hash_mismatch$") as caught:
        _read(monkeypatch, copy, other)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_one_changed_byte_refuses_with_the_old_listed_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    listed = _sha(copy)
    copy.write_bytes(copy.read_bytes() + b" ")
    with pytest.raises(RegisterRefusal, match=r"^hash_mismatch$"):
        _read(monkeypatch, copy, listed)


def test_the_hash_is_compared_before_any_row_is_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(RegisterRefusal, match=r"^hash_mismatch$"):
        _read(monkeypatch, broken, "0" * 64)
    with pytest.raises(RegisterRefusal, match=r"^row_shape$"):
        _read(monkeypatch, broken, _sha(broken))


def test_undecodable_bytes_with_a_matching_hash_refuse_as_row_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = tmp_path / "raw.json"
    raw.write_bytes(b"\xff\xfe{")
    with pytest.raises(RegisterRefusal, match=r"^row_shape$") as caught:
        _read(monkeypatch, raw, _sha(raw))
    assert caught.value.__cause__ is None
    assert "xff" not in repr(caught.value)


def test_a_matching_hash_reads_the_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    bundle = _read(monkeypatch, copy, _sha(copy))
    assert bundle is not None
    assert len(bundle.rows) == 10


def test_an_unset_setting_still_opens_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(NAME, raising=False)
    assert read_fc_register_rows(None, listed_sha256=None) is None


def test_the_listed_hash_is_a_required_keyword(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    with pytest.raises(TypeError):
        read_fc_register_rows(str(copy))  # type: ignore[call-arg]


@settings(max_examples=200, deadline=None)
@given(
    body=st.binary(max_size=64),
    listed=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
)
def test_property_only_the_exact_digest_of_the_bytes_passes_the_hash_gate(
    tmp_path_factory: pytest.TempPathFactory, body: bytes, listed: str
) -> None:
    path = tmp_path_factory.mktemp("prop") / "file.json"
    path.write_bytes(body)
    actual = hashlib.sha256(body).hexdigest()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        if listed != actual:
            with pytest.raises(RegisterRefusal, match=r"^hash_mismatch$"):
                read_fc_register_rows(str(path), listed_sha256=listed)
        try:
            read_fc_register_rows(str(path), listed_sha256=actual)
        except RegisterRefusal as refusal:
            assert refusal.reason == "row_shape"


# --- the release document field ----------------------------------------------


def test_a_manifest_without_listed_inputs_is_still_accepted() -> None:
    refuse_document(_document())


def test_a_manifest_with_one_listed_entry_is_accepted() -> None:
    document = _document()
    document["listed_inputs"] = [_entry("ab" * 32)]
    refuse_document(document)


@pytest.mark.parametrize(
    ("value", "reason"),
    (
        ("not-a-list", "manifest_type_invalid"),
        ([], "manifest_type_invalid"),
        (["not-an-object"], "manifest_type_invalid"),
        ([{"name": "fc_register"}], "manifest_type_invalid"),
        ([{"sha256": "ab" * 32}], "manifest_type_invalid"),
        ([{"name": "fc_register", "sha256": "AB" * 32}], "manifest_type_invalid"),
        ([{"name": "fc_register", "sha256": "ab" * 31}], "manifest_type_invalid"),
        ([{"name": "fc_register", "sha256": 7}], "manifest_type_invalid"),
        ([{"name": 7, "sha256": "ab" * 32}], "manifest_type_invalid"),
        (
            [{"name": "fc_register", "sha256": "ab" * 32, "path": "x"}],
            "unknown_manifest_key",
        ),
        ([{"Name": "fc_register", "sha256": "ab" * 32}], "manifest_key_case"),
        ([{"name": "biz_register", "sha256": "ab" * 32}], "unknown_manifest_key"),
        ([_entry("ab" * 32), _entry("cd" * 32)], "duplicate_key"),
    ),
)
def test_one_bad_listed_entry_is_refused_with_its_reason(
    value: object, reason: str
) -> None:
    assert listed_inputs_reason(value) == reason
    document = _document()
    document["listed_inputs"] = value
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == reason


def test_a_wrong_case_top_level_field_is_refused() -> None:
    document = _document()
    document["Listed_Inputs"] = [_entry("ab" * 32)]
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == "manifest_key_case"


def test_manifest_rows_carry_the_listed_hash_or_null() -> None:
    document = _document()
    assert manifest_rows(document)[0]["fc_register_sha256"] is None
    document["listed_inputs"] = [_entry("ab" * 32)]
    assert manifest_rows(document)[0]["fc_register_sha256"] == "ab" * 32
    assert [column.name for column in RELEASE_MANIFEST_COLUMNS][-1] == (
        "fc_register_sha256"
    )


# --- the fixed application-schema read function ------------------------------


def _store(tmp_path: Path, document: dict[str, object]) -> EmbeddedStore:
    import duckdb

    path = tmp_path / "release.duckdb"
    connection = duckdb.connect(str(path))
    try:
        _create_manifest_table(connection)
        for row in manifest_rows(document):
            connection.execute(
                "INSERT INTO release_manifest VALUES ("
                + ", ".join("?" for _ in row)
                + ")",
                [row[column.name] for column in RELEASE_MANIFEST_COLUMNS],
            )
    finally:
        connection.close()
    return EmbeddedStore(path, IDENTITY, PACKAGED)


def test_the_read_function_returns_the_listed_hash(tmp_path: Path) -> None:
    document = _document()
    document["listed_inputs"] = [_entry("ab" * 32)]
    assert listed_fc_register_sha256(_store(tmp_path, document)) == "ab" * 32


def test_the_read_function_returns_nothing_for_an_unlisted_release(
    tmp_path: Path,
) -> None:
    assert listed_fc_register_sha256(_store(tmp_path, _document())) is None


def test_no_store_lists_nothing() -> None:
    assert listed_fc_register_sha256(None) is None


def test_two_disagreeing_stored_values_list_nothing(tmp_path: Path) -> None:
    document = _document()
    document["listed_inputs"] = [_entry("ab" * 32)]
    second = dict(document["tables"][0], name="pub_census_zone")  # type: ignore[index]
    document["tables"] = [document["tables"][0], second]  # type: ignore[index]
    store = _store(tmp_path, document)
    import duckdb

    store.close()
    connection = duckdb.connect(str(tmp_path / "release.duckdb"))
    connection.execute(
        "UPDATE release_manifest SET fc_register_sha256 = ? WHERE table_name = ?",
        ["cd" * 32, "pub_census_zone"],
    )
    connection.close()
    reopened = EmbeddedStore(tmp_path / "release.duckdb", IDENTITY, PACKAGED)
    assert listed_fc_register_sha256(reopened) is None


# --- the served app ----------------------------------------------------------


def _app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: Path, listed: str | None
) -> object:
    tiles = tmp_path / "tiles"
    tiles.mkdir(exist_ok=True)
    monkeypatch.setenv(NAME, str(path))
    return create_app(
        tiles,
        fc_setting_reader=lambda: str(path),
        fc_listed_reader=lambda _store: listed,
    )


def test_the_start_refuses_an_unlisted_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    monkeypatch.setenv(NAME, str(copy))
    with pytest.raises(RegisterRefusal, match=r"^hash_unlisted$") as caught:
        create_app(tiles, fc_setting_reader=lambda: str(copy))
    assert "INVENTED-secret-place" not in repr(caught.value)


def test_the_start_refuses_a_mismatched_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    with pytest.raises(RegisterRefusal, match=r"^hash_mismatch$") as caught:
        _app(tmp_path, monkeypatch, copy, "0" * 64)
    assert "INVENTED-secret-place" not in repr(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_a_file_changed_after_the_start_refuses_at_the_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    app = _app(tmp_path, monkeypatch, copy, _sha(copy))
    copy.write_bytes(copy.read_bytes() + b"\n")
    with pytest.raises(RegisterRefusal, match=r"^hash_mismatch$"):
        _get(app, ROUTE)


def test_a_matching_hash_serves_only_the_public_card_and_the_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = _copy(tmp_path)
    status, body = _get(_app(tmp_path, monkeypatch, copy, _sha(copy)), ROUTE)
    assert status == 200
    assert body["status"] == "ok"
    features = _features(body)
    assert features
    assert all(feature["metric_key"] == "firms_per_tower" for feature in features)
    payload = body["payload"]
    assert isinstance(payload, dict)
    companies = payload["fc_firms"]["companies"]
    assert companies
    for company in companies:
        assert {field["key"] for field in company["fields"]} <= {
            "trade_name",
            "activity",
        }
    dumped = json.dumps(body)
    assert "INV-FC-" not in dumped
    assert "INVENTED-secret-place" not in dumped
    assert str(copy) not in dumped
    assert _sha(copy) not in dumped


def test_the_path_is_never_printed_by_either_hash_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    copy = _copy(tmp_path)
    messages: list[str] = []
    for listed in (None, "0" * 64):
        with pytest.raises(RegisterRefusal) as caught:
            _read(monkeypatch, copy, listed)
        messages += [str(caught.value), repr(caught.value)]
        messages += [str(caught.value.__cause__), str(caught.value.__context__)]
    captured = capsys.readouterr()
    text = "\n".join([*messages, captured.out, captured.err, caplog.text])
    assert "INVENTED-secret-place" not in text
    assert str(tmp_path) not in text
    assert _sha(copy) not in text
    assert set(messages[::4]) == {"hash_unlisted", "hash_mismatch"}
