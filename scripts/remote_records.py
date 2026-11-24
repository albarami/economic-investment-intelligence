"""Closed checks of the S3-T20 records. They read text; nothing is run or fetched.

Each function returns its problems as a sorted list of strings, empty when the
record holds. None of them proves that evidence is true: the phone captures,
the boot run and the gate approval are the lead's records.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from pack_anchors import check_cite

SCENES = ("first_map", "story")
LANGUAGES = ("en", "ar")
THEMES = ("light", "dark")
# Decision 0049 item 2: the eight named sizes, each phone in both rotations.
SIZES = (
    (360, 640),
    (640, 360),
    (390, 844),
    (844, 390),
    (768, 1024),
    (1366, 768),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),
    (3840, 2160),
)
CELL_KEYS = ("scene", "language", "theme", "width", "height")
ROW_KEYS = frozenset({*CELL_KEYS, "sha256"})
HEX64 = re.compile(r"[0-9a-f]{64}\Z")

TASK_HEADING = "### S3-T20 — "
BOX = re.compile(r"\[([ x])\] ")
BOXES = 12
GATE_HEADING = re.compile(r"#### (Slice S3 gate — .*APPROVED.*)\Z")
DEPENDENCY_LINE = "- S3-T20 dependency evidence: "

DOC13 = "docs/13_DEPLOYMENT_AND_OPERATIONS.md"
DOC17 = "docs/17_DEPLOYMENT_HARDENING.md"
NO_LOGIN_SECTION = "S3-T20 start on boot and the no-login choice"
NO_LOGIN_MARK = "**The owner's no-login choice and what it means.**"
REGISTER_ROWS = ("DHA-146", "DHA-147", "DHA-148", "DHA-149")
NO_LOGIN_CITES = "; ".join(
    (
        f'{DOC13} section "{NO_LOGIN_SECTION}"',
        f"{DOC17} DHA-133",
        *(f"{DOC17} {row}" for row in REGISTER_ROWS),
        'docs/decisions/0041-remote-mode-through-the-owners-own-host.md section "Decision" item 8',
    )
)

TEST_OR_CI_PARTS = frozenset({"tests", ".github"})
TEST_OR_CI_NAMES = frozenset(
    {".pre-commit-config.yaml", "run_tests.py", "package.json"}
)
CODE_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".js", ".mjs"})
HOST_SETTING = "EII_REMOTE_HOST"
SWITCH_SETTING = "EII_REMOTE_ALLOW_PAID_ASSISTANT"
REFUSAL_CASE_PREFIX = "test_s3_t20_"
# A comment line names the command; it does not run it.
COMMENT_STARTS = ("#", "//", "/*", "*")
INVOCATION = re.compile(r"""eii["']?,?\s*["']?remote-check""")
# A setting written in a mapping, a call or a shell, YAML or JSON line. In code
# only a quoted literal is a value: an unquoted word there is an expression.
QUOTED = r"""["']?\]?[ \t]*[=:,][ \t]*["']([^"'\n]*)["']"""
BARE = r"""["']?[ \t]*[=:][ \t]*([^\s"'`,;)}\]]+)"""
# A constant that holds a setting's name stands for it in a mapping or a call.
ALIAS = r"""(?<!\w)(\w+)[ \t]*=[ \t]*["']%s["']"""
NAME_SHAPE = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.([a-z][a-z0-9-]*)\Z")


def evidence_cells() -> list[tuple[str, str, str, int, int]]:
    """The closed phone-evidence matrix of box B9 as amended by decision 0049."""
    return [
        (scene, language, theme, width, height)
        for scene in SCENES
        for language in LANGUAGES
        for theme in THEMES
        for width, height in SIZES
    ]


def evidence_problems(rows: Iterable[Mapping[str, object]]) -> list[str]:
    """Every cell exactly once, each with the hash of its capture."""
    expected = set(evidence_cells())
    seen: set[tuple[object, ...]] = set()
    problems = []
    for row in rows:
        if set(row) != ROW_KEYS:
            problems.append("malformed row")
            continue
        cell = tuple(row[key] for key in CELL_KEYS)
        label = "/".join(map(str, cell))
        digest = row["sha256"]
        # A name is text and a size a whole number: True and 360.0 equal a
        # cell's value but are not one, and a list cannot be looked up at all.
        kinds = [type(value) for value in cell]
        if kinds != [str, str, str, int, int] or cell not in expected:
            problems.append("unknown cell: " + label)
            continue
        if cell in seen:
            problems.append("repeated cell: " + label)
        elif not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
            problems.append("capture hash invalid: " + label)
        seen.add(cell)
    problems.extend(
        "missing cell: " + "/".join(map(str, cell)) for cell in expected - seen
    )
    return sorted(problems)


def gate_approval_problems(tasks: str, progress: str) -> list[str]:
    """Box B12 is ticked only after a cited slice S3 gate approval record."""
    lines = tasks.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(TASK_HEADING)), None
    )
    criteria = next(
        (
            line
            for line in lines[(start or 0) + 1 :]
            if line.startswith(("- Acceptance criteria: ", "### "))
        ),
        "",
    )
    marks = BOX.findall(criteria)
    last = BOX.split(criteria)[-1]
    if start is None or len(marks) != BOXES or "dependency evidence" not in last:
        return ["S3-T20 acceptance boxes cannot be read"]
    if marks[-1] != "x":
        return []
    records = progress.splitlines()
    approvals = [
        (index, match.group(1))
        for index, line in enumerate(records)
        if (match := GATE_HEADING.match(line)) is not None
    ]
    if not approvals:
        return ["dependency box ticked without a slice S3 gate approval record"]
    cited = [
        index
        for index, line in enumerate(records)
        if line.startswith(DEPENDENCY_LINE)
        and any(heading in line and at < index for at, heading in approvals)
    ]
    if not cited:
        return ["dependency box ticked without citing the approval record after it"]
    return []


