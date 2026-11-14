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
   (a bare run of exactly 8 or exactly 11 digits). A hit of an extra pattern
   passes only where a place-scoped exception allows it (see below).
7. The place-exception configuration ``scripts/check_docs_place_exceptions.toml``
   is a regular UTF-8 TOML file of the closed schema below; when it is missing
   or malformed the check fails and no exception applies.
8. Listed name: whenever the configuration lists a digest, no file git lists
   (of any suffix, read with replacement characters when it is not UTF-8, and
   once more without zero bytes), no line outside the allowed places, no listed
   path and no symbolic link's target holds a listed name: a run inside one word
   (in any letter case, up to 64 bytes), or a run of two to four name parts
   joined by one space, by nothing or as written, also cut across two lines.
   Each line is also read with HTML references and script escapes decoded,
   look-alike Cyrillic and Greek letters mapped, and invisible characters
   dropped. This check runs with or without the private list.
9. Paths: every listed name must be valid UTF-8 (``path-encoding``).

Which files are scanned: inside a git checkout, the files and symbolic links git
tracks plus the untracked ones it does not ignore; elsewhere, every file and
symbolic link under the root except build and cache folders and Zone.Identifier
files. A symbolic link is read as its link text only; its referent is never
opened; the built-in patterns, check 8 and the extra patterns read that text. A
file or link that cannot be read fails with a fixed line, and an unexpected
error ends in one fixed ``internal`` line and exit code 2; nothing is written to
standard error.

Extra forbidden patterns: if the environment variable
``EII_FORBIDDEN_PATTERNS_FILE`` is set, the file it names must be readable
(else one ``extra-patterns`` FAIL, without the path); each non-empty line of it
that does not start with ``#`` is a regular expression that is also forbidden in
every UTF-8 file of any suffix, in every listed path and in every link target.
A line that is not a valid regular expression fails with one fixed
``extra-patterns`` line; no error text, pattern or path is ever printed.
The built-in patterns skip ``scripts/check_docs.py``; the extra patterns and
check 8 read it.

Place-scoped exceptions (TST-263, task S1-T14): the configuration holds at most
one ``[[exception]]`` entry with exactly ``sha256``, ``reason`` and
``source_ids``, never a name. A hit of an extra pattern passes only on a line of
one of two places, and only when the SHA-256 of its matched text (case-folded,
UTF-8) is listed or the hit lies inside the listed name as written there. The
places are a source row of document 04 (a body row, with as many cells as its
header, of a ``source_id`` table inside its section "2. Source registry", whose
first-cell ids are all listed by the entry; the heading must be the one line of
the file that carries that text in any spelling) and the map attribution line
of ``web/src/stage/attribution.ts`` (the one top-level declaration of
``MAP_ATTRIBUTION`` with one string literal). A built-in pattern is never
excepted. Neither the matched text nor its digest is ever printed: a FAIL line
of a file whose path holds a listed name or an extra-pattern hit shows
``(path not shown)``, and a built-in or link FAIL line on a line that a listed
name or an extra pattern hits shows ``(matched text not shown)``.

