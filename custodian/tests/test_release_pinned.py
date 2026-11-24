"""Invented races against the pinned publication helper and the producer writer."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
from pathlib import Path

import pytest
from public_assembly_fixture import approve, inputs

from eii_custodian.release import pinned, producer

OUTPUTS = [
    "assembly/release_candidate.json",
    "assembly/release.json",
    "assembly/release_review.json",
]


def run(cache: Path, output: str) -> None:
    (producer.prepare if output.endswith("candidate.json") else producer.produce)(cache)


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("stage", ["create", "replace"])
@pytest.mark.parametrize("where", ["root", "parent", "leaf"])
@pytest.mark.parametrize("replacement", ["symlink", "real"])
@pytest.mark.parametrize("output", OUTPUTS)
def test_producer_output_swap_is_refused_without_outside_write(
    tmp_path, monkeypatch, existing, stage, where, replacement, output
):
    cache = tmp_path / "cache"
    inputs(cache)
    approve(cache)
    if existing:
        producer.produce(cache)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = cache / output
    victim = {"root": cache, "parent": target.parent, "leaf": target}[where]
    original_open, original_rename = os.open, pinned._renameat2
    original_write = producer._write
    armed = swapped = False

    def swap():
        nonlocal swapped
        swapped = True
        if victim.is_symlink() or victim.exists():
            victim.rename(tmp_path / "held")
        if replacement == "symlink":
            victim.symlink_to(
                elsewhere / "absent" if where == "leaf" else elsewhere,
                target_is_directory=where != "leaf",
            )
        elif where == "leaf":
            victim.write_bytes(b"INVENTED-substitute")
        else:
            victim.mkdir()

    def writing(cache, name, value):
        nonlocal armed
        armed = name == output
        try:
            original_write(cache, name, value)
        finally:
            armed = False

    def opening(path, flags, *args, **kwargs):
        if stage == "create" and armed and flags & os.O_CREAT and not swapped:
            swap()
        return original_open(path, flags, *args, **kwargs)

    def renaming(parent, name, destination, flags):
        if stage == "replace" and armed and not swapped:
            swap()
        return original_rename(parent, name, destination, flags)

    monkeypatch.setattr(producer, "_write", writing)
    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pytest.raises(ValueError, match=r"\Aproducer_path_refused\Z"):
        run(cache, output)
    assert swapped
    assert list(elsewhere.iterdir()) == []
    if where == "leaf" and replacement == "real":
        assert target.read_bytes() == b"INVENTED-substitute"
    assert not list(tmp_path.rglob("*.partial"))


class _Refusing:
    """A stand-in C function that fails with one errno."""

    def __init__(self, code: int):
        self.code = code

    def __call__(self, *args):
        ctypes.set_errno(self.code)
        return -1


class _Library:
    def __init__(self, function=None):
        if function is not None:
            self.renameat2 = function


@pytest.mark.parametrize(
    "library",
    [
        pytest.param(_Library(), id="missing"),
        pytest.param(_Library(_Refusing(errno.ENOSYS)), id="ENOSYS"),
        pytest.param(_Library(_Refusing(errno.EINVAL)), id="EINVAL"),
    ],
)
@pytest.mark.parametrize("existing", [False, True])
def test_a_system_without_renameat2_refuses_without_fallback(
    tmp_path, monkeypatch, library, existing
):
    cache = tmp_path / "cache"
    inputs(cache)
    target = cache / OUTPUTS[0]
    if existing:
        producer.prepare(cache)
    before = target.read_bytes() if existing else None
    monkeypatch.setattr(pinned, "_LIBC", library)
    monkeypatch.setattr(
        os, "replace", lambda *args, **kwargs: pytest.fail("plain rename")
    )
    monkeypatch.setattr(os, "rename", lambda *args, **kwargs: pytest.fail("rename"))
    with pytest.raises(ValueError, match=r"\Apublication_rename_unsupported\Z"):
        producer.prepare(cache)
    assert (target.read_bytes() if existing else target.exists()) == (
        before if existing else False
    )
    assert not list(cache.rglob("*.partial"))


def test_another_rename_errno_is_an_os_error(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    inputs(cache)
    monkeypatch.setattr(pinned, "_LIBC", _Library(_Refusing(errno.EXDEV)))
    with pytest.raises(ValueError, match=r"\Aproducer_path_refused\Z"):
        producer.prepare(cache)
    assert not (cache / OUTPUTS[0]).exists()


@pytest.mark.parametrize("relative", ["", ".", "..", "a/../b", "/abs", "a/./b"])
def test_target_refuses_dot_and_absolute_parts(tmp_path, relative):
    cache = tmp_path / "cache"
    cache.mkdir()
    with pinned.root(cache, "INVENTED_refused") as root:
        with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
            with pinned.target(root, relative):
                pass
    assert list(cache.iterdir()) == []


def test_target_refuses_a_non_regular_leaf(tmp_path):
    cache = tmp_path / "cache"
    (cache / "a" / "leaf").mkdir(parents=True)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
            with pinned.target(root, "a/leaf"):
                pass


@pytest.mark.parametrize("swap", ["file", "symlink"])
def test_read_refuses_a_leaf_swapped_after_pinning(tmp_path, swap):
    cache = tmp_path / "cache"
    (cache / "a").mkdir(parents=True)
    leaf = cache / "a" / "leaf"
    leaf.write_bytes(b"INVENTED-pinned")
    outside = tmp_path / "outside"
    outside.write_bytes(b"INVENTED-outside")
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "a/leaf") as pinned_leaf:
            leaf.rename(tmp_path / "held")  # kept alive: its inode is not reused
            if swap == "file":
                leaf.write_bytes(b"INVENTED-other")
                with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
                    pinned.read(pinned_leaf)
            else:
                leaf.symlink_to(outside)
                with pytest.raises(OSError) as raised:
                    pinned.read(pinned_leaf)
                assert raised.value.errno == errno.ELOOP


def test_read_of_an_absent_leaf_is_none_and_reads_nothing(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "a/leaf") as leaf:
            monkeypatch.setattr(os, "open", lambda *a, **k: pytest.fail("opened"))
            assert pinned.read(leaf) is None


def test_exchange_rollback_is_withheld_when_the_name_changed(tmp_path, monkeypatch):
    """After the exchange both names are substituted: refuse, delete neither.

    Round 3e: the rollback cannot complete, so the closed reason is
    ``publication_rollback_incomplete``."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")
    original_rename = pinned._renameat2
    calls = []

    def renaming(parent, name, destination, flags):
        calls.append(flags)
        original_rename(parent, name, destination, flags)
        if len(calls) == 1:
            # Entries are moved aside, not unlinked, so no inode is reused.
            (cache / name).rename(tmp_path / "displaced")
            (cache / name).write_bytes(b"INVENTED-temporary-plant")
            (cache / destination).rename(tmp_path / "published")
            (cache / destination).write_bytes(b"INVENTED-leaf-plant")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(
                ValueError, match=r"\Apublication_rollback_incomplete\Z"
            ):
                with pinned.publish(leaf) as output:
                    output.write(b"INVENTED-new")
    assert calls == [pinned.RENAME_EXCHANGE]
    assert (cache / "leaf").read_bytes() == b"INVENTED-leaf-plant"
    assert [p.read_bytes() for p in cache.glob("*.partial")] == [
        b"INVENTED-temporary-plant"
    ]


