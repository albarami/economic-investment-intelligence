"""Decision 0035 unchanged-controls pin.

Maker: SpaceXAI. Model: Grok 4.7.
Persona: senior test architect for privacy and security controls (builder).
A different maker reviews the code.

The walker reads declarations this checkout already has and compares them with
the stored pin. It adds no threshold. A missing pin fails the comparison.

Retired rule spellings stay in the privacy check and its own test. The pin
stores a digest of that set, and assertion text cites the set by stand-in, so
this fixture does not become a second copy of those spellings.

Routes by which overlay code can run or rebind behaviour without naming a
protected name or an import (S3-CTL r7, Python 3.14), and the decision for
each. A pinned value is reachable only by its name (the walker sees it), by
its module's namespace, or by code whose names the source does not show.

Added to `_NAMESPACE` (each family has a plant proven to empty or rebind a
pinned value before the fix and refused after it):
- code objects: `__code__`, `__replace__`, the `co_*` fields that
  `code.replace` retargets, and the other code-object reaches `gi_code`,
  `cr_code`, `ag_code`, `f_code` (plant `r7_code_object`, CF6's overlay);
- class machinery: `__subclasses__`, which walks from `object` to an import
  loader that hands out the module itself (plant `r7_subclasses`).
Census of module reads (`_MODULE_READS`): a name an `import` binds may appear
only as `module.attribute` loads the real tree holds today, so no submodule or
library gadget is reachable (`string.Formatter().get_field`, which fetches a
function's globals by a computed string; `dataclasses.annotationlib`,
`dataclasses.types`; `yaml` loaders other than `safe_load`) (plant
`r7_module_read`).
Not added, each shown by `test_r7_non_routes_cannot_reach_a_pinned_value`
(runs the overlay with Python, value unchanged, projection equal to the pin):
- `__defaults__`, `__kwdefaults__`, `__closure__`, `cell_contents`,
  `__func__`, `__wrapped__`: they rebind only what the overlay itself holds;
  an admitted file never hands a pinned mutable value to a default or a cell;
- `__class__`, `__bases__`, `__mro__`, `__init_subclass__`, `__set_name__`:
  they reach classes, never a module; hooks run code the walker reads;
- `compile` (the real tree uses `re.compile`), `type(f)` as FunctionType,
  `__reduce__`, `__reduce_ex__`: a code object runs only through `exec`,
  `eval`, `__code__` or a setter of `__code__` by a computed name, and a new
  function needs a globals dict, all refused;
- `types`, `marshal`, `pickle`, `copyreg`, `CodeType`, `FunctionType`: their
  imports are outside the import census and their module reads outside
  `_MODULE_READS`.
Added in S3-CTL r8 (CF7-F1): `__setattr__`, `__delattr__`. `object.__setattr__`
with a computed name (`"__co" + "de__"`) swaps a function's code for one that
`compile` built, with no refused token (plant `r8_setattr_compile`). The real
tree's one call, `object.__setattr__(self, "imagery_roles", ...)` in
`scripts/sandbox_policy.py`, is admitted by `_real_setattr` alone.
Accepted residual, unchanged: a cross-module runtime-computed alias.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
import sys
import tempfile
import textwrap
import tomllib
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.privacy.rules_config import RulesRefusal, load_rules

ROOT = Path(__file__).resolve().parents[2]
PIN = Path(__file__).resolve().parent / "fixtures" / "decision_0035_control_pin.json"

RULES_PY = "custodian/src/eii_custodian/privacy/rules_config.py"
RULES_TOML = "custodian/src/eii_custodian/privacy/rules.toml"
DOC06 = "docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md"
DOC12 = "docs/12_TESTING_AND_QUALITY.md"
AUDIENCE = "scripts/audience_origin_rules.json"
CHECKER = "scripts/check_audience_origin.py"
BACKEND = "product/src/eii_product/backend_origin.py"
PROFILES_PY = "scripts/sandbox_profiles.py"
POLICY_PY = "scripts/sandbox_policy.py"
SANDBOX_PY = "scripts/sandbox_check.py"
ENGINE_PY = "scripts/extension_tree.py"
CASES_PY = "scripts/ci_plant_cases.py"
PUBLIC_PY = "custodian/src/eii_custodian/release/public_only.py"
MANIFEST_PY = "core/src/eii_core/manifest.py"

DECLARING = (
    RULES_PY,
    RULES_TOML,
    DOC06,
    DOC12,
    AUDIENCE,
    CHECKER,
    BACKEND,
    PROFILES_PY,
    POLICY_PY,
    SANDBOX_PY,
    ENGINE_PY,
    CASES_PY,
    PUBLIC_PY,
    MANIFEST_PY,
)

KEYS = (
    "rules_config",
    "doc06_section5",
    "prv45",
    "prv116",
    "gates",
    "audience_retained",
    "sandbox_profiles",
    "sandbox_policy",
    "sandbox_check",
    "ci_cases",
    "public_only",
)

RULE_HEADER = "| Rule code, A / B |"
PRV45_ANCHOR = "| PRV-45 |"
PRV116_ANCHOR = "| PRV-116 |"
PREDICATE_HEADER = "| Predicate type |"
SECTION_5 = "## 5. Slice gates and the evidence that proves them"
SECTION_51 = "### 5.1 Tests added by decisions 0016 and 0017"
SECTION_6 = "## 6. Definition of done and evidence"
SUPPRESSION_IDS = (
    "en.suppressed",
    "ar.suppressed",
    "ar.suppressed.def",
    "ar.suppressed.f",
    "ar.suppressed.f.def",
)
CLAIM_DECLS = (
    "_CLAIM_EN",
    "_CLAIM_AR",
    "_CLAIM",
    "_ARABIC_MARKS",
    "_ALEF",
    "_normalise",
    "claim_word_in",
)
PRV116_TOKENS = (
    "solved exactly over the rationals",
    "OPTIMAL",
    "UNBOUNDED",
    "FEASIBLE",
    "INFEASIBLE",
    "INF_OR_UNBD",
    "audit_headcount_width",
    "(upper - lower) / max(1, (upper + lower) / 2)",
    "audit_wage_relative_width",
)
_PAIR = re.compile(
    r"`(?P<code>[a-z0-9_]+)` (?P<a>\d+(?:\.\d+)?%?) / (?P<b>\d+(?:\.\d+)?%?)\Z"
)
_TWO = re.compile(
    r"`(?P<c1>[a-z0-9_]+)` (?P<a1>\d+) / (?P<b1>\d+); "
    r"`(?P<c2>[a-z0-9_]+)` (?P<a2>\d+) / (?P<b2>\d+)\Z"
)
_UNSET = re.compile(
    r"`(?P<code>window_months|round_movement)` "
    r"(?P<phrase>set at the slice S1 gate \([^)]*\))\Z"
)
_TOLERANCE = re.compile(
    r"`(feasibility_tolerance|integrality_tolerance|optimality_tolerance|"
    r"outward_bound) = (1[eE]-\d+)`"
)
_DELTA = re.compile(
    r"`delta` (\d+\.\d+) \(A\) or (\d+\.\d+) \(B\) read from rule `money_delta`"
)
_TST = re.compile(r"TST-(\d+)(?:\s+to\s+TST-(\d+))?")
_DEF = re.compile(r"\| (TST-(\d+)) \|")


class ExtractionFailure(Exception):
    """A present declaration could not be read whole."""


def _canon(value: object) -> str:
    """Canonical JSON for equality. Key order is not a control."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sort_key(value: object) -> str:
    return _canon(value)


def _read(
    root: Path,
    relative: str,
    overlays: Mapping[str, str] | None,
    allow_absent: bool,
) -> str | None:
    if overlays is not None and relative in overlays:
        return overlays[relative]
    path = root / relative
    if not path.is_file():
        if allow_absent:
            return None
        raise ExtractionFailure(f"missing {relative}")
    return path.read_text(encoding="utf-8")


def _one(text: str, anchor: str) -> None:
    count = text.count(anchor)
    if count != 1:
        raise ExtractionFailure(f"anchor {anchor} count {count}")


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _cells(line: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            buf.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(char)
    parts.append("".join(buf).strip())
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _table(text: str, header: str) -> list[list[str]]:
    _one(text, header)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(header):
            continue
        rows: list[list[str]] = []
        for raw in lines[index + 2 :]:
            if not raw.startswith("|"):
                break
            rows.append(_cells(raw))
        return rows
    raise ExtractionFailure(f"table {header}")


def _slice(text: str, start: str, end: str) -> str:
    _one(text, start)
    _one(text, end)
    return text.split(start, 1)[1].split(end, 1)[0]


_BUILTIN_CALLS = frozenset({"frozenset", "tuple"})
_DYNAMIC_WRITES = frozenset(
    {"globals", "vars", "locals", "exec", "eval", "setattr", "delattr", "__import__"}
)
# The only uses a mutable projected value may have in its declaring file. Each
# is a read the current sources need or a plain read named by the brief; any
# other appearance (alias, call argument, starred or keyword passing, return,
# container element, other attribute, unbound method) is refused.
_CONTENT_METHODS = frozenset({"get", "items"})
_PATTERN_METHODS = frozenset({"search", "sub"})
_READ_CALLS = frozenset({"len", "list"})
# Builtins the allow-list and the evaluator rely on: a binding of one in any
# scope of a declaring file is refused, and so is any reach to the builtins
# module (S3-CTL r4, sub-class a).
_RELIED = _BUILTIN_CALLS | _READ_CALLS
_BUILTINS_MODULE = frozenset({"builtins", "__builtins__"})
# Allow-list of namespace reach (S3-CTL r5): a token that reaches a module's
# own namespace object, a frame's or function's globals, the builtins module,
# or rebinds a name by a computed string refuses wherever a declaring file
# names it (identifier, attribute, import, parameter or string constant).
_NAMESPACE = _BUILTINS_MODULE | frozenset(
    {
        "modules",
        "globals",
        "vars",
        "locals",
        "setattr",
        "delattr",
        "getattr",
        "__getattribute__",
        "attrgetter",
        "methodcaller",
        "__dict__",
        "__globals__",
        "__self__",
        "__loader__",
        "__spec__",
        "__import__",
        "importlib",
        "exec",
        "eval",
        "inspect",
        "gc",
        "ctypes",
        "_getframe",
        "currentframe",
        "f_globals",
        "f_locals",
        "f_builtins",
        "f_back",
        "tb_frame",
        "gi_frame",
        "cr_frame",
        "ag_frame",
        # S3-CTL r7: code objects and the walk from `object` to a loader.
        "__code__",
        "__replace__",
        "co_names",
        "co_consts",
        "co_code",
        "co_varnames",
        "co_freevars",
        "co_cellvars",
        "co_qualname",
        "gi_code",
        "cr_code",
        "ag_code",
        "f_code",
        "__subclasses__",
        # S3-CTL r8 (CF7-F1): the attribute setters reach a function's
        # `__code__` by a computed name; the real tree's one setter call is
        # admitted by `_real_setattr`, every other form refuses.
        "__setattr__",
        "__delattr__",
    }
)
# `sys` is admitted only as the real tree uses it: `import sys` without an
# alias, and a load of one of these attributes; every other form refuses.
_SYS_READS = frozenset({"argv", "executable", "exit", "stderr", "stdout"})
# Allow-list of imports (S3-CTL r6): every one-name import statement the real
# tree's declaring files hold today, at any scope. `test_import_census_*`
# asserts the census equals this literal, so a real change is a visible edit.
# A declaring file may hold only these, and never one naming its own module.
_IMPORTS = frozenset(
    {
        "from __future__ import annotations",
        "from collections.abc import Callable",
        "from collections.abc import Iterator",
        "from collections.abc import Mapping",
        "from collections.abc import Sequence",
        "from contextlib import contextmanager",
        "from dataclasses import dataclass",
        "from dataclasses import field",
        "from eii_core.manifest import ColumnSpec",
        "from eii_core.manifest import FORBIDDEN_PUBLIC_ONLY",
        "from eii_core.manifest import by_name",
        "from eii_core.manifest import canonical_json",
        "from eii_core.manifest import engine_versions_reason",
        "from eii_core.manifest import listed_inputs_reason",
        "from eii_core.manifest import release_hash",
        "from eii_core.manifest import schema_document",
        "from eii_core.manifest import schema_hash",
        "from eii_core.manifest import written_by_privacy",
        "from eii_core.source_chain import ChainTable",
        "from eii_core.source_chain import SourceChainRefusal",
        "from eii_core.source_chain import require_public_chain",
        "from eii_product.assistant.catalogue.load import catalogue_directory",
        "from eii_product.assistant.catalogue.load import load_catalogue",
        "from eii_product.assistant.catalogue.schema import Refusal",
        "from eii_product.assistant.templates.status import STEP_LABELS",
        "from eii_product.backend_origin import BackendOriginRefusal",
        "from eii_product.backend_origin import GENERATED_ORIGINS",
        "from eii_product.backend_origin import LEVELS",
        "from eii_product.backend_origin import MARKER_KEYS",
        "from eii_product.backend_origin import require_generated_output",
        "from eii_product.backend_origin import require_truthful_chain",
        "from html import unescape",
        "from pathlib import Path",
        "from typing import Any",
        "from typing import NoReturn",
        "from urllib.parse import unquote",
        "import argparse",
        "import dataclasses",
        "import duckdb",
        "import errno",
        "import extension_tree",
        "import hashlib",
        "import json",
        "import os",
        "import random",
        "import re",
        "import sandbox_launch as launch",
        "import sandbox_policy",
        "import sandbox_profiles as tables",
        "import shutil",
        "import socket",
        "import stat",
        "import string",
        "import subprocess",
        "import sys",
        "import tempfile",
        "import tomllib",
        "import unicodedata",
        "import yaml",
    }
)
# Census of module reads (S3-CTL r7): every `module.attribute` load the real
# tree's declaring files make on a name an `import` binds. A module name may
# appear only as one of these loads; `test_module_read_census_*` asserts the
# census equals this literal.
_MODULE_READS = frozenset(
    {
        "argparse.ArgumentParser",
        "argparse.Namespace",
        "dataclasses.dataclass",
        "dataclasses.replace",
        "duckdb.connect",
        "errno.ELOOP",
        "extension_tree.ENGINE",
        "extension_tree.PLATFORM",
        "hashlib.sha256",
        "json.JSONDecodeError",
        "json.dumps",
        "json.loads",
        "os.O_CLOEXEC",
        "os.O_DIRECTORY",
        "os.O_NOFOLLOW",
        "os.O_NONBLOCK",
        "os.O_PATH",
        "os.O_RDONLY",
        "os.close",
        "os.fstat",
        "os.listdir",
        "os.open",
        "os.pread",
        "os.readlink",
        "os.urandom",
        "random.Random",
        "re.IGNORECASE",
        "re.Pattern",
        "re.compile",
        "sandbox_launch.Interpreter",
        "sandbox_launch.Layout",
        "sandbox_launch.ROOT",
        "sandbox_launch.SandboxError",
        "sandbox_launch.build_argv",
        "sandbox_launch.check_profile",
        "sandbox_launch.close_all",
        "sandbox_launch.current_venv",
        "sandbox_launch.interpreter_for",
        "sandbox_launch.open_sources",
        "sandbox_launch.profile_named",
        "sandbox_launch.python_command",
        "sandbox_launch.run_in_sandbox",
        "sandbox_policy.PolicyInput",
        "sandbox_policy.judge",
        "sandbox_profiles.BWRAP",
        "sandbox_profiles.PROFILES",
        "sandbox_profiles.Profile",
        "shutil.rmtree",
        "shutil.which",
        "socket.AF_UNIX",
        "socket.socket",
        "stat.S_ISDIR",
        "stat.S_ISLNK",
        "stat.S_ISREG",
        "string.ascii_uppercase",
        "subprocess.run",
        "sys.argv",
        "sys.executable",
        "sys.exit",
        "sys.stderr",
        "sys.stdout",
        "tempfile.TemporaryDirectory",
        "tomllib.TOMLDecodeError",
        "tomllib.loads",
        "unicodedata.category",
        "unicodedata.normalize",
        "yaml.safe_load",
    }
)
# Methods that change their receiver in place (S3-CTL r6); any dunder too.
_MUTATORS = frozenset(
    {
        "add",
        "append",
        "clear",
        "difference_update",
        "discard",
        "extend",
        "insert",
        "intersection_update",
        "pop",
        "popitem",
        "remove",
        "reverse",
        "setdefault",
        "sort",
        "symmetric_difference_update",
        "update",
    }
)


def _simple(node: ast.AST) -> tuple[str, ast.expr] | None:
    """The one write form the walker evaluates: NAME = value."""
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id, node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        return node.target.id, node.value
    return None


def _names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple | ast.List):
        return [name for item in target.elts for name in _names(item)]
    if isinstance(target, ast.Starred):
        return _names(target.value)
    return []


