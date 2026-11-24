"""S2-P39: per-entry fetch-code fingerprints; invented stubs, no public bytes."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from custodian.tests.singles_entries import tender_entry
from custodian.tests.test_build_resume import (
    LATER,
    START,
    Harness,
    entry,
    record,
)
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.fetch import kinds, listing
from eii_custodian.publicdata.fetch.fingerprint import (
    BRANCH_ROOTS,
    EXCLUDED_SCOPES,
    CodeRoots,
    FingerprintUnavailable,
    _git_tracked,
    _ImportScan,
    _sha256,
    closed_encode,
    closure_files,
    default_roots,
    scan_run,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response, TransportFault


def _stub_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    files: tuple[str, ...] = ("syn_data.yaml",),
    brancher: Any = None,
    branch_roots: dict[str, tuple[str, ...]] | None = None,
) -> CodeRoots:
    """A stub code tree whose modules act as machinery and branch adapters."""
    root = tmp_path / "code"
    root.mkdir(exist_ok=True)
    (root / "syn_machinery.py").write_text("SYN_MACHINERY = 1\n")
    (root / "syn_adapter_a.py").write_text("SYN_A = 1\n")
    (root / "syn_adapter_b.py").write_text("SYN_B = 1\n")
    publicdata = tmp_path / "publicdata"
    publicdata.mkdir(exist_ok=True)
    for name in files:
        target = publicdata / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"syn invented {name}\n", encoding="utf-8")
    lock = tmp_path / "uv.lock"
    lock.write_text('name = "syn-dist"\n', encoding="utf-8")
    monkeypatch.syspath_prepend(str(root))
    tracked = frozenset((publicdata / name).resolve() for name in files)
    return CodeRoots(
        code_root=tmp_path.resolve(),
        publicdata=publicdata,
        tracked=lambda: tracked,
        uv_lock=lock,
        runtime_dirs=(root,),
        seeds=("syn_machinery",),
        scope_excludes={},
        branch_roots=branch_roots
        or {
            "a": ("syn_adapter_a",),
            "b": ("syn_adapter_b",),
            "listing": ("syn_adapter_a",),
            "paged_cards": ("syn_adapter_b",),
        },
        brancher=brancher or (lambda e, large: "b" if e.kind == "paged_cards" else "a"),
    )


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    fixture = Harness(tmp_path / "cache")

    def assemble(self: Production) -> tuple[str, ...]:
        assert self.fetcher is not None
        self.fetched = self.fetcher()
        self.lines.extend(self.fetched.lines)
        if self.fetched.failure:
            raise AssemblyError("assembly_fetch_refused")
        fixture.assembled.append(self.seed)
        return ()

    monkeypatch.setattr(Production, "run", assemble)
    return fixture


def _interrupt(harness: Harness, **kwargs: Any) -> None:
    outcome = harness.run(**kwargs)
    assert outcome.failure is not None
    assert outcome.failure.code == 6
    harness.fail = False
    harness.seen.clear()
    harness.stamp = LATER


def _rewrite(path: Path, token: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + f"\n{token}\n", "utf-8")


# --- owner cases ----------------------------------------------------------


def test_changed_registry_row_refetches_only_it(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    harness.entries = (
        replace(harness.entries[0], title_en="SYN changed title"),
        harness.entries[1],
    )
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen
    assert any(line.startswith("REFETCH SYN-first ") for line in outcome.lines)


def test_changed_adapter_refetches_its_entries(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        brancher=lambda e, large: "a" if e.key == "SYN-a" else "b",
    )
    harness.entries = (
        entry("SYN-a"),
        entry("SYN-b"),
        entry("SYN-fail"),
    )
    original = harness.transport

    def failing(url: str) -> Response:
        if url == harness.entries[2].url:
            raise TransportFault("unreachable", url)
        return original(url)

    harness.transport = failing  # type: ignore[method-assign]
    harness.fail = False
    outcome = harness.run(code_roots=roots)
    assert outcome.failure is not None and outcome.failure.code == 6
    harness.seen.clear()
    _rewrite(tmp_path / "code" / "syn_adapter_a.py", "SYN_A = 2")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is not None and outcome.failure.code == 6
    # Branch a is stale: its completed entry refetches; branch b still reuses.
    assert harness.entries[0].url in harness.seen
    assert harness.entries[1].url not in harness.seen
    assert any(line.startswith("REUSE SYN-b ") for line in outcome.lines)
    assert any(line.startswith("REFETCH SYN-a ") for line in outcome.lines)


def test_changed_shared_check_refetches_everything(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    _rewrite(tmp_path / "code" / "syn_machinery.py", "SYN_MACHINERY = 2")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen
    assert any(line.startswith("REFETCH SYN-first ") for line in outcome.lines)


# --- F11 global data input ------------------------------------------------


def test_review_file_edit_makes_museum_entry_refetch(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        files=(
            "syn_data.yaml",
            "review/additions_property_venues.yaml",
            "review/syn_reviewed_urls.yaml",
        ),
    )
    harness.entries = (
        replace(harness.entries[0], key="visits_museum/syn-museum"),
        harness.entries[1],
    )
    _interrupt(harness, code_roots=roots)
    _rewrite(
        tmp_path / "publicdata" / "review" / "additions_property_venues.yaml",
        "syn_missing_measure",
    )
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen


def test_reviewed_urls_config_edit_changes_global_input(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        files=("syn_data.yaml", "review/syn_reviewed_urls.yaml"),
    )
    _interrupt(harness, code_roots=roots)
    _rewrite(
        tmp_path / "publicdata" / "review" / "syn_reviewed_urls.yaml",
        "syn new group",
    )
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen


def test_untracked_publicdata_file_leaves_fingerprint_unavailable(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    (tmp_path / "publicdata" / "syn_untracked.yaml").write_text("x\n")
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen


def test_tracked_publicdata_missing_leaves_fingerprint_unavailable(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    gone = (tmp_path / "publicdata" / "syn_data.yaml").resolve()
    roots = replace(
        roots,
        tracked=lambda: frozenset({gone, gone.parent / "gone.yaml"}),
    )
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"


# --- _git_tracked: the option-fixed listing child --------------------------

_SEGMENT = st.from_regex(r"[A-Za-z0-9_.\- ]{1,12}", fullmatch=True).filter(
    lambda name: name not in {".", ".."}
)


@contextlib.contextmanager
def _listing_child(
    body: bytes, returncode: int = 0
) -> Iterator[list[tuple[tuple[Any, ...], dict[str, Any]]]]:
    """Record each subprocess.run call and answer the given listing bytes."""
    seen: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_run(*popenargs: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen.append((popenargs, kwargs))
        return subprocess.CompletedProcess(popenargs[0], returncode, body, b"")

    with patch.object(subprocess, "run", fake_run):
        yield seen


@settings(deadline=None)
@given(
    names=st.lists(
        st.lists(_SEGMENT, min_size=1, max_size=4).map("/".join), max_size=12
    ),
    trailing=st.booleans(),
)
def test_git_tracked_binds_exactly_the_listed_names(
    names: list[str], trailing: bool
) -> None:
    """Any -z listing resolves to exactly its names, under the fixed argv and
    an environment that cannot carry a credential."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "checkout"
        publicdata = root / "custodian" / "publicdata"
        listing = "\0".join(names) + ("\0" if names and trailing else "")
        with _listing_child(listing.encode("utf-8")) as seen:
            tracked = _git_tracked(root, publicdata)
    assert tracked == frozenset((root / name).resolve() for name in names if name)
    (argv,), kwargs = seen[0]
    assert argv == [
        "git",
        "-C",
        str(root),
        "ls-files",
        "-z",
        "--",
        "custodian/publicdata",
    ]
    assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    assert kwargs["capture_output"] and not kwargs["check"]


