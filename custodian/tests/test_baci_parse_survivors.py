"""Independent output and refusal oracles for invented BACI archives."""

import json
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path

import pytest
from custodian.tests.test_baci import MEMBERS, archive, configuration

from eii_custodian.publicdata.baci import parse
from eii_custodian.publicdata.baci.config import BaciError, Config


@contextmanager
def refusal(message):
    with pytest.raises(BaciError) as caught:
        yield
    assert str(caught.value) == message


def run(tmp_path, members=None, raw=None):
    path = tmp_path / "invented.zip"
    path.write_bytes(archive(MEMBERS if members is None else members))
    output = tmp_path / "nested" / "output"
    result = parse.parse_archive(
        path, Config.from_mapping(configuration() if raw is None else raw), output
    )
    return result, output


def test_baci_complete_output(tmp_path):
    members = dict(MEMBERS)
    members["invented-country.csv"] = members["invented-country.csv"].replace(
        "Invented target,", "Invented target,ZZZ"
    )
    result, output = run(tmp_path, members)
    digest = sha256(members["invented-year.csv"].encode()).hexdigest()
    common = {
        "hs_revision": "invented-HS-A",
        "hs_code": "000001",
        "source_id": "cepii_baci",
        "source_version": "invented-release",
        "year": 2091,
        "currency": "invented-currency",
        "value_unit": "invented-value-unit",
        "quantity_unit": "invented-quantity-unit",
        "valuation_basis": "unknown",
        "member_sha256": digest,
    }
    expected = {
        "pub_baci_country": [
            {
                "country_code": "00Q",
                "source_name": "Invented target",
                "iso3": "ZZZ",
                "source_id": "cepii_baci",
                "source_version": "invented-release",
            },
            {
                "country_code": "00A",
                "source_name": "Invented partner",
                "iso3": None,
                "source_id": "cepii_baci",
                "source_version": "invented-release",
            },
        ],
        "pub_baci_product": [
            {
                "hs_code": "000001",
                "source_description": "Invented product",
                "hs_revision": "invented-HS-A",
                "source_id": "cepii_baci",
                "source_version": "invented-release",
            }
        ],
        "pub_baci_trade": [
            {
                **common,
                "exporter_code": "00Q",
                "importer_code": "00A",
                "value": "123456789012.345600",
                "quantity": "0",
                "quantity_status": "present",
            },
            {
                **common,
                "exporter_code": "00A",
                "importer_code": "00Q",
                "value": "1.00",
                "quantity": None,
                "quantity_status": "source_missing",
            },
            {
                **common,
                "exporter_code": "00Q",
                "importer_code": "00Q",
                "value": "0",
                "quantity": "2.00",
                "quantity_status": "present",
            },
        ],
    }
    outputs = {}
    for table, rows in expected.items():
        payload = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows
        ).encode()
        assert (output / f"{table}.jsonl").read_bytes() == payload
        outputs[table] = {"sha256": sha256(payload).hexdigest(), "rows": len(rows)}
    receipts = []
    for name, header, count in [
        ("invented-country.csv", ["code", "name", "iso3"], 2),
        ("invented-product.csv", ["code", "description", "revision"], 1),
        (
            "invented-year.csv",
            [
                "year",
                "exporter",
                "importer",
                "product",
                "value",
                "quantity",
                "revision",
            ],
            4,
        ),
    ]:
        payload = members[name].encode()
        receipts.append(
            {
                "name": name,
                "header": header,
                "rows": count,
                "bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        )
    assert result == {
        "members": receipts,
        "outputs": outputs,
        "raw": 4,
        "selected": 3,
        "excluded": 1,
        "coverage": [
            {
                "year": 2091,
                "raw": 4,
                "selected": 3,
                "partners": ["00A", "00Q"],
                "products": ["000001"],
                "missing_partners": [],
                "missing_products": [],
                "missing_cells": "absence is not zero",
            }
        ],
    }


@pytest.mark.parametrize(
    "value,reason",
    [
        ("nan", "decimal_format"),
        ("0.1234567", "decimal_fractional_digits"),
        ("1" * 19, "decimal_total_digits"),
    ],
)
def test_baci_decimal_refusals(value, reason):
    with refusal(reason):
        parse.decimal_text(value, Config.from_mapping(configuration()))


def test_baci_integer_decimal():
    assert (
        parse.decimal_text("1234567", Config.from_mapping(configuration())) == "1234567"
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("empty", "header"),
        ("header", "header"),
        ("csv", "archive_integrity"),
        ("inventory", "inventory"),
        ("dictionary_key", "dictionary_key"),
        ("product_revision", "revision"),
        ("year", "year"),
        ("revision", "revision"),
        ("country_key", "country_key"),
        ("product_key", "product_key"),
        ("duplicate", "duplicate_trade_key"),
    ],
)
def test_baci_parser_refusals(tmp_path, change, reason):
    members = dict(MEMBERS)
    name = "invented-year.csv"
    if change == "empty":
        members[name] = ""
    elif change == "header":
        members[name] = members[name].replace("year,", "wrong,", 1)
    elif change == "csv":
        members[name] += '"unterminated'
    elif change == "inventory":
        del members[name]
    elif change == "dictionary_key":
        members["invented-country.csv"] = members["invented-country.csv"].replace(
            "00A", "00Q"
        )
    elif change == "product_revision":
        members["invented-product.csv"] = members["invented-product.csv"].replace(
            "invented-HS-A", "invented-HS-B"
        )
    elif change == "year":
        members[name] = members[name].replace("2091", "2090")
    elif change == "revision":
        members[name] = members[name].replace("invented-HS-A", "invented-HS-B")
    elif change == "country_key":
        members[name] = members[name].replace("00A", "00Z")
    elif change == "product_key":
        members[name] = members[name].replace("000001", "000002")
    elif change == "duplicate":
        members[name] = members[name].replace("00A,00A", "00Q,00Q")
    raw = configuration()
    raw["members"][2]["bytes"] = [0, 2048]
    with refusal(reason):
        run(tmp_path, members, raw)


@pytest.mark.parametrize(
    "kind,field,span,reason",
    [
        (None, "archive_bytes", [1, 2], "archive_bytes"),
        (None, "raw_rows", [5, 5], "raw_count"),
        (None, "raw_rows", [0, 3], "trade_count"),
        ("trade", "rows", [5, 5], "trade_count"),
        ("trade", "rows", [0, 3], "trade_count"),
        ("country", "rows", [3, 3], "dictionary_count"),
        ("country", "rows", [0, 1], "dictionary_count"),
    ],
)
def test_baci_count_messages(tmp_path, kind, field, span, reason):
    raw = configuration()
    if kind is None:
        raw[field] = span
    else:
        next(m for m in raw["members"] if m["kind"] == kind)[field] = span
    with refusal(reason):
        run(tmp_path, raw=raw)


def test_baci_member_checksum_message(tmp_path):
    raw = configuration()
    raw["members"][0]["sha256"] = "f" * 64
    with refusal("member_checksum"):
        run(tmp_path, raw=raw)


def test_baci_member_chunks_and_exact_bound(tmp_path):
    members = dict(MEMBERS)
    members["invented-country.csv"] = members["invented-country.csv"].replace(
        "Invented target", "invented " * 9000
    )
    raw = configuration()
    raw["archive_bytes"] = [1, 100000]
    size = len(members["invented-country.csv"].encode())
    raw["members"][0]["bytes"] = [size, size]
    result, _ = run(tmp_path, members, raw)
    assert result["members"][0]["bytes"] == size


def test_baci_excluded_row_does_not_end_scan(tmp_path):
    members = dict(MEMBERS)
    lines = members["invented-year.csv"].splitlines()
    members["invented-year.csv"] = "\n".join([lines[0], lines[4], *lines[1:4]]) + "\n"
    assert run(tmp_path, members)[0]["selected"] == 3


def test_baci_quoted_crlf_preserved(tmp_path):
    members = dict(MEMBERS)
    members["invented-country.csv"] = members["invented-country.csv"].replace(
        "Invented target", '"Invented\r\ntarget"'
    )
    _, output = run(tmp_path, members)
    row = json.loads((output / "pub_baci_country.jsonl").read_text().splitlines()[0])
    assert row["source_name"] == "Invented\r\ntarget"


def test_baci_partner_direction(tmp_path):
    members = dict(MEMBERS)
    lines = members["invented-year.csv"].splitlines()
    members["invented-year.csv"] = (
        "\n".join([lines[0], lines[1], lines[2], lines[4]]) + "\n"
    )
    raw = configuration()
    raw["raw_rows"] = [3, 3]
    raw["members"][2]["rows"] = [3, 3]
    coverage = run(tmp_path, members, raw)[0]["coverage"]
    assert coverage[0]["partners"] == ["00A"]
    assert coverage[0]["missing_partners"] == ["00Q"]


def test_baci_file_hash_bounded_read(tmp_path, monkeypatch):
    path = tmp_path / "invented.bin"
    path.write_bytes(b"invented")
    original = Path.open
    sizes = []

    @contextmanager
    def opened(self, *args, **kwargs):
        with original(self, *args, **kwargs) as source:

            class Reader:
                def read(self, size):
                    sizes.append(size)
                    return source.read(size)

            yield Reader()

    monkeypatch.setattr(Path, "open", opened)
    assert parse.file_hash(path) == sha256(b"invented").hexdigest()
    assert sizes == [65536, 65536]


def test_baci_output_explicit_encoding(tmp_path):
    class OtherDefaultPath(type(tmp_path)):
        def open(
            self, mode="r", buffering=-1, encoding=None, errors=None, newline=None
        ):
            if "b" not in mode:
                encoding = encoding or "cp037"
            return super().open(mode, buffering, encoding, errors, newline)

    test_baci_complete_output(OtherDefaultPath(tmp_path))


def test_baci_csv_explicit_encoding(tmp_path):
    import locale

    members = dict(MEMBERS)
    members["invented-country.csv"] = members["invented-country.csv"].replace(
        "Invented target", "Invented café"
    )
    previous = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, "C")
        _, output = run(tmp_path, members)
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)
    assert (
        json.loads((output / "pub_baci_country.jsonl").read_text().splitlines()[0])[
            "source_name"
        ]
        == "Invented café"
    )


