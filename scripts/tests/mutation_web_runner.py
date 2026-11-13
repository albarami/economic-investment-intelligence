"""Run Stryker's command runner on an invented module in disposable folders."""

import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest


def test_web_runner_refuses_survivor_and_accepts_exact_explanation() -> None:
    assert (Path(__file__).parents[1] / "mutation_web.py").is_file()
    runner = importlib.import_module("mutation_web")
    with TemporaryDirectory(prefix="synthetic-web-mutant-test-") as temporary:
        folder = Path(temporary)
        (folder / "web").mkdir()
        (folder / "package.json").write_text('{"type":"module"}')
        (folder / "toy.mjs").write_text("export const value = (n) => n + 1;\n")
        (folder / "web/vite.config.ts").write_text("export default {};\n")
        cache = runner.ROOT / "web/node_modules/.vite-temp"
        cache_before = cache.stat().st_mtime_ns if cache.exists() else None
        (folder / "toy.test.mjs").write_text(
            "import {value} from './toy.mjs';\n"
            "import assert from 'node:assert/strict';\n"
            "import fs from 'node:fs';\n"
            "import path from 'node:path';\n"
            "assert.equal(path.dirname(process.cwd()),process.env.EII_MUTATION_COMMANDS);\n"
            "import {loadConfigFromFile} from 'vite';\n"
            "await loadConfigFromFile({command:'build',mode:'test'},'web/vite.config.ts');\n"
            "assert.ok(fs.statSync('web/node_modules/.vite-temp').isDirectory());\n"
            "assert.ok(!fs.lstatSync('web/node_modules').isSymbolicLink());\n"
            "assert.ok(fs.existsSync(new URL('./web/node_modules/typescript/lib/tsc.js', import.meta.url)));\n"
            "assert.ok(value(10) > 0);\n"
        )
        ledger = folder / "explained.toml"
        ledger.write_text("survivors = []\n")
        runner.link_dependencies(folder, runner.ROOT / "web/node_modules")
        code, survivors = runner.run_copy(
            folder, ["toy.mjs"], "node toy.test.mjs", ledger
        )
        assert code == 1
        assert survivors
        ledger.write_text(
            "\n".join(
                "[[survivors]]\nmodule = "
                + json.dumps(row["module"])
                + "\nmutation = "
                + json.dumps(row["mutation"])
                + '\nreason = "Invented runner fixture; matching only."'
                for row in survivors
            )
        )
        code, after = runner.run_copy(folder, ["toy.mjs"], "node toy.test.mjs", ledger)
        assert code == 0
        assert after == survivors
        assert (cache.stat().st_mtime_ns if cache.exists() else None) == cache_before
        assert not (folder / ".stryker-tmp").exists()
        assert not (folder / "reports").exists()
        assert not (folder / ".command-sandboxes").exists()


def test_web_runner_rejects_modules_outside_its_closed_copy() -> None:
    runner = importlib.import_module("mutation_web")
    assert callable(getattr(runner, "listed_web_module", None))
    files = {
        "web/spikes/performance/trace.mjs",
        "web/spikes/performance/main.ts",
        "web/spikes/performance/README.md",
        "custodian/unrelated.mjs",
    }
    assert runner.listed_web_module("web/spikes/performance/trace.mjs", files)
    assert runner.listed_web_module("web/spikes/performance/main.ts", files)
    assert not runner.listed_web_module("web/spikes/performance/unlisted.mjs", files)
    assert not runner.listed_web_module("web/spikes/performance/README.md", files)
    assert not runner.listed_web_module("custodian/unrelated.mjs", files)


