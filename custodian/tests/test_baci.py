"""Invented BACI configuration, precision and parser refusal plants."""

from copy import deepcopy
from pathlib import Path

import pytest
from custodian.tests.fixtures.baci.invented import MEMBERS, archive, configuration


def test_baci_metadata_contract():
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    assert Config.from_mapping(raw).total_digits == 18
    for key in raw:
        bad = deepcopy(raw)
        del bad[key]
        with pytest.raises(BaciError):
            Config.from_mapping(bad)
    for key, value in [
        ("unknown", 1),
        ("total_digits", True),
        ("archive_bytes", [3, 2]),
        ("fractional_digits", 19),
        ("page_sha256", "bad"),
    ]:
        with pytest.raises(BaciError):
            Config.from_mapping({**raw, key: value})


def test_baci_decimal_limits():
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import decimal_text

    config = Config.from_mapping(configuration())
    for text in ("123456789012.345600", "0", "0.000000", "1.00"):
        assert decimal_text(text, config) == text
    for text, reason in [
        ("1234567890123.345600", "decimal_total_digits"),
        ("0.1234567", "decimal_fractional_digits"),
        ("nan", "decimal_format"),
        ("inf", "decimal_format"),
        ("1e2", "decimal_format"),
        ("NA", "decimal_format"),
        ("-1", "decimal_format"),
    ]:
        with pytest.raises(BaciError, match=reason):
            decimal_text(text, config)


@pytest.mark.parametrize(
    "replacement,reason",
    [
        ("2090,00A,00A", "year"),
        ("2091,00B,00A", "country_key"),
        ("2091,00A,00A,1", "product_key"),
    ],
)
def test_baci_excluded_rows_are_validated(tmp_path: Path, replacement, reason):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    members = dict(MEMBERS)
    old = "2091,00A,00A,000001" if reason == "product_key" else "2091,00A,00A"
    members["invented-year.csv"] = members["invented-year.csv"].replace(
        old, replacement
    )
    path = tmp_path / "archive.zip"
    path.write_bytes(archive(members))
    with pytest.raises(BaciError, match=reason):
        parse_archive(path, Config.from_mapping(configuration()), tmp_path)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing", "inventory"),
        ("extra", "inventory"),
        ("unsafe", "inventory"),
        ("header", "header"),
        ("revision", "revision"),
        ("duplicate", "duplicate_trade_key"),
        ("missing_quantity", "decimal_format"),
        ("country_duplicate", "dictionary_key"),
        ("quantity_precision", "decimal_fractional_digits"),
    ],
)
def test_baci_archive_rejections(tmp_path, change, reason):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    members = dict(MEMBERS)
    if change == "missing":
        del members["invented-country.csv"]
    elif change == "extra":
        members["extra.csv"] = "invented"
    elif change == "unsafe":
        members["../invented.csv"] = members.pop("invented-country.csv")
    elif change == "header":
        members["invented-year.csv"] = members["invented-year.csv"].replace(
            "year,", "wrong,", 1
        )
    elif change == "revision":
        members["invented-year.csv"] = members["invented-year.csv"].replace(
            "invented-HS-A", "invented-HS-B"
        )
    elif change == "duplicate":
        members["invented-year.csv"] = members["invented-year.csv"].replace(
            "00A,00A", "00Q,00Q"
        )
    elif change == "country_duplicate":
        members["invented-country.csv"] = members["invented-country.csv"].replace(
            "00A,", "00Q,"
        )
    elif change == "quantity_precision":
        members["invented-year.csv"] = members["invented-year.csv"].replace(
            ",NA,", ",0.1234567,"
        )
    else:
        members["invented-year.csv"] = members["invented-year.csv"].replace(
            ",NA,", ",undeclared,"
        )
    path = tmp_path / "archive.zip"
    path.write_bytes(archive(members))
    with pytest.raises(BaciError, match=reason):
        parse_archive(path, Config.from_mapping(configuration()), tmp_path)


