"""Gravity offline dispatch. The first failure is a missing dispatch."""

from pathlib import Path

import pytest
from custodian.tests.fixtures.gravity.invented import entry, metadata, stream


@pytest.fixture(autouse=True)
def no_real_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    import eii_custodian.publicdata.fetch.transport as transport

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Gravity test attempted a real opener")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)


def test_gravity_complete_archive(tmp_path: Path) -> None:
    from custodian.tests.fixtures.gravity.invented import configuration

    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.gravity.config import Config
    from eii_custodian.publicdata.gravity.contracts import read_selected

    outcome = run_build(
        [entry()],
        metadata,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        gravity_stream=stream,
        gravity_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is None
    assert outcome.manifests["cepii_gravity"]
    release = read_selected(tmp_path, outcome.manifests["cepii_gravity"])
    assert len(release.bilateral) == 2
    assert {(row.origin_code, row.destination_code) for row in release.bilateral} == {
        ("00Q", "00A"),
        ("00A", "00Q"),
    }
    assert release.bilateral[0].year == 2091
    assert release.manifest["receipt"]["retrieved_utc"].startswith("2026-11-16")
    assert release.source_registry["source_id"] == "cepii_gravity"
    assert len(release.fact_lineage) == 2
    assert release.bilateral[0].distance == "123456.789"
    assert any(row.gdp_destination == "0.0000" for row in release.bilateral)


def build(
    tmp_path,
    *,
    config=None,
    source=None,
    byte_transport=metadata,
    stream_transport=stream,
):
    from custodian.tests.fixtures.gravity.invented import configuration

    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.gravity.config import Config

    return run_build(
        [entry() if source is None else source],
        byte_transport,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        gravity_stream=stream_transport,
        gravity_config=Config.from_mapping(
            configuration() if config is None else config
        ),
    )


def test_gravity_pending_state(tmp_path: Path) -> None:
    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.fetch.registry import load_registry

    pending = next(row for row in load_registry() if row.source_id == "cepii_gravity")

    def forbidden(_):
        raise AssertionError("pending source requested")

    result = run_build(
        [pending], forbidden, tmp_path, lambda: "2026-11-16T00:00:00Z", lambda _: None
    )
    assert not result.manifests
    assert any("gravity_metadata_unconfirmed" in line for line in result.lines)


def test_gravity_repeat_publication_is_idempotent(tmp_path: Path) -> None:
    first = build(tmp_path)
    second = build(tmp_path)
    assert first.failure is None
    assert second.failure is None
    assert first.manifests == second.manifests


def test_gravity_does_not_use_the_baci_stream(tmp_path: Path) -> None:
    from custodian.tests.fixtures.gravity.invented import configuration

    from eii_custodian.publicdata.fetch.build import run_build
    from eii_custodian.publicdata.gravity.config import Config

    result = run_build(
        [entry()],
        metadata,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        stream_transport=stream,
        gravity_config=Config.from_mapping(configuration()),
    )
    assert result.failure is not None
    assert result.failure.check == "stream_transport_missing"


def test_gravity_access_and_terms(tmp_path: Path) -> None:
    from dataclasses import replace

    from custodian.tests.fixtures.gravity.invented import configuration

    for obstacle in ("registration", "sign_in", "robot_check", "paid_tier"):
        config = configuration()
        config["access"] = obstacle
        result = build(
            tmp_path / obstacle,
            config=config,
            byte_transport=lambda _: (_ for _ in ()).throw(
                AssertionError("obstacle requested")
            ),
        )
        assert result.failure is not None
        assert result.failure.check == "access_obstacle"
        assert "invented-secret-token" not in repr(result)
    for index, words in enumerate(
        ("terms to be read", "invented absent terms", "invented prohibitive terms")
    ):
        result = build(
            tmp_path / f"terms-{index}", source=replace(entry(), terms_words=words)
        )
        assert result.failure is None
    marked = build(
        tmp_path / "marker",
        byte_transport=lambda url: type(metadata(url))(
            url, b"Paid tier invented-secret-token", ()
        ),
    )
    assert marked.failure is not None
    assert marked.failure.check == "access_obstacle"
    assert "invented-secret-token" not in repr(marked)


def test_gravity_retries_and_interrupt(tmp_path: Path, monkeypatch) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from eii_custodian.publicdata.fetch.transport import ATTEMPT_LIMIT
    from eii_custodian.publicdata.gravity import fetch
    from eii_custodian.publicdata.gravity.contracts import read_selected

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

    failed = build(tmp_path / "retry", stream_transport=broken)
    assert failed.failure is not None
    assert failed.failure.check == "network_exhausted"
    assert len(calls) == ATTEMPT_LIMIT
    assert "invented-secret-token" not in repr(failed)
    assert not list((tmp_path / "retry" / "cepii_gravity").glob("*.manifest.json"))

    first = build(tmp_path / "keep")
    digest = first.manifests["cepii_gravity"]
    manifest = read_selected(tmp_path / "keep", digest).manifest
    directory = tmp_path / "keep" / "cepii_gravity"
    expected = [directory / f"{manifest['archive_sha256']}.zip"]
    expected.extend(
        directory / f"{manifest['outputs'][table]['sha256']}.jsonl"
        for table in fetch.TABLES
    )
    expected.append(directory / f"{digest}.manifest.json")
    original = fetch._publish
    for boundary in range(1, 5):
        seen = []

        def interrupted(source, destination, receipt, seen=seen, boundary=boundary):
            seen.append(destination)
            if len(seen) == boundary:
                raise OSError("invented-interruption")
            original(source, destination, receipt)

        with monkeypatch.context() as patch:
            patch.setattr(fetch, "_publish", interrupted)
            result = build(tmp_path / "keep")
        assert len(seen) == boundary
        assert seen == expected[:boundary]
        assert len(list((directory / "index").glob("*.json"))) == 4
        assert result.failure is not None
        assert result.failure.check == "write_or_stream_failed"
        assert "invented-interruption" not in repr(result)
        assert len(read_selected(tmp_path / "keep", digest).bilateral) == 2


def test_gravity_hosts_credentials_and_query(monkeypatch) -> None:
    import eii_custodian.publicdata.fetch.transport as transport
    from eii_custodian.publicdata.gravity.config import safe_url

    def forbidden(*args, **kwargs):
        raise AssertionError("opener constructed")

    monkeypatch.setattr(transport.urllib.request, "build_opener", forbidden)
    for address in (
        "https://unlisted.invalid/invented",
        "http://www.data.gov.qa/invented",
        "https://invented-storage.invalid/invented",
        "https://www.data.gov.qa/invented?id=8",
        "https://" + "invented-user" + "@www.data.gov.qa/invented",
    ):
        assert safe_url(address) is False
        with pytest.raises(transport.TransportFault):
            with transport.open_https_stream(address):
                raise AssertionError("unsafe address opened")


def test_gravity_entry_and_command(tmp_path: Path, monkeypatch, capsys) -> None:
    from dataclasses import replace

    from custodian.tests.fixtures.gravity.invented import configuration

    import commands.build_public as build_public
    import eii_custodian.publicdata.fetch.build as module
    from eii_custodian.publicdata.gravity.config import Config

    for field, value, reason in (
        ("licence_basis", "", "licence_basis"),
        ("terms_words", "", "terms_metadata"),
        ("commit_allowed", True, "registry_policy"),
        ("landing_url", "", "page"),
        ("fetch_host", "unlisted.invalid", "blocked_host"),
    ):
        result = build(tmp_path / field, source=replace(entry(), **{field: value}))
        assert result.failure is not None
        assert result.failure.check == reason
    clock = build(tmp_path / "clock")
    assert clock.failure is None
    clock_samples = iter(("2026-11-16T00:00:00Z", "not-a-date"))
    bad_clock_result = __import__(
        "eii_custodian.publicdata.fetch.build", fromlist=["run_build"]
    ).run_build(
        [entry()],
        metadata,
        tmp_path / "bad-clock",
        lambda: next(clock_samples),
        lambda _: None,
        gravity_stream=stream,
        gravity_config=Config.from_mapping(configuration()),
    )
    assert bad_clock_result.failure is not None
    assert bad_clock_result.failure.check == "retrieval_date"

    monkeypatch.setattr(build_public, "load_registry", lambda: (entry(),))
    monkeypatch.setattr(
        module, "load_gravity_config", lambda: Config.from_mapping(configuration())
    )
    monkeypatch.setattr(
        build_public,
        "open_https_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("real stream")),
    )
    assert (
        build_public.run(
            tmp_path / "cmd", {}, [], transport=metadata, sleep=lambda _: None
        )
        == 1
    )
    assert "stream_transport_missing" in capsys.readouterr().out
    assert (
        build_public.run(
            tmp_path / "cmd-ok",
            {},
            [],
            transport=metadata,
            sleep=lambda _: None,
            gravity_stream=stream,
        )
        == 0
    )


def test_gravity_production_binding_is_separate(tmp_path: Path, monkeypatch) -> None:
    from custodian.tests.fixtures.gravity.invented import configuration

    import commands.build_public as build_public
    from eii_custodian.publicdata.gravity.config import Config

    config = Config.from_mapping(configuration())
    observed = []

    def byte(url, *, reviewed_urls, token=""):
        observed.append(reviewed_urls)
        return metadata(url)

    def chunks(url, *, reviewed_urls):
        observed.append(reviewed_urls)
        return stream(url)

    monkeypatch.setattr(build_public, "load_registry", lambda: (entry(),))
    monkeypatch.setattr(build_public, "load_gravity_config", lambda: config)
    monkeypatch.setattr(build_public, "open_https", byte)
    monkeypatch.setattr(build_public, "open_https_stream", chunks)
    assert build_public.run(tmp_path, {}, [], sleep=lambda _: None) == 0
    assert observed == [config.reviewed_urls, config.reviewed_urls]