Only the Python standard library is used.
"""

from __future__ import annotations

import hashlib
import html
import io
import os
import re
import subprocess
import sys
import tomllib
import unicodedata
import warnings
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
    """Files git tracks plus untracked files it does not ignore; None outside a checkout.

    Names are decoded as the file system does, so a name that is not UTF-8 still
    names its file (and is refused by check ``path-encoding``).
    """
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
    return [ROOT / os.fsdecode(name) for name in done.stdout.split(b"\0") if name]


# Place-scoped exceptions (TST-263). The configuration lists digests, never names.
PLACE_CONFIG = "scripts/check_docs_place_exceptions.toml"
PLACE_DOC04 = "docs/04_PUBLIC_DATA_PACK.md"
PLACE_ATTRIBUTION = "web/src/stage/attribution.ts"
PLACE_KEYS = {"sha256", "reason", "source_ids"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SOURCE_ID = r"[a-z][a-z0-9_]*\*?"
SOURCE_ID_RE = re.compile(SOURCE_ID)
FIRST_CELL_RE = re.compile(rf" *(`{SOURCE_ID}`(?:, `{SOURCE_ID}`)*) *")
DELIMITER_RE = re.compile(r"\|(?: *:?-+:? *\|)+")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
SECTION_2 = "## 2. Source registry"
# The heading text in every spelling: tags, entities, marks and punctuation dropped.
SECTION_2_KEY = "2sourceregistry"
SECTION_END_RE = re.compile(r"^ {0,3}#{1,2}(?:[ \t]|$)")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
TAG_RE = re.compile(r"<[^>]*>")
# HTML that can hide lines across blank lines: comments, processing instructions,
# declarations, CDATA, and the blocks that end only at their closing tag.
HTML_OPENER_RE = re.compile(
    r"<(?:[!?]|(?:pre|script|style|textarea)(?![A-Za-z0-9-]))", re.IGNORECASE
)
# Characters at which str.splitlines() splits although git and GitHub do not.
LINE_BREAK_TRAP_RE = re.compile("[\x0b\x0c\x1c-\x1e\x85\u2028\u2029]|\r(?!\n)")
ATTRIBUTION_RE = re.compile(
    r"export const MAP_ATTRIBUTION(?:: string)? = "
    r"(?:`[^`\\$]*`|\"[^\"\\]*\"|'[^'\\]*');"
)
NAME_PART_RE = re.compile(r"[^\W_]+")
# Invisible characters dropped before names are matched (zero-width, soft hyphen,
# joiners, direction marks, variation selectors, byte-order mark).
ZERO_WIDTH_RE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f"
    "\u202a-\u202e\u2060-\u206f\ufe00-\ufe0f\ufeff]"
)
JS_ESCAPE_RE = re.compile(
    r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})"
)
# Cyrillic and Greek letters that look like Latin ones.
CONFUSABLES = str.maketrans(
    dict(
        zip(
            "аеорсхуіјѕԁӏһԛԝкмнтвАВЕКМНОРСТХУІЈЅαονικυχΑΒΕΖΗΙΚΜΝΟΡΤΥΧ",
            "aeopcxyijsdlhqwkmhtbabekmhopctxyijsaovikuxabezhikmnoptyx",
            strict=True,
        )
    )
)
MAX_NAME_PARTS = 4
MAX_NAME_LENGTH = 64
HIDDEN_PATH = "(path not shown)"
NOT_SHOWN = "(matched text not shown)"

# Paths whose FAIL lines must not show the path (they hold a listed name).
HIDDEN_PATHS: set[str] = set()


def show(rel: str) -> str:
    return HIDDEN_PATH if rel in HIDDEN_PATHS else rel


def name_digest(text: str) -> str:
    """Lowercase hexadecimal SHA-256 of the case-folded text, encoded as UTF-8."""
    return hashlib.sha256(
        text.casefold().encode("utf-8", "surrogateescape")
    ).hexdigest()


def listed_files() -> list[Path]:
    """Every regular file and symbolic link of the scan: git's list, else a walk."""
    listed = git_listed_files()
    if listed is None:
        candidates: list[Path] = []
        for folder, dirs, names in os.walk(ROOT):
            base = Path(folder)
            links = [name for name in dirs if (base / name).is_symlink()]
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d not in links]
            candidates.extend(
                base / name
                for name in names + links
                if name not in SKIP_DIRS and not name.endswith("Zone.Identifier")
            )
    else:
        # A tracked file is checked whatever its name: only the walk skips the
        # Zone.Identifier files that git ignores anyway.
        candidates = listed
    return [
        path for path in sorted(set(candidates)) if path.is_symlink() or path.is_file()
    ]


def read_regular(path: Path) -> bytes | None:
    """The bytes of a regular file, never through a symbolic link; None when it
    cannot be read. The error is never shown: its text can hold a private path."""
    if path.is_symlink():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES


def iter_text_files() -> list[Path]:
    return [
        path
        for path in listed_files()
        if not path.is_symlink() and path.is_file() and is_text_file(path)
    ]