def _scope(body: list[ast.stmt]) -> list[ast.stmt]:
    """Every statement that runs in module scope, nested blocks included."""
    found: list[ast.stmt] = []
    for node in body:
        found.append(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler | ast.match_case):
                found.extend(_scope(child.body))
        for field in ("body", "orelse", "finalbody"):
            found.extend(_scope(getattr(node, field, [])))
    return found


def _walrus(node: ast.AST) -> list[str]:
    found: list[str] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt | ast.Lambda):
            continue
        if isinstance(child, ast.NamedExpr):
            found.extend(_names(child.target))
        found.extend(_walrus(child))
    return found


def _binds(node: ast.stmt) -> list[str]:
    """Names one module-scope statement binds or unbinds, in any form."""
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign | ast.Delete):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign | ast.AugAssign | ast.For | ast.AsyncFor):
        targets = [node.target]
    elif isinstance(node, ast.With | ast.AsyncWith):
        targets = [item.optional_vars for item in node.items if item.optional_vars]
    elif isinstance(node, ast.TypeAlias):
        targets = [node.name]
    found = [name for target in targets for name in _names(target)]
    if isinstance(node, ast.Try | ast.TryStar):
        found.extend(handler.name for handler in node.handlers if handler.name)
    if isinstance(node, ast.Import | ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                raise ExtractionFailure("star import")
            found.append(alias.asname or alias.name.split(".")[0])
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        found.append(node.name)
    if isinstance(node, ast.Match):
        for case in node.cases:
            for sub in ast.walk(case.pattern):
                if isinstance(sub, ast.MatchAs | ast.MatchStar) and sub.name:
                    found.append(sub.name)
                if isinstance(sub, ast.MatchMapping) and sub.rest:
                    found.append(sub.rest)
    return found + _walrus(node)


def _writes(tree: ast.Module) -> dict[str, list[ast.AST]]:
    """Every statically visible write to a module name, by name."""
    found: dict[str, list[ast.AST]] = {}
    for statement in _scope(tree.body):
        for name in _binds(statement):
            found.setdefault(name, []).append(statement)
    for node in ast.walk(tree):
        if isinstance(node, ast.Global | ast.Nonlocal):
            for name in node.names:
                found.setdefault(name, []).append(node)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DYNAMIC_WRITES
        ):
            raise ExtractionFailure(f"dynamic write {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr == "__dict__":
            raise ExtractionFailure("dynamic write __dict__")
    return found


def _root(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute | ast.Subscript | ast.Starred):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _mutated(tree: ast.Module) -> set[str]:
    """Names changed in place through an item or attribute target."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute | ast.Subscript) and isinstance(
            node.ctx, ast.Store | ast.Del
        ):
            root = _root(node)
            if root is not None:
                found.add(root)
    return found


def _frozen(node: ast.expr, frozen: set[str]) -> bool:
    """True when a declared value holds nothing that can change in place."""
    if isinstance(node, ast.Constant | ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        return node.id in frozen
    if isinstance(node, ast.BinOp):
        return _frozen(node.left, frozen) and _frozen(node.right, frozen)
    if isinstance(node, ast.Tuple):
        return all(_frozen(item, frozen) for item in node.elts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _BUILTIN_CALLS
        and len(node.args) == 1
        and not node.keywords
    ):
        arg = node.args[0]
        items = arg.elts if isinstance(arg, ast.Set | ast.List | ast.Tuple) else [arg]
        return all(_frozen(item, frozen) for item in items)
    return False


def _pattern(value: ast.expr, writes: Mapping[str, list[ast.AST]]) -> bool:
    """True for `re.compile(...)` with `re` bound once, by `import re`."""
    found = writes.get("re", [])
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "compile"
        and isinstance(value.func.value, ast.Name)
        and value.func.value.id == "re"
        and len(found) == 1
        and isinstance(found[0], ast.Import)
        and [(a.name, a.asname) for a in found[0].names] == [("re", None)]
    )


def _mutable(
    tree: ast.Module, protected: set[str], writes: Mapping[str, list[ast.AST]]
) -> dict[str, str]:
    """Protected names whose value can change in place, each mapped to its
    kind: "items" when every item it holds (dict keys and values, list or set
    members) is frozen, "pattern" for a compiled pattern, else "opaque"."""
    values: dict[str, ast.expr] = {}
    for node in tree.body:
        simple = _simple(node)
        if simple is not None and simple[0] in protected:
            values[simple[0]] = simple[1]
    frozen: set[str] = set()
    while True:
        more = {n for n, v in values.items() if n not in frozen and _frozen(v, frozen)}
        if not more:
            break
        frozen |= more
    found: dict[str, str] = {}
    for name, value in values.items():
        if name in frozen:
            continue
        items: list[ast.expr | None] = []
        if isinstance(value, ast.Dict):
            items = [*value.keys, *value.values]
        elif isinstance(value, ast.List | ast.Set):
            items = list(value.elts)
        if items and all(item is not None and _frozen(item, frozen) for item in items):
            found[name] = "items"
        else:
            found[name] = "pattern" if _pattern(value, writes) else "opaque"
    return found


def _bound(tree: ast.Module) -> set[str]:
    """Every name bound in any scope of a file, in any form."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            found.add(node.id)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            found.update(node.names)
        elif isinstance(node, ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple):
            found.add(node.name)
        elif isinstance(node, ast.stmt):
            found.update(_binds(node))
    return found


def _tokens(node: ast.AST) -> list[str]:
    """Every dotted part of every name or string one node carries."""
    found: list[str] = []
    for field in ("id", "attr", "value", "name", "asname", "module", "arg"):
        value = getattr(node, field, None)
        if isinstance(value, str):
            found.extend(value.split("."))
    if isinstance(node, ast.Global | ast.Nonlocal):
        found.extend(node.names)
    return found


def _real_sys(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    """True for `import sys` or a load of `sys.<one of _SYS_READS>`."""
    parent = parents.get(node)
    if isinstance(node, ast.alias):
        return node.name == "sys" and not node.asname and isinstance(parent, ast.Import)
    return (
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and isinstance(parent, ast.Attribute)
        and parent.value is node
        and isinstance(parent.ctx, ast.Load)
        and parent.attr in _SYS_READS
    )


def _real_setattr(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    """True only for the real tree's call
    `object.__setattr__(self, "imagery_roles", <value>)`: three positional
    arguments, no keyword, no starred argument. The caller passes only a
    node whose token is `__setattr__`, so an attribute node here is that
    attribute; the func of a call is always a load."""
    call = parents.get(node)
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "object"
        and isinstance(call, ast.Call)
        and call.func is node
        and not call.keywords
        and len(call.args) == 3
        and not any(isinstance(a, ast.Starred) for a in call.args)
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "self"
        and isinstance(call.args[1], ast.Constant)
        and call.args[1].value == "imagery_roles"
    )


def _refuse_redirects(tree: ast.Module, parents: Mapping[ast.AST, ast.AST]) -> None:
    """Sub-class (a): a relied-on builtin is never rebound, in any scope, and
    no token of `_NAMESPACE` nor any non-real form of `sys` is ever named."""
    shadowed = sorted(_bound(tree) & _RELIED)
    if shadowed:
        raise ExtractionFailure(f"shadowed {shadowed[0]}")
    for node in ast.walk(tree):
        for token in _tokens(node):
            if token == "__setattr__" and _real_setattr(node, parents):
                continue
            if token in _NAMESPACE or (token == "sys" and not _real_sys(node, parents)):
                raise ExtractionFailure(f"namespace reach {token}")


def _import_lines(tree: ast.AST) -> list[tuple[str, list[str]]]:
    """Each import of a file, at any scope, as one-name statement text with
    the modules it names."""
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(ast.unparse(ast.Import([a])), [a.name]) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = "." * node.level + (node.module or "")
            found += [
                (
                    ast.unparse(ast.ImportFrom(node.module, [a], node.level)),
                    [base, f"{base}.{a.name}"],
                )
                for a in node.names
            ]
    return found


def _own_module(path: str) -> str:
    """A declaring file's import name: dotted after `src`, else its stem."""
    parts = Path(path).with_suffix("").parts
    return ".".join(parts[parts.index("src") + 1 :] if "src" in parts else parts[-1:])


def _refuse_imports(tree: ast.AST, path: str) -> None:
    """S3-CTL r6: only an import of `_IMPORTS`, and none of the file's own
    module or a package or submodule of it."""
    own = _own_module(path)
    for line, modules in _import_lines(tree):
        if line not in _IMPORTS:
            raise ExtractionFailure(f"import outside census: {line}")
        for module in modules:
            if f"{module}.".startswith(f"{own}.") or f"{own}.".startswith(f"{module}."):
                raise ExtractionFailure(f"import of own module: {line}")


def _module_names(tree: ast.AST) -> dict[str, str]:
    """Each name an `import` binds, with the module it binds."""
    return {
        alias.asname or alias.name: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }


def _refuse_module_reads(tree: ast.Module, parents: Mapping[ast.AST, ast.AST]) -> None:
    """S3-CTL r7: a module name appears only as a load of `_MODULE_READS`."""
    modules = _module_names(tree)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and node.id in modules):
            continue
        read = parents.get(node)
        name = modules[node.id]
        if not (
            isinstance(read, ast.Attribute)
            and read.value is node
            and isinstance(read.ctx, ast.Load)
        ):
            raise ExtractionFailure(f"namespace reach {name}")
        if f"{name}.{read.attr}" not in _MODULE_READS:
            raise ExtractionFailure(f"namespace reach {name}.{read.attr}")


def _carried(node: ast.AST, tainted: set[str]) -> bool:
    """True when an expression's value may be a tainted object itself."""
    if isinstance(node, ast.Name):
        return node.id in tainted
    if isinstance(node, ast.Attribute | ast.Subscript | ast.Starred | ast.NamedExpr):
        return _carried(node.value, tainted)
    parts: list[ast.expr | None] = []
    if isinstance(node, ast.IfExp):
        parts = [node.body, node.orelse]
    elif isinstance(node, ast.Tuple | ast.List | ast.Set):
        parts = list(node.elts)
    elif isinstance(node, ast.Dict):
        parts = [*node.keys, *node.values]
    elif isinstance(node, ast.BoolOp):
        parts = list(node.values)
    return any(part is not None and _carried(part, tainted) for part in parts)


def _bindings(node: ast.AST) -> list[tuple[list[ast.AST], ast.AST]]:
    """Each (targets, value) pair one node binds, in any binding form."""
    if isinstance(node, ast.Assign):
        return [(list(node.targets), node.value)]
    if isinstance(node, ast.AnnAssign | ast.NamedExpr) and node.value is not None:
        return [([node.target], node.value)]
    if isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
        return [([node.target], node.iter)]
    if isinstance(node, ast.withitem) and node.optional_vars is not None:
        return [([node.optional_vars], node.context_expr)]
    if isinstance(node, ast.arguments):
        names: list[ast.AST] = [*node.posonlyargs, *node.args, *node.kwonlyargs]
        return [
            (names, value) for value in [*node.defaults, *node.kw_defaults] if value
        ]
    return []


def _aliases(tree: ast.Module, roots: set[str]) -> set[str]:
    """`roots` and every name bound, in any form, from one of them or from an
    alias of one; an item or attribute target taints its root name."""
    tainted = set(roots)
    while True:
        more: set[str] = set()
        for node in ast.walk(tree):
            for targets, value in _bindings(node):
                if not _carried(value, tainted):
                    continue
                for target in targets:
                    root = _root(target)
                    more.update(_names(target) + ([root] if root else []))
                    if isinstance(target, ast.arg):
                        more.add(target.arg)
        if more <= tainted:
            return tainted
        tainted |= more


def _refuse_alias_writes(tree: ast.Module, protected: set[str]) -> None:
    """S3-CTL r6: no in-place change whose receiver is a protected name, a
    name an import binds, or any alias of one."""
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for name in _binds(node)
    }
    tainted = _aliases(tree, imported | protected)
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and _carried(node.target, tainted):
            raise ExtractionFailure(f"alias augmented line {node.lineno}")
        if (
            isinstance(node, ast.Attribute | ast.Subscript)
            and isinstance(node.ctx, ast.Store | ast.Del)
            and _carried(node.value, tainted)
        ):
            raise ExtractionFailure(f"alias write line {node.lineno}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and (node.func.attr in _MUTATORS or node.func.attr.startswith("__"))
            and _carried(node.func.value, tainted)
        ):
            raise ExtractionFailure(f"alias mutation {node.func.attr}")


def _view_targets(
    call: ast.Call, parents: Mapping[ast.AST, ast.AST]
) -> list[str] | None:
    """Sub-class (c): where a live view (`.items()`) of a mutable value may
    go. Direct iteration or a discarded statement binds nothing; a plain
    assignment, as the whole value or one item of a tuple value, binds names
    that must never be read. Any other use returns None (refused)."""
    node: ast.AST = call
    parent = parents[node]
    if isinstance(parent, ast.For | ast.AsyncFor | ast.comprehension):
        return [] if parent.iter is node else None
    if isinstance(parent, ast.Expr):
        return []
    if isinstance(parent, ast.Tuple) and isinstance(parent.ctx, ast.Load):
        node, parent = parent, parents[parent]
    targets: list[ast.expr] = []
    if isinstance(parent, ast.Assign) and parent.value is node:
        targets = parent.targets
    elif isinstance(parent, ast.AnnAssign) and parent.value is node:
        targets = [parent.target]
    if targets and all(isinstance(target, ast.Name) for target in targets):
        return [target.id for target in targets if isinstance(target, ast.Name)]
    return None


def _read_only(node: ast.Name, parents: Mapping[ast.AST, ast.AST], kind: str) -> bool:
    """One admitted read-only use of a mutable value of `kind` (`_mutable`);
    "items" holds only frozen items, so a read that hands out an item is safe."""
    parent = parents[node]
    items = kind == "items"
    if isinstance(parent, ast.Compare):
        # Sub-class (b): only the right-hand container of one unchained
        # in / not in, so no other operand's dunder ever receives the value.
        return (
            items
            and len(parent.ops) == 1
            and isinstance(parent.ops[0], ast.In | ast.NotIn)
            and parent.comparators[0] is node
        )
    if isinstance(parent, ast.Subscript):
        return parent.value is node and isinstance(parent.ctx, ast.Load) and items
    if isinstance(parent, ast.For | ast.AsyncFor | ast.comprehension):
        return parent.iter is node and items
    if isinstance(parent, ast.Call):
        func = parent.func
        return (
            isinstance(func, ast.Name)
            and func.id in _READ_CALLS
            and parent.args == [node]
            and not parent.keywords
            and (func.id == "len" or items)
        )
    if isinstance(parent, ast.Attribute):
        call = parents.get(parent)
        if not isinstance(call, ast.Call) or call.func is not parent:
            return False
        if parent.attr in _PATTERN_METHODS:
            return kind == "pattern"
        if parent.attr == "items":
            return items and _view_targets(call, parents) is not None
        return parent.attr in _CONTENT_METHODS and items
    return False


def _refuse_escapes(tree: ast.Module, protected: set[str]) -> None:
    """Refuse every appearance of a mutable protected value but a read-only
    one, every redirect of a relied-on builtin, and every read of a name that
    holds a live view of a mutable value."""
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    _refuse_redirects(tree, parents)
    _refuse_alias_writes(tree, protected)
    _refuse_module_reads(tree, parents)
    mutable = _mutable(tree, protected, _writes(tree))
    holders: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and node.id in mutable):
            continue
        if isinstance(node.ctx, ast.Load) and not _read_only(
            node, parents, mutable[node.id]
        ):
            raise ExtractionFailure(f"escape of {node.id} line {node.lineno}")
        attribute = parents.get(node)
        if isinstance(attribute, ast.Attribute) and attribute.attr == "items":
            call = parents[attribute]
            if isinstance(call, ast.Call):
                holders.update(_view_targets(call, parents) or [])
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in holders:
            if isinstance(node.ctx, ast.Load):
                raise ExtractionFailure(f"view read {node.id} line {node.lineno}")


