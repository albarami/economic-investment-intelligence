"""S1-T11: Stryker command-runner checks in a disposable git-listed copy.

Usage: uv run --locked python scripts/mutation_web.py MODULE [MODULE ...]
Only the command test runner is installed. Browser tests are excluded.
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from mutation import judge

ROOT = Path(__file__).resolve().parents[1]


def parallelism() -> tuple[int, int]:
    """Bound mutation workers times Node test files by available processors."""
    processors = os.cpu_count() or 1
    workers = min(4, processors)
    return workers, max(1, processors // workers)


def run_copy(
    folder: Path,
    modules: list[str],
    command: str,
    ledger: Path,
    *,
    workers: int | None = None,
) -> tuple[int, list[dict[str, str]]]:
    """Run only in a disposable folder; discard tool reports after reading them."""
    if workers is None:
        workers, _ = parallelism()
    # Command workers share Stryker's instrumented sandbox. Each invocation
    # gets its own files so builds and caches cannot race between mutants.
    commands = folder / ".command-sandboxes"
    commands.mkdir()
    prepare = (
        "const fs=require('node:fs');const path=require('node:path');"
        "const {spawnSync}=require('node:child_process');"
        "const work=fs.mkdtempSync(path.join(process.env.EII_MUTATION_COMMANDS,'run-'));"
        "let status=1;try{"
        "fs.cpSync(process.cwd(),work,{recursive:true,filter:source=>"
        "!source.split(path.sep).includes('node_modules') && path.basename(source)!=='dist'});"
        "for(const relative of ['node_modules','web/node_modules']){"
        "const modules=path.join(work,relative);fs.mkdirSync(modules,{recursive:true});"
        "for(const name of fs.readdirSync(process.env.EII_MUTATION_MODULES)){"
        "if(name.startsWith('.') && name!=='.bin') continue;"
        "fs.symlinkSync(path.join(process.env.EII_MUTATION_MODULES,name),path.join(modules,name),'dir');}}"
        "status=spawnSync('sh',['-c',"
        + json.dumps(command)
        + "],{cwd:work,stdio:'inherit'}).status??1;"
        "}finally{fs.rmSync(work,{recursive:true,force:true});}process.exit(status);"
    )
    command = "node -e " + shlex.quote(prepare)
    config = folder / "stryker.task.json"
    report = folder / "reports/mutation.json"
    config.write_text(
        json.dumps(
            {
                "testRunner": "command",
                "commandRunner": {"command": command},
                "mutate": modules,
                "reporters": ["json"],
                "jsonReporter": {"fileName": "reports/mutation.json"},
                "coverageAnalysis": "off",
                "ignoreStatic": False,
                "concurrency": workers,
                "tempDirName": ".stryker-tmp",
                "cleanTempDir": True,
                "thresholds": {"break": 0},
            }
        )
    )
    start = perf_counter()
    try:
        result = subprocess.run(
            [
                "node",
                str(ROOT / "web/node_modules/@stryker-mutator/core/bin/stryker.js"),
                "run",
                str(config),
            ],
            cwd=folder,
            env={
                **os.environ,
                "CI": "true",
                "EII_MUTATION_MODULES": str(folder / "node_modules"),
                "EII_MUTATION_COMMANDS": str(commands),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        print(result.stdout.replace(str(folder), "<temporary>"), end="")
        print(
            result.stderr.replace(str(folder), "<temporary>"), end="", file=sys.stderr
        )
        print(
            f"stryker exit={result.returncode} wall_seconds={perf_counter() - start:.3f}"
        )
        if result.returncode != 0:
            return result.returncode, []
        if not report.is_file():
            print("missing mutation report")
            return 1, []
        files = json.loads(report.read_text())["files"]
        survivors = []
        incomplete = False
        for module in modules:
            if module not in files:
                print(f"{module}: missing module report")
                incomplete = True
                continue
            entry = files[module]
            counts = Counter(mutant["status"] for mutant in entry["mutants"])
            print(
                f"{module}: made={len(entry['mutants'])} killed={counts['Killed']} survived={counts['Survived']} timed_out={counts['Timeout']} no_coverage={counts['NoCoverage']} compile_error={counts['CompileError']} runtime_error={counts['RuntimeError']}"
            )
            for mutant in entry["mutants"]:
                if mutant["status"] in {"Survived", "NoCoverage", "Timeout"}:
                    # Location and replacement bind an explanation to the actual change.
                    mutation = json.dumps(
                        {
                            "location": mutant["location"],
                            "mutator": mutant["mutatorName"],
                            "replacement": mutant["replacement"],
                        },
                        sort_keys=True,
                    )
                    row = {"module": module, "mutation": mutation}
                    if mutant["status"] != "Timeout":
                        survivors.append(row)
                    print(
                        json.dumps(
                            {
                                **row,
                                "line": mutant["location"]["start"]["line"],
                                "status": mutant["status"],
                            },
                            sort_keys=True,
                        )
                    )
            incomplete |= any(
                status
                not in {"Killed", "Survived", "Timeout", "NoCoverage", "CompileError"}
                for status in counts
            )
        return max(int(incomplete), judge(survivors, ledger)), survivors
    finally:
        config.unlink()
        for name in (".stryker-tmp", "reports", ".command-sandboxes"):
            if (folder / name).exists():
                shutil.rmtree(folder / name)


def listed_web_module(module: str, files: set[str]) -> bool:
    """Only copied runtime modules in the spike may be instrumented."""
    return (
        module in files
        and module.startswith("web/spikes/performance/")
        and Path(module).suffix in {".mjs", ".ts"}
    )


def copy_listed_files(root: Path, folder: Path, files: set[str]) -> None:
    """Copy ordinary listed files without following repository symlinks."""
    for name in sorted(files):
        source = root / name
        if source.is_symlink():
            raise ValueError("Refusing a symlink in the mutation copy: " + name)
        if source.is_file():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def link_dependencies(folder: Path, installed: Path) -> None:
    """Reuse package entries while keeping dependency cache directories local."""
    for relative in ("node_modules", "web/node_modules"):
        modules = folder / relative
        modules.mkdir(parents=True)
        for entry in installed.iterdir():
            if not entry.name.startswith(".") or entry.name == ".bin":
                (modules / entry.name).symlink_to(
                    entry, target_is_directory=entry.is_dir()
                )


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
    if any(not listed_web_module(module, files) for module in args.modules):
        parser.error("Every module must be a git-listed performance spike module")
    tests = sorted(
        name
        for name in files
        if name.startswith("web/spikes/performance/tests/")
        and name.endswith(".node-test.mjs")
        and Path(name).name != "run.node-test.mjs"
    )
    workers, node_files = parallelism()
    command = f"node --test --test-concurrency={node_files} " + shlex.join(tests)
    print(f"mutation_workers={workers} node_test_concurrency={node_files}")
    print(f"per_mutant_command={command}", flush=True)
    with TemporaryDirectory(prefix="synthetic-web-mutation-") as temporary:
        folder = Path(temporary)
        copy_listed_files(ROOT, folder, files)
        link_dependencies(folder, ROOT / "web/node_modules")
        code, _survivors = run_copy(
            folder,
            args.modules,
            command,
            ROOT / "scripts/mutation_explained.toml",
            workers=workers,
        )
        return code


if __name__ == "__main__":
    sys.exit(main())
