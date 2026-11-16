"""Offline source-specific policies and immutable benchmark releases."""

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from .test_benchmarks import row


def policy(source="ilostat_qat"):
    from eii_custodian.publicdata.benchmarks.config import Policy

    return Policy.from_mapping(
        {
            "source_id": source,
            "confirmed": True,
            "publisher": "invented-publisher",
            "page": "https://example.test/invented-page",
            "page_sha256": hashlib.sha256(b"invented-page").hexdigest(),
            "source_version": "invented-vintage",
            "licence_words": "invented terms",
            "attribution": "invented attribution",
            "access": "visitor",
            "url": "https://example.test/invented-data",
            "reviewed_urls": [
                "https://example.test/invented-page",
                "https://example.test/invented-data",
            ],
            "format": "json",
            "country": "invented-country",
            "indicators": ["invented-indicator"],
            "dimensions": ["invented-category"],
            "units": ["invented-unit"],
            "statuses": ["historical", "publisher_forecast", "unclassified"],
            "raw_rows": [1, 5],
            "selected_rows": [1, 5],
            "bytes": [1, 20000],
            "bound_origin": "invented-evidence",
            "periods": ["2020"],
            "missing": ["invented-missing"],
            "total_digits": 12,
            "fractional_digits": 4,
            "signed": True,
        }
    )


def test_policy_closed_and_pending():
    from eii_custodian.publicdata.benchmarks.config import Policy, load_policies

    assert all(not p.confirmed for p in load_policies().values())
    with pytest.raises(ValueError, match="policy_schema"):
        Policy.from_mapping({**asdict(policy()), "invented_extra": "forbidden"})


@pytest.mark.parametrize(
    "field",
    [
        "publisher",
        "page_sha256",
        "source_version",
        "licence_words",
        "attribution",
        "bound_origin",
        "country",
    ],
)
def test_metadata_required(field):
    from eii_custodian.publicdata.benchmarks.config import Policy

    data = asdict(policy())
    data[field] = ""
    with pytest.raises(ValueError):
        Policy.from_mapping(data)


def test_all_rows_checked_before_selection():
    from eii_custodian.publicdata.benchmarks.parse import parse

    good = asdict(row())
    bad = {**good, "country_code": "invented-excluded", "historical_value": "NaN"}
    with pytest.raises(ValueError):
        parse(json.dumps([good, bad]).encode(), policy(), "a" * 64)


def test_parse_preserves_status_and_missing():
    from eii_custodian.publicdata.benchmarks.parse import parse

    items = [
        asdict(row(status=status))
        for status in ("historical", "publisher_forecast", "unclassified")
    ]
    rows = parse(json.dumps(items).encode(), policy(), "a" * 64)
    assert len(rows) == 3
    assert rows[1].historical_value is None
    assert rows[1].publisher_forecast_value == "12.50"


def test_pending_fetch_never_calls_transport(tmp_path):
    from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark

    def forbidden(*args):
        pytest.fail("pending source called transport")

    with pytest.raises(ValueError, match="metadata_unconfirmed"):
        fetch_benchmark(
            None,
            replace(policy(), confirmed=False),
            forbidden,
            None,
            tmp_path,
            forbidden,
            forbidden,
        )


