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


def benchmark_release(cache):
    from contextlib import contextmanager

    from eii_custodian.publicdata.benchmarks.contracts import read_selected
    from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response, StreamResponse

    p = policy()
    entry = replace(
        next(e for e in load_registry() if e.source_id == p.source_id),
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        columns=(("invented", "string"),),
    )
    body = json.dumps([asdict(row())]).encode()

    @contextmanager
    def stream(url):
        yield StreamResponse(url, (), len(body), iter((body,)))

    selected = fetch_benchmark(
        entry,
        p,
        lambda u: Response(u, b"invented-page", ()),
        stream,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
    ).digest
    release = read_selected(cache, p.source_id, selected)
    assert release.rows[0].historical_value == "12.50"
    return p.source_id, selected, release.manifest


@pytest.mark.parametrize("body", [b"not json", b"\xff"], ids=["json", "unicode"])
def test_benchmark_decoder(tmp_path, body):
    from eii_custodian.publicdata.benchmarks.contracts import read_selected

    source, _, _ = benchmark_release(tmp_path)
    digest = hashlib.sha256(body).hexdigest()
    (tmp_path / source / f"{digest}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError, match=rf"^{source} selected_manifest_invalid$"):
        read_selected(tmp_path, source, digest)


POLICY_PLANTS = [
    ("source", ("source_id",), "fdi_projects", "source_id"),
    ("extra", ("invented_extra",), True, "policy_schema"),
    ("sequence", ("periods",), "2020", "policy_schema"),
    ("nested_sequence", ("status_map",), "invented", "policy_schema"),
    ("confirmed_type", ("confirmed",), 1, "policy_schema"),
    ("signed_type", ("signed",), 1, "policy_schema"),
    ("pending", ("confirmed",), False, "pending_urls"),
    ("page_hash", ("page_sha256",), "wrong", "page_hash"),
    ("access", ("access",), "owner_page", "access"),
    ("format", ("format",), "parquet", "format"),
    ("span_arity", ("raw_rows",), [1], "bounds"),
    ("span_type", ("raw_rows",), [False, 2], "bounds"),
    ("span_negative", ("selected_rows",), [-1, 2], "bounds"),
    ("span_reversed", ("bytes",), [3, 2], "bounds"),
    ("span_zero", ("bytes",), [0, 0], "bounds"),
    ("digits_zero", ("total_digits",), 0, "precision"),
    ("digits_type", ("total_digits",), True, "precision"),
    ("digits_high", ("total_digits",), 1001, "precision"),
    ("fraction_type", ("fractional_digits",), True, "precision"),
    ("fraction_negative", ("fractional_digits",), -1, "precision"),
    ("fraction_high", ("fractional_digits",), 13, "precision"),
    ("empty_selection", ("indicators",), [], "selection"),
    ("selection_type", ("dimensions",), [1], "selection"),
    ("selection_blank", ("periods",), [""], "selection"),
    ("selection_duplicate", ("units",), ["invented-unit"] * 2, "selection"),
    ("status", ("statuses",), ["invented"], "status_mapping"),
    ("missing_type", ("missing",), [1], "missing_tokens"),
    ("missing_number", ("missing",), ["123"], "missing_tokens"),
    ("missing_zero", ("missing",), ["0.0"], "missing_tokens"),
    ("page_unreviewed", ("page",), "https://invented.invalid/page", "blocked_host"),
    ("url_unreviewed", ("url",), "https://invented.invalid/file", "blocked_host"),
    (
        "columns_duplicate",
        ("native_columns",),
        ("invented_country", "invented_period", "invented_amount", "invented_amount"),
        "native_schema",
    ),
    ("columns_unmapped", ("column_map", "value"), "invented-other", "native_schema"),
    ("targets_extra", ("constants", "invented_extra"), "invented", "native_schema"),
    ("targets_overlap", ("constants", "period"), "2020", "native_schema"),
    ("status_empty", ("status_map",), (), "series_policy"),
    ("last_empty", ("last_periods",), (), "series_policy"),
    (
        "status_arity",
        ("status_map",),
        (("invented-indicator", "2020", "historical", "extra"),),
        "series_policy",
    ),
    (
        "status_unlisted",
        ("status_map",),
        (("invented-indicator", "2020", "invented"),),
        "series_policy",
    ),
    (
        "status_duplicate",
        ("status_map",),
        (("invented-indicator", "2020", "historical"),) * 2,
        "series_policy",
    ),
    ("last_arity", ("last_periods",), (("invented-country",),), "series_policy"),
    (
        "last_status",
        ("last_periods",),
        (
            (
                "invented-country",
                "invented-indicator",
                "invented-category",
                "invented",
                "2020",
            ),
        ),
        "series_policy",
    ),
    (
        "last_period",
        ("last_periods",),
        (
            (
                "invented-country",
                "invented-indicator",
                "invented-category",
                "historical",
                "2021",
            ),
        ),
        "series_policy",
    ),
    (
        "last_duplicate",
        ("last_periods",),
        (
            (
                "invented-country",
                "invented-indicator",
                "invented-category",
                "historical",
                "2020",
            ),
        )
        * 2,
        "series_policy",
    ),
    ("member_arity", ("members",), (("invented.csv", 1, 2, 1),), "member_policy"),
    (
        "member_slash",
        ("members",),
        (("invented/file.csv", 1, 2, 1, 2),),
        "member_policy",
    ),
    (
        "member_backslash",
        ("members",),
        (("invented\\file.csv", 1, 2, 1, 2),),
        "member_policy",
    ),
    ("member_empty", ("members",), (("", 1, 2, 1, 2),), "member_policy"),
    ("member_type", ("members",), ((1, 1, 2, 1, 2),), "member_policy"),
    (
        "member_bound_type",
        ("members",),
        (("invented.csv", False, 2, 1, 2),),
        "member_policy",
    ),
    ("member_bytes", ("members",), (("invented.csv", 3, 2, 1, 2),), "member_policy"),
    ("member_rows", ("members",), (("invented.csv", 1, 2, 3, 2),), "member_policy"),
    (
        "member_duplicate",
        ("members",),
        (("invented.csv", 1, 2, 1, 2),) * 2,
        "member_policy",
    ),
]
POLICY_PLANTS += [
    (f"metadata_{name}", (name,), "", "metadata_required")
    for name in (
        "publisher",
        "page",
        "source_version",
        "licence_words",
        "attribution",
        "bound_origin",
        "country",
    )
]
POLICY_PLANTS += [
    (f"url_{kind}", ("reviewed_urls",), [url], "blocked_host")
    for kind, url in (
        ("query", "https://example.test/file?invented=true"),
        ("userinfo", "https://invented-user:@example.test/file"),
        ("scheme", "http://example.test/file"),
        ("port", "https://example.test:8443/file"),
        ("fragment", "https://example.test/file#invented"),
    )
]


@pytest.mark.parametrize(
    "case,path,value,reason", POLICY_PLANTS, ids=[p[0] for p in POLICY_PLANTS]
)
def test_policy_plants(case, path, value, reason):
    from eii_custodian.publicdata.benchmarks.config import Policy

    from .test_benchmark_native import native

    data = asdict(native())
    assert Policy.from_mapping(data) == native()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        Policy.from_mapping(data)


def test_policy_mapping_type():
    from eii_custodian.publicdata.benchmarks.config import Policy

    assert Policy.from_mapping(asdict(policy())) == policy()
    with pytest.raises(ValueError, match=r"^policy_schema$"):
        Policy.from_mapping(list(asdict(policy()).items()))


def test_policy_value_mapping():
    from eii_custodian.publicdata.benchmarks.config import Policy

    from .test_benchmark_native import native

    data = asdict(native())
    # Another target shares this column so moving value keeps the column inventory.
    data["constants"].pop("source_flags")
    data["column_map"]["source_flags"] = "invented_amount"
    Policy.from_mapping(data)
    data["constants"]["value"] = data["column_map"].pop("value")
    with pytest.raises(ValueError, match=r"^native_schema$"):
        Policy.from_mapping(data)


def test_empty_missing_token_is_not_numeric():
    from eii_custodian.publicdata.benchmarks.config import Policy
    from eii_custodian.publicdata.benchmarks.parse import parse

    from .test_benchmark_native import native, payload

    p = Policy.from_mapping({**asdict(native()), "missing": [""]})
    assert parse(payload(value=""), p, "a" * 64)[0].value_status == "source_missing"


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("keys", "policy_schema"),
        ("source", "source_id"),
        ("yaml", "benchmark configuration_unreadable"),
    ],
    ids=["keys", "source", "yaml"],
)
def test_load_policy_plants(tmp_path, plant, reason):
    import yaml

    from eii_custodian.publicdata.benchmarks.config import load_policies
    from eii_custodian.publicdata.benchmarks.contracts import TABLES

    data = {source: asdict(policy(source)) for source in TABLES}
    path = tmp_path / "invented.yaml"
    path.write_text(yaml.safe_dump(data))
    assert len(load_policies(path)) == len(TABLES)
    if plant == "keys":
        data.pop("wb_wdi")
    elif plant == "source":
        data["wb_wdi"]["source_id"] = "imf_weo"
    path.write_text("[" if plant == "yaml" else yaml.safe_dump(data))
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        load_policies(path)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("selected", "selected_manifest"),
        ("hash", "manifest_hash"),
        ("policy_pending", "manifest_policy"),
        ("policy_source", "manifest_policy"),
        ("policy_access", "manifest_policy"),
        ("raw_digest", "output_hash"),
        ("output_digest", "output_hash"),
        ("publisher", "source_chain"),
        ("commit", "source_chain"),
        ("date", "retrieval_date"),
        ("host", "source_chain"),
        ("missing_key", "ilostat_qat selected_manifest_invalid"),
    ],
    ids=lambda value: value,
)
def test_benchmark_reader_plants(tmp_path, plant, reason):
    from eii_custodian.publicdata.benchmarks.contracts import read_selected

    source, selected, manifest = benchmark_release(tmp_path)
    directory = tmp_path / source
    if plant == "selected":
        selected = "invented"
    elif plant == "hash":
        (directory / f"{selected}.manifest.json").write_bytes(b"invented")
    else:
        if plant == "policy_pending":
            manifest["policy"] = {"source_id": source, "confirmed": False}
        elif plant == "policy_source":
            manifest["policy"]["source_id"] = "wb_wdi"
        elif plant == "policy_access":
            manifest["policy"]["access"] = "registration"
        elif plant == "raw_digest":
            manifest["receipt"]["sha256"] = "xyz"
        elif plant == "output_digest":
            manifest["output_sha256"] = "xyz"
        elif plant == "publisher":
            manifest["receipt"]["publisher"] = "invented-other"
        elif plant == "commit":
            manifest["receipt"]["commit_allowed"] = True
        elif plant == "date":
            manifest["receipt"]["retrieved_utc"] = "2026-1-1T00:00:00Z"
        elif plant == "host":
            manifest["receipt"]["fetch_host"] = "invented-other.example"
        else:
            manifest.pop("complete")
        body = json.dumps(manifest).encode()
        selected = hashlib.sha256(body).hexdigest()
        (directory / f"{selected}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        read_selected(tmp_path, source, selected)
