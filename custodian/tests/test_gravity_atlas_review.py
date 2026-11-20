"""Invented regression plants for S2-T25 review findings F1 through F5."""

import importlib
import json
import traceback
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest

from eii_custodian.publicdata.fetch.transport import TransportFault

CLOCK = "2026-11-16T00:00:00Z"


def modules(source):
    base = "eii_custodian.publicdata." + source
    return SimpleNamespace(
        fixture=importlib.import_module(
            "custodian.tests.fixtures." + source + ".invented"
        ),
        config=importlib.import_module(base + ".config"),
        fetch=importlib.import_module(base + ".fetch"),
        contracts=importlib.import_module(base + ".contracts"),
    )


def acquire(source, cache, raw=None, metadata=None, stream=None):
    m = modules(source)
    return getattr(m.fetch, "fetch_" + source)(
        m.fixture.entry(),
        m.config.Config.from_mapping(m.fixture.configuration() if raw is None else raw),
        m.fixture.metadata if metadata is None else metadata,
        m.fixture.stream if stream is None else stream,
        cache,
        lambda: CLOCK,
        lambda _: None,
    )


def rewrite(cache, source, digest, change):
    directory = cache / modules(source).config.SOURCE_ID
    manifest = json.loads((directory / f"{digest}.manifest.json").read_text())
    change(manifest)
    body = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    selected = sha256(body).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(body)
    return selected


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("real opener forbidden")

    monkeypatch.setattr("urllib.request.build_opener", forbidden)