def test_baci_selected_manifest_tampering(tmp_path):
    import json
    from hashlib import sha256

    from custodian.tests.test_baci_fetch import build

    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    result = build(tmp_path)
    selected = result.manifests["cepii_baci"]
    directory = tmp_path / "cepii_baci"
    original = json.loads((directory / f"{selected}.manifest.json").read_text())
    for key in (
        "attribution",
        "method",
        "archive_sha256",
        "receipt",
        "members",
        "outputs",
        "config",
        "complete",
    ):
        changed = deepcopy(original)
        del changed[key]
        payload = json.dumps(changed).encode()
        digest = sha256(payload).hexdigest()
        (directory / f"{digest}.manifest.json").write_bytes(payload)
        with pytest.raises(BaciError):
            read_selected(tmp_path, digest)
    output = directory / f"{original['outputs']['pub_baci_trade']['sha256']}.jsonl"
    output.write_text("invented changed bytes")
    with pytest.raises(BaciError, match="output_hash"):
        read_selected(tmp_path, selected)


def test_baci_count_bounds(tmp_path):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    body = archive()
    path = tmp_path / "archive.zip"
    path.write_bytes(body)
    for bounds in ([4, 4], [3, 4], [4, 5]):
        config = configuration()
        config["raw_rows"] = bounds
        assert parse_archive(path, Config.from_mapping(config), tmp_path)["raw"] == 4
    for kind, slot, limits, reason in (
        (None, "raw_rows", [5, 5], "raw_count"),
        (None, "raw_rows", [0, 3], "trade_count"),
        ("trade", "rows", [5, 5], "trade_count"),
        ("trade", "rows", [0, 3], "trade_count"),
        ("country", "rows", [3, 3], "dictionary_count"),
        ("country", "rows", [0, 1], "dictionary_count"),
        ("product", "bytes", [1, 2], "member_bytes"),
        ("product", "bytes", [1024, 2048], "member_bytes"),
    ):
        config = configuration()
        if kind is None:
            config[slot] = limits
        else:
            next(m for m in config["members"] if m["kind"] == kind)[slot] = limits
        with pytest.raises(BaciError, match=reason):
            parse_archive(path, Config.from_mapping(config), tmp_path)


def test_baci_cache_leak(tmp_path):
    import subprocess

    from custodian.tests.repository_root import repository_root

    sentinel = "invented-" + "baci-cache-" + "sentinel-only"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "invented.txt").write_text(sentinel)
    root = repository_root(Path(__file__))
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout

    def leaked(paths):
        return [p for p in paths if p.is_file() and sentinel.encode() in p.read_bytes()]

    candidates = [root / name.decode() for name in listed.split(b"\0") if name]
    assert leaked(candidates) == []
    plant = tmp_path / "invented-output.txt"
    plant.write_text(sentinel)
    assert leaked([plant]) == [plant]


