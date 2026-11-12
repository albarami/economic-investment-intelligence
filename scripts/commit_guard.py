"""Commit guard (task S0-T06): refuse a commit that would hold a local secret value.

The guard reads what the commit would contain from git's index, never from the work
tree, and compares every added, modified or type-changed blob with the non-empty
values of a closed list of secret variables, read from the uncommitted ``.env`` file
at the repository root and from the process environment. It prints variable names
and, when it holds no value, a path; never a value, not even a part of one.

Exit status: 0 nothing staged equals a local secret; 1 refused; 2 usage error;
3 the guard could not judge (git failed or ``.env`` is unreadable).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from urllib.parse import parse_qsl, unquote, urlsplit

SECRET_NAMES = ("ANTHROPIC_API_KEY", "JEV_PRO_API_KEY", "EII_DATABASE_URL")
DATABASE_URL_NAME = "EII_DATABASE_URL"
DATABASE_SCHEMES = frozenset({"postgres", "postgresql"})
QUERY_SECRET_KEYS = frozenset({"password", "passfile"})
MIN_LENGTH = 12
ENV_FILE = ".env"
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_UNABLE = 3
QUOTES = ('"', "'")
COMMENT_TAIL = re.compile(r"\s+#.*$")
GITLINK_MODE = b"160000"
RECORD_FIELDS = 5
OBJECT_ID = re.compile(rb"[0-9a-f]{40}|[0-9a-f]{64}")
DIFF_ARGS = (
    "diff",
    "--cached",
    "--raw",
    "-z",
    "--no-abbrev",
    "--no-renames",
    "--no-ext-diff",
    "--no-textconv",
    "--no-relative",
    "--ignore-submodules=none",
    f"-O{os.devnull}",
    "--diff-filter=AMT",
)
WITHHELD = "<path withheld>"
REASONS = {
    "weak": f"is shorter than {MIN_LENGTH} characters, so it cannot be checked; use a longer value or remove it",
    "unparseable": "cannot be parsed as a URL, so it cannot be checked; use a longer value or remove it",
    "unreadable": "is written in .env in a form the guard cannot read, so it cannot be checked; fix or remove it",
}


class Unable(Exception):
    """The guard cannot judge; the message is safe to print."""


def git(*args: str) -> bytes:
    """Run git in the current folder and return its standard output.

    Args:
        *args: The git arguments.

    Returns:
        The raw standard output.

    Raises:
        Unable: git is missing or exited with a non-zero status.
    """
    command = args[2] if args[0] == "-C" else args[0]
    try:
        done = subprocess.run(
            ["git", *args], stdin=subprocess.DEVNULL, capture_output=True, check=False
        )
    except OSError as error:
        raise Unable(
            f"git {command} could not start ({type(error).__name__})"
        ) from error
    if done.returncode != 0:
        raise Unable(f"git {command} failed (exit {done.returncode})")
    return done.stdout


def read_value(text: str) -> list[str] | None:
    """Return the values a reader of ``.env`` could take from the text right of ``=``.

    A quoted value ends at its closing quote and may be followed by a comment; a
    double-quoted value that holds a backslash cannot be read with certainty. An
    unquoted value is kept whole and also without a trailing ``  # comment``.

    Args:
        text: The text after the equals sign.

    Returns:
        The candidate values, or None when the text cannot be read with certainty.
    """
    value = text.strip()
    if value.startswith(QUOTES):
        end = value.find(value[0], 1)
        if end <= 0 or (value[0] == '"' and "\\" in value[1:end]):
            return None
        rest = value[end + 1 :].strip()
        if rest and not rest.startswith("#"):
            return None
        return [value[1:end]]
    bare = COMMENT_TAIL.sub("", value)
    return [value] if bare == value else [value, bare]


def parse_env_file(text: str) -> tuple[dict[str, list[str]], list[str]]:
    """Read ``NAME=value`` lines of the closed list from the text of ``.env``.

    Supported form: optional ``export`` and white space, white space around the name,
    one pair of matching quotes, a trailing comment. Every assignment is kept.

    Args:
        text: The decoded file, without a byte order mark.

    Returns:
        The values per secret name, and the names with a line that cannot be read.
    """
    found: dict[str, list[str]] = {}
    unreadable: set[str] = set()
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export") and line[6:7].isspace():
            line = line[6:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or name not in SECRET_NAMES:
            continue
        candidates = read_value(value)
        if candidates is None:
            unreadable.add(name)
        else:
            found.setdefault(name, []).extend(candidates)
    return found, sorted(unreadable)


def needles_for(name: str, value: str) -> tuple[list[str], list[str]]:
    """Turn one configured value into the strings to search for.

    Args:
        name: The variable name.
        value: The configured value, possibly empty.

    Returns:
        The strings to search for, and the problems (``weak`` or ``unparseable``).
    """
    if not value:
        return [], []
    candidates = [value]
    if name == DATABASE_URL_NAME:
        try:
            parts = urlsplit(value)
            _ = parts.port
        except ValueError:
            return [], ["unparseable"]
        if parts.scheme.lower().split("+", 1)[0] not in DATABASE_SCHEMES:
            return [], ["unparseable"]
        if not parts.hostname:
            return [], ["unparseable"]
        if "@" in parts.path + parts.query + parts.fragment:
            return [], ["unparseable"]
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        if any(key.lower() in QUERY_SECRET_KEYS for key, _ in pairs):
            return [], ["unparseable"]
        password = parts.password
        if not password:
            return [], []
        decoded = unquote(password)
        candidates = [password] + ([decoded] if decoded != password else [])
    if any(len(c) < MIN_LENGTH for c in candidates):
        return [], ["weak"]
    return candidates, []


def collect_needles(
    file_values: Mapping[str, list[str]],
    unreadable: list[str],
    environ: Mapping[str, str],
) -> tuple[list[tuple[str, bytes]], list[tuple[str, str]]]:
    """Gather the (name, needle) pairs and the (name, problem) pairs.

    Args:
        file_values: Values read from ``.env``.
        unreadable: The names with a ``.env`` line that cannot be read.
        environ: The process environment.

    Returns:
        The needles as bytes, and the problems.
    """
    needles: list[tuple[str, bytes]] = []
    problems: list[tuple[str, str]] = [(name, "unreadable") for name in unreadable]
    for name in SECRET_NAMES:
        values = list(file_values.get(name, []))
        if name in environ:
            values.append(environ[name])
        for value in values:
            found, trouble = needles_for(name, value)
            needles += [(name, n.encode("utf-8", "surrogateescape")) for n in found]
            problems += [(name, kind) for kind in trouble]
    return sorted(set(needles)), sorted(set(problems))


def staged_blobs(top: str) -> list[tuple[bytes, str | None]]:
    """List (path, blob id) of the content the commit would add or change.

    Args:
        top: The repository root.

    Returns:
        One pair per added, modified or type-changed index entry; a gitlink has
        no blob, so its id is None and only its path is judged.

    Raises:
        Unable: the diff output is not in the expected shape.
    """
    parts = git("-C", top, *DIFF_ARGS).split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    if len(parts) % 2:
        raise Unable("git diff output has an unexpected shape")
    entries: list[tuple[bytes, str | None]] = []
    for meta, path in zip(parts[0::2], parts[1::2], strict=True):
        fields = meta.split(b" ")
        if len(fields) != RECORD_FIELDS or not fields[0].startswith(b":"):
            raise Unable("git diff output has an unexpected shape")
        if not OBJECT_ID.fullmatch(fields[3]):
            raise Unable("git diff output has an unexpected shape")
        blob = None if fields[1] == GITLINK_MODE else fields[3].decode("ascii")
        entries.append((path, blob))
    return entries


def read_env_file(top: str) -> tuple[dict[str, list[str]], list[str]]:
    """Read ``.env`` at the repository root; a missing file holds no values.

    Args:
        top: The repository root.

    Returns:
        The values per secret name.

    Raises:
        Unable: the file exists and cannot be read.
    """
    path = os.path.join(top, ENV_FILE)
    if not os.path.lexists(path):
        return {}, []
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise Unable(f"{ENV_FILE} cannot be read ({type(error).__name__})") from error
    return parse_env_file(data.decode("utf-8-sig", "surrogateescape"))


def show_path(path: bytes, needles: list[tuple[str, bytes]]) -> str:
    """Return a printable form of a path, or a marker if the path holds a needle.

    Args:
        path: The raw index path.
        needles: The (name, needle) pairs.

    Returns:
        A JSON string literal of the path, or the withheld marker.
    """
    if any(needle in path for _, needle in needles):
        return WITHHELD
    return json.dumps(path.decode("utf-8", "surrogateescape"))


def run(environ: Mapping[str, str]) -> int:
    """Judge the staged content.

    Args:
        environ: The process environment.

    Returns:
        The exit status.
    """
    try:
        top = (
            git("rev-parse", "--show-toplevel")
            .decode("utf-8", "surrogateescape")
            .rstrip("\n")
        )
        file_values, unreadable = read_env_file(top)
        needles, problems = collect_needles(file_values, unreadable, environ)
        entries = staged_blobs(top)
        refused = bool(problems)
        for name, kind in problems:
            print(
                f"guard: refused: the local value of {name} {REASONS[kind]}",
                file=sys.stderr,
            )
        for path, blob in entries:
            for name, needle in needles:
                if needle in path:
                    refused = True
                    print(
                        f"guard: refused: a staged path holds the local value of {name}",
                        file=sys.stderr,
                    )
            if blob is None:
                continue
            data = git("-C", top, "cat-file", "blob", blob)
            for name, needle in needles:
                if needle in data:
                    refused = True
                    print(
                        f"guard: refused: staged content of {show_path(path, needles)} "
                        f"holds the local value of {name}",
                        file=sys.stderr,
                    )
    except Unable as error:
        print(f"guard: cannot judge: {error}", file=sys.stderr)
        return EXIT_UNABLE
    if refused:
        return EXIT_REFUSED
    blobs = sum(1 for _, blob in entries if blob is not None)
    print(
        f"guard: checked {blobs} staged file(s) against {len(needles)} local secret value(s)"
    )
    return EXIT_OK


def main(argv: list[str]) -> int:
    """Entry point.

    Args:
        argv: The command-line arguments after the program name; none are accepted.

    Returns:
        The exit status.
    """
    if argv:
        print("usage: commit_guard.py (no arguments)", file=sys.stderr)
        return EXIT_USAGE
    return run(os.environ)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
