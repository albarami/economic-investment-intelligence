"""Supplied metadata and invented files of the reviewed native archive shape."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from eii_custodian.publicdata.baci.config import BaciError, Config, load_config
from eii_custodian.publicdata.baci.parse import parse_archive

from .fixtures.baci.invented import configuration


def native_archive():
    raw = configuration()
    bodies = {
        "invented-year.csv": "t,i,j,k,v,q\n2091,00A,00Q,000001,12.50,0\n",
        "invented-country.csv": "country_code,country_name,country_iso2,country_iso3\n00Q,Invented target,QQ,QQQ\n00A,Invented partner,AA,AAA\n",
        "invented-product.csv": "code,description\n000001,Invented product\n",
        "Readme.txt": "Invented readme; no source values.\n",
    }
    mappings = {
        "trade": dict(
            zip(
                ("t", "i", "j", "k", "v", "q"),
                (
                    "year",
                    "exporter_code",
                    "importer_code",
                    "hs_code",
                    "value",
                    "quantity",
                ),
                strict=True,
            )
        ),
        "country": {
            "country_code": "country_code",
            "country_name": "source_name",
            "country_iso2": "iso2",
            "country_iso3": "iso3",
        },
        "product": {"code": "hs_code", "description": "source_description"},
    }
    for member in raw["members"]:
        member["columns"] = mappings[member["kind"]]
        member["header"] = list(member["columns"])
        if member["kind"] == "trade":
            member["rows"] = [1, 1]
    raw["members"].append(
        {
            "name": "Readme.txt",
            "kind": "text",
            "year": None,
            "bytes": [1, 2048],
            "rows": None,
            "sha256": "",
            "columns": {},
            "header": [],
        }
    )
    raw["raw_rows"] = [1, 1]
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as zipped:
        for name, body in bodies.items():
            zipped.writestr(name, body)
        for member in raw["members"]:
            info = zipped.getinfo(member["name"])
            member["bytes"] = [info.file_size, info.file_size]
            member["compressed_bytes"] = [info.compress_size, info.compress_size]
    return raw, buffer.getvalue()


def test_native_headers_text_member_and_compressed_bounds(tmp_path):
    raw, body = native_archive()
    config = Config.from_mapping(raw)
    path = tmp_path / "invented.zip"
    path.write_bytes(body)
    output = tmp_path / "output"
    result = parse_archive(path, config, output)
    assert result["raw"] == result["selected"] == 1
    import json

    trade = json.loads((output / "pub_baci_trade.jsonl").read_text())
    assert trade["hs_revision"] == "invented-HS-A"
    product = json.loads((output / "pub_baci_product.jsonl").read_text())
    assert product["hs_revision"] == "invented-HS-A"
    countries = [
        json.loads(row)
        for row in (output / "pub_baci_country.jsonl").read_text().splitlines()
    ]
    assert all("iso2" not in row for row in countries)
    assert len(result["members"]) == 4
    assert all(m["compressed_bytes"] > 0 for m in result["members"])
    assert (
        next(m for m in result["members"] if m["name"] == "Readme.txt")["rows"] is None
    )


@pytest.mark.parametrize(
    "plant",
    ["compressed", "expanded", "extra", "missing", "schema", "text_name", "counts"],
)
def test_reviewed_archive_plants(tmp_path, plant):
    raw, body = native_archive()
    path = tmp_path / "invented.zip"
    path.write_bytes(body)
    if plant == "compressed":
        raw["members"][0]["compressed_bytes"] = [0, 0]
        reason = "member_compressed_bytes"
    elif plant == "expanded":
        raw["members"][0]["bytes"] = [0, 0]
        reason = "member_bytes"
    elif plant in {"extra", "missing"}:
        if plant == "missing":
            raw["members"].pop()
        else:
            raw["members"].append({**raw["members"][-1], "name": "invented.txt"})
        reason = "inventory" if plant == "missing" else "member_name"
    elif plant == "schema":
        raw["members"][0]["columns"]["country_iso3"] = "invented"
        reason = "member_schema"
    elif plant == "text_name":
        raw["members"][-1]["name"] = "../Readme.txt"
        reason = "member_name"
    else:
        raw["raw_rows"] = None
        reason = "rows_unconfirmed"
    with pytest.raises(BaciError, match=rf"^{reason}$"):
        parse_archive(path, Config.from_mapping(raw), tmp_path / "output")


def test_pending_row_counts_never_activate(tmp_path):
    raw, body = native_archive()
    raw.update(confirmed=False, raw_rows=None)
    for member in raw["members"]:
        member["rows"] = None
    config = Config.from_mapping(raw)
    path = tmp_path / "invented.zip"
    path.write_bytes(body)
    with pytest.raises(BaciError, match=r"^rows_unconfirmed$"):
        parse_archive(path, config, tmp_path / "output")
    raw["confirmed"] = True
    with pytest.raises(BaciError, match=r"^rows_unconfirmed$"):
        Config.from_mapping(raw)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("rows", [0, 0], "member_schema"),
        ("columns", {"invented": "invented"}, "member_schema"),
        ("header", ["invented"], "member_schema"),
        ("year", 2091, "member_year"),
        ("extra", "invented", "configuration_fields"),
    ],
)
def test_readme_record_is_closed(field, value, reason):
    raw, _ = native_archive()
    raw["members"][-1][field] = value
    with pytest.raises(BaciError, match=rf"^{reason}$"):
        Config.from_mapping(raw)


def test_native_iso2_is_validated(tmp_path):
    raw, body = native_archive()
    buffer = BytesIO()
    with (
        ZipFile(BytesIO(body)) as original,
        ZipFile(buffer, "w", compression=ZIP_DEFLATED) as mutated,
    ):
        for info in original.infolist():
            text = original.read(info.filename)
            if info.filename == "invented-country.csv":
                text = text.replace(b",QQ,QQQ", b",Q3,QQQ")
            mutated.writestr(info.filename, text)
            member = next(m for m in raw["members"] if m["name"] == info.filename)
            changed = mutated.getinfo(info.filename)
            member["bytes"] = [changed.file_size, changed.file_size]
            member["compressed_bytes"] = [changed.compress_size, changed.compress_size]
    path = tmp_path / "invented.zip"
    path.write_bytes(buffer.getvalue())
    with pytest.raises(BaciError, match=r"^iso2$"):
        parse_archive(path, Config.from_mapping(raw), tmp_path / "output")


def test_lead_archive_reading_is_configured_without_guessed_counts():
    config = load_config()
    assert config.confirmed is False
    assert config.source_version == "202601"
    assert config.hs_revision == "HS17"
    assert config.archive_bytes == (794_583_540, 794_583_540)
    assert config.raw_rows is None
    expected = [
        ("BACI_HS17_Y2017_V202601.csv", 89_426_357, 324_485_600),
        ("BACI_HS17_Y2018_V202601.csv", 96_882_092, 352_137_922),
        ("BACI_HS17_Y2019_V202601.csv", 100_037_104, 365_060_090),
        ("BACI_HS17_Y2020_V202601.csv", 97_687_183, 357_505_759),
        ("BACI_HS17_Y2021_V202601.csv", 103_041_055, 377_609_211),
        ("BACI_HS17_Y2022_V202601.csv", 103_981_559, 380_985_070),
        ("BACI_HS17_Y2023_V202601.csv", 104_272_449, 382_952_885),
        ("BACI_HS17_Y2024_V202601.csv", 99_143_798, 363_762_242),
        ("product_codes_HS17_V202601.csv", 106_837, 598_831),
        ("country_codes_V202601.csv", 3121, 5346),
        ("Readme.txt", 389, 571),
    ]
    assert [(m.name, m.compressed_bytes, m.bytes) for m in config.members] == [
        (name, (compressed, compressed), (expanded, expanded))
        for name, compressed, expanded in expected
    ]
    assert all(m.rows is None and m.sha256 == "" for m in config.members)
    assert all(
        m.header == ("t", "i", "j", "k", "v", "q")
        for m in config.members
        if m.kind == "trade"
    )
    assert next(m for m in config.members if m.kind == "product").header == (
        "code",
        "description",
    )
    assert next(m for m in config.members if m.kind == "country").header == (
        "country_code",
        "country_name",
        "country_iso2",
        "country_iso3",
    )
    assert (
        "https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS17_V202601.zip"
        in config.reviewed_urls
    )
    assert (
        "c05558932651ca22915f5fca081f8c5ce30697ffcc845553e15763e84226d49f"
        in config.evidence
    )
