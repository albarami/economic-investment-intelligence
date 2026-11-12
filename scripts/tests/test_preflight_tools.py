"""Deferred preflight tool-row tests (R01-R02)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_proc as proc
import preflight_rows as rows

REPO_ROOT = Path(__file__).resolve().parents[2]


class ToolRows(unittest.TestCase):
    """Adapters over the S0-T11 and S0-T12 checks."""

    def test_toolchain_rows(self) -> None:
        """R01: one full probe is split into the two toolchain rows."""
        components = [
            SimpleNamespace(name=name, kind="toolchain")
            for name in ("python", "uv", "node", "npm")
        ]
        cases = [
            ("all_pass", [], 0, None),
            (
                "python_fail",
                [("toolchain", "python", "running 3.13.1 is outside 3.14.x")],
                0,
                None,
            ),
            (
                "npm_fail",
                [("toolchain", "npm", "running 9.0.0 is outside 10.9.x")],
                0,
                None,
            ),
            ("record_fail", [], 2, None),
            ("raised", [], 0, OSError("planted")),
        ]
        ran: list[str] = []
        for label, failures, record_count, raised in cases:
            with self.subTest(label=label):
                ran.append(label)
                record_failures = [
                    ("record-row", "pins.toml", "planted") for _ in range(record_count)
                ]
                with (
                    mock.patch.object(
                        rows.versions_record,
                        "load_record",
                        return_value=(components, record_failures, len(components)),
                    ),
                    mock.patch.object(
                        rows.versions_tools,
                        "check_toolchain",
                        side_effect=raised,
                        return_value=failures,
                    ) as check,
                ):
                    tools = rows.default_tools(REPO_ROOT, {"PATH": ""}, 0.25)
                    python = tools.python().text()
                    node = tools.node_npm().text()
                if record_count:
                    self.assertEqual(
                        python,
                        "FAIL python: pins.toml cannot be read (2 problems); "
                        "run uv run --locked python scripts/check_versions.py",
                    )
                    self.assertEqual(
                        node,
                        "FAIL node-npm: pins.toml cannot be read (2 problems); "
                        "run uv run --locked python scripts/check_versions.py",
                    )
                    check.assert_not_called()
                elif raised is not None:
                    self.assertEqual(python, "FAIL python: the check raised OSError")
                    self.assertEqual(node, "FAIL node-npm: the check raised OSError")
                    check.assert_called_once()
                else:
                    check.assert_called_once_with(
                        components,
                        sys.version_info[:3],
                        {"PATH": ""},
                        REPO_ROOT,
                        0.25,
                    )
                    if label == "all_pass":
                        self.assertEqual(
                            python,
                            "PASS python: Python and uv match pins.toml",
                        )
                        self.assertEqual(
                            node,
                            "PASS node-npm: Node and npm match pins.toml",
                        )
                    elif label == "python_fail":
                        self.assertEqual(
                            python,
                            "FAIL python: python running 3.13.1 is outside 3.14.x",
                        )
                        self.assertEqual(
                            node,
                            "PASS node-npm: Node and npm match pins.toml",
                        )
                    else:
                        self.assertEqual(
                            python,
                            "PASS python: Python and uv match pins.toml",
                        )
                        self.assertEqual(
                            node,
                            "FAIL node-npm: npm running 9.0.0 is outside 10.9.x",
                        )
        self.assertEqual(ran, [case[0] for case in cases])

    def test_remaining_toolchain_failure_owners(self) -> None:
        """R03: uv/node failures stay local; unknown owners fail both rows."""
        for owner, severities in (
            ("uv", ("FAIL", "PASS")),
            ("node", ("PASS", "FAIL")),
            ("unknown", ("FAIL", "FAIL")),
        ):
            with (
                self.subTest(owner=owner),
                mock.patch.object(
                    rows,
                    "_probe_toolchain",
                    return_value=rows.ToolchainProbe(
                        0, (("toolchain", owner, "planted"),), None
                    ),
                ),
            ):
                tools = rows.default_tools(REPO_ROOT, {"PATH": ""}, 0.25)
                actual = (tools.python(), tools.node_npm())
                self.assertEqual(tuple(line.severity for line in actual), severities)
                for line in actual:
                    if line.severity == "FAIL":
                        self.assertEqual(line.reason, f"{owner} planted")

    def test_sandbox_refusal_and_start_error(self) -> None:
        """R04: an unavailable check fails without reading child streams."""
        for command, check in (
            ("check-extensions", "duckdb-extensions"),
            ("check", "bubblewrap-sandbox"),
        ):
            for label, outcome, error, reason in (
                (
                    "refused",
                    None,
                    proc.CommandRefused("planted"),
                    "the sandbox command was refused",
                ),
                (
                    "start_error",
                    SimpleNamespace(start_error="ENOENT"),
                    None,
                    "the sandbox command could not start (ENOENT)",
                ),
            ):
                with (
                    self.subTest(command=command, label=label),
                    mock.patch.object(
                        proc, "run_child", return_value=outcome, side_effect=error
                    ),
                ):
                    line = rows.sandbox_row(
                        check, command, "passed", REPO_ROOT, {"PATH": ""}, 0.25
                    )
                    self.assertEqual(
                        line.text(),
                        f"FAIL {check}: {reason}; run uv run --locked python "
                        f"scripts/sandbox_check.py {command}",
                    )

    def test_sandbox_rows(self) -> None:
        """R02: bounded sandbox children keep severity and hide output."""
        cases = [
            (
                "extensions_pass",
                "extensions",
                "check-extensions",
                0,
                0.0,
                "PASS duckdb-extensions: spatial and h3 load from the local "
                "folder with network access disabled",
            ),
            (
                "extensions_exit",
                "extensions",
                "check-extensions",
                7,
                0.0,
                "FAIL duckdb-extensions: the sandbox command exited with status 7; "
                "run uv run --locked python scripts/sandbox_check.py check-extensions",
            ),
            (
                "extensions_timeout",
                "extensions",
                "check-extensions",
                0,
                60.0,
                "FAIL duckdb-extensions: the sandbox command timed out after 0.1 s; "
                "run uv run --locked python scripts/sandbox_check.py check-extensions",
            ),
            (
                "bubblewrap_pass",
                "bubblewrap",
                "check",
                0,
                0.0,
                "PASS bubblewrap-sandbox: bubblewrap is present and the sandbox "
                "test passes",
            ),
            (
                "bubblewrap_exit",
                "bubblewrap",
                "check",
                7,
                0.0,
                "FAIL bubblewrap-sandbox: the sandbox command exited with status 7; "
                "run uv run --locked python scripts/sandbox_check.py check",
            ),
            (
                "bubblewrap_timeout",
                "bubblewrap",
                "check",
                0,
                60.0,
                "FAIL bubblewrap-sandbox: the sandbox command timed out after 0.1 s; "
                "run uv run --locked python scripts/sandbox_check.py check",
            ),
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label, owner, command, status, sleep, expected in cases:
                with self.subTest(label=label):
                    ran.append(label)
                    root = base / label
                    scripts = root / "scripts"
                    scripts.mkdir(parents=True)
                    (scripts / "sandbox_check.py").write_text(
                        "import sys\n"
                        "import time\n"
                        "print('hidden out', flush=True)\n"
                        "print('hidden err', file=sys.stderr, flush=True)\n"
                        f"time.sleep({sleep!r})\n"
                        f"raise SystemExit({status})\n",
                        encoding="utf-8",
                    )
                    with mock.patch.object(
                        rows,
                        "_probe_toolchain",
                        return_value=rows.ToolchainProbe(0, (), None),
                    ):
                        tools = rows.default_tools(root, {"PATH": ""}, 0.1)
                        line = (
                            tools.extensions()
                            if owner == "extensions"
                            else tools.bubblewrap()
                        )
                    self.assertTrue(
                        proc.command_allowed(
                            proc.INTERPRETER,
                            (proc.SANDBOX_CHECK, command),
                        )
                    )
                    self.assertEqual(line.text(), expected)
                    self.assertNotIn("hidden out", line.text())
                    self.assertNotIn("hidden err", line.text())
        self.assertEqual(ran, [case[0] for case in cases])


if __name__ == "__main__":
    unittest.main()
