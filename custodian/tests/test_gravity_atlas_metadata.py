"""Fake opener bounds acquisition, including the production command binding."""

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from typing import ClassVar

import pytest
from custodian.tests.test_gravity_atlas_review import CLOCK, modules

from eii_custodian.publicdata.fetch import transport


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("phase", ["page", "terms"])
@pytest.mark.parametrize("case", ["exact", "overflow", "continuing"])
def test_metadata_acquisition_bound(source, phase, case, tmp_path, monkeypatch):
    m = modules(source)
    raw = m.fixture.configuration()
    limit = (
        raw["archive_bytes"][1]
        if source == "gravity"
        else max(d["archive_bytes"][1] for d in raw["downloads"])
    )
    payload = b"x" * (limit if case == "exact" else limit + 1)
    page = payload if phase == "page" else b"Invented publisher page"
    raw["page_sha256"] = sha256(page).hexdigest()
    terms = m.fixture.PAGE + "-terms"
    raw["reviewed_urls"].append(terms)
    config = m.config.Config.from_mapping(raw)
    entry = replace(m.fixture.entry(), terms_url=terms if phase == "terms" else "")
    reads = []
    closed = []

    class Body:
        headers: ClassVar[dict[str, str]] = {}

        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(self.url)

        def geturl(self):
            return self.url

        def read(self, size=-1):
            reads.append((self.url, size))
            if case == "continuing" and (phase == "page" or self.url == terms):
                assert size >= 0, "unbounded continuing metadata read"
                return b"x" * size
            body = page if self.url == m.fixture.PAGE else payload
            return body if size < 0 else body[:size]

    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *args: SimpleNamespace(
            open=lambda request, **kwargs: Body(request.full_url)
        ),
    )
    # Exercise the production closure, which retains a one-argument transport seam.
    import commands.build_public as command

    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    monkeypatch.setattr(command, "load_" + source + "_config", lambda: config)
    monkeypatch.setattr(command, "utc_now", lambda: CLOCK)
    monkeypatch.setattr(
        command, "open_https_stream", lambda url, **kwargs: m.fixture.stream(url)
    )
    code = command.run(tmp_path, {}, [], sleep=lambda _: None)
    assert all(size == limit + 1 for _, size in reads)
    assert len(reads) == len(closed)
    if case == "exact":
        assert code == 0
        assert list(tmp_path.rglob("*.manifest.json"))
    else:
        assert code == 1
        assert not list(tmp_path.rglob("*.manifest.json"))
        assert not list(tmp_path.rglob("*.zip"))


def test_unbounded_transport_default_unchanged(monkeypatch):
    """All other sources keep the pre-existing no-limit interface."""
    reads = []
    url = "https://www.data.gov.qa/invented-other-page"

    class Body:
        headers: ClassVar[dict[str, str]] = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def geturl(self):
            return url

        def read(self, size=-1):
            reads.append(size)
            return b"invented other source"

    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *args: SimpleNamespace(open=lambda *args, **kwargs: Body()),
    )
    assert transport.open_https(url).body == b"invented other source"
    assert reads == [-1]


def test_metadata_limit_resets_after_exception(monkeypatch):
    from eii_custodian.publicdata.fetch.transport import metadata_limit

    reads = []
    url = "https://www.data.gov.qa/invented-other-page"

    class Body:
        headers: ClassVar[dict[str, str]] = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def geturl(self):
            return url

        def read(self, size=-1):
            reads.append(size)
            return b"invented"

    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *args: SimpleNamespace(open=lambda *args, **kwargs: Body()),
    )
    with pytest.raises(LookupError):
        with metadata_limit(7):
            transport.open_https(url)
            with metadata_limit(3):
                transport.open_https(url)
            transport.open_https(url)
            raise LookupError("invented failure")
    transport.open_https(url)
    assert reads == [8, 4, 8, -1]