def test_web_runner_fails_closed_on_tool_and_report_faults() -> None:
    """Inject report faults a command runner cannot normally emit.

    The separate integration test above runs real pinned Stryker. This temporary
    Node reporter is needed for impossible/failed-tool metadata, not a substitute
    for that integration test.
    """
    from unittest.mock import patch

    runner = importlib.import_module("mutation_web")
    mutant = {
        "status": "NoCoverage",
        "location": {
            "start": {"line": 1, "column": 0},
            "end": {"line": 1, "column": 1},
        },
        "mutatorName": "BooleanLiteral",
        "replacement": "false",
    }
    for label, status, report_kind, expected in (
        ("tool-failed", 2, "empty", 2),
        ("missing-report", 0, "missing", 1),
        ("missing-module", 0, "other", 1),
        ("uncovered", 0, "NoCoverage", 1),
        ("survived", 0, "Survived", 1),
        ("runtime-error", 0, "RuntimeError", 1),
        ("unknown-status", 0, "Unexpected", 1),
        ("killed", 0, "Killed", 0),
        ("compile-error", 0, "CompileError", 0),
        ("timeout", 0, "Timeout", 0),
    ):
        with TemporaryDirectory(prefix="synthetic-report-fault-") as temporary:
            folder = Path(temporary)
            tool = folder / "web/node_modules/@stryker-mutator/core/bin/stryker.js"
            tool.parent.mkdir(parents=True)
            work = folder / "work"
            work.mkdir()
            ledger = work / "explained.toml"
            ledger.write_text("survivors = []\n")
            report: dict[str, Any] = {"files": {"toy.mjs": {"mutants": []}}}
            if report_kind == "other":
                report["files"] = {}
            elif report_kind not in {"empty", "missing"}:
                report["files"]["toy.mjs"]["mutants"] = [
                    {**mutant, "status": report_kind}
                ]
            script = (
                "const fs=require('node:fs');"
                "fs.mkdirSync('reports');fs.mkdirSync('.stryker-tmp');"
            )
            if report_kind != "missing":
                script += (
                    "fs.writeFileSync('reports/mutation.json',"
                    + json.dumps(json.dumps(report))
                    + ");"
                )
            tool.write_text(script + "process.exit(" + str(status) + ");")
            with patch.object(runner, "ROOT", folder):
                code, survivors = runner.run_copy(work, ["toy.mjs"], "unused", ledger)
            assert code == expected, label
            assert bool(survivors) == (report_kind in {"NoCoverage", "Survived"}), label
            assert not (work / "stryker.task.json").exists(), label
            assert not (work / ".stryker-tmp").exists(), label
            assert not (work / "reports").exists(), label
            if survivors:
                ledger.write_text(
                    "\n".join(
                        "[[survivors]]\nmodule = "
                        + json.dumps(row["module"])
                        + "\nmutation = "
                        + json.dumps(row["mutation"])
                        + '\nreason = "Synthetic metadata fixture only."'
                        for row in survivors
                    )
                )
                with patch.object(runner, "ROOT", folder):
                    accepted, after = runner.run_copy(
                        work, ["toy.mjs"], "unused", ledger
                    )
                assert accepted == 0, label
                assert after == survivors, label
                assert not (work / "stryker.task.json").exists(), label
                assert not (work / ".stryker-tmp").exists(), label
                assert not (work / "reports").exists(), label


def test_web_copy_refuses_symlinks_and_copies_regular_listed_files() -> None:
    runner = importlib.import_module("mutation_web")
    assert callable(getattr(runner, "copy_listed_files", None))
    with TemporaryDirectory(prefix="synthetic-copy-guard-") as temporary:
        root = Path(temporary) / "source"
        folder = Path(temporary) / "copy"
        root.mkdir()
        folder.mkdir()
        (root / "regular.txt").write_text("synthetic fixture\n")
        runner.copy_listed_files(root, folder, {"regular.txt", "absent.txt"})
        assert (folder / "regular.txt").read_text() == "synthetic fixture\n"
        assert not (folder / "absent.txt").exists()
        (root / "linked.txt").symlink_to(root / "regular.txt")
        with pytest.raises(
            ValueError, match=r"^Refusing a symlink in the mutation copy: linked\.txt$"
        ):
            runner.copy_listed_files(root, folder, {"linked.txt"})
        assert not (folder / "linked.txt").exists()


