"""Independent mount policy for the two generator sandbox profiles.

The launcher builds the argument list. This module judges that list against
the semantic mounts of ARC-09, ARC-10 and SYN-01. It starts no process.
File descriptors and host paths are reduced to roles; an extra operation is
a problem even when a sentinel read would still fail.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import extension_tree
import sandbox_launch as launch
import sandbox_profiles as tables

READ_ONLY = "read-only"
WRITABLE = "writable"
TEMPORARY = "temporary"
DIRECTORY = "directory"
DEVICE = "device"
SYMLINK = "symlink"
SEALED = "sealed"
UNSHARED = "unshared"
SET = "set"
SCRATCH = "scratch"
OFF = "off"
VIRTUAL_ENVIRONMENT = "virtual environment"
PATH_READ_ONLY = "path-read-only"
PATH_WRITABLE = "path-writable"
OTHER = "other"
# Destinations the proof requires. They are not read from the profile tables,
# so a table edit that moves a mount fails this judge.
_PROGRAM = "/usr/bin/bwrap"
_DEVICES = "/dev"
_SCRATCH_PATH = "/tmp"
_LOADER_TARGET = "usr/lib64"
_LOADER_DEST = "/lib64"
_SYSTEM_GNU = "/usr/lib/x86_64-linux-gnu"
_SYSTEM_LIB64 = "/usr/lib64"
_SCENARIO_DEST = "/scenario/scenario.bin"
_PROFILE_VARIABLE = "EII_SANDBOX_PROFILE"
# (staging, scenario) for the two profiles. The profile object's own flags are
# not the source of this table.
_CLOSED: dict[str, tuple[bool, bool]] = {
    "build-world": (False, True),
    "build-release": (True, False),
}
_EXTENSION_FILES = (
    "extension file h3",
    "extension file h3 info",
    "extension file spatial",
    "extension file spatial info",
)
_INFO_SUFFIX = ".duckdb_extension.info"
_BINARY_SUFFIX = ".duckdb_extension"
# Argument counts from the installed bubblewrap help, so a planted option is
# parsed instead of swallowing the next mount.
_ARITY: dict[str, int] = {
    "--help": 0,
    "--version": 0,
    "--level-prefix": 0,
    "--unshare-all": 0,
    "--share-net": 0,
    "--unshare-user": 0,
    "--unshare-user-try": 0,
    "--unshare-ipc": 0,
    "--unshare-pid": 0,
    "--unshare-net": 0,
    "--unshare-uts": 0,
    "--unshare-cgroup": 0,
    "--unshare-cgroup-try": 0,
    "--disable-userns": 0,
    "--assert-userns-disabled": 0,
    "--new-session": 0,
    "--die-with-parent": 0,
    "--as-pid-1": 0,
    "--clearenv": 0,
    "--args": 1,
    "--argv0": 1,
    "--userns": 1,
    "--userns2": 1,
    "--pidns": 1,
    "--uid": 1,
    "--gid": 1,
    "--hostname": 1,
    "--chdir": 1,
    "--unsetenv": 1,
    "--lock-file": 1,
    "--sync-fd": 1,
    "--remount-ro": 1,
    "--overlay-src": 1,
    "--tmp-overlay": 1,
    "--ro-overlay": 1,
    "--exec-label": 1,
    "--file-label": 1,
    "--proc": 1,
    "--dev": 1,
    "--tmpfs": 1,
    "--mqueue": 1,
    "--dir": 1,
    "--seccomp": 1,
    "--add-seccomp-fd": 1,
    "--block-fd": 1,
    "--userns-block-fd": 1,
    "--info-fd": 1,
    "--json-status-fd": 1,
    "--cap-add": 1,
    "--cap-drop": 1,
    "--perms": 1,
    "--size": 1,
    "--setenv": 2,
    "--bind": 2,
    "--bind-try": 2,
    "--dev-bind": 2,
    "--dev-bind-try": 2,
    "--ro-bind": 2,
    "--ro-bind-try": 2,
    "--bind-fd": 2,
    "--ro-bind-fd": 2,
    "--file": 2,
    "--bind-data": 2,
    "--ro-bind-data": 2,
    "--symlink": 2,
    "--chmod": 2,
    "--overlay": 3,
}
_FLAGS: dict[str, tuple[str, str]] = {
    "--unshare-user": ("user namespace", UNSHARED),
    "--unshare-ipc": ("ipc namespace", UNSHARED),
    "--unshare-pid": ("pid namespace", UNSHARED),
    "--unshare-net": ("network", UNSHARED),
    "--unshare-uts": ("uts namespace", UNSHARED),
    "--unshare-cgroup-try": ("cgroup namespace", UNSHARED),
    "--unshare-cgroup": ("cgroup namespace", "required"),
    "--die-with-parent": ("die with parent", SET),
    "--new-session": ("new session", SET),
    "--clearenv": ("clear environment", SET),
    "--share-net": ("network", "shared"),
}


@dataclass(frozen=True)
class PolicyInput:
    """The profile, the layout, the interpreter and the generated argument list."""

    profile: tables.Profile
    layout: launch.Layout
    interpreter: launch.Interpreter
    argv: Sequence[str]


@dataclass(frozen=True)
class MountRecord:
    """One normalized operation.

    Attributes:
        role: A semantic name, never a host path.
        mode: The access the operation asks for.
    """

    role: str
    mode: str


@dataclass(frozen=True)
class PolicyJudgement:
    """The normalized mounts and every problem found in them."""

    mounts: tuple[MountRecord, ...]
    problems: tuple[str, ...]


def expected_mounts(item: PolicyInput) -> tuple[MountRecord, ...]:
    """Return the mount sequence the profile name must produce.

    Args:
        item: The request. Only the profile name and whether the interpreter
            has an alias select the sequence; the argument list is not read.
    """
    closed = _CLOSED.get(item.profile.name)
    staging, scenario = (False, False) if closed is None else closed
    records = [
        MountRecord("user namespace", UNSHARED),
        MountRecord("ipc namespace", UNSHARED),
        MountRecord("pid namespace", UNSHARED),
        MountRecord("network", UNSHARED),
        MountRecord("uts namespace", UNSHARED),
        MountRecord("cgroup namespace", UNSHARED),
        MountRecord("die with parent", SET),
        MountRecord("new session", SET),
        MountRecord("clear environment", SET),
        MountRecord("home", SCRATCH),
        MountRecord("bytecode", OFF),
        MountRecord("interpreter path", VIRTUAL_ENVIRONMENT),
        MountRecord("profile name", item.profile.name),
        MountRecord("devices", DEVICE),
        MountRecord("scratch", TEMPORARY),
        MountRecord("system library", READ_ONLY),
        MountRecord("system library lib64", READ_ONLY),
        MountRecord("loader link", SYMLINK),
        MountRecord("interpreter", READ_ONLY),
    ]
    if item.interpreter.alias is not None:
        records.append(MountRecord("interpreter alias", SYMLINK))
    records.extend(
        [
            MountRecord("virtual environment", READ_ONLY),
            MountRecord("code core", READ_ONLY),
            MountRecord("code custodian", READ_ONLY),
            MountRecord("code sandbox programs", READ_ONLY),
            MountRecord("public cache", READ_ONLY),
            MountRecord("extension folder", TEMPORARY),
            MountRecord("extension version", DIRECTORY),
            MountRecord("extension platform", DIRECTORY),
            *[MountRecord(role, READ_ONLY) for role in _EXTENSION_FILES],
            MountRecord("extension sealing", SEALED),
        ]
    )
    if scenario:
        records.append(MountRecord("scenario", READ_ONLY))
    records.append(MountRecord("vault", WRITABLE))
    if staging:
        records.append(MountRecord("release staging", WRITABLE))
    records.extend(
        [
            MountRecord("working directory", SCRATCH),
            MountRecord("root sealing", SEALED),
        ]
    )
    return tuple(records)


def normalize(item: PolicyInput) -> tuple[MountRecord, ...]:
    """Reduce an argument list to semantic mounts.

    Args:
        item: The request, including the argument list the profiles generated.
    """
    records, _problems = _parse(item)
    return tuple(records)


def judge(item: PolicyInput) -> PolicyJudgement:
    """Judge an argument list against the closed mount policy.

    Args:
        item: The profile, layout, interpreter and generated argument list.

    Returns:
        The normalized mounts and one problem per mismatch. Problems name the
        semantic role and the expected mode. An empty problem list means the
        list matches.
    """
    closed_problems = _declaration_problems(item.profile)
    records, parse_problems = _parse(item)
    if parse_problems == ["bubblewrap: missing, expected present"]:
        return PolicyJudgement(tuple(records), tuple(closed_problems + parse_problems))
    compared = _compare(records, expected_mounts(item))
    return PolicyJudgement(
        tuple(records), tuple(closed_problems + parse_problems + compared)
    )


def _declaration_problems(profile: tables.Profile) -> list[str]:
    """Report a profile object whose flags disagree with the closed table."""
    closed = _CLOSED.get(profile.name)
    if closed is None:
        return [f"profile: extra {profile.name} mount, expected absent"]
    problems = []
    staging, scenario = closed
    declared = _declared("release staging", profile.staging, staging)
    if declared is not None:
        problems.append(declared)
    declared = _declared("scenario", profile.scenario, scenario)
    if declared is not None:
        problems.append(declared)
    return problems


def _declared(role: str, actual: bool, expected: bool) -> str | None:
    if actual == expected:
        return None
    if expected:
        return f"{role}: declared absent, expected present"
    return f"{role}: declared present, expected absent"


def _parse(item: PolicyInput) -> tuple[list[MountRecord], list[str]]:
    """Walk the argument list. The command that follows the options is required."""
    argv = list(item.argv)
    if not argv or argv[0] != _PROGRAM:
        return [], ["bubblewrap: missing, expected present"]
    records: list[MountRecord] = []
    index = 1
    while index < len(argv):
        token = argv[index]
        if token == "--":
            index += 1
            break
        if not token.startswith("--"):
            break
        width = _ARITY.get(token)
        if width is None:
            records.append(MountRecord("unrecognised operation", token))
            index += 1
            continue
        arguments = argv[index + 1 : index + 1 + width]
        if len(arguments) < width:
            return records, ["argument list: truncated, expected a complete operation"]
        records.append(_operation(token, arguments, item))
        index += 1 + width
    if index >= len(argv):
        return records, ["program: missing, expected present"]
    return records, []


def _operation(option: str, arguments: Sequence[str], item: PolicyInput) -> MountRecord:
    """Turn one bubblewrap option into a semantic record."""
    flagged = _FLAGS.get(option)
    if flagged is not None:
        return MountRecord(*flagged)
    if option == "--setenv":
        return _environment(arguments[0], arguments[1], item)
    if option == "--chdir":
        mode = SCRATCH if arguments[0] == _SCRATCH_PATH else OTHER
        return MountRecord("working directory", mode)
    if option == "--dev":
        return MountRecord(_role(arguments[0], item), DEVICE)
    if option == "--tmpfs":
        return MountRecord(_role(arguments[0], item), TEMPORARY)
    if option == "--dir":
        return MountRecord(_role(arguments[0], item), DIRECTORY)
    if option == "--remount-ro":
        return _remount(arguments[0], item)
    if option == "--symlink":
        return _symlink(arguments[0], arguments[1], item)
    if option in {"--ro-bind-fd", "--bind-fd"}:
        return _descriptor(option, arguments[0], arguments[1], item)
    if option in {"--ro-bind", "--ro-bind-try"}:
        return MountRecord(_role(arguments[1], item), PATH_READ_ONLY)
    if option in {"--bind", "--bind-try"}:
        return MountRecord(_role(arguments[1], item), PATH_WRITABLE)
    if option in {"--dev-bind", "--dev-bind-try"}:
        return MountRecord(_role(arguments[1], item), "device-bind")
    if option == "--proc":
        return MountRecord("proc", "mounted")
    return MountRecord("unrecognised operation", option)


def _environment(name: str, value: str, item: PolicyInput) -> MountRecord:
    """Classify one --setenv without keeping the value."""
    if name == "HOME":
        return MountRecord("home", SCRATCH if value == _SCRATCH_PATH else OTHER)
    if name == "PYTHONDONTWRITEBYTECODE":
        return MountRecord("bytecode", OFF if value == "1" else OTHER)
    if name == "PATH":
        expected = str(item.interpreter.venv / "bin")
        mode = VIRTUAL_ENVIRONMENT if value == expected else OTHER
        return MountRecord("interpreter path", mode)
    if name == _PROFILE_VARIABLE:
        mode = item.profile.name if value == item.profile.name else OTHER
        return MountRecord("profile name", mode)
    return MountRecord("environment", SET)


def _remount(destination: str, item: PolicyInput) -> MountRecord:
    if destination == str(item.layout.extensions):
        return MountRecord("extension sealing", SEALED)
    if destination == "/":
        return MountRecord("root sealing", SEALED)
    return MountRecord(_role(destination, item), SEALED)


def _symlink(source: str, destination: str, item: PolicyInput) -> MountRecord:
    role = _role(destination, item)
    matched = role == "loader link" and source == _LOADER_TARGET
    alias = item.interpreter.alias
    if role == "interpreter alias" and alias is not None:
        matched = source == item.interpreter.real.name
    return MountRecord(role, SYMLINK if matched else OTHER)


def _descriptor(
    option: str, descriptor: str, destination: str, item: PolicyInput
) -> MountRecord:
    mode = READ_ONLY if option == "--ro-bind-fd" else WRITABLE
    if not descriptor.isdecimal():
        mode = OTHER
    return MountRecord(_role(destination, item), mode)


def _role(destination: str, item: PolicyInput) -> str:
    """Name the semantic role of a destination. Unknown paths stay unnamed."""
    layout = item.layout
    interpreter = item.interpreter
    extensions = layout.extensions
    engine = extension_tree.ENGINE
    platform = extension_tree.PLATFORM
    named = {
        _DEVICES: "devices",
        _SCRATCH_PATH: "scratch",
        "/": "root",
        _LOADER_DEST: "loader link",
        _SYSTEM_GNU: "system library",
        _SYSTEM_LIB64: "system library lib64",
        _SCENARIO_DEST: "scenario",
        str(layout.cache): "public cache",
        str(layout.vault): "vault",
        str(extensions): "extension folder",
        str(extensions / engine): "extension version",
        str(extensions / engine / platform): "extension platform",
        str(interpreter.real): "interpreter",
        str(interpreter.venv): "virtual environment",
        str(layout.code_root / "core/src"): "code core",
        str(layout.code_root / "custodian/src"): "code custodian",
        str(layout.code_root / "scripts/sandbox_inside"): "code sandbox programs",
        str(layout.code_root): "checkout",
    }
    if interpreter.alias is not None:
        named[str(interpreter.alias)] = "interpreter alias"
    if destination in named:
        return named[destination]
    folder = extensions / engine / platform
    prefix = str(folder) + "/"
    if destination.startswith(prefix):
        return _file_role(destination[len(prefix) :])
    staging = layout.code_root / "data" / "releases" / ".staging"
    path = Path(destination)
    if path == staging or staging in path.parents:
        return "release staging"
    if layout.staging is not None and destination == str(layout.staging):
        return "release staging"
    root = layout.code_root
    if path == root or root in path.parents:
        return "checkout"
    return "unrecognised"


def _file_role(name: str) -> str:
    if "/" in name:
        return "unrecognised"
    if name.endswith(_INFO_SUFFIX):
        stem = name[: -len(_INFO_SUFFIX)]
        return f"extension file {stem} info"
    if name.endswith(_BINARY_SUFFIX):
        stem = name[: -len(_BINARY_SUFFIX)]
        return f"extension file {stem}"
    return "unrecognised"


def _compare(got: Sequence[MountRecord], expected: Sequence[MountRecord]) -> list[str]:
    """Name every role whose modes differ, then any role the policy does not list."""
    issues: list[str] = []
    expected_roles = _roles(expected)
    got_roles = _roles(got)
    for role in expected_roles:
        issues.extend(_role_issues(role, _modes(got, role), _modes(expected, role)))
    for role in got_roles:
        if role in expected_roles:
            continue
        for mode in _modes(got, role):
            issues.append(f"{role}: extra {mode} mount, expected absent")
    if not issues and list(got) != list(expected):
        issues.append("mount order: differs, expected the policy order")
    return issues


def _roles(records: Sequence[MountRecord]) -> list[str]:
    found: list[str] = []
    for record in records:
        if record.role not in found:
            found.append(record.role)
    return found


def _modes(records: Sequence[MountRecord], role: str) -> list[str]:
    return [record.mode for record in records if record.role == role]


def _role_issues(role: str, have: list[str], want: list[str]) -> list[str]:
    if have == want:
        return []
    issues = []
    for got_mode, want_mode in zip(have, want, strict=False):
        if got_mode != want_mode:
            issues.append(f"{role}: mode {got_mode}, expected {want_mode}")
    if len(have) < len(want):
        for mode in want[len(have) :]:
            issues.append(f"{role}: missing, expected {mode}")
    else:
        for mode in have[len(want) :]:
            issues.append(f"{role}: extra {mode} mount, expected absent")
    return issues
