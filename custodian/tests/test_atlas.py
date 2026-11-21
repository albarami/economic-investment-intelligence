"""Invented Atlas configuration, finished-file grains and refusal plants."""

from copy import deepcopy
from pathlib import Path

import pytest
from custodian.tests.fixtures.atlas.invented import (
    CPP_MEMBERS,
    CPY_MEMBERS,
    configuration,
    cpp_archive,
    cpy_archive,
)


def _parse(
    tmp_path: Path, cpy: dict[str, str], cpp: dict[str, str], raw: dict[str, object]
):
    from eii_custodian.publicdata.atlas.config import Config
    from eii_custodian.publicdata.atlas.parse import parse_archives

    tmp_path.mkdir(parents=True, exist_ok=True)
    cpy_path = tmp_path / "cpy.zip"
    cpp_path = tmp_path / "cpp.zip"
    cpy_path.write_bytes(cpy_archive(cpy))
    cpp_path.write_bytes(cpp_archive(cpp))
    return parse_archives(
        {"country_product_year": cpy_path, "country_partner_product_year": cpp_path},
        Config.from_mapping(raw),
        tmp_path / "out",
    )


def test_atlas_closed_configuration_refuses_rebuild_and_pending() -> None:
    from eii_custodian.publicdata.atlas.config import AtlasError, Config, load_config

    raw = configuration()
    loaded = Config.from_mapping(raw)
    assert loaded.finished_only is True
    assert loaded.publisher_mapping == "pending"
    pending = load_config()
    assert pending.confirmed is False
    assert pending.access == "visitor"
    assert pending.bound_origin == "pending"
    assert pending.source_version == ""
    assert pending.page == "https://atlas.hks.harvard.edu/data-downloads"
    assert pending.page_sha256 == (
        "c880b9e92765c8d5fe42c776da6fe29a2ba6b840ffa5df78e660f60c84fb2b5b"
    )
    assert pending.reviewed_urls == (
        pending.page,
        "https://dataverse.harvard.edu/dataverse/atlas",
        "https://dataverse.harvard.edu/api/dataverses/atlas/contents",
        "https://dataverse.harvard.edu/api/access/datafile/13685113",
    )
    assert pending.licence_words == "CC0 1.0"
    assert "no registration, no key, no paid tier" in pending.evidence
    assert "guestbook" in pending.evidence
    assert "2026-11-21" in pending.attribution
    assert pending.year_selection == "pending"
    assert all(item.url == "" for item in pending.downloads)
    assert tuple(item.grain for item in pending.downloads) == (
        "country_product_year",
        "country_partner_product_year",
    )
    for key in ("finished_only", "downloads", "measures"):
        broken = deepcopy(raw)
        del broken[key]
        with pytest.raises(AtlasError, match="configuration_fields"):
            Config.from_mapping(broken)
    with pytest.raises(AtlasError, match="rebuild_refused"):
        Config.from_mapping({**raw, "finished_only": False})
    with pytest.raises(AtlasError, match="rebuild_refused"):
        changed = deepcopy(raw)
        changed["downloads"][0]["members"][0]["kind"] = "rebuild"
        Config.from_mapping(changed)
    with pytest.raises(AtlasError, match="configuration_fields"):
        Config.from_mapping({**raw, "concordance": "invented"})
    with pytest.raises(AtlasError, match="bounds_unconfirmed"):
        Config.from_mapping({**raw, "bound_origin": "pending"})


def test_atlas_selection_decimals_and_excluded_rows(tmp_path: Path) -> None:
    from eii_custodian.publicdata.atlas.config import AtlasError
    from eii_custodian.publicdata.fetch.decimals import DecimalRefusal, exact_decimal

    parsed = _parse(
        tmp_path / "ok", dict(CPY_MEMBERS), dict(CPP_MEMBERS), configuration()
    )
    assert parsed["selected"] == 3
    assert parsed["excluded"] == 2
    assert parsed["finished_only"] is True
    assert parsed["hs_detail"] == "configured revision only; no concordance inferred"
    for text in ("-123456.654321", "123456.654321", "0", "0.000000"):
        assert (
            exact_decimal(text, total_digits=12, fractional_digits=6, signed=True)
            == text
        )
    with pytest.raises(DecimalRefusal, match="decimal_fractional_digits"):
        exact_decimal("1.1234567", total_digits=12, fractional_digits=6, signed=True)
    with pytest.raises(DecimalRefusal, match="decimal_total_digits"):
        exact_decimal(
            "1234567.654321", total_digits=12, fractional_digits=6, signed=True
        )
    with pytest.raises(DecimalRefusal, match="decimal_format"):
        exact_decimal(1.25, total_digits=12, fractional_digits=6, signed=True)
    members = dict(CPY_MEMBERS)
    members["invented-cpy.csv"] = members["invented-cpy.csv"].replace("00A", "00Z")
    with pytest.raises(AtlasError, match="country_key"):
        _parse(tmp_path / "bad-row", members, dict(CPP_MEMBERS), configuration())
    other = dict(CPY_MEMBERS)
    other["invented-cpy.csv"] = other["invented-cpy.csv"].replace(
        "invented-HS-A", "invented-HS-B"
    )
    with pytest.raises(AtlasError, match="revision"):
        _parse(tmp_path / "revision", other, dict(CPP_MEMBERS), configuration())


def test_atlas_rejects_a_third_grain(tmp_path: Path) -> None:
    from eii_custodian.publicdata.atlas.config import AtlasError, Config
    from eii_custodian.publicdata.atlas.parse import parse_archives

    raw = configuration()
    with pytest.raises(AtlasError, match="finished_grain"):
        parse_archives(
            {"country_product_year": tmp_path / "missing.zip"},
            Config.from_mapping(raw),
            tmp_path / "out",
        )


def test_atlas_documented_contract_and_product_boundary() -> None:
    from dataclasses import fields

    from custodian.tests.repository_root import repository_root

    from eii_custodian.publicdata.atlas.contracts import (
        Country,
        CountryProduct,
        Product,
    )

    root = repository_root(Path(__file__))
    section = (
        (root / "docs/03_DATA_CONTRACTS.md")
        .read_text()
        .split("#### Gravity and Atlas columns and source chain (S2-T25)")[1]
        .split("## 8.")[0]
    )
    for cls in (CountryProduct, Country, Product):
        assert all(f"`{field.name}`" in section for field in fields(cls))
    assert "total_digits: 12" in section
    sources = "\n".join(
        path.read_text()
        for path in (root / "custodian/src/eii_custodian/publicdata/atlas").glob("*.py")
    )
    assert "eii_product" not in sources