def test_post_publication_check_failure_unpublishes_a_new_leaf(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    refusals = []

    def failing():
        if (cache / "leaf").exists():
            refusals.append(True)
            raise ValueError("INVENTED_late")

    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(ValueError, match=r"\AINVENTED_late\Z"):
                with pinned.publish(leaf, failing) as output:
                    output.write(b"INVENTED-new")
    assert refusals == [True]
    assert list(cache.iterdir()) == []


def test_post_publication_check_failure_restores_a_replaced_leaf(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")
    published = []

    def failing():
        published.append((cache / "leaf").read_bytes())
        if published[-1] == b"INVENTED-new":
            raise ValueError("INVENTED_late")

    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(ValueError, match=r"\AINVENTED_late\Z"):
                with pinned.publish(leaf, failing) as output:
                    output.write(b"INVENTED-new")
    assert published == [b"INVENTED-old", b"INVENTED-new"]
    assert [p.name for p in cache.iterdir()] == ["leaf"]
    assert (cache / "leaf").read_bytes() == b"INVENTED-old"


def test_another_errno_reaches_the_caller_as_that_os_error(monkeypatch):
    monkeypatch.setattr(pinned, "_LIBC", _Library(_Refusing(errno.EXDEV)))
    with pytest.raises(OSError) as raised:
        pinned._renameat2(0, "a", "b", pinned.RENAME_NOREPLACE)
    assert raised.value.errno == errno.EXDEV


def test_read_refuses_a_leaf_swapped_only_while_it_is_opened(tmp_path, monkeypatch):
    """The name is restored before the post-read check: only fstat can see it."""
    cache = tmp_path / "cache"
    cache.mkdir()
    leaf = cache / "leaf"
    leaf.write_bytes(b"INVENTED-pinned")
    other = tmp_path / "other"
    other.write_bytes(b"INVENTED-other")
    original_open = os.open
    swaps = []

    def opening(path, flags, *args, **kwargs):
        if path != "leaf":
            return original_open(path, flags, *args, **kwargs)
        swaps.append(True)
        leaf.rename(tmp_path / "held")
        other.rename(leaf)
        try:
            return original_open(path, flags, *args, **kwargs)
        finally:
            leaf.rename(other)
            (tmp_path / "held").rename(leaf)

    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as pinned_leaf:
            monkeypatch.setattr(os, "open", opening)
            with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
                pinned.read(pinned_leaf)
    assert swaps == [True]


def test_a_check_leaf_substituted_during_the_copy_refuses_before_publication(
    tmp_path, monkeypatch
):
    """The other target's leaf changes: its check refuses before the rename."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "other").write_bytes(b"INVENTED-other")
    original_fsync = os.fsync

    def syncing(descriptor):
        (cache / "other").rename(tmp_path / "held")
        (cache / "other").write_bytes(b"INVENTED-substitute")
        return original_fsync(descriptor)

    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf, pinned.target(root, "other") as other:
            monkeypatch.setattr(os, "fsync", syncing)
            with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
                with pinned.publish(leaf, other.check) as output:
                    output.write(b"INVENTED-new")
    assert sorted(p.name for p in cache.iterdir()) == ["other"]


# Round 3c (ruling L-1515, read side): each producer read named by the function
# that performs it, with the cache file it reads in the invented inputs; the
# body that ``_bound`` reads is named by the spec.
READS = {
    "_read": "assembly/final_audit.json",
    "_bound": None,
    "_phase": "assembly/graph/graph_node.parquet",
    "_candidate": "assembly/gis_property_singles.json",
}


def _read_target(cache: Path, reader: str) -> Path:
    """Build the invented inputs and return the cache file the reader opens."""
    from custodian.tests.test_release_producer import graph_inputs

    spec = graph_inputs(cache)
    relative = READS[reader] or spec["sources"]["INVENTED-source"]["body"]["path"]
    return cache / relative


@pytest.mark.parametrize("where", ["root", "parent", "leaf"])
@pytest.mark.parametrize("replacement", ["symlink", "real", "none"])
@pytest.mark.parametrize("reader", sorted(READS))
def test_producer_read_swap_after_the_check_is_refused(
    tmp_path, monkeypatch, where, replacement, reader
):
    """A root, parent or leaf swapped between the check and the open: refused.

    The outside copy of the file is unreadable, so a read through the swapped
    name surfaces as ``producer_receipt_missing`` instead of passing silently
    and being refused later. A leaf replaced by a real file holds the same
    bytes, so only the descriptor identity can tell it apart. With no
    replacement (round 3e, cf2 finding 2) the entry is only renamed away, and
    a pinned entry that disappears is refused, not read as absent.
    """
    cache = tmp_path / "cache"
    target = _read_target(cache, reader)
    body = target.read_bytes()
    victim = {"root": cache, "parent": target.parent, "leaf": target}[where]
    elsewhere = tmp_path / "elsewhere"
    if where == "leaf":
        elsewhere.write_bytes(body)
    else:
        shutil.copytree(victim, elsewhere)
    (elsewhere / target.relative_to(victim)).chmod(0)
    swapped = []

    def swap() -> None:
        swapped.append(True)
        victim.rename(tmp_path / "held")  # kept alive: its inode is not reused
        if replacement == "none":
            return
        if replacement == "symlink":
            victim.symlink_to(elsewhere, target_is_directory=where != "leaf")
        elif where == "leaf":
            victim.write_bytes(body)
        else:
            shutil.copytree(tmp_path / "held", victim)
            (victim / target.relative_to(victim)).chmod(0)

    original_open = os.open
    original_read_bytes, original_is_file = Path.read_bytes, Path.is_file

    def opening(path, flags, *args, **kwargs):
        if path == target.name and not flags & os.O_DIRECTORY and not swapped:
            swap()
        return original_open(path, flags, *args, **kwargs)

    def by_name(original):
        def call(self, *args, **kwargs):
            if self == target and not swapped:
                swap()
            return original(self, *args, **kwargs)

        return call

    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(Path, "read_bytes", by_name(original_read_bytes))
    monkeypatch.setattr(Path, "is_file", by_name(original_is_file))
    with pytest.raises(ValueError, match=r"\Aproducer_path_refused\Z"):
        producer.prepare(cache)
    assert swapped == [True]


# Round 3e (cf2 finding 1): after the exchange, cleanup is aware of success.
# A displaced previous file is never unlinked on an exceptional exit; when the
# rollback cannot complete it is kept under the temporary name for recovery,
# the owned target is withdrawn only while it is still the owned one, and the
# refusal is the closed reason ``publication_rollback_incomplete``.
def _exchange_then(tmp_path, monkeypatch, after, fail_rollback=False):
    """Publish over an existing leaf; ``after`` runs right after the exchange."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")
    original_rename = pinned._renameat2
    calls = []

    def renaming(parent, name, destination, flags):
        calls.append(flags)
        if len(calls) > 1 and fail_rollback:
            raise OSError(errno.EIO, "INVENTED rollback failure")
        original_rename(parent, name, destination, flags)
        if len(calls) == 1:
            after(cache, name)

    def late():
        if calls and (cache / "leaf").read_bytes() == b"INVENTED-new":
            raise ValueError("INVENTED_late")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(
                ValueError, match=r"\Apublication_rollback_incomplete\Z"
            ):
                with pinned.publish(leaf, late) as output:
                    output.write(b"INVENTED-new")
    return cache, calls


def test_target_only_substitution_keeps_the_displaced_file(tmp_path, monkeypatch):
    def substitute(cache, temporary):
        (cache / "leaf").rename(tmp_path / "published")  # moved, not unlinked
        (cache / "leaf").write_bytes(b"INVENTED-leaf-plant")

    cache, calls = _exchange_then(tmp_path, monkeypatch, substitute)
    assert calls == [pinned.RENAME_EXCHANGE]
    assert (cache / "leaf").read_bytes() == b"INVENTED-leaf-plant"
    assert [p.read_bytes() for p in cache.glob("*.partial")] == [b"INVENTED-old"]


def test_temporary_disappearance_withdraws_the_owned_target(tmp_path, monkeypatch):
    def vanish(cache, temporary):
        (cache / temporary).rename(tmp_path / "displaced")

    cache, calls = _exchange_then(tmp_path, monkeypatch, vanish)
    # The exchange back runs and the real call fails (no temporary name).
    assert calls == [pinned.RENAME_EXCHANGE, pinned.RENAME_EXCHANGE]
    assert list(cache.iterdir()) == []
    assert (tmp_path / "displaced").read_bytes() == b"INVENTED-old"


def test_rollback_failure_keeps_the_displaced_file_and_withdraws(tmp_path, monkeypatch):
    cache, calls = _exchange_then(
        tmp_path, monkeypatch, lambda cache, name: None, fail_rollback=True
    )
    assert calls == [pinned.RENAME_EXCHANGE, pinned.RENAME_EXCHANGE]
    assert not (cache / "leaf").exists()
    assert [p.read_bytes() for p in cache.glob("*.partial")] == [b"INVENTED-old"]


def test_rollback_failure_leaves_a_substituted_target_alone(tmp_path, monkeypatch):
    """The rollback fails and the target is no longer the owned one."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")
    original_rename = pinned._renameat2
    calls = []

    def renaming(parent, name, destination, flags):
        calls.append(flags)
        if len(calls) > 1:
            (cache / "leaf").rename(tmp_path / "published")
            (cache / "leaf").write_bytes(b"INVENTED-leaf-plant")
            raise OSError(errno.EIO, "INVENTED rollback failure")
        original_rename(parent, name, destination, flags)

    def late():
        if calls:
            raise ValueError("INVENTED_late")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(
                ValueError, match=r"\Apublication_rollback_incomplete\Z"
            ):
                with pinned.publish(leaf, late) as output:
                    output.write(b"INVENTED-new")
    assert (cache / "leaf").read_bytes() == b"INVENTED-leaf-plant"
    assert [p.read_bytes() for p in cache.glob("*.partial")] == [b"INVENTED-old"]


def test_a_completed_rollback_keeps_the_callers_refusal(tmp_path, monkeypatch):
    """Rollback succeeds: the caller's own reason, the old leaf, no temporary."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")

    def late():
        if (cache / "leaf").read_bytes() == b"INVENTED-new":
            raise ValueError("INVENTED_late")

    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(ValueError, match=r"\AINVENTED_late\Z"):
                with pinned.publish(leaf, late) as output:
                    output.write(b"INVENTED-new")
    assert [p.name for p in cache.iterdir()] == ["leaf"]
    assert (cache / "leaf").read_bytes() == b"INVENTED-old"


def test_a_new_leaf_substituted_after_publication_is_left_alone(tmp_path, monkeypatch):
    """``RENAME_NOREPLACE`` then a substitute: never withdraw what is not owned."""
    cache = tmp_path / "cache"
    cache.mkdir()
    original_rename = pinned._renameat2

    def renaming(parent, name, destination, flags):
        original_rename(parent, name, destination, flags)
        (cache / "leaf").rename(tmp_path / "published")
        (cache / "leaf").write_bytes(b"INVENTED-leaf-plant")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
                with pinned.publish(leaf) as output:
                    output.write(b"INVENTED-new")
    assert [p.name for p in cache.iterdir()] == ["leaf"]
    assert (cache / "leaf").read_bytes() == b"INVENTED-leaf-plant"


# Round 3e (cf2 finding 2): a pinned leaf that disappears, with no replacement,
# before it is opened is refused, never read as absent.
def test_read_refuses_a_pinned_leaf_that_disappears(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    leaf = cache / "leaf"
    leaf.write_bytes(b"INVENTED-pinned")
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as pinned_leaf:
            leaf.rename(tmp_path / "held")
            with pytest.raises(ValueError, match=r"\AINVENTED_refused\Z"):
                pinned.read(pinned_leaf)


def test_an_exchange_back_that_does_not_return_the_owned_file_unlinks_nothing(
    tmp_path, monkeypatch
):
    """The target is substituted just before the exchange back runs."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")
    original_rename = pinned._renameat2
    calls = []

    def renaming(parent, name, destination, flags):
        calls.append(flags)
        if len(calls) > 1:
            (cache / "leaf").rename(tmp_path / "published")
            (cache / "leaf").write_bytes(b"INVENTED-leaf-plant")
        original_rename(parent, name, destination, flags)

    def late():
        if calls:
            raise ValueError("INVENTED_late")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(
                ValueError, match=r"\Apublication_rollback_incomplete\Z"
            ):
                with pinned.publish(leaf, late) as output:
                    output.write(b"INVENTED-new")
    assert calls == [pinned.RENAME_EXCHANGE, pinned.RENAME_EXCHANGE]
    assert (cache / "leaf").read_bytes() == b"INVENTED-old"
    assert [p.read_bytes() for p in cache.glob("*.partial")] == [b"INVENTED-leaf-plant"]
    assert (tmp_path / "published").read_bytes() == b"INVENTED-new"


# Round 3f (cf3 finding 1): an owned entry that vanishes between its identity
# check and its unlink is absent and not owned, never a ``FileNotFoundError``.
@pytest.mark.parametrize(
    ("existing", "refused"),
    [(True, "publication_rollback_incomplete"), (False, "INVENTED_late")],
)
def test_an_owned_entry_that_vanishes_at_its_unlink_is_absent(
    tmp_path, monkeypatch, existing, refused
):
    cache = tmp_path / "cache"
    cache.mkdir()
    if existing:
        (cache / "leaf").write_bytes(b"INVENTED-old")
    original_unlink, original_rename = os.unlink, pinned._renameat2
    calls = []

    def renaming(parent, name, destination, flags):
        calls.append(flags)
        if len(calls) > 1:
            raise OSError(errno.EIO, "INVENTED rollback failure")
        original_rename(parent, name, destination, flags)

    def vanishing(name, *, dir_fd):
        os.rename(name, "INVENTED-held", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        original_unlink(name, dir_fd=dir_fd)

    def late():
        if calls:
            raise ValueError("INVENTED_late")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    monkeypatch.setattr(os, "unlink", vanishing)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(ValueError, match=rf"\A{refused}\Z"):
                with pinned.publish(leaf, late) as output:
                    output.write(b"INVENTED-new")
    assert not (cache / "leaf").exists()
    assert (cache / "INVENTED-held").read_bytes() == b"INVENTED-new"
    assert [p.read_bytes() for p in cache.glob("*.partial")] == (
        [b"INVENTED-old"] if existing else []
    )


# Round 3e edge classes: every post-exchange state, against an oracle. The
# target is the owned file, a substitute or missing; the temporary name holds
# the displaced file, a substitute or nothing; the rollback call works or
# fails. Moved entries go to ``held`` so no inode is reused or lost.
@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("temporary_state", ["displaced", "substitute", "missing"])
@pytest.mark.parametrize("target_state", ["owned", "substitute", "missing"])
def test_every_post_exchange_state_keeps_the_displaced_file(
    tmp_path, monkeypatch, target_state, temporary_state, fails
):
    cache = tmp_path / "cache"
    cache.mkdir()
    held = tmp_path / "held"
    held.mkdir()
    (cache / "leaf").write_bytes(b"INVENTED-old")
    original_rename = pinned._renameat2
    calls = []

    def move(path, body):
        path.rename(held / path.name)
        if body is not None:
            path.write_bytes(body)

    def renaming(parent, name, destination, flags):
        calls.append(flags)
        if len(calls) > 1 and fails:
            raise OSError(errno.EIO, "INVENTED rollback failure")
        original_rename(parent, name, destination, flags)
        if len(calls) == 1:
            plants = {"owned": None, "substitute": b"INVENTED-t-plant", "missing": None}
            if target_state != "owned":
                move(cache / destination, plants[target_state])
            temps = {"substitute": b"INVENTED-m-plant", "missing": None}
            if temporary_state != "displaced":
                move(cache / name, temps[temporary_state])

    def late():
        if calls:
            raise ValueError("INVENTED_late")

    # Oracle: the publication refuses with the caller's reason only when both
    # names hold what the exchange left, and with the leaf's own refusal
    # otherwise; the rollback completes only from the owned target, with an
    # entry under the temporary name and a working call.
    intact = target_state == "owned" and temporary_state == "displaced"
    original = "INVENTED_late" if intact else "INVENTED_refused"
    completes = target_state == "owned" and temporary_state != "missing" and not fails
    refused = original if completes else "publication_rollback_incomplete"
    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pinned.root(cache, "INVENTED_refused") as root:
        with pinned.target(root, "leaf") as leaf:
            with pytest.raises(ValueError) as raised:
                with pinned.publish(leaf, late) as output:
                    output.write(b"INVENTED-new")
    assert str(raised.value) == refused
    leaf_body = (cache / "leaf").read_bytes() if (cache / "leaf").exists() else None
    partials = [p.read_bytes() for p in cache.glob("*.partial")]
    everywhere = [leaf_body, *partials] + [p.read_bytes() for p in held.iterdir()]
    # The displaced file is never deleted, and never twice.
    assert everywhere.count(b"INVENTED-old") == 1
    # A refused publication is never left published.
    assert leaf_body != b"INVENTED-new"
    # Only the owned file is ever removed: every plant survives.
    if target_state == "substitute":
        assert everywhere.count(b"INVENTED-t-plant") == 1
    if temporary_state == "substitute":
        assert everywhere.count(b"INVENTED-m-plant") == 1
    if completes:
        assert partials == []
        assert leaf_body == (
            b"INVENTED-old" if temporary_state == "displaced" else b"INVENTED-m-plant"
        )
    else:
        assert leaf_body == (
            b"INVENTED-t-plant" if target_state == "substitute" else None
        )
