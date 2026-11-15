"""Kills of registry-loader survivors, on invented rows only."""

from __future__ import annotations

import locale
from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.fetch.registry import (
    RegistryError,
    load_registry,
    read_yaml,
)

ROOT_NOT_A_MAP = "registry root is not a map"
UNKNOWN_ROOT = "unknown field planted_a,planted_b"
SOURCES_EMPTY = "sources is empty"
DUPLICATE_KEY = "duplicate key"
MALFORMED = "malformed yaml"
ENTRY_NOT_A_MAP = "entry is not a map"
UNKNOWN_ROW = "unknown field planted_a,planted_b"
MISSING_FIELDS = "missing field extension,slug"
TRAFFIC_ROW = "traffic provider has no registry row"
UNKNOWN_KIND = "unknown kind"
UNKNOWN_BASIS = "unknown licence_basis"
OWNER_RECORD = "owner_decision needs a decision record"
BARE_RECORD = "decision_record set without owner_decision"
WATCH_NOTE = "terms_watch set without basis_note"
WATCH_URL = "terms_watch set without terms_url"
WATCH_BOOL = "terms_watch is not a boolean"
NOTE_TEXT = "basis_note is not text"
LAYER_OTHER = "layer on a row that is not paged_layer"
LAYER_REQUIRED = "paged_layer requires layer"
LAYER_INTEGER = "layer is not an integer"
LAYER_NEGATIVE = "layer is negative"
OPTIONAL_TEXT = "licence_url is not text"
FLAG_BOOL = "nightly_live_fetch is not a boolean"
COUNT_INTEGER = "row_count_min is not an integer"
SPLITS_TEXT = "public_splits is not a list of text"
COLUMNS_LIST = "columns is not a list"
COLUMN_MAP = "column is not a map"
COLUMN_FIELD = "unknown column field"
COLUMN_TEXT = "column name or type is not text"
COLUMN_TYPE = "unknown column type"

FETCH_HOST = "invented.invalid"
LANDING_URL = "https://invented.invalid/land"
PERIOD_FIRST = "2019"
PERIOD_LAST = "2020"
PERIOD_FIELD = "invented_period"
BASIS_NOTE = "Invented basis note for a planted row"


def full_refusal(exc: RegistryError, text: str) -> None:
    """The whole refusal equals one hand-written literal."""
    assert exc.detail == text
    assert exc.args == (text,)
    assert str(exc) == text


def invented_row(**overrides: object) -> dict[str, object]:
    """One invented registry row. Optional fields stay absent until set."""
    row: dict[str, object] = {
        "key": "planted-key",
        "source_id": "planted_source",
        "slug": "planted-slug",
        "kind": "https_file",
        "title_en": "Invented planted file",
        "publisher": "Invented publisher",
        "licence_id": "invented-terms",
        "licence_basis": "dataset",
        "decision_record": "",
        "fetch_host": FETCH_HOST,
        "url": "https://invented.invalid/file",
        "terms_url": "https://invented.invalid/terms",
        "terms_words": "Invented words of use for a planted row",
        "terms_read_on": "2026-01-15",
        "landing_url": LANDING_URL,
        "nightly_live_fetch": False,
        "public_splits": ["alpha", "beta"],
        "commit_allowed": False,
        "release_tables": ["invented_table"],
        "caveat_keys": ["invented_caveat"],
        "columns": [{"name": "invented_count", "type": "integer"}],
        "reconciliation": "none",
        "skip_reason": "schema_unconfirmed",
        "extension": "json",
        "row_count_min": 2,
        "row_count_max": 9,
        "period_first": PERIOD_FIRST,
        "period_last": PERIOD_LAST,
        "period_field": PERIOD_FIELD,
    }
    row.update(overrides)
    return row


def dump(folder: Path, name: str, document: object) -> Path:
    """Write one invented YAML document."""
    path = folder / name
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def sources(folder: Path, name: str, rows: object, **extra: object) -> Path:
    """Write a registry whose sources value is the planted rows."""
    document: dict[str, object] = {"sources": rows}
    document.update(extra)
    return dump(folder, name, document)


def expect(path: Path, text: str) -> None:
    """Load one file and require the whole refusal."""
    with pytest.raises(RegistryError) as caught:
        load_registry(path)
    full_refusal(caught.value, text)


def test_root_is_not_a_map(tmp_path: Path) -> None:
    """A list root is refused with the whole message, stored on the error."""
    expect(dump(tmp_path, "list.yaml", ["planted"]), ROOT_NOT_A_MAP)


def test_unknown_root_fields_are_listed(tmp_path: Path) -> None:
    """Two unknown root fields are named, comma-separated, in sorted order."""
    path = sources(
        tmp_path,
        "extra.yaml",
        [invented_row()],
        planted_b=1,
        planted_a=1,
    )
    expect(path, UNKNOWN_ROOT)


