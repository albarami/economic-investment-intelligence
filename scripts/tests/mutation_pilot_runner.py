"""Pinned mutmut integration fixtures; run explicitly with the mutation group."""

import contextlib
import importlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

mutation = importlib.import_module("scripts.mutation")
pilot = importlib.import_module("scripts.mutation_pilot")


class PilotRunnerTests(unittest.TestCase):
    def test_real_discovery_full_partition_and_legacy(self) -> None:
        with TemporaryDirectory(prefix="synthetic-pilot-") as temporary:
            folder = Path(temporary)
            (folder / "src").mkdir()
            (folder / "tests").mkdir()
            (folder / "src/toy.py").write_text("def value():\n    return 2 + 3 + 4\n")
            (folder / "tests/test_toy.py").write_text(
                "from toy import value\ndef test_value():\n    assert value() == 9\n"
            )
            original = '[tool.pytest]\npythonpath=["src"]\n'
            (folder / "pyproject.toml").write_text(original)
            ledger = folder / "ledger.toml"
            ledger.write_text("survivors=[]\n")
            ctx = {
                "commit": "a" * 40,
                "module": pilot.MODULE,
                "hashes": {
                    "source": pilot.digest((folder / "src/toy.py").read_bytes())
                },
            }
            manifest_path = folder / "manifest.json"

            def run(**options: object) -> int:
                code, _ = mutation.run_copy(
                    folder, ["src/toy.py"], ["tests"], ledger, pilot_options=options
                )
                self.assertEqual((folder / "pyproject.toml").read_text(), original)
                self.assertFalse((folder / "mutants").exists())
                self.assertIsInstance(code, int)
                return int(code)

            self.assertEqual(run(context=ctx, list_mutants=manifest_path), 0)
            universe = pilot.read(manifest_path)
            self.assertGreaterEqual(len(universe["mutants"]), 4)
            full = folder / "full.json"
            self.assertEqual(run(context=ctx, report=full), 0)
            parts = []
            for index in range(4):
                target = folder / f"part-{index}.json"
                self.assertEqual(
                    run(
                        context=ctx,
                        mutant_list=manifest_path,
                        shard_index=index,
                        report=target,
                    ),
                    0,
                )
                parts.append(pilot.read(target))
            merged = pilot.merge(universe, parts, ["success"] * 4)
            self.assertEqual(pilot.compare(pilot.read(full), merged), [])
            # The old path's command and stable output match the immutable base source.
            import subprocess
            import types

            base = subprocess.run(
                [
                    "git",
                    "show",
                    "c45f338c23dd96f16e603cd55238127c8048aff3:scripts/mutation.py",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            old = types.ModuleType("legacy_mutation_fixture")
            old.__file__ = mutation.__file__
            exec(compile(base, "legacy_mutation_fixture", "exec"), old.__dict__)
            outputs = []
            calls = []
            for runner in (old, mutation):
                output = io.StringIO()
                real = runner.command
                observed: list[Any] = []

                def command(
                    *args: Any,
                    _observed: list[Any] = observed,
                    _real: Any = real,
                    **kwargs: Any,
                ) -> Any:
                    _observed.append((args[1:], kwargs))
                    return _real(*args, **kwargs)

                with (
                    patch.object(runner, "command", side_effect=command),
                    patch.object(runner, "perf_counter", return_value=0),
                    contextlib.redirect_stdout(output),
                ):
                    code, survivors = runner.run_copy(
                        folder, ["src/toy.py"], ["tests"], ledger
                    )
                self.assertEqual(code, 0)
                self.assertEqual(survivors, [])
                # Tool progress has timings; compare the runner-owned output verbatim.
                outputs.append(
                    [
                        line
                        for line in output.getvalue().splitlines()
                        if line.startswith(("mutmut exit=", "src/toy.py:"))
                    ]
                )
                calls.append(observed)
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(calls[0], calls[1])

    def test_baseline_failure_exports_and_propagates(self) -> None:
        with TemporaryDirectory(prefix="synthetic-pilot-baseline-") as temporary:
            folder = Path(temporary)
            (folder / "src").mkdir()
            (folder / "tests").mkdir()
            (folder / "src/toy.py").write_text("def value():\n    return 2\n")
            (folder / "tests/test_toy.py").write_text(
                "def test_failure():\n    assert False\n"
            )
            (folder / "pyproject.toml").write_text(
                '[tool.pytest]\npythonpath=["src"]\n'
            )
            ledger = folder / "ledger.toml"
            ledger.write_text("survivors=[]\n")
            target = folder / "result.json"
            code, _ = mutation.run_copy(
                folder,
                ["src/toy.py"],
                ["tests"],
                ledger,
                pilot_options={
                    "context": {
                        "commit": "a" * 40,
                        "module": pilot.MODULE,
                        "hashes": {},
                    },
                    "report": target,
                },
            )
            self.assertNotEqual(code, 0)
            result = json.loads(target.read_text())
            self.assertEqual(result["command_exit"], code)
            self.assertFalse((folder / "mutants").exists())

    def test_report_preserves_unexplained_survivors(self) -> None:
        with TemporaryDirectory(prefix="synthetic-pilot-survivor-") as temporary:
            folder = Path(temporary)
            (folder / "src").mkdir()
            (folder / "tests").mkdir()
            (folder / "src/toy.py").write_text("def value():\n    return 2\n")
            (folder / "tests/test_toy.py").write_text(
                "from toy import value\ndef test_value():\n    assert value() > 0\n"
            )
            (folder / "pyproject.toml").write_text(
                '[tool.pytest]\npythonpath=["src"]\n'
            )
            ledger = folder / "ledger.toml"
            ledger.write_text("survivors=[]\n")
            target = folder / "result.json"
            code, survivors = mutation.run_copy(
                folder,
                ["src/toy.py"],
                ["tests"],
                ledger,
                pilot_options={
                    "context": {
                        "commit": "a" * 40,
                        "module": pilot.MODULE,
                        "hashes": {},
                    },
                    "report": target,
                },
            )
            self.assertEqual(code, 1)
            self.assertEqual(len(survivors), 1)
            result = pilot.read(target)
            self.assertEqual(result["counts"]["survived"], 1)
            self.assertEqual(result["records"][0]["raw_exit"], 0)
            self.assertEqual(result["records"][0]["mutation"], survivors[0]["mutation"])
            self.assertEqual(
                set(result["timing"]["qualification"]),
                {"stats_seconds", "forced_fail_seconds", "clean_tests_seconds"},
            )
            self.assertFalse((folder / "mutants").exists())

    def test_nonzero_generation_exit_is_exact(self) -> None:
        import subprocess

        with TemporaryDirectory(prefix="synthetic-pilot-command-") as temporary:
            folder = Path(temporary)
            (folder / "pyproject.toml").write_text("")
            report = folder / "result.json"
            with patch.object(
                mutation.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 7, "", ""),
            ):
                code, _ = mutation.run_copy(
                    folder,
                    ["src/toy.py"],
                    ["tests"],
                    folder / "ledger.toml",
                    pilot_options={"report": report},
                )
            self.assertEqual(code, 7)
            self.assertEqual(pilot.read(report)["command_exit"], 7)
            self.assertEqual((folder / "pyproject.toml").read_text(), "")

    def test_legacy_bytes_with_fixed_tool_output(self) -> None:
        import subprocess
        import types

        base = subprocess.run(
            [
                "git",
                "show",
                "c45f338c23dd96f16e603cd55238127c8048aff3:scripts/mutation.py",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        old = types.ModuleType("legacy_mutation_fixture")
        old.__file__ = mutation.__file__
        exec(compile(base, "legacy_mutation_fixture", "exec"), old.__dict__)
        with TemporaryDirectory(prefix="synthetic-pilot-legacy-") as temporary:
            folder = Path(temporary)
            (folder / "pyproject.toml").write_text("")
            ledger = folder / "ledger.toml"
            ledger.write_text("survivors=[]\n")
            snapshots = []
            for runner in (old, mutation):
                out, err = io.StringIO(), io.StringIO()
                calls: list[Any] = []

                def fixed_command(
                    work: Path, *args: str, _calls: list[Any] = calls, **kwargs: Any
                ) -> Any:
                    _calls.append((args, kwargs))
                    (work / "mutants/src").mkdir(parents=True, exist_ok=True)
                    (work / "mutants/src/toy.py.meta").write_text(
                        json.dumps({"exit_code_by_key": {"toy.x_value__mutmut_1": 0}})
                    )
                    if args[0] == "show":
                        return subprocess.CompletedProcess(
                            args,
                            0,
                            "mutant heading\n--- src/toy.py\n+++ src/toy.py\n@@ -1 +1 @@\n-2\n+3\n",
                            "",
                        )
                    return subprocess.CompletedProcess(
                        args, 0, "fixed tool output\n", "fixed tool diagnostic\n"
                    )

                with (
                    patch.object(runner, "command", side_effect=fixed_command),
                    patch.object(runner, "perf_counter", return_value=0),
                    contextlib.redirect_stdout(out),
                    contextlib.redirect_stderr(err),
                ):
                    result = runner.run_copy(folder, ["src/toy.py"], ["tests"], ledger)
                snapshots.append((calls, out.getvalue(), err.getvalue(), result))
            self.assertEqual(snapshots[0], snapshots[1])

    def test_nonzero_diff_export_is_exact_and_recorded(self) -> None:
        import subprocess

        with TemporaryDirectory(prefix="synthetic-pilot-diff-") as temporary:
            folder = Path(temporary)
            (folder / "pyproject.toml").write_text("")
            (folder / "mutants/src").mkdir(parents=True)
            (folder / "mutants/src/toy.py.meta").write_text(
                json.dumps({"exit_code_by_key": {"toy.x_value__mutmut_1": None}})
            )
            report = folder / "result.json"
            with (
                patch.object(
                    mutation.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, "", ""),
                ),
                patch.object(
                    mutation,
                    "command",
                    return_value=subprocess.CompletedProcess([], 7, "", ""),
                ),
            ):
                code, _ = mutation.run_copy(
                    folder,
                    ["src/toy.py"],
                    ["tests"],
                    folder / "ledger.toml",
                    pilot_options={"report": report},
                )
            self.assertEqual(code, 7)
            self.assertEqual(pilot.read(report)["command_exit"], 7)
            self.assertEqual(pilot.read(report)["incidents"], ["diff-export-failed"])
            self.assertFalse((folder / "mutants").exists())
