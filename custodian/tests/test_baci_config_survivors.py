"""Exact configuration guards and boundary values on invented metadata."""

from contextlib import contextmanager

import pytest
import yaml
from custodian.tests.test_baci import configuration

from eii_custodian.publicdata.baci.config import (
    BaciError,
    Config,
    load_config,
    safe_url,
    text,
)


@contextmanager
def refusal(message):
    with pytest.raises(BaciError) as caught:
        yield
    assert str(caught.value) == message


@pytest.mark.parametrize(
    "suffix,expected",
    [
        ("/invented space", False),
        ("/invented!", True),
        (":443/invented", True),
        (":444/invented", False),
        (":bad/invented", False),
    ],
)
def test_baci_url_boundaries(suffix, expected):
    assert safe_url("https://www.data.gov.qa" + suffix) is expected


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("extra", "invented", "configuration_fields"),
        ("publisher", " ", "metadata_missing"),
        ("country_width", True, "configuration_count"),
        ("archive_bytes", [-1, 1], "configuration_bounds"),
        ("confirmed", 1, "configuration_type"),
        ("members", (), "configuration_type"),
        ("config_version", "invented", "method_version"),
        ("access", "invented", "access_state"),
        ("fractional_digits", -1, "decimal_limits"),
        ("country_width", 0, "code_width"),
        ("period_first", 0, "period_bounds"),
        ("page_sha256", "invented", "page_hash"),
        ("reviewed_urls", [], "blocked_host"),
        ("publisher_sha256", "invented", "archive_checksum"),
    ],
)
def test_baci_config_messages(field, value, reason):
    raw = configuration()
    raw[field] = value
    with refusal(reason):
        Config.from_mapping(raw)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("name", "../invented.csv", "member_name"),
        ("kind", "invented", "member_kind"),
        ("year", 2091, "member_year"),
        ("columns", [], "member_schema"),
        (
            "columns",
            {"code": "country_code", "name": "source_name", "iso3": "wrong"},
            "member_schema",
        ),
        ("header", ["code", "name", "wrong"], "member_schema"),
        ("sha256", "invented", "member_checksum"),
    ],
)
def test_baci_member_messages(field, value, reason):
    raw = configuration()
    raw["members"][0][field] = value
    with refusal(reason):
        Config.from_mapping(raw)


def test_baci_member_uppercase_name():
    raw = configuration()
    raw["members"][0]["name"] = "Invented-Country.csv"
    assert Config.from_mapping(raw).members[0].name == "Invented-Country.csv"


@pytest.mark.parametrize("kind", ["country", "product"])
def test_baci_dictionary_presence(kind):
    raw = configuration()
    raw["members"] = [m for m in raw["members"] if m["kind"] != kind]
    with refusal("dictionaries"):
        Config.from_mapping(raw)


@pytest.mark.parametrize(
    "total,fraction,accepted",
    [
        (1, 0, True),
        (1, 1, True),
        (0, 0, False),
    ],
)
def test_baci_precision_boundaries(total, fraction, accepted):
    raw = configuration()
    raw.update(total_digits=total, fractional_digits=fraction)
    if accepted:
        config = Config.from_mapping(raw)
        assert (config.total_digits, config.fractional_digits) == (total, fraction)
    else:
        with refusal("decimal_limits"):
            Config.from_mapping(raw)


@pytest.mark.parametrize("year,accepted", [(9999, True), (10000, False)])
def test_baci_period_boundaries(year, accepted):
    raw = configuration()
    raw.update(period_first=year, period_last=year)
    raw["members"][2]["year"] = year
    if accepted:
        assert Config.from_mapping(raw).period_last == 9999
    else:
        with refusal("period_bounds"):
            Config.from_mapping(raw)


def test_baci_text_default_refuses_empty():
    # Config passes empty explicitly; only a direct call exercises this default.
    with refusal("metadata_missing"):
        text("")


@pytest.mark.parametrize("contents", [None, "["])
def test_baci_load_unreadable(tmp_path, contents):
    path = tmp_path / "invented.yaml"
    if contents is not None:
        path.write_text(contents)
    with refusal("configuration_unreadable"):
        load_config(path)


def test_baci_load_default():
    config = load_config()
    assert config.config_version == "baci-v1"
    assert config.confirmed is False


def test_baci_explicit_read_encoding(tmp_path):
    class OtherDefaultPath(type(tmp_path)):
        def read_text(self, encoding=None, errors=None, newline=None):
            return super().read_text(
                encoding=encoding or "cp037", errors=errors, newline=newline
            )

    path = OtherDefaultPath(tmp_path / "invented.yaml")
    path.write_text(yaml.safe_dump(configuration()), encoding="utf-8")
    assert load_config(path).publisher == "Invented publisher"


def test_baci_load_default_uses_package_root(tmp_path, monkeypatch):
    from eii_custodian.publicdata.baci import config as module

    package = tmp_path / "invented-package"
    metadata = package / "publicdata" / "baci.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(yaml.safe_dump(configuration()), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "__file__",
        str(package / "src/eii_custodian/publicdata/baci/config.py"),
    )
    assert module.load_config().publisher == "Invented publisher"