def _protect(tree: ast.Module, wanted: set[str]) -> set[str]:
    """Refuse every write the walker cannot evaluate to a projected name.

    A projected name, and each name its value reads, must have exactly one
    write in the module. A projected name's write must be a top-level
    NAME = value (or a top-level def for a projected function). A mutable
    one may appear only in a read-only use (`_refuse_escapes`). Returns the
    projected names with their value dependencies.
    """
    writes = _writes(tree)
    mutated = _mutated(tree)
    protected: set[str] = set()
    todo = sorted(wanted)
    while todo:
        name = todo.pop()
        if name in protected:
            continue
        protected.add(name)
        if name in mutated:
            raise ExtractionFailure(f"in-place write {name}")
        found = writes.get(name, [])
        if name in _BUILTIN_CALLS and name not in wanted:
            if found:
                raise ExtractionFailure(f"shadowed {name}")
            continue
        if len(found) != 1:
            raise ExtractionFailure(f"{len(found)} writes to {name}")
        node = found[0]
        top = any(node is item for item in tree.body)
        simple = _simple(node) if top else None
        if simple is not None:
            todo.extend(
                sub.id for sub in ast.walk(simple[1]) if isinstance(sub, ast.Name)
            )
        elif name in wanted and not (
            top and isinstance(node, ast.FunctionDef) and node.name == name
        ):
            raise ExtractionFailure(f"unsupported write to {name}")
    _refuse_escapes(tree, protected)
    return protected


def _definition(tree: ast.Module, name: str) -> ast.AST:
    """The one protected top-level write of a projected name."""
    _protect(tree, {name})
    return _writes(tree)[name][0]


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    node = _definition(tree, name)
    if not isinstance(node, ast.FunctionDef):
        raise ExtractionFailure(f"function {name}")
    return node


def _one_match(found: list[Any], what: str) -> Any:
    if len(found) != 1:
        raise ExtractionFailure(f"{what} count {len(found)}")
    return found[0]


