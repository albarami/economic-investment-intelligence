"""Rules for the hosted-runner workflow and for the AppArmor step (TST-62, rule 12).

Plain-text checks over the workflow file and over ``scripts/ci_sandbox.py``, and a
structural check of the module (``ast``); the tests plant one violation per rule.
"""

from __future__ import annotations

import ast
import re

RUNNER = "ubuntu-24.04"
FORBIDDEN_TOKENS = (
    "continue-on-error",
    "if:",
    "needs:",
    "paths:",
    "paths-ignore:",
    "||",
    "schedule:",
    "workflow_dispatch",
    "ubuntu-latest",
    "sysctl",
    "--share-net",
    "env:",
    "shell:",
    "working-directory:",
)
EXPECTED_RUN_STEPS = (
    "uv python install 3.14",
    "uv sync --managed-python --all-packages --locked --group engine",
    "sudo apt-get update && sudo apt-get install -y --no-install-recommends bubblewrap apparmor-profiles",
    "uv run --locked python scripts/ci_sandbox.py facts",
    "uv run --locked python scripts/ci_sandbox.py install-profile",
    "uv run --locked python scripts/engine_extensions.py fetch",
    "uv run --locked python scripts/ci_sandbox.py prove",
)
FORBIDDEN_WORDS = (
    "sysctl",
    "systemctl",
    "aa-disable",
    "aa-complain",
    "aa-teardown",
    "apparmor_parser -R",
    "setenforce",
    "unconfined",
    "tee ",
    "--share-net",
    "firejail",
    "nsjail",
    "chroot",
)
SETTING_WORD = "apparmor_restrict_unprivileged_userns"
SETTING_LINE_START = "SYSCTL = Path("
SUDO_LISTS = ("INSTALL_ARGV", "PARSER_ARGV", "LISTING_ARGV")
RUNNER_FUNCTIONS = ("run_command", "prove")
SETTING_READER = "restriction_value"
SUBPROCESS_CALLS = frozenset(
    {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "getoutput",
        "getstatusoutput",
    }
)
WRITE_CALLS = frozenset(
    {"write_text", "write_bytes", "touch", "truncate", "open", "write", "writelines"}
)
PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


def check_workflow(text: str, uv_version: str, python_series: str) -> list[str]:
    """Judge the workflow text against the rules of the plan.

    Args:
        text: The workflow file.
        uv_version: The uv version the project requires, for example ``0.11.31``.
        python_series: The content of ``.python-version``, for example ``3.14``.

    Returns:
        One ``workflow: ...`` line per broken rule, in rule order.
    """
    problems = []
    runners = re.findall(r"(?m)^\s*runs-on:\s*(\S+)\s*$", text)
    if runners != [RUNNER]:
        problems.append(f"workflow: runs-on is not {RUNNER}")
    if len(re.findall(r"(?m)^  [a-z][a-z0-9-]*:\s*$", text.split("jobs:", 1)[-1])) != 1:
        problems.append("workflow: expected exactly one job")
    problems += [
        f"workflow: forbidden: {token}" for token in FORBIDDEN_TOKENS if token in text
    ]
    if not re.search(r"(?m)^permissions:\n  contents: read\n(?=\S|\n)", text):
        problems.append("workflow: permissions are not exactly contents read")
    if len(re.findall(r"(?m)^\s*permissions:", text)) != 1:
        problems.append("workflow: expected exactly one permissions block")
    if "timeout-minutes:" not in text:
        problems.append("workflow: no timeout-minutes")
    for value in re.findall(r"(?m)^\s*(?:- )?uses:\s*(\S+)", text):
        if not PIN_RE.match(value):
            problems.append(f"workflow: action not pinned by commit: {value}")
    if not re.search(r"(?m)^  pull_request:\s*$", text):
        problems.append("workflow: missing trigger pull_request")
    if not re.search(r"(?m)^  push:\n    branches:\n      - main\s*$", text):
        problems.append("workflow: missing trigger push to main")
    runs = re.findall(r"(?m)^\s*run:\s*(.+?)\s*$", text)
    if tuple(runs) != EXPECTED_RUN_STEPS:
        problems.append("workflow: run steps differ")
    if f'version: "{uv_version}"' not in text:
        problems.append("workflow: uv version differs from required-version")
    if f"uv python install {python_series}" not in text:
        problems.append("workflow: python version differs from .python-version")
    return problems


