"""The financial-centre register is read only through its setting."""

import asyncio
import hashlib
import json
import logging
import traceback
from pathlib import Path

import pytest

from eii_product.api.app import create_app
from eii_product.config import ConfigError
from eii_product.register_file import RegisterRefusal, read_fc_register_rows

FIXTURE = Path(__file__).parent / "fixtures" / "fc_register" / "stand_in_register.json"


def listed(setting: object) -> str:
    """The hash a release would list for the file's present bytes (L-1509).

    An unreadable or invalid setting gets an invented hash, so the read is
    attempted and the reader's own refusal is the one asserted.
    """
    try:
        return hashlib.sha256(Path(str(setting)).read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


@pytest.fixture(autouse=True)
def configured_register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct-reader callers configure only their invented temporary stand-in."""
    monkeypatch.setenv("EII_FC_REGISTER_FILE", str(tmp_path / "stand_in_register.json"))


def _copy(tmp_path: Path) -> Path:
    dest = tmp_path / "stand_in_register.json"
    dest.write_bytes(FIXTURE.read_bytes())
    return dest


def test_an_unset_reader_returns_nothing_and_opens_no_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EII_FC_REGISTER_FILE", raising=False)
    assert read_fc_register_rows(None, listed_sha256=None) is None


def test_the_read_opens_only_the_path_the_setting_names(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    bundle = read_fc_register_rows(str(copy), listed_sha256=listed(str(copy)))
    assert bundle is not None
    assert bundle.rows[0].tower_or_building == "Invented Tower Aleph"
    assert bundle.rows[0].position == ("51.5", "25.3")
    assert bundle.rows[0].row_id == "row-aleph-one"


def test_a_planted_read_of_another_path_is_refused(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    other = tmp_path / "other.json"
    other.write_text("[]", encoding="utf-8")
    with pytest.raises(RegisterRefusal, match="path_refused") as caught:
        read_fc_register_rows(
            str(copy), listed_sha256=listed(str(copy)), asked_path=str(other)
        )
    assert str(other) not in str(caught.value)
    assert other.read_text(encoding="utf-8") == "[]"


def test_an_absent_setting_yields_no_data_and_no_substitute_path(
    tmp_path: Path,
) -> None:
    calls: list[object] = []

    def reader(setting: str | None, *, asked_path: str | None = None) -> None:
        calls.append((setting, asked_path))
        raise AssertionError("opened")

    tiles = tmp_path / "tiles"
    tiles.mkdir()
    app = create_app(tiles, fc_setting_reader=lambda: None, fc_rows_reader=reader)
    status, body = _get(app, "/api/layers/fc_firms_per_tower")
    assert status == 200
    assert body["status"] == "NO_DATA"
    assert body["reason"] == "missing_input"
    assert body["facts"] == []
    assert calls == []


def test_the_stand_in_has_the_shape_the_reader_accepts(tmp_path: Path) -> None:
    copy = str(_copy(tmp_path))
    bundle = read_fc_register_rows(copy, listed_sha256=listed(copy))
    assert bundle is not None
    assert len(bundle.rows) == 10
    assert bundle.year == "2024"
    assert "Invented Tower Gimel" in bundle.gazetteer
    assert "INV-NORTH" in bundle.districts
    free = next(row for row in bundle.rows if row.row_id == "row-zone-free")
    assert free.district_free_zone is True
    assert free.district_key is None
    assert free.tower_or_building is None


def test_nothing_of_the_file_or_its_path_is_printed_or_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tmp_path)
    before = copy.read_bytes()
    read_fc_register_rows(str(copy), listed_sha256=listed(str(copy)))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert copy.read_bytes() == before
    assert str(copy) not in captured.out
    assert str(copy) not in captured.err


def test_a_missing_file_stops_the_start_without_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "invented-missing.json"
    _assert_start_hides_path(tmp_path, monkeypatch, caplog, missing)


def test_a_directory_stops_the_start_without_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    folder = tmp_path / "invented-directory"
    folder.mkdir()
    _assert_start_hides_path(tmp_path, monkeypatch, caplog, folder)


def test_an_unreadable_file_stops_the_start_without_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    target = tmp_path / "invented-unreadable.json"
    target.write_bytes(FIXTURE.read_bytes())
    target.chmod(0)
    try:
        _assert_start_hides_path(tmp_path, monkeypatch, caplog, target)
    finally:
        target.chmod(0o644)


def test_a_later_read_failure_returns_a_fixed_refusal_without_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    copy = _copy(tmp_path)
    monkeypatch.setenv("EII_FC_REGISTER_FILE", str(copy))
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    caplog.set_level(logging.DEBUG)
    app = create_app(tiles, fc_listed_reader=lambda _store: listed(copy))
    copy.chmod(0)
    try:
        status, body = _get(app, "/api/layers/fc_firms_per_tower")
    finally:
        copy.chmod(0o644)
    assert status == 200
    assert body == {"status": "NO_DATA", "reason": "read_refused", "facts": []}
    dumped = json.dumps(body)
    assert copy.name not in dumped
    assert str(copy) not in dumped
    assert copy.name not in caplog.text
    assert str(copy) not in caplog.text


def test_a_broken_document_refuses_without_a_chained_parser_error(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "stand_in_register.json"
    dest.write_text("{", encoding="utf-8")
    with pytest.raises(RegisterRefusal, match="row_shape") as caught:
        read_fc_register_rows(str(dest), listed_sha256=listed(str(dest)))
    assert caught.value.__cause__ is None


def test_an_unmutated_fixture_still_reads(tmp_path: Path) -> None:
    copy = str(_copy(tmp_path))
    bundle = read_fc_register_rows(copy, listed_sha256=listed(copy))
    assert bundle is not None
    assert len(bundle.rows) == 10


def test_two_distinct_towers_cannot_share_a_place_code(tmp_path: Path) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first, second = parsed["gazetteer"][:2]
    assert first["tower_or_building"] != second["tower_or_building"]
    second["place_code"] = first["place_code"]
    dest = tmp_path / "stand_in_register.json"
    dest.write_text(json.dumps(parsed), encoding="utf-8")
    with pytest.raises(RegisterRefusal, match=r"^row_shape$"):
        read_fc_register_rows(str(dest), listed_sha256=listed(str(dest)))


@pytest.mark.parametrize(
    "plant",
    (
        "duplicate_registration_key",
        "duplicate_row_id",
        "lon_without_lat",
        "lat_without_lon",
        "lon_syntax",
        "lat_syntax",
        "card_not_object",
        "card_missing_field",
        "card_extra_field",
        "card_blank",
        "card_untrimmed",
        "card_not_text",
        "release_hash_not_text",
        "release_hash_syntax",
        "source_hash_not_text",
        "source_hash_syntax",
        "year_not_text",
        "year_syntax",
        "date_not_text",
        "date_syntax",
        "date_impossible",
    ),
)
def test_one_broken_register_field_is_refused(tmp_path: Path, plant: str) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _plant_reader(parsed, plant)
    dest = tmp_path / "stand_in_register.json"
    dest.write_text(json.dumps(parsed), encoding="utf-8")
    with pytest.raises(RegisterRefusal, match="row_shape"):
        read_fc_register_rows(str(dest), listed_sha256=listed(str(dest)))


def test_an_invalid_value_stops_the_start_naming_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EII_FC_REGISTER_FILE", "bad\nvalue")
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    with pytest.raises(ConfigError) as caught:
        create_app(tiles)
    assert str(caught.value) == "EII_FC_REGISTER_FILE"
    assert "bad" not in str(caught.value)
    assert "\n" not in str(caught.value)


def _assert_start_hides_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    target: Path,
) -> None:
    monkeypatch.setenv("EII_FC_REGISTER_FILE", str(target))
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ConfigError) as caught:
        create_app(tiles, fc_listed_reader=lambda _store: "0" * 64)
    formatted = "".join(traceback.format_exception(caught.value))
    blob = formatted + repr(caught.value) + str(caught.value) + caplog.text
    assert str(caught.value) == "EII_FC_REGISTER_FILE"
    assert target.name not in blob
    assert str(target) not in blob
    assert caught.value.__cause__ is None


def _plant_reader(parsed: dict[str, object], plant: str) -> None:
    rows = parsed["rows"]
    source = parsed["source"]
    assert isinstance(rows, list)
    assert isinstance(source, dict)
    first = rows[0]
    second = rows[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    card = first["card"]
    assert isinstance(card, dict)
    if plant == "duplicate_registration_key":
        second["registration_key"] = first["registration_key"]
    elif plant == "duplicate_row_id":
        second["row_id"] = first["row_id"]
    elif plant == "lon_without_lat":
        first["position_lat"] = None
    elif plant == "lat_without_lon":
        first["position_lon"] = None
    elif plant == "lon_syntax":
        first["position_lon"] = "north"
    elif plant == "lat_syntax":
        first["position_lat"] = "east"
    elif plant == "card_not_object":
        first["card"] = []
    elif plant == "card_missing_field":
        del card["activity"]
    elif plant == "card_extra_field":
        card["jobs"] = "none"
    elif plant == "card_blank":
        card["trade_name"] = "   "
    elif plant == "card_untrimmed":
        card["trade_name"] = " Invented House Aleph"
    elif plant == "card_not_text":
        card["trade_name"] = ["Invented House Aleph"]
    elif plant == "release_hash_not_text":
        parsed["release_id"] = 1
    elif plant == "release_hash_syntax":
        parsed["release_id"] = "abcd"
    elif plant == "source_hash_not_text":
        source["sha256"] = None
    elif plant == "source_hash_syntax":
        source["sha256"] = "abcd"
    elif plant == "year_not_text":
        parsed["year"] = 2024
    elif plant == "year_syntax":
        parsed["year"] = "24"
    elif plant == "date_not_text":
        source["retrieved_on"] = None
    elif plant == "date_syntax":
        source["retrieved_on"] = "2026/01/15"
    elif plant == "date_impossible":
        source["retrieved_on"] = "2026-02-31"
    else:
        raise AssertionError(plant)


def _get(app: object, path: str) -> tuple[int, dict[str, object]]:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
    }
    asyncio.run(app(scope, receive, send))
    start = next(item for item in sent if item["type"] == "http.response.start")
    raw = b"".join(
        item.get("body", b"") for item in sent if item["type"] == "http.response.body"
    )
    status = start["status"]
    assert isinstance(status, int)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    return status, parsed