def load_place_exceptions(failures: list[str]) -> dict[str, frozenset[str]]:
    """Listed digests and their source ids; on the first defect, one FAIL and none."""

    def fail(detail: str) -> dict[str, frozenset[str]]:
        failures.append(f"FAIL place-exception-config: {PLACE_CONFIG}: {detail}")
        return {}

    path = ROOT / PLACE_CONFIG
    if path.is_symlink() or not path.is_file():
        return fail("missing or not a regular file")
    raw = read_regular(path)
    if raw is None:
        return fail("cannot be read")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return fail("not valid UTF-8")
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, RecursionError, ValueError):
        return fail("not valid TOML")
    if set(data) - {"exception"}:
        return fail("unknown top-level key")
    entries = data.get("exception", [])
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) for entry in entries
    ):
        return fail("exception is not a list of tables")
    listed: dict[str, frozenset[str]] = {}
    for number, entry in enumerate(entries, 1):
        if set(entry) != PLACE_KEYS:
            return fail(
                f"entry {number}: keys are not exactly sha256, reason and source_ids"
            )
        sha = entry["sha256"]
        if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha):
            return fail(
                f"entry {number}: sha256 is not 64 lowercase hexadecimal digits"
            )
        if sha == EMPTY_DIGEST:
            return fail(f"entry {number}: sha256 is the digest of empty text")
        reason = entry["reason"]
        if not isinstance(reason, str) or not reason.strip():
            return fail(f"entry {number}: reason is empty")
        ids = entry["source_ids"]
        if (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(i, str) and SOURCE_ID_RE.fullmatch(i) for i in ids)
            or len(set(ids)) != len(ids)
        ):
            return fail(
                f"entry {number}: source_ids is not a non-empty list of distinct source ids"
            )
        listed[sha] = frozenset(ids)
    # At most one entry: nobody can review which name a digest stands for, so a
    # second name needs a new owner note and a reviewed change of this limit.
    if len(entries) > 1:
        return fail("more than one entry")
    return listed


def indent_width(line: str) -> int:
    """Columns of leading white space, a tab reaching the next multiple of four."""
    width = 0
    for char in line:
        if char == " ":
            width += 1
        elif char == "\t":
            width += 4 - width % 4
        else:
            break
    return width


def blank(line: str) -> bool:
    """CommonMark's blank line: spaces and tabs only. Python's strip() also
    removes a no-break space or a unit separator, which CommonMark reads as text."""
    return not line.strip(" \t")


def fenced_lines(lines: list[str]) -> list[bool] | None:
    """CommonMark fences: which lines open, sit in or close a fenced block.

    None for a form this reader does not follow: inside a fence whose opener is
    indented, a non-blank line indented less than the opener. Such an opener may
    sit in a list item, and that line then ends the list item and the fence with
    it (it may even open the next fence), where a top-level fence goes on."""
    fenced: list[bool] = []
    fence: tuple[str, int, int] | None = None
    for line in lines:
        if fence is None:
            match = FENCE_OPEN_RE.match(line)
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence = (match.group(1)[0], len(match.group(1)), indent_width(line))
                fenced.append(True)
            else:
                fenced.append(False)
            continue
        if fence[2] and not blank(line) and indent_width(line) < fence[2]:
            return None
        fenced.append(True)
        close = FENCE_CLOSE_RE.match(line)
        if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= fence[1]:
            fence = None
    return fenced


def heading_key(line: str) -> str:
    """The text of a line in every spelling: no tags, entities, marks or punctuation."""
    plain = html.unescape(TAG_RE.sub("", line))
    plain = unicodedata.normalize("NFKC", plain).translate(CONFUSABLES)
    return re.sub(r"[^0-9a-z]", "", ZERO_WIDTH_RE.sub("", plain).casefold())


def table_cells(line: str) -> list[str] | None:
    """The cells of a pipe-delimited row, or None when the line is not one."""
    parts = CELL_SPLIT_RE.split(line.strip(" \t"))
    if len(parts) < 3 or parts[0].strip(" \t") or parts[-1].strip(" \t"):
        return None
    return parts[1:-1]


