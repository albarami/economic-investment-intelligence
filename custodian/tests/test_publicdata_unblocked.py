"""Offline S2-T28 checks; all response bodies are invented."""

from dataclasses import replace
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from custodian.tests.test_publicdata_behaviour import _clock, _entry, _ok, _sleep

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import load_registry


@pytest.mark.parametrize("body", [b"<html>invented frame</html>", b"PK\x03\x04broken"])
def test_workbook_refuses_non_workbook_body(tmp_path: Path, body: bytes) -> None:
    entry = replace(_entry(), extension="xlsx")
    failure = fetch_entry(entry, lambda url: _ok(url, body), tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.source_id == entry.source_id
    assert failure.check == "workbook_content"
    assert not list(tmp_path.rglob("*"))


def test_workbook_accepts_ooxml_container(tmp_path: Path) -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
    entry = replace(_entry(), extension="xlsx")
    body = buffer.getvalue()
    assert (
        fetch_entry(entry, lambda url: _ok(url, body), tmp_path, _clock, _sleep) is None
    )
    assert next(tmp_path.rglob("*.xlsx")).read_bytes() == body


def test_direct_file_rows() -> None:
    entries = {entry.key: entry for entry in load_registry()}
    population = entries["worldpop_qat_2020"]
    workbook = entries["census_2020_workbook"]
    assert population.url.endswith("/qat_pop_2020_CN_100m_R2025A_v1.tif")
    assert "id_/https://" in workbook.url
    assert population.skip_reason == workbook.skip_reason == ""
    assert not population.commit_allowed and not workbook.commit_allowed


@pytest.mark.parametrize(
    ("key", "publisher", "count"),
    [
        ("wage_sector", "National Planning Council", 98),
        ("wage_bands_priv", "Ministry of Labour", 71),
        ("work_hours_act", "National Planning Council", 266),
        ("cpi_group", "National Planning Council", 936),
        ("zone_population", "National Planning Council", 552),
        ("census_hh_type_2020", "National Planning Council", 480),
        ("accident", "Ministry of Interior", 1_000_500),
    ],
)
def test_advisor_metadata(key: str, publisher: str, count: int) -> None:
    entry = next(entry for entry in load_registry() if entry.key == key)
    assert entry.publisher == publisher
    assert entry.row_count_min == entry.row_count_max == count
    assert entry.licence_id == "CC-BY-4.0"
    assert entry.licence_basis == "dataset"
    assert entry.licence_url == "https://creativecommons.org/licenses/by/4.0/"
    assert entry.decision_record == ""
    assert not entry.commit_allowed


def test_household_sex_split_declared() -> None:
    entry = next(
        entry for entry in load_registry() if entry.key == "census_hh_type_2020"
    )
    assert entry.public_splits == ("sex",)


@pytest.mark.parametrize("field", ["sex", "gender"])
def test_split_field_without_declaration_refused(tmp_path: Path, field: str) -> None:
    import yaml
    from custodian.tests.test_registry_survivors import invented_row

    from eii_custodian.publicdata.fetch.registry import RegistryError

    row = invented_row(columns=[{"name": field, "type": "string"}], public_splits=[])
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}), encoding="utf-8")
    with pytest.raises(RegistryError, match="sex field requires public_splits sex"):
        load_registry(path)


def test_declared_split_is_accepted(tmp_path: Path) -> None:
    import yaml
    from custodian.tests.test_registry_survivors import invented_row

    row = invented_row(
        columns=[{"name": "gender", "type": "string"}], public_splits=["sex"]
    )
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}), encoding="utf-8")
    assert load_registry(path)[0].public_splits == ("sex",)


@pytest.mark.parametrize("key", ["worldpop_qat_2020", "census_2020_workbook"])
def test_direct_file_receipt(tmp_path: Path, key: str) -> None:
    from custodian.tests.test_publicdata_behaviour import _sidecar

    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    entry = next(entry for entry in load_registry() if entry.key == key)
    body = b"invented raster bytes"
    if entry.extension == "xlsx":
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("xl/workbook.xml", "<workbook/>")
            archive.writestr("_rels/.rels", "<Relationships/>")
        body = buffer.getvalue()
    requested: list[str] = []

    def transport(url: str):
        requested.append(url)
        return _ok(url, body)

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert requested == [entry.url]
    assert side["sha256"] == sha256_hex(body)
    assert side["fetch_url"] == entry.url
    assert side["commit_allowed"] is False
    assert side["retrieved_utc"] == _clock()
    assert side["publisher"] == entry.publisher
    assert side["licence_basis"] == entry.licence_basis
