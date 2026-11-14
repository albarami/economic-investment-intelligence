"""Closed table of the twelve command forms."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

USAGE_PREFIX = "eii: usage error: unknown command or flag."
TEST_FORM = "test [--seed N]"
NOT_YET = "not_built (not built yet)"
State = Literal["real", "placeholder"]


@dataclass(frozen=True)
class Command:
    """One pinned command form."""

    form: str
    word: str
    plane: str
    state: State
    detail: str


COMMANDS: tuple[Command, ...] = (
    Command("preflight", "preflight", "Product", "real", ""),
    Command("db-up", "db-up", "Product", "real", ""),
    Command("db-down", "db-down", "Product", "real", ""),
    Command("up", "up", "Product", "real", NOT_YET),
    Command("up --embedded", "up", "Product", "real", NOT_YET),
    Command("down", "down", "Product", "placeholder", NOT_YET),
    Command(TEST_FORM, "test", "All", "real", ""),
    Command("build-public", "build-public", "Custodian", "real", ""),
    Command("build-world", "build-world", "Custodian", "placeholder", NOT_YET),
    Command("build-release", "build-release", "Custodian", "placeholder", NOT_YET),
    Command(
        "load-release",
        "load-release",
        "Product",
        "placeholder",
        "not_built (built by task S3-T02)",
    ),
    Command(
        "freeze",
        "freeze",
        "Product",
        "placeholder",
        "not_built (built by task S11-T01 and S11-T06)",
    ),
)

WORDS = frozenset(row.word for row in COMMANDS)
PLACEHOLDERS = frozenset(row.word for row in COMMANDS if row.state == "placeholder")


def by_word(word: str) -> Command:
    """Return the first row whose command word is word."""
    for row in COMMANDS:
        if row.word == word:
            return row
    raise KeyError(word)


def usage_text() -> str:
    """Return the usage error text, one form per line."""
    forms = "\n".join(row.form for row in COMMANDS)
    return f"{USAGE_PREFIX}\n{forms}\n"


def write_usage() -> None:
    """Print the usage error text to standard error."""
    sys.stderr.write(usage_text())