def doc04_source_rows(text: str, lines: list[str]) -> dict[int, frozenset[str]]:
    """Line number -> first-cell source ids of each source row of section 2."""
    if LINE_BREAK_TRAP_RE.search(text):
        return {}
    # Exactly one line of the whole file, fenced or not, carries the heading text
    # in any spelling, and it is the plain heading after a blank line.
    heads = [i for i, line in enumerate(lines) if heading_key(line) == SECTION_2_KEY]
    if len(heads) != 1:
        return {}
    start = heads[0]
    fenced = fenced_lines(lines)
    if (
        fenced is None
        or fenced[start]
        or lines[start].rstrip(" \t") != SECTION_2
        or (start and not blank(lines[start - 1]))
    ):
        return {}
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if not fenced[index] and SECTION_END_RE.match(lines[index]):
            end = index
            break
    # Any line that starts HTML before the end of section 2: an HTML block that
    # ends at a blank line can hold a fence-looking line the reader would follow.
    if any(
        HTML_OPENER_RE.search(line) or re.match(r"^ {0,3}<", line)
        for line in lines[:end]
    ):
        return {}
    for index in range(start + 1, end):
        bare = lines[index].strip()
        if fenced[index] or (
            bare
            and (set(bare) == {"="} or set(bare) == {"-"})
            and not blank(lines[index - 1])
        ):
            return {}
    rows: dict[int, frozenset[str]] = {}
    index = start + 1
    while index < end:
        header = table_cells(lines[index]) if lines[index].startswith("|") else None
        delimiter = (
            table_cells(lines[index + 1])
            if index + 1 < end
            and DELIMITER_RE.fullmatch(lines[index + 1].rstrip(" \t"))
            else None
        )
        if (
            header is not None
            and header[0].strip() == "source_id"
            and blank(lines[index - 1])
            and delimiter is not None
            and len(delimiter) == len(header)
        ):
            body = index + 2
            while body < end and lines[body].startswith("|"):
                row = table_cells(lines[body])
                match = (
                    FIRST_CELL_RE.fullmatch(row[0])
                    if row is not None and len(row) == len(header)
                    else None
                )
                if match:
                    rows[body + 1] = frozenset(
                        re.findall(rf"`({SOURCE_ID})`", match.group(1))
                    )
                body += 1
            index = body
            continue
        index += 1
    return rows


def code_line_starts(text: str) -> list[bool] | None:
    """For each line of TypeScript text: True when it starts outside comments,
    strings, templates and brackets. None for a form this reader does not follow
    (a hashbang line, a slash outside comments, a template substitution, an
    unclosed construct)."""
    if text.startswith("#!"):
        return None
    starts = [True]
    state, quote, depth = "code", "", 0
    index, size = 0, len(text)
    while index < size:
        char = text[index]
        after = text[index + 1] if index + 1 < size else ""
        if char == "\n":
            if state == "quote":
                return None
            if state == "line":
                state = "code"
            starts.append(state == "code" and depth == 0)
        elif state == "code":
            if char == "/" and after in "/*" and after:
                state = "line" if after == "/" else "block"
                index += 1
            elif char == "/":
                return None
            elif char in "'\"":
                state, quote = "quote", char
            elif char == "`":
                state = "template"
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth < 0:
                    return None
        elif state == "block":
            if char == "*" and after == "/":
                state = "code"
                index += 1
        elif state in ("quote", "template"):
            if char == "\\":
                if after in "\r\n":
                    return None
                index += 1
            elif state == "template" and char == "$" and after == "{":
                return None
            elif char == (quote if state == "quote" else "`"):
                state = "code"
        index += 1
    if state not in ("code", "line") or depth:
        return None
    return starts


def attribution_line(text: str, lines: list[str]) -> int | None:
    """The one declaration line of the map's credits, at the top level, or None."""
    if LINE_BREAK_TRAP_RE.search(text):
        return None
    hits = [
        number
        for number, line in enumerate(lines, 1)
        if ATTRIBUTION_RE.fullmatch(line.rstrip())
    ]
    if len(hits) != 1:
        return None
    starts = code_line_starts(text)
    if starts is None or not starts[hits[0] - 1]:
        return None
    return hits[0]


