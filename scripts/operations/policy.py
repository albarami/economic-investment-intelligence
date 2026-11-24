"""Static command policy, complementary to the runtime executable allow-list."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from operations.common import Refusal

PROCESS_MODULES = frozenset({"process.py", "package.py", "install.py"})
BANNED = frozenset(
    {
        "docker",
        "docker-compose",
        "compose",
        "podman",
        "pg_ctl",
        "pg_ctlcluster",
        "postgres",
        "systemctl",
        "service",
        "sudo",
    }
)


def require_sources(sources: Mapping[str, str]) -> None:
    """No operational module can introduce an unreviewed process-control path."""
    for name, source in sources.items():
        tree = ast.parse(source)
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = alias.name
                    if alias.name == "subprocess" and name not in PROCESS_MODULES:
                        raise Refusal("operation_command_refused")
            elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                # Keep the three reviewed implementations visibly qualified.
                raise Refusal("operation_command_refused")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                raise Refusal("operation_command_refused")
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "subprocess"
            ):
                raise Refusal("operation_command_refused")
            if not isinstance(node.func, ast.Attribute) or not isinstance(
                node.func.value, ast.Name
            ):
                continue
            module = aliases.get(node.func.value.id)
            if module == "os" and (
                node.func.attr == "system"
                or node.func.attr.startswith(("exec", "spawn", "posix_spawn"))
            ):
                raise Refusal("operation_command_refused")
            if module == "subprocess" and node.args:
                argument = node.args[0]
                if isinstance(argument, (ast.List, ast.Tuple)) and argument.elts:
                    first = argument.elts[0]
                    if (
                        isinstance(first, ast.Constant)
                        and isinstance(first.value, str)
                        and first.value.rsplit("/", 1)[-1] in BANNED
                    ):
                        raise Refusal("operation_command_refused")
