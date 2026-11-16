"""Invented closed configuration edges and exact refusal messages."""

from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata.benchmarks import config as cfg

from .test_benchmark_native import native
from .test_benchmarks_fetch import policy


def refusal(caught, expected):
    assert str(caught.value) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.test:443/invented", True),
        ("https://example.test:444/invented", False),
        ("https://example.test/invented", True),
        ("http://example.test/invented", False),
        ("https:///invented", False),
        ("https://invented-user" + "@" + "example.test/invented", False),
        ("https://:invented-password" + "@" + "example.test/invented", False),
        ("https://example.test/invented?invented", False),
        ("https://example.test/invented#invented", False),
    ],
)
def test_safe_url_components(url, expected):
    assert cfg.safe_url(url) is expected


def test_digest_marker_rejected():
    assert cfg.digest_ok("X" * 64) is False


@pytest.mark.parametrize(
    "name",
    [
        "native_columns",
        "reviewed_urls",
        "indicators",
        "dimensions",
        "units",
        "statuses",
        "periods",
        "missing",
        "raw_rows",
        "selected_rows",
        "bytes",
    ],
)
def test_sequence_normalization(name):
    original = native()
    data = asdict(original)
    data[name] = list(data[name])
    result = cfg.Policy.from_mapping(data)
    assert result == original
    assert isinstance(getattr(result, name), tuple)


@pytest.mark.parametrize("name", ["status_map", "last_periods", "members"])
def test_nested_normalization(name):
    original = replace(native(), members=(("invented.csv", 0, 0, 0, 0),))
    data = asdict(original)
    data[name] = [list(v) for v in data[name]]
    assert cfg.Policy.from_mapping(data) == original


@pytest.mark.parametrize(
    "name,value",
    [
        ("url", "https://example.test/invented"),
        ("reviewed_urls", ["https://example.test/invented"]),
    ],
)
def test_pending_single_url_refused(name, value):
    with pytest.raises(ValueError) as caught:
        cfg.Policy.from_mapping({"source_id": "wb_wdi", name: value})
    refusal(caught, "pending_urls")


@pytest.mark.parametrize(
    "access", ["visitor", "registration", "sign_in", "robot_check", "paid_tier"]
)
def test_access_values(access):
    data = asdict(policy())
    data["access"] = access
    assert cfg.Policy.from_mapping(data).access == access


@pytest.mark.parametrize("total,fraction", [(1, 0), (1000, 1000), (1, 1)])
def test_precision_edges(total, fraction):
    data = asdict(policy())
    data.update(total_digits=total, fractional_digits=fraction)
    assert cfg.Policy.from_mapping(data).total_digits == total


def test_zero_total_is_refused_independently():
    data = asdict(policy())
    data.update(total_digits=0, fractional_digits=0)
    with pytest.raises(ValueError) as caught:
        cfg.Policy.from_mapping(data)
    refusal(caught, "precision")


def test_all_statuses_and_empty_member_bounds():
    data = asdict(policy())
    data.update(
        statuses=[
            "historical",
            "publisher_estimate",
            "publisher_forecast",
            "unclassified",
        ],
        members=[["invented.csv", 0, 0, 0, 0]],
    )
    result = cfg.Policy.from_mapping(data)
    assert result.statuses == (
        "historical",
        "publisher_estimate",
        "publisher_forecast",
        "unclassified",
    )
    assert result.members == (("invented.csv", 0, 0, 0, 0),)


def test_default_policy_file():
    assert set(cfg.load_policies()) == {
        "wb_wdi",
        "unctad_fdi",
        "imf_weo",
        "ilostat_qat",
    }


def test_utf8_configuration_under_ascii_locale(tmp_path):
    import locale

    import yaml

    data = {
        source: {"source_id": source, "publisher": "invented-é"}
        for source in ("wb_wdi", "unctad_fdi", "imf_weo", "ilostat_qat")
    }
    path = tmp_path / "invented.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    previous = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, "C")
        assert cfg.load_policies(path)["wb_wdi"].publisher == "invented-é"
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)


def test_default_policy_layout(tmp_path, monkeypatch):
    import yaml

    package = tmp_path / "invented-package"
    directory = package / "publicdata"
    directory.mkdir(parents=True)
    data = {
        source: {"source_id": source}
        for source in ("wb_wdi", "unctad_fdi", "imf_weo", "ilostat_qat")
    }
    (directory / "benchmarks.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(
        cfg,
        "__file__",
        str(package / "src/eii_custodian/publicdata/benchmarks/config.py"),
    )
    assert set(cfg.load_policies()) == {
        "wb_wdi",
        "unctad_fdi",
        "imf_weo",
        "ilostat_qat",
    }
