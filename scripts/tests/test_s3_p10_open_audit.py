"""S3-P10 rounds r5b to r5e: a runtime open-audit hook beside the lexical read guard.

The lexical guard of ``test_s3_p10_regular_file.py`` scans source for reads
outside the one helper; this file checks the same rule at runtime (L-1528).
A child process installs ``sys.addaudithook`` for the ``open`` event —
``open``, ``io.open`` and ``os.open`` all raise it — and fails on any open
of the invented stand-in register not made by the one pinned reader,
``eii_product.register_file.read_register_bytes``. The stand-in is matched
by file identity (L-1536), so a second name or a ``bytes`` spelling is seen;
the excusing frame is identified by the reader's code object, so a
same-named frame cannot excuse an open it did not make. Every file here is
invented. The hook sees only the paths the child executes, so the lexical
guard stays.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import s3_t28_support  # noqa: F401  (puts scripts, core and product on the path)
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "product/tests/fixtures/fc_register/stand_in_register.json"
NAME = "EII_FC_REGISTER_FILE"
SECRET = "INVENTED-secret-place"
VIOLATION = "register_open_outside_helper"
LAUNCH_VIOLATION = "register_hook_process_launch"
INTERPRETER_VIOLATION = "register_hook_interpreter_import"
WAIT = 30.0
SOURCE_ROOTS = ("scripts", "core/src", "custodian/src", "product/src")

_CHILD = """
import os
import sys

MODE, STAND_IN, DIGEST = sys.argv[1:4]
GUARDED = os.path.normpath(os.path.abspath(STAND_IN))
GUARDED_ID = os.stat(GUARDED)
for folder in sys.argv[4:]:
    sys.path.insert(0, folder)


LAUNCHES = frozenset(
    {
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.posix_spawn",
        "os.spawn",
        "os.fork",
        "os.forkpty",
    }
)
INTERPRETERS = frozenset({"_interpreters", "_interpchannels", "_interpqueues"})


def _pinned_reader_open(frame, target):
    module = sys.modules.get("eii_product.register_file")
    reader = getattr(module, "read_register_bytes", None)
    return (
        frame is not None
        and frame.f_code is getattr(reader, "__code__", None)
        and frame.f_locals.get("path") is target
        and frame.f_globals is vars(module)
    )


def _same_file(name, dir_fd=None):
    try:
        return os.path.samestat(os.stat(name, dir_fd=dir_fd), GUARDED_ID)
    except (OSError, ValueError):
        return False


def _open_descriptors():
    try:
        return [int(entry) for entry in os.listdir("/proc/self/fd")]
    except OSError:
        return []


def _is_guarded(target):
    if type(target) not in (str, bytes):
        return True
    name = os.fsdecode(target)
    if _same_file(name) or os.path.normpath(os.path.abspath(name)) == GUARDED:
        return True
    return not os.path.isabs(name) and any(
        _same_file(name, descriptor) for descriptor in _open_descriptors()
    )


def _audit(event, args):
    if event == "import" and args and args[0] in INTERPRETERS:
        raise RuntimeError("register_hook_interpreter_import")
    if event in LAUNCHES:
        raise RuntimeError("register_hook_process_launch")
    if event != "open" or not args:
        return
    target = args[0]
    if not isinstance(target, (str, bytes, os.PathLike)):
        return
    if _is_guarded(target) and not _pinned_reader_open(sys._getframe(1), target):
        raise RuntimeError("register_open_outside_helper")


sys.addaudithook(_audit)

if MODE == "pinned":
    import hashlib

    from eii_product.register_file import (
        read_fc_register_rows,
        read_register_bytes,
    )
    from operations.build import fc_register_sha256

    if hashlib.sha256(read_register_bytes(STAND_IN)).hexdigest() != DIGEST:
        raise SystemExit("the pinned read returned other bytes")
    if read_fc_register_rows(STAND_IN, listed_sha256=DIGEST) is None:
        raise SystemExit("the pinned rows read returned nothing")
    if fc_register_sha256() != DIGEST:
        raise SystemExit("the build hash named other bytes")
elif MODE == "unrelated":
    other = os.path.join(os.path.dirname(GUARDED), "other.json")
    with open(other, "w", encoding="utf-8") as stream:
        stream.write("invented")
    with open(other, encoding="utf-8") as stream:
        stream.read()
elif MODE == "alias":
    load_input = os.open
    load_input(GUARDED, os.O_RDONLY)
elif MODE == "partial":
    import functools

    functools.partial(open, GUARDED)()
