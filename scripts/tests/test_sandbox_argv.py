"""Argument-list rules for the two sandbox profiles. No sandbox is started."""

from __future__ import annotations

import errno
import io
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_golden as golden
import sandbox_support as support

import extension_tree
import sandbox_check
import sandbox_launch as launch
import sandbox_profiles as tables

FORBIDDEN = (
    "--share-net",
    "--cap-add",
    "--dev-bind",
    "--dev-bind-try",
    "--bind",
    "--ro-bind",
    "--bind-try",
    "--ro-bind-try",
    "--userns",
    "--userns2",
    "--proc",
    "--unshare-all",
    "--uid",
    "--gid",
)
HIDDEN_ROOTS = ("/etc", "/home", "/proc", "/sys", "/run", "/var", "/root")
CODE = Path("/w/repo")
REAL = Path("/w/py/cpython-3.14.6-linux-x86_64-gnu")
ALIAS = Path("/w/py/cpython-3.14-linux-x86_64-gnu")
VENV = CODE / ".venv"
EXTENSIONS = CODE / "data" / "engine_extensions"
COMMAND = [
    str(VENV / "bin" / "python"),
    "-I",
    "-B",
    str(CODE / "scripts" / "sandbox_inside" / "sentinel_probe.py"),
]


def contains_forbidden(text: str) -> list[str]:
    """Return forbidden options that appear quoted in a source text."""
    return [option for option in FORBIDDEN if f'"{option}"' in text]


def golden_layout(
    profile_name: str,
) -> tuple[tables.Profile, launch.Layout, launch.Interpreter, dict[Path, int]]:
    """Return the fake layout of the golden lists and its descriptors."""
    scenario = Path("/w/scenario.bin")
    staging = CODE / "data" / "releases" / ".staging" / "b1"
    layout = launch.Layout(
        CODE,
        CODE / "data" / "public_cache",
        CODE / "data" / "vault" / "b1",
        EXTENSIONS,
        staging if profile_name == "build-release" else None,
        scenario if profile_name == "build-world" else None,
    )
    interpreter = launch.Interpreter(VENV, REAL, ALIAS)
    profile = launch.profile_named(profile_name)
    paths = launch.bound_paths(profile, layout, interpreter)
    descriptors = {path: 10 + index for index, path in enumerate(paths)}
    return profile, layout, interpreter, descriptors


class _Process:
    """A stand-in for the process ``Popen`` returns."""

    def __init__(self, communicate: object, returncode: int = 0) -> None:
        self.pid = 4242
        self.returncode = returncode
        self.communicate = communicate