def _eval(node: ast.AST, env: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if node.value is None or type(node.value) in {bool, int, float, str}:
            return node.value
        raise ExtractionFailure("constant")
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ExtractionFailure(f"name {node.id}")
        return env[node.id]
    if isinstance(node, ast.Tuple | ast.List):
        return [_eval(item, env) for item in node.elts]
    if isinstance(node, ast.Set):
        return [_eval(item, env) for item in node.elts]
    if isinstance(node, ast.Dict):
        out: dict[str, Any] = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                raise ExtractionFailure("dict unpack")
            got = _eval(key, env)
            if not isinstance(got, str):
                raise ExtractionFailure("dict key")
            out[got] = _eval(value, env)
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mult):
        left = _eval(node.left, env)
        right = _eval(node.right, env)
        if type(left) is not int or type(right) is not int:
            raise ExtractionFailure("arithmetic")
        if isinstance(node.op, ast.Add):
            return left + right
        return left * right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if isinstance(value, ast.FormattedValue):
                parts.append(_formatted(value, env))
                continue
            raise ExtractionFailure("format")
        return "".join(parts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return _call(node, env)
    raise ExtractionFailure(f"node {type(node).__name__}")


def _formatted(node: ast.FormattedValue, env: Mapping[str, Any]) -> str:
    value = node.value
    if (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == "extension_tree"
        and value.attr == "ENGINE"
    ):
        engine = env.get("__engine__")
        if not isinstance(engine, str):
            raise ExtractionFailure("engine")
        return engine
    raise ExtractionFailure("format value")


def _call(node: ast.Call, env: Mapping[str, Any]) -> Any:
    if not isinstance(node.func, ast.Name):
        raise ExtractionFailure("call")
    name = node.func.id
    if name == "frozenset" and len(node.args) == 1 and not node.keywords:
        items = _eval(node.args[0], env)
        if not isinstance(items, list):
            raise ExtractionFailure("frozenset")
        return sorted(items, key=_sort_key)
    if name == "tuple" and len(node.args) == 1 and not node.keywords:
        items = _eval(node.args[0], env)
        if not isinstance(items, list):
            raise ExtractionFailure("tuple call")
        return items
    classes = env.get("__classes__", {})
    if name in classes:
        return _construct(node, classes[name], env)
    raise ExtractionFailure(f"call {name}")


def _dataclass_fields(node: ast.ClassDef) -> list[tuple[str, ast.expr | None]]:
    """Field names and default expressions, read from the class source.

    Only a plain dataclass of annotated fields is read; any decorator option,
    base, method or other statement that can change construction is refused.
    """
    if node.bases or node.keywords or len(node.decorator_list) != 1:
        raise ExtractionFailure(f"class {node.name}")
    decorator = node.decorator_list[0]
    options: list[ast.keyword] = []
    if isinstance(decorator, ast.Call) and not decorator.args:
        options = decorator.keywords
        decorator = decorator.func
    if not isinstance(decorator, ast.Name) or decorator.id != "dataclass":
        raise ExtractionFailure(f"decorator {node.name}")
    if any(option.arg != "frozen" for option in options):
        raise ExtractionFailure(f"dataclass option {node.name}")
    body = node.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        body = body[1:]
    fields: list[tuple[str, ast.expr | None]] = []
    for item in body:
        if (
            not isinstance(item, ast.AnnAssign)
            or not isinstance(item.target, ast.Name)
            or not isinstance(item.annotation, ast.Name)
        ):
            raise ExtractionFailure(f"class statement {node.name}")
        if any(item.target.id == name for name, _default in fields):
            raise ExtractionFailure(f"duplicate field {node.name}.{item.target.id}")
        fields.append((item.target.id, item.value))
    return fields


def _construct(
    node: ast.Call, cls: ast.ClassDef, env: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind a dataclass call as Python would; omitted fields take source defaults."""
    fields = _dataclass_fields(cls)
    if len(node.args) > len(fields):
        raise ExtractionFailure(f"arguments {cls.name}")
    values: dict[str, Any] = {}
    for (name, _default), arg in zip(fields, node.args, strict=False):
        if isinstance(arg, ast.Starred):
            raise ExtractionFailure(f"arguments {cls.name}")
        values[name] = _eval(arg, env)
    names = [name for name, _default in fields]
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg not in names or keyword.arg in values:
            raise ExtractionFailure(f"keyword {cls.name}.{keyword.arg}")
        values[keyword.arg] = _eval(keyword.value, env)
    for name, default in fields:
        if default is not None:
            resolved = _eval(default, {})
            values.setdefault(name, resolved)
        elif name not in values:
            raise ExtractionFailure(f"missing {cls.name}.{name}")
    return {name: values[name] for name in names}


def _dataclasses(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            _root(item.func if isinstance(item, ast.Call) else item) == "dataclass"
            for item in node.decorator_list
        )
    }


def _env(text: str, wanted: set[str], engine: str | None = None) -> dict[str, Any]:
    tree = ast.parse(text)
    protected = _protect(tree, wanted)
    env: dict[str, Any] = {"__classes__": _dataclasses(tree)}
    if engine is not None:
        env["__engine__"] = engine
    for node in tree.body:
        simple = _simple(node)
        if simple is None:
            continue
        target, value = simple
        try:
            env[target] = _eval(value, env)
        except ExtractionFailure:
            if target in protected:
                raise
    missing = sorted(wanted - set(env))
    if missing:
        raise ExtractionFailure("missing " + ", ".join(missing))
    return env


def _pick(env: Mapping[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    return {name: env[name] for name in names}


def _retired_pin(codes: list[str]) -> dict[str, Any]:
    """Pin the retired set by count and digest, not by copying its spellings."""
    stand_ins = _retired_stand_ins(codes)
    for code, stand_in in stand_ins.items():
        if code in stand_in:
            raise ExtractionFailure("retired stand-in")
    return {
        "count": len(codes),
        "sha256": hashlib.sha256(_canon(codes).encode("utf-8")).hexdigest(),
    }


def _retired_stand_ins(codes: list[str]) -> dict[str, str]:
    return {code: f"retired-code-{index}" for index, code in enumerate(codes)}


def _redact_retired(text: str, codes: list[str]) -> str:
    stand_ins = _retired_stand_ins(codes)
    redacted = text
    for code in sorted(stand_ins, key=len, reverse=True):
        redacted = redacted.replace(code, stand_ins[code])
    for code in codes:
        if code in redacted:
            raise ExtractionFailure("retired spelling in assertion")
    return redacted


def _rules_py(text: str) -> dict[str, Any]:
    wanted = {
        "WINDOW_MIN",
        "WINDOW_MAX",
        "LATEST_COMPLETE_INDEX",
        "PARAMETER_SETS",
        "EXPORTED_SETS",
        "TASK_PLACEMENTS",
        "TASK_RULE_SETS",
        "TASK_UNITS",
        "RETIRED_CODES",
        "SET_RULE_CODES",
        "SHARED_RULE_CODES",
        "ENTRY_FIELD_ORDER",
        "ENTRY_FIELDS",
        "RECORD_FIELDS",
    }
    picked = _pick(_env(text, wanted), tuple(sorted(wanted)))
    codes = _strings(picked["RETIRED_CODES"], "RETIRED_CODES")
    picked["RETIRED_CODES"] = _retired_pin(codes)
    return picked


def _toml_rows(text: str) -> list[dict[str, str]]:
    loaded = tomllib.loads(text)
    raw = loaded.get("rules_version")
    if not isinstance(raw, list):
        raise ExtractionFailure("rules_version")
    fields = (
        "rules_version_id",
        "parameter_set",
        "rule_code",
        "value",
        "unit",
        "description_en",
    )
    rows: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ExtractionFailure("toml row")
        row: dict[str, str] = {}
        for field in fields:
            value = item.get(field)
            if not isinstance(value, str):
                raise ExtractionFailure(f"toml {field}")
            row[field] = value
        if set(item) - set(fields):
            raise ExtractionFailure("toml extra")
        rows.append(row)
    return rows


def _code_cell(cell: str) -> list[dict[str, str]]:
    two = _TWO.fullmatch(cell)
    if two is not None:
        return [
            {"code": two.group("c1"), "A": two.group("a1"), "B": two.group("b1")},
            {"code": two.group("c2"), "A": two.group("a2"), "B": two.group("b2")},
        ]
    unset = _UNSET.fullmatch(cell)
    if unset is not None:
        return [
            {
                "code": unset.group("code"),
                "A": "unset",
                "B": "unset",
                "gate_phrase": unset.group("phrase"),
            }
        ]
    pair = _PAIR.fullmatch(cell)
    if pair is not None:
        return [
            {"code": pair.group("code"), "A": pair.group("a"), "B": pair.group("b")}
        ]
    raise ExtractionFailure(f"rule cell {cell}")


def _rule_codes(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for cells in _table(text, RULE_HEADER):
        if len(cells) != 3:
            raise ExtractionFailure("rule row")
        entries.extend(_code_cell(_collapse(cells[0])))
    return entries


def _requirement(text: str, anchor: str) -> str:
    for line in text.splitlines():
        if line.startswith(anchor):
            cells = _cells(line)
            if len(cells) != 2:
                raise ExtractionFailure(anchor)
            return _collapse(cells[1])
    raise ExtractionFailure(anchor)


def _prv45(text: str) -> dict[str, Any]:
    clause = _requirement(text, PRV45_ANCHOR)
    found = _DELTA.findall(clause)
    if len(found) != 1:
        raise ExtractionFailure("money_delta")
    return {"money_delta": {"A": found[0][0], "B": found[0][1]}, "clause": clause}


def _tolerances(clause: str) -> tuple[dict[str, str], str]:
    found = _TOLERANCE.findall(clause)
    names = [name for name, _literal in found]
    if names != [
        "feasibility_tolerance",
        "integrality_tolerance",
        "optimality_tolerance",
        "outward_bound",
    ]:
        raise ExtractionFailure("tolerance literal")
    literals = {name: literal.lower() for name, literal in found}

    def lower(match: re.Match[str]) -> str:
        return f"`{match.group(1)} = {match.group(2).lower()}`"

    normalised = _TOLERANCE.sub(lower, clause)
    for token in PRV116_TOKENS:
        if token not in normalised:
            raise ExtractionFailure(f"prv116 {token}")
    return literals, normalised


def _predicates(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cells in _table(text, PREDICATE_HEADER):
        if len(cells) != 3:
            raise ExtractionFailure("predicate row")
        ident = cells[0].strip("`")
        if re.fullmatch(r"[a-z0-9_]+", ident) is None:
            raise ExtractionFailure("predicate id")
        rows.append(
            {
                "id": ident,
                "target": _collapse(cells[1]),
                "gate": _collapse(cells[2]),
            }
        )
    return rows


def _prv116(text: str) -> dict[str, Any]:
    literals, clause = _tolerances(_requirement(text, PRV116_ANCHOR))
    return {
        "literals": literals,
        "clause": clause,
        "predicates": _predicates(text),
    }


def _doc06(text: str) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    for anchor in (RULE_HEADER, PRV45_ANCHOR, PRV116_ANCHOR, PREDICATE_HEADER):
        _one(text, anchor)
    return _rule_codes(text), _prv45(text), _prv116(text)


def _gate_rows(text: str, header: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cells in _table(text, header):
        if len(cells) != 3:
            raise ExtractionFailure(header)
        gate = _collapse(cells[1])
        evidence = _collapse(cells[2])
        rows.append(
            {
                "name": _collapse(cells[0]),
                "gate": gate,
                "evidence": evidence,
                "tst": _tst_numbers(gate + "\n" + evidence),
            }
        )
    return rows


def _tst_numbers(text: str) -> list[int]:
    numbers: list[int] = []
    for match in _TST.finditer(text):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        if end < start:
            raise ExtractionFailure("tst range")
        numbers.extend(range(start, end + 1))
    return numbers


def _definitions(text: str) -> dict[int, tuple[str, str]]:
    found: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        match = _DEF.match(line)
        if match is None:
            continue
        number = int(match.group(2))
        if number in found:
            raise ExtractionFailure(f"duplicate definition TST-{number}")
        body = line[match.end() :]
        if body.endswith("|"):
            body = body[:-1]
        found[number] = (match.group(1), _collapse(body.replace("\\|", "|")))
    return found


def _labels(
    numbers: list[int], definitions: Mapping[int, tuple[str, str]]
) -> list[str]:
    labels: list[str] = []
    for number in numbers:
        if number not in definitions:
            raise ExtractionFailure(f"missing definition TST-{number}")
        labels.append(definitions[number][0])
    return labels


def _require_s5(rows: list[dict[str, Any]]) -> None:
    matched = [row for row in rows if str(row["name"]).startswith("slice S5 ")]
    if len(matched) != 1:
        raise ExtractionFailure("S5 row")
    match = re.search(r"at least (\d[\d,]*) area pairs", str(matched[0]["gate"]))
    if match is None:
        raise ExtractionFailure("S5 minimum")
    number = match.group(1).replace(",", "")
    if not number.isdigit() or (len(number) > 1 and number.startswith("0")):
        raise ExtractionFailure("S5 minimum")


def _require_51(rows: list[dict[str, Any]]) -> None:
    matched = [row for row in rows if str(row["name"]).startswith("Talent available")]
    if len(matched) != 1:
        raise ExtractionFailure("section 5.1 minimum")
    if re.search(r"\d+, \d+ and \d+ minutes", str(matched[0]["gate"])) is None:
        raise ExtractionFailure("section 5.1 minimum")


def _gates(text: str, rules_text: str | None = None) -> dict[str, Any]:
    for anchor in (SECTION_5, SECTION_51, SECTION_6):
        _one(text, anchor)
    section_5 = _gate_rows(_slice(text, SECTION_5, SECTION_51), "| Slice |")
    section_51 = _gate_rows(_slice(text, SECTION_51, SECTION_6), "| Feature |")
    _require_s5(section_5)
    _require_51(section_51)
    definitions = _definitions(text)
    referenced = sorted(
        set(
            _tst_numbers(
                _slice(text, SECTION_5, SECTION_51)
                + _slice(text, SECTION_51, SECTION_6)
            )
        )
    )
    resolved = _labels(referenced, definitions)
    if len(resolved) != len(referenced):
        raise ExtractionFailure("tst labels")
    assertions = {
        definitions[number][0]: definitions[number][1] for number in referenced
    }
    if rules_text is not None:
        codes = _strings(
            _env(rules_text, {"RETIRED_CODES"})["RETIRED_CODES"],
            "RETIRED_CODES",
        )
        assertions = {
            label: _redact_retired(body, codes) for label, body in assertions.items()
        }
    for rows in (section_5, section_51):
        for row in rows:
            row["tst"] = _labels(row["tst"], definitions)
    return {
        "section_5": section_5,
        "section_5_1": section_51,
        "assertions": assertions,
    }


def _strings(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ExtractionFailure(name)
    return list(value)


def _optional_strings(entry: Mapping[str, Any], key: str) -> list[str] | None:
    if key not in entry:
        return None
    return _strings(entry[key], key)


def _audience_rules(text: str) -> dict[str, Any]:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ExtractionFailure("audience rules")
    surfaces_raw = raw.get("surfaces")
    if not isinstance(surfaces_raw, list):
        raise ExtractionFailure("surfaces")
    surfaces: list[dict[str, Any]] = []
    for item in surfaces_raw:
        if not isinstance(item, dict):
            raise ExtractionFailure("surface")
        ident = item.get("id")
        output = item.get("output_class")
        required = item.get("required")
        minimum = item.get("min_items")
        if (
            not isinstance(ident, str)
            or not isinstance(output, str)
            or type(required) is not bool
            or type(minimum) is not int
        ):
            raise ExtractionFailure("surface")
        surfaces.append(
            {
                "id": ident,
                "output_class": output,
                "required": required,
                "min_items": minimum,
            }
        )
    terms = raw.get("terms")
    if not isinstance(terms, list):
        raise ExtractionFailure("terms")
    suppression: list[dict[str, Any]] = []
    method: list[dict[str, Any]] = []
    for entry in terms:
        if not isinstance(entry, dict):
            raise ExtractionFailure("term")
        ident = entry.get("id")
        term = entry.get("term")
        verdict = entry.get("verdict")
        if (
            not isinstance(ident, str)
            or not isinstance(term, str)
            or not isinstance(verdict, str)
        ):
            raise ExtractionFailure("term")
        row = {
            "id": ident,
            "term": term,
            "verdict": verdict,
            "exempt_field_kinds": _optional_strings(entry, "exempt_field_kinds"),
            "allow_contexts": _optional_strings(entry, "allow_contexts"),
        }
        if ident in SUPPRESSION_IDS:
            suppression.append(row)
        if entry.get("group") == "method":
            method.append(row)
    markers = raw.get("backend_markers")
    if not isinstance(markers, dict):
        raise ExtractionFailure("backend_markers")
    allow_raw = raw.get("allow_values")
    if not isinstance(allow_raw, list):
        raise ExtractionFailure("allow_values")
    allow_values: list[dict[str, str]] = []
    for item in allow_raw:
        if not isinstance(item, dict):
            raise ExtractionFailure("allow_values")
        allow: dict[str, str] = {}
        for key, value in item.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ExtractionFailure("allow_values")
            allow[key] = value
        allow_values.append(allow)
    return {
        "scan_kinds": _strings(raw.get("scan_kinds"), "scan_kinds"),
        "claim_scan_kinds": _strings(raw.get("claim_scan_kinds"), "claim_scan_kinds"),
        "allow_values": allow_values,
        "surfaces": surfaces,
        "field_kinds": _strings(raw.get("field_kinds"), "field_kinds"),
        "output_classes": _strings(raw.get("output_classes"), "output_classes"),
        "unproduced_classes": _strings(
            raw.get("unproduced_classes"), "unproduced_classes"
        ),
        "badge_exempt_kinds": _strings(
            raw.get("badge_exempt_kinds"), "badge_exempt_kinds"
        ),
        "suppression": suppression,
        "method_terms": method,
        "backend_markers": {
            "levels": _strings(markers.get("levels"), "levels"),
            "fields": _strings(markers.get("fields"), "fields"),
            "generated_values": _strings(
                markers.get("generated_values"), "generated_values"
            ),
        },
    }


def _ok_expr(text: str) -> str:
    found: list[str] = []
    for sub in ast.walk(_function(ast.parse(text), "_report")):
        if not isinstance(sub, ast.Dict):
            continue
        for key, value in zip(sub.keys, sub.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "ok"
                and value is not None
            ):
                found.append(ast.unparse(value))
    return str(_one_match(found, "ok"))


def _declarations(text: str) -> dict[str, str]:
    tree = ast.parse(text)
    found: dict[str, str] = {}
    for name in CLAIM_DECLS:
        node = _definition(tree, name)
        simple = _simple(node)
        found[name] = ast.unparse(simple[1] if simple is not None else node)
    return found


def _chain_keys(text: str) -> list[str]:
    found: list[list[str]] = []
    for sub in ast.walk(_function(ast.parse(text), "require_truthful_chain")):
        if not isinstance(sub, ast.For) or not isinstance(sub.iter, ast.Tuple):
            continue
        keys: list[str] = []
        for item in sub.iter.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                keys = []
                break
            keys.append(item.value)
        if keys:
            found.append(keys)
    return list(_one_match(found, "chain keys"))


def _backend(text: str) -> dict[str, Any]:
    names = (
        "LEVELS",
        "MARKER_KEYS",
        "GENERATED_ORIGINS",
        "CHILDREN",
        "DISPLAY_KEYS",
        "REFUSAL_CODES",
    )
    env = _env(text, set(names))
    picked = _pick(env, names)
    picked["chain_keys"] = _chain_keys(text)
    picked["declarations"] = _declarations(text)
    return picked


def _checker(text: str) -> dict[str, Any]:
    return {"GROUPS": _env(text, {"GROUPS"})["GROUPS"], "ok": _ok_expr(text)}


def _argv_modes(text: str) -> list[str]:
    found: list[list[str]] = []
    for sub in ast.walk(_function(ast.parse(text), "main")):
        if (
            not isinstance(sub, ast.Compare)
            or len(sub.ops) != 1
            or not isinstance(sub.ops[0], ast.NotIn)
            or len(sub.comparators) != 1
            or not isinstance(sub.comparators[0], ast.Tuple)
        ):
            continue
        modes: list[str] = []
        for item in sub.comparators[0].elts:
            if (
                isinstance(item, ast.List)
                and len(item.elts) == 1
                and isinstance(item.elts[0], ast.Constant)
                and isinstance(item.elts[0].value, str)
            ):
                modes.append(item.elts[0].value)
            else:
                modes = []
                break
        if modes:
            found.append(modes)
    return list(_one_match(found, "argv modes"))


def _engine(text: str) -> str:
    value = _env(text, {"ENGINE"})["ENGINE"]
    if not isinstance(value, str):
        raise ExtractionFailure("engine")
    return value


def _sandbox_check(text: str, engine: str) -> dict[str, Any]:
    env = _env(text, {"INSIDE_LINES", "LOAD_LINES"}, engine=engine)
    return {
        "INSIDE_LINES": env["INSIDE_LINES"],
        "LOAD_LINES": env["LOAD_LINES"],
        "argv": _argv_modes(text),
    }


def _kind_refusal(text: str) -> tuple[str, str]:
    found: list[tuple[str, str]] = []
    for sub in ast.walk(_function(ast.parse(text), "_refuse_scalars")):
        if not isinstance(sub, ast.If) or not isinstance(sub.test, ast.Compare):
            continue
        test = sub.test
        if (
            len(test.ops) != 1
            or not isinstance(test.ops[0], ast.NotEq)
            or len(test.comparators) != 1
            or not isinstance(test.comparators[0], ast.Constant)
            or not isinstance(test.comparators[0].value, str)
        ):
            continue
        for statement in sub.body:
            if (
                isinstance(statement, ast.Raise)
                and isinstance(statement.exc, ast.Call)
                and statement.exc.args
                and isinstance(statement.exc.args[0], ast.Constant)
                and isinstance(statement.exc.args[0].value, str)
            ):
                found.append((test.comparators[0].value, statement.exc.args[0].value))
    kind, refusal = _one_match(found, "release kind")
    return str(kind), str(refusal)


def _forbidden_classes(text: str) -> list[str]:
    found: list[list[str]] = []
    for sub in ast.walk(_function(ast.parse(text), "_refuse_table")):
        if (
            not isinstance(sub, ast.Compare)
            or len(sub.ops) != 1
            or not isinstance(sub.ops[0], ast.In)
            or not isinstance(sub.comparators[0], ast.Set)
        ):
            continue
        values = [
            item.value
            for item in sub.comparators[0].elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        if values:
            found.append(sorted(values))
    return list(_one_match(found, "forbidden classes"))


def _privacy_writer(text: str) -> str:
    found: list[str] = []
    for sub in ast.walk(_function(ast.parse(text), "written_by_privacy")):
        if (
            isinstance(sub, ast.Return)
            and isinstance(sub.value, ast.Compare)
            and len(sub.value.ops) == 1
            and isinstance(sub.value.ops[0], ast.Eq)
            and isinstance(sub.value.comparators[0], ast.Constant)
            and isinstance(sub.value.comparators[0].value, str)
        ):
            found.append(sub.value.comparators[0].value)
    return str(_one_match(found, "privacy writer"))


def _public(public_text: str, manifest_text: str) -> dict[str, Any]:
    kind, refusal = _kind_refusal(public_text)
    forbidden = _env(manifest_text, {"FORBIDDEN_PUBLIC_ONLY"})["FORBIDDEN_PUBLIC_ONLY"]
    return {
        "forbidden_fields": forbidden,
        "accepted_kind": kind,
        "kind_refusal": refusal,
        "forbidden_classes": _forbidden_classes(public_text),
        "privacy_writer": _privacy_writer(manifest_text),
    }


def _present(value: str | None, relative: str, build: Callable[[str], Any]) -> Any:
    if value is None:
        return {"absent": relative}
    return build(value)


def project(
    root: Path,
    overlays: Mapping[str, str] | None = None,
    *,
    allow_absent: bool = False,
) -> dict[str, Any]:
    """Read one tree's control declarations. Overlays replace file text."""

    def read(relative: str) -> str | None:
        return _read(root, relative, overlays, allow_absent)

    for relative in DECLARING:
        text = read(relative) if relative.endswith(".py") else None
        if text is not None:
            _refuse_imports(ast.parse(text), relative)

    rules_py = read(RULES_PY)
    rules_toml = read(RULES_TOML)
    doc06 = read(DOC06)
    doc12 = read(DOC12)
    audience = read(AUDIENCE)
    checker = read(CHECKER)
    backend = read(BACKEND)
    profiles = read(PROFILES_PY)
    policy = read(POLICY_PY)
    sandbox = read(SANDBOX_PY)
    engine = read(ENGINE_PY)
    cases = read(CASES_PY)
    public = read(PUBLIC_PY)
    manifest = read(MANIFEST_PY)

    if rules_py is None or rules_toml is None:
        missing = [
            path
            for path, text in ((RULES_PY, rules_py), (RULES_TOML, rules_toml))
            if text is None
        ]
        rules: Any = {"absent": missing}
    else:
        rules = {**_rules_py(rules_py), "toml_rows": _toml_rows(rules_toml)}

    if doc06 is None:
        codes: Any = {"absent": DOC06}
        prv45: Any = {"absent": DOC06}
        prv116: Any = {"absent": DOC06}
    else:
        codes, prv45, prv116 = _doc06(doc06)

    audience_out: dict[str, Any] = {}
    absent: list[str] = []
    if audience is None:
        absent.append(AUDIENCE)
    else:
        audience_out.update(_audience_rules(audience))
    if checker is None:
        absent.append(CHECKER)
    else:
        audience_out.update(_checker(checker))
    if backend is None:
        absent.append(BACKEND)
    else:
        audience_out["backend_origin"] = _backend(backend)
    if absent:
        audience_out["absent"] = absent

    if sandbox is None or engine is None:
        sandbox_out: Any = {
            "absent": [
                path
                for path, text in ((SANDBOX_PY, sandbox), (ENGINE_PY, engine))
                if text is None
            ]
        }
    else:
        sandbox_out = _sandbox_check(sandbox, _engine(engine))

    if public is None or manifest is None:
        public_out: Any = {
            "absent": [
                path
                for path, text in ((PUBLIC_PY, public), (MANIFEST_PY, manifest))
                if text is None
            ]
        }
    else:
        public_out = _public(public, manifest)

    return {
        "rules_config": rules,
        "doc06_section5": codes,
        "prv45": prv45,
        "prv116": prv116,
        "gates": _present(
            doc12,
            DOC12,
            lambda text: _gates(text, rules_py),
        ),
        "audience_retained": audience_out,
        "sandbox_profiles": _present(
            profiles,
            PROFILES_PY,
            lambda text: _pick(
                _env(
                    text,
                    {
                        "ISOLATION",
                        "READ_ONLY_BIND",
                        "WRITABLE_BIND",
                        "CODE_FOLDERS",
                        "PROFILE_VARIABLE",
                        "FIXED_ENVIRONMENT",
                        "CHILD_ENVIRONMENT_NAMES",
                        "TIMEOUT_SECONDS",
                        "PROFILES",
                    },
                ),
                (
                    "ISOLATION",
                    "READ_ONLY_BIND",
                    "WRITABLE_BIND",
                    "CODE_FOLDERS",
                    "PROFILE_VARIABLE",
                    "FIXED_ENVIRONMENT",
                    "CHILD_ENVIRONMENT_NAMES",
                    "TIMEOUT_SECONDS",
                    "PROFILES",
                ),
            ),
        ),
        "sandbox_policy": _present(
            policy,
            POLICY_PY,
            lambda text: _pick(
                _env(text, {"_CLOSED", "_FLAGS"}), ("_CLOSED", "_FLAGS")
            ),
        ),
        "sandbox_check": sandbox_out,
        "ci_cases": _present(
            cases, CASES_PY, lambda text: _env(text, {"CASES"})["CASES"]
        ),
        "public_only": public_out,
    }


def _as_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(type(value).__name__)
    return value


def _as_list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise AssertionError(type(value).__name__)
    return value


def assert_cardinalities(got: dict[str, Any]) -> None:
    """Stop a short walk before it can be stored as the pin."""
    assert set(got) == set(KEYS)
    rules = _as_dict(got["rules_config"])
    assert len(_as_list(rules["toml_rows"])) == 4
    assert len(_as_list(got["doc06_section5"])) == 16
    predicates = _as_list(_as_dict(got["prv116"])["predicates"])
    assert len(predicates) == 19
    assert _as_dict(predicates[0])["id"] == "person_pay_band"
    assert _as_dict(predicates[-1])["id"] == "assistant_tool_escape"
    gates = _as_dict(got["gates"])
    assert len(_as_list(gates["section_5"])) == 12
    assert len(_as_list(gates["section_5_1"])) == 27
    audience = _as_dict(got["audience_retained"])
    assert "absent" not in audience
    surfaces = _as_list(audience["surfaces"])
    assert len(surfaces) == 12
    document = next(
        item for item in surfaces if _as_dict(item)["id"] == "web.dist.document"
    )
    assert _as_dict(document)["min_items"] == 1
    assert len(_as_list(got["ci_cases"])) == 17
    assert len(_as_list(_as_dict(got["public_only"])["forbidden_fields"])) == 8
    origin = _as_dict(audience["backend_origin"])
    markers = _as_dict(audience["backend_markers"])
    assert markers["levels"] == origin["LEVELS"]
    assert markers["fields"] == origin["MARKER_KEYS"]
    assert sorted(_as_list(markers["generated_values"])) == list(
        origin["GENERATED_ORIGINS"]
    )
    assert audience["GROUPS"] == ["audience", "extraction", "backend", "method"]


def _pin() -> Any:
    return json.loads(PIN.read_text(encoding="utf-8"))


def _replace(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"plant count {text.count(old)} for {old!r}")
    return text.replace(old, new, 1)


def _json_edit(text: str, edit: Callable[[dict[str, Any]], None]) -> str:
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise AssertionError("rules")
    edit(loaded)
    return json.dumps(loaded)


def _drop_term(term_id: str) -> Callable[[str], str]:
    def mutate(text: str) -> str:
        def edit(data: dict[str, Any]) -> None:
            terms = _as_list(data["terms"])
            kept = [term for term in terms if _as_dict(term).get("id") != term_id]
            if len(kept) != len(terms) - 1:
                raise AssertionError(term_id)
            data["terms"] = kept

        return _json_edit(text, edit)

    return mutate


def _append_rule(code: str, value: str, unit: str) -> Callable[[str], str]:
    block = (
        "\n\n[[rules_version]]\n"
        'rules_version_id = "rv-1.0.0-s1"\n'
        'parameter_set = "A"\n'
        f'rule_code = "{code}"\n'
        f'value = "{value}"\n'
        f'unit = "{unit}"\n'
        'description_en = "Planted row."\n'
    )

    def mutate(text: str) -> str:
        return text.rstrip() + block

    return mutate


def _drop_anchor(anchor: str) -> Callable[[str], str]:
    def mutate(text: str) -> str:
        return _replace(text, anchor, "ANCHOR-REMOVED")

    return mutate


def _duplicate_anchor(anchor: str) -> Callable[[str], str]:
    def mutate(text: str) -> str:
        if text.count(anchor) != 1:
            raise AssertionError(anchor)
        return text + "\n" + anchor + "\n"

    return mutate


def _talent_minimum(text: str) -> str:
    found = 0
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("| Talent available near this site |"):
            found += 1
            lines.append(
                line.replace("10, 20 and 30 minutes", "ten, 20 and 30 minutes", 1)
            )
        else:
            lines.append(line)
    if found != 1:
        raise AssertionError(found)
    return "".join(lines)


def _tst21_body(text: str) -> str:
    found = 0
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("| TST-21 |"):
            found += 1
            if line.count("10,000") != 2:
                raise AssertionError(line.count("10,000"))
            lines.append(line.replace("10,000", "9,999"))
        else:
            lines.append(line)
    if found != 1:
        raise AssertionError(found)
    return "".join(lines)


def _suppression_context(text: str) -> str:
    def edit(data: dict[str, Any]) -> None:
        found = 0
        for term in _as_list(data["terms"]):
            row = _as_dict(term)
            if row.get("id") == "en.suppressed":
                found += 1
                if "allow_contexts" in row:
                    raise AssertionError("allow_contexts already present")
                row["allow_contexts"] = ["suppressed figure"]
        if found != 1:
            raise AssertionError(found)

    return _json_edit(text, edit)


def _empty_claims(text: str) -> str:
    def edit(data: dict[str, Any]) -> None:
        data["claim_scan_kinds"] = []

    return _json_edit(text, edit)


def _allow_official(text: str) -> str:
    def edit(data: dict[str, Any]) -> None:
        values = _as_list(data["allow_values"])
        values.append({"value": "official figure"})
        data["allow_values"] = values

    return _json_edit(text, edit)


def _zero_minimum(text: str) -> str:
    def edit(data: dict[str, Any]) -> None:
        found = 0
        for surface in _as_list(data["surfaces"]):
            row = _as_dict(surface)
            if row.get("id") == "web.dist.document":
                found += 1
                row["min_items"] = 0
        if found != 1:
            raise AssertionError(found)

    return _json_edit(text, edit)


def _after(anchor: str, block: str) -> Callable[[str], str]:
    def mutate(text: str) -> str:
        if not anchor:
            return text + block
        return _replace(text, anchor, anchor + block)

    return mutate


def _executed(text: str, path: str, read: Callable[[types.ModuleType], Any]) -> Any:
    """Run one declaring file's text with Python itself and read its module."""
    name = "decision_0035_probe"
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(text, path, "exec"), module.__dict__)
        return read(module)
    finally:
        del sys.modules[name]


def _python_cases(text: str) -> list[dict[str, Any]]:
    """Instantiate the case declarations with Python itself; runs nothing else."""
    cases: list[dict[str, Any]] = _executed(
        text, CASES_PY, lambda module: [dataclasses.asdict(c) for c in module.CASES]
    )
    return cases


def _load_rules_text(text: str) -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rules.toml"
        path.write_text(text, encoding="utf-8")
        load_rules(path)


@dataclass(frozen=True)
class Plant:
    """One copied-file mutation compared with the unchanged pin."""

    name: str
    path: str
    kind: str
    expected: int
    mutate: Callable[[str], str]


PLANTS: tuple[Plant, ...] = (
    Plant(
        "toml_round_movement_a",
        RULES_TOML,
        "inequality",
        1,
        lambda text: _replace(
            text,
            'parameter_set = "A"\nrule_code = "round_movement"\nvalue = "50"',
            'parameter_set = "A"\nrule_code = "round_movement"\nvalue = "49"',
        ),
    ),
    Plant(
        "s5_gate_minimum",
        DOC12,
        "inequality",
        1,
        lambda text: _replace(
            text, "at least 10,000 area pairs", "at least 9,999 area pairs"
        ),
    ),
    Plant(
        "s5_controls_on_outcome",
        DOC12,
        "inequality",
        1,
        lambda text: _replace(
            text, "with controls on none is", "with controls on some are"
        ),
    ),
    Plant(
        "feasibility_tolerance",
        DOC06,
        "inequality",
        1,
        lambda text: _replace(
            text, "feasibility_tolerance = 1e-7", "feasibility_tolerance = 1e-6"
        ),
    ),
    Plant(
        "drop_unshare_net",
        PROFILES_PY,
        "inequality",
        1,
        lambda text: _replace(text, '    "--unshare-net",\n', ""),
    ),
    Plant(
        "docs_local_path_command",
        CASES_PY,
        "inequality",
        1,
        lambda text: _replace(
            text,
            '"docs-local-path",\n        "documentation",\n        DOCS,',
            '"docs-local-path",\n        "documentation",\n        "true",',
        ),
    ),
    Plant(
        "drop_check_enforcement",
        SANDBOX_PY,
        "inequality",
        1,
        lambda text: _replace(
            text,
            '(["check"], ["check-extensions"], ["check-enforcement"])',
            '(["check"], ["check-extensions"])',
        ),
    ),
    Plant(
        "delete_en_suppressed", AUDIENCE, "inequality", 1, _drop_term("en.suppressed")
    ),
    Plant(
        "delete_claim_en_official",
        AUDIENCE,
        "inequality",
        1,
        _drop_term("claim.en.official"),
    ),
    Plant("empty_claim_scan_kinds", AUDIENCE, "inequality", 1, _empty_claims),
    Plant("allow_official_figure", AUDIENCE, "inequality", 1, _allow_official),
    Plant("document_min_items_zero", AUDIENCE, "inequality", 1, _zero_minimum),
    Plant(
        "toml_added_min_earners",
        RULES_TOML,
        "added",
        1,
        _append_rule("min_earners_count", "10", "unspecified"),
    ),
    Plant(
        "toml_unknown_code",
        RULES_TOML,
        "refusal",
        3,
        _append_rule("not_a_rule", "1", "unspecified"),
    ),
    Plant("missing_rule_header", DOC06, "extract", 2, _drop_anchor(RULE_HEADER)),
    Plant("missing_prv45", DOC06, "extract", 2, _drop_anchor(PRV45_ANCHOR)),
    Plant("missing_prv116", DOC06, "extract", 2, _drop_anchor(PRV116_ANCHOR)),
    Plant("missing_section_5", DOC12, "extract", 2, _drop_anchor(SECTION_5)),
    Plant("missing_section_51", DOC12, "extract", 2, _drop_anchor(SECTION_51)),
    Plant("duplicate_rule_header", DOC06, "extract", 2, _duplicate_anchor(RULE_HEADER)),
    Plant("duplicate_prv45", DOC06, "extract", 2, _duplicate_anchor(PRV45_ANCHOR)),
    Plant("duplicate_prv116", DOC06, "extract", 2, _duplicate_anchor(PRV116_ANCHOR)),
    Plant("duplicate_section_5", DOC12, "extract", 2, _duplicate_anchor(SECTION_5)),
    Plant("duplicate_section_51", DOC12, "extract", 2, _duplicate_anchor(SECTION_51)),
    Plant(
        "broken_ab_pair",
        DOC06,
        "extract",
        2,
        lambda text: _replace(
            text, "`min_earners_count` 10 / 20", "`min_earners_count` 10 /"
        ),
    ),
    Plant(
        "money_delta_non_numeric",
        DOC06,
        "extract",
        2,
        lambda text: _replace(
            text,
            "`delta` 0.02 (A) or 0.03 (B)",
            "`delta` two (A) or 0.03 (B)",
        ),
    ),
    Plant(
        "broken_tolerance_literal",
        DOC06,
        "extract",
        2,
        lambda text: _replace(
            text, "feasibility_tolerance = 1e-7", "feasibility_tolerance = 1e-"
        ),
    ),
    Plant(
        "s5_minimum_non_numeric",
        DOC12,
        "extract",
        2,
        lambda text: _replace(
            text, "at least 10,000 area pairs", "at least many area pairs"
        ),
    ),
    Plant("section_51_minimum_non_numeric", DOC12, "extract", 2, _talent_minimum),
    Plant(
        "round_count_a",
        DOC06,
        "inequality",
        1,
        lambda text: _replace(text, "`round_count` 5 / 10", "`round_count` 6 / 10"),
    ),
    Plant(
        "round_money_a",
        DOC06,
        "inequality",
        1,
        lambda text: _replace(
            text, "`round_money` 100 / 500", "`round_money` 101 / 500"
        ),
    ),
    Plant(
        "s5_evidence_new_tst",
        DOC12,
        "inequality",
        1,
        lambda text: _replace(
            text,
            "two byte-identical release builds with the same `release_id`",
            "two byte-identical release builds with the same `release_id` TST-02",
        ),
    ),
    Plant(
        "suppression_allow_contexts", AUDIENCE, "inequality", 1, _suppression_context
    ),
    Plant(
        "claim_en_without_official_alternative",
        BACKEND,
        "inequality",
        1,
        lambda text: _replace(text, '    r"official(?:ly)?",\n', ""),
    ),
    Plant("tst21_body_minimum", DOC12, "inequality", 1, _tst21_body),
)

WINDOW_ANCHOR = "WINDOW_MAX = 23\n"
CASE_SCANNER = "    scanner: bool = False\n"

# Every write form that can rebind a projected name or one it reads (F1 class).
WRITE_PLANTS: tuple[Plant, ...] = tuple(
    Plant(name, path, "extract", 2, _after(anchor, block))
    for name, path, anchor, block in (
        ("window_augassign", RULES_PY, WINDOW_ANCHOR, "WINDOW_MAX += 1\n"),
        ("window_repeated", RULES_PY, WINDOW_ANCHOR, "WINDOW_MAX = 23\n"),
        ("window_annotation_only", RULES_PY, WINDOW_ANCHOR, "WINDOW_MAX: int\n"),
        ("window_tuple", RULES_PY, WINDOW_ANCHOR, "WINDOW_MAX, _P = 24, 0\n"),
        ("window_starred", RULES_PY, WINDOW_ANCHOR, "*WINDOW_MAX, = [24]\n"),
        ("window_multi_target", RULES_PY, WINDOW_ANCHOR, "WINDOW_MAX = _P = 24\n"),
        ("window_walrus", RULES_PY, WINDOW_ANCHOR, "_P = (WINDOW_MAX := 24)\n"),
        (
            "window_conditional",
            RULES_PY,
            WINDOW_ANCHOR,
            "if WINDOW_MIN:\n    WINDOW_MAX = 24\n",
        ),
        ("window_for", RULES_PY, WINDOW_ANCHOR, "for WINDOW_MAX in (24,):\n    pass\n"),
        (
            "window_with",
            RULES_PY,
            WINDOW_ANCHOR,
            "with open(__file__) as WINDOW_MAX:\n    pass\n",
        ),
        (
            "window_except",
            RULES_PY,
            WINDOW_ANCHOR,
            "try:\n    pass\nexcept ValueError as WINDOW_MAX:\n    pass\n",
        ),
        (
            "window_import_as",
            RULES_PY,
            WINDOW_ANCHOR,
            "from math import tau as WINDOW_MAX\n",
        ),
        ("window_del", RULES_PY, WINDOW_ANCHOR, "del WINDOW_MAX\n"),
        (
            "window_match_capture",
            RULES_PY,
            WINDOW_ANCHOR,
            "match 24:\n    case WINDOW_MAX:\n        pass\n",
        ),
        ("window_type_alias", RULES_PY, WINDOW_ANCHOR, "type WINDOW_MAX = int\n"),
        (
            "window_function",
            RULES_PY,
            WINDOW_ANCHOR,
            "def WINDOW_MAX() -> int:\n    return 24\n",
        ),
        ("window_class", RULES_PY, WINDOW_ANCHOR, "class WINDOW_MAX:\n    pass\n"),
        (
            "window_global",
            RULES_PY,
            WINDOW_ANCHOR,
            "def _p() -> None:\n    global WINDOW_MAX\n    WINDOW_MAX = 24\n",
        ),
        ("window_globals", RULES_PY, WINDOW_ANCHOR, 'globals()["WINDOW_MAX"] = 24\n'),
        (
            "window_setattr",
            RULES_PY,
            WINDOW_ANCHOR,
            'setattr(sys.modules[__name__], "WINDOW_MAX", 24)\n',
        ),
        (
            "dependency_augassign",
            RULES_PY,
            "TASK_PLACEMENTS = frozenset(REQUIRED_PLACEMENTS)\n",
            "REQUIRED_PLACEMENTS += ()\n",
        ),
        ("units_item_write", RULES_PY, WINDOW_ANCHOR, 'TASK_UNITS["p"] = "p"\n'),
        ("units_mutator", RULES_PY, WINDOW_ANCHOR, 'TASK_UNITS.update({"p": "p"})\n'),
        ("frozenset_shadowed", RULES_PY, WINDOW_ANCHOR, "frozenset = tuple\n"),
        (
            "claim_repeated",
            BACKEND,
            "",
            "\n_CLAIM_EN = ()\n",
        ),
        (
            "main_repeated",
            SANDBOX_PY,
            "",
            "\n\ndef main() -> int:\n    return 0\n",
        ),
        ("case_class_repeated", CASES_PY, CASE_SCANNER, "\n\nclass Case:\n    pass\n"),
    )
)

# Every value the walker once supplied itself, now read from source (F2 class).
DEFAULT_PLANTS: tuple[Plant, ...] = (
    Plant(
        "case_folder_default",
        CASES_PY,
        "inequality",
        1,
        lambda text: _replace(text, 'folder: str = "."', 'folder: str = "web"'),
    ),
    Plant(
        "case_default_unsupported",
        CASES_PY,
        "extract",
        2,
        lambda text: _replace(
            text, 'folder: str = "."', 'folder: str = field(default=".")'
        ),
    ),
    Plant(
        "case_default_missing",
        CASES_PY,
        "extract",
        2,
        lambda text: _replace(text, CASE_SCANNER, "    scanner: bool\n"),
    ),
    Plant(
        "case_field_duplicate",
        CASES_PY,
        "extract",
        2,
        _after(CASE_SCANNER, '    folder: str = "web"\n'),
    ),
    Plant(
        "case_post_init",
        CASES_PY,
        "extract",
        2,
        _after(CASE_SCANNER, "\n    def __post_init__(self) -> None:\n        pass\n"),
    ),
    Plant(
        "case_kw_only",
        CASES_PY,
        "extract",
        2,
        lambda text: _replace(
            text,
            "@dataclass(frozen=True)\nclass Case",
            "@dataclass(frozen=True, kw_only=True)\nclass Case",
        ),
    ),
)

# Every appearance of a pinned mutable value outside its read-only uses (F1a/F1b).
ESCAPE_PLANTS: tuple[Plant, ...] = tuple(
    Plant(name, path, "extract", 2, _after("", block))
    for name, path, block in (
        (
            "alias_item",
            RULES_PY,
            '\n_review_alias = TASK_UNITS\n_review_alias["window_months"] = "days"\n',
        ),
        (
            "argument_item",
            RULES_PY,
            "\ndef _review_change(value):\n"
            '    value["window_months"] = "days"\n_review_change(TASK_UNITS)\n',
        ),
        ("dunder_init", RULES_PY, '\nTASK_UNITS.__init__(window_months="days")\n'),
        (
            "unbound_update",
            RULES_PY,
            '\ndict.update(TASK_UNITS, window_months="days")\n',
        ),
        ("rule_sets_element", RULES_PY, "\n_review = [TASK_RULE_SETS]\n"),
        ("children_starred", BACKEND, "\nprint(*CHILDREN)\n"),
        ("closed_keyword", POLICY_PY, "\n_review = dict(**_CLOSED)\n"),
        ("flags_bound_method", POLICY_PY, "\n_review = _FLAGS.update\n"),
        (
            "inside_return",
            SANDBOX_PY,
            "\n\ndef _review():\n    return INSIDE_LINES\n",
        ),
        (
            "cases_item_setattr",
            CASES_PY,
            '\nobject.__setattr__(CASES[0], "folder", "web")\n',
        ),
        ("claim_argument", BACKEND, "\nprint(_CLAIM)\n"),
    )
)

# Admitted forms whose meaning user code redirects (S3-CTL r4): the ten
# escapes confirmation cf3 executed, verbatim, then one plant for each form of
# sub-classes (a) rebound builtin, (b) operand dunder and (c) live view that
# those ten do not cover.
_CF3_HOOK = (
    "\nclass _ReviewEqual:\n    def __eq__(self, value):\n"
    '        value["window_months"] = "days"\n        return True\n'
)
_CF3_LAMBDA = 'lambda value: value.update(window_months="days")'
REDIRECT_PLANTS: tuple[Plant, ...] = (
    *(
        Plant(name, path, "extract", 2, _after("", block))
        for name, path, block in (
            (
                "cf3_class_len",
                RULES_PY,
                f"\nclass _Review:\n    len = {_CF3_LAMBDA}\n    _value = len(TASK_UNITS)\n",
            ),
            (
                "cf3_comparison_chain_eq",
                RULES_PY,
                _CF3_HOOK
                + '_review = "window_months" in TASK_UNITS == _ReviewEqual()\n',
            ),
            (
                "cf3_comparison_chain_in",
                RULES_PY,
                "\nclass _ReviewContains:\n    def __contains__(self, value):\n"
                '        value["window_months"] = "days"\n        return True\n'
                '_review = "window_months" in TASK_UNITS in _ReviewContains()\n',
            ),
            (
                "cf3_comparison_chain_notin",
                RULES_PY,
                _CF3_HOOK + '_review = "absent" not in TASK_UNITS == _ReviewEqual()\n',
            ),
            (
                "cf3_comprehension_len",
                RULES_PY,
                f"\n_review = [len(TASK_UNITS) for len in [{_CF3_LAMBDA}]]\n",
            ),
            (
                "cf3_function_local_len",
                RULES_PY,
                f"\ndef _review_apply():\n    len = {_CF3_LAMBDA}\n    len(TASK_UNITS)\n"
                "_review_apply()\n",
            ),
            (
                "cf3_function_parameter_len",
                RULES_PY,
                "\ndef _review_apply(len):\n    len(TASK_UNITS)\n"
                f"_review_apply({_CF3_LAMBDA})\n",
            ),
            (
                "cf3_function_parameter_list",
                RULES_PY,
                "\ndef _review_apply(list):\n    list(TASK_UNITS)\n"
                f"_review_apply({_CF3_LAMBDA})\n",
            ),
            (
                "cf3_items_mapping_equality",
                RULES_PY,
                _CF3_HOOK + "_review = TASK_UNITS.items().mapping == _ReviewEqual()\n",
            ),
            (
                "cf3_lambda_parameter_len",
                RULES_PY,
                f"\n(lambda len: len(TASK_UNITS))({_CF3_LAMBDA})\n",
            ),
            ("a_import_as", RULES_PY, "\nfrom operator import truth as len\n"),
            ("a_global", RULES_PY, "\ndef _p():\n    global list\n"),
            (
                "a_nonlocal",
                RULES_PY,
                "\ndef _p():\n    def _q():\n        nonlocal len\n",
            ),
            ("a_walrus", RULES_PY, "\n_review = [(len := print), len(TASK_UNITS)]\n"),
            ("a_for_target", RULES_PY, "\nfor list in [print]:\n    pass\n"),
            (
                "a_match_capture",
                RULES_PY,
                "\nmatch print:\n    case len:\n        pass\n",
            ),
            (
                "a_except_name",
                RULES_PY,
                "\ntry:\n    pass\nexcept OSError as len:\n    pass\n",
            ),
            ("a_with_target", RULES_PY, "\nwith open(__file__) as list:\n    pass\n"),
            ("a_def_name", RULES_PY, "\nclass _P:\n    def len(self):\n        pass\n"),
            ("a_type_parameter", RULES_PY, "\ndef _p[list]() -> None:\n    pass\n"),
            ("a_keyword_only", RULES_PY, "\ndef _p(*, tuple=print):\n    pass\n"),
            ("a_builtins_import", RULES_PY, "\nimport builtins\n"),
            ("a_builtins_dunder", RULES_PY, '\n__builtins__["len"] = print\n'),
            ("a_builtins_string", RULES_PY, '\n_review = sys.modules["builtins"]\n'),
            (
                "b_equal_left",
                RULES_PY,
                _CF3_HOOK + "_review = TASK_UNITS == _ReviewEqual()\n",
            ),
            ("b_ordering", RULES_PY, "\n_review = TASK_UNITS < print\n"),
            ("b_hook_left", RULES_PY, "\n_review = print != TASK_UNITS\n"),
            ("b_binary_or", RULES_PY, "\n_review = TASK_UNITS | {}\n"),
            ("b_in_left", RULES_PY, "\n_review = TASK_UNITS in ()\n"),
            ("b_chained_order", RULES_PY, '\n_review = "a" not in TASK_UNITS < "b"\n'),
            ("b_is", RULES_PY, "\n_review = TASK_UNITS is None\n"),
            ("b_in_mutable_items", CASES_PY, '\n_review = "x" in CASES\n'),
            (
                "c_items_holder",
                RULES_PY,
                "\n_view = TASK_UNITS.items()\nprint(_view)\n",
            ),
            (
                "c_items_tuple_holder",
                RULES_PY,
                "\n_view = 0, TASK_UNITS.items()\n_review = _view[1]\n",
            ),
            ("c_items_walrus", RULES_PY, "\n_review = (_view := TASK_UNITS.items())\n"),
            ("c_items_operand", RULES_PY, "\n_review = TASK_UNITS.items() == print\n"),
            ("c_items_argument", RULES_PY, "\nprint(TASK_UNITS.items())\n"),
            (
                "c_items_element",
                RULES_PY,
                "\nfor _view in [TASK_UNITS.items()]:\n    pass\n",
            ),
            ("c_items_starred_target", RULES_PY, "\n*_view, = 0, TASK_UNITS.items()\n"),
        )
    ),
    Plant(
        "c_pattern_not_compiled",
        BACKEND,
        "extract",
        2,
        lambda text: _replace(text, "import re\n", "from _review import re\n"),
    ),
)

# Routes to a declaring module's own namespace object (S3-CTL r5): the six
# overlays confirmation cf4 executed, verbatim, then one plant for each other
# route the allow-list of `_refuse_redirects` closes.
_CF4_LEN = "def _review_len(value):\n    value.clear()\n    return 0\n"
_CF4_LIST = "def _review_list(value):\n    value.clear()\n    return []\n"
NAMESPACE_ROUTES: tuple[tuple[str, str], ...] = (
    (
        "cf4_module_attribute_len",
        f"\nimport sys\n{_CF4_LEN}sys.modules[__name__].len = _review_len\n"
        "len(TASK_UNITS)\n",
    ),
    (
        "cf4_module_attribute_list",
        f"\nimport sys\n{_CF4_LIST}sys.modules[__name__].list = _review_list\n"
        "list(TASK_UNITS)\n",
    ),
    (
        "cf4_module_attribute_len_function",
        f"\nimport sys\n{_CF4_LEN}def _review_apply():\n"
        "    sys.modules[__name__].len = _review_len\n    len(TASK_UNITS)\n"
        "_review_apply()\n",
    ),
    (
        "cf4_module_attribute_list_class",
        f"\nimport sys\n{_CF4_LIST}class _Review:\n"
        "    sys.modules[__name__].list = _review_list\n    _value = list(TASK_UNITS)\n",
    ),
    (
        "cf4_module_namespace_alias_len",
        f"\nimport sys\n_module = sys.modules[__name__]\n{_CF4_LEN}"
        "_module.len = _review_len\nlen(TASK_UNITS)\n",
    ),
    (
        "cf4_module_attribute_pinned_rebind",
        "\nimport sys\nsys.modules[__name__].TASK_UNITS = {}\n",
    ),
    ("n_sys_import_as", "\nimport sys as _y\n_y.modules[__name__].len = print\n"),
    (
        "n_from_sys_modules",
        "\nfrom sys import modules as _m\n_m[__name__].len = print\n",
    ),
    ("n_os_sys", "\nimport os\nos.sys.modules[__name__].len = print\n"),
    ("n_sys_alias_name", "\nimport sys\n_y = sys\n"),
    ("n_sys_other_attribute", "\nimport sys\n_review = sys.path\n"),
    ("n_globals_alias", '\n_g = globals\n_g()["len"] = print\n'),
    ("n_locals_alias", '\n_l = locals\n_l()["len"] = print\n'),
    ("n_vars_alias", '\n_v = vars\n_v()["len"] = print\n'),
    (
        "n_setattr_alias",
        '\nimport sys\n_s = setattr\n_s(sys.modules[__name__], "len", print)\n',
    ),
    ("n_delattr_alias", '\n_d = delattr\n_d(print, "len")\n'),
    (
        "n_dict_by_getattr",
        '\nimport sys\ngetattr(sys.modules[__name__], "__dict__")["len"] = print\n',
    ),
    ("n_builtins_self", "\nprint.__self__.len = print\n"),
    (
        "n_function_globals",
        '\ndef _review():\n    pass\n_review.__globals__["len"] = print\n',
    ),
    (
        "n_frame_globals",
        '\nimport inspect\ninspect.currentframe().f_globals["len"] = print\n',
    ),
    ("n_sys_getframe", '\nimport sys\nsys._getframe(0).f_locals["len"] = print\n'),
    (
        "n_traceback_frame",
        "\ntry:\n    raise OSError\nexcept OSError as _e:\n"
        '    _e.__traceback__.tb_frame.f_locals["len"] = print\n',
    ),
    ("n_import_alias", "\n_i = __import__\n_i(__name__).len = print\n"),
    (
        "n_importlib",
        "\nimport importlib\nimportlib.import_module(__name__).len = print\n",
    ),
    ("n_loader", "\n__loader__.load_module(__name__).len = print\n"),
    ("n_exec_alias", '\n_e = exec\n_e("len = print")\n'),
    (
        "n_getattribute",
        "\ndef _review():\n    pass\n"
        '_g = object.__getattribute__(_review, "__glob" + "als__")\n_g["len"] = print\n',
    ),
    (
        "n_attrgetter",
        "\nfrom operator import attrgetter\ndef _review():\n    pass\n"
        '_g = attrgetter("__glob" + "als__")(_review)\n_g["len"] = print\n',
    ),
    ("n_gc_referrers", "\nimport gc\n_review = gc.get_referrers(print)\n"),
)
NAMESPACE_PLANTS: tuple[Plant, ...] = tuple(
    Plant(name, RULES_PY, "extract", 2, _after("", block))
    for name, block in NAMESPACE_ROUTES
)
# The exact read-only forms of `sys` the real declaring files use.
SYS_REAL_FORMS = (
    "\nimport sys\n_review = sys.argv[1:], sys.executable\n"
    'print("", file=sys.stderr)\nsys.stdout.write("")\n'
    "def _review_exit():\n    sys.exit(0)\n"
)

# Generated grid: escape forms x protected names x scope wrappers. {V} is the
# protected name and {F} a relied-on builtin. `_mut` empties whatever dict it
# reaches, through a live view's mapping too; Python itself proves each
# executed escape empties the value and each safe form leaves it equal.
GRID_PRELUDE = """

def _mut(value, *args):
    if hasattr(value, "mapping"):
        return value.mapping == _Hook()
    value.clear()
    return True


class _Hook:
    def __eq__(self, value):
        return _mut(value)

    __ne__ = __lt__ = __le__ = __gt__ = __ge__ = __contains__ = __eq__
    __ror__ = __radd__ = __rsub__ = __rand__ = __rxor__ = __rmul__ = __eq__
    __call__ = __eq__
    __hash__ = object.__hash__

    def __enter__(self):
        return _mut

    def __exit__(self, *args):
        return False


class _Raised(Exception):
    def __call__(self, value):
        return _mut(value)
"""
_REDIRECTS = (  # sub-class (a); every form binds {F} and calls {F}({V})
    "{F} = _mut\n{F}({V})\n",
    "class _C:\n    {F} = _mut\n    _r = {F}({V})\n",
    "def _f():\n    {F} = _mut\n    {F}({V})\n_f()\n",
    "def _f({F}):\n    {F}({V})\n_f(_mut)\n",
    "def _f(*, {F}=_mut):\n    {F}({V})\n_f()\n",
    "(lambda {F}: {F}({V}))(_mut)\n",
    "_r = [{F}({V}) for {F} in [_mut]]\n",
    "_r = {{F}({V}) for {F} in [_mut]}\n",
    "for {F} in [_mut]:\n    {F}({V})\n",
    "_r = [({F} := _mut), {F}({V})]\n",
    "def _g():\n    global {F}\n    {F} = _mut\n_g()\n{F}({V})\n",
    "def _o():\n    {F} = None\n    def _i():\n        nonlocal {F}\n"
    "        {F} = _mut\n    _i()\n    {F}({V})\n_o()\n",
    "match _mut:\n    case {F}:\n        {F}({V})\n",
    "with _Hook() as {F}:\n    {F}({V})\n",
    "try:\n    raise _Raised\nexcept _Raised as {F}:\n    {F}({V})\n",
    "def {F}(value):\n    return _mut(value)\n{F}({V})\n",
    "class {F}:\n    def __init__(self, value):\n        _mut(value)\n{F}({V})\n",
)
_OPERANDS = (
    tuple(  # sub-class (b)
        form
        for op in ("==", "!=", "<", "<=", ">", ">=")
        for form in (f"_r = {{V}} {op} _Hook()\n", f"_r = _Hook() {op} {{V}}\n")
    )
    + tuple(f"_r = {{V}} {op} _Hook()\n" for op in ("|", "+", "-", "&", "^", "*"))
    + (
        "_r = {V} in _Hook()\n",
        "_r = {V} not in _Hook()\n",
        '_r = "_absent" not in {V} == _Hook()\n',
        '_r = "_absent" not in {V} in _Hook()\n',
        '_r = "_absent" not in {V} != _Hook()\n',
        "_r = _Hook() < {V} < _Hook()\n",
    )
)
_VIEWS = (  # sub-class (c)
    "_r = {V}.items().mapping == _Hook()\n",
    "_r = {V}.items() == _Hook()\n",
    "_v = {V}.items()\n_r = _v.mapping == _Hook()\n",
    "_v = 0, {V}.items()\n_r = _v[1] == _Hook()\n",
    "_r = (_v := {V}.items()) == _Hook()\n",
    "for _v in [{V}.items()]:\n    _r = _v == _Hook()\n",
    "_mut({V}.items())\n",
    "_v: object = {V}.items()\n_mut(_v)\n",
)
# Escapes that stay static: running them would redirect this test process.
_STATIC = (
    "from operator import truth as {F}\n{F}({V})\n",
    "def _t[{F}]():\n    return {F}({V})\n",
    "import builtins\nbuiltins.{F} = _mut\n{F}({V})\n",
    '__builtins__["{F}"] = _mut\n{F}({V})\n',
    'sys.modules["builtins"].{F} = _mut\n{F}({V})\n',
)
GRID_SAFE = (
    "_r = len({V})\n",
    "_r = list({V})\n",
    "list({V}).clear()\n",
    '_r = "_absent" in {V}\n',
    '_r = "_absent" not in {V}\n',
    '_r = {V}.get("_absent")\n',
    "try:\n    _r = {V}[0]\nexcept KeyError:\n    pass\n",
    "_r = {V}.items()\n",
    "_r = 0, {V}.items()\n",
    "{V}.items()\n",
    "for _k in {V}:\n    _r = _k\n",
    "_r = [_k for _k in {V}]\n",
    "for _k, _w in {V}.items():\n    _r = _w\n",
    "_r = [_k for _k, _w in {V}.items()]\n",
)
GRID_ESCAPES = (
    tuple(
        (form.replace("{F}", builtin), True)
        for form in _REDIRECTS
        for builtin in sorted(_READ_CALLS)
    )
    + tuple((form, True) for form in _OPERANDS + _VIEWS)
    + tuple(
        (form.replace("{F}", builtin), False)
        for form in _STATIC
        for builtin in sorted(_RELIED)
    )
)
GRID_RUN_NAMES = ((RULES_PY, "TASK_UNITS"), (RULES_PY, "TASK_RULE_SETS"))
GRID_NAMES = (
    *GRID_RUN_NAMES,
    (BACKEND, "CHILDREN"),
    (POLICY_PY, "_FLAGS"),
    (POLICY_PY, "_CLOSED"),
    (SANDBOX_PY, "INSIDE_LINES"),
)
GRID_WRAPPERS = (
    "{}",
    "def _w():\n{}\n_w()\n",
    "class _W:\n{}\n",
    "if __name__:\n{}\n",
    "try:\n{}\nfinally:\n    pass\n",
)


def _wrap(block: str, wrappers: tuple[str, ...]) -> str:
    for wrapper in wrappers:
        inner = block if wrapper == "{}" else textwrap.indent(block, "    ")
        block = wrapper.replace("{}", inner.rstrip("\n")) + "\n"
    return block


# The three overlays confirmation cf5 executed, verbatim (S3-CTL r6).
CF5_MODULE = "eii_custodian.privacy.rules_config"
CF5_OVERLAYS = (
    (
        "cf5_self_import_rebind",
        f"import {CF5_MODULE} as _self\n_self.TASK_UNITS = {{}}\n",
    ),
    (
        "cf5_self_import_builtin",
        f"import {CF5_MODULE} as _self\n{_CF4_LEN}_self.len = _review_len\n"
        "len(TASK_UNITS)\n",
    ),
    (
        "cf5_self_from_import_mutation",
        f"from {CF5_MODULE} import TASK_UNITS as _review\n_review.clear()\n",
    ),
)
# Module, function and class scope.
CF5_SCOPES = (
    ("module", GRID_WRAPPERS[0]),
    *zip(("function", "class"), GRID_WRAPPERS[1:3], strict=True),
)
# One route per refusal branch of `_refuse_imports` and `_refuse_alias_writes`,
# each one admitted file plus one block, with the reason it must refuse with.
R6_ROUTES: tuple[tuple[str, str, str, str], ...] = (
    ("i_absolute", RULES_PY, "import heapq\n", "import outside census: import heapq"),
    ("i_aliased", RULES_PY, "import json as _j\n", "outside census: import json as"),
    ("i_relative", RULES_PY, "from . import rules\n", "outside census: from . import"),
    ("i_from", RULES_PY, "from json import loads\n", "outside census: from json"),
    ("i_function", RULES_PY, "def _p():\n    import heapq\n", "outside census"),
    (
        "i_try",
        RULES_PY,
        "try:\n    import heapq\nexcept ImportError:\n    pass\n",
        "outside census",
    ),
    ("i_if", RULES_PY, "if __name__:\n    import heapq\n", "outside census"),
    (
        "i_own_from",
        BACKEND,
        "from eii_product.backend_origin import BackendOriginRefusal\n",
        "import of own module: from eii_product.backend_origin import BackendOriginRefusal",
    ),
    ("i_own_module", POLICY_PY, "import sandbox_policy\n", "import of own module"),
    ("w_attribute", RULES_PY, "json.loads = print\n", "alias write"),
    ("w_delete", RULES_PY, "del json.loads\n", "alias write"),
    ("w_item_alias", RULES_PY, "_review = [json]\n_review[0].x = 0\n", "alias write"),
    ("w_target_root", RULES_PY, "class _C:\n    pass\n_C.x = json\n", "alias write"),
    ("m_clear", CHECKER, "GENERATED_ORIGINS.clear()\n", "alias mutation clear"),
    ("m_dunder", CHECKER, "LEVELS.__setitem__(0, 0)\n", "alias mutation __setitem__"),
    ("a_augmented", CHECKER, "MARKER_KEYS += ()\n", "alias augmented"),
)
R6_PLANTS: tuple[Plant, ...] = tuple(
    Plant(
        f"cf5_{scope}_{name.removeprefix('cf5_')}",
        RULES_PY,
        "extract",
        2,
        _after("", "\n" + _wrap(block, (wrapper,))),
    )
    for name, block in CF5_OVERLAYS
    for scope, wrapper in CF5_SCOPES
) + tuple(
    Plant(f"r6_{n}", p, "extract", 2, _after("", "\n" + b)) for n, p, b, _r in R6_ROUTES
)

# One plant per token family added in S3-CTL r7: the declaring file, the
# overlay, the pinned name Python reads back, and the exact refusal token.
R7_ROUTES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "r7_code_object",
        RULES_PY,
        "_scratch = {}\ndef _review():\n    _scratch.clear()\ndef _apply():\n"
        "    pass\n_apply.__code__ = _review.__code__.replace("
        'co_names=("TASK_UNITS", "clear"))\n_apply()\n',
        "TASK_UNITS",
        "__code__",
    ),
    (
        "r7_subclasses",
        RULES_PY,
        "_c = [c for c in object.__subclasses__()"
        ' if c.__name__ == "BuiltinImporter"][0]\n'
        "_c.load_module(__name__).TASK_UNITS.clear()\n",
        "TASK_UNITS",
        "__subclasses__",
    ),
    (
        "r7_module_read",
        CASES_PY,
        "def _review():\n    pass\n_g = string.Formatter().get_field("
        '"0.__glob" + "als__", [_review], {})[0]\n_g["CA" + "SES"] = ()\n',
        "CASES",
        "string.Formatter",
    ),
    (
        "r8_setattr_compile",
        RULES_PY,
        'def _apply():\n    pass\nobject.__setattr__(_apply, "__co" + "de__", '
        'compile("TASK_UNITS.clear()", "", "ex" + "ec"))\n_apply()\n',
        "TASK_UNITS",
        "__setattr__",
    ),
)
R7_PLANTS: tuple[Plant, ...] = tuple(
    Plant(n, p, "extract", 2, _after("", "\n" + b)) for n, p, b, _v, _t in R7_ROUTES
)