def test_sources_must_be_a_non_empty_list(tmp_path: Path) -> None:
    """An empty list and a non-list are both refused as empty sources."""
    expect(sources(tmp_path, "empty.yaml", []), SOURCES_EMPTY)
    expect(sources(tmp_path, "mapping.yaml", {"planted": 1}), SOURCES_EMPTY)
    expect(sources(tmp_path, "text.yaml", "planted"), SOURCES_EMPTY)


def test_duplicate_key_names_the_whole_refusal(tmp_path: Path) -> None:
    """Two invented rows that share a key are refused with the whole message."""
    first = invented_row()
    second = invented_row(source_id="planted_other", slug="planted-other")
    expect(sources(tmp_path, "duplicate.yaml", [first, second]), DUPLICATE_KEY)


def test_malformed_yaml_names_the_whole_refusal(tmp_path: Path) -> None:
    """A broken YAML document raises the package error and the whole message."""
    path = tmp_path / "broken.yaml"
    path.write_text(":\n", encoding="utf-8")
    expect(path, MALFORMED)


def test_read_yaml_decodes_utf8_under_an_ascii_locale(tmp_path: Path) -> None:
    """UTF-8 bytes load while the process locale is ASCII."""
    path = tmp_path / "encoded.yaml"
    path.write_bytes('word: "invented-\u00e9"\n'.encode())
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        loaded = read_yaml(path)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert loaded == {"word": "invented-\u00e9"}


def test_entry_must_be_a_map(tmp_path: Path) -> None:
    """A source item that is not a map is refused with the whole message."""
    expect(sources(tmp_path, "item.yaml", [1]), ENTRY_NOT_A_MAP)


def test_unknown_row_fields_are_listed(tmp_path: Path) -> None:
    """Two unknown row fields are named, comma-separated, in sorted order."""
    row = invented_row(planted_b=1, planted_a=1)
    expect(sources(tmp_path, "row.yaml", [row]), UNKNOWN_ROW)


def test_missing_fields_are_listed(tmp_path: Path) -> None:
    """Two missing fields are named, comma-separated, in sorted order."""
    row = invented_row()
    del row["slug"]
    del row["extension"]
    expect(sources(tmp_path, "missing.yaml", [row]), MISSING_FIELDS)


def test_traffic_provider_has_no_registry_row(tmp_path: Path) -> None:
    """A banned traffic source id is refused with the whole message."""
    row = invented_row(source_id="traffic_tomtom_flow")
    expect(sources(tmp_path, "traffic.yaml", [row]), TRAFFIC_ROW)


def test_unknown_kind_is_refused(tmp_path: Path) -> None:
    """An invented kind is refused with the whole message."""
    expect(
        sources(tmp_path, "kind.yaml", [invented_row(kind="invented_kind")]),
        UNKNOWN_KIND,
    )


def test_unknown_licence_basis_is_refused(tmp_path: Path) -> None:
    """An invented licence basis is refused with the whole message."""
    row = invented_row(licence_basis="invented_basis")
    expect(sources(tmp_path, "basis.yaml", [row]), UNKNOWN_BASIS)


def test_owner_decision_needs_record_0026(tmp_path: Path) -> None:
    """owner_decision with any other record is refused with the whole message."""
    row = invented_row(licence_basis="owner_decision", decision_record="0017")
    expect(sources(tmp_path, "record.yaml", [row]), OWNER_RECORD)


def test_decision_record_requires_owner_decision(tmp_path: Path) -> None:
    """A record on another basis is refused with the whole message."""
    row = invented_row(decision_record="0026")
    expect(sources(tmp_path, "bare.yaml", [row]), BARE_RECORD)


def test_terms_watch_requires_basis_note(tmp_path: Path) -> None:
    """terms_watch with no basis note is refused with the whole message."""
    row = invented_row(terms_watch=True)
    expect(sources(tmp_path, "watch-note.yaml", [row]), WATCH_NOTE)


def test_terms_watch_requires_terms_url(tmp_path: Path) -> None:
    """terms_watch with a blank terms url is refused with the whole message."""
    row = invented_row(
        terms_watch=True,
        basis_note=BASIS_NOTE,
        terms_url="   ",
    )
    expect(sources(tmp_path, "watch-url.yaml", [row]), WATCH_URL)


def test_terms_watch_must_be_boolean(tmp_path: Path) -> None:
    """A non-boolean terms_watch is refused with the whole message."""
    row = invented_row(terms_watch="yes")
    expect(sources(tmp_path, "watch-bool.yaml", [row]), WATCH_BOOL)


