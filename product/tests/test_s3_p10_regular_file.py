"""S3-P10 round 3 (R1 of rv2): the register file is a regular file, never followed.

Every file here is invented. Each case changes only the object the setting
names and keeps the listed hash valid for the fixture bytes, so the only
refusal left is the file-type or swap guard: ``read_refused``.
"""

from __future__ import annotations

import errno
import hashlib
import multiprocessing
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_product.config import ConfigError
from eii_product.register_file import (
    RegisterRefusal,
    read_fc_register_rows,
    read_register_bytes,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fc_register" / "stand_in_register.json"
BODY = FIXTURE.read_bytes()
DIGEST = hashlib.sha256(BODY).hexdigest()
SECRET = "INVENTED-secret-place"
NAME = "EII_FC_REGISTER_FILE"
WAIT = 5.0


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / SECRET
    folder.mkdir(exist_ok=True)
    return folder


def _regular(tmp_path: Path) -> Path:
    path = _folder(tmp_path) / "register.json"
    path.write_bytes(BODY)
    return path


def _reason_in_child(read: Callable[[str], object], path: str) -> str:
    """Run one read in a forked child so a blocking open can never hang the test."""
    context = multiprocessing.get_context("fork")
    queue = context.Queue()

    def child() -> None:
        try:
            read(path)
        except RegisterRefusal as exc:
            queue.put(exc.reason)
            return
        queue.put("accepted")

    process = context.Process(target=child)
    process.start()
    try:
        process.join(WAIT)
        assert not process.is_alive(), "the read blocks instead of refusing"
        return str(queue.get(timeout=WAIT))
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        queue.close()
        queue.join_thread()


def _rows(path: str) -> object:
    return read_fc_register_rows(path, listed_sha256=DIGEST)


def _refuses_without_the_path(path: Path) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        with pytest.raises(RegisterRefusal, match=r"^read_refused$") as caught:
            _rows(str(path))
    assert SECRET not in str(caught.value) and SECRET not in repr(caught.value)
    assert caught.value.__cause__ is None
    with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
        read_register_bytes(str(path))


def test_the_regular_file_with_its_listed_hash_still_reads(tmp_path: Path) -> None:
    path = _regular(tmp_path)
    assert read_register_bytes(str(path)) == BODY
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        assert _rows(str(path)) is not None


def test_a_symlink_to_a_valid_file_refuses(tmp_path: Path) -> None:
    link = _folder(tmp_path) / "link.json"
    link.symlink_to(_regular(tmp_path))
    _refuses_without_the_path(link)


def test_a_symlink_to_a_missing_file_refuses(tmp_path: Path) -> None:
    link = _folder(tmp_path) / "dangling.json"
    link.symlink_to(_folder(tmp_path) / "absent.json")
    _refuses_without_the_path(link)


def test_a_fifo_with_no_writer_refuses_without_blocking(tmp_path: Path) -> None:
    pipe = _folder(tmp_path) / "register.json"
    os.mkfifo(pipe)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(pipe))
        assert _reason_in_child(_rows, str(pipe)) == "read_refused"
    assert _reason_in_child(read_register_bytes, str(pipe)) == "read_refused"


def test_a_fifo_whose_writer_supplies_the_listed_bytes_refuses(tmp_path: Path) -> None:
    pipe = _folder(tmp_path) / "register.json"
    os.mkfifo(pipe)
    # Hold a read end so the write end opens at once; the valid bytes wait
    # in the pipe for the reader under test.
    keep = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
    writer = os.open(pipe, os.O_WRONLY)
    try:
        assert os.write(writer, BODY) == len(BODY)
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv(NAME, str(pipe))
            assert _reason_in_child(_rows, str(pipe)) == "read_refused"
    finally:
        os.close(writer)
        os.close(keep)


def _still_open(descriptor: int) -> bool:
    try:
        os.fstat(descriptor)
    except OSError as exc:
        assert exc.errno == errno.EBADF
        return False
    return True


