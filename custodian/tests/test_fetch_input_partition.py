"""Fetch input partition: invented bytes, audited opens and durable resume."""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_fetch_fingerprint import (
    _audit_opens,
    _interrupt,
    _rewrite,
    _stub_roots,
)
from custodian.tests.test_fetch_fingerprint import harness as harness
from custodian.tests.test_investment_crosswalk import specimen
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import fingerprint as fp
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.investment_contracts import InvestmentFailure

POST = "review/activity_spine_audits.json"
SHARED = "review/gis_layer_fields.yaml"


def refuse_content_hash(path: Path, *, fresh: bool = False) -> str:
    raise AssertionError("hash_before_symlink_validation")


@contextlib.contextmanager
def audited_reads(
    roots: fp.CodeRoots, monkeypatch: pytest.MonkeyPatch
) -> Iterator[set[str]]:
    """Reuse the fetch audit hook; exclude the fingerprint's own hash reads."""
    state = _audit_opens(roots.publicdata.resolve())
    original = fp._sha256
    seen: set[str] = set()

    def hash_input(path: Path, *, fresh: bool = False) -> str:
        enabled = state["enabled"]
        state["enabled"] = False
        try:
            return original(path, fresh=fresh)
        finally:
            state["enabled"] = enabled

    state["enabled"] = True
    try:
        with monkeypatch.context() as patch:
            patch.setattr(fp, "_sha256", hash_input)
            yield seen
    finally:
        state["enabled"] = False
    for path in state["opened"]:
        name = path.relative_to(roots.publicdata.resolve()).as_posix()
        if fp.INPUT_PARTITION.get(name, "shared fetch-pass") == "post-loop-only":
            raise AssertionError(f"fetch_input_post_loop:{name}")
        seen.add(name)


def test_partition_names_every_tracked_file_once() -> None:
    roots = fp.default_roots()
    names = {p.relative_to(roots.publicdata).as_posix() for p in roots.tracked()}
    assert set(fp.INPUT_PARTITION) == names
    assert set(fp.INPUT_PARTITION.values()) == {
        "per-entry",
        "shared fetch-pass",
        "post-loop-only",
    }
    assert [n for n, group in fp.INPUT_PARTITION.items() if group == "per-entry"] == [
        "sources.yaml"
    ]


def test_post_loop_edit_reuses_every_completed_entry(
    harness: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(POST,))
    _interrupt(harness, code_roots=roots)
    _rewrite(roots.publicdata / POST, "SYN post-loop edit")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.seen == [harness.entries[1].url]
    assert any(line.startswith("REUSE SYN-first ") for line in outcome.lines)


def test_shared_edit_rekeys_every_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custodian.tests.test_build_resume import entry

    roots = _stub_roots(tmp_path, monkeypatch, files=(SHARED,))
    entries = (entry("SYN-a"), entry("SYN-b"))
    before = fp.scan_run(entries, roots, large=False)
    _rewrite(roots.publicdata / SHARED, "SYN shared edit")
    after = fp.scan_run(entries, roots, large=False)
    assert all(before.records[e.key] != after.records[e.key] for e in entries)
    assert not before.closure_intact()


def test_per_entry_edit_rekeys_only_its_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custodian.tests.test_build_resume import entry

    roots = _stub_roots(tmp_path, monkeypatch, files=("sources.yaml",))
    entries = (entry("SYN-a"), entry("SYN-b"))
    before = fp.scan_run(entries, roots, large=False)
    _rewrite(roots.publicdata / "sources.yaml", "SYN changed row")
    changed = (replace(entries[0], title_en="SYN changed row"), entries[1])
    after = fp.scan_run(changed, roots, large=False)
    assert before.records[entries[0].key] != after.records[entries[0].key]
    assert before.records[entries[1].key] == after.records[entries[1].key]


def test_unlisted_tracked_file_is_shared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=("SYN-new.yaml",))
    before = fp._global_input(roots)
    _rewrite(roots.publicdata / "SYN-new.yaml", "SYN new input")
    assert fp._global_input(roots) != before


def test_fetch_pass_reads_only_bound_inputs(
    harness: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(SHARED, POST))
    transport = harness.transport

    def fetch(url: str) -> Any:
        (roots.publicdata / SHARED).read_bytes()
        return transport(url)

    monkeypatch.setattr(harness, "transport", fetch)
    harness.fail = False
    with audited_reads(roots, monkeypatch) as seen:
        outcome = harness.run(code_roots=roots)
    assert outcome.failure is None
    assert SHARED in seen
    assert POST not in seen  # The scanner hashed neither a fetch read nor its bytes.


@pytest.mark.parametrize("opener", ["path", "builtin", "descriptor"])
def test_open_auditor_refuses_a_post_loop_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, opener: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(POST,))
    with pytest.raises(AssertionError, match=f"^fetch_input_post_loop:{POST}$"):
        with audited_reads(roots, monkeypatch):
            path = roots.publicdata / POST
            if opener == "path":
                path.read_bytes()
            elif opener == "builtin":
                with open(path, "rb") as handle:
                    handle.read()
            else:
                fd = os.open(path, os.O_RDONLY)
                os.close(fd)


@pytest.mark.parametrize(
    "name", ["review/country_iso3.csv", "review/landmark_heights.yaml"]
)
def test_dynamic_fdi_targets_remain_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(name,))
    body = b"iso3\nSYN\n" if name.endswith("csv") else b"- iso3: SYN\n"
    (roots.publicdata / name).write_bytes(body)
    crosswalk, _page, item, *_rest = specimen(roots.publicdata / "review")
    item.update(
        target_key="SYN",
        target_resource=Path(name).name,
        target_sha256=sha256_hex(body),
    )
    with audited_reads(roots, monkeypatch) as seen:
        result = crosswalk._mapping(
            item, roots.publicdata / "review", tmp_path / "cache"
        )
    assert not isinstance(result, InvestmentFailure)
    assert name in seen