@pytest.mark.parametrize("returncode", [1, 128])
def test_git_tracked_refuses_a_failed_listing(tmp_path: Path, returncode: int) -> None:
    root = tmp_path / "checkout"
    with (
        _listing_child(b"", returncode),
        pytest.raises(FingerprintUnavailable, match="tracked_listing_failed"),
    ):
        _git_tracked(root, root / "custodian" / "publicdata")


def test_git_tracked_refuses_a_spawn_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*popenargs: Any, **kwargs: Any) -> None:
        raise OSError("invented spawn failure")

    monkeypatch.setattr(subprocess, "run", fail)
    root = tmp_path / "checkout"
    with pytest.raises(FingerprintUnavailable, match="tracked_listing_failed"):
        _git_tracked(root, root / "custodian" / "publicdata")


def test_git_tracked_refuses_publicdata_outside_root(tmp_path: Path) -> None:
    with pytest.raises(FingerprintUnavailable, match="publicdata_outside_root"):
        _git_tracked(tmp_path, tmp_path.parent / "other")


# --- F8 encoder / fingerprint contents ------------------------------------


def test_unsupported_entry_field_type_is_unavailable(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    harness.entries = (
        replace(harness.entries[0], comtrade_policy=object()),
        harness.entries[1],
    )
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"


def test_constructed_entry_is_inside_the_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    scan = scan_run((entry("SYN-only"),), roots, large=False)
    stored = scan.records["SYN-only"]
    assert stored is not None
    assert stored["schema"] == 2
    assert dict(stored["entry"])["key"] == "SYN-only"
    assert stored["entry"] == closed_encode(entry("SYN-only"))
    for path in scan.union:
        assert path.is_relative_to(roots.code_root)
    with pytest.raises(FingerprintUnavailable):
        closed_encode({"dict": "is not admitted"})


# --- F10 journal ----------------------------------------------------------


@pytest.mark.parametrize("plant", ["missing", "tampered", "wrong_type"])
def test_missing_or_tampered_fingerprint_refetches(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    path = harness.cache / "build-run.json"
    row = record(harness)
    if plant == "missing":
        del row["entries"]["SYN-first"]["fingerprint"]
    elif plant == "tampered":
        row["entries"]["SYN-first"]["fingerprint"]["code"] = "0" * 64
    else:
        row["entries"]["SYN-first"]["fingerprint"] = "not-a-fingerprint"
    path.write_text(json.dumps(row))
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen


# --- F1/F13 computed closure ----------------------------------------------


def _stub_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CodeRoots:
    """A stub package exercising module, function, relative and init edges."""
    # find_spec imports the parent package; drop any earlier test's copy.
    for loaded in [name for name in sys.modules if name.startswith("synpkg")]:
        del sys.modules[loaded]
    root = tmp_path / "tree"
    package = root / "synpkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from . import core\n", "utf-8")
    (package / "core.py").write_text("import os\n", "utf-8")
    (package / "build.py").write_text(
        "import syn_key\n"
        "from . import core\n"
        "def run_build():\n"
        "    import syn_loop\n"
        "def _publish():\n"
        "    import syn_post\n",
        "utf-8",
    )
    (root / "syn_key.py").write_text("K = 1\n", "utf-8")
    (root / "syn_loop.py").write_text("L = 1\n", "utf-8")
    (root / "syn_post.py").write_text("P = 1\n", "utf-8")
    monkeypatch.syspath_prepend(str(root))
    return _stub_roots(tmp_path, monkeypatch)


def test_closure_covers_module_function_relative_and_init_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_tree(tmp_path, monkeypatch)
    files = closure_files(
        roots,
        ("synpkg.build",),
        scoped=True,
    )
    names = {path.name for path in files}
    assert {
        "__init__.py",
        "core.py",
        "build.py",
        "syn_key.py",
        "syn_loop.py",
    } <= names
    # A literal bare-name script import entered the closure with its file.
    key = tmp_path / "tree" / "syn_key.py"
    assert key.resolve() in files
    assert all(path.is_relative_to(roots.code_root) for path in files)


def test_excluded_scope_imports_stay_out_of_the_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_tree(tmp_path, monkeypatch)
    roots = replace(roots, scope_excludes={"synpkg.build": frozenset({"_publish"})})
    files = closure_files(roots, ("synpkg.build",), scoped=True)
    names = {path.name for path in files}
    assert "syn_loop.py" in names
    assert "syn_post.py" not in names


def test_unresolvable_import_outside_stdlib_and_lock_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_tree(tmp_path, monkeypatch)
    bad = tmp_path / "tree" / "synpkg" / "broken.py"
    bad.write_text("import no_such_first_party_module_zzz\n", "utf-8")
    with pytest.raises(FingerprintUnavailable):
        closure_files(roots, ("synpkg.broken",), scoped=False)


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\nimportlib.import_module(name)\n",
        "from importlib import import_module\nimport_module(target)\n",
        "import runpy\nrunpy.run_module('x')\n",
        "__import__('json')\n",
        "exec('x = 1')\n",
        "eval('1 + 1')\n",
        "import importlib.util\nimportlib.util.spec_from_file_location('a','/a')\n",
    ],
)
def test_dynamic_import_forms_refuse_the_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    roots = _stub_tree(tmp_path, monkeypatch)
    bad = tmp_path / "tree" / "synpkg" / "dynamic.py"
    bad.write_text(source, "utf-8")
    with pytest.raises(FingerprintUnavailable):
        closure_files(roots, ("synpkg.dynamic",), scoped=False)


def test_literal_import_module_target_enters_the_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_tree(tmp_path, monkeypatch)
    target = tmp_path / "tree" / "synpkg" / "target.py"
    target.write_text("T = 1\n", "utf-8")
    loader = tmp_path / "tree" / "synpkg" / "loader.py"
    loader.write_text(
        "import importlib\nimportlib.import_module('synpkg.target')\n", "utf-8"
    )
    files = closure_files(roots, ("synpkg.loader",), scoped=False)
    assert target.resolve() in files