@pytest.mark.parametrize("source", ["ilostat_qat", "wb_wdi", "imf_weo", "unctad_fdi"])
def test_roundtrip_and_raw_tamper(tmp_path, source):
    from contextlib import contextmanager

    from eii_custodian.publicdata.benchmarks.contracts import read_selected
    from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response, StreamResponse

    p = policy(source)
    entry = next(e for e in load_registry() if e.source_id == source)
    entry = replace(
        entry,
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        period_first="2020",
        period_last="2020",
        columns=(("invented", "string"),),
    )
    body = json.dumps(
        [
            asdict(row(source, status))
            for status in ("historical", "publisher_forecast", "unclassified")
        ]
    ).encode()

    def metadata(url):
        return Response(url, b"invented-page", ())

    @contextmanager
    def stream(url):
        yield StreamResponse(url, (), len(body), iter((body,)))

    result = fetch_benchmark(
        entry,
        p,
        metadata,
        stream,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
    )
    release = read_selected(tmp_path, source, result.digest)
    assert release.rows[0].historical_value == "12.50"
    from eii_custodian.publicdata.benchmarks.contracts import historical_rows

    assert len(release.rows) == 3
    assert historical_rows(release.rows) == (release.rows[0],)
    assert release.receipt["commit_allowed"] is False
    (tmp_path / source / f"{release.receipt['sha256']}.bin").write_bytes(
        b"invented-tamper"
    )
    with pytest.raises(ValueError):
        read_selected(tmp_path, source, result.digest)


def test_build_dispatch_pending_no_transport(tmp_path):
    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.fetch.registry import load_registry

    entries = tuple(
        e
        for e in load_registry()
        if e.source_id in {"wb_wdi", "unctad_fdi", "imf_weo", "ilostat_qat"}
    )
    assert len(entries) == 4

    def forbidden(*args):
        pytest.fail("pending dispatch contacted a source")

    outcome = run_build(
        entries, forbidden, tmp_path, lambda: "2026-11-16T00:00:00Z", forbidden
    )
    assert outcome.failure is None
    assert not outcome.manifests
    assert all(
        any(
            entry.source_id in line and "benchmark_metadata_unconfirmed" in line
            for line in outcome.lines
        )
        for entry in entries
    )


@pytest.mark.parametrize("change", ["receipt", "output", "complete"])
def test_rehashed_manifest_tamper_refused(tmp_path, change):
    from contextlib import contextmanager

    from eii_custodian.publicdata.benchmarks.contracts import read_selected
    from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response, StreamResponse

    p = policy()
    entry = next(e for e in load_registry() if e.source_id == p.source_id)
    entry = replace(
        entry,
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        period_first="2020",
        period_last="2020",
        columns=(("invented", "string"),),
    )
    body = json.dumps([asdict(row())]).encode()

    @contextmanager
    def stream(url):
        yield StreamResponse(url, (), len(body), iter((body,)))

    result = fetch_benchmark(
        entry,
        p,
        lambda url: Response(url, b"invented-page", ()),
        stream,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
    )
    directory = tmp_path / p.source_id
    manifest = json.loads((directory / f"{result.digest}.manifest.json").read_text())
    if change == "receipt":
        manifest["receipt"]["licence_id"] = "invented-tamper"
    elif change == "complete":
        manifest["complete"] = False
    else:
        output = json.dumps([asdict(replace(row(), historical_value="99"))]).encode()
        digest = hashlib.sha256(output).hexdigest()
        (directory / f"{digest}.json").write_bytes(output)
        manifest["output_sha256"] = digest
    raw = json.dumps(manifest).encode()
    digest = hashlib.sha256(raw).hexdigest()
    (directory / f"{digest}.manifest.json").write_bytes(raw)
    with pytest.raises(ValueError):
        read_selected(tmp_path, p.source_id, digest)


def test_stream_exception_is_source_named_and_secret_free(tmp_path):
    from contextlib import contextmanager

    from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response

    p = policy()
    entry = next(e for e in load_registry() if e.source_id == p.source_id)
    entry = replace(
        entry,
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        period_first="2020",
        period_last="2020",
        columns=(("invented", "string"),),
    )

    @contextmanager
    def stream(url):
        raise RuntimeError("invented-secret-sentinel")
        yield

    with pytest.raises(ValueError) as caught:
        fetch_benchmark(
            entry,
            p,
            lambda url: Response(url, b"invented-page", ()),
            stream,
            tmp_path,
            lambda: "2026-11-16T00:00:00Z",
            lambda _: None,
        )
    assert p.source_id in str(caught.value)
    assert "invented-secret-sentinel" not in str(caught.value)
    assert not list(tmp_path.rglob("*.manifest.json"))