@pytest.mark.parametrize(
    "reason", ["tracked_publicdata_missing", "untracked_publicdata_file"]
)
def test_partition_keeps_whole_tree_refusals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(POST,))
    if reason == "tracked_publicdata_missing":
        (roots.publicdata / POST).unlink()
    else:
        (roots.publicdata / "SYN-untracked.yaml").write_text("SYN")
    with pytest.raises(fp.FingerprintUnavailable, match=f"^{reason}$"):
        fp._global_input(roots)


@settings(deadline=None)
@given(
    name=st.sampled_from([POST, SHARED, "sources.yaml", "SYN-new.yaml"]),
    before=st.binary(max_size=128),
    after=st.binary(max_size=128),
    reverse=st.booleans(),
)
def test_partition_edit_invariance(
    name: str, before: bytes, after: bytes, reverse: bool
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        publicdata = Path(directory)
        target = publicdata / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(before)
        other = publicdata / "SYN-other.yaml"
        other.write_bytes(b"SYN stable")
        paths = [target, other]
        if reverse:
            paths.reverse()
        roots = replace(
            fp.default_roots(),
            code_root=publicdata,
            publicdata=publicdata,
            tracked=lambda: frozenset(paths),
        )
        first = fp._global_input(roots)
        target.write_bytes(after)
        second = fp._global_input(roots)
        assert (first == second) == (name in {POST, "sources.yaml"} or before == after)


def test_shared_input_same_metadata_is_rehashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(SHARED,))
    path = roots.publicdata / SHARED
    path.write_bytes(b"SYN-a")
    before = fp._global_input(roots)
    old_digest = fp._sha256(path)
    path.write_bytes(b"SYN-b")
    stat = path.stat()
    # Simulate a filesystem tick that gives different bytes identical metadata.
    monkeypatch.setitem(
        fp._HASH_CACHE,
        path,
        (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, old_digest),
    )
    assert fp._global_input(roots) != before


def test_shared_input_outside_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(SHARED,))
    roots = replace(roots, code_root=tmp_path / "code")
    with pytest.raises(
        fp.FingerprintUnavailable, match=r"^tracked_publicdata_outside_root$"
    ):
        fp._global_input(roots)


@pytest.mark.parametrize("name", tuple(fp.INPUT_PARTITION))
def test_each_declared_file_has_its_promised_hash_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(name,))
    before = fp._global_input(roots)
    _rewrite(roots.publicdata / name, "SYN changed bytes")
    assert (fp._global_input(roots) != before) == (
        fp.INPUT_PARTITION[name] == "shared fetch-pass"
    )


@pytest.mark.parametrize("name", [POST, SHARED, "sources.yaml"])
def test_resume_parity_for_partition(
    harness: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    from custodian.tests.test_build_resume import entry

    from eii_custodian.publicdata.fetch.transport import TransportFault

    roots = _stub_roots(tmp_path, monkeypatch, files=(name,))
    harness.entries = (*harness.entries, entry("SYN-fail"))
    harness.fail = False
    transport = harness.transport

    def fetch(url: str) -> Any:
        if url == harness.entries[-1].url:
            harness.seen.append(url)
            raise TransportFault("unreachable", url)
        return transport(url)

    monkeypatch.setattr(harness, "transport", fetch)
    _interrupt(harness, code_roots=roots)
    _rewrite(roots.publicdata / name, "SYN changed input")
    if name == "sources.yaml":
        harness.entries = (
            replace(harness.entries[0], title_en="SYN changed row"),
            *harness.entries[1:],
        )
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is not None and outcome.failure.check == "unreachable"
    expected = {
        POST: [],
        SHARED: [e.url for e in harness.entries[:2]],
        "sources.yaml": [harness.entries[0].url],
    }
    completed_urls = {e.url for e in harness.entries[:2]}
    assert [url for url in harness.seen if url in completed_urls] == expected[name]
    for row in harness.entries[:2]:
        word = "REFETCH" if row.url in harness.seen else "REUSE"
        assert any(line.startswith(f"{word} {row.key} ") for line in outcome.lines)


@pytest.mark.parametrize(
    "link_name,target_name",
    [(POST, SHARED), (SHARED, POST), ("SYN-new.yaml", POST)],
)
def test_partition_refuses_symlink_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_name: str, target_name: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(SHARED, POST))
    link = roots.publicdata / link_name
    if link.exists():
        link.unlink()
    link.symlink_to((roots.publicdata / target_name).resolve())
    roots = replace(
        roots,
        tracked=lambda: frozenset(
            (roots.publicdata / name).resolve() for name in (SHARED, POST, link_name)
        ),
    )
    monkeypatch.setattr(fp, "_sha256", refuse_content_hash)
    with pytest.raises(fp.FingerprintUnavailable, match=r"^publicdata_symlink$"):
        fp._global_input(roots)


def test_partition_refuses_a_symlink_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, files=(SHARED,))
    moved = tmp_path / "SYN-moved-publicdata"
    roots.publicdata.rename(moved)
    roots.publicdata.symlink_to(moved, target_is_directory=True)
    roots = replace(
        roots, tracked=lambda: frozenset({(roots.publicdata / SHARED).resolve()})
    )
    monkeypatch.setattr(fp, "_sha256", refuse_content_hash)
    with pytest.raises(fp.FingerprintUnavailable, match=r"^publicdata_symlink$"):
        fp._global_input(roots)