def allowed_lines(
    rel: str, text: str, lines: list[str], listed: dict[str, frozenset[str]]
) -> dict[int, frozenset[str]]:
    """Line number -> digests allowed on that line (both places of TST-263)."""
    if not listed:
        return {}
    if text.startswith("﻿"):
        text = text[1:]
        lines = text.splitlines()
    if rel == PLACE_DOC04:
        allowed: dict[int, frozenset[str]] = {}
        for number, ids in doc04_source_rows(text, lines).items():
            digests = frozenset(d for d, own in listed.items() if ids <= own)
            if digests:
                allowed[number] = digests
        return allowed
    if rel == PLACE_ATTRIBUTION:
        declaration = attribution_line(text, lines)
        return {} if declaration is None else {declaration: frozenset(listed)}
    return {}


def js_unescape(text: str) -> str:
    def one(match: re.Match[str]) -> str:
        value = int(match.group(1) or match.group(2) or match.group(3), 16)
        if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
            return match.group(0)
        return chr(value)

    return JS_ESCAPE_RE.sub(one, text)


def variants(text: str) -> list[str]:
    """The text as written, with HTML references and script escapes decoded, and
    with look-alike letters mapped; invisible characters dropped from each."""
    forms = {text, html.unescape(text), js_unescape(text)}
    forms |= {
        unicodedata.normalize("NFKC", form).translate(CONFUSABLES) for form in forms
    }
    return sorted({ZERO_WIDTH_RE.sub("", form) for form in forms})


class NameFinder:
    """Finds a listed name in a text (check 8)."""

    def __init__(self, digests: frozenset[str]) -> None:
        self.digests = digests
        self.raw = {bytes.fromhex(value): value for value in digests}
        self.words: dict[str, list[tuple[int, int, str]]] = {}

    def spans(self, text: str) -> list[tuple[int, int]]:
        """Name parts: runs of letters or digits, split at case and digit changes."""
        spans: list[tuple[int, int]] = []
        for token in NAME_PART_RE.finditer(text):
            word, base, start = token.group(0), token.start(), 0
            if word.isdigit() or (
                word.isalpha()
                and (word.isupper() or not any(ch.isupper() for ch in word[1:]))
            ):
                # One part: no case change after the first letter, no digit change.
                spans.append((base, base + len(word)))
                continue
            for i in range(1, len(word)):
                before, after = word[i - 1], word[i]
                if (
                    before.isdigit() != after.isdigit()
                    or (before.islower() and after.isupper())
                    or (
                        before.isupper()
                        and after.isupper()
                        and i + 1 < len(word)
                        and word[i + 1].islower()
                    )
                ):
                    spans.append((base + start, base + i))
                    start = i
            spans.append((base + start, base + len(word)))
        return spans

    def word_hits(self, word: str) -> list[tuple[int, int, str]]:
        """Folded offsets of every listed run inside one word, in any letter case."""
        found = self.words.get(word)
        if found is None:
            folded = word.casefold().encode("utf-8", "surrogateescape")
            found = []
            size = len(folded)
            for start in range(size):
                for end in range(start + 1, min(start + MAX_NAME_LENGTH, size) + 1):
                    value = self.raw.get(hashlib.sha256(folded[start:end]).digest())
                    if value is not None:
                        found.append((start, end, value))
            self.words[word] = found
        return found

    def hits(self, text: str) -> list[tuple[int, int, str]]:
        """(start, end, digest) of each listed name: a run inside one word, or a
        run of two to six parts joined by one space, by nothing or as written."""
        out: list[tuple[int, int, str]] = []
        for token in NAME_PART_RE.finditer(text):
            word = token.group(0)
            found = self.word_hits(word)
            if found:
                # Byte offset of the folded word -> character of the word.
                where = [
                    index
                    for index, char in enumerate(word)
                    for _ in char.casefold().encode("utf-8", "surrogateescape")
                ]
                for start, end, value in found:
                    out.append(
                        (
                            token.start() + where[start],
                            token.start() + where[end - 1] + 1,
                            value,
                        )
                    )
        return out + self.runs(text)

    def runs(self, text: str, cut: int = -1) -> list[tuple[int, int, str]]:
        """Runs of two to MAX_NAME_PARTS parts, at most MAX_NAME_LENGTH long: joined
        by one space, and, across words, also by nothing and as written (inside one
        word those forms are runs of ``word_hits``). With ``cut``, only the runs
        that hold text on both sides of that position."""
        out: list[tuple[int, int, str]] = []
        spans = self.spans(text)
        folded = [
            text[a:b].casefold().encode("utf-8", "surrogateescape") for a, b in spans
        ]
        count = len(spans)
        raw, sha = self.raw, hashlib.sha256
        for first in range(count):
            begin = spans[first][0]
            if 0 <= cut <= begin:
                break
            crosses, size = False, len(folded[first])
            for last in range(first + 1, min(first + MAX_NAME_PARTS, count)):
                crosses = crosses or spans[last][0] > spans[last - 1][1]
                finish = spans[last][1]
                size += len(folded[last])
                if size > MAX_NAME_LENGTH:
                    break
                if cut >= 0 and finish <= cut + 1:
                    continue
                joined = folded[first : last + 1]
                keys = {b" ".join(joined)}
                if crosses:
                    written = text[begin:finish].casefold()
                    keys |= {
                        b"".join(joined),
                        written.encode("utf-8", "surrogateescape"),
                    }
                for key in keys:
                    value = raw.get(sha(key).digest())
                    if value is not None:
                        out.append((begin, finish, value))
        return out

    def find(self, text: str) -> bool:
        return any(self.hits(form) for form in variants(text))


