#!/usr/bin/env python3
"""Repository tree check.

Run from the repository root:

    python3 scripts/check_tree.py [--root PATH]

``--root`` defaults to the repository root (the parent of the ``scripts/``
folder that holds this script) and exists so that tests can aim the check at
a fixture.

Exit code 0 means every rule passed; the only output is
``checked 8 rules: OK``. Exit code 1 means at least one rule failed: each
failure is printed as ``FAIL <rule>: <path>: <detail>`` and the last output
line is ``checked 8 rules: <k> failure(s)``. Exit code 2 means a usage
error, a root that is not the top of a git work tree, or a failed git call;
a one-line reason goes to standard error.

The check judges the staged state (git's index): a file that exists but is
not staged does not count as tracked, and a ``.gitignore`` with unstaged
edits does not count as committed. The check only reads; it never creates,
changes or deletes anything in the work tree or in git.

Rules, in order:

1. committed-folder: each pinned top-level folder exists as a directory and
   has at least one tracked file.
2. top-level-folder: every tracked path lives in a pinned folder or in
   ``.github/``.
3. data-untracked: nothing under ``data/`` is tracked, and ``data/`` on disk,
   if present at all, is a real directory and not a symbolic link.
4. data-ignored: every generated-data probe is ignored by a committed rule.
5. secrets-ignored: every secret probe is ignored by a committed rule.
6. generated-ignored: every generated-artefact probe is ignored by a
   committed rule.
7. env-example: the staged ``.env.example`` is a regular file, is not
   ignored, and holds exactly the pinned variable names, each with an
   empty value. Its content is read from git's index, never from the
   work tree. When an unsynced ``.gitignore`` affects it, the rule reports
   that it cannot be judged.
8. tracked-ignored: no tracked path is ignored by a committed rule. Each
   unsynced ``.gitignore`` is reported, in sorted order, before the
   per-path lines.

"Committed rule" means a pattern from a relative path whose last component
is ``.gitignore``, itself tracked, whose index entry and work-tree path are
both regular files (the work-tree path is not a symbolic link and does not
lie beyond one) and whose work-tree bytes equal the staged blob read from
the index. Git's own change detection is not relied on. A tracked
``.gitignore`` that fails that comparison is unsynced and affects every
path in its folder and below; the root file affects every path. Rules 4
to 6 count an affected probe as not ignored by a committed rule. Rule 7
reports that ``.env.example`` cannot be judged when an unsynced source
affects it, and rule 8 reports each unsynced source. ``.git/info/exclude``,
an untracked ``.gitignore`` and any personal ignore file never count:
every git call uses ``core.excludesFile=<null device>`` and empty global
and system configuration.

A path that lies beyond a symbolic link (one of its parent folders in the
work tree is a symbolic link) is never passed to git, because git refuses
to judge such a path. A probe of that kind counts as not ignored by a
committed rule.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

PINNED_FOLDERS = (
    "contracts", "core", "custodian", "product", "web",
    "evals", "gateway", "infra", "scripts", "docs",
)
TOP_LEVEL_ALLOWED = frozenset(PINNED_FOLDERS) | {".github"}

DATA_PROBES = (
    "data/public_cache/x",
    "data/vault/x",
    "data/releases/x/manifest.json",
    "data/ledger_local.sqlite",
    "data/logs/x.jsonl",
    "data/freeze/x/SHA256SUMS",
)
SECRET_PROBES = (
    ".env",
    ".env.local",
    "web/.env",
    "web/.env.production",
    "cert.pem",
    "infra/tls.key",
)
GENERATED_PROBES = (
    ".venv/x",
    "node_modules/x",
    "web/node_modules/x",
    "web/dist/x",
    "core/__pycache__/x",
    ".pytest_cache/x",
    "core/eii_core.egg-info/PKG-INFO",
    ".coverage.worker",
    "web/tsconfig.tsbuildinfo",
    "web/.eslintcache",
)

ENV_EXAMPLE = ".env.example"
ENV_EXAMPLE_NAMES = (
    "ANTHROPIC_API_KEY",
    "EII_STORE",
    "EII_DATABASE_URL",
    "EII_RELEASE_DIR",
    "EII_LANG_DEFAULT",
    "EII_PRESENTER",
    "EII_DECISION_PROVIDER",
    "JEV_PRO_API_KEY",
)
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*=$")

RULE_COUNT = 8
REGULAR_INDEX_MODES = (b"100644", b"100755")


class CheckError(Exception):
    """A root-validation or git failure; reported on standard error."""


def git(root: Path, *args: str, feed: bytes = b"") -> subprocess.CompletedProcess:
    """One git call with personal ignore files and user configuration off."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    try:
        return subprocess.run(
            ["git", "-c", f"core.excludesFile={os.devnull}",
             "-C", str(root), *args],
            input=feed, capture_output=True, env=env)
    except OSError as exc:
        raise CheckError(f"git could not be run: {exc}") from exc