def no_login_problems(root: Path) -> list[str]:
    """Box B10: the choice and its meaning, and the register rows, are written."""
    problems = check_cite(root, NO_LOGIN_CITES)
    try:
        operations = (root / DOC13).read_text(encoding="utf-8")
        register = (root / DOC17).read_text(encoding="utf-8").splitlines()
    except OSError:
        return sorted([*problems, "documents cannot be read"])
    paragraph = next(
        (line for line in operations.splitlines() if line.startswith(NO_LOGIN_MARK)),
        "",
    )
    for phrase in ("decision 0041 item 8", "Anyone who has the address", "DHA-133"):
        if phrase not in paragraph:
            problems.append("no-login paragraph lacks: " + phrase)
    for row in REGISTER_ROWS:
        text = next((line for line in register if line.startswith(f"| {row} |")), "")
        for phrase in ("S3-T20", "decision 0041 item 8", "DHA-133", "not built now"):
            if text and phrase.lower() not in text.lower():
                problems.append(f"{row} lacks: {phrase}")
    return sorted(problems)


def is_test_or_ci(path: str) -> bool:
    """A file a test run or a hosted check reads as something to run."""
    parts = Path(path).parts
    name = parts[-1]
    return (
        bool(TEST_OR_CI_PARTS.intersection(parts))
        or name in TEST_OR_CI_NAMES
        or name.startswith(("test_", "ci_", "playwright"))
    )


def invocation_lines(text: str) -> list[int]:
    """Lines that write the launcher's remote-check form, in shell or list form."""
    return [
        number
        for number, line in enumerate(text.splitlines(), 1)
        if INVOCATION.search(line) is not None
        and not line.lstrip().startswith(COMMENT_STARTS)
    ]


def assigned_values(text: str, name: str, *, code: bool) -> list[str]:
    """Non-empty literal values a text gives one setting."""
    found = re.findall(r"(?<!\w)" + re.escape(name) + QUOTED, text)
    if not code:
        found += re.findall(r"(?<!\w)" + re.escape(name) + BARE, text)
    return [value for value in found if value]


def possible_real_host(value: str) -> bool:
    """A host name that could be a real one.

    A name under the reserved `.invalid` label, a single label and an address
    literal can never be the owner's host name; anything else of two or more
    labels could be.
    """
    core = value.lower().split("://", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0]
    match = NAME_SHAPE.fullmatch(core.rstrip("."))
    return match is not None and match.group(1) != "invalid"


def setting_values(text: str, name: str, *, code: bool) -> list[str]:
    """Values given to a setting by its name or, in code, by a constant holding it."""
    names = [name, *re.findall(ALIAS % re.escape(name), text)] if code else [name]
    return [
        value
        for each in dict.fromkeys(names)
        for value in assigned_values(text, each, code=code)
        if value != name
    ]


def _values(root: Path, path: str, name: str) -> list[str]:
    text = (root / path).read_text(encoding="utf-8")
    return setting_values(text, name, code=Path(path).suffix in CODE_SUFFIXES)


def invocation_problems(root: Path, paths: Iterable[str]) -> list[str]:
    """Box B7: no test or CI file writes the lead's remote-check form."""
    return sorted(
        f"{path}:{line}"
        for path in paths
        if is_test_or_ci(path)
        for line in invocation_lines((root / path).read_text(encoding="utf-8"))
    )


def host_problems(root: Path, paths: Iterable[str]) -> list[str]:
    """Box B1: the files that give the host setting a possible real name."""
    return sorted(
        path
        for path in paths
        if any(map(possible_real_host, _values(root, path, HOST_SETTING)))
    )


def switch_problems(root: Path, paths: Iterable[str]) -> list[str]:
    """Box B4: the paid switch is given a value nowhere but one refusal case.

    The one admitted site is a single mapping in one S3-T20 test file, where a
    start with the switch set is the planted input of a refusal.
    """
    sites = {
        path: len(_values(root, path, SWITCH_SETTING))
        for path in paths
        if Path(path).suffix != ".md"
    }
    sites = {path: count for path, count in sites.items() if count}
    admitted = [
        path
        for path, count in sites.items()
        if count == 1
        and "tests" in Path(path).parts
        and Path(path).name.startswith(REFUSAL_CASE_PREFIX)
    ]
    if len(sites) == len(admitted) <= 1:
        return []
    return sorted(f"{path}: {count}" for path, count in sites.items())
