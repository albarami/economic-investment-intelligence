"""Invented Gravity configuration, precision and parser refusal plants."""

from copy import deepcopy
from pathlib import Path

import pytest
from custodian.tests.fixtures.gravity.invented import MEMBERS, archive, configuration


def _parse(tmp_path: Path, members: dict[str, str], raw: dict[str, object]):
    from eii_custodian.publicdata.gravity.config import Config
    from eii_custodian.publicdata.gravity.parse import parse_archive

    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "archive.zip"
    path.write_bytes(archive(members))
    return parse_archive(path, Config.from_mapping(raw), tmp_path / "out")


def test_gravity_closed_configuration_and_pending_file() -> None:
    from eii_custodian.publicdata.gravity.config import (
        Config,
        GravityError,
        load_config,
    )

    raw = configuration()
    assert Config.from_mapping(raw).publisher_mapping == "pending"
    pending = load_config()
    assert pending.confirmed is False
    assert pending.bound_origin == "pending"
    assert pending.reviewed_urls == ()
    assert pending.page == ""
    for key in raw:
        broken = deepcopy(raw)
        del broken[key]
        with pytest.raises(GravityError, match="configuration_fields"):
            Config.from_mapping(broken)
    with pytest.raises(GravityError, match="bounds_unconfirmed"):
        Config.from_mapping({**raw, "bound_origin": "pending"})
    with pytest.raises(GravityError, match="publisher_mapping"):
        Config.from_mapping({**raw, "publisher_mapping": "invented"})
    with pytest.raises(GravityError, match="blocked_host"):
        Config.from_mapping(
            {
                **raw,
                "reviewed_urls": ["https://www.data.gov.qa/invented?id=8"],
                "page": "https://www.data.gov.qa/invented?id=8",
            }
        )


def test_gravity_decimal_limits(tmp_path: Path) -> None:
    from eii_custodian.publicdata.fetch.decimals import DecimalRefusal, exact_decimal

    parsed = _parse(tmp_path, dict(MEMBERS), configuration())
    assert parsed["selected"] == 2
    assert parsed["raw"] == 3
    assert parsed["hs_revision"] == "absent"
    assert parsed["hs_detail"] == "recorded marker; no revision inferred"
    for text, total, fraction in (
        ("123456.789", 9, 3),
        ("0.000", 9, 3),
        ("123456789012.3456", 16, 4),
        ("0.0000", 16, 4),
    ):
        assert (
            exact_decimal(
                text, total_digits=total, fractional_digits=fraction, signed=False
            )
            == text
        )
    for text, total, fraction, reason in (
        ("1234567.890", 9, 3, "decimal_total_digits"),
        ("1.1234", 9, 3, "decimal_fractional_digits"),
        ("1234567890123.3456", 16, 4, "decimal_total_digits"),
        ("1.12345", 16, 4, "decimal_fractional_digits"),
    ):
        with pytest.raises(DecimalRefusal, match=reason):
            exact_decimal(
                text, total_digits=total, fractional_digits=fraction, signed=False
            )
    with pytest.raises(DecimalRefusal, match="decimal_format"):
        exact_decimal(1.25, total_digits=9, fractional_digits=3, signed=False)


@pytest.mark.parametrize(
    "old,new,reason",
    [
        ("2091,00A,00B", "2090,00A,00B", "year"),
        ("2091,00A,00B", "2092,00A,00B", "stale_period"),
        ("2091,00A,00B", "2091,00A,00Z", "country_key"),
        ("123456.789", "NA", None),
        ("123456.789", "1234567.890", "decimal_total_digits"),
        ("1,0,0,1", "2,0,0,1", "flag_token"),
        ("..,0.0000", "undeclared,0.0000", "missing_undeclared"),
    ],
)
def test_gravity_row_plants(
    tmp_path: Path, old: str, new: str, reason: str | None
) -> None:
    from eii_custodian.publicdata.gravity.config import GravityError

    members = dict(MEMBERS)
    members["invented-bilateral.csv"] = members["invented-bilateral.csv"].replace(
        old, new, 1
    )
    if reason is None:
        parsed = _parse(tmp_path, members, configuration())
        text = (tmp_path / "out" / "pub_gravity_bilateral.jsonl").read_text()
        assert parsed["selected"] == 2
        assert '"distance": null' in text
        assert "0.0000" in text
        return
    with pytest.raises(GravityError, match=reason):
        _parse(tmp_path, members, configuration())