def validate_root(root: Path) -> None:
    """Refuse anything that is not the top of a git work tree."""
    if not (root / ".git").exists():
        raise CheckError(f"{root}: not the top of a git work tree")
    done = git(root, "rev-parse", "--show-toplevel")
    if done.returncode != 0:
        raise CheckError("git rev-parse --show-toplevel failed")
    top = done.stdout.decode("utf-8", errors="replace").strip()
    if not top or Path(top).resolve() != root:
        raise CheckError(f"{root}: not the top of a git work tree")


def tracked_files(root: Path) -> set:
    """TRACKED: staged, repository-relative paths."""
    done = git(root, "ls-files", "-z", "--cached")
    if done.returncode != 0:
        raise CheckError("git ls-files failed")
    return {name for name in
            done.stdout.decode("utf-8", errors="replace").split("\0") if name}


def beyond_a_symbolic_link(root: Path, path: str) -> bool:
    """True when a proper ancestor folder of path under root is a link."""
    folder = root
    for component in path.split("/")[:-1]:
        folder = folder / component
        if os.path.islink(folder):
            return True
    return False


def ignore_matches(root: Path, paths: set) -> dict:
    """MATCH: the deciding ignore record for each path that has one."""
    judged = {path for path in paths
              if not beyond_a_symbolic_link(root, path)}
    if not judged:
        return {}
    feed = ("\0".join(sorted(judged)) + "\0").encode("utf-8")
    done = git(root, "check-ignore", "-v", "-z", "--no-index", "--stdin",
               feed=feed)
    if done.returncode not in (0, 1):
        raise CheckError("git check-ignore failed")
    fields = [field for field in done.stdout.split(b"\0") if field]
    if len(fields) % 4:
        raise CheckError("git check-ignore returned unexpected output")
    records = {}
    for index in range(0, len(fields), 4):
        source, line, pattern, path = (
            fields[index + offset].decode("utf-8", errors="replace")
            for offset in range(4))
        records[path] = (source, line, pattern)
    return records


def index_entry_is_regular(root: Path, source: str) -> bool:
    """True when the index mode of source is 100644 or 100755."""
    done = git(root, "ls-files", "-s", "-z", "--", source)
    if done.returncode != 0:
        raise CheckError("git ls-files failed")
    mode = done.stdout.split(b" ", 1)[0]
    return mode in REGULAR_INDEX_MODES


def work_tree_is_regular(root: Path, source: str) -> bool:
    """True when source is a regular file and not beyond a symbolic link."""
    if beyond_a_symbolic_link(root, source):
        return False
    try:
        info = (root / source).lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode)


def staged_blob(root: Path, source: str) -> bytes:
    """Return the staged blob of source."""
    done = git(root, "cat-file", "blob", f":{source}")
    if done.returncode != 0:
        raise CheckError("git cat-file failed")
    return done.stdout


def gitignore_matches_staged(root: Path, source: str) -> bool:
    """True when a tracked ignore file equals the blob staged for it.

    The index entry and the work-tree path must both be regular files, and
    the work-tree bytes must equal the staged blob. A symbolic link, a
    folder or a missing file is rejected before any work-tree byte is read.
    """
    if not index_entry_is_regular(root, source):
        return False
    if not work_tree_is_regular(root, source):
        return False
    try:
        found = (root / source).read_bytes()
    except OSError:
        return False
    return found == staged_blob(root, source)


def gitignore_affects(source: str, path: str) -> bool:
    """True when source is the root ignore file or a folder above path."""
    if source == ".gitignore":
        return True
    folder = source[:-len(".gitignore")]
    return folder.endswith("/") and path.startswith(folder)


