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
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    import json
    from hashlib import sha256

    from custodian.tests.test_baci_fetch import build

    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    result = build(fixture_cache)
    selected = result.manifests["cepii_baci"]
    directory = fixture_cache / "cepii_baci"
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
            read_selected(fixture_cache, digest)
    output = directory / f"{original['outputs']['pub_baci_trade']['sha256']}.jsonl"
    output.write_text("invented changed bytes")
    with pytest.raises(BaciError, match="output_hash"):
        read_selected(fixture_cache, selected)


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


@pytest.mark.parametrize("width", ["missing", "extra"])
def test_baci_row_schema_guard(tmp_path, width):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    members = dict(MEMBERS)
    lines = members["invented-year.csv"].splitlines()
    fields = lines[-1].split(",")
    fields = fields[:-1] if width == "missing" else [*fields, "invented-extra"]
    lines[-1] = ",".join(fields)
    members["invented-year.csv"] = "\n".join(lines) + "\n"
    path = tmp_path / "archive.zip"
    path.write_bytes(archive(members))
    with pytest.raises(BaciError, match=r"^row_schema$"):
        parse_archive(path, Config.from_mapping(configuration()), tmp_path)


def test_baci_running_member_bytes_guard(tmp_path, monkeypatch):
    from io import BytesIO
    from zipfile import ZipInfo

    from eii_custodian.publicdata.baci import parse
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    member = raw["members"][0]
    content = MEMBERS[member["name"]].encode()
    member["bytes"] = [1, len(content)]
    path = tmp_path / "archive.zip"
    path.write_bytes(archive())
    original = parse.ZipFile.open
    reads = []

    class Overrun(BytesIO):
        def read(self, size=-1):
            assert not reads, "read continued past the running member bound"
            reads.append(size)
            return super().read(size)

    def supplied(zipped, name, *args, **kwargs):
        if isinstance(name, ZipInfo) and name.filename == member["name"]:
            assert name.file_size == len(content)
            return Overrun(content + b"x")
        return original(zipped, name, *args, **kwargs)

    monkeypatch.setattr(parse.ZipFile, "open", supplied)
    with pytest.raises(BaciError, match=r"^member_bytes$"):
        parse.parse_archive(path, Config.from_mapping(raw), tmp_path)
    assert reads == [65536]


def test_baci_member_size_consistency_guard(tmp_path, monkeypatch):
    from io import BytesIO
    from zipfile import ZipInfo

    from eii_custodian.publicdata.baci import parse
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    member = raw["members"][0]
    content = MEMBERS[member["name"]].encode()
    path = tmp_path / "archive.zip"
    path.write_bytes(archive())
    original = parse.ZipFile.open

    def supplied(zipped, name, *args, **kwargs):
        if isinstance(name, ZipInfo) and name.filename == member["name"]:
            assert name.file_size == len(content)
            assert member["bytes"][0] <= len(content) + 1 <= member["bytes"][1]
            return BytesIO(content + b"x")
        return original(zipped, name, *args, **kwargs)

    monkeypatch.setattr(parse.ZipFile, "open", supplied)
    with pytest.raises(BaciError, match=r"^member_bytes$"):
        parse.parse_archive(path, Config.from_mapping(raw), tmp_path)


def test_baci_final_member_bytes_guard(tmp_path, monkeypatch):
    from io import BytesIO
    from zipfile import ZipInfo

    from eii_custodian.publicdata.baci import parse
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    member = raw["members"][0]
    content = MEMBERS[member["name"]].encode()
    member["bytes"] = [len(content), len(content)]
    path = tmp_path / "archive.zip"
    path.write_bytes(archive())
    original_open = parse.ZipFile.open
    original_within = parse.within
    member_sizes = []

    def supplied(zipped, name, *args, **kwargs):
        if isinstance(name, ZipInfo) and name.filename == member["name"]:
            assert name.file_size == len(content)
            return BytesIO(content[:-1])
        return original_open(zipped, name, *args, **kwargs)

    def checked(value, span, reason):
        # The final bounds check must refuse before the size-consistency check.
        if reason == "member_bytes":
            member_sizes.append(value)
        original_within(value, span, reason)

    monkeypatch.setattr(parse.ZipFile, "open", supplied)
    monkeypatch.setattr(parse, "within", checked)
    with pytest.raises(BaciError, match=r"^member_bytes$"):
        parse.parse_archive(path, Config.from_mapping(raw), tmp_path)
    assert member_sizes == [len(content), len(content) - 1]