elif MODE == "getattr":
    import io

    getattr(io, "open")(GUARDED)
elif MODE == "bytes":
    with open(os.fsencode(GUARDED), "rb") as stream:
        stream.read()
elif MODE == "symlink":
    alias = os.path.join(os.path.dirname(GUARDED), "alias.json")
    os.symlink(GUARDED, alias)
    with open(alias, "rb") as stream:
        stream.read()
elif MODE == "procroot":
    with open("/proc/self/root" + GUARDED, "rb") as stream:
        stream.read()
elif MODE == "renamed":
    moved = os.path.join(os.path.dirname(GUARDED), "moved.json")
    os.rename(GUARDED, moved)
    with open(moved, "rb") as stream:
        stream.read()
elif MODE == "fileio_bytes":
    import io

    io.FileIO(os.fsencode(GUARDED)).readall()
elif MODE == "copyfile_bytes":
    import shutil

    shutil.copyfile(os.fsencode(GUARDED), os.fsencode(GUARDED) + b".copy")
elif MODE == "link_then_fileio":
    import io

    hard = os.path.join(os.path.dirname(GUARDED), "hard.json")
    os.link(GUARDED, hard)
    io.FileIO(hard).readall()
elif MODE == "fspath_door":
    from eii_product.register_file import read_register_bytes

    foreign = os.path.join(os.path.dirname(GUARDED), "foreign.json")
    with open(foreign, "w", encoding="utf-8") as stream:
        stream.write("invented")

    class Evil:
        def __fspath__(self):
            with open(GUARDED, "rb") as stream:
                stream.read()
            return foreign

    read_register_bytes(Evil())
elif MODE == "exec_same_name":
    namespace = {"__name__": "eii_product.register_file", "G": GUARDED}
    exec('def read_register_bytes():\\n    open(G, "rb").read()', namespace)
    namespace["read_register_bytes"]()
elif MODE == "lying_bytes_fileio":
    import io

    class LyingBytes(bytes):
        def decode(self, *args, **kwargs):
            return os.path.join(os.path.dirname(GUARDED), "foreign.json")

    io.FileIO(LyingBytes(os.fsencode(GUARDED))).readall()
elif MODE == "two_answer_fspath":
    import io

    class TwoAnswers:
        calls = 0

        def __fspath__(self):
            TwoAnswers.calls += 1
            if TwoAnswers.calls == 1:
                return GUARDED
            return os.path.join(os.path.dirname(GUARDED), "foreign.json")

    io.FileIO(TwoAnswers()).readall()
elif MODE == "c_only_fspath":
    import io

    from eii_product.register_file import RegisterRefusal, read_register_bytes

    held = []
    chain = map(held.append, map(io.FileIO, [GUARDED]))

    class COnly:
        pass

    COnly.__fspath__ = staticmethod(chain.__next__)
    try:
        read_register_bytes(COnly())
    except (TypeError, RegisterRefusal):
        pass
    held[0].readall()
elif MODE == "dir_fd":
    folder = os.open(os.path.dirname(GUARDED), os.O_RDONLY)
    descriptor = os.open(os.path.basename(GUARDED), os.O_RDONLY, dir_fd=folder)
    os.fdopen(descriptor, "rb").read()
elif MODE == "subprocess_cat":
    import subprocess

    subprocess.run(["cat", GUARDED], capture_output=True, check=True)
elif MODE == "spelled":
    os.open(STAND_IN, os.O_RDONLY)
elif MODE == "spelled_bytes":
    with open(os.fsencode(STAND_IN), "rb") as stream:
        stream.read()
elif MODE == "reader_code_other_globals":
    import types

    import eii_product.register_file as register_file

    other = dict(vars(register_file))
    other["_regular_file_bytes"] = lambda descriptor, path: os.read(descriptor, 1)
    types.FunctionType(register_file.read_register_bytes.__code__, other)(GUARDED)
elif MODE == "subinterpreter":
    from concurrent import interpreters

    interpreters.create().exec("open(%r, 'rb').read()" % GUARDED)
elif MODE == "os_system":
    os.system("cat " + GUARDED)
elif MODE == "posix_spawn":
    pid = os.posix_spawn("/bin/cat", ["cat", GUARDED], os.environ)
    os.waitpid(pid, 0)
elif MODE == "os_spawn":
    os.spawnv(os.P_WAIT, "/bin/cat", ["cat", GUARDED])
elif MODE == "os_spawn_event":
    sys.audit("os.spawn", os.P_WAIT, "/bin/cat", ["cat", GUARDED], None)
