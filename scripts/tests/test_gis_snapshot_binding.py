"""Planted mount widening/writing; invented files, no external tree or network."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from test_sandbox_argv import COMMAND, golden_layout

import sandbox_launch as launch
import sandbox_policy


def test_selected_files_are_the_only_new_read_only_mounts() -> None:
    profile, layout, interpreter, descriptors = golden_layout("build-release")
    selected = Path("/invented-gis-root/1995-02/level-10/2026-11-20") / (
        "a" * 64 + ".tar"
    )
    layout = replace(
        layout, imagery_root=Path("/invented-gis-root"), imagery=((selected, "a" * 64),)
    )
    descriptors = dict(descriptors)
    descriptors[selected] = 999
    argv = launch.build_argv(profile, layout, interpreter, COMMAND, descriptors)
    judgement = sandbox_policy.judge(
        sandbox_policy.PolicyInput(profile, layout, interpreter, argv)
    )
    assert judgement.problems == ()
    index = argv.index("/imagery/" + "a" * 64 + ".tar")
    assert argv[index - 2 : index] == ["--ro-bind-fd", "999"]
    for mutation in (
        [*argv[: index - 2], "--bind-fd", *argv[index - 1 :]],
        [
            *argv[: index - 2],
            "--ro-bind",
            "/invented-gis-root",
            "/imagery",
            *argv[index + 1 :],
        ],
    ):
        assert sandbox_policy.judge(
            sandbox_policy.PolicyInput(profile, layout, interpreter, mutation)
        ).problems


def test_world_profile_cannot_select_imagery() -> None:
    profile, layout, interpreter, descriptors = golden_layout("build-world")
    layout = replace(
        layout,
        imagery_root=Path("/invented"),
        imagery=((Path("/invented/a.tar"), "a" * 64),),
    )
    with pytest.raises(launch.SandboxError, match="imagery"):
        launch.build_argv(profile, layout, interpreter, COMMAND, descriptors)


@pytest.mark.parametrize(
    "relative", ["../outside.tar", "selection.json", ".env", "nested/link.tar"]
)
def test_unverified_paths_and_nonobjects_cannot_be_selected(relative: str) -> None:
    profile, layout, _, _ = golden_layout("build-release")
    root = Path("/invented-gis-root")
    layout = replace(layout, imagery_root=root, imagery=((root / relative, "a" * 64),))
    with pytest.raises(launch.SandboxError, match="imagery"):
        launch.check_profile(profile, layout)


def test_no_selection_needs_no_external_root_and_selected_unset_refuses() -> None:
    import gis_snapshot_input
    from eii_custodian.publicdata.gis.snapshot_policy import SnapshotRefusal

    _, layout, _, _ = golden_layout("build-release")
    assert gis_snapshot_input.select(layout, {}) == (layout, ())
    with pytest.raises(SnapshotRefusal, match="root_unset"):
        gis_snapshot_input.select(layout, {}, imagery=True)


def test_kernel_mount_is_read_only_hides_the_root_and_rechecks_file_hash(
    tmp_path: Path,
) -> None:
    import hashlib

    root = tmp_path / "repo"
    for relative in (
        "core/src",
        "custodian/src",
        "scripts/sandbox_inside",
        "cache",
        "vault",
        "extensions",
        "staging",
    ):
        (root / relative).mkdir(parents=True)
    source_root = tmp_path / "snapshot"
    folder = source_root / "1995-02/level-10/2026-11-20"
    folder.mkdir(parents=True)
    body = b"invented immutable shard"
    digest = hashlib.sha256(body).hexdigest()
    source = folder / (digest + ".tar")
    source.write_bytes(body)
    layout = launch.Layout(
        root,
        root / "cache",
        root / "vault",
        root / "extensions",
        staging=root / "staging",
        imagery_root=source_root,
        imagery=((source, digest),),
    )
    inside = "/imagery/" + digest + ".tar"
    program = "\n".join(
        [
            "from pathlib import Path",
            "p=Path(" + repr(inside) + ")",
            "assert p.read_bytes()==" + repr(body),
            "assert not Path(" + repr(str(source_root)) + ").exists()",
            "try:",
            "    p.write_bytes(b'planted mutation')",
            "except OSError:",
            "    print('selected-only read-only')",
            "else:",
            "    raise AssertionError('writable imagery')",
        ]
    )
    result = launch.run_in_sandbox(
        "build-release", layout, launch.python_command("-c", program)
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "selected-only read-only\n",
        "",
    )
    source.write_bytes(b"planted corruption")
    with pytest.raises(launch.SandboxError, match="hash mismatch"):
        launch.run_in_sandbox(
            "build-release", layout, launch.python_command("-c", "print('unreachable')")
        )


def test_supervisor_pid_descriptor_collision_does_not_change_mount_judgement() -> None:
    from test_sandbox_argv import bound_destinations

    # The old argv.index("3") selects the supervisor's pid, before bubblewrap.
    argv = [
        "python",
        "-I",
        "-B",
        "supervisor.py",
        "3",
        "4",
        "3,5",
        "--",
        "/usr/bin/bwrap",
        "--ro-bind-fd",
        "3",
        "/selected",
        "--bind-fd",
        "5",
        "/output",
        "/python",
    ]
    assert argv[argv.index("3") + 1] != "/selected"
    assert bound_destinations(argv) == {3: "/selected", 5: "/output"}


def test_selected_file_budget_refuses_before_opening_any_source() -> None:
    from unittest.mock import patch

    profile, layout, interpreter, _ = golden_layout("build-release")
    root = Path("/invented-gis-root")
    source = root / "1995-02/level-10/2026-11-20" / ("a" * 64 + ".tar")
    chosen = replace(
        layout,
        imagery_root=root,
        imagery=((source, "a" * 64),) * (launch.MAX_IMAGERY_FILES + 1),
    )
    with (
        patch.object(launch, "_open_one", side_effect=AssertionError("opened")),
        pytest.raises(launch.SandboxError, match="descriptor budget"),
    ):
        launch.open_sources(profile, chosen, interpreter)
    chosen = replace(layout, imagery_root=root, imagery=((source, "a" * 64),))
    with (
        patch("resource.getrlimit", return_value=(16, 16)),
        patch.object(launch, "_open_one", side_effect=AssertionError("opened")),
        pytest.raises(launch.SandboxError, match="descriptor budget"),
    ):
        launch.open_sources(profile, chosen, interpreter)
