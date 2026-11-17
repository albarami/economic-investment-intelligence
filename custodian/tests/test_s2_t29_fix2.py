"""Real transport and staged replacement plants for fix confirmation B."""

import io
import ssl
import urllib.request
from dataclasses import replace
from http.client import HTTPMessage, IncompleteRead
from pathlib import Path

import pytest
from custodian.tests.test_s2_t29_fix import award_intake
from custodian.tests.test_s2_t29_pages import BODY, STAMP, page_entry, review
from custodian.tests.test_s2_t29_transport import pin

from eii_custodian.publicdata.fetch import awards, page_records
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    KeyedRequest,
    Response,
    TransportFault,
    open_https,
)


def fake_opener(monkeypatch, *, redirect=None, broken=False):
    """Replace only I/O; drive the redirect handler supplied by real open_https."""
    calls = []
    redirects = []

    class Body(io.BytesIO):
        def __init__(self, body):
            super().__init__(body)
            self.headers = {}

        def geturl(self):
            return calls[-1]

        def read(self, *args):
            if broken:
                raise IncompleteRead(b"SYN-private-upstream-body", 17)
            return super().read(*args)

    def build(guard, *handlers):
        class Opener:
            def open(self, request, *, timeout):
                calls.append(request.full_url)
                if redirect is not None:
                    redirects.append(redirect)
                    guard().redirect_request(
                        request,
                        io.BytesIO(),
                        302,
                        "SYN-redirect",
                        HTTPMessage(),
                        redirect,
                    )
                    pytest.fail("pin guard admitted a redirected send")
                return Body(BODY)

        return Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build)
    return calls, redirects


@pytest.mark.parametrize("source", ["awards", "page"])
@pytest.mark.parametrize(
    "redirect",
    ["https://www.data.qa/syn-other", "https://example.invalid/syn-unpinned"],
)
def test_real_redirect_pin_refusal(tmp_path, monkeypatch, source, redirect):
    # Invented DER is admitted only at the SSL loading seam. validate_pin,
    # verified_context, open_https and _redirect_guard all execute unchanged.
    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", lambda *a, **kw: None)
    calls, redirects = fake_opener(monkeypatch, redirect=redirect)
    if source == "awards":
        entry, declaration, _ = award_intake(tmp_path, monkeypatch)
        declaration["pin"] = {}
        monkeypatch.setattr(awards, "load_pin", lambda *args: pin())
    else:
        entry = replace(
            page_entry(), source_id="schools_private_directory", key="SYN-page"
        )
        monkeypatch.setattr(page_records, "load_declaration", lambda _: review(entry))
        monkeypatch.setattr(page_records, "load_pin", lambda *args: pin())
    sleeps = []
    outcome = run_build((entry,), open_https, tmp_path, lambda: STAMP, sleeps.append)
    assert outcome.failure is not None
    assert outcome.failure.check == "certificate_host_mismatch"
    assert len(calls) == 1
    assert redirects == [redirect]
    assert sleeps == []
    assert not (tmp_path / entry.key).exists()
    assert not list(tmp_path.glob(".page-stage-*"))
    assert "fetch_failed" not in repr(outcome)
    for path in tmp_path.rglob("*.json"):
        assert "fetch_failed" not in path.read_text()


def test_real_incomplete_awards_proof(tmp_path, monkeypatch, capsys):
    entry, _, _ = award_intake(tmp_path, monkeypatch)
    calls, _ = fake_opener(monkeypatch, broken=True)
    sleeps = []
    outcome = run_build((entry,), open_https, tmp_path, lambda: STAMP, sleeps.append)
    assert outcome.failure is None
    indices = list((tmp_path / entry.key / "index").glob("*.json"))
    assert len(indices) == 1
    snapshot = read_snapshot(tmp_path / entry.key, indices[0].stem)
    check = snapshot.sidecar["award_check"]
    assert check["failed_fetches"] == 2
    assert check["incomplete"] is True
    assert check["match_rate"] == "0"
    assert all(item["result"] == "fetch_failed" for item in check["results"])
    assert len(calls) == 2 * ATTEMPT_LIMIT
    assert sleeps == list(BACKOFF_S) * 2
    assert not (tmp_path / entry.key / "proofs").exists()
    diagnostics = repr(outcome) + repr(capsys.readouterr())
    assert "SYN-private-upstream-body" not in diagnostics
    assert "IncompleteRead" not in diagnostics
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"SYN-private-upstream-body" not in path.read_bytes()
            assert b"IncompleteRead" not in path.read_bytes()