def test_unlisted_loaded_module_marks_the_item_unproven(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    smuggled = tmp_path / "code" / "syn_smuggled.py"
    smuggled.write_text("S = 1\n", "utf-8")
    original = harness.transport

    def planting(url: str) -> Response:
        module = types.ModuleType("syn_smuggled")
        module.__file__ = str(smuggled)
        sys.modules["syn_smuggled"] = module
        return original(url)

    harness.transport = planting  # type: ignore[method-assign]
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unproven"
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen


def test_machinery_seed_scope_contains_the_fetch_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real machinery: loop-scope lazy imports in, post-fetch scopes out."""
    roots = default_roots()
    machinery = closure_files(roots, roots.seeds, scoped=True)
    root = roots.code_root
    # A lazy import inside run_build's kept scope is machinery.
    assert (
        root / "custodian/src/eii_custodian/publicdata/fetch/page_records.py"
        in machinery
    )
    # Post-fetch-only scopes keep assembly and heights out.
    assert root / "custodian/src/eii_custodian/publicdata/assembly.py" not in machinery
    assert (
        root / "custodian/src/eii_custodian/publicdata/assembly_adapters.py"
        not in machinery
    )
    # The exclusion list is honest: each named scope is a build.py function.
    source = (root / "custodian/src/eii_custodian/publicdata/fetch/build.py").read_text(
        encoding="utf-8"
    )
    import ast as _ast

    defined = {
        node.name
        for node in _ast.parse(source).body
        if isinstance(node, _ast.FunctionDef)
    }
    assert EXCLUDED_SCOPES <= defined
    assert "scripts/commands/build_public.py" in {
        path.relative_to(root).as_posix() for path in machinery
    }


def test_code_exclusions_are_disjoint_from_every_closure() -> None:
    """Nothing under .venv/.git/node_modules may enter a computed closure."""
    roots = default_roots()
    union = set(closure_files(roots, roots.seeds, scoped=True))
    for seeds in BRANCH_ROOTS.values():
        union |= set(closure_files(roots, seeds, scoped=False))
    for excluded in roots.code_excludes:
        assert not any(path.is_relative_to(excluded) for path in union)


# --- F12 listing sibling fold ---------------------------------------------


def test_listing_sibling_row_edit_refetches_parent(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        brancher=lambda e, large: "listing" if e.key == "places_ovt" else "a",
    )
    parent = replace(
        entry("places_ovt"),
        url="https://www.data.gov.qa/SYN/places_ovt.bin",
    )
    part = replace(
        entry("places_ovt/part-00001"),
        skip_reason="SYN skipped",
    )
    harness.entries = (parent, harness.entries[1], part)

    def fake_listing(row: Entry, reader: Any, registry_entries: Any) -> kinds.Prepared:
        reader(row.url)
        return kinds.Prepared(
            b"SYN invented listing",
            row.url,
            row.fetch_host,
            row.publisher,
            "",
            None,
            "",
            None,
        )

    monkeypatch.setattr(listing, "prepare_listing", fake_listing)
    _interrupt(harness, code_roots=roots)
    harness.entries = (
        parent,
        harness.entries[1],
        replace(part, url="https://www.data.gov.qa/SYN/part-changed.bin"),
    )
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert parent.url in harness.seen
    assert any(line.startswith("REFETCH places_ovt ") for line in outcome.lines)


# --- F4 tenders intake triple ----------------------------------------------
# Joined with decision 0084 (train S2-13): the ordinary run never fetches the
# tender row, so it never reaches the resume plan's intake triple. The first
# test proves that skip on a resume; the second keeps F4's claim on the resume
# plan itself, with the ordinary run's skip of the tender row lifted, the path
# the tender row's own run takes through the same plan.


def test_ordinary_resume_skips_the_tender_row(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch, brancher=lambda e, large: "a")
    harness.entries = (
        tender_entry(),
        harness.entries[1],
    )
    _interrupt(harness, code_roots=roots)
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    tender = [line for line in outcome.lines if line.split()[1:2] == ["tenders_pub"]]
    assert tender == ["SKIP tenders_pub own_run"]
    assert harness.seen == [harness.entries[1].url]


def test_changed_intake_triple_refetches_tenders(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch import awards
    from eii_custodian.publicdata.fetch import build as build_module

    monkeypatch.setattr(build_module, "is_tender_entry", lambda entry: False)
    from eii_custodian.publicdata.singles.tenders import (
        LIST_PATHS,
        ListReading,
        _write_pages,
    )

    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        brancher=lambda e, large: "b" if e.kind == "paged_cards" else "a",
    )
    harness.entries = (
        replace(harness.entries[0], kind="paged_cards", source_id="tenders_pub"),
        harness.entries[1],
    )

    def fetch_pages(source: Entry, sleep: Any, cache: Path | None) -> Any:
        assert cache is not None
        stored = []
        readings = []
        for name, _ in LIST_PATHS:
            for language in ("en", "ar"):
                response = harness.transport(f"{source.url}/{name}/{language}/1")
                stored.append((name, language, 1, response.body))
                readings.append(
                    ListReading(name, language, 1, 1, harness.stamp, harness.stamp)
                )
        _write_pages(cache / source.key, stored, readings)
        return kinds.Prepared(
            b"", source.url, source.fetch_host, source.publisher, "", None, "", None
        )

    monkeypatch.setattr(kinds, "_paged_cards", fetch_pages)
    monkeypatch.setattr(awards, "intake_cutoff", lambda cache, stamp: (None, "", None))
    _interrupt(harness, code_roots=roots)
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert any(line.startswith("REUSE SYN-first ") for line in outcome.lines)
    # The intake moved: the proven pages refetch rather than reuse.
    harness.entries = (harness.entries[0], harness.entries[1])
    row = record(harness)
    row["state"] = "interrupted"
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    monkeypatch.setattr(
        awards,
        "intake_cutoff",
        lambda cache, stamp: ("2026-01-01", "", None),
    )
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert not any(line.startswith("REUSE SYN-first ") for line in outcome.lines)


# --- F5 double resume ------------------------------------------------------


def test_second_resume_reuses_refetched_and_refetches_stale(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        brancher=lambda e, large: (
            "a" if e.key == "SYN-a" else "b" if e.key == "SYN-b" else "a"
        ),
    )
    harness.entries = (
        entry("SYN-a"),
        entry("SYN-b"),
        entry("SYN-fail"),
    )
    original = harness.transport

    def failing(url: str) -> Response:
        if url == harness.entries[2].url:
            raise TransportFault("unreachable", url)
        return original(url)

    harness.transport = failing  # type: ignore[method-assign]
    harness.fail = False
    outcome = harness.run(code_roots=roots)
    assert outcome.failure is not None and outcome.failure.code == 6
    harness.seen.clear()
    # First resume: branch a is stale, b still reuses; the third entry fails.
    _rewrite(tmp_path / "code" / "syn_adapter_a.py", "SYN_A = 2")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is not None and outcome.failure.code == 6
    assert any(line.startswith("REFETCH SYN-a ") for line in outcome.lines)
    assert any(line.startswith("REUSE SYN-b ") for line in outcome.lines)
    harness.seen.clear()
    # Second resume: what the first refetched now reuses; branch b is stale.
    _rewrite(tmp_path / "code" / "syn_adapter_b.py", "SYN_B = 2")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is not None and outcome.failure.code == 6
    assert any(line.startswith("REUSE SYN-a ") for line in outcome.lines)
    assert any(line.startswith("REFETCH SYN-b ") for line in outcome.lines)


# --- F11 audit-hook guard ---------------------------------------------------


def _audit_opens(root: Path) -> Any:
    """Collect files opened under the repository root during a fixture fetch."""
    state = {"enabled": False, "opened": set()}

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event != "open" or not state["enabled"]:
            return
        try:
            path = Path(args[0]).resolve()
        except (OSError, TypeError, ValueError):
            return
        if path.is_relative_to(root):
            state["opened"].add(path)

    sys.addaudithook(hook)
    return state


def _audited_fetch(
    state: dict[str, Any], entry: Entry, transport: Any, cache: Path
) -> None:
    from eii_custodian.publicdata.fetch.build import fetch_entry

    state["enabled"] = True
    try:
        fetch_entry(
            entry,
            transport,
            cache,
            lambda: START,
            lambda seconds: None,
        )
    finally:
        state["enabled"] = False


def test_fixture_fetch_opens_only_declared_repo_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = default_roots()
    tracked = roots.tracked()
    chain = roots.code_root / "data" / "public_chain"
    cache = tmp_path / "cache"
    state = _audit_opens(roots.code_root)

    def declared(path: Path) -> bool:
        return (
            path in tracked or path.is_relative_to(chain) or path.is_relative_to(cache)
        )

    def transport(url: str) -> Response:
        if url.endswith("/exports/json"):
            return Response(url, b'[{"number": 1}]', ())
        return Response(
            url,
            json.dumps(
                {
                    "metas": {
                        "default": {
                            "publisher": "SYN invented publisher",
                            "license": "",
                            "license_url": "",
                            "modified": "",
                        }
                    }
                }
            ).encode(),
            (),
        )

    plain = entry("SYN-file")
    _audited_fetch(state, plain, transport, cache)
    museum = replace(
        entry("visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum"),
        kind="portal_dataset",
        url="https://www.data.gov.qa/SYN/museum/exports/json",
        extension="json",
    )
    _audited_fetch(state, museum, transport, cache)
    parent = replace(entry("places_ovt"), kind="https_file")

    def fake_listing(row: Entry, reader: Any, registry_entries: Any) -> kinds.Prepared:
        reader(row.url)
        return kinds.Prepared(
            b"SYN invented listing",
            row.url,
            row.fetch_host,
            row.publisher,
            "",
            None,
            "",
            None,
        )

    monkeypatch.setattr(listing, "prepare_listing", fake_listing)
    _audited_fetch(state, parent, transport, cache)
    violations = {path for path in state["opened"] if not declared(path)}
    assert violations == set()
    state["opened"].clear()
    # The guard has teeth: an undeclared in-repo read is caught.
    state["enabled"] = True
    (roots.code_root / "uv.lock").read_bytes()
    state["enabled"] = False
    assert roots.code_root / "uv.lock" in state["opened"]


# --- review RV1 planted attacks --------------------------------------------
#
# The independent review's attack tests, planted on the same invented stubs.
# Each asserts the corrected behaviour: a module loaded before begin() is
# bound by hash, a dynamic form anywhere refuses the scan, an unavailable
# proof refetches instead of refusing the build, and the comparison is exact.

FORMS = {
    # control: a static import inside the closure is bound, so the edit
    # refetches through the union hash (must pass)
    "control_static_import": "import syn_hidden\nH = syn_hidden\n",
    "importlib_dunder_import": (
        'import importlib\nH = importlib.__import__("syn_hidden")\n'
    ),
    "getattr_import_module": (
        'import importlib\nH = getattr(importlib, "import_module")("syn_hidden")\n'
    ),
    "bound_alias_of_import_module": (
        'import importlib\nload = importlib.import_module\nH = load("syn_hidden")\n'
    ),
    "sys_modules_lookup": 'import sys\nH = sys.modules["syn_hidden"]\n',
    "pkgutil_resolve_name": 'import pkgutil\nH = pkgutil.resolve_name("syn_hidden")\n',
    "source_file_loader": (
        "from importlib.machinery import SourceFileLoader\n"
        'H = SourceFileLoader("syn_hidden", "syn_hidden.py")\n'
    ),
    # a submodule reached by attribute, imported by a module outside the closure
    "attribute_chain_submodule": "import synhid\nH = synhid.hidden\n",
}


@pytest.mark.parametrize("form", sorted(FORMS))
def test_module_level_load_before_begin_is_bound_by_hash(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    """A module loaded before begin() is hashed even outside the closure.

    A launcher or machinery module's own module-level load runs before
    begin(), so the loaded module is already in sys.modules when the baseline
    is taken; the run-time guard excuses it and, outside the union, the
    static scan never sees it. The loaded-module hash binds it anyway: an
    edit between the runs refetches.
    """
    for name in [
        n for n in sys.modules if n.startswith(("syn_hidden", "synhid", "syn_preload"))
    ]:
        del sys.modules[name]
    roots = _stub_roots(tmp_path, monkeypatch)
    code = tmp_path / "code"
    (code / "syn_hidden.py").write_text("PACING_SECONDS = 1\n", "utf-8")
    (code / "synhid").mkdir()
    (code / "synhid" / "__init__.py").write_text("", "utf-8")
    (code / "synhid" / "hidden.py").write_text("PACING_SECONDS = 1\n", "utf-8")
    if form == "control_static_import":
        (code / "syn_machinery.py").write_text(FORMS[form], "utf-8")
        preload = "PRELOADED = 1\n"
    else:
        # Each dynamic form lives in syn_preload, a module outside the
        # closure that is loaded before begin().
        preload = FORMS[form]
    (code / "syn_preload.py").write_text(preload, "utf-8")
    edited = (
        code / "synhid" / "hidden.py"
        if form == "attribute_chain_submodule"
        else code / "syn_hidden.py"
    )
    importlib.import_module("syn_hidden")
    importlib.import_module("synhid.hidden")
    importlib.import_module("syn_preload")
    _interrupt(harness, code_roots=roots)
    assert "fingerprint" in record(harness)["entries"]["SYN-first"]
    _rewrite(edited, "PACING_SECONDS = 0")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    stale = [line for line in outcome.lines if line.startswith("REUSE SYN-first ")]
    assert not stale, f"stale reuse after editing {edited.name}: {stale}"
    assert harness.entries[0].url in harness.seen


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\nimportlib.__import__('x')\n",
        "import importlib\nimportlib.reload\n",
        "from importlib.machinery import SourceFileLoader\nSourceFileLoader('a','b')\n",
        "import importlib.util\nimportlib.util.module_from_spec\n",
        "import importlib.util\nimportlib.util.spec_from_loader\n",
        "import pkgutil\npkgutil.resolve_name('x')\n",
        "import zipimport\nzipimport.zipimporter\n",
        "import sys\nsys.modules['x']\n",
        "import sys\nvalue = sys.modules.get('x')\n",
        "import importlib\ngetattr(importlib, 'import_module')('x')\n",
        "import builtins\ngetattr(builtins, 'eval')('1')\n",
        "import sys\ngetattr(sys, 'modules')['x']\n",
        "import importlib\nload = importlib.import_module\nload('x')\n",
        "from importlib import import_module\nload = import_module\n",
        "import runpy\nload = runpy.run_module\n",
    ],
)
def test_reference_level_dynamic_forms_refuse_the_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    """Each dynamic form refuses on any reference, not only a call."""
    roots = _stub_tree(tmp_path, monkeypatch)
    bad = tmp_path / "tree" / "synpkg" / "dynamic.py"
    bad.write_text(source, "utf-8")
    with pytest.raises(FingerprintUnavailable):
        closure_files(roots, ("synpkg.dynamic",), scoped=False)


def test_launcher_module_is_bound_by_the_loaded_hash() -> None:
    """scripts/commands/main.py calls build_public.run(root, environ, args).

    It chooses the transport seam, the environment mapping and the root that
    the whole fetch runs under. It is loaded before begin(), so it is bound
    through the loaded-module hash, not the closure.
    """
    roots = default_roots()
    sys.path.insert(0, str(roots.code_root / "scripts"))
    try:
        import commands.main  # noqa: F401  (as ./eii loads it)

        scan = scan_run((), roots, large=True)
    finally:
        sys.path.pop(0)
    launcher = roots.code_root / "scripts/commands/main.py"
    assert launcher.is_file()
    assert launcher in scan.baseline
    assert not scan.unexpected_loaded()  # the guard excuses it as baseline
    # Bound through the loaded-module hash: the union holds every bound file.
    assert launcher in scan.union
    assert launcher in scan.hashes
    # The eii shell launcher is a named hashed file of every record.
    assert roots.code_root / "eii" in scan.hashes


def test_loaded_digest_and_named_file_are_in_each_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    launcher = tmp_path / "code" / "syn_launcher.sh"
    launcher.write_text("#!/bin/sh\necho syn\n", "utf-8")
    roots = replace(roots, named_files={"syn_launcher": launcher})
    scan = scan_run((entry("SYN-only"),), roots, large=False)
    stored = scan.records["SYN-only"]
    assert stored is not None
    assert stored["named_files"] == {"syn_launcher": _sha256(launcher.resolve())}
    assert launcher.resolve() in scan.hashes
    assert isinstance(stored["loaded"], str)
    assert len(stored["loaded"]) == 64


def test_missing_named_file_leaves_every_item_unproven(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    roots = replace(roots, named_files={"syn_gone": tmp_path / "gone"})
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"


def test_ordinary_run_is_not_refused_by_the_resume_proof(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-resume seeded build still fetches when the proof is unavailable.

    A refused form, an unresolvable import or an unreadable module leaves the
    whole scan unavailable; the build fetches anyway and every item is marked
    resume_fingerprint_unavailable.
    """
    roots = _stub_roots(tmp_path, monkeypatch)
    (tmp_path / "code" / "syn_machinery.py").write_text('X = eval("1")\n', "utf-8")
    outcome = harness.run(code_roots=roots)
    assert harness.seen, f"nothing fetched; failure={outcome.failure}"
    assert outcome.failure is not None and outcome.failure.code == 6
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"


def test_resume_run_marks_and_refetches_when_the_proof_is_unavailable(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On resume an unavailable proof refetches every entry, never reuses."""
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    _rewrite(tmp_path / "code" / "syn_machinery.py", 'X = eval("1")')
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert harness.seen == [source.url for source in harness.entries]
    assert not [line for line in outcome.lines if line.startswith("REUSE ")]
    item = record(harness)["entries"]["SYN-first"]
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"


@pytest.mark.parametrize("version", ["2", 2.0, True, None, 3, 1])
def test_journal_version_mixups_never_reuse(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: Any
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    row = record(harness)
    if version is None:
        del row["version"]
    else:
        row["version"] = version
    # a version-1 shaped item: no fingerprint
    del row["entries"]["SYN-first"]["fingerprint"]
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    outcome = harness.run(resume=True, code_roots=roots)
    assert not [line for line in outcome.lines if line.startswith("REUSE ")]
    assert harness.entries[0].url in harness.seen or outcome.failure is not None


@pytest.mark.parametrize("plant", ["bytes", "receipt"])
def test_receipt_rehash_still_gates_reuse_with_a_matching_fingerprint(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    names = sorted(item["proofs"][0]["files"])
    target = next(
        harness.cache / n
        for n in names
        if (plant == "receipt") == ("receipt" in n or n.endswith(".meta.json"))
    )
    target.write_bytes(target.read_bytes() + b" ")
    outcome = harness.run(resume=True, code_roots=roots)
    assert not [line for line in outcome.lines if line.startswith("REUSE SYN-first")]
    assert harness.entries[0].url in harness.seen


def test_fingerprint_comparison_is_type_exact(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """true/1/1.0 are different canonical rows; Python == treats them as equal."""
    roots = _stub_roots(tmp_path, monkeypatch)
    _interrupt(harness, code_roots=roots)
    row = record(harness)
    changed = 0

    def swap(value: Any) -> Any:
        nonlocal changed
        if isinstance(value, list):
            return [swap(item) for item in value]
        if value is True or value is False:
            changed += 1
            return int(value)
        return value

    stored = row["entries"]["SYN-first"]["fingerprint"]
    stored["entry"] = swap(stored["entry"])
    assert changed, "fixture entry has no boolean field"
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    harness.run(resume=True, code_roots=roots)
    assert harness.entries[0].url in harness.seen


def test_same_size_same_mtime_edit_is_rehashed(tmp_path: Path) -> None:
    """The file-hash cache key holds ctime too: a copy that preserves times
    still changes it, so a same-size, same-mtime rewrite is rehashed."""
    path = tmp_path / "syn_module.py"
    path.write_text("A = 1\n", "utf-8")
    first = _sha256(path)
    stat = path.stat()
    # Cross the filesystem's ctime granularity so the metadata change lands.
    time.sleep(0.05)
    path.write_text("B = 2\n", "utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert _sha256(path) != first


# --- review CF2 planted attacks --------------------------------------------
#
# The confirmation-2 review's attack tests, planted on the same invented
# stubs. Every scripts/ module loaded before begin() is bound by hash on
# the real roots, each missed dynamic form refuses the scan, and the held
# attacks keep their assertions. The two runtime-dirs boundary probes are
# stated limits of decision 0081 item 4.


def _clean_syn_modules() -> None:
    for name in [
        n
        for n in sys.modules
        if n.startswith(("syn_hidden", "synhid", "syn_pre", "syn_side"))
    ]:
        del sys.modules[name]


def test_scripts_modules_loaded_before_begin_are_bound_on_the_real_roots() -> None:
    """The nine scripts/ modules commands.main loads pre-begin are hashed.

    preflight_cmd.py, up_cmd.py and database.py import them at module level,
    so they run in the fetch process before begin(); the loaded-module
    digest binds each of them like the launcher and assembly modules.
    """
    roots = default_roots()
    sys.path.insert(0, str(roots.code_root / "scripts"))
    try:
        import commands.main  # noqa: F401  (as ./eii loads it)

        scan = scan_run((), roots, large=True)
    finally:
        sys.path.pop(0)
    wanted = [
        roots.code_root / "scripts" / name
        for name in (
            "preflight.py",
            "preflight_database.py",
            "preflight_proc.py",
            "preflight_rows.py",
            "preflight_store.py",
            "pack_anchors.py",
            "versions_inputs.py",
            "versions_record.py",
            "versions_tools.py",
        )
    ]
    loaded = {
        Path(m.__file__).resolve()
        for m in list(sys.modules.values())
        if getattr(m, "__file__", None)
    }
    missing = [p.name for p in wanted if p not in loaded]
    assert not missing, f"not loaded by import commands.main: {missing}"
    for path in wanted:
        assert path in scan.baseline, f"{path.name} outside the baseline"
        assert path in scan.hashes, f"{path.name} bound by no digest"
        assert path in scan.union


def test_production_shape_loads_no_checkout_module_outside_the_bound_set() -> None:
    """Under the production shape (`python -I`, `import commands.main`,
    `scan_run` on `default_roots()`), every loaded module file under
    `code_root` and outside the excluded roots is in `scan.hashes`: the set
    of loaded checkout modules outside the bound set is empty. This is the
    tracked proof of decision 0081 item 4's stated-limit premise; a
    `python -I` interpreter holds only `scripts/` and the `src` roots, so a
    checkout module loaded outside the runtime roots would show up here.
    """
    roots = default_roots()
    code = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, sys.argv[1] + "/scripts")
        import commands.main
        from eii_custodian.publicdata.fetch import fingerprint as fp
        roots = fp.default_roots()
        scan = fp.scan_run((), roots, large=True)
        unbound = []
        for module in list(sys.modules.values()):
            file = getattr(module, "__file__", None)
            if not file:
                continue
            path = Path(file).resolve()
            if (path.is_relative_to(roots.code_root)
                    and not any(path.is_relative_to(x) for x in roots.code_excludes)
                    and path not in scan.hashes):
                unbound.append(str(path.relative_to(roots.code_root)))
        print(sorted(unbound))
        """
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code, str(roots.code_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-400:]
    assert done.stdout.strip() == "[]", done.stdout


# Drives the real seeded run_build (`python -I`, `import commands.main`, the
# real registry and roots) up to the fetch loop. The stubbed loop applies the
# action of argv[3], prints the paths unexpected_loaded() would flag, the
# guard results and _fingerprint's refusal for the first https_file entry,
# then returns a failure without fetching.
_SEEDED_LOOP_PROBE = textwrap.dedent(
    """
    import json, sys
    from pathlib import Path
    root, cache, action = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    sys.path[:0] = [str(root / d) for d in (
        "scripts", "custodian/src", "core/src", "product/src", "gateway/src")]
    import commands.main
    import eii_custodian
    from eii_custodian.publicdata.fetch import build, resume
    from eii_custodian.publicdata.fetch import fingerprint as fp
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import TransportFault
    from eii_custodian.publicdata.method_pin_config import load_generation_config
    assert Path(eii_custodian.__file__).resolve().is_relative_to(root)
    runs = []
    begin = resume.RunRecord.begin.__func__
    def capture(cls, *a, **k):
        runs.append(begin(cls, *a, **k))
        return runs[-1]
    resume.RunRecord.begin = classmethod(capture)
    entries = tuple(e for e in load_registry()
                    if e.kind not in {"cdse_backup", "company_web"})
    first = next(e for e in entries if e.kind == "https_file" and not e.skip_reason)
    seeded = build.run_build
    def loop(*a, **k):
        if not k.get("_fetch_only"):
            return seeded(*a, **k)
        if action.startswith("tamper:"):
            with (root / action[7:]).open("a") as handle:
                handle.write("# changed after begin\\n")
        elif action == "plant":
            import syn_late_probe
        scan = runs[0].scan
        flagged = sorted(p.relative_to(root).as_posix()
                         for p in fp._qualifying_modules(scan.roots)
                         if p not in scan.baseline and p not in scan.union)
        print(json.dumps({"flagged": flagged,
                          "intact": scan.closure_intact(),
                          "unexpected": scan.unexpected_loaded(),
                          "refusal": runs[0]._fingerprint(first)[1]}))
        failure = build.FetchFailure(1, "build-public", "", "probe_stop", "", "")
        return build.BuildOutcome((), failure)
    build.run_build = loop
    def unreachable(url, *a, **k):
        raise TransportFault("unreachable", url)
    outcome = build.run_build(entries, unreachable, cache, build.utc_now, lambda s: None,
                    large_stream=unreachable, seed=7,
                    pin_generation_config=load_generation_config(root),
                    pin_auto_supply=True, environ={})
    print(outcome.failure and outcome.failure.check, file=sys.stderr)
    """
)
_NEWLY_BOUND = (
    "custodian/src/eii_custodian/publicdata/assembly_method_pins.py",
    "custodian/src/eii_custodian/publicdata/assembly_refusals.py",
)


def _seeded_loop_probe(root: Path, tmp_path: Path, action: str) -> dict[str, Any]:
    cache = tmp_path / "run" / "data" / "public_cache"
    cache.mkdir(parents=True)
    done = subprocess.run(
        [sys.executable, "-I", "-c", _SEEDED_LOOP_PROBE, str(root), str(cache), action],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = done.stdout.strip().splitlines()
    assert done.returncode == 0 and lines, done.stderr[-1200:]
    result: dict[str, Any] = json.loads(lines[-1])
    return result


def _tracked_copy(tmp_path: Path) -> Path:
    """The checkout's tracked files, as on disk now, in a fresh git tree."""
    source = default_roots().code_root
    listed = subprocess.run(
        ["git", "-C", str(source), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    copy = tmp_path / "copy"
    for name in filter(None, listed.stdout.decode("utf-8").split("\0")):
        origin = source / name
        if origin.is_file():
            (copy / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, copy / name)
    commit = ["-c", "user.name=syn", "-c", "user.email=", "-c", "commit.gpgsign=false"]
    commit += ["-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "copy"]
    for args in (["init", "-q"], ["add", "-A"], commit):
        subprocess.run(["git", "-C", str(copy), *args], capture_output=True, check=True)
    return copy


def test_seeded_run_loads_no_unbound_module_before_the_fetch_loop(
    tmp_path: Path,
) -> None:
    """At fetch-loop entry of the real seeded run, nothing loaded after
    begin() sits outside the bound set, so an ordinary entry gets a record:
    _seeded_assembly binds the modules Production.run imports pre-fetch."""
    result = _seeded_loop_probe(default_roots().code_root, tmp_path, "none")
    assert result["flagged"] == []
    assert result["unexpected"] is False
    assert result["intact"] is True
    assert result["refusal"] is None


def test_seeded_run_module_loaded_late_is_flagged(tmp_path: Path) -> None:
    """Planted twin: an out-of-closure module first imported inside the loop
    is flagged and withholds the record, so the probe above is not vacuous."""
    copy = _tracked_copy(tmp_path)
    (copy / "custodian/src/syn_late_probe.py").write_text("X = 1\n")
    result = _seeded_loop_probe(copy, tmp_path, "plant")
    assert result["flagged"] == ["custodian/src/syn_late_probe.py"]
    assert result["unexpected"] is True
    assert result["intact"] is True
    assert result["refusal"] == "resume_fingerprint_unproven"


@pytest.mark.parametrize("name", _NEWLY_BOUND)
def test_seeded_run_newly_bound_file_edit_mid_run_is_unproven(
    tmp_path: Path, name: str
) -> None:
    """The preloaded assembly modules are bound, not exempted: an edit after
    begin() breaks closure_intact() and withholds the record."""
    copy = _tracked_copy(tmp_path)
    result = _seeded_loop_probe(copy, tmp_path, f"tamper:{name}")
    assert result["flagged"] == []
    assert result["unexpected"] is False
    assert result["intact"] is False
    assert result["refusal"] == "resume_fingerprint_unproven"


MISSED_FORMS = {
    "star_import_importlib": 'from importlib import *\nH = import_module("syn_hidden")\n',
    "star_import_importlib_nonliteral": (
        'from importlib import *\nN = "syn_" + "hidden"\nH = import_module(N)\n'
    ),
    "star_import_sys": 'from sys import *\nH = modules["syn_hidden"]\n',
    "sys_dict": 'import sys\nH = sys.__dict__["modules"]["syn_hidden"]\n',
    "vars_sys": 'import sys\nH = vars(sys)["modules"]["syn_hidden"]\n',
    "dunder_builtins": 'H = __builtins__["__import__"]("syn_hidden")\n',
    "bootstrap_gcd": (
        "import importlib._bootstrap\n"
        'H = importlib._bootstrap._gcd_import("syn_hidden")\n'
    ),
    "loader_load_module": (
        "import importlib.util\n"
        'H = importlib.util.find_spec("syn_hidden").loader.load_module("syn_hidden")\n'
    ),
    "exec_module_unregistered": (
        "import importlib.util, types\n"
        'S = importlib.util.find_spec("syn_hidden")\nH = types.ModuleType("h")\nS.loader.exec_module(H)\n'
    ),
    "function_type_compile": (
        "import types\n"
        'H = types.FunctionType(compile(open("syn_hidden.py").read(), "h", "exec"), {})\n'
    ),
}

REFUSED_MISSED = sorted(MISSED_FORMS)

SWEEP_FORMS = {
    "os_sys_modules": 'import os\nH = os.sys.modules["syn_hidden"]\n',
    "sys_getframe": (
        "import sys\n"
        'H = sys._getframe().f_globals["__builtins__"]["__import__"]("syn_hidden")\n'
    ),
    "sys_current_frames": (
        "import sys\n"
        'H = list(sys._current_frames().values())[0].f_globals["__builtins__"]["__import__"]("syn_hidden")\n'
    ),
    "inspect_currentframe": (
        "import inspect\n"
        'H = inspect.currentframe().f_globals["__builtins__"]["__import__"]("syn_hidden")\n'
    ),
    "getattr_exec_module": (
        "import importlib.util, types\n"
        'S = importlib.util.find_spec("syn_hidden")\nH = types.ModuleType("h")\ngetattr(S.loader, "exec_module")(H)\n'
    ),
    "getattr_load_module": (
        "import importlib.util\n"
        'S = importlib.util.find_spec("syn_hidden")\nH = getattr(S.loader, "load_module")("syn_hidden")\n'
    ),
    "star_import_machinery": (
        "from importlib.machinery import *\n"
        'H = SourceFileLoader("syn_hidden", "syn_hidden.py")\n'
    ),
    "star_import_bootstrap": (
        'from importlib._bootstrap import *\nH = _gcd_import("syn_hidden")\n'
    ),
    "star_import_pkgutil": 'from pkgutil import *\nH = resolve_name("syn_hidden")\n',
    "star_import_runpy": 'from runpy import *\nH = run_module("x")\n',
    "star_import_zipimport": 'from zipimport import *\nH = zipimporter("x")\n',
    "star_import_builtins": 'from builtins import *\nH = __import__("syn_hidden")\n',
    "star_import_util": (
        "from importlib.util import *\n"
        'H = find_spec("syn_hidden").loader.load_module("syn_hidden")\n'
    ),
    "importlib_dict": (
        'import importlib\nH = importlib.__dict__["import_module"]("syn_hidden")\n'
    ),
    "builtins_dict": 'import builtins\nH = builtins.__dict__["__import__"]("syn_hidden")\n',
    "vars_importlib": (
        'import importlib\nH = vars(importlib)["import_module"]("syn_hidden")\n'
    ),
    "vars_builtins": 'import builtins\nH = vars(builtins)["__import__"]("syn_hidden")\n',
    "builtins_dunder_attr": 'H = __builtins__.__import__("syn_hidden")\n',
    "dunder_loader_load_module": (
        'import syn_hidden\nH = syn_hidden.__loader__.load_module("syn_hidden")\n'
    ),
    "builtins_compile": (
        'import builtins\nH = builtins.compile("x = 1", "h", "exec")\n'
    ),
    "marshal_function": (
        'import marshal, types\nH = types.FunctionType(marshal.loads(b"\\xe3"), {})\n'
    ),
    "code_interactive": (
        'import code\nH = code.InteractiveConsole().push("import syn_hidden")\n'
    ),
    "codeop_compile": 'import codeop\nH = codeop.compile_command("x = 1")\n',
    "meta_path_insert": "import sys\nsys.meta_path.insert(0, object())\n",
    "path_hooks_append": "import sys\nsys.path_hooks.append(object())\n",
    "inspect_getmodule": "import inspect\nH = inspect.getmodule(H)\n",
    "module_type_exec": (
        "import importlib.util, types\n"
        'S = importlib.util.find_spec("syn_hidden")\nH = types.ModuleType("h")\n'
        "S.loader.exec_module(H)\n"
    ),
    "pickle_loads": 'import pickle\nH = pickle.loads(b"\\x80\\x05.")\n',
    "shelve_open": 'import shelve\nH = shelve.open("syn.db")\n',
    "operator_attrgetter": (
        "import importlib.util, operator, types\n"
        'S = importlib.util.find_spec("syn_hidden")\nH = types.ModuleType("h")\n'
        'operator.attrgetter("loader.exec_module")(S)(H)\n'
    ),
    "operator_methodcaller": (
        "import importlib.util, operator\n"
        'S = importlib.util.find_spec("syn_hidden")\n'
        'H = operator.methodcaller("load_module", "syn_hidden")(S.loader)\n'
    ),
    "getattribute_exec_module": (
        "import importlib.util, types\n"
        'S = importlib.util.find_spec("syn_hidden")\nH = types.ModuleType("h")\n'
        'S.loader.__getattribute__("exec_module")(H)\n'
    ),
    "code_interact": "import code\nH = code.interact\n",
    "code_interpreter": "import code\nH = code.InteractiveInterpreter()\n",
    "types_codetype": "import types\nH = types.CodeType\n",
    "types_lambdatype": "import types\nH = types.LambdaType\n",
    "inspect_stack": "import inspect\nH = inspect.stack()\n",
    "inspect_trace": "import inspect\nH = inspect.trace()\n",
    "inspect_getframeinfo": "import inspect\nH = inspect.getframeinfo\n",
    "inspect_getinnerframes": "import inspect\nH = inspect.getinnerframes\n",
    "inspect_getouterframes": "import inspect\nH = inspect.getouterframes\n",
    "dunder_getattr_member": "H = X.__getattr__\n",
    "loader_exec_module_unresolved": (
        "import importlib.util\n"
        'importlib.util.find_spec("syn_hidden").loader.exec_module(H)\n'
    ),
    "bare_exec": "H = exec\n",
    "bare_eval": "H = eval\n",
    "bare_compile": "H = compile\n",
    "bare_dunder_import": "H = __import__\n",
    "bare_builtins_import": "import builtins\nH = builtins.__import__\n",
    "bare_builtins_compile": "import builtins\nH = builtins.compile\n",
    "bare_builtins_exec": "import builtins\nH = builtins.exec\n",
    "bare_builtins_eval": "import builtins\nH = builtins.eval\n",
    "bare_spec_from_file_location": (
        "import importlib.util\nH = importlib.util.spec_from_file_location\n"
    ),
}


@pytest.mark.parametrize("form", REFUSED_MISSED)
def test_missed_form_is_refused_by_the_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    (tmp_path / "code" / "syn_hidden.py").write_text("P = 1\n", "utf-8")
    (tmp_path / "code" / "syn_machinery.py").write_text(MISSED_FORMS[form], "utf-8")
    with pytest.raises(FingerprintUnavailable):
        closure_files(roots, ("syn_machinery",), scoped=False)


@pytest.mark.parametrize("form", sorted(SWEEP_FORMS))
def test_sweep_dynamic_form_is_refused_by_the_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    """Forms beyond the reviewer's ten, found in the class sweep."""
    roots = _stub_roots(tmp_path, monkeypatch)
    (tmp_path / "code" / "syn_hidden.py").write_text("P = 1\n", "utf-8")
    (tmp_path / "code" / "syn_machinery.py").write_text(SWEEP_FORMS[form], "utf-8")
    with pytest.raises(FingerprintUnavailable):
        closure_files(roots, ("syn_machinery",), scoped=False)


def test_refuse_getattr_attrs_is_the_closed_set() -> None:
    """Pin the set the parametrized test reads: a removed member shrinks the
    parametrize list, so membership needs its own deciding row."""
    assert _ImportScan._REFUSE_GETATTR_ATTRS == frozenset(
        {
            "__builtins__",
            "__dict__",
            "__import__",
            "__loader__",
            "__spec__",
            "_current_frames",
            "_gcd_import",
            "_getframe",
            "__getattr__",
            "__getattribute__",
            "currentframe",
            "exec_module",
            "import_module",
            "load_module",
            "module_from_spec",
            "modules",
            "reload",
            "resolve_name",
            "run_module",
            "run_path",
            "spec_from_file_location",
            "spec_from_loader",
        }
    )


@pytest.mark.parametrize("attr", sorted(_ImportScan._REFUSE_GETATTR_ATTRS))
def test_literal_getattr_member_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str
) -> None:
    """Every literal attribute of the closed getattr set refuses, one row
    per member (class sweep L-1384)."""
    roots = _stub_roots(tmp_path, monkeypatch)
    (tmp_path / "code" / "syn_machinery.py").write_text(
        f'X = object()\nH = getattr(X, "{attr}", None)\n', "utf-8"
    )
    with pytest.raises(FingerprintUnavailable):
        closure_files(roots, ("syn_machinery",), scoped=False)


@pytest.mark.parametrize("form", REFUSED_MISSED)
def test_refused_missed_form_gives_no_fingerprint_and_refetches(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    """A refused second-round form in a scanned module leaves no proof."""
    _clean_syn_modules()
    roots = _stub_roots(tmp_path, monkeypatch)
    code = tmp_path / "code"
    (code / "syn_hidden.py").write_text("PACING_SECONDS = 1\n", "utf-8")
    (code / "syn_machinery.py").write_text(MISSED_FORMS[form], "utf-8")
    importlib.import_module("syn_hidden")
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert "fingerprint" not in item
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"
    _rewrite(code / "syn_hidden.py", "PACING_SECONDS = 0")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert not [line for line in outcome.lines if line.startswith("REUSE ")]
    assert harness.seen == [e.url for e in harness.entries]


CF2_ORIGINAL_FORMS = {
    "importlib_dunder_import": 'import importlib\nH = importlib.__import__("syn_hidden")\n',
    "getattr_import_module": (
        'import importlib\nH = getattr(importlib, "import_module")("syn_hidden")\n'
    ),
    "bound_alias_of_import_module": (
        'import importlib\nload = importlib.import_module\nH = load("syn_hidden")\n'
    ),
    "sys_modules_lookup": 'import sys\nH = sys.modules["syn_hidden"]\n',
    "pkgutil_resolve_name": 'import pkgutil\nH = pkgutil.resolve_name("syn_hidden")\n',
    "source_file_loader": (
        "from importlib.machinery import SourceFileLoader\n"
        'H = SourceFileLoader("syn_hidden", "syn_hidden.py")\n'
    ),
}


@pytest.mark.parametrize("form", sorted(CF2_ORIGINAL_FORMS))
def test_refused_form_in_scanned_module_gives_no_fingerprint_and_refetches(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    """The builder's move, judged: a refused form in a scanned module."""
    _clean_syn_modules()
    roots = _stub_roots(tmp_path, monkeypatch)
    code = tmp_path / "code"
    (code / "syn_hidden.py").write_text("PACING_SECONDS = 1\n", "utf-8")
    (code / "syn_machinery.py").write_text(CF2_ORIGINAL_FORMS[form], "utf-8")
    importlib.import_module("syn_hidden")
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert "fingerprint" not in item
    assert item["reuse_unavailable"] == "resume_fingerprint_unavailable"
    _rewrite(code / "syn_hidden.py", "PACING_SECONDS = 0")
    outcome = harness.run(resume=True, code_roots=roots)
    assert outcome.failure is None
    assert not [line for line in outcome.lines if line.startswith("REUSE ")]
    assert harness.seen == [e.url for e in harness.entries]


def test_stated_limit_preloaded_module_outside_runtime_dirs_is_not_bound(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins a stated limit (decision 0081 item 4): a module under code_root
    but outside the runtime roots, preloaded before the run begins, is bound
    by nothing, so an edit to it between runs still reuses. Production keeps
    every loaded module under the runtime roots (the real-roots test). If a
    later change binds such a module, this test fails and the limit is
    restated. Production has no such module: scripts/ is itself a runtime
    root, so scripts/preflight.py, loaded at process start by the launcher
    module preflight_cmd.py, is bound by the loaded-module digest. Replaces a
    strict expected failure, which the ledger's zero-skip rule refuses and
    which any unrelated error would also satisfy."""
    _clean_syn_modules()
    roots = _stub_roots(tmp_path, monkeypatch)
    side = tmp_path / "side"
    side.mkdir()
    (side / "syn_side.py").write_text("PACING_SECONDS = 1\n", "utf-8")
    monkeypatch.syspath_prepend(str(side))
    (tmp_path / "code" / "syn_preload.py").write_text("import syn_side\n", "utf-8")
    importlib.import_module("syn_preload")
    _interrupt(harness, code_roots=roots)
    assert "fingerprint" in record(harness)["entries"]["SYN-first"]
    _rewrite(side / "syn_side.py", "PACING_SECONDS = 0")
    outcome = harness.run(resume=True, code_roots=roots)
    stale = [line for line in outcome.lines if line.startswith("REUSE SYN-first ")]
    assert outcome.failure is None
    assert len(stale) == 1, f"the stated limit no longer holds: {outcome.lines}"


def test_stated_limit_module_outside_runtime_dirs_loaded_after_begin_is_unwatched(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins a stated limit (decision 0081 item 4): the run-time guard watches
    the runtime roots only, so a module outside them loaded after the run
    begins leaves the entry's fingerprint in place. Production keeps every
    loaded module under the runtime roots. If a later change makes the guard
    trip here, this test fails and the limit is restated. Replaces a strict
    expected failure, which the ledger's zero-skip rule refuses."""
    roots = _stub_roots(tmp_path, monkeypatch)
    side = tmp_path / "side"
    side.mkdir()
    smuggled = side / "syn_side_late.py"
    smuggled.write_text("S = 1\n", "utf-8")
    original = harness.transport

    def planting(url):  # type: ignore[no-untyped-def]
        module = types.ModuleType("syn_side_late")
        module.__file__ = str(smuggled)
        sys.modules["syn_side_late"] = module
        return original(url)

    harness.transport = planting  # type: ignore[method-assign]
    try:
        _interrupt(harness, code_roots=roots)
    finally:
        sys.modules.pop("syn_side_late", None)
    item = record(harness)["entries"]["SYN-first"]
    assert "reuse_unavailable" not in item, item.keys()
    assert "fingerprint" in item, item.keys()


def test_named_file_edit_between_runs_refetches(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    launcher = tmp_path / "syn_eii"
    launcher.write_text("#!/bin/sh\nexec python -I a.py\n", "utf-8")
    roots = replace(roots, named_files={"eii": launcher})
    _interrupt(harness, code_roots=roots)
    assert "fingerprint" in record(harness)["entries"]["SYN-first"]
    launcher.write_text("#!/bin/sh\nexec python -E a.py\n", "utf-8")
    outcome = harness.run(resume=True, code_roots=roots)
    assert not [line for line in outcome.lines if line.startswith("REUSE ")]
    assert harness.entries[0].url in harness.seen


def test_named_file_edit_mid_run_leaves_item_unproven(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _stub_roots(tmp_path, monkeypatch)
    launcher = tmp_path / "syn_eii"
    launcher.write_text("#!/bin/sh\nexec python -I a.py\n", "utf-8")
    roots = replace(roots, named_files={"eii": launcher})
    original = harness.transport

    def editing(url):  # type: ignore[no-untyped-def]
        time.sleep(0.05)
        launcher.write_text("#!/bin/sh\nexec python -E a.py\n", "utf-8")
        return original(url)

    harness.transport = editing  # type: ignore[method-assign]
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert "fingerprint" not in item, item


def test_preloaded_module_edit_mid_run_leaves_item_unproven(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clean_syn_modules()
    roots = _stub_roots(tmp_path, monkeypatch)
    pre = tmp_path / "code" / "syn_preload.py"
    pre.write_text("P = 1\n", "utf-8")
    importlib.import_module("syn_preload")
    original = harness.transport

    def editing(url):  # type: ignore[no-untyped-def]
        time.sleep(0.05)
        pre.write_text("P = 2\n", "utf-8")
        return original(url)

    harness.transport = editing  # type: ignore[method-assign]
    _interrupt(harness, code_roots=roots)
    item = record(harness)["entries"]["SYN-first"]
    assert "fingerprint" not in item, item


def test_loaded_set_change_between_runs_refetches(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clean_syn_modules()
    roots = _stub_roots(tmp_path, monkeypatch)
    (tmp_path / "code" / "syn_preload.py").write_text("P = 1\n", "utf-8")
    _interrupt(harness, code_roots=roots)
    importlib.import_module("syn_preload")  # now part of the baseline
    outcome = harness.run(resume=True, code_roots=roots)
    assert not [line for line in outcome.lines if line.startswith("REUSE ")]


def test_old_file_same_size_same_mtime_edit_is_seen(tmp_path: Path) -> None:
    """The production shape: the file is older than one tick when hashed."""
    path = tmp_path / "syn_old.py"
    path.write_text("A = 1\n", "utf-8")
    time.sleep(0.05)
    first = _sha256(path)
    stat = path.stat()
    path.write_text("B = 2\n", "utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert _sha256(path) != first
