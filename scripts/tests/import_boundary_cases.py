"""Shared tables and fixture builders for import-boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]

PACKAGE_TREES: dict[str, str] = {
    "eii_core": "core/src/eii_core",
    "eii_custodian": "custodian/src/eii_custodian",
    "eii_product": "product/src/eii_product",
}

EDGES: list[tuple[str, str]] = [
    ("eii_core", "eii_custodian"),
    ("eii_core", "eii_product"),
    ("eii_core", "eii_gateway"),
    ("eii_custodian", "eii_product"),
    ("eii_custodian", "eii_gateway"),
    ("eii_product", "eii_custodian"),
    ("eii_product", "eii_gateway"),
]

ALLOWED: list[tuple[str, str]] = [
    ("eii_custodian", "eii_core"),
    ("eii_product", "eii_core"),
    ("eii_core", "eii_core"),
    ("eii_custodian", "eii_custodian"),
    ("eii_product", "eii_product"),
]

_FRESH_LOADED = (
    "FAIL fresh-interpreter: eii_product: forbidden module loaded: eii_custodian"
)
_FRESH_ATTEMPTED = (
    "FAIL fresh-interpreter: eii_product: forbidden import attempted: eii_custodian"
)


class Mechanism(NamedTuple):
    """One row of the judged import-form table."""

    id: str
    lines: tuple[str, ...]
    form: str
    target: str
    line: int


MECHANISMS: list[Mechanism] = [
    Mechanism("S1", ("import T",), "import", "T", 1),
    Mechanism("S2", ("import T.sub",), "import", "T.sub", 1),
    Mechanism("S3", ("import T as q",), "import", "T", 1),
    Mechanism("S4", ("from T import n as m",), "from", "T", 1),
    Mechanism("S5", ("from T.sub import n",), "from", "T.sub", 1),
    Mechanism("S6", ("import os, T",), "import", "T", 1),
    Mechanism(
        "D1",
        ("import importlib", 'importlib.import_module("T.sub")'),
        "import_module",
        "T.sub",
        2,
    ),
    Mechanism(
        "D2",
        ("import importlib", 'importlib.import_module(name="T")'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D3",
        ("import importlib as il", 'il.import_module("T")'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D4",
        ("from importlib import import_module", 'import_module("T")'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D5",
        ("from importlib import import_module as im", 'im("T")'),
        "import_module",
        "T",
        2,
    ),
    Mechanism("D6", ('__import__("T")',), "__import__", "T", 1),
    Mechanism(
        "D7",
        ("import importlib", 'importlib.import_module(".sub", "T")'),
        "import_module",
        "T.sub",
        2,
    ),
    Mechanism(
        "D8",
        ("import importlib", 'importlib.import_module(".sub", package="T")'),
        "import_module",
        "T.sub",
        2,
    ),
    Mechanism("D9", ('__import__("T", None, None, (), 0)',), "__import__", "T", 1),
    Mechanism("D10", ('__import__("T", level=0)',), "__import__", "T", 1),
    Mechanism("D11", ('__import__("T", fromlist=["a"])',), "__import__", "T", 1),
    Mechanism(
        "D12",
        ("import importlib", 'importlib.import_module("T", "pkg")'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D13",
        ("import importlib", 'importlib.import_module("T", package="pkg")'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D14",
        ("import importlib", 'importlib.import_module("T", *extra)'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D15",
        ("import importlib", 'importlib.import_module("T", **extra)'),
        "import_module",
        "T",
        2,
    ),
    Mechanism(
        "D16",
        ('__import__("T", None, None, (), 0, *extra)',),
        "__import__",
        "T",
        1,
    ),
    Mechanism("D17", ('__import__("T", level=0, **extra)',), "__import__", "T", 1),
    Mechanism(
        "D18",
        ("import importlib", 'importlib.import_module(".sub", "T", *extra)'),
        "import_module",
        "T.sub",
        2,
    ),
    Mechanism(
        "D19",
        ("import importlib", 'importlib.import_module(".sub", *extra, package="T")'),
        "import_module",
        "T.sub",
        2,
    ),
    Mechanism(
        "D20",
        ("import importlib", 'importlib.__import__("T")'),
        "__import__",
        "T",
        2,
    ),
    Mechanism(
        "D21",
        ("import builtins", 'builtins.__import__("T")'),
        "__import__",
        "T",
        2,
    ),
    Mechanism(
        "D22",
        ("import builtins as b", 'b.__import__("T")'),
        "__import__",
        "T",
        2,
    ),
    Mechanism(
        "D23",
        ("from builtins import __import__ as f", 'f("T")'),
        "__import__",
        "T",
        2,
    ),
    Mechanism(
        "D24",
        ("from importlib import __import__ as f", 'f("T")'),
        "__import__",
        "T",
        2,
    ),
]

NOTE_CASES: list[tuple[str, ...]] = [
    ('importlib.import_module("eii_" + "custodian")',),
    ('importlib.import_module(f"eii_custodian")',),
    ("importlib.import_module(name)",),
    ("importlib.import_module(*args)",),
    ("importlib.import_module(**kwargs)",),
    ("importlib.import_module()",),
    ("__import__(name)",),
    ('__import__("eii_custodian", None, None, (), 1)',),
    ('importlib.import_module(".sub", pkg)',),
    ('importlib.import_module("..x", "eii_product")',),
    ('__import__("eii_custodian", level=1)',),
    ('importlib.import_module(".sub", package=None)',),
    ('importlib.import_module(".sub", *extra)',),
    ('importlib.import_module(*extra, "eii_custodian")',),
    ('__import__("eii_custodian", *extra)',),
    ('__import__("eii_custodian", None, None, (), *extra)',),
    ('__import__("eii_custodian", **extra)',),
    ('__import__("eii_custodian", level=None)',),
    ('__import__("eii_custodian", level=False)',),
    ('__import__(".sub")',),
    ('importlib.import_module(name=".sub")',),
]

_PYC_PAYLOAD = b"\x00import eii_custodian"

NOT_JUDGED: list[tuple[str, str, bytes]] = [
    (
        "N1",
        "planted.py",
        b'import importlib\nf = importlib.import_module\nf("eii_custodian")\n',
    ),
    (
        "N2",
        "planted.py",
        b'import importlib\ngetattr(importlib, "import_module")("eii_custodian")\n',
    ),
    ("N3", "planted.py", b'exec("import eii_custodian")\n'),
    ("N4", "planted.py", b"eval(\"__import__('eii_custodian')\")\n"),
    ("N5", "planted.py", b'compile("import eii_custodian", "x", "exec")\n'),
    (
        "N6",
        "planted.py",
        b'import pkgutil\npkgutil.resolve_name("eii_custodian")\n',
    ),
    (
        "N7",
        "planted.py",
        b'import sys\nsys.modules["eii_custodian"] = sys\n',
    ),
    (
        "N8",
        "planted.py",
        b'import importlib.util\nimportlib.util.spec_from_file_location("zz", "p.py")\n',
    ),
    ("N9", "planted.py", b'import runpy\nrunpy.run_path("p.py")\n'),
    ("N10", "planted.py", b"import ctypes\nctypes.CDLL(None)\n"),
    (
        "N11",
        "planted.py",
        b"import subprocess\nimport sys\n"
        b'subprocess.run([sys.executable, "-c", "import eii_custodian"])\n',
    ),
    (
        "N12",
        "planted.py",
        b'import importlib.util\nimportlib.util.find_spec("eii_custodian")\n',
    ),
    (
        "N13",
        "planted.py",
        b"import importlib\nimport os\n"
        b'x = importlib.import_module("os")\nimportlib.reload(x)\n',
    ),
    (
        "N14",
        "planted.py",
        b'import importlib.resources\nimportlib.resources.files("eii_custodian")\n',
    ),
    (
        "N15",
        "planted.py",
        b'import pkgutil\npkgutil.get_data("eii_custodian", "x")\n',
    ),
    (
        "N16",
        "planted.py",
        b'import unittest.mock\nunittest.mock.patch("eii_custodian.x").start()\n',
    ),
    (
        "N17",
        "planted.py",
        b'import pydoc\npydoc.locate("eii_custodian.x")\n',
    ),
    (
        "N18",
        "planted.py",
        b'import importlib\nlist(map(importlib.import_module, ["eii_custodian"]))\n',
    ),
    (
        "N19",
        "planted.py",
        b"from importlib import import_module\n"
        b'import functools\nfunctools.partial(import_module, "eii_custodian")\n',
    ),
    ("N20", "m.pyc", _PYC_PAYLOAD),
    ("N21", "ns/m.pyc", _PYC_PAYLOAD),
    ("N22", "ext.so", _PYC_PAYLOAD),
    ("N23", "stub.pyi", b"import eii_custodian\n"),
    ("N24", "planted.py", b'x = "EII_DECISION_" + "PROVIDER"\n'),
    (
        "N25",
        "planted.py",
        b'import pkgutil\npkgutil.importlib.import_module("eii_custodian")\n',
    ),
    (
        "N26",
        "planted.py",
        b"import importlib\nimport sys\n"
        b'sys.modules["importlib"].import_module("eii_custodian")\n',
    ),
    (
        "N27",
        "planted.py",
        b"import importlib._bootstrap\n"
        b'importlib._bootstrap._gcd_import("eii_custodian")\n',
    ),
    (
        "N28",
        "planted.py",
        b'import builtins\nbuiltins.__dict__["__import__"]("eii_custodian")\n',
    ),
    (
        "N29",
        "planted.py",
        b'from importlib.__init__ import import_module as im\nim("eii_custodian")\n',
    ),
    (
        "N30",
        "planted.py",
        b'from pkgutil import importlib as il\nil.import_module("eii_custodian")\n',
    ),
]

CHILD_CASES: list[tuple[str, str, list[str]]] = [
    ("N3", "exec", [_FRESH_LOADED]),
    ("N7", "sys.modules assignment", [_FRESH_LOADED]),
    ("N12", "find_spec", [_FRESH_ATTEMPTED]),
    ("N18", "map(importlib.import_module, ...)", [_FRESH_LOADED]),
    ("N8", "spec_from_file_location + exec_module", []),
    ("N9", "runpy.run_path", []),
    ("N10", "ctypes.CDLL", []),
    ("N11", "subprocess custodian import", []),
    ("sneak.pyc", "package-root sourceless pyc", [_FRESH_LOADED]),
    ("ns/sneak.pyc", "namespace sourceless pyc", []),
]


def package_rel(package: str) -> str:
    """Return the repository-relative source tree path for a package.

    Args:
        package: Top-level package name (``eii_core``, ``eii_custodian``, or
            ``eii_product``).

    Returns:
        Path relative to the repository root, using forward slashes.

    Raises:
        KeyError: If ``package`` is not one of the three plane packages.
    """
    return PACKAGE_TREES[package]


def package_dir(root: Path, package: str) -> Path:
    """Return the absolute path to a package source tree.

    Args:
        root: Repository root.
        package: Top-level package name.

    Returns:
        Absolute path to the package directory under ``root``.
    """
    return root / package_rel(package)


def planted_path(root: Path, package: str, rel_name: str = "planted.py") -> Path:
    """Return the absolute path where a planted file would live.

    Args:
        root: Repository root.
        package: Package that owns the planted file.
        rel_name: File name relative to the package tree (may include subfolders).

    Returns:
        Absolute path to the planted file (parent directories are not created).
    """
    return package_dir(root, package) / rel_name


def planted_rel_path(package: str, rel_name: str = "planted.py") -> str:
    """Return the repository-relative path to a planted file.

    Args:
        package: Package that owns the planted file.
        rel_name: File name relative to the package tree.

    Returns:
        Posix path from the repository root to the planted file.
    """
    return f"{package_rel(package)}/{rel_name}"


def write_planted(
    root: Path,
    package: str,
    content: str | bytes,
    rel_name: str = "planted.py",
) -> Path:
    """Write a planted file under a package tree.

    Args:
        root: Repository root.
        package: Package that owns the planted file.
        content: File body as text or bytes.
        rel_name: File name relative to the package tree.

    Returns:
        Absolute path to the written file.
    """
    path = planted_path(root, package, rel_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def write_not_judged(root: Path, row: tuple[str, str, bytes]) -> Path:
    """Plant one not-judged form under the product package tree.

    Args:
        root: Repository root.
        row: One ``NOT_JUDGED`` entry ``(label, rel_path, content)``.

    Returns:
        Absolute path to the written file.
    """
    _label, rel_name, content = row
    return write_planted(root, "eii_product", content, rel_name)


def write_custodian_other(root: Path) -> Path:
    """Write the custodian helper module used by child visibility tests.

    Args:
        root: Repository root.

    Returns:
        Absolute path to ``custodian/src/eii_custodian/other.py``.
    """
    path = planted_path(root, "eii_custodian", "other.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("VALUE = 1\n", encoding="utf-8")
    return path


def make_tree(root: Path, *, gateway: bool = False) -> None:
    """Create minimal synthetic package trees for boundary tests.

    Args:
        root: Directory that will hold ``core/``, ``custodian/``, and
            ``product/`` package layouts.
        gateway: When true, also write a stub ``eii_gateway`` package under
            ``gateway/src/eii_gateway``.
    """
    layouts = (
        ("eii_core", "core/src/eii_core"),
        ("eii_custodian", "custodian/src/eii_custodian"),
        ("eii_product", "product/src/eii_product"),
    )
    for _name, rel in layouts:
        base = root / rel
        base.mkdir(parents=True, exist_ok=True)
        (base / "__init__.py").write_text('__version__ = "0.0.0"\n', encoding="utf-8")
        sub = base / "sub"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "__init__.py").write_text("from . import mod\n", encoding="utf-8")
        (sub / "mod.py").write_text("from .. import __version__\n", encoding="utf-8")
    if gateway:
        gw = root / "gateway" / "src" / "eii_gateway"
        gw.mkdir(parents=True, exist_ok=True)
        (gw / "__init__.py").write_text('__version__ = "0.0.0"\n', encoding="utf-8")


def gateway_src(root: Path) -> Path:
    """Return the gateway stub ``src`` folder for ``run_fresh`` extra paths.

    Args:
        root: Repository root of a fixture that was built with ``gateway=True``.

    Returns:
        Absolute path to ``gateway/src``.
    """
    return root / "gateway" / "src"


def substitute_target(pattern: str, forbidden: str) -> str:
    """Replace the placeholder ``T`` in a mechanism target pattern.

    Args:
        pattern: Target pattern from the mechanisms table (contains ``T``).
        forbidden: Forbidden module name to substitute.

    Returns:
        Resolved import target string.
    """
    return pattern.replace("T", forbidden)


def mechanism_source(mech: Mechanism, forbidden: str) -> str:
    """Render mechanism source with ``T`` replaced by the forbidden package.

    Args:
        mech: Mechanism row from ``MECHANISMS``.
        forbidden: Forbidden module name to substitute for ``T``.

    Returns:
        Full source text for a ``planted.py`` file, including a trailing newline.
    """
    lines = [line.replace("T", forbidden) for line in mech.lines]
    return "\n".join(lines) + "\n"


def note_case_source(call_lines: tuple[str, ...]) -> str:
    """Build product ``planted.py`` source for a dynamic-import note case.

    Args:
        call_lines: Call line or lines from ``NOTE_CASES`` (line 2 onward).

    Returns:
        Source with ``import importlib`` on line 1 and the call lines following.
    """
    body = ["import importlib", *call_lines]
    return "\n".join(body) + "\n"


def note_form_from_call(call_line: str) -> str:
    """Return the note ``form`` field for a dynamic-import call line.

    Args:
        call_line: Second-line call source from a note case.

    Returns:
        Either ``import_module`` or ``__import__``.
    """
    stripped = call_line.lstrip()
    if stripped.startswith("__import__"):
        return "__import__"
    return "import_module"


def expected_forbidden_line(
    rel_path: str,
    line: int,
    form: str,
    target: str,
    source_package: str,
    forbidden_package: str,
) -> str:
    """Build an expected ``forbidden-import`` failure line.

    Args:
        rel_path: File path relative to the repository root.
        line: One-based line number of the import.
        form: Import form (`import`, `from`, `import_module`, or `__import__`).
        target: Resolved forbidden module target.
        source_package: Package owning the file.
        forbidden_package: First component of the forbidden target.

    Returns:
        Full ``FAIL forbidden-import`` line as produced by the static guard.
    """
    return (
        f"FAIL forbidden-import: {rel_path}:{line}: {form} {target} "
        f"({source_package} -> {forbidden_package})"
    )


def expected_mechanism_failure(
    package: str,
    forbidden: str,
    mech: Mechanism,
    rel_name: str = "planted.py",
) -> str:
    """Build the expected failure for one edge times one mechanism planting.

    Args:
        package: Source package name.
        forbidden: Forbidden module name substituted for ``T``.
        mech: Mechanism row from ``MECHANISMS``.
        rel_name: Planted file name relative to the package tree.

    Returns:
        Expected ``forbidden-import`` failure line.
    """
    rel_path = planted_rel_path(package, rel_name)
    target = substitute_target(mech.target, forbidden)
    return expected_forbidden_line(
        rel_path,
        mech.line,
        mech.form,
        target,
        package,
        forbidden,
    )


def expected_relative_escape_line(rel_path: str, line: int) -> str:
    """Build an expected ``relative-escape`` failure line.

    Args:
        rel_path: File path relative to the repository root.
        line: One-based line number of the relative import.

    Returns:
        Full ``FAIL relative-escape`` line.
    """
    return (
        f"FAIL relative-escape: {rel_path}:{line}: "
        "relative import goes beyond its top-level package"
    )


def expected_dynamic_note_line(rel_path: str, line: int, form: str) -> str:
    """Build an expected ``NOTE dynamic-import`` line.

    Args:
        rel_path: File path relative to the repository root.
        line: One-based line number of the dynamic call.
        form: Either ``import_module`` or ``__import__``.

    Returns:
        Full ``NOTE dynamic-import`` line.
    """
    return (
        f"NOTE dynamic-import: {rel_path}:{line}: {form} "
        "argument cannot be resolved statically"
    )


def expected_note_for_case(
    call_lines: tuple[str, ...], rel_name: str = "planted.py"
) -> str:
    """Build the expected note line for one ``NOTE_CASES`` entry in the product tree.

    Args:
        call_lines: Tuple from ``NOTE_CASES``.
        rel_name: Planted file name relative to the product package.

    Returns:
        Expected ``NOTE dynamic-import`` line at line 2.
    """
    rel_path = planted_rel_path("eii_product", rel_name)
    form = note_form_from_call(call_lines[0])
    return expected_dynamic_note_line(rel_path, 2, form)


def expected_env_name_line(rel_path: str, line: int, name: str) -> str:
    """Build an expected ``env-name`` failure line.

    Args:
        rel_path: File path relative to the repository root.
        line: One-based line number where the name first appears.
        name: Environment variable name that must not appear in source trees.

    Returns:
        Full ``FAIL env-name`` line.
    """
    return f"FAIL env-name: {rel_path}:{line}: contains {name}"


def expected_src_tree_missing(rel: str) -> str:
    """Build an expected missing source-tree failure line.

    Args:
        rel: Repository-relative path to the expected package tree.

    Returns:
        Full ``FAIL src-tree`` line for a missing directory.
    """
    return f"FAIL src-tree: {rel}: missing or not a directory"


def expected_src_tree_no_python(rel: str) -> str:
    """Build an expected empty source-tree failure line.

    Args:
        rel: Repository-relative path to the package tree.

    Returns:
        Full ``FAIL src-tree`` line when no ``.py`` file exists.
    """
    return f"FAIL src-tree: {rel}: no Python file"


def expected_symlink_line(rel_path: str) -> str:
    """Build an expected symbolic-link failure line.

    Args:
        rel_path: Repository-relative path to the link.

    Returns:
        Full ``FAIL symlink`` line.
    """
    return f"FAIL symlink: {rel_path}: symbolic link under a source tree"


def expected_unparsable_read(rel_path: str, errno_name: str) -> str:
    """Build an expected unreadable-file failure line.

    Args:
        rel_path: Repository-relative path to the file or folder.
        errno_name: ``errno.errorcode`` name (for example ``EACCES``).

    Returns:
        Full ``FAIL unparsable`` line for a read error.
    """
    return f"FAIL unparsable: {rel_path}: cannot be read ({errno_name})"


def expected_unparsable_parse(rel_path: str, exc_name: str) -> str:
    """Build an expected unparsable-source failure line.

    Args:
        rel_path: Repository-relative path to the ``.py`` file.
        exc_name: Exception class name from ``type(exc).__name__``.

    Returns:
        Full ``FAIL unparsable`` line for a parse error.
    """
    return f"FAIL unparsable: {rel_path}: cannot be parsed ({exc_name})"


def expected_fresh_loaded(package: str, module: str) -> str:
    """Build an expected forbidden-module-loaded fresh-interpreter line.

    Args:
        package: Package under test in the child.
        module: Forbidden module that was loaded.

    Returns:
        Full ``FAIL fresh-interpreter`` line.
    """
    return f"FAIL fresh-interpreter: {package}: forbidden module loaded: {module}"


def expected_fresh_attempted(package: str, name: str) -> str:
    """Build an expected forbidden-import-attempted fresh-interpreter line.

    Args:
        package: Package under test in the child.
        name: Top-level forbidden name that was requested.

    Returns:
        Full ``FAIL fresh-interpreter`` line.
    """
    return f"FAIL fresh-interpreter: {package}: forbidden import attempted: {name}"


def expected_fresh_import_error(package: str, module: str, exc_name: str) -> str:
    """Build an expected import-error fresh-interpreter line.

    Args:
        package: Package under test in the child.
        module: Module that failed to import.
        exc_name: Exception class name reported by the child.

    Returns:
        Full ``FAIL fresh-interpreter`` line.
    """
    return f"FAIL fresh-interpreter: {package}: {module} could not be imported ({exc_name})"


def expected_fresh_timeout(package: str, timeout: int) -> str:
    """Build an expected fresh-interpreter timeout line.

    Args:
        package: Package under test in the child.
        timeout: Timeout seconds passed to ``run_fresh``.

    Returns:
        Full timeout failure line.
    """
    return f"FAIL fresh-interpreter: {package}: timed out after {timeout} s"


def expected_fresh_harness_exit(package: str, exit_code: int) -> str:
    """Build an expected harness non-zero exit failure line.

    Args:
        package: Package under test in the child.
        exit_code: Child process exit status.

    Returns:
        Full harness failure line.
    """
    return f"FAIL fresh-interpreter: {package}: harness failed (exit {exit_code})"


def expected_fresh_harness_no_result(package: str) -> str:
    """Build an expected harness missing-result failure line.

    Args:
        package: Package under test in the child.

    Returns:
        Full harness failure line when JSON output is missing.
    """
    return f"FAIL fresh-interpreter: {package}: harness failed (no result)"


def expected_fresh_already_loaded(package: str, module: str) -> str:
    """Build an expected already-loaded fresh-interpreter failure line.

    Args:
        package: Package under test in the child.
        module: Forbidden module present before the import walk.

    Returns:
        Full failure line.
    """
    return f"FAIL fresh-interpreter: {package}: {module} was already loaded before the import"
