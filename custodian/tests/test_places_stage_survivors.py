"""Mutation regressions for places stage helpers. Every fixture is invented."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.display import CAVEAT_KEY, PubPlace
from eii_custodian.publicdata.places.flagship import digest_of
from eii_custodian.publicdata.places.stage import (
    _check_text,
    _json,
    _manifest_sha,
    _point_index,
    _points,
    commit_files,
    render_place_rows,
    validate_recorded_decision,
)

_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_REAL_PATH_READ_TEXT = Path.read_text
_REAL_PATH_WRITE_TEXT = Path.write_text


def _any(value: object) -> Any:
    return value


def _refusal(call: Callable[[], object], whole: str) -> None:
    """Compare the complete refusal text, not a prefix or a regular expression."""
    with pytest.raises(PlacesError) as caught:
        call()
    assert str(caught.value) == whole
    assert caught.value.reason == whole


def _place(**changes: object) -> PubPlace:
    fields: dict[str, object] = {
        "place_id": "SYN-P-A",
        "name": "SYN Café",
        "name_ar": "مقهى تجريبي",
        "category": "syn_other",
        "category_class": "other",
        "lon": Decimal("0.01"),
        "lat": Decimal("0.02"),
        "cell": 7,
        "source_release": "syn-release",
        "source_provider": "syn-source",
        "licence": "SYN-LICENCE",
        "confidence": Decimal("0.8"),
        "merged_ids": "",
    }
    fields.update(changes)
    return PubPlace(**_any(fields))


def _ascii_default_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make an omitted text encoding behave as an ASCII process default."""

    def read_text(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if encoding is None:
            raise LookupError("planted_ascii_default")
        return _REAL_PATH_READ_TEXT(path, encoding=encoding, errors=errors)

    def write_text(
        path: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if encoding is None:
            raise LookupError("planted_ascii_default")
        return _REAL_PATH_WRITE_TEXT(
            path, data, encoding=encoding, errors=errors, newline=newline
        )

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "write_text", write_text)


def _files() -> dict[str, str]:
    text = '{"caveat_key":"open_listings_incomplete","name":"مكان تجريبي"}\n'
    return {
        "pub_place.jsonl": text,
        "pub_place_verification.jsonl": text,
        "place_points.json": text,
        "build_report.json": text,
        "flagship_check.json": text,
    }


def _write_record(path: Path, **changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "candidates": [],
        "method": "places.flagship.v1",
        "passing_evidence": False,
        "provider_given": False,
        "provisional": True,
    }
    loaded: dict[str, object] = {
        "body": body,
        "digest": digest_of(body),
        "manifest_sha256": "syn-manifest",
        "passed_keys": [],
        "passing_evidence": False,
    }
    loaded.update(changes)
    path.write_text(json.dumps(loaded, ensure_ascii=False), encoding="utf-8")
    return loaded


def _decision() -> dict[str, object]:
    return {
        "candidate_key": "SYN-CAND",
        "digest": "",
        "manifest_sha256": "syn-manifest",
        "provisional": True,
    }


def test_place_rows_have_one_exact_compact_unicode_line() -> None:
    expected = (
        '{"place_id":"SYN-P-A","name":"SYN Café","name_ar":"مقهى تجريبي",'
        '"category":"syn_other","lon":"0.010000","lat":"0.020000","cell":7,'
        '"source_release":"syn-release","source_provider":"syn-source",'
        '"licence":"SYN-LICENCE","confidence":"0.8000","merged_ids":""}\n'
    )
    assert render_place_rows((_place(),)) == expected
    _refusal(
        lambda: render_place_rows((_place(source_provider=""),)), "pub_place_field"
    )


def test_commit_files_missing_output_has_the_whole_refusal(tmp_path: Path) -> None:
    files = _files()
    del files["pub_place.jsonl"]
    _refusal(lambda: commit_files(tmp_path / "out", files), "caveat_missing")
    assert not (tmp_path / "out").exists()


def test_commit_files_is_utf8_under_an_ascii_process_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ascii_default_encoding(monkeypatch)
    files = _files()
    commit_files(tmp_path / "out", files)
    expected = files["pub_place.jsonl"].encode("utf-8")
    assert (tmp_path / "out" / "pub_place.jsonl").read_bytes() == expected


def test_validate_record_normalizes_a_non_mapping_body(tmp_path: Path) -> None:
    path = tmp_path / "check.json"
    _write_record(path, body=[], digest="")
    _refusal(lambda: validate_recorded_decision(_decision(), path), "stale_digest")


def test_validate_record_normalizes_non_list_passed_keys(tmp_path: Path) -> None:
    path = tmp_path / "check.json"
    loaded = _write_record(path, passed_keys="not-a-list")
    decision = _decision()
    decision["digest"] = loaded["digest"]
    _refusal(lambda: validate_recorded_decision(decision, path), "no_provider")


def test_validate_record_reads_utf8_under_an_ascii_process_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ascii_default_encoding(monkeypatch)
    path = tmp_path / "check.json"
    loaded = _write_record(path, syn_note="مكان تجريبي")
    decision = _decision()
    decision["digest"] = loaded["digest"]
    _refusal(lambda: validate_recorded_decision(decision, path), "no_provider")


def test_points_carry_exact_place_and_building_rows() -> None:
    buildings = (("bldg_ovt", "SYN-B-A", "0.030000", "0.040000"),)
    assert _points((_place(),), buildings) == [
        {
            "caveat_key": CAVEAT_KEY,
            "lat": "0.020000",
            "lon": "0.010000",
            "record_key": "SYN-P-A",
            "source_id": "places_ovt",
        },
        {
            "caveat_key": CAVEAT_KEY,
            "lat": "0.040000",
            "lon": "0.030000",
            "record_key": "SYN-B-A",
            "source_id": "bldg_ovt",
        },
    ]


def test_point_index_requires_both_key_parts_to_be_strings() -> None:
    points: list[Mapping[str, object]] = [
        {"source_id": "places_ovt", "record_key": 7, "lon": "0.1", "lat": "0.2"},
        {"source_id": 7, "record_key": "SYN-P-B", "lon": "0.3", "lat": "0.4"},
        {
            "source_id": "places_ovt",
            "record_key": "SYN-P-A",
            "lon": "0.5",
            "lat": "0.6",
        },
    ]
    assert _point_index(points) == {
        ("places_ovt", "SYN-P-A"): {"lon": "0.5", "lat": "0.6"}
    }


def test_empty_flagship_check_is_one_exact_json_document() -> None:
    expected = (
        '{"body": {"candidates": [], "method": "places.flagship.v1", '
        '"passing_evidence": false, "provider_given": false, "provisional": true}, '
        '"caveat_key": "open_listings_incomplete", "digest": "", '
        '"manifest_sha256": "syn-manifest", "passed_keys": [], '
        '"passing_evidence": false}\n'
    )
    assert _check_text(None, "syn-manifest") == expected


def test_manifest_digest_uses_the_exact_path_and_empty_missing_digest(
    tmp_path: Path,
) -> None:
    assert _manifest_sha(tmp_path) == ""
    manifest = tmp_path / "places_s2_t06" / "areas" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"")
    assert _manifest_sha(tmp_path) == _EMPTY_SHA256


def test_json_sorts_keys_and_preserves_unicode() -> None:
    assert _json({"z": "مكان تجريبي", "a": 1}) == '{"a": 1, "z": "مكان تجريبي"}\n'