def test_web_dependencies_keep_cache_writes_inside_disposable_copy() -> None:
    runner = importlib.import_module("mutation_web")
    assert callable(getattr(runner, "link_dependencies", None))
    with TemporaryDirectory(prefix="synthetic-dependency-cache-") as temporary:
        root = Path(temporary)
        installed = root / "installed"
        (installed / "synthetic-package").mkdir(parents=True)
        (installed / "synthetic-package/index.js").write_text("export default 1;\n")
        (installed / ".vite-temp").mkdir()
        (installed / ".vite-temp/keep").write_text("unchanged\n")
        (installed / ".bin").mkdir()
        (installed / ".package-lock.json").write_text("{}")
        before = {
            str(path.relative_to(installed)): (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in installed.rglob("*")
            if path.is_file()
        }
        folder = root / "copy"
        runner.link_dependencies(folder, installed)
        for relative in ("node_modules", "web/node_modules"):
            modules = folder / relative
            assert modules.is_dir() and not modules.is_symlink()
            assert (modules / "synthetic-package").is_symlink()
            assert (
                modules / "synthetic-package/index.js"
            ).read_text() == "export default 1;\n"
            assert (modules / ".bin").is_symlink()
            assert not (modules / ".package-lock.json").exists()
            assert not (modules / ".vite-temp").exists()
            (modules / ".vite-temp").mkdir()
            (modules / ".vite-temp/new").write_text("local cache\n")
        after = {
            str(path.relative_to(installed)): (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in installed.rglob("*")
            if path.is_file()
        }
        assert after == before


def test_command_copy_excludes_artifacts_and_propagates_failure() -> None:
    """Exercise the real command wrapper with an invented reporter tool."""
    from unittest.mock import patch

    runner = importlib.import_module("mutation_web")
    with TemporaryDirectory(prefix="synthetic-command-isolation-") as temporary:
        root = Path(temporary)
        installed = root / "web/node_modules"
        tool = installed / "@stryker-mutator/core/bin/stryker.js"
        tool.parent.mkdir(parents=True)
        tool.write_text(
            "const fs=require('node:fs');const {spawnSync}=require('node:child_process');"
            "const config=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));"
            "const result=spawnSync('sh',['-c',config.commandRunner.command],{cwd:'sandbox',stdio:'inherit'});"
            "if(result.status!==0)process.exit(result.status??1);"
            "fs.mkdirSync('reports');"
            "fs.writeFileSync('reports/mutation.json',JSON.stringify({files:{'toy.mjs':{mutants:[]}}}));"
        )
        (installed / ".bin").mkdir()
        (installed / ".vite-temp").mkdir()
        (installed / ".vite-temp/keep").write_text("unchanged")
        for expected in (0, 7, 1):
            folder = root / ("case-" + str(expected))
            source = folder / "sandbox"
            (source / "web/dist").mkdir(parents=True)
            (source / "web/dist/stale").write_text("excluded")
            (source / "toy.mjs").write_text("synthetic source")
            (source / "check.cjs").write_text(
                "const fs=require('node:fs');const assert=require('node:assert/strict');"
                "assert.equal(fs.readFileSync('toy.mjs','utf8'),'synthetic source');"
                "assert.ok(!fs.existsSync('web/dist'));"
                "assert.ok(!fs.existsSync('web/node_modules/.vite-temp'));"
                "assert.ok(!fs.lstatSync('web/node_modules').isSymbolicLink());"
                "assert.ok(fs.lstatSync('web/node_modules/.bin').isSymbolicLink());"
                "fs.mkdirSync('web/node_modules/.vite-temp');"
                "fs.writeFileSync('web/node_modules/.vite-temp/new','local');"
                "process.exit(" + str(expected) + ");"
            )
            ledger = folder / "explained.toml"
            ledger.write_text("survivors = []\n")
            runner.link_dependencies(folder, installed)
            (source / "node_modules").symlink_to(folder / "node_modules")
            (source / "web/node_modules").symlink_to(folder / "web/node_modules")
            with patch.object(runner, "ROOT", root):
                code, survivors = runner.run_copy(
                    folder,
                    ["toy.mjs"],
                    "kill -TERM $$" if expected == 1 else "node check.cjs",
                    ledger,
                )
            assert code == expected
            assert not survivors
            assert not (folder / ".command-sandboxes").exists()
            assert not (installed / ".vite-temp/new").exists()
            assert (installed / ".vite-temp/keep").read_text() == "unchanged"
            assert (source / "web/dist/stale").read_text() == "excluded"