def check_no_switch(text: str) -> list[str]:
    """Find words that would mean a system-wide switch or another sandbox tool.

    Args:
        text: A file of the sandbox step or the workflow.

    Returns:
        One ``forbidden: <word>`` line per word found. The name of the kernel setting
        is allowed only on the line that defines the read-only constant ``SYSCTL``.
    """
    found = [f"forbidden: {word}" for word in FORBIDDEN_WORDS if word in text]
    for line in text.splitlines():
        if SETTING_WORD in line and not line.startswith(SETTING_LINE_START):
            found.append(f"forbidden: {SETTING_WORD}")
    return found


class _Structure(ast.NodeVisitor):
    """Collect the places where ``ci_sandbox.py`` could run or write more than it may."""

    def __init__(self) -> None:
        self.found: list[str] = []
        self.scope: list[str] = []
        self.sudo_allowed: set[int] = set()

    def where(self) -> str:
        return self.scope[-1] if self.scope else "<module>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if (
            len(names) == 1
            and names[0] in SUDO_LISTS
            and isinstance(node.value, ast.List)
            and node.value.elts
        ):
            self.sudo_allowed.add(id(node.value.elts[0]))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in ("subprocess", "os"):
            self.found.append(f"forbidden: from {node.module} import")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "SYSCTL" and isinstance(node.ctx, ast.Load):
            if self.where() != SETTING_READER:
                self.found.append(f"forbidden: SYSCTL used in {self.where()}")

    def visit_Constant(self, node: ast.Constant) -> None:
        if (
            isinstance(node.value, str)
            and "sudo" in node.value
            and id(node) not in self.sudo_allowed
        ):
            self.found.append(
                "forbidden: sudo outside INSTALL_ARGV, PARSER_ARGV, LISTING_ARGV"
            )

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if isinstance(function, ast.Attribute):
            owner = function.value.id if isinstance(function.value, ast.Name) else ""
            if (
                owner == "subprocess"
                and function.attr in SUBPROCESS_CALLS
                and self.where() not in RUNNER_FUNCTIONS
            ):
                self.found.append(
                    f"forbidden: subprocess.{function.attr} in {self.where()}"
                )
            if owner == "os" and function.attr.startswith(
                ("system", "popen", "exec", "spawn", "posix_spawn")
            ):
                self.found.append(f"forbidden: os.{function.attr} in {self.where()}")
            if function.attr in WRITE_CALLS:
                self.found.append(f"forbidden: {function.attr} in {self.where()}")
        elif isinstance(function, ast.Name) and function.id in WRITE_CALLS:
            self.found.append(f"forbidden: {function.id} in {self.where()}")
        for keyword in node.keywords:
            if (
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            ):
                self.found.append(f"forbidden: shell=True in {self.where()}")
        self.generic_visit(node)


def check_ci_module(text: str) -> list[str]:
    """Judge ``scripts/ci_sandbox.py`` by its words and by its syntax tree.

    The word list and the setting-line rule of ``check_no_switch`` apply. In
    addition: the text ``sudo`` is allowed only as the first element of the three
    argument lists; ``subprocess`` is called only in ``run_command`` and ``prove``;
    the constant ``SYSCTL`` is read only in ``restriction_value``; no call writes,
    opens, truncates or creates a file; ``shell=True`` and the ``os`` functions that
    start programs are refused.

    Args:
        text: The source of the module.

    Returns:
        Sorted ``forbidden: ...`` lines without repeats; empty when the module is clean.
    """
    visitor = _Structure()
    visitor.visit(ast.parse(text))
    return sorted(set(check_no_switch(text) + visitor.found))