def test_gravity_narrower_selection_records_excluded_years(tmp_path: Path) -> None:
    members = dict(MEMBERS)
    members["invented-bilateral.csv"] = members["invented-bilateral.csv"].replace(
        "2091,00A,00B,0.000,0,0,0,0,0.0000,0.0000",
        "2090,00Q,00A,1.000,0,0,0,0,0.0000,0.0000\n"
        "2091,00A,00B,0.000,0,0,0,0,0.0000,0.0000",
        1,
    )
    raw = configuration()
    raw["year_selection"] = "narrower"
    raw["raw_rows"] = [4, 4]
    for member in raw["members"]:
        if member["kind"] == "bilateral":
            member["rows"] = [4, 4]
    parsed = _parse(tmp_path, members, raw)
    assert parsed["raw"] == 4
    assert parsed["selected"] == 2
    assert parsed["excluded_coverage"] == [{"year": 2090, "rows": 1}]


def test_gravity_archive_and_bound_plants(tmp_path: Path) -> None:
    from eii_custodian.publicdata.gravity.config import GravityError

    members = dict(MEMBERS)
    with pytest.raises(GravityError, match="member_count"):
        _parse(
            tmp_path / "missing",
            {key: value for key, value in members.items() if "country" not in key},
            configuration(),
        )
    renamed = dict(members)
    renamed["invented-renamed.csv"] = renamed.pop("invented-country.csv")
    with pytest.raises(GravityError, match="inventory"):
        _parse(tmp_path / "renamed", renamed, configuration())
    duplicate = dict(members)
    duplicate["invented-bilateral.csv"] = duplicate["invented-bilateral.csv"].replace(
        "00A,00B", "00Q,00A", 1
    )
    with pytest.raises(GravityError, match="duplicate_trade_key"):
        _parse(tmp_path / "duplicate", duplicate, configuration())
    low = configuration()
    low["raw_rows"] = [4, 4]
    with pytest.raises(GravityError, match="raw_count"):
        _parse(tmp_path / "low", dict(members), low)
    high = configuration()
    high["archive_bytes"] = [1, 2]
    with pytest.raises(GravityError, match="archive_bytes"):
        _parse(tmp_path / "high", dict(members), high)


def test_gravity_does_not_join_baci_countries() -> None:
    from eii_custodian.publicdata.baci.contracts import Country as BaciCountry
    from eii_custodian.publicdata.gravity.contracts import baci_country_is_not_joined

    baci = BaciCountry(
        source_id="cepii_baci",
        source_version="invented",
        country_code="00Q",
        source_name="Invented",
        iso3=None,
    )
    assert baci_country_is_not_joined(baci, "00A", 3) is True


def test_gravity_documented_contract() -> None:
    from dataclasses import fields

    from custodian.tests.repository_root import repository_root

    from eii_custodian.publicdata.gravity.contracts import Bilateral, Country

    root = repository_root(Path(__file__))
    document = (root / "docs/03_DATA_CONTRACTS.md").read_text()
    section = document.split(
        "#### Gravity and Atlas columns and source chain (S2-T25)"
    )[1].split("## 8.")[0]
    assert all(f"`{field.name}`" in section for field in fields(Bilateral))
    assert all(f"`{field.name}`" in section for field in fields(Country))
    assert "total_digits: 9" in section
    assert "total_digits: 16" in section
    sources = "\n".join(
        path.read_text()
        for path in (root / "custodian/src/eii_custodian/publicdata/gravity").glob(
            "*.py"
        )
    )
    assert "eii_product" not in sources