ALL_PLANTS = (
    PLANTS
    + WRITE_PLANTS
    + DEFAULT_PLANTS
    + ESCAPE_PLANTS
    + REDIRECT_PLANTS
    + NAMESPACE_PLANTS
    + R6_PLANTS
    + R7_PLANTS
)


def _grid_text(path: str, name: str, form: str, wrappers: tuple[str, ...]) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    return text + GRID_PRELUDE + _wrap(form.replace("{V}", name), wrappers)


def _refused(text: str, path: str, name: str) -> bool:
    try:
        tree = ast.parse(text)
        _refuse_imports(tree, path)
        _protect(tree, {name})
    except ExtractionFailure:
        return True
    return False


def _run_value(text: str, path: str, name: str) -> Any:
    return _executed(text, path, lambda module: dict(getattr(module, name)))


def grid_cell(
    path: str, name: str, form: str, executes: bool | None, chain: tuple[str, ...]
) -> str | None:
    """The broken property of one grid cell, or None. `executes` is None for a
    safe form, which must be accepted and leave the value equal when run;
    an escape must be refused and, when it executes, empty the value."""
    text = _grid_text(path, name, form, chain)
    run = (path, name) in GRID_RUN_NAMES
    if executes is None:
        if _refused(text, path, name):
            return "refused safe"
        whole = _grid_text(path, name, "", ())
        if run and _run_value(text, path, name) != _run_value(whole, path, name):
            return "safe changed"
        return None
    if not _refused(text, path, name):
        return "accepted escape"
    if run and executes and _run_value(text, path, name):
        return "not an escape"
    return None


