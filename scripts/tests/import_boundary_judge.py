"""Static AST judgement for import-boundary violations (not a test module)."""

from __future__ import annotations

import ast
import importlib.util
from collections.abc import Sequence
from typing import NamedTuple


class Hit(NamedTuple):
    """A single static finding in a source file."""

    kind: str
    line: int
    form: str
    target: str


def _collect_importlib_names(tree: ast.AST) -> set[str]:
    names: set[str] = {"importlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    names.add(alias.asname or alias.name.split(".")[0])
    return names


def _collect_builtins_names(tree: ast.AST) -> set[str]:
    names: set[str] = {"builtins"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    names.add(alias.asname or "builtins")
    return names


def _collect_import_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = {"import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    names.add(alias.asname or "import_module")
    return names


def _collect_dunder_import_names(tree: ast.AST) -> set[str]:
    names: set[str] = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "__import__":
                        names.add(alias.asname or "__import__")
            if node.module == "builtins":
                for alias in node.names:
                    if alias.name == "__import__":
                        names.add(alias.asname or "__import__")
    return names


def argument(call: ast.Call, index: int, name: str) -> ast.expr | None:
    """Read a positional or keyword argument from a call node."""
    if len(call.args) > index and not any(
        isinstance(a, ast.Starred) for a in call.args[: index + 1]
    ):
        return call.args[index]
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _literal_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _forbidden_first_component(target: str, forbidden: Sequence[str]) -> str | None:
    first = target.split(".")[0]
    if first in forbidden:
        return target
    return None


def _judge_import_from(node: ast.ImportFrom, forbidden: Sequence[str]) -> list[Hit]:
    if node.module is None:
        return []
    hit = _forbidden_first_component(node.module, forbidden)
    if hit is not None:
        return [
            Hit("forbidden-import", node.lineno, "from", node.module),
        ]
    return []


def _judge_import(node: ast.Import, forbidden: Sequence[str]) -> list[Hit]:
    hits: list[Hit] = []
    for alias in node.names:
        hit = _forbidden_first_component(alias.name, forbidden)
        if hit is not None:
            hits.append(Hit("forbidden-import", node.lineno, "import", alias.name))
    return hits


def _judge_import_module_call(
    call: ast.Call,
    forbidden: Sequence[str],
) -> list[Hit]:
    form = "import_module"
    name_node = argument(call, 0, "name")
    name = _literal_str(name_node)
    if name is None:
        return [Hit("dynamic-import", call.lineno, form, "")]
    if not name.startswith("."):
        hit = _forbidden_first_component(name, forbidden)
        if hit is not None:
            return [Hit("forbidden-import", call.lineno, form, name)]
        return []
    pkg_node = argument(call, 1, "package")
    pkg = _literal_str(pkg_node)
    if pkg is None or pkg == "":
        return [Hit("dynamic-import", call.lineno, form, "")]
    try:
        resolved = importlib.util.resolve_name(name, pkg)
    except ImportError:
        return [Hit("dynamic-import", call.lineno, form, "")]
    hit = _forbidden_first_component(resolved, forbidden)
    if hit is not None:
        return [Hit("forbidden-import", call.lineno, form, resolved)]
    return []


def _judge_dunder_import_call(
    call: ast.Call,
    forbidden: Sequence[str],
) -> list[Hit]:
    form = "__import__"
    name_node = argument(call, 0, "name")
    name = _literal_str(name_node)
    if name is None or name.startswith("."):
        return [Hit("dynamic-import", call.lineno, form, "")]
    level_node = argument(call, 4, "level")
    if level_node is not None:
        if not (
            isinstance(level_node, ast.Constant)
            and type(level_node.value) is int
            and level_node.value == 0
        ):
            return [Hit("dynamic-import", call.lineno, form, "")]
    else:
        if len(call.args) > 4:
            return [Hit("dynamic-import", call.lineno, form, "")]
        if any(isinstance(a, ast.Starred) for a in call.args):
            return [Hit("dynamic-import", call.lineno, form, "")]
        if any(kw.arg is None for kw in call.keywords):
            return [Hit("dynamic-import", call.lineno, form, "")]
    hit = _forbidden_first_component(name, forbidden)
    if hit is not None:
        return [Hit("forbidden-import", call.lineno, form, name)]
    return []


def _call_form(
    call: ast.Call,
    importlib_names: set[str],
    builtins_names: set[str],
    import_module_names: set[str],
    dunder_names: set[str],
) -> str | None:
    func = call.func
    if isinstance(func, ast.Name) and func.id in import_module_names:
        return "import_module"
    if isinstance(func, ast.Name) and func.id in dunder_names:
        return "__import__"
    if isinstance(func, ast.Attribute) and func.attr == "import_module":
        if isinstance(func.value, ast.Name) and func.value.id in importlib_names:
            return "import_module"
    if isinstance(func, ast.Attribute) and func.attr == "__import__":
        if isinstance(func.value, ast.Name):
            if func.value.id in importlib_names or func.value.id in builtins_names:
                return "__import__"
    return None


def judge_tree(
    tree: ast.AST,
    package: str,
    parts: Sequence[str],
    forbidden: Sequence[str],
) -> list[Hit]:
    """Walk ``tree`` and return static import-boundary hits.

    Args:
        tree: Parsed module AST.
        package: Top-level package name of the importing module.
        parts: Package parts ``[package, *folder names between tree and file]``.
        forbidden: Forbidden target top-level names from this package.

    Returns:
        Forbidden-import, relative-escape and dynamic-import hits.
    """
    del package
    importlib_names = _collect_importlib_names(tree)
    builtins_names = _collect_builtins_names(tree)
    import_module_names = _collect_import_module_names(tree)
    dunder_names = _collect_dunder_import_names(tree)
    hits: list[Hit] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:
                if node.level > len(parts):
                    hits.append(
                        Hit(
                            "relative-escape",
                            node.lineno,
                            "from",
                            "",
                        )
                    )
            else:
                hits.extend(_judge_import_from(node, forbidden))
        elif isinstance(node, ast.Import):
            hits.extend(_judge_import(node, forbidden))
        elif isinstance(node, ast.Call):
            form = _call_form(
                node,
                importlib_names,
                builtins_names,
                import_module_names,
                dunder_names,
            )
            if form == "import_module":
                hits.extend(_judge_import_module_call(node, forbidden))
            elif form == "__import__":
                hits.extend(_judge_dunder_import_call(node, forbidden))
    return hits
