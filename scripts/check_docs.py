#!/usr/bin/env python3
"""Documentation and repository-safety check.

Run from the repository root:

    python3 scripts/check_docs.py

Exit code 0 means every check passed. Any other exit code means at least one
check failed; each failure is printed as ``FAIL <check>: <path>:<line>: <detail>``.

Checks
------
1. Required files exist.
2. AGENTS.md and CLAUDE.md are byte-identical.
3. Relative Markdown links point at files that exist.
4. Every numbered document starts with the standard header block.
5. Requirement IDs are defined exactly once, and every referenced ID is defined.
6. No text file contains a forbidden pattern: an absolute local path, an
   e-mail address, a secret-shaped token, or an identifier-shaped number
   (a bare run of exactly 8 or exactly 11 digits).

Which files are scanned: inside a git checkout, the files git tracks plus the
untracked files it does not ignore; elsewhere, every text file under the root
except build and cache folders.

Extra forbidden patterns: if the environment variable
``EII_FORBIDDEN_PATTERNS_FILE`` names a readable file, each non-empty line of it
that does not start with ``#`` is a regular expression that is also forbidden.

Only the Python standard library is used.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "TASKS.md",
    "PROGRESS.md",
    "OPEN_ITEMS.md",
    "LICENSE",
    "docs/README.md",
    "docs/01_PROJECT_BRIEF.md",
    "docs/02_ARCHITECTURE.md",
    "docs/03_DATA_CONTRACTS.md",
    "docs/04_PUBLIC_DATA_PACK.md",
    "docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md",
    "docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md",
    "docs/07_ECONOMIC_METHODS.md",
    "docs/08_BACKEND.md",
    "docs/09_AI_ASSISTANT.md",
    "docs/10_FRONTEND.md",
    "docs/11_DESIGN_DIRECTION.md",
    "docs/12_TESTING_AND_QUALITY.md",
    "docs/13_DEPLOYMENT_AND_OPERATIONS.md",
    "docs/14_IMPLEMENTATION_PLAN.md",
    "docs/15_REVIEWER_CHECKLIST.md",
    "docs/16_DEMO_RUNBOOK.md",
    "docs/GLOSSARY.md",
]

# Directories that are never scanned when the root is not a git checkout.
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "data",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".html",
    ".sql",
    ".sh",
    ".cfg",
    ".ini",
    ".env",
}
TEXT_NAMES = {"LICENSE", "eii", ".gitignore", ".gitattributes", "Makefile"}

REQUIREMENT_PREFIXES = (
    "BRF",
    "ARC",
    "DAT",
    "PUB",
    "SYN",
    "PRV",
    "MTH",
    "BE",
    "AI",
    "FE",
    "DES",
    "TST",
    "OPS",
    "PLN",
    "REV",
    "RUN",
)
PREFIX_ALTERNATION = "|".join(REQUIREMENT_PREFIXES)
ID_RE = re.compile(
    rf"(?<![A-Za-z0-9-])(?:{PREFIX_ALTERNATION})-\d{{2,3}}(?![A-Za-z0-9])"
)
# A definition is the first cell of a table row.
DEF_RE = re.compile(rf"^\|\s*((?:{PREFIX_ALTERNATION})-\d{{2,3}})\s*\|")

LINK_RE = re.compile(r"(?<!\!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

HEADER_ROWS = ("| Status |", "| Date |", "| Owner |", "| Purpose |")
NUMBERED_DOC_RE = re.compile(r"^docs/\d{2}_[A-Z0-9_]+\.md$")

# Forbidden patterns. Each entry: (check name, compiled pattern, explanation).
FORBIDDEN = [
    (
        "local-path",
        re.compile(
            r"/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z]|[A-Za-z]:\\\\Users\\\\|\\\\\\\\wsl"
        ),
        "absolute local path",
    ),
    (
        "email",
        re.compile(
            r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
        ),
        "e-mail address",
    ),
    (
        "secret",
        re.compile(
            r"sk-ant-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
            r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
        ),
        "secret-shaped token",
    ),
    (
        "identifier-number",
        re.compile(r"(?<![0-9A-Za-z,.:/_#-])(?:\d{8}|\d{11})(?![0-9A-Za-z,_-]|\.\d)"),
        "identifier-shaped number (exactly 8 or 11 digits)",
    ),
]

# E-mail-shaped strings that are allowed (none are personal addresses).
EMAIL_ALLOW = {"git@github.com"}


def git_listed_files() -> list[Path] | None:
    """Files git tracks plus untracked files it does not ignore; None outside a checkout."""
    if not (ROOT / ".git").exists():
        return None
    try:
        done = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    names = [
        name
        for name in done.stdout.decode("utf-8", errors="replace").split("\0")
        if name
    ]
    return [ROOT / name for name in names]


def iter_text_files() -> list[Path]:
    listed = git_listed_files()
    if listed is None:
        candidates = [
            path
            for path in ROOT.rglob("*")
            if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
        ]
    else:
        candidates = listed
    files: list[Path] = []
    for path in sorted(set(candidates)):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if rel.name.endswith("Zone.Identifier"):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or rel.name in TEXT_NAMES:
            files.append(path)
    return files


def load_extra_patterns() -> list[tuple[str, re.Pattern[str], str]]:
    """Extra forbidden patterns from the file named by EII_FORBIDDEN_PATTERNS_FILE."""
    patterns: list[tuple[str, re.Pattern[str], str]] = []
    name = os.environ.get("EII_FORBIDDEN_PATTERNS_FILE", "")
    extra = Path(name) if name else None
    if extra is not None and extra.is_file():
        for number, line in enumerate(
            extra.read_text(encoding="utf-8").splitlines(), 1
        ):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(
                (
                    f"extra-{number}",
                    re.compile(line, re.IGNORECASE),
                    "extra forbidden pattern",
                )
            )
    return patterns


def check_required(failures: list[str]) -> None:
    for name in REQUIRED_FILES:
        if not (ROOT / name).is_file():
            failures.append(f"FAIL required-file: {name}: missing")
    decisions = ROOT / "docs" / "decisions"
    if not decisions.is_dir() or not any(decisions.glob("[0-9][0-9][0-9][0-9]-*.md")):
        failures.append("FAIL required-file: docs/decisions: no decision record found")


def check_agent_files(failures: list[str]) -> None:
    agents, claude = ROOT / "AGENTS.md", ROOT / "CLAUDE.md"
    if (
        agents.is_file()
        and claude.is_file()
        and agents.read_bytes() != claude.read_bytes()
    ):
        failures.append("FAIL agent-files: AGENTS.md and CLAUDE.md differ")


def check_links(path: Path, lines: list[str], failures: list[str]) -> None:
    rel = path.relative_to(ROOT)
    in_fence = False
    for number, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in LINK_RE.findall(re.sub(r"`[^`]*`", "", line)):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                failures.append(
                    f"FAIL link: {rel}:{number}: points outside the repository: {target}"
                )
                continue
            if not resolved.exists():
                failures.append(
                    f"FAIL link: {rel}:{number}: target does not exist: {target}"
                )


def check_header(path: Path, text: str, failures: list[str]) -> None:
    rel = path.relative_to(ROOT).as_posix()
    if not NUMBERED_DOC_RE.match(rel):
        return
    head = "\n".join(text.splitlines()[:25])
    if not text.startswith("# "):
        failures.append(
            f"FAIL header: {rel}:1: document must start with a level-one title"
        )
    for row in HEADER_ROWS:
        if row not in head:
            failures.append(
                f"FAIL header: {rel}: header block is missing the row '{row}'"
            )


def check_forbidden(
    path: Path,
    lines: list[str],
    patterns: list[tuple[str, re.Pattern[str], str]],
    failures: list[str],
) -> None:
    rel = path.relative_to(ROOT)
    if rel.as_posix() == "scripts/check_docs.py":
        return
    for number, line in enumerate(lines, 1):
        for name, pattern, why in patterns:
            for match in pattern.finditer(line):
                token = match.group(0)
                if name == "email" and token in EMAIL_ALLOW:
                    continue
                if name == "secret":
                    shown = token[:6] + "..."
                elif name.startswith("extra-"):
                    shown = "(matched text not shown)"
                else:
                    shown = token
                failures.append(f"FAIL {name}: {rel}:{number}: {why}: {shown}")


def check_requirement_ids(markdown: dict[Path, list[str]], failures: list[str]) -> None:
    defined: dict[str, str] = {}
    for path, lines in markdown.items():
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(lines, 1):
            match = DEF_RE.match(line)
            if not match:
                continue
            req = match.group(1)
            if req in defined:
                failures.append(
                    f"FAIL requirement-id: {rel}:{number}: {req} is already defined at {defined[req]}"
                )
            else:
                defined[req] = f"{rel}:{number}"
    for path, lines in markdown.items():
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(lines, 1):
            for req in ID_RE.findall(line):
                if req not in defined:
                    failures.append(
                        f"FAIL requirement-id: {rel}:{number}: {req} is referenced but defined nowhere"
                    )


def main() -> int:
    failures: list[str] = []
    patterns = FORBIDDEN + load_extra_patterns()
    check_required(failures)
    check_agent_files(failures)
    markdown: dict[Path, list[str]] = {}
    files = iter_text_files()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"FAIL encoding: {path.relative_to(ROOT)}: not valid UTF-8")
            continue
        lines = text.splitlines()
        check_forbidden(path, lines, patterns, failures)
        if path.suffix.lower() == ".md":
            markdown[path] = lines
            check_links(path, lines, failures)
            check_header(path, text, failures)
    check_requirement_ids(markdown, failures)
    for failure in failures:
        print(failure)
    print(
        f"checked {len(files)} text files, {len(markdown)} Markdown files: "
        f"{'OK' if not failures else str(len(failures)) + ' failure(s)'}"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