class ArgvRules(unittest.TestCase):
    def test_two_profiles_exactly(self) -> None:
        self.assertEqual(
            [item.name for item in tables.PROFILES], ["build-world", "build-release"]
        )
        self.assertEqual(
            [(item.staging, item.scenario) for item in tables.PROFILES],
            [(False, True), (True, False)],
        )
        self.assertIs(launch.profile_named("build-release"), tables.PROFILES[1])
        with self.assertRaises(launch.SandboxError) as caught:
            launch.profile_named("build-x")
        self.assertEqual(str(caught.exception), "unknown profile: build-x")

    def test_golden_command_line_build_world(self) -> None:
        profile, layout, interpreter, descriptors = golden_layout("build-world")
        argv = launch.build_argv(profile, layout, interpreter, COMMAND, descriptors)
        self.assertEqual(argv, golden.GOLDEN_WORLD)
        self.assertEqual(len(argv), 90)

    def test_golden_command_line_build_release(self) -> None:
        profile, layout, interpreter, descriptors = golden_layout("build-release")
        argv = launch.build_argv(profile, layout, interpreter, COMMAND, descriptors)
        self.assertEqual(argv, golden.GOLDEN_RELEASE)
        self.assertEqual(len(argv), 90)

    def test_forbidden_options_never_appear(self) -> None:
        lists = [golden.GOLDEN_WORLD, golden.GOLDEN_RELEASE]
        for argv in lists:
            for option in FORBIDDEN:
                self.assertNotIn(option, argv)
            for token in argv:
                self.assertFalse(token.startswith(HIDDEN_ROOTS))
        launch_text = (support.ROOT / "scripts" / "sandbox_launch.py").read_text(
            encoding="utf-8"
        )
        profiles_text = (support.ROOT / "scripts" / "sandbox_profiles.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(contains_forbidden(launch_text), [])
        self.assertEqual(contains_forbidden(profiles_text), [])
        self.assertEqual(
            contains_forbidden(profiles_text + '"--share-net",'), ["--share-net"]
        )
        self.assertEqual(contains_forbidden(launch_text + '"--cap-add"'), ["--cap-add"])

    def test_mount_destinations_are_the_closed_list(self) -> None:
        world = self._operations(golden.GOLDEN_WORLD)
        release = self._operations(golden.GOLDEN_RELEASE)
        files = [
            str(EXTENSIONS / "v2.0.0" / "linux_amd64" / name)
            for name in (
                "h3.duckdb_extension",
                "h3.duckdb_extension.info",
                "spatial.duckdb_extension",
                "spatial.duckdb_extension.info",
            )
        ]
        common = [
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib64",
            str(REAL),
            str(VENV),
            str(CODE / "core" / "src"),
            str(CODE / "custodian" / "src"),
            str(CODE / "scripts" / "sandbox_inside"),
            str(CODE / "data" / "public_cache"),
            *files,
        ]
        self.assertEqual(world["--ro-bind-fd"], [*common, "/scenario/scenario.bin"])
        self.assertEqual(release["--ro-bind-fd"], common)
        self.assertEqual(world["--bind-fd"], [str(CODE / "data" / "vault" / "b1")])
        self.assertEqual(
            release["--bind-fd"],
            [
                str(CODE / "data" / "vault" / "b1"),
                str(CODE / "data" / "releases" / ".staging" / "b1"),
            ],
        )
        inner = [
            str(EXTENSIONS / "v2.0.0"),
            str(EXTENSIONS / "v2.0.0" / "linux_amd64"),
        ]
        extension = str(EXTENSIONS)
        for operations, argv in (
            (world, golden.GOLDEN_WORLD),
            (release, golden.GOLDEN_RELEASE),
        ):
            self.assertEqual(operations["--dir"], inner)
            cache = argv.index(str(CODE / "data" / "public_cache"))
            first_file = argv.index(files[0])
            last_file = argv.index(files[-1])
            mount = argv.index(extension)
            seal = argv.index(extension, mount + 1)
            self.assertLess(mount, first_file)
            self.assertGreater(mount, cache)
            self.assertGreater(seal, last_file)
            self.assertNotIn(extension, operations["--ro-bind-fd"])
            self.assertNotIn(extension, operations["--bind-fd"])
            numbers = [
                argv[index + 1]
                for index, token in enumerate(argv)
                if token in {"--ro-bind-fd", "--bind-fd"}
            ]
            self.assertEqual(len(numbers), 14)
            self.assertEqual(len(set(numbers)), 14)
            self.assertTrue(all(token.isdecimal() for token in numbers))
            self.assertEqual(set(operations["--symlink"]), {"/lib64", str(ALIAS)})
            self.assertEqual(operations["--tmpfs"], ["/tmp", extension])
            self.assertEqual(operations["--dev"], ["/dev"])
            self.assertEqual(operations["--remount-ro"], [extension, "/"])
            self.assertEqual(operations["--chdir"], ["/tmp"])
            names = {token for token in argv if token.startswith("--")}
            self.assertEqual(
                names,
                {
                    *tables.ISOLATION,
                    "--setenv",
                    "--ro-bind-fd",
                    "--bind-fd",
                    "--dir",
                    "--symlink",
                    "--tmpfs",
                    "--dev",
                    "--remount-ro",
                    "--chdir",
                },
            )

    def test_scenario_and_staging_belong_to_one_profile(self) -> None:
        self.assertIn("/scenario/scenario.bin", golden.GOLDEN_WORLD)
        self.assertNotIn(
            str(CODE / "data" / "releases" / ".staging" / "b1"), golden.GOLDEN_WORLD
        )
        self.assertIn(
            str(CODE / "data" / "releases" / ".staging" / "b1"), golden.GOLDEN_RELEASE
        )
        self.assertNotIn("/scenario/scenario.bin", golden.GOLDEN_RELEASE)
        world, layout, interpreter, descriptors = golden_layout("build-world")
        release, release_layout, _, release_descriptors = golden_layout("build-release")
        both = launch.Layout(
            CODE,
            layout.cache,
            layout.vault,
            EXTENSIONS,
            release_layout.staging,
            layout.scenario,
        )
        neither = launch.Layout(CODE, layout.cache, layout.vault, EXTENSIONS)
        cases = [
            (world, neither, "profile build-world needs a scenario file"),
            (release, both, "profile build-release takes no scenario file"),
            (world, both, "profile build-world takes no staging folder"),
            (release, neither, "profile build-release needs a staging folder"),
            (
                tables.Profile("x", staging=False, scenario=False),
                both,
                "profile x takes no staging folder",
            ),
        ]
        labels = []
        for index, (profile, chosen, message) in enumerate(cases, start=1):
            labels.append(index)
            with self.assertRaises(launch.SandboxError) as caught:
                launch.build_argv(
                    profile,
                    chosen,
                    interpreter,
                    COMMAND,
                    descriptors or release_descriptors,
                )
            self.assertEqual(str(caught.exception), message)
        self.assertEqual(labels, [1, 2, 3, 4, 5])

    def test_environment_is_set_after_clearenv(self) -> None:
        for name, argv in (
            ("build-world", golden.GOLDEN_WORLD),
            ("build-release", golden.GOLDEN_RELEASE),
        ):
            clear = argv.index("--clearenv")
            pairs = []
            index = 0
            while index < len(argv):
                if argv[index] == "--setenv":
                    self.assertLess(clear, index)
                    pairs.append((argv[index + 1], argv[index + 2]))
                    index += 3
                    continue
                index += 1
            self.assertEqual(
                pairs,
                [
                    ("HOME", "/tmp"),
                    ("PYTHONDONTWRITEBYTECODE", "1"),
                    ("PATH", "/w/repo/.venv/bin"),
                    ("EII_SANDBOX_PROFILE", name),
                ],
            )
        self.assertEqual(
            tables.CHILD_ENVIRONMENT_NAMES,
            ("HOME", "PATH", "PWD", "PYTHONDONTWRITEBYTECODE", "EII_SANDBOX_PROFILE"),
        )

    def test_open_sources_cases(self) -> None:
        labels = []
        with tempfile_tree() as tree:
            labels.append(1)
            opened = tree.open("build-world")
            self.assertEqual(list(opened), tree.bound("build-world"))
            self._descriptors_name_keys(opened)
            launch.close_all(opened)
            labels.append(2)
            opened = tree.open("build-release")
            self.assertEqual(list(opened), tree.bound("build-release"))
            self._descriptors_name_keys(opened)
            launch.close_all(opened)
        refusals = [
            (3, "world-staging", "profile build-world takes no staging folder"),
            (4, "release-no-staging", "profile build-release needs a staging folder"),
            (5, "release-scenario", "profile build-release takes no scenario file"),
            (6, "world-no-scenario", "profile build-world needs a scenario file"),
            (7, "relative-cache", "mount source is not absolute: data/public_cache"),
            (
                8,
                "cache-missing",
                "mount source is missing or of the wrong kind: {cache}",
            ),
            (9, "cache-file", "mount source is missing or of the wrong kind: {cache}"),
            (
                10,
                "vault-link",
                "mount source is or lies below a symbolic link: {vault}",
            ),
            (
                11,
                "scenario-dir",
                "mount source is missing or of the wrong kind: {scenario}",
            ),
            (
                12,
                "extensions-equal-cache",
                "mount sources overlap: {cache} and {cache}",
            ),
            (
                13,
                "vault-inside-cache",
                "mount sources overlap: {cache} and {cache}/vault",
            ),
            (
                14,
                "cache-inside-vault",
                "mount sources overlap: {vault}/cache and {vault}",
            ),
            (
                15,
                "core-missing",
                "mount source is missing or of the wrong kind: {core}",
            ),
            (
                16,
                "inside-link",
                "mount source is or lies below a symbolic link: {inside}",
            ),
            (
                17,
                "vault-through-link",
                "mount source is or lies below a symbolic link: {linked}",
            ),
            (
                18,
                "core-through-link",
                "mount source is or lies below a symbolic link: {core}",
            ),
            (
                19,
                "vault-dangling",
                "mount source is or lies below a symbolic link: {vault}",
            ),
            (
                20,
                "cache-mode",
                "mount source cannot be opened: {cache} (PermissionError)",
            ),
            (
                23,
                "scenario-nlink",
                "mount source has 2 hard links, expected 1: {scenario}",
            ),
            (
                24,
                "venv-link",
                "mount source is or lies below a symbolic link: {venvlink}",
            ),
            (
                25,
                "scenario-link",
                "mount source is or lies below a symbolic link: {scenario}",
            ),
        ]
        pending = {number: (kind, message) for number, kind, message in refusals}
        for number in range(3, 26):
            labels.append(number)
            with tempfile_tree() as tree:
                before = support.descriptor_snapshot()
                with self.assertRaises(launch.SandboxError) as caught:
                    if number == 21:
                        with patch.object(launch, "FIRST_FREE_DESCRIPTOR", 10**6):
                            tree.open("build-world")
                    elif number == 22:
                        real = os.readlink

                        def broken(
                            path: str | Path,
                            *args: object,
                            readlink: Callable[[str | Path], str] = real,
                        ) -> str:
                            if str(path).startswith("/proc/self/fd/"):
                                raise FileNotFoundError(path)
                            return readlink(path)

                        with patch.object(
                            support.exposed(launch, "os"), "readlink", broken
                        ):
                            tree.open("build-world")
                    else:
                        kind, _message = pending[number]
                        tree.refuse(kind)
                if number == 21:
                    self.assertRegex(
                        str(caught.exception),
                        r"mount source /usr/lib/x86_64-linux-gnu was opened as descriptor [0-9]+, "
                        r"a standard stream: start the launcher with standard input, output and error open",
                    )
                elif number == 22:
                    self.assertEqual(
                        str(caught.exception),
                        "mount source cannot be checked: /usr/lib/x86_64-linux-gnu (FileNotFoundError)",
                    )
                else:
                    _kind, message = pending[number]
                    self.assertEqual(str(caught.exception), tree.message(message))
                self.assertEqual(support.descriptor_snapshot(), before)
        self.assertEqual(labels, list(range(1, 26)))

    def test_interpreter_for_cases(self) -> None:
        labels = []
        with tempfile_tree() as tree:
            labels.append("a")
            found = launch.interpreter_for(tree.venv)
            self.assertEqual(
                found, launch.Interpreter(tree.venv, tree.real, tree.alias)
            )
            labels.append("b")
            straight = tree.base / "straight"
            (straight / "bin").mkdir(parents=True)
            os.symlink(tree.real / "bin" / "python3.14", straight / "bin" / "python")
            self.assertEqual(
                launch.interpreter_for(straight),
                launch.Interpreter(straight, tree.real, None),
            )
            labels.append("c")
            plain = tree.base / "plain"
            (plain / "bin").mkdir(parents=True)
            (plain / "bin" / "python").write_text("", encoding="utf-8")
            with self.assertRaises(launch.SandboxError) as caught:
                launch.interpreter_for(plain)
            self.assertEqual(
                str(caught.exception),
                f"{plain / 'bin' / 'python'} is not a link to a uv-managed interpreter",
            )
            labels.append("d")
            relative = tree.base / "relative"
            (relative / "bin").mkdir(parents=True)
            os.symlink("python3.14", relative / "bin" / "python")
            with self.assertRaises(launch.SandboxError) as caught:
                launch.interpreter_for(relative)
            self.assertEqual(
                str(caught.exception),
                f"{relative / 'bin' / 'python'} does not link to an absolute .../bin/ path",
            )
            labels.append("e")
            odd = tree.base / "odd"
            (odd / "bin").mkdir(parents=True)
            os.symlink("/tmp/python3.14", odd / "bin" / "python")
            with self.assertRaises(launch.SandboxError) as caught:
                launch.interpreter_for(odd)
            self.assertEqual(
                str(caught.exception),
                f"{odd / 'bin' / 'python'} does not link to an absolute .../bin/ path",
            )
            labels.append("f")
            with (
                patch.object(
                    support.exposed(launch, "os").path,
                    "realpath",
                    return_value="/usr/local/py",
                ),
                self.assertRaises(launch.SandboxError) as caught,
            ):
                launch.interpreter_for(tree.venv)
            self.assertEqual(
                str(caught.exception),
                "the interpreter /usr/local/py is not uv-managed: create the environment "
                "with 'uv sync --managed-python --all-packages --locked --group engine'",
            )
        self.assertEqual(labels, ["a", "b", "c", "d", "e", "f"])

    def test_current_venv_refuses_outside_an_environment(self) -> None:
        with patch.object(sys, "prefix", sys.base_prefix):
            with self.assertRaises(launch.SandboxError) as caught:
                launch.current_venv()
        self.assertEqual(
            str(caught.exception),
            "not running in the project environment: use 'uv run --locked' after "
            "'uv sync --managed-python --all-packages --locked --group engine'",
        )
        original = Path(os.path.abspath(sys.prefix))
        self.assertEqual(launch.current_venv(), original)
        with patch.object(sys, "prefix", str(original / "bin" / "..")):
            self.assertEqual(launch.current_venv(), original)

    def test_run_starts_bubblewrap_with_nothing_inherited(self) -> None:
        seen: dict[str, object] = {}

        def recorder(argv: list[str], **kwargs: object) -> _Process:
            seen["argv"] = argv
            seen["kwargs"] = kwargs
            passed = kwargs["pass_fds"]
            assert isinstance(passed, tuple)
            for number in passed:
                os.fstat(number)
                self.assertGreaterEqual(number, 3)
            seen["during"] = support.descriptor_snapshot()
            return _Process(lambda timeout=None: ("out", "err"))

        with (
            tempfile_tree() as tree,
            patch.dict(
                os.environ,
                {
                    "PYTHONPATH": "/x",
                    "LD_PRELOAD": "/nonexistent/hook.so",
                    "EII_PLANTED_SECRET": "planted-value-1234",
                },
            ),
        ):
            before = support.descriptor_snapshot()
            with (
                patch.object(support.exposed(launch, "subprocess"), "Popen", recorder),
                patch.object(
                    support.exposed(launch, "os"), "access", return_value=True
                ),
            ):
                result = launch.run_in_sandbox(
                    "build-world",
                    tree.layout("build-world"),
                    COMMAND,
                    venv=tree.venv,
                )
            self.assertEqual(result, launch.SandboxResult(0, "out", "err"))
            argv_seen = seen["argv"]
            assert isinstance(argv_seen, list)
            labels = ["interpreter"]
            self.assertEqual(
                argv_seen[argv_seen.index("PATH") + 1], str(tree.venv / "bin")
            )
            self.assertEqual(labels, ["interpreter"])
            kwargs = seen["kwargs"]
            assert isinstance(kwargs, dict)
            opened = tree.bound("build-world")
            # The launcher closed the descriptors; rebuild the expected argv from the call.
            argv = seen["argv"]
            assert isinstance(argv, list)
            self.assertEqual(kwargs["env"], {})
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stdout"], subprocess.PIPE)
            self.assertEqual(kwargs["stderr"], subprocess.PIPE)
            self.assertEqual(kwargs["text"], True)
            self.assertEqual(kwargs["encoding"], "utf-8")
            self.assertEqual(kwargs["errors"], "replace")
            self.assertEqual(kwargs["close_fds"], True)
            self.assertEqual(kwargs["start_new_session"], True)
            passed = kwargs["pass_fds"]
            assert isinstance(passed, tuple)
            self.assertEqual(passed, tuple(sorted(passed)))
            self.assertEqual(len(passed), 14)
            during = seen["during"]
            assert isinstance(during, dict)
            new = {name for name in during if name not in before}
            self.assertEqual(new, {str(number) for number in passed})
            self.assertNotIn(
                str(tree.extensions), [during[str(number)] for number in passed]
            )
            for number in passed:
                self.assertGreaterEqual(number, 3)
                os_path = during[str(number)]
                destination = argv[argv.index(str(number)) + 1]
                if destination == "/scenario/scenario.bin":
                    self.assertEqual(os_path, str(tree.scenario))
                else:
                    self.assertEqual(os_path, destination)
            for number in passed:
                with self.assertRaises(OSError) as caught:
                    os.fstat(number)
                self.assertEqual(caught.exception.errno, errno.EBADF)
            self.assertEqual(len(opened), 14)

    def test_setup_failure_exit_and_timeout(self) -> None:
        labels: list[str] = []

        def run(
            communicate: object, returncode: int = 0, kill: object | None = None
        ) -> object:
            def recorder(argv: list[str], **kwargs: object) -> _Process:
                return _Process(communicate, returncode)

            with (
                tempfile_tree() as tree,
                patch.object(support.exposed(launch, "subprocess"), "Popen", recorder),
                patch.object(
                    support.exposed(launch, "os"), "access", return_value=True
                ),
            ):
                context = (
                    patch.object(support.exposed(launch, "os"), "killpg", kill)
                    if kill is not None
                    else patch.object(
                        support.exposed(launch, "os"), "killpg", lambda *args: None
                    )
                )
                with context:
                    return launch.run_in_sandbox(
                        "build-world",
                        tree.layout("build-world"),
                        COMMAND,
                        venv=tree.venv,
                        timeout=3,
                    )

        labels.append("a")
        stderr = "ERROR: ld.so: object 'x' cannot be preloaded\nbwrap: Can't find source path /x: No such file or directory\n"
        with self.assertRaises(launch.SandboxSetupError) as setup_a:
            run(lambda timeout=None: ("", stderr), 1)
        self.assertEqual(
            str(setup_a.exception),
            "could not enter the sandbox build-world: bwrap: Can't find source path /x: No such file or directory",
        )
        labels.append("b")
        self.assertEqual(
            run(lambda timeout=None: ("", "oops\n"), 1),
            launch.SandboxResult(1, "", "oops\n"),
        )
        labels.append("c")
        self.assertEqual(
            run(lambda timeout=None: ("", "note: bwrap: x\n"), 7),
            launch.SandboxResult(7, "", "note: bwrap: x\n"),
        )
        labels.append("d")
        self.assertEqual(
            run(lambda timeout=None: ("", ""), 137), launch.SandboxResult(137, "", "")
        )
        labels.append("e")
        self.assertEqual(
            run(lambda timeout=None: ("", "bwrap: x\n"), 2),
            launch.SandboxResult(2, "", "bwrap: x\n"),
        )
        labels.append("f")
        calls: list[object] = []

        def expire(timeout: object = None) -> tuple[str, str]:
            calls.append(timeout)
            if len(calls) == 1:
                limit = float(timeout) if isinstance(timeout, int | float) else 0.0
                raise subprocess.TimeoutExpired("bwrap", limit)
            return "", ""

        killed: list[tuple[int, int]] = []
        with self.assertRaises(launch.SandboxTimeout) as timed:
            run(expire, kill=lambda pid, sig: killed.append((pid, sig)))
        self.assertEqual(
            str(timed.exception),
            "sandbox build-world timed out after 3 s; the process group was killed",
        )
        self.assertEqual(killed, [(4242, signal_kill())])
        self.assertEqual(calls, [3, None])
        labels.append("g")
        with self.assertRaises(launch.SandboxSetupError) as setup:
            run(lambda timeout=None: ("", "bwrap: fake\n"), 1)
        self.assertEqual(
            str(setup.exception),
            "could not enter the sandbox build-world: bwrap: fake",
        )
        labels.append("h")
        calls.clear()
        killed.clear()

        def gone(pid: int, sig: int) -> None:
            killed.append((pid, sig))
            raise ProcessLookupError(3, "No such process")

        with self.assertRaises(launch.SandboxTimeout) as timed_again:
            run(expire, kill=gone)
        self.assertEqual(
            str(timed_again.exception),
            "sandbox build-world timed out after 3 s; the process group was killed",
        )
        self.assertEqual(killed, [(4242, signal_kill())])
        self.assertEqual(calls, [3, None])
        labels.append("i")
        calls.clear()
        killed.clear()

        def denied(pid: int, sig: int) -> None:
            killed.append((pid, sig))
            raise PermissionError(1, "Operation not permitted")

        with self.assertRaises(PermissionError):
            run(expire, kill=denied)
        self.assertEqual(killed, [(4242, signal_kill())])
        self.assertEqual(calls, [3])
        self.assertEqual(labels, ["a", "b", "c", "d", "e", "f", "g", "h", "i"])

    def test_missing_bubblewrap_is_reported(self) -> None:
        message = "bubblewrap is not installed at /nonexistent/bwrap: install the distribution package bubblewrap"
        started: list[object] = []
        with patch.object(tables, "BWRAP", "/nonexistent/bwrap"):
            before = support.descriptor_snapshot()
            with (
                patch.object(
                    support.exposed(launch, "subprocess"),
                    "Popen",
                    lambda *args, **kwargs: started.append(args),
                ),
                self.assertRaises(launch.SandboxError) as caught,
            ):
                launch.run_in_sandbox(
                    "build-world", launch.Layout(CODE, CODE, CODE, CODE), ["/bin/true"]
                )
            self.assertEqual(str(caught.exception), message)
            self.assertEqual(started, [])
            self.assertEqual(support.descriptor_snapshot(), before)
            problems = sandbox_check.check_bubblewrap()
            self.assertEqual(
                problems,
                [
                    "bwrap --version: not available (FileNotFoundError)",
                    f"profile build-world: {message}",
                    f"profile build-release: {message}",
                ],
            )
            status, out, _err = streams(sandbox_check.main, ["check"])
        self.assertEqual(status, 1)
        self.assertEqual(
            out.splitlines(),
            [
                "bubblewrap: not available (FileNotFoundError)",
                "FAIL bwrap --version: not available (FileNotFoundError)",
                f"FAIL profile build-world: {message}",
                f"FAIL profile build-release: {message}",
                "sandbox: FAILED",
            ],
        )

    def test_python_command_and_usage(self) -> None:
        self.assertEqual(
            launch.python_command("-c", "x", venv=Path("/v")),
            ["/v/bin/python", "-I", "-B", "-c", "x"],
        )
        profile, layout, interpreter, _descriptors = golden_layout("build-world")
        for command in ([], ["python"]):
            with self.assertRaises(launch.SandboxError) as caught:
                launch.build_argv(profile, layout, interpreter, command, {})
            self.assertEqual(
                str(caught.exception), "the sandboxed program must be an absolute path"
            )
        for argv in (["bogus"], [], ["check", "x"]):
            status, out, err = streams(sandbox_check.main, argv)
            self.assertEqual(status, 2)
            self.assertEqual(out, "")
            self.assertEqual(
                err,
                "sandbox_check: usage: check | check-extensions | check-enforcement\n",
            )

    def _operations(self, argv: list[str]) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        index = 0
        options = {
            "--ro-bind-fd": 2,
            "--bind-fd": 2,
            "--dir": 1,
            "--symlink": 2,
            "--tmpfs": 1,
            "--dev": 1,
            "--remount-ro": 1,
            "--chdir": 1,
            "--setenv": 2,
        }
        while index < len(argv):
            token = argv[index]
            if token in options:
                width = options[token]
                if token in {
                    "--ro-bind-fd",
                    "--bind-fd",
                    "--dir",
                    "--symlink",
                    "--tmpfs",
                    "--dev",
                    "--remount-ro",
                    "--chdir",
                }:
                    found.setdefault(token, []).append(argv[index + width])
                index += 1 + width
                continue
            index += 1
        return found

    def _descriptors_name_keys(self, opened: dict[Path, int]) -> None:
        for path, number in opened.items():
            self.assertGreaterEqual(number, 3)
            self.assertEqual(os.readlink(f"/proc/self/fd/{number}"), str(path))
            os.fstat(number)


def signal_kill() -> int:
    return signal.SIGKILL


def streams(main: Callable[[list[str]], int], argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
        status = main(argv)
    return status, out.getvalue(), err.getvalue()


class tempfile_tree:
    """A temporary mount tree with a fake uv interpreter and four extension files."""

    def __enter__(self) -> tempfile_tree:
        self._holder = tempfile.TemporaryDirectory()
        self.base = Path(self._holder.__enter__()).resolve()
        self._build()
        self._patch = patch.object(
            extension_tree, "PINNED", support.fake_extensions(self.extensions)
        )
        self._patch.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._patch.stop()
        self._holder.__exit__(exc_type, exc, tb)

    def _build(self) -> None:
        self.real = self.base / "py" / "cpython-3.14.6-x"
        (self.real / "bin").mkdir(parents=True)
        (self.real / "bin" / "python3.14").write_text("", encoding="utf-8")
        self.alias = self.base / "py" / "cpython-3.14-x"
        os.symlink(self.real.name, self.alias)
        self.repo = self.base / "repo"
        for folder in (
            "core/src",
            "custodian/src",
            "scripts/sandbox_inside",
            "data/public_cache",
            "data/vault/b1",
            "data/releases/.staging/b1",
        ):
            (self.repo / folder).mkdir(parents=True)
        self.extensions = self.repo / "data" / "engine_extensions"
        self.venv = self.repo / ".venv"
        (self.venv / "bin").mkdir(parents=True)
        os.symlink(self.alias / "bin" / "python3.14", self.venv / "bin" / "python")
        self.scenario = self.base / "scenario.bin"
        self.scenario.write_text("scenario\n", encoding="utf-8")
        self.cache = self.repo / "data" / "public_cache"
        self.vault = self.repo / "data" / "vault" / "b1"
        self.staging = self.repo / "data" / "releases" / ".staging" / "b1"
        self.core = self.repo / "core" / "src"
        self.inside = self.repo / "scripts" / "sandbox_inside"

    def interpreter(self) -> launch.Interpreter:
        return launch.interpreter_for(self.venv)

    def layout(self, profile_name: str) -> launch.Layout:
        return launch.Layout(
            self.repo,
            self.cache,
            self.vault,
            self.extensions,
            self.staging if profile_name == "build-release" else None,
            self.scenario if profile_name == "build-world" else None,
        )

    def bound(self, profile_name: str) -> list[Path]:
        return launch.bound_paths(
            launch.profile_named(profile_name),
            self.layout(profile_name),
            self.interpreter(),
        )

    def open(self, profile_name: str) -> dict[Path, int]:
        return launch.open_sources(
            launch.profile_named(profile_name),
            self.layout(profile_name),
            self.interpreter(),
        )

    def message(self, template: str) -> str:
        return template.format(
            cache=self.cache,
            extensions=self.extensions,
            vault=self.vault,
            scenario=self.scenario,
            core=self.core,
            inside=self.inside,
            venv=self.venv,
            linked=self.base / "link" / "sub",
            venvlink=self.base / "venv-link",
        )

    def refuse(self, kind: str) -> None:
        profile = "build-world"
        if kind == "world-staging":
            layout = launch.Layout(
                self.repo,
                self.cache,
                self.vault,
                self.extensions,
                self.staging,
                self.scenario,
            )
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        if kind == "release-no-staging":
            layout = launch.Layout(self.repo, self.cache, self.vault, self.extensions)
            launch.open_sources(
                launch.profile_named("build-release"), layout, self.interpreter()
            )
            return
        if kind == "release-scenario":
            layout = launch.Layout(
                self.repo,
                self.cache,
                self.vault,
                self.extensions,
                self.staging,
                self.scenario,
            )
            launch.open_sources(
                launch.profile_named("build-release"), layout, self.interpreter()
            )
            return
        if kind == "world-no-scenario":
            layout = launch.Layout(self.repo, self.cache, self.vault, self.extensions)
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        if kind == "relative-cache":
            layout = launch.Layout(
                self.repo,
                Path("data/public_cache"),
                self.vault,
                self.extensions,
                scenario=self.scenario,
            )
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        if kind == "cache-missing":
            os.rmdir(self.cache)
        elif kind == "cache-file":
            os.rmdir(self.cache)
            self.cache.write_text("x\n", encoding="utf-8")
        elif kind == "vault-link":
            os.rmdir(self.vault)
            os.symlink(self.base / "elsewhere", self.vault)
            (self.base / "elsewhere").mkdir()
        elif kind == "scenario-dir":
            self.scenario.unlink()
            self.scenario.mkdir()
        elif kind == "extensions-equal-cache":
            layout = launch.Layout(
                self.repo, self.cache, self.vault, self.cache, scenario=self.scenario
            )
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        elif kind == "vault-inside-cache":
            nested = self.cache / "vault"
            nested.mkdir()
            layout = launch.Layout(
                self.repo, self.cache, nested, self.extensions, scenario=self.scenario
            )
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        elif kind == "cache-inside-vault":
            nested = self.vault / "cache"
            nested.mkdir()
            layout = launch.Layout(
                self.repo, nested, self.vault, self.extensions, scenario=self.scenario
            )
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        elif kind == "core-missing":
            os.rmdir(self.core)
        elif kind == "inside-link":
            os.rmdir(self.inside)
            os.symlink(self.core, self.inside)
        elif kind == "vault-through-link":
            link = self.base / "link"
            os.symlink(self.cache, link)
            nested = link / "sub"
            nested.mkdir()
            layout = launch.Layout(
                self.repo, self.cache, nested, self.extensions, scenario=self.scenario
            )
            launch.open_sources(
                launch.profile_named(profile), layout, self.interpreter()
            )
            return
        elif kind == "core-through-link":
            other = self.base / "other-core"
            (other / "src").mkdir(parents=True)
            os.rmdir(self.core)
            os.rmdir(self.repo / "core")
            os.symlink(other, self.repo / "core")
        elif kind == "vault-dangling":
            os.rmdir(self.vault)
            os.symlink(self.base / "missing-vault", self.vault)
        elif kind == "cache-mode":
            parent = self.cache.parent
            parent.chmod(0)
            try:
                self.open(profile)
            finally:
                parent.chmod(0o755)
            return
        elif kind == "scenario-nlink":
            os.link(self.scenario, self.vault / "scenario.bin")
        elif kind == "venv-link":
            linked = self.base / "venv-link"
            os.symlink(self.venv, linked)
            found = launch.interpreter_for(linked)
            launch.open_sources(
                launch.profile_named(profile), self.layout(profile), found
            )
            return
        elif kind == "scenario-link":
            target = self.base / "scenario-real.bin"
            self.scenario.rename(target)
            os.symlink(target, self.scenario)
        self.open(profile)


if __name__ == "__main__":
    unittest.main()