def test_baci_direct_rows_strict_zip(tmp_path):
    from dataclasses import replace
    from zipfile import ZipFile

    # Member.load refuses a duplicate header at member_schema before _rows.
    member = Config.from_mapping(configuration()).members[0]
    member = replace(member, header=("code", "name", "iso3", "code"))
    path = tmp_path / "invented.zip"
    path.write_bytes(
        archive({"invented-country.csv": "code,name,iso3,code\n00Q,Invented,ZZZ\n"})
    )
    with ZipFile(path) as zipped:
        with pytest.raises(ValueError):
            list(parse._rows(zipped, member))


def test_baci_direct_duplicate_inventory(tmp_path):
    from dataclasses import replace
    from io import BytesIO
    from zipfile import ZipFile

    # Config.from_mapping refuses duplicate names at inventory first.
    # The duplicated member is trade: a second dictionary is refused at entry.
    config = Config.from_mapping(configuration())
    trade = next(member for member in config.members if member.kind == "trade")
    config = replace(config, members=(*config.members, trade))
    buffer = BytesIO(archive())
    with ZipFile(buffer, "a") as zipped:
        with pytest.warns(UserWarning, match="Duplicate name"):
            zipped.writestr(trade.name, MEMBERS[trade.name])
    path = tmp_path / "invented.zip"
    path.write_bytes(buffer.getvalue())
    with refusal("inventory"):
        parse.parse_archive(path, config, tmp_path)


@pytest.mark.parametrize("kind", ["country", "product"])
def test_baci_unconfirmed_second_dictionary_is_refused(tmp_path, kind):
    raw = configuration()
    raw["confirmed"] = False
    original = next(member for member in raw["members"] if member["kind"] == kind)
    extra_name = f"invented-{kind}-b.csv"
    raw["members"].append({**original, "name": extra_name})
    members = dict(MEMBERS)
    if kind == "country":
        members[extra_name] = (
            "code,name,iso3\n00B,Invented other,\n00C,Invented further,\n"
        )
    else:
        members[extra_name] = (
            "code,description,revision\n000002,Invented other product,invented-HS-A\n"
        )
    path = tmp_path / "invented.zip"
    path.write_bytes(archive(members))
    output = tmp_path / "nested" / "output"
    config = Config.from_mapping(raw)
    assert config.confirmed is False
    assert sum(member.kind == kind for member in config.members) == 2
    with refusal("dictionaries"):
        parse.parse_archive(path, config, output)
    assert not output.exists()