def listed_hits(lines: list[str], finder: NameFinder) -> dict[int, set[str]]:
    """Line number -> digests of the listed names on that line, in any form; a
    name cut across two lines counts on the second."""
    found: dict[int, set[str]] = {}
    for number, line in enumerate(lines, 1):
        values = {hit[2] for form in variants(line) for hit in finder.hits(form)}
        if values:
            found[number] = values
    for number in range(1, len(lines)):
        tail = ZERO_WIDTH_RE.sub("", lines[number - 1])[-MAX_NAME_LENGTH:]
        head = ZERO_WIDTH_RE.sub("", lines[number])[:MAX_NAME_LENGTH]
        for hit in finder.runs(tail + "\n" + head, cut=len(tail)):
            found.setdefault(number + 1, set()).add(hit[2])
    return found


def check_listed_bytes(
    rel: str, data: bytes, finder: NameFinder, failures: list[str]
) -> None:
    """Check 8 on a file that is not UTF-8: read with replacement characters, and
    once more without zero bytes (UTF-16 text)."""
    texts = [data.decode("utf-8", "replace")]
    if b"\x00" in data:
        texts.append(data.replace(b"\x00", b"").decode("utf-8", "replace"))
    numbers: set[int] = set()
    for text in texts:
        numbers.update(listed_hits(text.splitlines(), finder))
    for number in sorted(numbers):
        failures.append(
            f"FAIL listed-name: {show(rel)}:{number}: a listed name outside its "
            f"places: {NOT_SHOWN}"
        )