def test_real_incomplete_registry_source(tmp_path, monkeypatch):
    entry = next(e for e in load_registry() if e.key == "bnd_geob")
    assert entry.kind == "https_file"
    assert not entry.skip_reason
    calls, _ = fake_opener(monkeypatch, broken=True)
    sleeps = []
    outcome = run_build((entry,), open_https, tmp_path, lambda: STAMP, sleeps.append)
    assert outcome.failure is not None
    assert outcome.failure.check == "unreachable"
    assert outcome.failure.code == 6
    assert calls == [entry.url] * ATTEMPT_LIMIT
    assert sleeps == list(BACKOFF_S)
    assert not (tmp_path / entry.key).exists()
    assert "SYN-private-upstream-body" not in repr(outcome)
    assert "unreachable" in (tmp_path / "build-log.json").read_text()
    for path in tmp_path.rglob("*.json"):
        assert "SYN-private-upstream-body" not in path.read_text()
        assert "IncompleteRead" not in path.read_text()


def test_real_incomplete_keyed_request(monkeypatch):
    from eii_custodian.publicdata.busyness.parse import QUERY_URL

    fake_opener(monkeypatch, broken=True)
    request = KeyedRequest(
        QUERY_URL, "GET", {}, {"BESTTIME_API_KEY_PUBLIC": "SYN-private-key"}
    )
    with pytest.raises(TransportFault) as caught:
        open_https(request)
    assert caught.value.kind == "unreachable"
    assert caught.value.url == QUERY_URL
    assert "SYN-private" not in str(caught.value)
    assert "IncompleteRead" not in str(caught.value)
    assert caught.value.__suppress_context__ is True


def tree_bytes(root):
    """Compare directories, link text and bytes without following any link."""
    return {
        str(path.relative_to(root)): (
            ("link", path.readlink())
            if path.is_symlink()
            else ("directory", None)
            if path.is_dir()
            else ("file", path.read_bytes())
        )
        for path in root.rglob("*")
    }


def existing_page(tmp_path, monkeypatch):
    entry = page_entry()
    monkeypatch.setattr(page_records, "load_declaration", lambda _: review(entry))
    page_records.fetch_page(
        entry,
        lambda url: Response(url, BODY, ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
    )
    return entry


def test_nested_source_symlink_refuses(tmp_path, monkeypatch):
    import shutil

    cache = tmp_path / "cache"
    entry = existing_page(cache, monkeypatch)
    outside = tmp_path / "SYN-outside-source"
    outside.mkdir()
    (outside / "SYN-secret.txt").write_bytes(b"SYN-outside-content")
    nested = cache / entry.key / "SYN-nested"
    nested.mkdir()
    (nested / "link").symlink_to(
        "../../../SYN-outside-source", target_is_directory=True
    )
    before = tree_bytes(cache / entry.key)
    outside_before = tree_bytes(outside)
    copied = []
    original = shutil.copytree

    def copy(*args, **kwargs):
        copied.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", copy)
    outcome = run_build(
        (entry,),
        lambda url: Response(url, BODY, ()),
        cache,
        lambda: STAMP,
        lambda _: None,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "snapshot_path_invalid"
    assert copied == []
    assert tree_bytes(cache / entry.key) == before
    assert tree_bytes(outside) == outside_before
    assert not list(cache.glob(".page-stage-*"))


def test_final_rename_failure_restores_source(tmp_path, monkeypatch):
    entry = existing_page(tmp_path, monkeypatch)
    destination = tmp_path / entry.key
    before = tree_bytes(destination)
    original = Path.rename
    events = []

    def rename(path, target):
        if (
            path.name == entry.key
            and path.parent.name == "cache"
            and target == destination
        ):
            events.append("staged-failed")
            raise OSError("SYN-private-rename-error")
        result = original(path, target)
        if path == destination:
            events.append("backed-up")
        if path.name == "previous" and target == destination:
            events.append("restored")
        return result

    monkeypatch.setattr(Path, "rename", rename)
    outcome = run_build(
        (entry,),
        lambda url: Response(url, BODY.replace(b">7<", b">9<"), ()),
        tmp_path,
        lambda: "2024-02-04T00:00:00Z",
        lambda _: None,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "page_validation_failed"
    assert events == ["backed-up", "staged-failed", "restored"]
    assert destination.is_dir()
    assert tree_bytes(destination) == before
    assert not list(tmp_path.glob(".page-stage-*"))
    assert "SYN-private-rename-error" not in repr(outcome)
