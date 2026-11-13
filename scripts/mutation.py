"""Local mutation runs in a disposable copy of git-listed files (S1-T11 M2).

Usage: python scripts/mutation.py MODULE [MODULE ...]
Each package runs from its own folder with source_paths=["src/"] and its own
tests/ only. Cross-plane scripts/tests/ are not part of a package run.
No hosted hook.
mutmut's metadata and show command are read using the pinned 3.8.1 format.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]


def judge(survivors: list[dict[str, str]], ledger: Path) -> int:
    entries = tomllib.loads(ledger.read_text()).get("survivors", [])
    explained = {
        (row["module"], row["mutation"])
        for row in entries
        if isinstance(row.get("reason"), str) and row["reason"].strip()
    }
    return int(
        any((row["module"], row["mutation"]) not in explained for row in survivors)
    )


def command(folder: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mutmut", *arguments],
        cwd=folder,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        capture_output=True,
        check=False,
    )


def run_copy(
    folder: Path, modules: list[str], tests: list[str], ledger: Path, prefix: str = ""
) -> tuple[int, list[dict[str, str]]]:
    """Operate only inside an already disposable folder; always delete mutants."""
    source_roots = ["src/"]
    # The entire git-listed copy is safe to copy again; no ignored files enter it.
    extra = sorted(path.name for path in folder.iterdir() if path.name != "mutants")
    config = folder / "pyproject.toml"
    original = config.read_text()
    config.write_text(
        original
        + "\n[tool.mutmut]\n"
        + "\n".join(
            [
                "source_paths = " + json.dumps(source_roots),
                "only_mutate = " + json.dumps(modules),
                "also_copy = " + json.dumps(extra),
                "pytest_add_cli_args_test_selection = " + json.dumps(tests),
                'pytest_add_cli_args = ["-p", "no:cacheprovider"]',
                'process_isolation = "fork"',
            ]
        )
        + "\n"
    )
    started = perf_counter()
    survivors: list[dict[str, str]] = []
    try:
        result = command(folder, "run", "--max-children", "1")
        print(result.stdout.replace(str(folder), "<temporary>"), end="")
        print(
            result.stderr.replace(str(folder), "<temporary>"), end="", file=sys.stderr
        )
        print(
            f"mutmut exit={result.returncode} wall_seconds={perf_counter() - started:.3f}"
        )
        if result.returncode != 0:
            return result.returncode, survivors
        incomplete = False
        for module in modules:
            meta = folder / "mutants" / (module + ".meta")
            if not meta.is_file():
                print(f"{module}: no mutation metadata")
                incomplete = True
                continue
            codes = json.loads(meta.read_text())["exit_code_by_key"]
            counts: Counter[str] = Counter()
            for key, code in codes.items():
                status = {
                    0: "survived",
                    1: "killed",
                    3: "killed",
                    5: "not_covered",
                    33: "not_covered",
                    36: "timed_out",
                    -24: "timed_out",
                    24: "timed_out",
                    152: "timed_out",
                    255: "timed_out",
                    37: "killed",
                }.get(code, "incomplete")
                counts[status] += 1
                if status in ("survived", "not_covered"):
                    shown = command(folder, "show", key)
                    if shown.returncode:
                        return shown.returncode, survivors
                    # Store the exact tool diff, not its unstable mutant index or status heading.
                    mutation = "\n".join(shown.stdout.splitlines()[1:]).strip()
                    location = re.search(r"@@ -([0-9]+)", mutation)
                    row = {"module": prefix + module, "mutation": mutation}
                    survivors.append(row)
                    print(
                        json.dumps(
                            {
                                **row,
                                "line": location.group(1) if location else "unknown",
                            },
                            sort_keys=True,
                        )
                    )
            print(
                f"{prefix}{module}: made={len(codes)} killed={counts['killed']} survived={counts['survived']} timed_out={counts['timed_out']} not_covered={counts['not_covered']} incomplete={counts['incomplete']}"
            )
            incomplete = incomplete or bool(counts["incomplete"])
        return max(int(incomplete), judge(survivors, ledger)), survivors
    finally:
        config.write_text(original)
        shutil.rmtree(folder / "mutants", ignore_errors=False) if (
            folder / "mutants"
        ).exists() else None


def run_packages(folder: Path, modules: list[str], ledger: Path) -> int:
    """Keep mutmut's file-derived names identical to package imports."""
    packages = sorted({Path(module).parts[0] for module in modules})
    for package in packages:
        selected = [
            str(Path(module).relative_to(package))
            for module in modules
            if Path(module).parts[0] == package
        ]
        work = folder / package
        config = work / "pyproject.toml"
        original = config.read_text()
        config.write_text(
            original
            + "\n[tool.pytest]\n"
            + 'addopts = ["--import-mode=importlib", "-p", "no:cacheprovider"]\n'
            + 'pythonpath = ["src", "../.."]\n'
        )
        try:
            code, _survivors = run_copy(
                work, selected, ["tests/"], ledger, package + "/"
            )
        finally:
            config.write_text(original)
        if code:
            return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="+")
    args = parser.parse_args()
    listed = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    files = {name for name in listed if name}
    if any(module not in files for module in args.modules):
        parser.error("Every module must be a git-listed file")
    if any(
        Path(module).parts[:2] not in {("custodian", "src"), ("product", "src")}
        for module in args.modules
    ):
        parser.error("Every module must be inside custodian/src or product/src")
    with TemporaryDirectory(prefix="synthetic-mutation-") as temporary:
        folder = Path(temporary)
        for name in sorted(files):
            source = ROOT / name
            if source.is_symlink():
                raise ValueError("Refusing a symlink in the mutation copy: " + name)
            if source.is_file():
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        return run_packages(
            folder, args.modules, ROOT / "scripts/mutation_explained.toml"
        )


if __name__ == "__main__":
    sys.exit(main())