def test_baci_documented_contract():
    from dataclasses import fields

    from custodian.tests.repository_root import repository_root

    from eii_custodian.publicdata.baci.config import load_config
    from eii_custodian.publicdata.baci.contracts import Country, Product, Trade

    root = repository_root(Path(__file__))
    document = (root / "docs/03_DATA_CONTRACTS.md").read_text()
    section = document.split("#### BACI columns and source chain (S2-T24)")[1].split(
        "## 8."
    )[0]
    catalogue = document.split("#### BACI table contracts (S2-T24)")[1].split(
        "### 7.3"
    )[0]
    config = load_config()

    def complete(text):
        return (
            all(
                f"`{field.name}`" in text
                for cls in (Trade, Country, Product)
                for field in fields(cls)
            )
            and f"total_digits: {config.total_digits}" in text
            and f"fractional_digits: {config.fractional_digits}" in text
        )

    assert complete(catalogue + section)
    assert not complete((catalogue + section).replace("`member_sha256`", "missing"))
    assert not complete(
        (catalogue + section).replace("total_digits: 18", "total_digits: 17")
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.update(publisher=""),
        lambda c: c.update(attribution=""),
        lambda c: c.update(source_version=""),
        lambda c: c.update(hs_revision=""),
        lambda c: c.update(value_unit=""),
        lambda c: c.update(quantity_unit=""),
        lambda c: c.update(currency=""),
        lambda c: c.update(period_first=2092),
        lambda c: c.update(confirmed=1),
        lambda c: c.update(country_width=0),
        lambda c: c.update(product_width=False),
        lambda c: c.update(access="other"),
        lambda c: c.update(method_version="v2"),
        lambda c: c.update(publisher_sha256="bad"),
        lambda c: c.update(reviewed_urls=[]),
        lambda c: c.update(members=[]),
        lambda c: c["members"][0].update(name="../bad.csv"),
        lambda c: c["members"][0].update(kind="other"),
        lambda c: c["members"][0].update(year=2091),
        lambda c: c["members"][0].update(sha256="bad"),
        lambda c: c["members"][0].update(header=["code"]),
        lambda c: c["members"][0].update(columns={"code": "country_code"}),
        lambda c: c["members"][0].update(rows=[True, 2]),
        lambda c: c["members"][0].update(bytes=[2, 1]),
    ],
    ids=[
        "publisher",
        "attribution",
        "source-version",
        "revision",
        "value-unit",
        "quantity-unit",
        "currency",
        "period",
        "confirmed-type",
        "country-width",
        "product-width",
        "access",
        "method",
        "checksum",
        "urls",
        "members",
        "member-name",
        "member-kind",
        "member-year",
        "member-hash",
        "header",
        "mapping",
        "count-type",
        "bounds",
    ],
)
def test_baci_configuration_plants(mutate):
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    mutate(raw)
    with pytest.raises(BaciError):
        Config.from_mapping(raw)


def test_baci_archive_integrity(tmp_path):
    from io import BytesIO
    from zipfile import ZipFile

    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    path = tmp_path / "archive.zip"
    raw = archive()
    corrupted = bytearray(raw)
    index = corrupted.index(b"Invented target")
    corrupted[index] = ord("X")
    for payload in (raw[:-10], bytes(corrupted), b"invented-not-a-zip"):
        path.write_bytes(payload)
        with pytest.raises(BaciError, match="archive_integrity"):
            parse_archive(path, Config.from_mapping(configuration()), tmp_path)
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zipped:
        for name, content in MEMBERS.items():
            zipped.writestr(name, content)
        with pytest.warns(UserWarning, match="Duplicate name"):
            zipped.writestr("invented-year.csv", MEMBERS["invented-year.csv"])
    path.write_bytes(buffer.getvalue())
    with pytest.raises(BaciError, match="inventory"):
        parse_archive(path, Config.from_mapping(configuration()), tmp_path)


def test_baci_checksum_plants(tmp_path):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    path = tmp_path / "archive.zip"
    path.write_bytes(archive())
    config = configuration()
    config["members"][0]["sha256"] = "f" * 64
    with pytest.raises(BaciError, match="member_checksum"):
        parse_archive(path, Config.from_mapping(config), tmp_path)


def test_baci_deflate_failure_is_safe(tmp_path, monkeypatch):
    import zlib

    from eii_custodian.publicdata.baci import parse
    from eii_custodian.publicdata.baci.config import BaciError, Config

    path = tmp_path / "archive.zip"
    path.write_bytes(archive())

    def broken(*args, **kwargs):
        raise zlib.error("invented-compressed-error")

    monkeypatch.setattr(parse.ZipFile, "open", broken)
    with pytest.raises(BaciError, match="archive_integrity"):
        parse.parse_archive(path, Config.from_mapping(configuration()), tmp_path)
