"""Per-entry fetch-code and data-input fingerprints for durable resume.

A reuse-capable journal item (schema 2) binds one entry to the exact code and
inputs that produced it: the closed-encoded constructed ``Entry`` (which
carries every field of its registry row), the dispatch branch, the computed
code closure hash, the repository modules loaded before the run began, the
named non-module files such as the ``eii`` launcher, the global public-data
input, the Python version and the locked dependency set. The code closure is
computed from a static AST scan resolved with ``importlib.util.find_spec``
under the actual ``sys.path``; anything dynamic or unresolvable refuses
rather than guessing. Anything the scan cannot prove leaves the item without
a fingerprint and is never reused.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, ClassVar, cast

from .registry import Entry

SCHEMA = 2

_BUILD_MODULE = "eii_custodian.publicdata.fetch.build"
_KINDS_MODULE = "eii_custodian.publicdata.fetch.kinds"

# The machinery is every module the fetch loop itself can reach. build.py's
# seed is all of it minus the named scopes below; an unlisted scope is inside
# the machinery by default so a lazy import added later fails closed.
MACHINERY_SEEDS: tuple[str, ...] = (
    _BUILD_MODULE,
    "eii_custodian.publicdata.fetch.resume",
    "commands.build_public",
    "earthdata_key",
)

# build.py function scopes excluded from the machinery closure. Each runs
# only after the fetch loop or only for note-only rows (whose completion
# never carries a fingerprint), except _seeded_assembly, which runs before
# the loop and is bound through the loaded-module hash instead. Each name is
# asserted to exist as a top-level function of build.py; the scope set may not
# overlap any computed closure's inputs.
EXCLUDED_SCOPES: frozenset[str] = frozenset(
    {
        "_seeded_assembly",
        "_publish_additions",
        "_heights",
        "_archive_investment_attempts",
        "_comtrade_dispatch",
        # Separate tender entry point. Its assembly imports run after the
        # ordinary fetch loop and must not enter that loop's machinery.
        "run_tenders_only",
    }
)
_OWN_RUN_MODULE = "eii_custodian.publicdata.fetch.own_run"
# Called only from run_tenders_only, and only to adopt an already completed
# archive. The assembly imports inside it are outside the fetch loop.
OWN_RUN_EXCLUDED_SCOPES: frozenset[str] = frozenset({"handoff_completed_archive"})

# One branch root per dispatch branch. Modules these roots pull are already
# shared machinery today (their lazy imports sit inside kept scopes); the map
# exists so a branch id always has an explicit, reviewable root list.
BRANCH_ROOTS: dict[str, tuple[str, ...]] = {
    "grid": ("eii_custodian.publicdata.grids.fetch",),
    "comtrade": ("eii_custodian.publicdata.comtrade.fetch",),
    "pages": (
        "eii_custodian.publicdata.fetch.awards",
        "eii_custodian.publicdata.fetch.page_records",
    ),
    "besttime": ("eii_custodian.publicdata.busyness.build",),
    "release": ("eii_custodian.publicdata.places_fsq.fetch",),
    "place_file": ("eii_custodian.publicdata.places.fetch",),
    "large": ("eii_custodian.publicdata.fetch.large",),
    "listing": ("eii_custodian.publicdata.fetch.listing",),
    "benchmark": ("eii_custodian.publicdata.benchmarks.fetch",),
    "baci": ("eii_custodian.publicdata.baci.fetch",),
    "gravity": ("eii_custodian.publicdata.gravity.fetch",),
    "atlas": ("eii_custodian.publicdata.atlas.fetch",),
    "paged_cards": (_KINDS_MODULE,),
    "portal_dataset": (_KINDS_MODULE,),
    "paged_layer": (
        _KINDS_MODULE,
        "eii_custodian.publicdata.gis.fields",
    ),
    "terms_page": (_KINDS_MODULE,),
    "file": (_KINDS_MODULE,),
    "citation": (),
    "register": (),
    "skipped": (),
}


class FingerprintUnavailable(ValueError):
    """The proof machinery cannot compute a sound fingerprint; refuse reuse."""


def branch_for(entry: Entry, large: bool) -> str:
    """Name the dispatch branch run_build actually takes for one entry."""
    from eii_custodian.publicdata.benchmarks.contracts import (
        TABLES as BENCHMARK_TABLES,
    )
    from eii_custodian.publicdata.grids.fetch import GRID_SOURCES
    from eii_custodian.publicdata.places.fetch import is_place_file
    from eii_custodian.publicdata.places_fsq.fetch import is_release_entry

    if entry.kind == "register_file":
        return "register"
    if entry.source_id in GRID_SOURCES:
        return "grid"
    if entry.source_id in BENCHMARK_TABLES:
        return "benchmark"
    if entry.source_id == "cepii_baci":
        return "baci"
    if entry.source_id == "cepii_gravity":
        return "gravity"
    if entry.source_id == "atlas_complexity":
        return "atlas"
    if entry.kind == "besttime":
        return "besttime"
    if entry.skip_reason:
        return "skipped"
    if entry.kind in {"public_page", "awards_intake"}:
        return "pages"
    if entry.kind == "citation_only":
        return "citation"
    if entry.kind == "comtrade_api":
        return "comtrade"
    if is_release_entry(entry):
        return "release"
    if is_place_file(entry):
        return "place_file"
    if large:
        from eii_custodian.publicdata.fetch.large import REQUIRED_KEYS

        if entry.key in REQUIRED_KEYS:
            return "large"
    if entry.key in {"places_ovt", "bldg_ovt"}:
        return "listing"
    if entry.kind == "paged_cards":
        return "paged_cards"
    if entry.kind in {"portal_dataset", "paged_layer", "terms_page"}:
        return entry.kind
    return "file"


def closed_encode(value: object) -> Any:
    """Encode registry values into canonical JSON-safe structures, or refuse.

    Only the closed set str, int, float, bool, None, tuple, list and frozen
    dataclasses is admitted; anything else raises rather than degrading to a
    string. Dataclasses encode as ordered ``[field, value]`` pairs.
    """
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise FingerprintUnavailable("entry_field_type")
        return value
    if type(value) in {list, tuple}:
        return [closed_encode(item) for item in cast(Sequence[object], value)]
    if is_dataclass(value) and not isinstance(value, type):
        return [
            [item.name, closed_encode(getattr(value, item.name))]
            for item in fields(value)
        ]
    raise FingerprintUnavailable("entry_field_type")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


_HASH_CACHE: dict[Path, tuple[int, int, int, str]] = {}


def _sha256(path: Path) -> str:
    stat = path.stat()
    cached = _HASH_CACHE.get(path)
    if (
        cached is not None
        and cached[0] == stat.st_mtime_ns
        and cached[1] == stat.st_ctime_ns
        and cached[2] == stat.st_size
    ):
        return cached[3]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    value = digest.hexdigest()
    _HASH_CACHE[path] = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, value)
    return value


def _git_tracked(root: Path, publicdata: Path) -> frozenset[Path]:
    """Resolved paths git tracks under publicdata, via an option-fixed call."""
    try:
        relative = publicdata.relative_to(root)
    except ValueError:
        raise FingerprintUnavailable("publicdata_outside_root") from None
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", relative.as_posix()],
            capture_output=True,
            env=env,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise FingerprintUnavailable("tracked_listing_failed") from None
    if result.returncode != 0:
        raise FingerprintUnavailable("tracked_listing_failed")
    return frozenset(
        (root / name).resolve()
        for name in result.stdout.decode("utf-8").split("\0")
        if name
    )


def _find(name: str) -> Any:
    try:
        return importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError):
        return None


_DISTRIBUTIONS: frozenset[str] | None = None
_LOCKED_NAMES: dict[Path, frozenset[str]] = {}


def _locked_distributions(roots: CodeRoots) -> frozenset[str]:
    """Installed distribution module names plus every name uv.lock declares."""
    global _DISTRIBUTIONS
    cached = _LOCKED_NAMES.get(roots.uv_lock)
    if cached is not None:
        return cached
    names: set[str] = set()
    if _DISTRIBUTIONS is None:
        try:
            _DISTRIBUTIONS = frozenset(importlib.metadata.packages_distributions())
        except Exception:
            _DISTRIBUTIONS = frozenset()
    names.update(_DISTRIBUTIONS)
    try:
        for line in roots.uv_lock.read_text(encoding="utf-8").splitlines():
            if line.startswith('name = "'):
                locked = line.split('"')[1]
                names.add(locked)
                names.add(locked.replace("-", "_"))
    except (OSError, IndexError):
        pass
    result = frozenset(names)
    _LOCKED_NAMES[roots.uv_lock] = result
    return result


@dataclass(frozen=True)
class _ModuleScan:
    edges: tuple[tuple[str, str], ...]
    refusals: tuple[tuple[str, str], ...]


class _ImportScan(ast.NodeVisitor):
    """Collect absolute import edges and refused dynamic forms per scope.

    Calls of the named forms refuse, and so does any reference — call or not —
    to an object that can load code or reach module state the static scan
    cannot see. The one named exception is this module's own ``sys.modules``
    read in ``_qualifying_modules``.
    """

    _REFUSE_NAMES: ClassVar[frozenset[str]] = frozenset(
        {"__import__", "compile", "exec", "eval"}
    )
    _REFUSE_EXACT: ClassVar[frozenset[str]] = frozenset(
        {
            "builtins.__import__",
            "builtins.compile",
            "builtins.exec",
            "builtins.eval",
            "importlib.util.spec_from_file_location",
        }
    )
    _REFUSE_REFERENCES: ClassVar[frozenset[str]] = frozenset(
        {
            "__import__",
            "compile",
            "exec",
            "eval",
            "builtins.__import__",
            "builtins.compile",
            "builtins.exec",
            "builtins.eval",
            "code.InteractiveConsole",
            "code.InteractiveInterpreter",
            "code.interact",
            "importlib.__import__",
            "importlib.reload",
            "importlib.util.module_from_spec",
            "importlib.util.spec_from_loader",
            "importlib.util.spec_from_file_location",
            "operator.attrgetter",
            "operator.methodcaller",
            "sys.meta_path",
            "sys.path_hooks",
            "types.CodeType",
            "types.FunctionType",
            "types.LambdaType",
        }
    )
    _REFUSE_REFERENCE_ROOTS: ClassVar[frozenset[str]] = frozenset(
        {
            "codeop",
            "importlib.machinery",
            "pickle",
            "pkgutil",
            "runpy",
            "shelve",
            "zipimport",
        }
    )
    # Frame and module-object access reaches globals the static scan cannot
    # see. The bare name ``inspect`` is a legal local name in real modules,
    # so the refusal names the members, not the module.
    _REFUSE_FRAME_ACCESS: ClassVar[frozenset[str]] = frozenset(
        {
            "inspect.currentframe",
            "inspect.getframeinfo",
            "inspect.getinnerframes",
            "inspect.getmodule",
            "inspect.getouterframes",
            "inspect.stack",
            "inspect.trace",
            "sys._current_frames",
            "sys._getframe",
        }
    )
    _GETATTR_ROOTS: ClassVar[frozenset[str]] = frozenset(
        {"builtins", "importlib", "sys"}
    )
    _REFUSE_ATTRS: ClassVar[frozenset[str]] = frozenset(
        {"load_module", "exec_module", "__getattr__", "__getattribute__"}
    )
    # getattr(x, "name") with a literal attribute from this set reaches the
    # same loading and module-state surfaces the named references refuse.
    _REFUSE_GETATTR_ATTRS: ClassVar[frozenset[str]] = frozenset(
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

    def __init__(self, module: str, is_package: bool) -> None:
        self.module = module
        self.is_package = is_package
        self.scope: list[str] = []
        self.edges: list[tuple[str, str]] = []
        self.refusals: list[tuple[str, str]] = []
        self.aliases: dict[str, str] = {}
        self._permitted: set[int] = set()

    def _top(self) -> str:
        return self.scope[0] if self.scope else ""

    def _refuse(self, form: str) -> None:
        item = (form, self._top())
        if item not in self.refusals:
            self.refusals.append(item)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                self.aliases[alias.asname] = alias.name
            else:
                top = alias.name.partition(".")[0]
                self.aliases[top] = top
            self.edges.append((alias.name, self._top()))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = self._from_base(node)
        if base:
            self.edges.append((base, self._top()))
            for alias in node.names:
                bound = alias.asname or alias.name
                self.aliases[bound] = base + "." + alias.name
                if alias.name == "*":
                    # A star import binds names the scan cannot enumerate;
                    # refuse it on every root that can load or reach module
                    # state.
                    if (
                        base.split(".", 1)[0] in self._GETATTR_ROOTS
                        or base in self._REFUSE_REFERENCE_ROOTS
                    ):
                        self._refuse(f"{base}.*")
                    continue
                self.edges.append((base + "." + alias.name, self._top()))
        self.generic_visit(node)

    def _from_base(self, node: ast.ImportFrom) -> str | None:
        if node.level == 0:
            return node.module
        parts = self.module.split(".")
        package = parts if self.is_package else parts[:-1]
        for _ in range(node.level - 1):
            package = package[:-1]
        base = ".".join(package)
        return (base + "." + node.module) if node.module else base

    def _dotted(self, node: ast.AST) -> str | None:
        """Resolve a Name or Attribute chain through the import aliases."""
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            base = self.aliases.get(node.id, node.id)
            return ".".join([base, *reversed(parts)])
        return None

    def _callee(self, node: ast.Call) -> str | None:
        return self._dotted(node.func)

    def _reference(self, node: ast.Name | ast.Attribute) -> None:
        """Refuse a resolved reference that can load or reach unseen code."""
        if id(node) in self._permitted:
            return
        if isinstance(node, ast.Attribute) and node.attr in self._REFUSE_ATTRS:
            # Loader entry points refuse on the attribute name alone: the
            # chain may sit on a call or subscript the scan cannot resolve.
            self._refuse(node.attr)
        name = self._dotted(node)
        if name is None:
            return
        if name == "sys.modules" or name.startswith("sys.modules."):
            # This module's own baseline read is the one named exception.
            if (self.module, self._top()) != (__name__, "_qualifying_modules"):
                self._refuse("sys.modules")
            return
        if (
            name in self._REFUSE_REFERENCES
            or name in self._REFUSE_REFERENCE_ROOTS
            or any(name.startswith(root + ".") for root in self._REFUSE_REFERENCE_ROOTS)
            or name == "importlib.import_module"
            or name.endswith(".import_module")
            or name.endswith(".load_module")
            or name.endswith(".exec_module")
            or name == "__builtins__"
            or name.startswith("__builtins__.")
            or name == "importlib._bootstrap"
            or name.startswith("importlib._bootstrap.")
            or name == "os.sys"
            or name.startswith("os.sys.")
            or name in self._REFUSE_FRAME_ACCESS
            or any(
                name == root + ".__dict__" or name.startswith(root + ".__dict__.")
                for root in self._GETATTR_ROOTS
            )
        ):
            self._refuse(name)

    def visit_Name(self, node: ast.Name) -> None:
        self._reference(node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._reference(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = self._callee(node)
        if name is None:
            self.generic_visit(node)
            return
        if name in {"getattr", "builtins.getattr"} and node.args:
            target = self._dotted(node.args[0])
            if target is not None and target.split(".", 1)[0] in self._GETATTR_ROOTS:
                self._refuse(f"getattr:{target}")
            if (
                len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and node.args[1].value in self._REFUSE_GETATTR_ATTRS
            ):
                self._refuse(f"getattr:{target or '?'}:{node.args[1].value}")
        if (
            name in {"vars", "builtins.vars"}
            and node.args
            and (target := self._dotted(node.args[0])) is not None
            and target.split(".", 1)[0] in self._GETATTR_ROOTS
        ):
            self._refuse(f"vars:{target}")
        if (
            name in self._REFUSE_NAMES
            or name in self._REFUSE_EXACT
            or name == "runpy"
            or name.startswith("runpy.")
        ):
            self._refuse(name)
        elif name == "importlib.import_module" or name.endswith(".import_module"):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.edges.append((first.value, self._top()))
                self._permitted.add(id(node.func))
            else:
                self._refuse("importlib.import_module")
        self.generic_visit(node)


_SCAN_CACHE: dict[tuple[Path, str], tuple[int, int, int, _ModuleScan]] = {}


def _scan_file(path: Path, module: str) -> _ModuleScan:
    try:
        stat = path.stat()
    except OSError:
        raise FingerprintUnavailable("module_unreadable") from None
    cached = _SCAN_CACHE.get((path, module))
    if (
        cached is not None
        and cached[0] == stat.st_mtime_ns
        and cached[1] == stat.st_ctime_ns
        and cached[2] == stat.st_size
    ):
        return cached[3]
    try:
        tree = ast.parse(path.read_bytes(), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        raise FingerprintUnavailable("module_unreadable") from None
    visitor = _ImportScan(module, path.name == "__init__.py")
    visitor.visit(tree)
    scan = _ModuleScan(tuple(visitor.edges), tuple(visitor.refusals))
    _SCAN_CACHE[(path, module)] = (
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        stat.st_size,
        scan,
    )
    return scan


def _under(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _origin(spec: Any) -> Path | None:
    origin = getattr(spec, "origin", None)
    if origin is None or origin in {"frozen", "built-in", "namespace"}:
        return None
    try:
        path = Path(origin).resolve()
    except OSError:
        return None
    return path if path.is_file() else None


@dataclass(frozen=True)
class CodeRoots:
    """The roots and seams the fingerprint computation binds.

    ``code_root`` bounds the static closure; ``runtime_dirs``/``runtime_files``
    bound the runtime loaded-module check; ``named_files`` are bound by hash
    into every record; ``tracked`` lists the public-data input files;
    ``seeds``/``scope_excludes``/``branch_roots``/``brancher`` define the
    machinery and per-branch roots. Tests substitute a small stub tree for
    ``code_root`` and the seed names.
    """

    code_root: Path
    publicdata: Path
    tracked: Callable[[], frozenset[Path]]
    uv_lock: Path
    code_excludes: tuple[Path, ...] = ()
    runtime_dirs: tuple[Path, ...] = ()
    runtime_files: frozenset[Path] = frozenset()
    named_files: Mapping[str, Path] = field(default_factory=dict)
    seeds: tuple[str, ...] = MACHINERY_SEEDS
    scope_excludes: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: {
            _BUILD_MODULE: EXCLUDED_SCOPES,
            _OWN_RUN_MODULE: OWN_RUN_EXCLUDED_SCOPES,
        }
    )
    branch_roots: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: BRANCH_ROOTS
    )
    brancher: Callable[..., str] = branch_for


def default_roots() -> CodeRoots:
    """The production roots: the repository checkout this module lives in."""
    root = Path(__file__).resolve().parents[5]
    runtime_dirs = tuple(
        path
        for path in (
            root / "custodian/src",
            root / "core/src",
            root / "product/src",
            root / "gateway/src",
            root / "scripts",
        )
        if path.is_dir()
    )
    runtime_files = frozenset(
        path
        for path in (
            root / "scripts/cdse_key.py",
            root / "scripts/earthdata_key.py",
        )
        if path.is_file()
    )
    publicdata = root / "custodian" / "publicdata"
    code_excludes = tuple(
        path
        for path in (root / ".venv", root / ".git", root / "node_modules")
        if path.exists()
    )
    return CodeRoots(
        code_root=root,
        publicdata=publicdata,
        tracked=lambda: _git_tracked(root, publicdata),
        uv_lock=root / "uv.lock",
        code_excludes=code_excludes,
        runtime_dirs=runtime_dirs,
        runtime_files=runtime_files,
        # The eii shell launcher is no Python module; it sets python -I and
        # the entry script, so it is bound as a named hashed file instead.
        named_files={"eii": root / "eii"},
    )


class _Closure:
    """Static import closure resolved under the actual sys.path."""

    def __init__(self, roots: CodeRoots) -> None:
        self.roots = roots
        self.names: dict[str, Path | None] = {}
        self.scanned: set[str] = set()

    def reach(self, seeds: Sequence[str], scoped: bool) -> frozenset[Path]:
        reached: set[str] = set()
        pending = list(seeds)
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            if name not in self.names:
                self.names[name] = self._resolve_target(name)
            path = self.names[name]
            if path is None or name in self.scanned:
                continue
            self.scanned.add(name)
            scan = _scan_file(path, name)
            excludes = (
                self.roots.scope_excludes.get(name, frozenset())
                if scoped
                else frozenset()
            )
            for form, scope in scan.refusals:
                if scope not in excludes:
                    raise FingerprintUnavailable(f"dynamic_import:{form}")
            for target, scope in scan.edges:
                if scope in excludes:
                    continue
                if target not in self.names:
                    self.names[target] = self._resolve_target(target)
                if self.names[target] is not None:
                    pending.append(target)
                for ancestor in self._ancestors(target):
                    if ancestor not in self.names:
                        self.names[ancestor] = self._resolve_target(ancestor)
                    if self.names[ancestor] is not None:
                        pending.append(ancestor)
        return frozenset(
            path for name in reached if (path := self.names[name]) is not None
        )

    def _ancestors(self, name: str) -> tuple[str, ...]:
        """Each parent package __init__ runs on import; it joins the closure."""
        parts = name.split(".")
        return tuple(".".join(parts[:index]) for index in range(1, len(parts)))

    def _resolve_target(self, name: str) -> Path | None:
        spec = _find(name)
        if spec is not None:
            origin = _origin(spec)
            if (
                origin is not None
                and _under(origin, self.roots.code_root)
                and not any(
                    _under(origin, excluded) for excluded in self.roots.code_excludes
                )
            ):
                return origin
            return None
        for depth in range(1, name.count(".") + 1):
            if _find(name.rsplit(".", depth)[0]) is not None:
                return None
        top = name.partition(".")[0]
        if top in sys.stdlib_module_names or top in _locked_distributions(self.roots):
            return None
        raise FingerprintUnavailable(f"unresolvable_import:{name}")


def closure_files(
    roots: CodeRoots, seeds: Sequence[str], *, scoped: bool
) -> frozenset[Path]:
    """Files of one computed closure; refusals raise FingerprintUnavailable."""
    return _Closure(roots).reach(seeds, scoped)


def _global_input(roots: CodeRoots) -> str:
    """SHA-256 of the canonical (path, hash) list of every tracked input.

    sources.yaml stays bound per registry row. A tracked path missing from the
    working tree, and any untracked file under publicdata, refuses rather than
    silently leaving the input unbound.
    """
    tracked = roots.tracked()
    sources_yaml = (roots.publicdata / "sources.yaml").resolve()
    items: list[list[str]] = []
    for path in sorted(tracked):
        if not path.is_file():
            raise FingerprintUnavailable("tracked_publicdata_missing")
        if path == sources_yaml:
            continue
        try:
            relative = path.relative_to(roots.code_root).as_posix()
        except ValueError:
            raise FingerprintUnavailable("tracked_publicdata_outside_root") from None
        items.append([relative, _sha256(path)])
    if roots.publicdata.is_dir():
        for found in sorted(roots.publicdata.rglob("*")):
            if found.is_file() and found.resolve() not in tracked:
                raise FingerprintUnavailable("untracked_publicdata_file")
    return hashlib.sha256(_canonical(items).encode("ascii")).hexdigest()


def _qualifying_modules(roots: CodeRoots) -> frozenset[Path]:
    """Loaded modules whose origin file lies under the runtime roots."""
    found: set[Path] = set()
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if not file:
            continue
        try:
            path = Path(file).resolve()
        except OSError:
            continue
        if path in roots.runtime_files or any(
            _under(path, directory) for directory in roots.runtime_dirs
        ):
            found.add(path)
    return frozenset(found)


@dataclass
class RunScan:
    """Every fingerprint input computed once at RunRecord.begin."""

    records: dict[str, dict[str, Any] | None]
    # The static closure plus every baseline module outside it: the set of
    # module files the per-entry fingerprints bind.
    union: frozenset[Path]
    hashes: dict[Path, str]
    baseline: frozenset[Path]
    data: str | None
    roots: CodeRoots

    def closure_intact(self) -> bool:
        """Re-hash every bound file; a mid-run edit breaks the proof."""
        try:
            for path, digest in self.hashes.items():
                if _sha256(path) != digest:
                    return False
        except OSError:
            return False
        if self.data is not None:
            try:
                if _global_input(self.roots) != self.data:
                    return False
            except (FingerprintUnavailable, OSError):
                return False
        return True

    def unexpected_loaded(self) -> bool:
        """A repository module loaded after begin() outside the closures."""
        for path in _qualifying_modules(self.roots):
            if path not in self.baseline and path not in self.union:
                return True
        return False


def scan_run(entries: Sequence[Entry], roots: CodeRoots, *, large: bool) -> RunScan:
    """Compute the machinery, per-branch closures and per-entry records."""
    closure = _Closure(roots)
    machinery = closure.reach(roots.seeds, scoped=True)
    branch_files: dict[str, frozenset[Path]] = {}
    for branch, seeds in roots.branch_roots.items():
        branch_files[branch] = machinery | closure.reach(seeds, scoped=False)
    union = frozenset().union(machinery, *branch_files.values())
    hashes: dict[Path, str] = {}
    try:
        for path in union:
            hashes[path] = _sha256(path)
    except OSError:
        raise FingerprintUnavailable("module_unreadable") from None

    def digest(files: frozenset[Path]) -> str:
        rows = sorted(
            [path.relative_to(roots.code_root).as_posix(), hashes[path]]
            for path in files
        )
        return hashlib.sha256(_canonical(rows).encode("ascii")).hexdigest()

    digests = {branch: digest(files) for branch, files in branch_files.items()}
    try:
        data = _global_input(roots)
    except (FingerprintUnavailable, OSError):
        data = None
    try:
        uv_lock = _sha256(roots.uv_lock)
    except OSError:
        uv_lock = None
    python = ".".join(str(part) for part in sys.version_info[:3])
    records: dict[str, dict[str, Any] | None] = {}
    for entry in entries:
        try:
            if data is None or uv_lock is None:
                raise FingerprintUnavailable("fingerprint_input_unavailable")
            branch = roots.brancher(entry, large)
            code = digests.get(branch)
            if code is None:
                raise FingerprintUnavailable("fingerprint_branch_unknown")
            record: dict[str, Any] = {
                "schema": SCHEMA,
                "branch": branch,
                "entry": closed_encode(entry),
                "code": code,
                "data": data,
                "python": python,
                "uv_lock": uv_lock,
            }
            if branch == "listing":
                record["siblings"] = [
                    [sibling.key, closed_encode(sibling)]
                    for sibling in sorted(
                        (s for s in entries if s.key.startswith(entry.key + "/")),
                        key=lambda s: s.key,
                    )
                ]
            records[entry.key] = record
        except (FingerprintUnavailable, ValueError):
            records[entry.key] = None
    # The baseline stays last so modules this scan itself loads (parent
    # packages of find_spec, the brancher's lazy imports) are recorded as
    # loaded-before-fetch rather than tripping the runtime guard. Every
    # baseline module outside the static closure is hashed, folded into each
    # record's loaded digest and joined into the union, which then holds
    # every module file the fingerprints bind: an edit to it refetches, and
    # a module loaded later still trips the guard.
    baseline = _qualifying_modules(roots)
    outside = baseline - union
    named: dict[str, str] = {}
    try:
        for path in outside:
            if not path.is_relative_to(roots.code_root):
                raise FingerprintUnavailable("loaded_module_outside_root")
            hashes[path] = _sha256(path)
        for name, path in sorted(roots.named_files.items()):
            resolved = path.resolve()
            if not resolved.is_file():
                raise FingerprintUnavailable("named_file_missing")
            hashes[resolved] = _sha256(resolved)
            named[name] = hashes[resolved]
    except OSError:
        raise FingerprintUnavailable("module_unreadable") from None
    loaded = digest(outside)
    for stored in records.values():
        if stored is not None:
            stored["loaded"] = loaded
            stored["named_files"] = named
    return RunScan(records, union | outside, hashes, baseline, data, roots)