@pytest.mark.parametrize("source", ["baci", "gravity", "atlas"])
@pytest.mark.parametrize("phase", ["conversion", "metadata", "stream"])
def test_traceback_redaction(source, phase, tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    m = modules(source)
    secret = "invented-secret-token"
    address = "https://" + "invented-user:invented-password" + "@invented.invalid/file"
    message = secret + " " + address

    def fail():
        if phase == "conversion":
            raise ValueError(message)
        try:
            raise ValueError(message)
        except ValueError as cause:
            raise TransportFault("blocked_host", address) from cause

    def metadata(_):
        fail()

    @contextmanager
    def stream(_):
        fail()
        yield

    error = getattr(m.config, source.capitalize() + "Error")
    with pytest.raises(error) as caught:
        acquire(
            source,
            fixture_cache,
            metadata=metadata if phase != "stream" else None,
            stream=stream if phase == "stream" else None,
        )
    rendered = "".join(traceback.format_exception(caught.value))
    assert secret not in rendered
    assert address not in rendered
    assert str(caught.value) == (
        "transport_metadata_invalid" if phase == "conversion" else "blocked_host"
    )
    from eii_custodian.publicdata.fetch.build import run_build

    options = {
        source + "_config": m.config.Config.from_mapping(m.fixture.configuration()),
        "stream_transport" if source == "baci" else source + "_stream": stream
        if phase == "stream"
        else m.fixture.stream,
    }
    result = run_build(
        [m.fixture.entry()],
        metadata if phase != "stream" else m.fixture.metadata,
        fixture_cache,
        lambda: CLOCK,
        lambda _: None,
        **options,
    )
    assert secret not in repr(result)
    assert address not in repr(result)
    for path in fixture_cache.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
            assert address.encode() not in path.read_bytes()
    assert not list(fixture_cache.rglob("*.manifest.json"))


@pytest.mark.parametrize("source,grain", [("gravity", 0), ("atlas", 0), ("atlas", 1)])
@pytest.mark.parametrize("case", ["all_old", "missing_final", "final"])
def test_narrower_final_period(source, grain, case, tmp_path):
    m = modules(source)
    raw = m.fixture.configuration()
    raw.update(year_selection="narrower", period_first=2090, period_last=2091)
    member_sets = (
        [dict(m.fixture.MEMBERS)]
        if source == "gravity"
        else [dict(m.fixture.CPY_MEMBERS), dict(m.fixture.CPP_MEMBERS)]
    )
    data_name = (
        raw["members"][-1]["name"]
        if source == "gravity"
        else raw["downloads"][grain]["members"][-1]["name"]
    )
    rows = member_sets[grain][data_name]
    if case == "all_old":
        rows = rows.replace("2091", "2089")
    elif case == "missing_final":
        rows = rows.replace("2091", "2090")
    else:
        rows = rows.replace("2091", "2089", 1)
    member_sets[grain][data_name] = rows
    config = m.config.Config.from_mapping(raw)
    parse = importlib.import_module("eii_custodian.publicdata." + source + ".parse")

    def run():
        if source == "gravity":
            path = tmp_path / "archive.zip"
            path.write_bytes(m.fixture.archive(member_sets[0]))
            return parse.parse_archive(path, config, tmp_path / "out")
        paths = {}
        for download, members, zipper in zip(
            config.downloads,
            member_sets,
            (m.fixture.cpy_archive, m.fixture.cpp_archive),
            strict=True,
        ):
            path = tmp_path / (download.grain + ".zip")
            path.write_bytes(zipper(members))
            paths[download.grain] = path
        return parse.parse_archives(paths, config, tmp_path / "out")

    if case == "final":
        parsed = run()
        selected = (
            parsed
            if source == "gravity"
            else parsed["by_grain"][config.downloads[grain].grain]
        )
        assert selected["excluded_coverage"] == [{"year": 2089, "rows": 1}]
    else:
        with pytest.raises(
            getattr(m.config, source.capitalize() + "Error"), match=r"^year_coverage$"
        ):
            run()
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("grain", [0, 1])
def test_atlas_reader_publisher_checksum(grain, tmp_path):
    m = modules("atlas")
    result = acquire("atlas", tmp_path)

    def tamper(manifest):
        manifest["config"]["downloads"][grain]["publisher_sha256"] = "a" * 64

    selected = rewrite(tmp_path, "atlas", result.digest, tamper)
    with pytest.raises(m.config.AtlasError, match=r"^archive_checksum$"):
        m.contracts.read_selected(tmp_path, selected)


@pytest.mark.parametrize("grain", [0, 1])
@pytest.mark.parametrize("case", ["opposite", "duplicate"])
def test_atlas_member_inventory(grain, case, tmp_path):
    m = modules("atlas")
    raw = m.fixture.configuration()
    target = raw["downloads"][grain]
    if case == "opposite":
        extra = deepcopy(raw["downloads"][1 - grain]["members"][-1])
        target["members"].append(extra)
        target["member_count"] = [4, 4]
    else:
        target["members"][-1]["name"] = target["members"][0]["name"]
    malformed = dict(m.fixture.CPY_MEMBERS if grain == 0 else m.fixture.CPP_MEMBERS)
    if case == "opposite":
        malformed[extra["name"]] = "malformed opposite-grain rows\n"
    zipper = m.fixture.cpy_archive if grain == 0 else m.fixture.cpp_archive
    malformed_archive = zipper(malformed)
    calls = []

    @contextmanager
    def malformed_stream(url):
        calls.append(url)
        yield SimpleNamespace(
            final_url=url,
            hops=(),
            declared_length=len(malformed_archive),
            chunks=iter([malformed_archive]),
        )

    def forbidden(url):
        calls.append(url)
        raise AssertionError("invalid configuration reached fetch")

    with pytest.raises(m.config.AtlasError, match=r"^(finished_grain|inventory)$"):
        acquire("atlas", tmp_path, raw=raw, metadata=forbidden, stream=malformed_stream)
    assert calls == []
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("case", ["ok", "receipt", "unreviewed"])
def test_reviewed_redirect_roundtrip(source, case, tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import allowlist

    m = modules(source)
    raw = m.fixture.configuration()
    host = "invented-mirror.invalid"
    finals = ["https://" + host + "/invented-" + str(i) for i in range(2)]
    original = allowlist.approve

    def approve(url):
        if url in finals:
            return SimpleNamespace(ok=True)
        return original(url)

    monkeypatch.setattr(allowlist, "approve", approve)
    raw["reviewed_urls"].extend(finals)
    urls = (
        [m.fixture.URL]
        if source == "gravity"
        else [m.fixture.CPY_URL, m.fixture.CPP_URL]
    )

    @contextmanager
    def redirected(url):
        with m.fixture.stream(url) as response:
            final = (
                finals[urls.index(url)]
                if case != "unreviewed"
                else "https://unreviewed.invalid/file"
            )
            yield SimpleNamespace(
                final_url=final,
                hops=(final,),
                declared_length=response.declared_length,
                chunks=response.chunks,
            )

    error = getattr(m.config, source.capitalize() + "Error")
    if case == "unreviewed":
        with pytest.raises(error, match=r"^blocked_host$"):
            acquire(source, tmp_path, raw=raw, stream=redirected)
        assert not list(tmp_path.rglob("*.manifest.json"))
        return
    result = acquire(source, tmp_path, raw=raw, stream=redirected)
    if case == "receipt":
        selected = rewrite(
            tmp_path,
            source,
            result.digest,
            lambda manifest: manifest["receipt"].update(fetch_host="www.data.gov.qa"),
        )
        with pytest.raises(error, match=r"^source_chain$"):
            m.contracts.read_selected(tmp_path, selected)
    else:
        release = m.contracts.read_selected(tmp_path, result.digest)
        assert release.manifest["receipt"]["fetch_host"] == host


@pytest.mark.parametrize("source", ["baci", "gravity", "atlas", "boundary"])
def test_refusal_suppression_independently(source):
    from eii_custodian.publicdata.fetch.bounded import _converted_refusal

    message = "invented-sensitive-upstream"

    def callback(reason):
        raise LookupError(reason)

    try:
        try:
            raise ValueError(message)
        except ValueError:
            if source == "boundary":
                _converted_refusal(callback, "fixed_reason")
            else:
                modules(source).fetch._refuse("fixed_reason")
    except Exception as exc:
        assert message not in "".join(traceback.format_exception(exc))
        assert str(exc) == "fixed_reason"
    else:
        raise AssertionError("refusal returned")


@pytest.mark.parametrize("phase", ["conversion", "metadata", "stream"])
def test_shared_conversion_boundary(phase, tmp_path):
    from eii_custodian.publicdata.fetch.bounded import read_metadata, stream_download

    message = "invented-sensitive-upstream"

    def refuse(reason):
        raise LookupError(reason)

    def failed(_):
        if phase == "conversion":
            raise ValueError(message)
        try:
            raise ValueError(message)
        except ValueError as cause:
            raise TransportFault("blocked_host", "") from cause

    with pytest.raises(LookupError) as caught:
        if phase == "stream":
            stream_download(
                "invented",
                failed,
                tmp_path / "target",
                review=lambda _: None,
                byte_bounds=(1, 5),
                sleep=lambda _: None,
                refuse=refuse,
            )
        else:
            read_metadata(
                "invented",
                failed,
                review=lambda _: None,
                max_bytes=5,
                sleep=lambda _: None,
                refuse=refuse,
            )
    assert message not in "".join(traceback.format_exception(caught.value))
