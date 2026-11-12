"""Toolchain probes, command line and read-only behaviour."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base


class ToolchainRules(unittest.TestCase):
    def test_python_series(self) -> None:
        passing = ((3, 14, 0), (3, 14, 6))
        for interpreter in passing:
            with self.subTest(interpreter=interpreter):
                root, path = base.ready(self)
                self.assertEqual(
                    base.run(root, interpreter=interpreter, path=path),
                    [base.SUMMARY_OK],
                )
        failing = ((3, 13, 9), (3, 15, 0), (3, 1, 4), (2, 7, 18), (3, 140, 0))
        for interpreter in failing:
            with self.subTest(interpreter=interpreter):
                root, path = base.ready(self)
                text = ".".join(str(part) for part in interpreter)
                self.assertEqual(
                    base.run(root, interpreter=interpreter, path=path),
                    [
                        f"FAIL toolchain: python: running {text} is outside 3.14.x",
                        base.summary(1),
                    ],
                )

    def test_uv_exact(self) -> None:
        for text in ("uv 0.11.31 (x86_64-unknown-linux-gnu)", "uv 0.11.31"):
            with self.subTest(text=text):
                root, path = self._tools(uv=text)
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        for text in ("uv 0.11.32", "uv 0.11.30", "uv 0.11.3", "uv 10.11.31"):
            with self.subTest(text=text):
                root, path = self._tools(uv=text)
                version = text.removeprefix("uv ")
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL toolchain: uv: running {version} is outside 0.11.31",
                        base.summary(1),
                    ],
                )

    def test_node_series_and_floor(self) -> None:
        for text in ("v22.22.3", "v22.12.0", "v22.100.0"):
            with self.subTest(text=text):
                root, path = self._tools(node=text)
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        floor = ("v22.11.9", "v22.9.0")
        for text in floor:
            version = text[1:]
            with self.subTest(text=text):
                root, path = self._tools(node=text)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL toolchain: node: "
                        f"running {version} is below the floor 22.12.0",
                        base.summary(1),
                    ],
                )
        outside = ("v23.0.0", "v20.19.0", "v220.1.0")
        for text in outside:
            version = text[1:]
            with self.subTest(text=text):
                root, path = self._tools(node=text)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL toolchain: node: running {version} is outside 22.x",
                        base.summary(1),
                    ],
                )
        for text in ("22.22.3", "v22"):
            with self.subTest(text=text):
                root, path = self._tools(node=text)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL toolchain: node: version output not understood",
                        base.summary(1),
                    ],
                )

    def test_npm_series(self) -> None:
        for text in ("10.9.8", "10.9.0"):
            with self.subTest(text=text):
                root, path = self._tools(npm=text)
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        for text in ("10.8.2", "11.0.0", "10.90.0"):
            with self.subTest(text=text):
                root, path = self._tools(npm=text)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL toolchain: npm: running {text} is outside 10.9.x",
                        base.summary(1),
                    ],
                )
        root, path = self._tools(npm="v10.9.8")
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: npm: version output not understood", base.summary(1)],
        )

    def test_failures_come_in_tool_order(self) -> None:
        root, path = self._tools(uv="uv 0.11.32", node="v20.0.0", npm="11.0.0")
        self.assertEqual(
            base.run(root, interpreter=(3, 13, 9), path=path),
            [
                "FAIL toolchain: python: running 3.13.9 is outside 3.14.x",
                "FAIL toolchain: uv: running 0.11.32 is outside 0.11.31",
                "FAIL toolchain: node: running 20.0.0 is outside 22.x",
                "FAIL toolchain: npm: running 11.0.0 is outside 10.9.x",
                base.summary(4),
            ],
        )

    def test_probe_failures_are_reported(self) -> None:
        root, path = base.ready(self)
        bindir = Path(path)
        for name in ("uv", "node", "npm"):
            (bindir / name).unlink()
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL toolchain: uv: not found on PATH",
                "FAIL toolchain: node: not found on PATH",
                "FAIL toolchain: npm: not found on PATH",
                base.summary(3),
            ],
        )
        root, path = self._tools()
        base.make_tool(Path(path), "uv", "exit 1\n")
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: uv: exit status 1", base.summary(1)],
        )
        root, path = self._tools()
        base.make_tool(Path(path), "node", "/bin/sleep 30\n")
        lines, _count = __import__("check_versions").run_checks(
            root,
            interpreter=base.GOOD_INTERPRETER,
            environ={"PATH": path},
            probe_timeout=0.5,
        )
        self.assertEqual(
            lines,
            ["FAIL toolchain: node: timed out after 0.5 s", base.summary(1)],
        )
        root, path = self._tools()
        stub = Path(path) / "npm"
        stub.write_text("#!/bin/sh\nprintf '%s\\n' '10.9.8'\n", encoding="utf-8")
        stub.chmod(0o644)
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: npm: not found on PATH", base.summary(1)],
        )
        root, path = self._tools()
        base.make_tool(Path(path), "uv", "#!/no/such/interpreter\nexit 0\n")
        # make_tool already wrote a shebang; replace the whole file.
        target = Path(path) / "uv"
        target.write_text("#!/no/such/interpreter\nexit 0\n", encoding="utf-8")
        target.chmod(0o755)
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: uv: could not run (FileNotFoundError)", base.summary(1)],
        )

    def test_probe_garbage_does_not_crash(self) -> None:
        root, path = self._tools()
        (Path(path) / "uv").write_bytes(
            b"#!/bin/sh\nprintf '\\377\\376 long'\nexit 0\n"
        )
        (Path(path) / "uv").chmod(0o755)
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: uv: version output not understood", base.summary(1)],
        )
        root, path = self._tools()
        base.make_tool(Path(path), "node", "printf '%s\\n' '" + ("n" * 1000000) + "'\n")
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: node: version output not understood", base.summary(1)],
        )
        root, path = self._tools()
        base.make_tool(Path(path), "npm", "exit 0\n")
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL toolchain: npm: version output not understood", base.summary(1)],
        )

    def test_cli_exit_codes_and_usage(self) -> None:
        root, path = base.ready(self)
        proc = base.cli(["--root", str(root)], {"PATH": path})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [base.SUMMARY_OK])
        self.assertEqual(proc.stderr, "")
        base.write(root, ".nvmrc", "20\n")
        proc = base.cli(["--root", str(root)], {"PATH": path})
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stdout.splitlines()[0].startswith("FAIL "))
        self.assertEqual(proc.stderr, "")
        usage = (
            (["--bogus"], 'unknown argument "--bogus"'),
            (["--root"], "--root needs a value"),
            (["--root", "a", "--root", "b"], "--root given twice"),
            (["--root=DIR"], 'unknown argument "--root=DIR"'),
            (["DIR"], 'unknown argument "DIR"'),
        )
        for args, detail in usage:
            with self.subTest(args=args):
                proc = base.cli(args, {"PATH": path})
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(
                    proc.stderr, f"check_versions: usage error: {detail}\n"
                )
        file_path = root / "pins.toml"
        proc = base.cli(["--root", str(file_path)], {"PATH": path})
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(
            proc.stderr, "check_versions: usage error: root is not a directory\n"
        )

    def test_internal_error_is_reported(self) -> None:
        root, path = base.ready(self)
        out = __import__("io").StringIO()
        err = __import__("io").StringIO()
        with patch("versions_tools.check_toolchain", side_effect=RuntimeError("boom")):
            code = base.check_versions.main(
                ["--root", str(root)],
                out=out,
                err=err,
                environ={"PATH": path},
            )
        self.assertEqual(code, 1)
        self.assertEqual(
            out.getvalue(),
            "FAIL internal-error: check_versions: RuntimeError: boom\n",
        )
        self.assertEqual(err.getvalue(), "")

    def _tools(
        self,
        *,
        uv: str | None = None,
        node: str | None = None,
        npm: str | None = None,
    ) -> tuple[Path, str]:
        root, path = base.ready(self)
        base.make_tools(
            Path(path),
            uv=uv if uv is not None else "uv 0.11.31 (x86_64-unknown-linux-gnu)",
            node=node if node is not None else "v22.22.3",
            npm=npm if npm is not None else "10.9.8",
        )
        return root, path


class Surroundings(unittest.TestCase):
    def test_hostile_surroundings_do_not_change_the_result(self) -> None:
        root, path = base.ready(self)
        bindir = Path(path)
        base.make_tool(
            bindir,
            "npm",
            "if [ -n \"$NODE_OPTIONS\" ]; then exit 1; fi\nprintf '%s\\n' '10.9.8'\n",
        )
        base.make_tool(
            bindir,
            "uv",
            'if [ "$UV_NO_CONFIG" = "1" ]; then\n'
            "  printf '%s\\n' 'uv 0.11.31 (x86_64-unknown-linux-gnu)'\n"
            "else\n"
            "  printf '%s\\n' 'uv 9.9.9'\n"
            "fi\n",
        )
        hostile = {
            "PATH": path,
            "NODE_OPTIONS": "--require=missing.js",
            "PYTHONPATH": "elsewhere",
            "UV_CONFIG_FILE": "elsewhere",
            "HOME": str(root / "home"),
            "npm_config_userconfig": "elsewhere",
        }
        proc = base.cli(["--root", str(root)], hostile)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [base.SUMMARY_OK])
        tooth_npm = __import__("subprocess").run(
            [str(bindir / "npm"), "--version"],
            capture_output=True,
            text=True,
            env=hostile,
            check=False,
        )
        self.assertEqual(tooth_npm.returncode, 1)
        tooth_uv = __import__("subprocess").run(
            [str(bindir / "uv"), "--version"],
            capture_output=True,
            text=True,
            env={"PATH": path},
            check=False,
        )
        self.assertEqual(tooth_uv.stdout.strip(), "uv 9.9.9")

    def test_probe_environment_is_the_allow_list(self) -> None:
        root, path = base.ready(self)
        bindir = Path(path)
        folder = Path(path).parent
        for name in ("uv", "node", "npm"):
            base.make_tool(
                bindir,
                name,
                "/usr/bin/env | /usr/bin/sort > '"
                + str(folder / (name + ".env"))
                + "'\n"
                + {
                    "uv": "printf '%s\\n' 'uv 0.11.31'\n",
                    "node": "printf '%s\\n' 'v22.22.3'\n",
                    "npm": "printf '%s\\n' '10.9.8'\n",
                }[name],
            )
        lines, _count = base.check_versions.run_checks(
            root,
            interpreter=base.GOOD_INTERPRETER,
            environ={
                "PATH": path,
                "NODE_OPTIONS": "--require=missing.js",
                "HOME": "home",
                "npm_config_userconfig": "elsewhere",
            },
        )
        self.assertEqual(lines, [base.SUMMARY_OK])
        for name in ("uv", "node", "npm"):
            env_path = folder / (name + ".env")
            self.assertTrue(env_path.is_file(), name)
            keys = _env_keys(env_path.read_text(encoding="utf-8"))
            self.assertEqual(keys, {"LANG", "PATH", "UV_NO_CONFIG"})

    def test_check_only_reads(self) -> None:
        root, path = base.ready(self)
        before = base.tree_digest(root)
        base.run(root, path=path)
        self.assertEqual(base.tree_digest(root), before)
        proc = base.cli(["--root", str(root)], {"PATH": path})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(base.tree_digest(root), before)
        base.write(root, ".nvmrc", "20\n")
        failing = base.tree_digest(root)
        base.run(root, path=path)
        self.assertEqual(base.tree_digest(root), failing)
        proc = base.cli(["--root", str(root)], {"PATH": path})
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(base.tree_digest(root), failing)


def _env_keys(text: str) -> set[str]:
    keys = set()
    for line in text.splitlines():
        key = line.split("=", 1)[0]
        if key not in base.SHELL_ENV_KEYS:
            keys.add(key)
    return keys