def load_extra_patterns(failures: list[str]) -> list[tuple[str, re.Pattern[str], str]]:
    """Extra forbidden patterns from the file named by EII_FORBIDDEN_PATTERNS_FILE."""
    patterns: list[tuple[str, re.Pattern[str], str]] = []
    name = os.environ.get("EII_FORBIDDEN_PATTERNS_FILE", "")
    if not name:
        return patterns
    try:
        # utf-8-sig: a byte-order mark must not become part of the first pattern.
        text = Path(name).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        # The path is never printed: it can be a private path.
        failures.append(
            "FAIL extra-patterns: EII_FORBIDDEN_PATTERNS_FILE names no readable file"
        )
        return patterns
    invalid = False
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            # A warning would print this file's path and a position in the pattern.
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                compiled = re.compile(line, re.IGNORECASE)
        except (
            re.error,
            OverflowError,
            RecursionError,
            ValueError,
            MemoryError,
            Warning,
        ):
            # Fail closed with a fixed line: the error text can hold the pattern.
            invalid = True
            continue
        patterns.append((f"extra-{number}", compiled, "extra forbidden pattern"))
    if invalid:
        failures.append(
            "FAIL extra-patterns: a line of EII_FORBIDDEN_PATTERNS_FILE is not a "
            "valid regular expression"
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
    if not (agents.is_file() and claude.is_file()):
        return
    first, second = read_regular(agents), read_regular(claude)
    if first is None or second is None:
        failures.append("FAIL agent-files: AGENTS.md or CLAUDE.md cannot be read")
    elif first != second:
        failures.append("FAIL agent-files: AGENTS.md and CLAUDE.md differ")


def check_links(
    path: Path, lines: list[str], sensitive: set[int], failures: list[str]
) -> None:
    rel = show(path.relative_to(ROOT).as_posix())
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
            shown = NOT_SHOWN if number in sensitive else target
            unresolved = (
                f"FAIL link: {rel}:{number}: target cannot be resolved: {NOT_SHOWN}"
            )
            try:
                resolved = (path.parent / file_part).resolve()
            except (OSError, ValueError):
                failures.append(unresolved)
                continue
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                failures.append(
                    f"FAIL link: {rel}:{number}: points outside the repository: {shown}"
                )
                continue
            try:
                exists = resolved.exists()
            except (OSError, ValueError):
                failures.append(unresolved)
                continue
            if not exists:
                failures.append(
                    f"FAIL link: {rel}:{number}: target does not exist: {shown}"
                )


def check_header(path: Path, text: str, failures: list[str]) -> None:
    rel = path.relative_to(ROOT).as_posix()
    if not NUMBERED_DOC_RE.match(rel):
        return
    rel = show(rel)
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
    allowed: dict[int, frozenset[str]],
    finder: NameFinder,
    sensitive: set[int],
    failures: list[str],
) -> None:
    """Forbidden patterns; ``allowed`` maps a line to the digests excepted there.

    An extra-pattern hit on an allowed line passes when its matched text, or the
    listed name it lies within, has an allowed digest. On a line in ``sensitive``
    (an extra pattern or a listed name hits it) no matched text is printed.
    """
    rel = path.relative_to(ROOT).as_posix()
    own = rel == "scripts/check_docs.py"
    shown_rel = show(rel)
    for number, line in enumerate(lines, 1):
        excepted = allowed.get(number, frozenset())
        names: list[tuple[int, int, str]] | None = None
        for name, pattern, why in patterns:
            extra = name.startswith("extra-")
            # This file spells the built-in patterns; the extra patterns still read it.
            if own and not extra:
                continue
            for match in pattern.finditer(line):
                token = match.group(0)
                if name == "email" and token in EMAIL_ALLOW:
                    continue
                if extra and excepted:
                    if name_digest(token) in excepted:
                        continue
                    if names is None:
                        # A listed name as written: never another spelling of it.
                        names = [
                            hit
                            for hit in finder.hits(line)
                            if name_digest(line[hit[0] : hit[1]]) in excepted
                        ]
                    if any(
                        start <= match.start() and match.end() <= end
                        for start, end, _ in names
                    ):
                        continue
                if name == "secret" or extra or number in sensitive:
                    shown = NOT_SHOWN
                else:
                    shown = token
                failures.append(f"FAIL {name}: {shown_rel}:{number}: {why}: {shown}")


def check_requirement_ids(markdown: dict[Path, list[str]], failures: list[str]) -> None:
    defined: dict[str, str] = {}
    for path, lines in markdown.items():
        rel = show(path.relative_to(ROOT).as_posix())
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
        rel = show(path.relative_to(ROOT).as_posix())
        for number, line in enumerate(lines, 1):
            for req in ID_RE.findall(line):
                if req not in defined:
                    failures.append(
                        f"FAIL requirement-id: {rel}:{number}: {req} is referenced but defined nowhere"
                    )