def _opened_then_closed(action: Callable[[], None], *, times: int) -> None:
    """Run ``action`` ``times`` times; every descriptor it opens is closed."""
    opened: list[int] = []
    real = os.open

    def opener(name: str, mode: int, *args: Any) -> int:
        descriptor = real(name, mode, *args)
        opened.append(descriptor)
        return descriptor

    try:
        with patch("os.open", side_effect=opener):
            for _ in range(times):
                action()
        assert len(opened) == times
        assert [fd for fd in opened if _still_open(fd)] == []
    finally:
        for descriptor in opened:
            if _still_open(descriptor):
                os.close(descriptor)


def test_a_directory_refuses(tmp_path: Path) -> None:
    folder = _folder(tmp_path) / "register.json"
    folder.mkdir()
    _refuses_without_the_path(folder)


def test_refusing_a_directory_closes_its_descriptor(tmp_path: Path) -> None:
    folder = _folder(tmp_path) / "register.json"
    folder.mkdir()

    def once() -> None:
        with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
            read_register_bytes(str(folder))

    _opened_then_closed(once, times=4)


def test_requests_after_a_file_becomes_a_directory_do_not_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from product.tests.test_layers_fc_firms import _get

    from eii_product.api.app import create_app

    file = _folder(tmp_path) / "register.json"
    file.write_bytes(BODY)
    monkeypatch.setenv(NAME, str(file))
    app = create_app(
        tmp_path,
        fc_setting_reader=lambda: str(file),
        fc_listed_reader=lambda _store: DIGEST,
    )
    file.unlink()
    file.mkdir()

    def once() -> None:
        status, body = _get(app, "/api/layers/fc_firms_per_tower")
        assert status == 200
        assert body == {"status": "NO_DATA", "reason": "read_refused", "facts": []}

    _opened_then_closed(once, times=4)


def test_directory_refusals_do_not_exhaust_a_small_descriptor_limit(
    tmp_path: Path,
) -> None:
    regular = _regular(tmp_path)
    directory = _folder(tmp_path) / "directory.json"
    directory.mkdir()
    program = "\n".join(
        (
            "import os",
            "import resource",
            "from eii_product.register_file import RegisterRefusal, read_fc_register_rows",
            "soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)",
            "resource.setrlimit(resource.RLIMIT_NOFILE, (64, hard))",
            "try:",
            f"    os.environ['{NAME}'] = {str(directory)!r}",
            "    for _ in range(96):",
            "        try:",
            f"            read_fc_register_rows({str(directory)!r}, listed_sha256={DIGEST!r})",
            "        except RegisterRefusal as exc:",
            "            assert exc.reason == 'read_refused'",
            "        else:",
            "            raise SystemExit('directory accepted')",
            f"    os.environ['{NAME}'] = {str(regular)!r}",
            "    got = read_fc_register_rows("
            f"{str(regular)!r}, listed_sha256={DIGEST!r})",
            "    assert got is not None",
            "finally:",
            "    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_a_missing_file_refuses(tmp_path: Path) -> None:
    _refuses_without_the_path(_folder(tmp_path) / "register.json")


@pytest.mark.skipif(not os.path.exists("/dev/null"), reason="no device node here")
def test_a_device_refuses() -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, "/dev/null")
        assert _reason_in_child(_rows, "/dev/null") == "read_refused"


def test_a_path_with_a_null_character_refuses() -> None:
    with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
        read_register_bytes("register\x00.json")


def _swap_after_the_read(action: Callable[[], None]) -> Any:
    """Call ``action`` at the descriptor check that follows the read."""
    real = os.fstat
    calls = []

    def fstat(descriptor: int) -> os.stat_result:
        calls.append(descriptor)
        if len(calls) == 2:
            action()
        return real(descriptor)

    return patch("os.fstat", side_effect=fstat)


def test_a_path_replaced_during_the_read_refuses(tmp_path: Path) -> None:
    path = _regular(tmp_path)
    other = _folder(tmp_path) / "other.json"
    other.write_bytes(BODY)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        with _swap_after_the_read(lambda: os.replace(other, path)):
            with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
                _rows(str(path))


def test_a_path_replaced_by_a_symlink_during_the_read_refuses(tmp_path: Path) -> None:
    path = _regular(tmp_path)
    target = _folder(tmp_path) / "target.json"
    target.write_bytes(BODY)
    staged = _folder(tmp_path) / "staged.json"
    staged.symlink_to(target)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        with _swap_after_the_read(lambda: os.replace(staged, path)):
            with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
                _rows(str(path))


def test_a_file_grown_during_the_read_refuses(tmp_path: Path) -> None:
    path = _regular(tmp_path)

    def grow() -> None:
        with path.open("ab") as stream:
            stream.write(b" ")

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        with _swap_after_the_read(grow):
            with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
                _rows(str(path))


def test_the_start_refuses_a_symlink_naming_only_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_product.api.app import create_app

    link = _folder(tmp_path) / "link.json"
    link.symlink_to(_regular(tmp_path))
    monkeypatch.setenv(NAME, str(link))
    with pytest.raises(ConfigError) as caught:
        create_app(
            tmp_path,
            fc_setting_reader=lambda: str(link),
            fc_listed_reader=lambda store: DIGEST,
        )
    assert caught.value.variable == "EII_FC_REGISTER_FILE"
    assert SECRET not in repr(caught.value)


def test_a_parent_folder_swapped_during_the_read_refuses(tmp_path: Path) -> None:
    # The original file's own inode is untouched, so only the check of the
    # path against the read descriptor can see this swap.
    first = tmp_path / "first"
    first.mkdir()
    (first / "register.json").write_bytes(BODY)
    second = tmp_path / "second"
    second.mkdir()
    (second / "register.json").write_bytes(BODY)
    live = tmp_path / SECRET

    def swap() -> None:
        live.rename(tmp_path / "old")
        second.rename(live)

    first.rename(live)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(live / "register.json"))
        with _swap_after_the_read(swap):
            with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
                _rows(str(live / "register.json"))