def grid_cells(
    wrappers: tuple[tuple[str, ...], ...],
) -> list[tuple[str, str, str, bool | None, tuple[str, ...]]]:
    """Every escape and safe form over every protected name; the names whose
    file Python runs take every wrapper chain, the others module scope."""
    forms: list[tuple[str, bool | None]] = [*GRID_ESCAPES]
    forms += [(form, None) for form in GRID_SAFE]
    return [
        (path, name, form, executes, chain)
        for path, name in GRID_NAMES
        for chain in (wrappers if (path, name) in GRID_RUN_NAMES else ((),))
        for form, executes in forms
    ]


def grid_failures(wrappers: tuple[tuple[str, ...], ...]) -> list[str]:
    found = [(cell, grid_cell(*cell)) for cell in grid_cells(wrappers)]
    return [
        f"{broken} {cell[1]} {cell[4]} {cell[2]!r}" for cell, broken in found if broken
    ]


def _row(document: dict[str, Any], section: str, prefix: str) -> dict[str, Any]:
    rows = _as_list(_as_dict(document["gates"])[section])
    return next(
        _as_dict(row) for row in rows if str(_as_dict(row)["name"]).startswith(prefix)
    )


def _extra(name: str, got: dict[str, Any], pin: dict[str, Any]) -> None:
    if name == "s5_gate_minimum":
        live = _row(got, "section_5", "slice S5 ")
        saved = _row(pin, "section_5", "slice S5 ")
        assert live["evidence"] == saved["evidence"]
        assert live["gate"] != saved["gate"]
    elif name == "s5_controls_on_outcome":
        live = _row(got, "section_5", "slice S5 ")
        saved = _row(pin, "section_5", "slice S5 ")
        assert live["tst"] == saved["tst"]
        assert live["gate"] != saved["gate"]
    elif name == "s5_evidence_new_tst":
        live = _row(got, "section_5", "slice S5 ")
        saved = _row(pin, "section_5", "slice S5 ")
        assert live["gate"] == saved["gate"]
        assert _as_list(live["tst"]) != _as_list(saved["tst"])
        assert len(_as_list(live["tst"])) == len(_as_list(saved["tst"])) + 1
    elif name == "toml_added_min_earners":
        assert got["doc06_section5"] == pin["doc06_section5"]
        assert len(_as_list(_as_dict(got["rules_config"])["toml_rows"])) == 5
    elif name == "tst21_body_minimum":
        assert got["gates"]["section_5"] == pin["gates"]["section_5"]
        assert got["gates"]["section_5_1"] == pin["gates"]["section_5_1"]
        assert (
            _as_dict(got["gates"])["assertions"]["TST-21"]
            != _as_dict(pin["gates"])["assertions"]["TST-21"]
        )
    elif name == "suppression_allow_contexts":
        live_terms = _as_list(_as_dict(got["audience_retained"])["suppression"])
        saved_terms = _as_list(_as_dict(pin["audience_retained"])["suppression"])
        live = next(
            _as_dict(term) for term in live_terms if term["id"] == "en.suppressed"
        )
        saved = next(
            _as_dict(term) for term in saved_terms if term["id"] == "en.suppressed"
        )
        assert saved["allow_contexts"] is None
        assert live["allow_contexts"] == ["suppressed figure"]
        assert live["term"] == saved["term"]
        assert live["verdict"] == saved["verdict"]
        assert live["exempt_field_kinds"] == saved["exempt_field_kinds"]
    elif name == "case_folder_default":
        text = (ROOT / CASES_PY).read_text(encoding="utf-8")
        planted = _python_cases(
            _replace(text, 'folder: str = "."', 'folder: str = "web"')
        )
        assert got["ci_cases"] == planted
        assert got["ci_cases"] != pin["ci_cases"]
    elif name == "claim_en_without_official_alternative":
        live = _as_dict(_as_dict(got["audience_retained"])["backend_origin"])[
            "declarations"
        ]
        saved = _as_dict(_as_dict(pin["audience_retained"])["backend_origin"])[
            "declarations"
        ]
        assert "official(?:ly)?" not in str(_as_dict(live)["_CLAIM_EN"])
        assert _as_dict(live)["_CLAIM_EN"] != _as_dict(saved)["_CLAIM_EN"]