elif MODE == "os_forkpty":
    if os.forkpty()[0] == 0:
        os._exit(0)
elif MODE == "execv":
    os.execv("/bin/cat", ["cat", GUARDED])
else:
    raise SystemExit("unknown mode " + MODE)
"""


def _run_child(
    stand_in: str, digest: str, mode: str
) -> subprocess.CompletedProcess[str]:
    """Run one child program under the audit hook, stand-in named by env."""
    environment = dict(os.environ)
    environment[NAME] = stand_in
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            _CHILD,
            mode,
            stand_in,
            digest,
            *(str(ROOT / folder) for folder in SOURCE_ROOTS),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=WAIT,
    )


class OpenAuditHook(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.folder = Path(scratch.name) / SECRET
        self.folder.mkdir()
        self.body = FIXTURE.read_bytes()
        self.file = self.folder / "register.json"
        self.file.write_bytes(self.body)
        self.digest = hashlib.sha256(self.body).hexdigest()

    def _run(self, mode: str) -> subprocess.CompletedProcess[str]:
        return _run_child(str(self.file), self.digest, mode)

    def test_the_pinned_reads_of_the_stand_in_pass_the_hook(self) -> None:
        completed = self._run("pinned")
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_an_unrelated_open_is_not_flagged(self) -> None:
        completed = self._run("unrelated")
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_an_aliased_os_open_of_the_stand_in_fails(self) -> None:
        completed = self._run("alias")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_partial_open_of_the_stand_in_fails(self) -> None:
        completed = self._run("partial")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_getattr_io_open_of_the_stand_in_fails(self) -> None:
        completed = self._run("getattr")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_bytes_spelling_of_the_stand_in_fails(self) -> None:
        completed = self._run("bytes")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_symlink_alias_of_the_stand_in_fails(self) -> None:
        completed = self._run("symlink")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_proc_self_root_spelling_of_the_stand_in_fails(self) -> None:
        completed = self._run("procroot")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_renamed_stand_in_open_fails(self) -> None:
        completed = self._run("renamed")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_fileio_open_over_bytes_fails(self) -> None:
        completed = self._run("fileio_bytes")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_copyfile_over_bytes_fails(self) -> None:
        completed = self._run("copyfile_bytes")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_hard_link_then_fileio_fails(self) -> None:
        completed = self._run("link_then_fileio")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_an_fspath_door_through_the_reader_fails(self) -> None:
        completed = self._run("fspath_door")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_an_exec_made_same_name_function_fails(self) -> None:
        completed = self._run("exec_same_name")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_bytes_subclass_that_lies_in_decode_fails(self) -> None:
        completed = self._run("lying_bytes_fileio")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_two_answer_fspath_into_fileio_fails(self) -> None:
        completed = self._run("two_answer_fspath")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_c_only_fspath_under_the_reader_frame_fails(self) -> None:
        completed = self._run("c_only_fspath")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_dir_fd_relative_open_fails(self) -> None:
        completed = self._run("dir_fd")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_process_launch_is_refused(self) -> None:
        completed = self._run("subprocess_cat")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(LAUNCH_VIOLATION, completed.stderr)

    def test_the_reader_code_over_other_globals_fails(self) -> None:
        completed = self._run("reader_code_other_globals")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(VIOLATION, completed.stderr)

    def test_a_subinterpreter_import_is_refused(self) -> None:
        completed = self._run("subinterpreter")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(INTERPRETER_VIOLATION, completed.stderr)

    def test_each_other_launch_event_is_refused(self) -> None:
        for mode in (
            "os_system",
            "posix_spawn",
            "execv",
            "os_spawn",
            "os_spawn_event",
            "os_forkpty",
        ):
            with self.subTest(mode=mode):
                completed = self._run(mode)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(LAUNCH_VIOLATION, completed.stderr)


@settings(max_examples=10, deadline=None, database=None)
@given(
    redundant=st.lists(st.sampled_from(["/./", "//"]), min_size=0, max_size=3).map(
        "".join
    ),
    as_bytes=st.booleans(),
)
def test_the_hook_matches_equivalent_path_spellings(
    redundant: str, as_bytes: bool
) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch) / SECRET
        folder.mkdir()
        file = folder / "register.json"
        file.write_bytes(FIXTURE.read_bytes())
        digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        spelling = str(folder) + "/" + redundant + "register.json"
        completed = _run_child(
            spelling, digest, "spelled_bytes" if as_bytes else "spelled"
        )
    assert completed.returncode != 0, completed.stderr
    assert VIOLATION in completed.stderr


if __name__ == "__main__":
    unittest.main()