class Checker:
    """The staged state of one work tree, read once."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.tracked = tracked_files(root)
        probes = (set(DATA_PROBES) | set(SECRET_PROBES)
                  | set(GENERATED_PROBES) | {ENV_EXAMPLE})
        self.matches = ignore_matches(root, probes | self.tracked)
        self._committed: dict[str, bool] = {}
        self.unsynced = self._unsynced_sources()

    def _unsynced_sources(self) -> list[str]:
        """Sorted tracked .gitignore paths that do not equal their staged blob."""
        return sorted(
            path for path in self.tracked
            if path.split("/")[-1] == ".gitignore"
            and not self.source_committed(path))

    def source_committed(self, source: str) -> bool:
        """True when source is a tracked .gitignore equal to its staged blob."""
        if source not in self._committed:
            tracked_gitignore = (
                not source.startswith("/")
                and source.split("/")[-1] == ".gitignore"
                and source in self.tracked)
            self._committed[source] = (
                tracked_gitignore
                and gitignore_matches_staged(self.root, source))
        return self._committed[source]

    def affected_by_unsynced(self, path: str) -> bool:
        """True when an unsynced .gitignore lies at the root or above path."""
        return any(
            gitignore_affects(source, path) for source in self.unsynced)

    def ignored_by_committed_rule(self, path: str) -> bool:
        """True when path has a non-negated record from a committed source."""
        record = self.matches.get(path)
        return (
            record is not None
            and not record[2].startswith("!")
            and self.source_committed(record[0]))


def committed_folder(check: Checker, failures: list) -> None:
    for name in PINNED_FOLDERS:
        if not (check.root / name).is_dir():
            failures.append(f"FAIL committed-folder: {name}: missing")
        elif not any(path.startswith(name + "/") for path in check.tracked):
            failures.append(f"FAIL committed-folder: {name}: no tracked file")


def top_level_folder(check: Checker, failures: list) -> None:
    components = sorted({
        path.split("/", 1)[0]
        for path in check.tracked if "/" in path
    } - TOP_LEVEL_ALLOWED)
    for component in components:
        failures.append(
            f"FAIL top-level-folder: {component}: not a pinned folder")


def data_untracked(check: Checker, failures: list) -> None:
    for path in sorted(check.tracked):
        if path == "data" or path.startswith("data/"):
            failures.append(f"FAIL data-untracked: {path}: tracked")
    data = check.root / "data"
    if os.path.lexists(data) and (not data.is_dir() or data.is_symlink()):
        failures.append("FAIL data-untracked: data: not a real directory")


def probes_ignored(check: Checker, failures: list,
                   probes: tuple, rule: str) -> None:
    for probe in probes:
        if (check.affected_by_unsynced(probe)
                or not check.ignored_by_committed_rule(probe)):
            failures.append(
                f"FAIL {rule}: {probe}: not ignored by a committed rule")


def env_example(check: Checker, failures: list) -> None:
    tracked = ENV_EXAMPLE in check.tracked
    if not tracked:
        failures.append(f"FAIL env-example: {ENV_EXAMPLE}: not tracked")
    record = check.matches.get(ENV_EXAMPLE)
    if record is not None and not record[2].startswith("!"):
        failures.append(
            f"FAIL env-example: {ENV_EXAMPLE}: "
            f"ignored by {record[0]}:{record[1]}")
    if check.affected_by_unsynced(ENV_EXAMPLE):
        failures.append(
            f"FAIL env-example: {ENV_EXAMPLE}: cannot be judged: "
            ".gitignore differs from its staged content")
    if not tracked:
        return
    done = git(check.root, "ls-files", "-s", "-z", "--", ENV_EXAMPLE)
    if done.returncode != 0:
        raise CheckError("git ls-files failed")
    if done.stdout.split(b" ", 1)[0] not in (b"100644", b"100755"):
        failures.append(
            f"FAIL env-example: {ENV_EXAMPLE}: "
            "not a regular file in the index")
        return
    done = git(check.root, "cat-file", "blob", f":{ENV_EXAMPLE}")
    if done.returncode != 0:
        raise CheckError("git cat-file failed")
    try:
        lines = done.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        failures.append(
            f"FAIL env-example: {ENV_EXAMPLE}: cannot be read as UTF-8")
        return
    names = []
    for number, line in enumerate(lines, 1):
        if not line or line.startswith("#"):
            continue
        if not ENV_NAME.match(line):
            failures.append(
                f"FAIL env-example: {ENV_EXAMPLE}:{number}: "
                "not a name with an empty value")
        else:
            names.append(line[:-1])
    if names != list(ENV_EXAMPLE_NAMES):
        failures.append(
            f"FAIL env-example: {ENV_EXAMPLE}: names differ from the pinned list")


def tracked_ignored(check: Checker, failures: list) -> None:
    for source in check.unsynced:
        failures.append(
            f"FAIL tracked-ignored: {source}: differs from its staged content")
    for path in sorted(check.tracked):
        record = check.matches.get(path)
        if (record is not None and not record[2].startswith("!")
                and check.source_committed(record[0])):
            failures.append(
                f"FAIL tracked-ignored: {path}: "
                f"tracked although ignored by {record[0]}:{record[1]}")


def run(root: Path) -> list:
    validate_root(root)
    check = Checker(root)
    failures: list = []
    committed_folder(check, failures)
    top_level_folder(check, failures)
    data_untracked(check, failures)
    probes_ignored(check, failures, DATA_PROBES, "data-ignored")
    probes_ignored(check, failures, SECRET_PROBES, "secrets-ignored")
    probes_ignored(check, failures, GENERATED_PROBES, "generated-ignored")
    env_example(check, failures)
    tracked_ignored(check, failures)
    return failures


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_tree.py",
        description="Check the pinned repository layout and ignore rules "
                    "against the staged state of a git work tree.")
    parser.add_argument(
        "--root", metavar="PATH", default=None,
        help="work tree to check (default: the repository root)")
    args = parser.parse_args(argv)
    root = (Path(args.root).resolve() if args.root
            else Path(__file__).resolve().parent.parent)
    try:
        failures = run(root)
    except CheckError as exc:
        print(f"check_tree.py: {exc}", file=sys.stderr)
        return 2
    for line in failures:
        print(line)
    summary = "OK" if not failures else f"{len(failures)} failure(s)"
    print(f"checked {RULE_COUNT} rules: {summary}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
