"""Invented native layouts; these fixtures assert no publisher schema."""

import csv
import hashlib
import io
import json
import zipfile
from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata.benchmarks.config import Policy
from eii_custodian.publicdata.benchmarks.parse import parse

from .test_benchmarks import row
from .test_benchmarks_fetch import policy


def native(source="wb_wdi", fmt="csv"):
    data = asdict(policy(source))
    data.update(
        format=fmt,
        native_columns=("invented_country", "invented_period", "invented_amount"),
        column_map={
            "country_code": "invented_country",
            "period": "invented_period",
            "value": "invented_amount",
        },
        constants={
            k: v
            for k, v in asdict(row(source)).items()
            if k
            not in {
                "country_code",
                "period",
                "publisher_status",
                "value_status",
                "receipt_sha256",
                "source_row_key",
            }
            and not k.endswith("_value")
        },
        status_map=(("invented-indicator", "2020", "historical"),),
        last_periods=(
            (
                "invented-country",
                "invented-indicator",
                "invented-category",
                "historical",
                "2020",
            ),
        ),
    )
    return Policy.from_mapping(data)


def payload(fmt="csv", value="12.50", country="invented-country", extra=False):
    rows = [
        {
            "invented_country": country,
            "invented_period": "2020",
            "invented_amount": value,
        }
    ]
    if extra:
        rows.append({**rows[0], "invented_country": "invented-excluded"})
    if fmt == "json":
        return json.dumps(rows).encode()
    out = io.StringIO()
    writer = csv.DictWriter(
        out, fieldnames=list(rows[0]), delimiter="\t" if fmt == "tsv" else ","
    )
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


@pytest.mark.parametrize(
    "source,fmt",
    [
        ("wb_wdi", "json"),
        ("unctad_fdi", "csv"),
        ("imf_weo", "tsv"),
        ("ilostat_qat", "csv"),
    ],
)
def test_native_layout_and_missing(source, fmt):
    p = native(source, fmt)
    rows = parse(payload(fmt, "invented-missing"), p, "a" * 64)
    assert rows[0].historical_value is None
    assert rows[0].value_status == "source_missing"
    assert rows[0].source_id == source
    assert parse(payload(fmt), p, "a" * 64)[0].historical_value == "12.50"


@pytest.mark.parametrize(
    "plant", ["stale", "header", "excluded", "status", "duplicate", "missing"]
)
def test_native_refusals(plant):
    p = native()
    body = payload()
    if plant == "stale":
        p = replace(
            p,
            last_periods=(
                (
                    "invented-country",
                    "invented-indicator",
                    "invented-category",
                    "historical",
                    "2021",
                ),
            ),
        )
    elif plant == "header":
        body = body.replace(b"invented_amount", b"invented_other")
    elif plant == "excluded":
        body = payload(value="NaN", country="invented-excluded")
    elif plant == "status":
        p = replace(p, status_map=())
    elif plant == "duplicate":
        body += body.splitlines(keepends=True)[1]
    else:
        body = payload(value="invented-undeclared")
    with pytest.raises(ValueError):
        parse(body, p, "a" * 64)


def archive(body, name="invented.csv"):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(name, body)
    return out.getvalue()


@pytest.mark.parametrize("plant", ["none", "member", "bytes", "rows"])
def test_zip_inventory(plant):
    data = asdict(native())
    data["members"] = (("invented.csv", 1, 2000, 1, 3),)
    p = Policy.from_mapping(data)
    body = payload()
    if plant == "bytes":
        p = replace(p, members=(("invented.csv", 1, 2, 1, 3),))
    elif plant == "rows":
        p = replace(p, members=(("invented.csv", 1, 2000, 2, 3),))
    packed = archive(body, "other.csv" if plant == "member" else "invented.csv")
    if plant == "none":
        assert parse(packed, p, "a" * 64)[0].historical_value == "12.50"
    else:
        with pytest.raises(ValueError):
            parse(packed, p, "a" * 64)


def test_native_coverage_receipt():
    from eii_custodian.publicdata.benchmarks.parse import parse_with_coverage

    result = parse_with_coverage(payload(extra=True), native(), "a" * 64)
    assert result.coverage["raw"] == 2
    assert result.coverage["excluded"] == 1
    assert result.coverage["selected"] == 1
    assert result.coverage["missing"] == 0
    assert result.coverage["members"] == []
    assert result.rows[0].receipt_sha256 == "a" * 64


