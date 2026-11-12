"""Fresh-interpreter import-boundary guard."""

from __future__ import annotations

import json
import os
import site
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import import_boundary_guard as guard

# Child interpreter program (string constant, not linted as application code).
CHILD = """
import importlib, json, pkgutil, sys
cfg = json.loads(sys.argv[1])
top, banned, paths = cfg["top"], tuple(cfg["banned"]), cfg["paths"]
requested = []
class Watch:
    def find_spec(self, name, path=None, target=None):
        if "." not in name and name in banned:
            requested.append(name)
        return None
def banned_loaded():
    return sorted(n for n in tuple(sys.modules) if n.split(".")[0] in banned)
sys.meta_path.insert(0, Watch())
out = {"before": banned_loaded(), "errors": []}
for p in reversed(paths):
    sys.path.insert(0, p)
names = []
try:
    pkg = importlib.import_module(top)
    names = [top] + [i.name for i in pkgutil.walk_packages(pkg.__path__, top + ".", onerror=lambda n: None)]
except BaseException as e:
    out["errors"].append([top, type(e).__name__])
for n in names[1:]:
    try:
        importlib.import_module(n)
    except BaseException as e:
        out["errors"].append([n, type(e).__name__])
out["loaded"] = [n for n in banned_loaded() if n not in out["before"]]
out["requested"] = sorted(set(requested))
print(json.dumps(out))
"""


def child_env() -> dict[str, str]:
    """Build the child process environment (stdlib-only)."""
    env: dict[str, str] = {}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


def default_site_paths() -> list[str]:
    """Return global site-packages folders for the running interpreter."""
    return [str(p) for p in site.getsitepackages()]


def run_fresh(
    root: Path,
    package: str,
    *,
    extra_paths: Sequence[Path] = (),
    site_paths: Sequence[str] | None = None,
    flags: Sequence[str] = ("-I", "-S", "-B"),
    env: Mapping[str, str] | None = None,
    python: str | None = None,
    timeout: int = 120,
) -> list[str]:
    """Import ``package`` in an isolated child and return failure lines.

    Args:
        root: Repository root.
        package: Top-level package to import.
        extra_paths: Additional folders placed on ``sys.path`` after the source trees.
        site_paths: Site folders appended after the source trees; ``None`` uses
            ``default_site_paths()``; ``()`` uses none.
        flags: Interpreter isolation flags.
        env: Child environment; ``None`` uses ``child_env()``.
        python: Interpreter executable; ``None`` uses ``sys.executable``.
        timeout: Seconds before the child is killed.

    Returns:
        Failure lines for this package only.
    """
    if site_paths is None:
        site_dirs = default_site_paths()
    else:
        site_dirs = list(site_paths)
    src = [
        str(root / "core" / "src"),
        str(root / "custodian" / "src"),
        str(root / "product" / "src"),
    ]
    paths = [*src, *[str(p) for p in extra_paths], *site_dirs]
    cfg = {
        "top": package,
        "banned": list(guard.FORBIDDEN[package]),
        "paths": paths,
    }
    exe = python if python is not None else sys.executable
    with tempfile.TemporaryDirectory() as work:
        try:
            proc = subprocess.run(
                [exe, *flags, "-c", CHILD, json.dumps(cfg)],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                cwd=work,
                env=dict(env) if env is not None else child_env(),
            )
        except subprocess.TimeoutExpired:
            return [f"FAIL fresh-interpreter: {package}: timed out after {timeout} s"]
    if proc.returncode != 0:
        return [
            f"FAIL fresh-interpreter: {package}: harness failed (exit {proc.returncode})"
        ]
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        return [f"FAIL fresh-interpreter: {package}: harness failed (no result)"]
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return [f"FAIL fresh-interpreter: {package}: harness failed (no result)"]
    if not isinstance(payload, dict):
        return [f"FAIL fresh-interpreter: {package}: harness failed (no result)"]
    for key in ("before", "errors", "loaded", "requested"):
        if key not in payload:
            return [f"FAIL fresh-interpreter: {package}: harness failed (no result)"]
    out: list[str] = []
    before = payload["before"]
    for name in before:
        out.append(
            f"FAIL fresh-interpreter: {package}: {name} was already loaded before the import"
        )
    for name in payload["loaded"]:
        out.append(
            f"FAIL fresh-interpreter: {package}: forbidden module loaded: {name}"
        )
    for name in payload["requested"]:
        if name not in payload["loaded"] and not any(
            m.startswith(name + ".") or m == name for m in payload["loaded"]
        ):
            first = name.split(".")[0]
            if first in guard.FORBIDDEN[package]:
                out.append(
                    f"FAIL fresh-interpreter: {package}: forbidden import attempted: {first}"
                )
    for item in payload["errors"]:
        if isinstance(item, list) and len(item) == 2:
            mod, cls = item[0], item[1]
            out.append(
                f"FAIL fresh-interpreter: {package}: {mod} could not be imported ({cls})"
            )
    return sorted(out)


def check_fresh(root: Path) -> list[str]:
    """Run ``run_fresh`` for each plane package and return all failure lines."""
    lines: list[str] = []
    for package, _rel in guard.PACKAGES:
        lines.extend(run_fresh(root, package))
    return lines
