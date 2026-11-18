"""Local mutation runs in a disposable copy of git-listed files (S1-T11 M2).

Usage: python scripts/mutation.py MODULE [MODULE ...]
Each package runs from its own folder with source_paths=["src/"] and its own
tests/ only. Cross-plane scripts/tests/ are not part of a package run.
For a package run the copy's root is made an empty git repository, so that a
package test that asks git about an ignore rule gets git's own answer.
The four typed-decision modules run from the copy's root with evals/ as their
source root and scripts/tests/test_requalify.py as their test selection.
Optional S1-T20 pilot discovery, subset and report exports; the default path is local.
mutmut's metadata and show command are read using the pinned 3.8.1 format.
"""

import argparse
import importlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# Source-text checks inspect instrumentation, not calculated values (L-273 part 3).
SOURCE_TEXT_GUARDS = {
    "core/tests/test_calculation_purity.py::test_purity_guard_and_planted_io_helper": "The AST import allow-list refuses mutmut.mutation.trampoline instrumentation.",
    "custodian/tests/test_publicdata_heights.py::test_no_python_file_repeats_the_storey_literal": "The storey-literal scan reads the instrumented heights files, whose mutant copies hold changed numeric literals.",
}

EVAL_MODULES = {
    "evals/typed_decisions/" + name + ".py"
    for name in ("interval", "reproduction", "route", "requalify")
}
# Each of these points git at a repository other than the one of the folder it runs in.
GIT_REDIRECTS = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
    }
)


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


def package_environment() -> dict[str, str]:
    """The caller's environment without the variables that redirect git."""
    return {
        name: value for name, value in os.environ.items() if name not in GIT_REDIRECTS
    }


def command(
    folder: Path, *arguments: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mutmut", *arguments],
        cwd=folder,
        env={
            **(os.environ if environment is None else environment),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        text=True,
        capture_output=True,
        check=False,
    )


def run_copy(
    folder: Path,
    modules: list[str],
    tests: list[str],
    ledger: Path,
    prefix: str = "",
    *,
    source_roots: list[str] | None = None,
    environment: dict[str, str] | None = None,
    pilot_options: dict[str, Any] | None = None,
) -> tuple[int, list[dict[str, str]]]:
    """Operate only inside an already disposable folder; always delete mutants."""
    for test in tests:
        if test.startswith("-"):
            print(f"Refusing test selection option: {test}", file=sys.stderr)
            return 2, []
    if os.environ.get("PYTEST_ADDOPTS"):
        print("Refusing PYTEST_ADDOPTS in mutation run", file=sys.stderr)
        return 2, []
    pytest_args = ["-p", "no:cacheprovider"]
    for node in SOURCE_TEXT_GUARDS:
        if prefix and node.startswith(prefix):
            pytest_args.append("--deselect=" + node.removeprefix(prefix))
    if source_roots is None:
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
                "pytest_add_cli_args = " + json.dumps(pytest_args),
                'process_isolation = "fork"',
            ]
        )
        + "\n"
    )
    started = perf_counter()
    survivors: list[dict[str, str]] = []
    try:
        if pilot_options is not None:
            try:
                return run_pilot_copy(
                    folder, modules, ledger, prefix, environment, pilot_options
                )
            except (
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                RecursionError,
                OSError,
            ) as exc:
                pilot = importlib.import_module(
                    "scripts.mutation_pilot" if __package__ else "mutation_pilot"
                )
                reason = (
                    str(exc)
                    if isinstance(exc, pilot.Refusal)
                    else "pilot-infrastructure"
                )
                print("mutation-pilot: " + reason, file=sys.stderr)
                if pilot_options.get("report"):
                    try:
                        pilot.write(
                            pilot_options["report"],
                            {"command_exit": 2, "incidents": [reason], "records": []},
                        )
                    except (ValueError, OSError):
                        print("mutation-pilot: evidence-write-failed", file=sys.stderr)
                return 2, []
        result = command(folder, "run", "--max-children", "1", environment=environment)
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
                    shown = command(folder, "show", key, environment=environment)
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