def test_terms_fingerprint_roundtrip(tmp_path):
    from eii_custodian.publicdata.benchmarks.fetch import terms_fingerprint
    from eii_custodian.publicdata.fetch.registry import load_registry

    entry = next(e for e in load_registry() if e.source_id == "wb_wdi")
    fingerprint = terms_fingerprint(entry)
    assert len(fingerprint) == 64
    assert fingerprint != terms_fingerprint(
        replace(entry, terms_words="invented changed terms")
    )
    assert fingerprint != hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize(
    "source,fmt",
    [
        ("wb_wdi", "json"),
        ("unctad_fdi", "csv"),
        ("imf_weo", "tsv"),
        ("ilostat_qat", "csv"),
    ],
)
def test_native_release_receipt_and_coverage_tamper(tmp_path, source, fmt):
    from contextlib import contextmanager

    from eii_custodian.publicdata.benchmarks.contracts import read_selected
    from eii_custodian.publicdata.benchmarks.fetch import (
        fetch_benchmark,
        terms_fingerprint,
    )
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response, StreamResponse

    p = native(source, fmt)
    entry = replace(
        next(e for e in load_registry() if e.source_id == source),
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        columns=tuple((c, "string") for c in p.native_columns),
    )
    body = payload(fmt, extra=True)

    @contextmanager
    def stream(url):
        yield StreamResponse(url, (), len(body), iter((body,)))

    selected = fetch_benchmark(
        entry,
        p,
        lambda u: Response(u, b"invented-page", ()),
        stream,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
    )
    released = read_selected(tmp_path, source, selected.digest)
    assert released.receipt["terms_sha256"] == terms_fingerprint(entry)
    assert released.receipt["coverage"]["excluded"] == 1
    assert released.receipt["coverage"]["raw"] == 2
    directory = tmp_path / source
    manifest = released.manifest
    manifest["receipt"]["coverage"]["raw"] = 99
    body = json.dumps(manifest).encode()
    digest = hashlib.sha256(body).hexdigest()
    (directory / f"{digest}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError):
        read_selected(tmp_path, source, digest)


def test_native_registry_schema_matches_mapping():
    from eii_custodian.publicdata.benchmarks.fetch import entry_check
    from eii_custodian.publicdata.fetch.registry import load_registry

    p = native()
    entry = replace(
        next(e for e in load_registry() if e.source_id == p.source_id),
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        columns=(("invented-wrong-header", "string"),),
    )
    with pytest.raises(ValueError, match="native_schema"):
        entry_check(entry, p)


def aligned_entry(p):
    from eii_custodian.publicdata.fetch.registry import load_registry

    return replace(
        next(e for e in load_registry() if e.source_id == p.source_id),
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=p.raw_rows[0],
        row_count_max=p.raw_rows[1],
        columns=tuple((c, "string") for c in p.native_columns),
    )


ENTRY_PLANTS = [
    ("id", "source_id", "imf_weo", "source_id"),
    ("key", "key", "invented-other", "source_id"),
    ("commit", "commit_allowed", True, "registry_policy"),
    ("nightly", "nightly_live_fetch", False, "registry_policy"),
    ("publisher", "publisher", "invented-other", "source_chain"),
    ("page", "landing_url", "https://example.test/other", "source_chain"),
    ("url", "url", "https://example.test/other", "source_chain"),
    ("host", "fetch_host", "invented-other.example", "blocked_host"),
    ("tables", "release_tables", (), "release_contract"),
    ("columns", "columns", (), "release_contract"),
    ("raw_min", "row_count_min", 2, "raw_bounds"),
    ("raw_max", "row_count_max", 6, "raw_bounds"),
    ("licence", "licence_id", "", "licence_metadata"),
]


@pytest.mark.parametrize(
    "case,field,value,reason", ENTRY_PLANTS, ids=[p[0] for p in ENTRY_PLANTS]
)
def test_entry_plants(case, field, value, reason):
    from eii_custodian.publicdata.benchmarks.fetch import entry_check

    p = native()
    entry = aligned_entry(p)
    entry_check(entry, p)
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        entry_check(replace(entry, **{field: value}), p)


@pytest.mark.parametrize(
    "value", ["", " ", "pending"], ids=["empty", "blank", "marker"]
)
def test_entry_pending_terms_fields_never_refuse(value):
    """Ruling L-1001: a pending terms field refuses no benchmark entry."""
    from eii_custodian.publicdata.benchmarks.fetch import entry_check

    p = native()
    entry = aligned_entry(p)
    entry_check(replace(entry, terms_words=value), p)
    entry_check(replace(entry, terms_read_on=value), p)


PARSE_PLANTS = [
    ("json_shape", "row_schema"),
    ("native_keys", "native_schema"),
    ("native_type", "native_types"),
    ("pending", "benchmark_metadata_unconfirmed"),
    ("bytes_low", "data_bytes"),
    ("bytes_high", "data_bytes"),
    ("raw_low", "raw_bounds"),
    ("raw_high", "raw_bounds"),
    ("flat_keys", "row_schema"),
    ("source", "source_version"),
    ("version", "source_version"),
    ("unit", "row_mapping"),
    ("status", "row_mapping"),
    ("dimension", "row_mapping"),
    ("period", "row_mapping"),
    ("digits", "benchmark row_schema"),
    ("fraction", "benchmark row_schema"),
    ("selected_low", "selected_bounds"),
    ("selected_high", "selected_bounds"),
]


@pytest.mark.parametrize("plant,reason", PARSE_PLANTS, ids=[p[0] for p in PARSE_PLANTS])
def test_parse_plants(plant, reason):
    p = native(fmt="json") if plant.startswith("native_") else policy()
    if plant in {"raw_high", "selected_high"}:
        p = replace(
            p, **{"raw_rows" if plant == "raw_high" else "selected_rows": (1, 1)}
        )
    body = payload("json") if p.native_columns else json.dumps([asdict(row())]).encode()
    assert len(parse(body, p, "a" * 64)) == 1
    items = json.loads(body)
    if plant == "json_shape":
        body = b"{}"
    elif plant == "native_keys":
        items[0]["invented_extra"] = "invented"
    elif plant == "native_type":
        items[0]["invented_amount"] = 1
    elif plant == "pending":
        p = replace(p, confirmed=False)
    elif plant.startswith("bytes_"):
        p = replace(
            p,
            bytes=(len(body) + 1, len(body) + 2)
            if plant.endswith("low")
            else (1, len(body) - 1),
        )
    elif plant == "raw_low":
        p = replace(p, raw_rows=(2, 3))
    elif plant in {"raw_high", "selected_high"}:
        items.append(asdict(row(status="publisher_forecast")))
    elif plant == "flat_keys":
        items[0].pop("scale")
    elif plant in {"source", "version", "unit", "dimension", "period"}:
        field = {
            "source": "source_id",
            "version": "source_version",
            "dimension": "dimension_key",
        }.get(plant, plant)
        items[0][field] = "wb_wdi" if plant == "source" else "invented-other"
    elif plant == "status":
        p = replace(p, statuses=("publisher_forecast",))
    elif plant == "digits":
        items[0]["historical_value"] = "123456789.1234"
    elif plant == "fraction":
        items[0]["historical_value"] = "1.12345"
    elif plant == "selected_low":
        p = replace(p, selected_rows=(2, 3))
    if plant != "json_shape":
        body = json.dumps(items).encode()
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        parse(body, p, "a" * 64)


@pytest.mark.parametrize("bound", ["bytes", "raw_rows", "selected_rows"])
@pytest.mark.parametrize("edge", ["low", "high", "equal"])
def test_inclusive_parse_bounds(bound, edge):
    body = json.dumps([asdict(row())]).encode()
    count = len(body) if bound == "bytes" else 1
    span = (
        (count, count + 1)
        if edge == "low"
        else (0, count)
        if edge == "high"
        else (count, count)
    )
    p = Policy.from_mapping({**asdict(policy()), bound: span})
    assert parse(body, p, "a" * 64) == (row(),)


def test_zip_content_size_plant():
    import struct

    body = payload()
    packed = archive(body + b"\n")
    p = replace(
        native(), members=(("invented.csv", len(body) + 1, len(body) + 1, 1, 1),)
    )
    assert len(parse(packed, p, "a" * 64)) == 1
    # Truncate the member, retaining its declared uncompressed size and a valid
    # CRC for the remaining content. getinfo still satisfies the unchanged bounds.
    damaged = bytearray(archive(body))
    central = damaged.index(b"PK\x01\x02")
    struct.pack_into("<I", damaged, central + 24, len(body) + 1)
    with zipfile.ZipFile(io.BytesIO(damaged)) as archive_file:
        assert archive_file.getinfo("invented.csv").file_size == len(body) + 1
        assert archive_file.read("invented.csv") == body
    with pytest.raises(ValueError, match=r"^member_bytes$"):
        parse(bytes(damaged), p, "a" * 64)