def path_is_utf8(rel: str) -> bool:
    try:
        rel.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def check_names_and_links(
    every: list[Path],
    extra_patterns: list[tuple[str, re.Pattern[str], str]],
    finder: NameFinder | None,
    failures: list[str],
) -> None:
    """Paths and link targets: encoding, listed names and extra patterns."""
    HIDDEN_PATHS.clear()
    for path in every:
        rel = path.relative_to(ROOT).as_posix()
        if not path_is_utf8(rel):
            HIDDEN_PATHS.add(rel)
            failures.append(
                f"FAIL path-encoding: {HIDDEN_PATH}: a file or folder name is not "
                "valid UTF-8"
            )
        if finder is not None and finder.find(rel):
            HIDDEN_PATHS.add(rel)
            failures.append(
                f"FAIL listed-name: {HIDDEN_PATH}: a listed name in a file or "
                f"folder name: {NOT_SHOWN}"
            )
        for name, pattern, why in extra_patterns:
            if pattern.search(rel):
                HIDDEN_PATHS.add(rel)
                failures.append(
                    f"FAIL {name}: {HIDDEN_PATH}: {why} in a file or folder name: "
                    f"{NOT_SHOWN}"
                )
    for path in every:
        if not path.is_symlink():
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            target = os.readlink(path)
        except OSError:
            failures.append(f"FAIL read: {show(rel)}: link cannot be read")
            continue
        if finder is not None and finder.find(target):
            failures.append(
                f"FAIL listed-name: {show(rel)}: a listed name in a link target: "
                f"{NOT_SHOWN}"
            )
        for name, pattern, why in FORBIDDEN:
            if any(
                not (name == "email" and match.group(0) in EMAIL_ALLOW)
                for match in pattern.finditer(target)
            ):
                failures.append(
                    f"FAIL {name}: {show(rel)}: {why} in a link target: {NOT_SHOWN}"
                )
        for name, pattern, why in extra_patterns:
            if pattern.search(target):
                failures.append(
                    f"FAIL {name}: {show(rel)}: {why} in a link target: {NOT_SHOWN}"
                )


def main() -> int:
    failures: list[str] = []
    extra_patterns = load_extra_patterns(failures)
    patterns = FORBIDDEN + extra_patterns
    check_required(failures)
    check_agent_files(failures)
    listed = load_place_exceptions(failures)
    finder = NameFinder(frozenset(listed))
    every = listed_files()
    check_names_and_links(every, extra_patterns, finder if listed else None, failures)
    markdown: dict[Path, list[str]] = {}
    # A symbolic link is scanned as its link text only (above); its referent is
    # never opened: it can lie outside the repository or in an ignored folder. A
    # listed regular target is scanned through its own entry.
    regular = [path for path in every if not path.is_symlink() and path.is_file()]
    files = [path for path in regular if is_text_file(path)]
    for path in regular:
        text_file = is_text_file(path)
        rel = path.relative_to(ROOT).as_posix()
        data = read_regular(path)
        if data is None:
            failures.append(f"FAIL read: {show(rel)}: cannot be read")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            if text_file:
                failures.append(f"FAIL encoding: {show(rel)}: not valid UTF-8")
            if listed:
                check_listed_bytes(rel, data, finder, failures)
            continue
        lines = text.splitlines()
        allowed = allowed_lines(rel, text, lines, listed)
        found = listed_hits(lines, finder) if listed else {}
        for number, values in sorted(found.items()):
            if values - allowed.get(number, frozenset()):
                failures.append(
                    f"FAIL listed-name: {show(rel)}:{number}: a listed name outside "
                    f"its places: {NOT_SHOWN}"
                )
        sensitive = set(found) | {
            number
            for number, line in enumerate(lines, 1)
            if any(pattern.search(line) for _, pattern, _ in extra_patterns)
        }
        # Every UTF-8 file meets the extra patterns; text files also the built-in ones.
        check_forbidden(
            path,
            lines,
            patterns if text_file else extra_patterns,
            allowed,
            finder,
            sensitive,
            failures,
        )
        if text_file and path.suffix.lower() == ".md":
            markdown[path] = lines
            check_links(path, lines, sensitive, failures)
            check_header(path, text, failures)
    check_requirement_ids(markdown, failures)
    for failure in failures:
        print(failure)
    print(
        f"checked {len(files)} text files, {len(markdown)} Markdown files: "
        f"{'OK' if not failures else str(len(failures)) + ' failure(s)'}"
    )
    return 0 if not failures else 1


INTERNAL_FAIL = (
    "FAIL internal: the check stopped on an unexpected error (details not shown)"
)


def run_guarded() -> int:
    """main() with nothing on standard error: a character the output cannot
    encode is escaped, and an unexpected error ends in one fixed line and exit 2
    (its text and traceback can hold a private path or pattern)."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")
    try:
        return main()
    except Exception:
        print(INTERNAL_FAIL)
        return 2


if __name__ == "__main__":
    sys.exit(run_guarded())