def run_pilot_copy(
    folder: Path,
    modules: list[str],
    ledger: Path,
    prefix: str,
    environment: dict[str, str] | None,
    options: dict[str, Any],
) -> tuple[int, list[dict[str, str]]]:
    """Version-checked discovery and exact-name runs inside run_copy's cleanup."""
    pilot = importlib.import_module(
        "scripts.mutation_pilot" if __package__ else "mutation_pilot"
    )
    started = perf_counter()
    adapter = "\n".join(
        [
            "from importlib.metadata import version",
            "if version('mutmut') != '3.8.1': raise RuntimeError('mutmut-version')",
            "from mutmut.__main__ import copy_src_dir, copy_also_copy_files, setup_source_paths, store_lines_covered_by_tests, create_mutants",
            "copy_src_dir()",
            "copy_also_copy_files()",
            "setup_source_paths()",
            "store_lines_covered_by_tests()",
            "create_mutants(max_children=1)",
        ]
    )
    generated = subprocess.run(
        [sys.executable, "-c", adapter],
        cwd=folder,
        env={
            **(os.environ if environment is None else environment),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if generated.returncode:
        print("mutation-pilot: generation-failed")
        if options.get("report"):
            pilot.write(
                options["report"],
                {
                    "command_exit": generated.returncode,
                    "incidents": ["generation-failed"],
                    "records": [],
                },
            )
        return generated.returncode, []
    module = modules[0]
    meta = folder / "mutants" / (module + ".meta")
    names = sorted(json.loads(meta.read_text())["exit_code_by_key"])
    rows = []
    diffs = {}
    for name in names:
        shown = command(folder, "show", name, environment=environment)
        if shown.returncode:
            if options.get("report"):
                pilot.write(
                    options["report"],
                    {
                        "command_exit": shown.returncode,
                        "incidents": ["diff-export-failed"],
                        "records": [],
                    },
                )
            return shown.returncode, []
        diff = "\n".join(shown.stdout.splitlines()[1:]).strip()
        diffs[name] = diff
        rows.append({"name": name, "diff_sha256": pilot.digest(diff.encode())})
    universe = pilot.manifest(options["context"], rows)
    if options.get("list_mutants"):
        pilot.write(options["list_mutants"], universe)
        return 0, []
    index = options.get("shard_index")
    selected = rows
    if options.get("mutant_list"):
        supplied = pilot.read(options["mutant_list"])
        pilot.verify_manifest(supplied)
        if universe != supplied:
            raise pilot.Refusal("regenerated-universe")
        selected = pilot.assigned(universe, index)
    generation_seconds = perf_counter() - started
    # An empty assignment cannot be expressed to mutmut: no names means all.
    if not selected:
        raise pilot.Refusal("empty-assignment")
    phases_path = folder / "pilot-phases.json"
    timing_adapter = "\n".join(
        [
            "import atexit, functools, json, sys, time",
            "from pathlib import Path",
            "import mutmut.__main__ as m",
            "phases = {}",
            "def timed(owner, name, label):",
            "    original = getattr(owner, name)",
            "    @functools.wraps(original)",
            "    def call(*args, **kwargs):",
            "        started = time.perf_counter()",
            "        try: return original(*args, **kwargs)",
            "        finally: phases[label] = phases.get(label, 0) + time.perf_counter() - started",
            "    setattr(owner, name, call)",
            "timed(m, 'run_stats_collection', 'stats_seconds')",
            "timed(m, 'run_forced_fail_test', 'forced_fail_seconds')",
            "timed(type(m.get_mutant_runner()), 'run_clean_tests', 'clean_tests_seconds')",
            "atexit.register(lambda: Path('pilot-phases.json').write_text(json.dumps(phases)))",
            "m.cli(args=sys.argv[1:])",
        ]
    )
    before_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            timing_adapter,
            "run",
            *([r["name"] for r in selected] if index is not None else []),
            "--max-children",
            "1",
        ],
        cwd=folder,
        env={
            **(os.environ if environment is None else environment),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        text=True,
        capture_output=True,
        check=False,
    )
    after_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    codes = json.loads(meta.read_text())["exit_code_by_key"]
    records = []
    survivors = []
    for row in selected:
        code = codes[row["name"]]
        outcome = pilot.status(code)
        record = dict(row, raw_exit=code, status=outcome)
        if outcome in ("survived", "not_covered"):
            record["mutation"] = diffs[row["name"]]
            survivors.append(
                {"module": prefix + module, "mutation": diffs[row["name"]]}
            )
        records.append(record)
    payload = pilot.report(universe, index, records, result.returncode)
    payload["timing"] = {
        "discovery_seconds": generation_seconds,
        "campaign_seconds": perf_counter() - started - generation_seconds,
        "campaign_cpu_seconds": after_cpu.ru_utime
        + after_cpu.ru_stime
        - before_cpu.ru_utime
        - before_cpu.ru_stime,
        "qualification": json.loads(phases_path.read_text())
        if phases_path.is_file()
        else {"incident": "missing-phase-timing"},
        "load_average": list(os.getloadavg()),
    }
    if phases_path.is_file():
        phases_path.unlink()
    # The phase file was consumed above; qualification must hold all completed phases.
    phase_ok = all(
        name in payload["timing"]["qualification"]
        for name in ("stats_seconds", "forced_fail_seconds", "clean_tests_seconds")
    )
    payload["incidents"] = [] if phase_ok else ["missing-phase-timing"]
    payload["budgets"] = {
        "timeout_constant": 1,
        "timeout_multiplier": 15,
        "max_children": 1,
        "isolation": "fork",
    }
    if index is None and result.returncode == 0 and phase_ok:
        payload = pilot.summary(
            universe, pilot.checked_records(universe, payload, universe["mutants"])
        ) | {"timing": payload["timing"], "budgets": payload["budgets"]}
    pilot.write(options["report"], payload)
    print(f"mutation-pilot: command_exit={result.returncode}")
    return (
        result.returncode
        or max(
            int(
                not phase_ok
                or any(r["status"] == "infrastructure_failure" for r in records)
            ),
            judge(survivors, ledger),
        )
    ), survivors


def run_packages(
    folder: Path,
    modules: list[str],
    ledger: Path,
    pilot_options: dict[str, Any] | None = None,
) -> int:
    """Keep mutmut's file-derived names identical to package imports."""
    packages = sorted({Path(module).parts[0] for module in modules})
    # A package test may ask git about an ignore rule. The copy holds the listed
    # ignore files; an empty repository at its root lets git evaluate them itself.
    # Neither the init nor the package's tests may follow a caller's git variables
    # to another repository.
    environment = package_environment()
    if packages:
        subprocess.run(
            ["git", "init", "--quiet", str(folder)],
            check=True,
            capture_output=True,
            env=environment,
        )
    for package in packages:
        selected = [
            str(Path(module).relative_to(package))
            for module in modules
            if Path(module).parts[0] == package
        ]
        work = folder / package
        # Instrumented tests are one level deeper; preserve their repository-doc path.
        if (folder / "docs").is_dir():
            shutil.copytree(folder / "docs", work / "docs")
        config = work / "pyproject.toml"
        original = config.read_text()
        config.write_text(
            original
            + "\n[tool.pytest]\n"
            + 'addopts = ["--import-mode=importlib", "-p", "no:cacheprovider"]\n'
            + 'pythonpath = ["src", "../..", "../../scripts", "../../scripts/tests"]\n'
        )
        try:
            code, _survivors = run_copy(
                work,
                selected,
                ["tests/"],
                ledger,
                package + "/",
                environment=environment,
                pilot_options=pilot_options,
            )
        finally:
            config.write_text(original)
        if code:
            return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="+")
    parser.add_argument("--list-mutants", type=Path)
    parser.add_argument("--mutant-list", type=Path)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    pilot_options = None
    if any(
        v is not None
        for v in (args.list_mutants, args.mutant_list, args.shard_index, args.report)
    ):
        pilot = importlib.import_module(
            "scripts.mutation_pilot" if __package__ else "mutation_pilot"
        )
        if args.modules != [pilot.MODULE]:
            parser.error("wrong-module")
        if (
            (
                args.list_mutants
                and (args.report or args.mutant_list or args.shard_index is not None)
            )
            or (bool(args.mutant_list) != (args.shard_index is not None))
            or (args.mutant_list and not args.report)
        ):
            parser.error("incompatible-pilot-options")
        if args.shard_index is not None and args.shard_index not in range(4):
            parser.error("shard-index")
        pilot_options = {
            k: getattr(args, k)
            for k in ("list_mutants", "mutant_list", "shard_index", "report")
            if getattr(args, k) is not None
        }
        for key in ("list_mutants", "mutant_list", "report"):
            if key in pilot_options:
                path = pilot_options[key]
                if (
                    path.is_absolute()
                    or any(ord(c) < 32 or ord(c) == 127 for c in str(path))
                    or ".." in path.parts
                    or path.is_symlink()
                    or any(p.is_symlink() for p in path.parents)
                ):
                    parser.error("unsafe-evidence-path")
                pilot_options[key] = ROOT / path
        for name in (
            pilot.MODULE,
            "uv.lock",
            "scripts/mutation.py",
            "scripts/mutation_pilot.py",
            "scripts/mutation_explained.toml",
        ):
            candidate = ROOT / name
            if candidate.is_symlink() or any(p.is_symlink() for p in candidate.parents):
                parser.error("symlink-source")
        pilot_options["context"] = {
            "commit": pilot.git(ROOT, "rev-parse", "HEAD").decode().strip(),
            "module": pilot.MODULE,
            "hashes": {
                name: pilot.digest((ROOT / name).read_bytes())
                for name in (
                    pilot.MODULE,
                    "uv.lock",
                    "scripts/mutation.py",
                    "scripts/mutation_pilot.py",
                    "scripts/mutation_explained.toml",
                )
            },
        }
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
        module not in EVAL_MODULES
        and Path(module).parts[:2]
        not in {("core", "src"), ("custodian", "src"), ("product", "src")}
        for module in args.modules
    ):
        parser.error(
            "Every module must be inside core/src, custodian/src or product/src "
            "or one of the four typed-decision modules"
        )
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
        ledger = ROOT / "scripts/mutation_explained.toml"
        evals = [module for module in args.modules if module in EVAL_MODULES]
        packages = [module for module in args.modules if module not in EVAL_MODULES]
        if evals:
            code, _survivors = run_copy(
                folder,
                evals,
                ["scripts/tests/test_requalify.py"],
                ledger,
                source_roots=["evals/"],
            )
            if code:
                return code
        return run_packages(
            folder,
            packages,
            ledger,
            pilot_options=pilot_options,
        )


if __name__ == "__main__":
    sys.exit(main())
