"""Access, redirect and secrecy matrix on invented responses."""

from contextlib import contextmanager
from dataclasses import replace

import pytest

from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response, StreamResponse

from .test_benchmarks_fetch import policy


@pytest.mark.parametrize("source", ["wb_wdi", "unctad_fdi", "imf_weo", "ilostat_qat"])
@pytest.mark.parametrize(
    "access", ["registration", "sign_in", "robot_check", "paid_tier"]
)
def test_access_owner_record(tmp_path, source, access):
    from eii_custodian.publicdata.benchmarks.fetch import owner_obstacle

    p = replace(policy(source), access=access)

    def forbidden(*args):
        pytest.fail("access obstacle contacted transport")

    entry = replace(
        next(e for e in load_registry() if e.source_id == source), skip_reason=""
    )
    with pytest.raises(ValueError, match=source):
        fetch_benchmark(entry, p, forbidden, None, tmp_path, forbidden, forbidden)
    report = owner_obstacle(p)
    assert report == {
        "source_id": source,
        "reason": access,
        "evidence_sha256": p.page_sha256,
        "price_amount": None,
        "price_currency": None,
    }


@pytest.mark.parametrize("stage", ["metadata", "stream"])
@pytest.mark.parametrize(
    "url",
    [
        "https://unreviewed.example.test/data",
        "http://example.test/data",
        "https://invented-user:@example.test/data",
        "https://example.test/data?key=invented-key-like-secret",
        "https://example.test/data#invented-key-like-secret",
    ],
)
def test_redirect_secrecy(tmp_path, stage, url):
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
    calls = []

    def metadata(address):
        calls.append(address)
        return Response(url if stage == "metadata" else address, b"invented-page", ())

    @contextmanager
    def stream(address):
        calls.append(address)
        yield StreamResponse(url, (), 2, iter((b"[]",)))

    with pytest.raises(ValueError) as exc:
        fetch_benchmark(
            entry,
            p,
            metadata,
            stream,
            tmp_path,
            lambda: "2026-11-16T00:00:00Z",
            lambda _: None,
        )
    assert p.source_id in str(exc.value)
    assert "invented-key-like-secret" not in str(exc.value)
    assert url not in calls
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize(
    "marker", [b"registration required", b"sign in", b"robot check", b"paid tier"]
)
def test_response_obstacle_source_named(tmp_path, marker):
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
    with pytest.raises(ValueError, match="ilostat_qat access_obstacle"):
        fetch_benchmark(
            entry,
            p,
            lambda u: Response(u, marker, ()),
            lambda _: None,
            tmp_path,
            lambda: "2026-11-16T00:00:00Z",
            lambda _: None,
        )


def test_dispatch_records_owner_obstacle(tmp_path):
    import json

    from eii_custodian.publicdata.fetch.build import run_build

    p = replace(policy(), access="paid_tier")
    entry = replace(
        next(e for e in load_registry() if e.source_id == p.source_id), skip_reason=""
    )
    result = run_build(
        (entry,),
        lambda _: pytest.fail("no network"),
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        benchmark_policies={p.source_id: p},
    )
    assert result.failure is not None
    report = json.loads((tmp_path / "benchmark_owner_report.json").read_text())
    assert report[0]["reason"] == "paid_tier"
