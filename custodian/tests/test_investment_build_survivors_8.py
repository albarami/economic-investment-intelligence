"""Complete compatibility-audit refusals on invented malformed manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from custodian.tests.test_investment_build import (
    RETRIEVED,
    _agency_entry,
    _agency_transport_bodies,
    _batch,
    _run,
)
from custodian.tests.test_investment_build_survivors import _failure

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.investment_contracts import InvestmentFailure


def _manifest(cache: Path, body: bytes, *, tamper: bool = False) -> str:
    """Authenticate the supplied bytes, or deliberately replace that exact file."""
    digest = hashlib.sha256(body).hexdigest()
    source = cache / "SYN-source"
    (source / "manifests").mkdir(parents=True)
    (source / "loadable.json").write_text(
        json.dumps({"manifest_sha256": digest}), encoding="utf-8"
    )
    (source / "manifests" / f"{digest}.json").write_bytes(
        b'{"SYN-replaced": true}' if tamper else body
    )
    return digest


def test_manifest_hash_refusal_preserves_every_field(tmp_path: Path) -> None:
    digest = _manifest(tmp_path, b'{"pages": []}', tamper=True)
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        f"1|SYN-source||hash_mismatch|{digest}|mismatch",
    )


@pytest.mark.parametrize("body", [b"{", b"\xff"], ids=["json", "unicode"])
def test_authenticated_unparseable_manifest_preserves_every_field(
    tmp_path: Path, body: bytes
) -> None:
    digest = _manifest(tmp_path, body)
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        f"1|SYN-source||missing_artifact|{digest}|missing",
    )


@pytest.mark.parametrize("body", [b"[]", b"null"], ids=["list", "null"])
def test_authenticated_nonobject_manifest_preserves_every_field(
    tmp_path: Path, body: bytes
) -> None:
    digest = _manifest(tmp_path, body)
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        f"1|SYN-source||missing_artifact|{digest}|missing",
    )


def test_authenticated_empty_pages_preserves_every_field(tmp_path: Path) -> None:
    _manifest(tmp_path, b'{"pages": []}')
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        "1|SYN-source||missing_artifact|pages|empty",
    )


def test_agency_empty_landing_digest_is_refused_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The helper accepts str, including an empty digest; its final envelope must
    # refuse missing lineage even when the earlier receipt is otherwise valid.
    entry = _agency_entry()
    bodies = _agency_transport_bodies()
    assert _run(tmp_path, monkeypatch, entry, bodies) == 0
    pointer, manifest, _ = _batch(tmp_path, entry.source_id)
    cache = tmp_path / "data/public_cache"
    directory = cache / entry.source_id
    digest = manifest["pages"][0]["sha256"]
    (directory / ".meta.json").write_bytes(
        (directory / f"{digest}.meta.json").read_bytes()
    )
    before = (directory / "loadable.json").read_bytes()
    spec = build.load_source_spec(entry.source_id, url=entry.url)
    assert not isinstance(spec, InvestmentFailure)

    def transport(url: str) -> Response:
        return Response(url, bodies[url], ())

    _failure(
        build._publish_agency(
            entry, spec, cache, "", transport, lambda _: None, lambda: RETRIEVED
        ),
        "1|investqa_pages|https://agency.invalid/|missing_lineage|page_sha256|absent",
    )
    assert (directory / "loadable.json").read_bytes() == before
    assert json.loads(before)["manifest_sha256"] == pointer["manifest_sha256"]