@pytest.mark.parametrize("kind", ["country", "product"])
def test_baci_dictionary_description_guard(tmp_path, kind):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    members = dict(MEMBERS)
    name = f"invented-{kind}.csv"
    old = "Invented target" if kind == "country" else "Invented product"
    members[name] = members[name].replace(old, " ")
    path = tmp_path / "archive.zip"
    path.write_bytes(archive(members))
    with pytest.raises(BaciError, match=r"^dictionary_description$"):
        parse_archive(path, Config.from_mapping(configuration()), tmp_path)


def test_baci_iso3_guard(tmp_path):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    members = dict(MEMBERS)
    members["invented-country.csv"] = members["invented-country.csv"].replace(
        "Invented target,", "Invented target,xx"
    )
    path = tmp_path / "archive.zip"
    path.write_bytes(archive(members))
    with pytest.raises(BaciError, match=r"^iso3$"):
        parse_archive(path, Config.from_mapping(configuration()), tmp_path)


def test_baci_qatar_key_guard(tmp_path):
    from eii_custodian.publicdata.baci.config import BaciError, Config
    from eii_custodian.publicdata.baci.parse import parse_archive

    raw = configuration()
    raw["qatar_key"] = "00Z"
    path = tmp_path / "archive.zip"
    path.write_bytes(archive())
    with pytest.raises(BaciError, match=r"^qatar_key$"):
        parse_archive(path, Config.from_mapping(raw), tmp_path)


def test_baci_config_text_type_guard():
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    raw["publisher"] = 1
    with pytest.raises(BaciError, match=r"^configuration_type$"):
        Config.from_mapping(raw)


def test_baci_config_strings_type_guard():
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    raw["reviewed_urls"] = tuple(raw["reviewed_urls"])
    with pytest.raises(BaciError, match=r"^configuration_type$"):
        Config.from_mapping(raw)


@pytest.mark.parametrize("value", [(1, 4096), [1], [1, 4096, 4096]])
def test_baci_config_bounds_type_guard(value):
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    raw["archive_bytes"] = value
    with pytest.raises(BaciError, match=r"^configuration_bounds$"):
        Config.from_mapping(raw)


def test_baci_config_confirmed_access_guard():
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    raw["access"] = "unconfirmed"
    with pytest.raises(BaciError, match=r"^access_state$"):
        Config.from_mapping(raw)


def test_baci_config_duplicate_inventory_guard():
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    raw["members"].append(deepcopy(raw["members"][-1]))
    with pytest.raises(BaciError, match=r"^inventory$"):
        Config.from_mapping(raw)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_baci_config_year_coverage_guard(change):
    from eii_custodian.publicdata.baci.config import BaciError, Config

    raw = configuration()
    if change == "missing":
        raw["period_last"] += 1
    else:
        member = deepcopy(raw["members"][-1])
        member["name"] = "invented-other-year.csv"
        if change == "extra":
            member["year"] += 1
        raw["members"].append(member)
    with pytest.raises(BaciError, match=r"^year_coverage$"):
        Config.from_mapping(raw)


def _baci_selected_fixture(cache):
    import json

    from custodian.tests.test_baci_fetch import build

    from eii_custodian.publicdata.baci.contracts import read_selected

    result = build(cache)
    assert result.failure is None
    selected = result.manifests["cepii_baci"]
    assert len(read_selected(cache, selected).trade) == 3
    directory = cache / "cepii_baci"
    manifest = json.loads((directory / f"{selected}.manifest.json").read_text())
    return directory, selected, manifest


def _baci_write_manifest(directory, manifest):
    import json
    from hashlib import sha256

    payload = json.dumps(manifest, sort_keys=True).encode()
    selected = sha256(payload).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(payload)
    return selected


