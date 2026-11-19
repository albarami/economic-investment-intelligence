"""Atlas offline dispatch for the two finished downloads."""

from pathlib import Path

import pytest
from custodian.tests.fixtures.atlas.invented import entry, metadata, stream


@pytest.fixture(autouse=True)
def no_real_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    import eii_custodian.publicdata.fetch.transport as transport

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Atlas test attempted a real opener")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)


def test_atlas_complete_archive(tmp_path: Path) -> None:
    from custodian.tests.fixtures.atlas.invented import configuration

    from eii_custodian.publicdata.atlas.config import Config
    from eii_custodian.publicdata.atlas.contracts import read_selected
    from eii_custodian.publicdata.fetch.build import run_build

    outcome = run_build(
        [entry()],
        metadata,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is None
    release = read_selected(tmp_path, outcome.manifests["atlas_complexity"])
    assert len(release.country_product_year) == 1
    assert release.country_product_year[0].finished_measure == "-123456.654321"
    assert release.country_product_year[0].country_code == "00Q"
    assert len(release.country_partner_product_year) == 2
    directions = {
        (row.reporter_code, row.partner_code)
        for row in release.country_partner_product_year
    }
    assert directions == {("00Q", "00A"), ("00A", "00Q")}
    assert release.manifest["finished_only"] is True
    assert release.manifest["excluded"] == 2
    assert release.country_product_year[0].year == 2091
    assert release.manifest["receipt"]["retrieved_utc"].startswith("2026-11-16")
    assert len(release.fact_lineage) == 6


def build(
    tmp_path,
    *,
    config=None,
    source=None,
    byte_transport=metadata,
    stream_transport=stream,
):
    from custodian.tests.fixtures.atlas.invented import configuration

    from eii_custodian.publicdata.atlas.config import Config
    from eii_custodian.publicdata.fetch.build import run_build

    return run_build(
        [entry() if source is None else source],
        byte_transport,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream_transport,
        atlas_config=Config.from_mapping(configuration() if config is None else config),
    )


def test_atlas_pending_access_and_secret(tmp_path: Path) -> None:
    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.fetch.registry import load_registry

    pending = next(
        row for row in load_registry() if row.source_id == "atlas_complexity"
    )

    def forbidden(_):
        raise AssertionError("pending source requested")

    result = run_build(
        [pending], forbidden, tmp_path, lambda: "2026-11-16T00:00:00Z", lambda _: None
    )
    assert any("atlas_metadata_unconfirmed" in line for line in result.lines)
    from custodian.tests.fixtures.atlas.invented import configuration

    config = configuration()
    config["access"] = "paid_tier"
    blocked = build(tmp_path / "paid", config=config, byte_transport=forbidden)
    assert blocked.failure is not None
    assert blocked.failure.check == "access_obstacle"
    marked = build(
        tmp_path / "body",
        byte_transport=lambda url: type(metadata(url))(
            url, b"registration required invented-secret-token", ()
        ),
    )
    assert marked.failure is not None
    assert marked.failure.check == "access_obstacle"
    assert "invented-secret-token" not in repr(marked)


def test_atlas_retries_without_stale_manifest(tmp_path: Path) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from eii_custodian.publicdata.fetch.transport import ATTEMPT_LIMIT

    calls = []

    def chunks():
        yield b"invented-partial"
        raise OSError("invented-secret-token")

    @contextmanager
    def broken(url):
        calls.append(url)
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=None, chunks=chunks()
        )

    failed = build(tmp_path, stream_transport=broken)
    assert failed.failure is not None
    assert failed.failure.check == "network_exhausted"
    assert len(calls) == ATTEMPT_LIMIT
    assert "invented-secret-token" not in repr(failed)


def test_atlas_interrupt_keeps_the_complete_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    from eii_custodian.publicdata.atlas import fetch
    from eii_custodian.publicdata.atlas.contracts import read_selected

    first = build(tmp_path)
    digest = first.manifests["atlas_complexity"]
    manifest = read_selected(tmp_path, digest).manifest
    directory = tmp_path / "atlas_complexity"
    expected = [
        directory / f"{manifest['archives'][grain]['sha256']}.zip"
        for grain in ("country_product_year", "country_partner_product_year")
    ]
    expected.extend(
        directory / f"{manifest['outputs'][table]['sha256']}.jsonl"
        for table in fetch.TABLES
    )
    expected.append(directory / f"{digest}.manifest.json")
    original = fetch._publish
    for boundary in range(1, 10):
        seen = []

        def interrupted(source, destination, receipt, seen=seen, boundary=boundary):
            seen.append(destination)
            if len(seen) == boundary:
                raise OSError("invented-interruption")
            original(source, destination, receipt)

        with monkeypatch.context() as patch:
            patch.setattr(fetch, "_publish", interrupted)
            result = build(tmp_path)
        assert len(seen) == boundary
        assert seen == expected[:boundary]
        assert len(list((directory / "index").glob("*.json"))) == 9
        assert result.failure is not None
        assert result.failure.check == "write_or_stream_failed"
        assert "invented-interruption" not in repr(result)
        assert len(read_selected(tmp_path, digest).country_product_year) == 1


def test_atlas_hosts_and_binding(tmp_path: Path, monkeypatch) -> None:
    from custodian.tests.fixtures.atlas.invented import configuration

    import commands.build_public as build_public
    import eii_custodian.publicdata.fetch.transport as transport
    from eii_custodian.publicdata.atlas.config import Config, safe_url

    def forbidden(*args, **kwargs):
        raise AssertionError("opener constructed")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)
    for address in (
        "https://unlisted.invalid/invented",
        "http://www.data.gov.qa/invented",
        "https://invented-storage.invalid/invented",
    ):
        assert safe_url(address) is False
        with pytest.raises(transport.TransportFault):
            with transport.open_https_stream(address):
                raise AssertionError("unsafe address opened")
    config = Config.from_mapping(configuration())
    observed = []

    def byte(url, *, reviewed_urls, token=""):
        observed.append(reviewed_urls)
        return metadata(url)

    def chunks(url, *, reviewed_urls):
        observed.append(reviewed_urls)
        return stream(url)

    monkeypatch.setattr(build_public, "load_registry", lambda: (entry(),))
    monkeypatch.setattr(build_public, "load_atlas_config", lambda: config)
    monkeypatch.setattr(build_public, "open_https", byte)
    monkeypatch.setattr(build_public, "open_https_stream", chunks)
    assert build_public.run(tmp_path / "bind", {}, [], sleep=lambda _: None) == 1
    assert (
        "snapshot_selection_invalid"
        in (tmp_path / "bind" / "data/public_cache/build-log.json").read_text()
    )
    assert observed == [
        config.reviewed_urls,
        config.reviewed_urls,
        config.reviewed_urls,
    ]
