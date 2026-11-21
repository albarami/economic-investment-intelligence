"""S2-P39: per-entry fetch-code fingerprints; invented stubs, no public bytes."""

from __future__ import annotations

import json
import sys
import types
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_build_resume import (
    LATER,
    START,
    Harness,
    entry,
    record,
)

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.fetch import kinds, listing
from eii_custodian.publicdata.fetch.fingerprint import (
    BRANCH_ROOTS,
    EXCLUDED_SCOPES,
    CodeRoots,
    FingerprintUnavailable,
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


def test_changed_intake_triple_refetches_tenders(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch import awards
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