def test_baci_selected_manifest_guard(tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, selected, _ = _baci_selected_fixture(fixture_cache)
    invalid = "invented-selection"
    (directory / f"{invalid}.manifest.json").write_bytes(
        (directory / f"{selected}.manifest.json").read_bytes()
    )
    with pytest.raises(BaciError, match=r"^selected_manifest$"):
        read_selected(fixture_cache, invalid)


def test_baci_manifest_hash_guard(tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, selected, _ = _baci_selected_fixture(fixture_cache)
    path = directory / f"{selected}.manifest.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(BaciError, match=r"^manifest_hash$"):
        read_selected(fixture_cache, selected)


@pytest.mark.parametrize(
    "field,value", [("confirmed", False), ("access", "registration")]
)
def test_baci_manifest_configuration_guard(tmp_path, field, value):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, _, manifest = _baci_selected_fixture(fixture_cache)
    manifest["config"][field] = value
    selected = _baci_write_manifest(directory, manifest)
    with pytest.raises(BaciError, match=r"^manifest_configuration$"):
        read_selected(fixture_cache, selected)


@pytest.mark.parametrize("field", ["kind", "digest"])
def test_baci_terms_fingerprint_guard(tmp_path, field):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, _, manifest = _baci_selected_fixture(fixture_cache)
    if field == "kind":
        manifest["terms_fingerprint_kind"] = "invented-kind"
    else:
        manifest["receipt"]["terms_sha256"] = "invented-digest"
    selected = _baci_write_manifest(directory, manifest)
    with pytest.raises(BaciError, match=r"^terms_fingerprint$"):
        read_selected(fixture_cache, selected)


def test_baci_manifest_retrieval_date_guard(tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, _, manifest = _baci_selected_fixture(fixture_cache)
    manifest["receipt"]["retrieved_utc"] = "2026-1-16T00:00:00Z"
    selected = _baci_write_manifest(directory, manifest)
    with pytest.raises(BaciError, match=r"^retrieval_date$"):
        read_selected(fixture_cache, selected)


@pytest.mark.parametrize("change", ["format", "cache", "receipt"])
def test_baci_archive_hash_guard(tmp_path, change):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, selected, manifest = _baci_selected_fixture(fixture_cache)
    if change == "cache":
        archive_path = directory / f"{manifest['archive_sha256']}.zip"
        archive_path.write_bytes(archive_path.read_bytes() + b"invented-tamper")
    else:
        if change == "format":
            manifest["archive_sha256"] = "invented-digest"
        else:
            manifest["receipt"]["sha256"] = "f" * 64
        selected = _baci_write_manifest(directory, manifest)
    with pytest.raises(BaciError, match=r"^archive_hash$"):
        read_selected(fixture_cache, selected)


@pytest.mark.parametrize(
    "field,value",
    [
        ("publisher", "invented-other"),
        ("landing_url", "invented-other"),
        ("licence_basis", "dataset"),
        ("terms_read_on", "2026-11-15"),
        ("commit_allowed", True),
        ("fetch_host", "invented.invalid"),
        ("bytes", 1),
    ],
)
def test_baci_source_chain_guard(tmp_path, monkeypatch, field, value):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci import contracts
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, _, manifest = _baci_selected_fixture(fixture_cache)
    manifest["receipt"][field] = value
    selected = _baci_write_manifest(directory, manifest)
    if field != "bytes":

        def forbidden(*args, **kwargs):
            raise AssertionError("receipt reconstruction reached past source guard")

        monkeypatch.setattr(contracts, "sidecar_for", forbidden)
    with pytest.raises(BaciError, match=r"^source_chain$"):
        read_selected(fixture_cache, selected)


def test_baci_manifest_archive_checksum_guard(tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, _, manifest = _baci_selected_fixture(fixture_cache)
    manifest["config"]["publisher_sha256"] = "f" * 64
    selected = _baci_write_manifest(directory, manifest)
    with pytest.raises(BaciError, match=r"^archive_checksum$"):
        read_selected(fixture_cache, selected)


@pytest.mark.parametrize(
    "field", ["members", "outputs", "raw", "selected", "excluded", "coverage"]
)
def test_baci_manifest_content_guard(tmp_path, field):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from eii_custodian.publicdata.baci.config import BaciError
    from eii_custodian.publicdata.baci.contracts import read_selected

    directory, _, manifest = _baci_selected_fixture(fixture_cache)
    if field == "members":
        manifest[field][0]["bytes"] += 1
    elif field == "outputs":
        manifest[field]["pub_baci_trade"]["rows"] += 1
    elif field == "coverage":
        manifest[field][0]["selected"] += 1
    else:
        manifest[field] += 1
        if field == "raw":
            manifest["receipt"]["row_count"] = manifest[field]
    selected = _baci_write_manifest(directory, manifest)
    with pytest.raises(BaciError, match=r"^manifest_content$"):
        read_selected(fixture_cache, selected)