def plant_exit(plant: Plant, pin: Any) -> int:
    """1 when the plant differs from the pin, 2 on extraction, 3 on RulesRefusal."""
    text = (ROOT / plant.path).read_text(encoding="utf-8")
    mutated = plant.mutate(text)
    if plant.kind == "refusal":
        try:
            _load_rules_text(mutated)
        except RulesRefusal:
            return 3
        return 0
    if plant.kind == "added":
        try:
            _load_rules_text(mutated)
        except RulesRefusal:
            return 0
    try:
        got = project(ROOT, {plant.path: mutated})
    except ExtractionFailure:
        return 2
    if _canon(got) != _canon(pin):
        return 1
    return 0


def test_real_tree_matches_the_stored_pin() -> None:
    """The comparison fails while the pin file is absent."""
    assert PIN.is_file()
    got = project(ROOT)
    assert_cardinalities(got)
    assert _canon(got) == _canon(_pin())


def test_tolerance_exponent_case_matches_the_pin() -> None:
    """1E-7 and 1e-7 are the same literal; 1e-6 is not."""
    text = (ROOT / DOC06).read_text(encoding="utf-8")
    mutated = _replace(
        text, "feasibility_tolerance = 1e-7", "feasibility_tolerance = 1E-7"
    )
    assert _canon(project(ROOT, {DOC06: mutated})) == _canon(_pin())


def test_case_declarations_match_python() -> None:
    """The walker's cases equal Python's own instantiation, defaults included."""
    text = (ROOT / CASES_PY).read_text(encoding="utf-8")
    assert project(ROOT)["ci_cases"] == _python_cases(text)


def test_admitted_read_only_uses_keep_the_pin() -> None:
    """Each admitted read of a pinned mutable value is accepted unchanged."""
    text = (ROOT / RULES_PY).read_text(encoding="utf-8") + (
        '\n_review = TASK_UNITS["window_months"], len(TASK_UNITS)\n'
        '_review = "p" in TASK_RULE_SETS, list(TASK_UNITS), TASK_UNITS.items()\n'
        "_review = [unit for unit in TASK_UNITS]\n"
    )
    assert _canon(project(ROOT, {RULES_PY: text})) == _canon(_pin())


def test_duplicate_tst_definition_is_refused() -> None:
    text = (ROOT / DOC12).read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.startswith("| TST-21 |"))
    with pytest.raises(ExtractionFailure, match="duplicate definition"):
        project(ROOT, {DOC12: text + "\n" + line + "\n"})


def test_missing_tst_definition_is_refused() -> None:
    lines = [
        line
        for line in (ROOT / DOC12).read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith("| TST-21 |")
    ]
    with pytest.raises(ExtractionFailure, match="missing definition TST-21"):
        project(ROOT, {DOC12: "".join(lines)})


@pytest.mark.parametrize("plant", ALL_PLANTS, ids=lambda plant: plant.name)
def test_each_plant_is_red_against_the_real_pin(plant: Plant) -> None:
    """Each plant fails against the stored pin and does not rebuild it."""
    pin = _pin()
    code = plant_exit(plant, pin)
    assert code == plant.expected
    if plant.kind not in {"inequality", "added"}:
        return
    got = project(
        ROOT,
        {plant.path: plant.mutate((ROOT / plant.path).read_text(encoding="utf-8"))},
    )
    _extra(plant.name, got, _as_dict(pin))


GRID_CHAINS = tuple((wrapper,) for wrapper in GRID_WRAPPERS)


def test_generated_escape_grid_refuses_and_safe_forms_keep_the_value() -> None:
    """Every generated escape refuses, each executed one really empties the
    value, and every safe form is accepted and leaves the value equal."""
    assert grid_failures(GRID_CHAINS) == []


def test_safe_grid_forms_keep_the_pin() -> None:
    """All safe forms at once, in every scope, project equal to the pin."""
    for path in sorted({path for path, _name in GRID_NAMES}):
        names = [name for where, name in GRID_NAMES if where == path]
        block = "".join(f.replace("{V}", n) for n in names for f in GRID_SAFE)
        text = (ROOT / path).read_text(encoding="utf-8")
        for chain in GRID_CHAINS:
            got = project(ROOT, {path: text + "\n" + _wrap(block, chain)})
            assert _canon(got) == _canon(_pin())


@settings(deadline=None)
@given(
    place=st.sampled_from(GRID_RUN_NAMES),
    form=st.sampled_from([*GRID_ESCAPES, *((form, None) for form in GRID_SAFE)]),
    chain=st.lists(st.sampled_from(GRID_WRAPPERS), max_size=3).map(tuple),
)
def test_nested_scopes_keep_every_grid_property(
    place: tuple[str, str], form: tuple[str, bool | None], chain: tuple[str, ...]
) -> None:
    """Any nesting of up to three scopes keeps each cell's property."""
    assert grid_cell(place[0], place[1], form[0], form[1], chain) is None