def test_basis_note_must_be_nonblank_text(tmp_path: Path) -> None:
    """A blank note and a non-text note are refused with the whole message."""
    blank = invented_row(basis_note="   ")
    expect(sources(tmp_path, "blank.yaml", [blank]), NOTE_TEXT)
    number = invented_row(basis_note=4)
    expect(sources(tmp_path, "number.yaml", [number]), NOTE_TEXT)


def test_layer_refusals_name_the_whole_text(tmp_path: Path) -> None:
    """Each layer refusal is the whole message for that case."""
    other = invented_row(layer=0)
    expect(sources(tmp_path, "other.yaml", [other]), LAYER_OTHER)
    missing = invented_row(kind="paged_layer")
    expect(sources(tmp_path, "missing.yaml", [missing]), LAYER_REQUIRED)
    absent = invented_row(kind="paged_layer", layer=None)
    expect(sources(tmp_path, "absent.yaml", [absent]), LAYER_REQUIRED)
    flag = invented_row(kind="paged_layer", layer=True)
    expect(sources(tmp_path, "flag.yaml", [flag]), LAYER_INTEGER)
    negative = invented_row(kind="paged_layer", layer=-1)
    expect(sources(tmp_path, "negative.yaml", [negative]), LAYER_NEGATIVE)


def test_stored_fields_keep_the_invented_literals(tmp_path: Path) -> None:
    """Stored fields are the invented literals, and absent optionals are empty."""
    loaded = load_registry(sources(tmp_path, "kept.yaml", [invented_row()]))
    assert len(loaded) == 1
    entry = loaded[0]
    assert entry.fetch_host == FETCH_HOST
    assert entry.landing_url == LANDING_URL
    assert entry.period_first == PERIOD_FIRST
    assert entry.period_last == PERIOD_LAST
    assert entry.period_field == PERIOD_FIELD
    assert entry.licence_url == ""
    assert entry.basis_note == ""
    assert entry.terms_watch is False
    assert entry.layer is None
    assert entry.public_splits == ("alpha", "beta")
    assert entry.columns == (("invented_count", "integer"),)
    assert entry.row_count_min == 2
    assert entry.row_count_max == 9
    cleared = invented_row()
    cleared["licence_url"] = None
    cleared["basis_note"] = None
    again = load_registry(sources(tmp_path, "cleared.yaml", [cleared]))
    assert again[0].licence_url == ""
    assert again[0].basis_note == ""


def test_optional_text_must_be_text(tmp_path: Path) -> None:
    """A non-text optional string is refused with the whole message."""
    row = invented_row(licence_url=4)
    expect(sources(tmp_path, "licence.yaml", [row]), OPTIONAL_TEXT)


def test_flag_must_be_boolean(tmp_path: Path) -> None:
    """A non-boolean nightly flag is refused with the whole message."""
    row = invented_row(nightly_live_fetch="yes")
    expect(sources(tmp_path, "flag.yaml", [row]), FLAG_BOOL)


def test_optional_int_rejects_bool_and_text(tmp_path: Path) -> None:
    """A boolean and a text count are refused with the whole message."""
    flag = invented_row(row_count_min=True)
    expect(sources(tmp_path, "flag.yaml", [flag]), COUNT_INTEGER)
    text = invented_row(row_count_min="2")
    expect(sources(tmp_path, "text.yaml", [text]), COUNT_INTEGER)


def test_string_list_rejects_a_non_list_and_a_mixed_list(tmp_path: Path) -> None:
    """A string and a mixed list are refused with the whole message."""
    text = invented_row(public_splits="alpha")
    expect(sources(tmp_path, "text.yaml", [text]), SPLITS_TEXT)
    mixed = invented_row(public_splits=["alpha", 2])
    expect(sources(tmp_path, "mixed.yaml", [mixed]), SPLITS_TEXT)


def test_columns_refusals(tmp_path: Path) -> None:
    """Each column refusal is the whole message for that case."""
    expect(
        sources(tmp_path, "list.yaml", [invented_row(columns="invented")]),
        COLUMNS_LIST,
    )
    expect(
        sources(tmp_path, "map.yaml", [invented_row(columns=["invented"])]),
        COLUMN_MAP,
    )
    extra = invented_row(
        columns=[{"name": "invented_count", "type": "integer", "planted": 1}]
    )
    expect(sources(tmp_path, "extra.yaml", [extra]), COLUMN_FIELD)
    bad_name = invented_row(columns=[{"name": 2, "type": "string"}])
    expect(sources(tmp_path, "name.yaml", [bad_name]), COLUMN_TEXT)
    bad_type = invented_row(columns=[{"name": "invented_count", "type": 2}])
    expect(sources(tmp_path, "kind.yaml", [bad_type]), COLUMN_TEXT)
    unknown = invented_row(columns=[{"name": "invented_count", "type": "date"}])
    expect(sources(tmp_path, "type.yaml", [unknown]), COLUMN_TYPE)
