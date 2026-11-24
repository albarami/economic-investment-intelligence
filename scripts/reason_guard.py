"""Reject Part-A outer handlers that discard an inner closed reason."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypeGuard

MODULES = (
    "scripts/operations/build.py",
    "scripts/operations/deploy.py",
    "scripts/operations/serve.py",
    "scripts/operations/package.py",
    "scripts/commands/build_release.py",
    "scripts/commands/load_release.py",
    "scripts/commands/up_cmd.py",
    "scripts/commands/question_lab.py",
    "scripts/preflight.py",
    "scripts/sandbox_inside/public_release.py",
    "scripts/export_web_catalogue.py",
    "custodian/src/eii_custodian/release/producer.py",
    "custodian/src/eii_custodian/release/assembly.py",
    "custodian/src/eii_custodian/publicdata/registers/__main__.py",
    "product/src/eii_product/api/health.py",
    "scripts/tests/live_public_playbook.py",
    "scripts/tests/live_public_release_load.py",
    "evals/question_lab/runner.py",
)
GENERIC = frozenset(
    {
        "assembly_build_refused",
        "assembly_input_refused",
        "producer_schema_refused",
        "producer_chain_incomplete",
        "producer_review_refused",
        "installation_refused",
        "startup_refused",
        "startup_verification_failed",
        "local_assets_missing",
        "application_web_build_failed",
        "lab_input_or_execution_failed",
        "register_verification_failed",
        "proof_failed",
        "engine operation failed",
        "execution:fixture_failed",
        "fixture:unavailable",
        "rollback_retention_failed",
        "question_capacity_or_manifest",
    }
)


def _mapping(
    node: ast.AST, bindings: dict[str, ast.expr], seen: frozenset[str]
) -> dict[str, str]:
    """Reconstruct literal formatting dictionaries, preserving overwrite order."""
    result: dict[str, str] = {}
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                result.update(_mapping(value, bindings, seen))
            elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                result[key.value] = _text(value, bindings, seen)
    return result


def _text(
    node: ast.AST, bindings: dict[str, ast.expr], seen: frozenset[str] = frozenset()
) -> str:
    """Fold literal string construction only; never execute repository code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
        return _text(bindings[node.id], bindings, seen | {node.id})
    if isinstance(node, ast.JoinedStr):
        return "".join(_text(value, bindings, seen) for value in node.values)
    if isinstance(node, ast.FormattedValue):
        return _text(node.value, bindings, seen)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _text(node.left, bindings, seen) + _text(node.right, bindings, seen)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        values = (
            tuple(_text(value, bindings, seen) for value in node.right.elts)
            if isinstance(node.right, ast.Tuple)
            else _mapping(node.right, bindings, seen)
            if isinstance(node.right, ast.Dict)
            else _text(node.right, bindings, seen)
        )
        try:
            return _text(node.left, bindings, seen) % values
        except (KeyError, TypeError, ValueError):
            return ""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        keywords = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                keywords.update(_mapping(keyword.value, bindings, seen))
            else:
                keywords[keyword.arg] = _text(keyword.value, bindings, seen)
        try:
            return _text(node.func.value, bindings, seen).format(
                *(_text(value, bindings, seen) for value in node.args), **keywords
            )
        except (AttributeError, IndexError, KeyError, ValueError):
            return ""
    return "\0"


def _leaks(sink: ast.AST, name: str | None) -> bool:
    parents = {
        child: parent
        for parent in ast.walk(sink)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(sink):
        if not isinstance(node, ast.Name) or node.id != name:
            continue
        parent = parents.get(node)
        if (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "reason"
            and parent.args
            and parent.args[0] is node
        ):
            continue
        if (
            isinstance(parent, ast.Attribute)
            and parent.value is node
            and parent.attr in {"reason", "code", "exit_code"}
        ):
            continue
        return True
    return False


def _sink(node: ast.AST) -> TypeGuard[ast.Raise | ast.Return | ast.Call]:
    if isinstance(node, (ast.Raise, ast.Return)):
        return True
    return isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == "print")
        or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr
            in {
                "debug",
                "info",
                "warning",
                "error",
                "exception",
                "critical",
                "log",
                "write",
            }
        )
    )


def _masks(
    sink: ast.AST, name: str | None, carries_reason: bool, bindings: dict[str, ast.expr]
) -> bool:
    nodes = list(ast.walk(sink))
    projects = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "reason"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == name
        for node in nodes
    )
    generic = any(
        value in GENERIC or value.rpartition(": ")[2] in GENERIC
        for node in nodes
        for value in [_text(node, bindings)]
    )
    fixed_raise = (
        isinstance(sink, ast.Raise)
        and isinstance(sink.exc, ast.Call)
        and bool(sink.exc.args)
        and isinstance(sink.exc.args[0], ast.Constant)
        and isinstance(sink.exc.args[0].value, str)
    )
    return (generic or (carries_reason and fixed_raise)) and not projects


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    while not isinstance(
        node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ):
        node = parents[node]
    return node


def _bindings(
    location: ast.stmt | ast.expr, parents: dict[ast.AST, ast.AST]
) -> dict[str, ast.expr]:
    scopes = []
    node: ast.AST = location
    while node in parents:
        node = parents[node]
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            scopes.append(node)
    bindings: dict[str, ast.expr] = {}
    for scope in reversed(scopes):
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bindings.update(
                {
                    arg.arg: ast.Constant(None)
                    for arg in ast.walk(scope.args)
                    if isinstance(arg, ast.arg)
                }
            )
        for assignment in sorted(
            ast.walk(scope), key=lambda node: getattr(node, "lineno", 0)
        ):
            if (
                not isinstance(assignment, (ast.Assign, ast.AnnAssign))
                or assignment.value is None
                or assignment.lineno > location.lineno
                or _scope(assignment, parents) is not scope
            ):
                continue
            for target in (
                assignment.targets
                if isinstance(assignment, ast.Assign)
                else [assignment.target]
            ):
                if isinstance(target, ast.Name):
                    bindings[target.id] = assignment.value
    return bindings


def violations(source: str, *, functions: tuple[str, ...] = ()) -> list[int]:
    """Reject generic masking and direct caught-exception output at sinks."""
    tree = ast.parse(source)
    roots = (
        [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in functions
        ]
        if functions
        else [tree]
    )
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    failed = []
    for handler in (node for root in roots for node in ast.walk(root)):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        caught = (
            {node.id for node in ast.walk(handler.type) if isinstance(node, ast.Name)}
            if handler.type
            else {"Exception"}
        )
        carries_reason = any(
            name in {"Exception", "ValueError"}
            or (
                name.endswith(("Refusal", "Error"))
                and name not in {"OSError", "UnicodeError"}
            )
            for name in caught
        )
        sinks = [
            node
            for statement in handler.body
            for node in ast.walk(statement)
            if _sink(node)
        ]
        stored_generic = any(
            _masks(statement, handler.name, False, _bindings(statement, parents))
            for statement in handler.body
            if not _sink(statement)
        )
        swallows = len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)
        if (
            stored_generic
            or swallows
            or any(
                _leaks(sink, handler.name)
                or _masks(sink, handler.name, carries_reason, _bindings(sink, parents))
                for sink in sinks
            )
        ):
            failed.append(handler.lineno)
    return failed


def check(root: Path) -> list[str]:
    # D32 health_probe and staging evidence belong to later parts, not D54.
    return [
        f"{name}:{line}: pass the inner closed reason through reason(error)"
        for name in MODULES
        for line in violations(
            (root / name).read_text(),
            functions=("require_retained",)
            if name == "scripts/operations/deploy.py"
            else (),
        )
    ]