def test_real_sys_forms_keep_the_pin() -> None:
    """The read-only `sys` forms the real tree uses stay admitted in every
    declaring Python file."""
    for path in (RULES_PY, BACKEND, POLICY_PY, SANDBOX_PY, CHECKER):
        text = (ROOT / path).read_text(encoding="utf-8") + SYS_REAL_FORMS
        assert _canon(project(ROOT, {path: text})) == _canon(_pin())


@settings(deadline=None)
@given(
    route=st.sampled_from(NAMESPACE_ROUTES),
    place=st.sampled_from(GRID_NAMES),
    chain=st.lists(st.sampled_from(GRID_WRAPPERS), max_size=3).map(tuple),
)
def test_namespace_routes_refuse_in_any_scope(
    route: tuple[str, str], place: tuple[str, str], chain: tuple[str, ...]
) -> None:
    """Every namespace route refuses in every declaring file and nesting."""
    assert _refused(_grid_text(*place, route[1], chain), *place)


# Every place a token can be named: identifier, attribute, string (whole or
# one dotted part), parameter, import, import alias, `global`.
_TOKEN_CARRIERS = (
    "_review = {T}\n",
    "_review = print.{T}\n",
    '_review = "{T}"\n',
    '_review = "_x.{T}"\n',
    "def _p({T}=None):\n    pass\n",
    "import {T}\n",
    "from _review import {T}\n",
    "import _review as {T}\n",
    "def _p():\n    global {T}\n",
)
# Every form of `sys` but the real ones of `SYS_REAL_FORMS`.
_SYS_OTHER_FORMS = (
    "import sys as _y\n",
    "from sys import argv\n",
    "import sys\n_review = sys\n",
    "import sys\nsys.argv = []\n",
    "import sys\n_review = sys.path\n",
    "import sys\nprint(sys)\n",
    "def _p(sys):\n    pass\n",
    '_review = "sys"\n',
)
TOKEN_FORMS = (
    *(
        carrier.replace("{T}", token)
        for token in sorted(_NAMESPACE)
        for carrier in _TOKEN_CARRIERS
    ),
    *_SYS_OTHER_FORMS,
)


def test_every_token_form_refuses_at_module_scope() -> None:
    """The whole domain of token forms, each alone in the rules module."""
    text = (ROOT / RULES_PY).read_text(encoding="utf-8")
    accepted = [
        f for f in TOKEN_FORMS if not _refused(f"{text}\n{f}", RULES_PY, "TASK_UNITS")
    ]
    assert accepted == []


@settings(deadline=None)
@given(
    form=st.sampled_from(TOKEN_FORMS),
    place=st.sampled_from(GRID_NAMES),
    chain=st.lists(st.sampled_from(GRID_WRAPPERS), max_size=3).map(tuple),
)
def test_each_namespace_token_refuses_wherever_named(
    form: str, place: tuple[str, str], chain: tuple[str, ...]
) -> None:
    """Each token of `_NAMESPACE`, in each carrier, and each non-real form of
    `sys` refuses alone, in every declaring file and nesting."""
    assert _refused(_grid_text(*place, form, chain), *place)


def _census() -> set[str]:
    """Every import line the real tree's declaring Python files hold."""
    return {
        line
        for path in DECLARING
        if path.endswith(".py")
        for line, _modules in _import_lines(ast.parse((ROOT / path).read_text("utf-8")))
    }


def test_import_census_equals_the_literal() -> None:
    """A real change to a declaring file's imports is a visible edit here."""
    assert _census() == set(_IMPORTS)


@pytest.mark.parametrize("scope", [s for s, _w in CF5_SCOPES])
@pytest.mark.parametrize("overlay", CF5_OVERLAYS, ids=lambda o: o[0])
def test_cf5_overlays_are_real_escapes_and_refuse(
    overlay: tuple[str, str], scope: str
) -> None:
    """Run under the probe's module name, each cf5 overlay empties
    TASK_UNITS; verbatim and under the probe name, each refuses."""
    text = (ROOT / RULES_PY).read_text(encoding="utf-8")
    wrapper = dict(CF5_SCOPES)[scope]
    probe = overlay[1].replace(CF5_MODULE, "decision_0035_probe")
    assert _run_value(text, RULES_PY, "TASK_UNITS")
    assert (
        _run_value(text + "\n" + _wrap(probe, (wrapper,)), RULES_PY, "TASK_UNITS") == {}
    )
    for block in (overlay[1], probe):
        with pytest.raises(ExtractionFailure, match="import outside census"):
            project(ROOT, {RULES_PY: text + "\n" + _wrap(block, (wrapper,))})


@pytest.mark.parametrize("route", R6_ROUTES, ids=lambda r: r[0])
def test_each_r6_refusal_branch_names_its_reason(
    route: tuple[str, str, str, str],
) -> None:
    """One admitted file plus one block refuses with that branch's reason."""
    _name, path, block, reason = route
    text = (ROOT / path).read_text(encoding="utf-8")
    with pytest.raises(ExtractionFailure, match=re.escape(reason)):
        project(ROOT, {path: text + "\n" + block})


# Every binding form that makes `_a` an alias of `{I}`, and every in-place
# change of `_a`, each with the reason it refuses with (S3-CTL r6).
_ALIAS_FORMS = (
    "_a = {I}\n",
    "_a, _b = {I}, 0\n",
    "_a = ({I}, 0)[0]\n",
    "_a = {I} if __name__ else None\n",
    "_a = None or {I}\n",
    "_r = (_a := {I})\n",
    "for _a in [{I}]:\n    pass\n",
    "_a: object = {0: {I}}\n",
)
_ALIAS_CHANGES = (
    ("_a.x = 0\n", "alias write"),
    ("del _a.x\n", "alias write"),
    ("_a[0] = 0\n", "alias write"),
    ("_a.clear()\n", "alias mutation clear"),
    ("_a.y.update()\n", "alias mutation update"),
    ("_a.__setitem__(0, 0)\n", "alias mutation __setitem__"),
    ("_a += 0\n", "alias augmented"),
)


@settings(deadline=None)
@given(
    imported=st.sampled_from(("json", "hashlib", "tomllib", "Mapping", "Path")),
    alias=st.sampled_from(_ALIAS_FORMS),
    change=st.sampled_from(_ALIAS_CHANGES),
    chain=st.lists(st.sampled_from(GRID_WRAPPERS), max_size=3).map(tuple),
)
def test_every_alias_of_an_imported_name_refuses_any_change(
    imported: str, alias: str, change: tuple[str, str], chain: tuple[str, ...]
) -> None:
    """Any alias form of a name the rules module imports, then any in-place
    change of the alias, in any nesting, refuses with the change's reason."""
    text = (ROOT / RULES_PY).read_text(encoding="utf-8")
    block = _wrap(alias.replace("{I}", imported) + change[0], chain)
    with pytest.raises(ExtractionFailure, match=re.escape(change[1])):
        project(ROOT, {RULES_PY: text + "\n" + block})


def test_a_default_argument_alias_refuses_its_change() -> None:
    text = (ROOT / RULES_PY).read_text(encoding="utf-8")
    block = "def _p(_a=json):\n    _a.clear()\n"
    with pytest.raises(ExtractionFailure, match="alias mutation clear"):
        project(ROOT, {RULES_PY: text + "\n" + block})


def test_changes_of_a_fresh_value_stay_admitted() -> None:
    """A call result or a literal is no alias: changing it keeps the pin."""
    text = (ROOT / RULES_PY).read_text(encoding="utf-8") + (
        "\n_review = json.loads('{}')\n_review.clear()\n_fresh = []\n"
        "_fresh.append(0)\n_fresh += [1]\nlist(TASK_UNITS).clear()\n"
    )
    assert _canon(project(ROOT, {RULES_PY: text})) == _canon(_pin())


def _pinned_size(path: str, name: str, overlay: str) -> int:
    """How many items Python leaves in `name` after the file plus overlay."""
    text = (ROOT / path).read_text(encoding="utf-8") + overlay
    size: int = _executed(text, path, lambda module: len(getattr(module, name)))
    return size


@pytest.mark.parametrize("route", R7_ROUTES, ids=lambda r: r[0])
def test_r7_routes_are_real_escapes_and_refuse(
    route: tuple[str, str, str, str, str],
) -> None:
    """Python empties or rebinds the pinned value; the walker refuses with
    the family's token and no other reason."""
    _name, path, block, pinned, token = route
    assert _pinned_size(path, pinned, "") > 0
    assert _pinned_size(path, pinned, "\n" + block) == 0
    text = (ROOT / path).read_text(encoding="utf-8")
    with pytest.raises(
        ExtractionFailure, match=f"^namespace reach {re.escape(token)}$"
    ):
        project(ROOT, {path: text + "\n" + block})


def _module_census() -> set[str]:
    """Every `module.attribute` the real tree's declaring files reference."""
    found: set[str] = set()
    for path in DECLARING:
        if not path.endswith(".py"):
            continue
        tree = ast.parse((ROOT / path).read_text("utf-8"))
        modules = _module_names(tree)
        found |= {
            f"{modules[node.value.id]}.{node.attr}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in modules
        }
    return found


def test_module_read_census_equals_the_literal() -> None:
    """A real change to a declaring file's module reads is a visible edit."""
    assert _module_census() == set(_MODULE_READS)


# One refusal branch each of `_refuse_module_reads`: ONE change to an admitted
# read (`json.loads(...)` in the rules module), with its exact reason.
_MODULE_READ_BRANCHES = (
    ("_review = json\n", "^namespace reach json$"),
    ("print(json)\n", "^namespace reach json$"),
    ("_review = json.decoder\n", "^namespace reach json.decoder$"),
    ("_review = hashlib.new\n", "^namespace reach hashlib.new$"),
)


@pytest.mark.parametrize("change", _MODULE_READ_BRANCHES, ids=lambda c: c[0])
def test_each_module_read_branch_names_its_reason(change: tuple[str, str]) -> None:
    text = (ROOT / RULES_PY).read_text(encoding="utf-8")
    assert _canon(project(ROOT, {RULES_PY: text + "\n_review = json.loads\n"})) == (
        _canon(_pin())
    )
    with pytest.raises(ExtractionFailure, match=change[1]):
        project(ROOT, {RULES_PY: text + "\n" + change[0]})


# The routes not added to `_NAMESPACE`, each in its strongest admitted form.
R7_NON_ROUTES = (
    "def _review(_x=None):\n    return _x\n_review.__defaults__ = ({},)\n"
    "_review.__kwdefaults__ = None\n_review.__wrapped__ = print\n",
    "def _review():\n    _x = {}\n    def _i():\n        return _x\n    return _i\n"
    "_review().__closure__[0].cell_contents = {}\n",
    "class _R:\n    def _m(self):\n        pass\n_review = _R()._m.__func__\n",
    "class _R:\n    def __init_subclass__(cls):\n        pass\n"
    "    def __set_name__(self, owner, name):\n        pass\n"
    "class _S(_R):\n    _d = _R()\n_review = _S.__mro__, _S.__bases__, _S().__class__\n",
    "def _review():\n    pass\n_r = compile('TASK_UNITS.clear()', '', 'single')\n"
    "_review = _r, type(_review), print.__reduce_ex__(2), _review.__reduce__\n",
)


# Forms near the real tree's one setter call: each refuses (S3-CTL r8).
R8_SETTER_FORMS: tuple[tuple[str, str, str], ...] = (
    # (case, overlay, refused token); each case breaks one condition of
    # `_real_setattr` alone, or is a form it never admits.
    ("alias", "_s = object.__setattr__\n", "__setattr__"),
    ("parameter", "def _f(__setattr__=None):\n    pass\n", "__setattr__"),
    (
        "not_the_func",
        "def _g(*_a):\n    pass\nclass _R:\n    def __init__(self):\n"
        "        _g(self, 'imagery_roles', object.__setattr__)\n",
        "__setattr__",
    ),
    (
        "receiver_type",
        "class _R:\n    def __init__(self):\n"
        "        type.__setattr__(self, 'imagery_roles', 0)\n",
        "__setattr__",
    ),
    (
        "receiver_super",
        "class _R:\n    def __init__(self):\n"
        "        super().__setattr__('imagery_roles', 0)\n",
        "__setattr__",
    ),
    (
        "keyword",
        "class _R:\n    def __init__(self):\n"
        "        object.__setattr__(self, 'imagery_roles', 0, x=1)\n",
        "__setattr__",
    ),
    (
        "four_arguments",
        "class _R:\n    def __init__(self):\n"
        "        object.__setattr__(self, 'imagery_roles', 0, 1)\n",
        "__setattr__",
    ),
    (
        "starred",
        "class _R:\n    def __init__(self):\n"
        "        object.__setattr__(self, 'imagery_roles', *(0,))\n",
        "__setattr__",
    ),
    (
        "first_not_a_name",
        "class _R:\n    def __init__(self):\n"
        "        object.__setattr__((self,)[0], 'imagery_roles', 0)\n",
        "__setattr__",
    ),
    (
        "first_not_self",
        "class _R:\n    def __init__(self, o):\n"
        "        object.__setattr__(o, 'imagery_roles', 0)\n",
        "__setattr__",
    ),
    (
        "second_computed",
        "class _R:\n    def __init__(self):\n"
        "        object.__setattr__(self, 'imagery' + '_roles', 0)\n",
        "__setattr__",
    ),
    (
        "second_other_name",
        "class _R:\n    def __init__(self):\n        object.__setattr__(self, 'x', 0)\n",
        "__setattr__",
    ),
    (
        "delattr",
        "class _R:\n    pass\n_r = _R()\nobject.__delattr__(_r, 'x')\n",
        "__delattr__",
    ),
)


@pytest.mark.parametrize("form", R8_SETTER_FORMS, ids=lambda f: f[0])
def test_r8_setter_forms_other_than_the_real_call_refuse(
    form: tuple[str, str, str],
) -> None:
    """Each form refuses with its own token; the real call earlier in the
    file must stay admitted for the `__delattr__` case to reach its own."""
    _case, overlay, token = form
    text = (ROOT / POLICY_PY).read_text(encoding="utf-8")
    with pytest.raises(
        ExtractionFailure, match=f"^namespace reach {re.escape(token)}$"
    ):
        project(ROOT, {POLICY_PY: text + "\n" + overlay})


def test_r8_real_setter_call_keeps_the_pin() -> None:
    """The real tree's `object.__setattr__(self, "imagery_roles", ...)` stays
    admitted: the projection of the unchanged tree equals the pin."""
    assert "object.__setattr__" in (ROOT / POLICY_PY).read_text(encoding="utf-8")
    assert _canon(project(ROOT)) == _canon(_pin())


@pytest.mark.parametrize("overlay", R7_NON_ROUTES)
def test_r7_non_routes_cannot_reach_a_pinned_value(overlay: str) -> None:
    """Python runs the overlay and leaves TASK_UNITS equal; the walker
    admits it and the projection keeps the pin."""
    text = (ROOT / RULES_PY).read_text(encoding="utf-8")
    assert _run_value(text + "\n" + overlay, RULES_PY, "TASK_UNITS") == (
        _run_value(text, RULES_PY, "TASK_UNITS")
    )
    assert _canon(project(ROOT, {RULES_PY: text + "\n" + overlay})) == _canon(_pin())


def main() -> int:
    """Print the real-tree exit and each plant exit. Writes nothing."""
    if not PIN.is_file():
        print("pin absent")
        return 1
    got = project(ROOT)
    assert_cardinalities(got)
    real = 0 if _canon(got) == _canon(_pin()) else 1
    print(f"real_tree {real}")
    pin = _pin()
    mismatches = 0
    for plant in ALL_PLANTS:
        code = plant_exit(plant, pin)
        print(f"{plant.name} {code}")
        if code != plant.expected:
            mismatches += 1
    print(f"plants {len(ALL_PLANTS)} mismatches {mismatches}")
    failures = grid_failures(GRID_CHAINS)
    print(f"grid {len(grid_cells(GRID_CHAINS))} failures {len(failures)}")
    print("\n".join(failures))
    return 1 if real or mismatches or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