def test_a_file_removed_during_the_read_refuses(tmp_path: Path) -> None:
    path = _regular(tmp_path)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(NAME, str(path))
        with _swap_after_the_read(path.unlink):
            with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
                _rows(str(path))


def test_a_symlink_is_refused_at_the_open_before_any_read(tmp_path: Path) -> None:
    link = _folder(tmp_path) / "link.json"
    link.symlink_to(_regular(tmp_path))
    with patch("os.fstat", side_effect=AssertionError("read past the open")):
        with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
            read_register_bytes(str(link))


def test_the_open_neither_follows_blocks_nor_leaks_the_descriptor(
    tmp_path: Path,
) -> None:
    path = _regular(tmp_path)
    real = os.open
    flags: list[int] = []

    def opener(name: str, mode: int, *args: Any) -> int:
        flags.append(mode)
        return real(name, mode, *args)

    with patch("os.open", side_effect=opener):
        assert read_register_bytes(str(path)) == BODY
    wanted = (os.O_NOFOLLOW, os.O_NONBLOCK, os.O_CLOEXEC)
    assert len(flags) == 1
    assert [flags[0] & bit for bit in wanted] == list(wanted)
    assert flags[0] & (os.O_WRONLY | os.O_RDWR) == 0


KINDS = (
    "regular",
    "symlink_to_regular",
    "symlink_to_missing",
    "symlink_to_folder",
    "fifo",
    "folder",
    "missing",
)


def _make(folder: Path, kind: str, body: bytes) -> Path:
    path = folder / "register.json"
    target = folder / "target.json"
    if kind == "regular":
        path.write_bytes(body)
    elif kind == "symlink_to_regular":
        target.write_bytes(body)
        path.symlink_to(target)
    elif kind == "symlink_to_missing":
        path.symlink_to(target)
    elif kind == "symlink_to_folder":
        path.symlink_to(folder)
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "folder":
        path.mkdir()
    return path


@settings(max_examples=120, deadline=None)
@given(kind=st.sampled_from(KINDS), body=st.binary(max_size=4096))
def test_only_a_regular_file_yields_its_exact_bytes(kind: str, body: bytes) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        path = _make(Path(scratch), kind, body)
        if kind == "fifo":
            assert _reason_in_child(read_register_bytes, str(path)) == "read_refused"
            return
        if kind == "regular":
            assert read_register_bytes(str(path)) == body
            return
        with pytest.raises(RegisterRefusal, match=r"^read_refused$"):
            read_register_bytes(str(path))
