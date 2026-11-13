"""Allow gateway consumers only in scripts and evals; implementation is internal."""

import ast
import subprocess
from collections.abc import Iterable
from pathlib import Path


def check_gateway_imports(root: Path, paths: Iterable[str]) -> list[str]:
    failures: list[str] = []
    for rel in sorted(paths):
        path = Path(rel)
        if path.suffix != ".py" or path.parts[0] in ("scripts", "evals", "gateway"):
            continue
        tree = ast.parse((root / path).read_bytes(), filename=rel)
        for node in ast.walk(tree):
            names: list[str] = []
            line = 0
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                line = node.lineno
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                line = node.lineno
            elif isinstance(node, ast.Call) and node.args:
                line = node.lineno
                # Existing three-plane guard also judges aliases and expressions.
                if isinstance(node.args[0], ast.Constant) and isinstance(
                    node.args[0].value, str
                ):
                    names = [node.args[0].value]
            if any(name.split(".")[0] == "eii_gateway" for name in names):
                failures.append(
                    f"FAIL gateway-import: {rel}:{line}: consumer outside scripts or evals"
                )
    return failures


def check_repository(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = result.stdout.decode().split("\0")
    return check_gateway_imports(root, (path for path in paths if path))
