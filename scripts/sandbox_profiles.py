"""Closed tables of the two generator sandbox profiles (ARC-09, ARC-10, SYN-01).

Everything the launcher mounts or sets is listed here, once. A mount that is not
in a table here cannot appear in a command line.
"""

from __future__ import annotations

from dataclasses import dataclass

BWRAP = "/usr/bin/bwrap"
# The namespaces that are unshared, then the process options. The network is
# unshared (ARC-09); no option that shares it again may appear anywhere.
ISOLATION = (
    "--unshare-user",
    "--unshare-ipc",
    "--unshare-pid",
    "--unshare-net",
    "--unshare-uts",
    "--unshare-cgroup-try",
    "--die-with-parent",
    "--new-session",
    "--clearenv",
)
# Every mount source is opened once by the launcher, checked on its descriptor
# and handed to bubblewrap by descriptor, never by path: a path can be swapped
# between the check and the mount. Bubblewrap 0.11.1 and the noble package
# 0.9.0-1ubuntu0.3 have both options; the noble release build does not.
READ_ONLY_BIND = "--ro-bind-fd"
WRITABLE_BIND = "--bind-fd"
# The extension folder is an in-memory mount of its own (--tmpfs). The launcher
# makes the version and platform folders inside it (--dir) and binds each
# checked file from its descriptor, then seals the mount (--remount-ro).
MAKE_FOLDER = "--dir"
# Read-only system folders that the interpreter's loader and C libraries need,
# and the link the loader path goes through (found by removing one at a time).
SYSTEM_READ_ONLY = ("/usr/lib/x86_64-linux-gnu", "/usr/lib64")
LOADER_LINK = ("usr/lib64", "/lib64")
# Tracked folders mounted read-only, relative to the code root. The checkout is
# not mounted as a whole: ``data/``, ``.env`` and the other folders stay hidden.
CODE_FOLDERS = ("core/src", "custodian/src", "scripts/sandbox_inside")
SCENARIO_INSIDE = "/scenario/scenario.bin"
DEVICES = "/dev"
SCRATCH = "/tmp"
SANDBOX_HOME = "/tmp"
PROFILE_VARIABLE = "EII_SANDBOX_PROFILE"
# Environment names the child sees, besides PATH and PROFILE_VARIABLE, and the
# one name that bubblewrap itself adds (PWD).
FIXED_ENVIRONMENT = (("HOME", SANDBOX_HOME), ("PYTHONDONTWRITEBYTECODE", "1"))
CHILD_ENVIRONMENT_NAMES = (
    "HOME",
    "PATH",
    "PWD",
    "PYTHONDONTWRITEBYTECODE",
    PROFILE_VARIABLE,
)
TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class Profile:
    """One sandbox profile.

    Attributes:
        name: The command that uses it.
        staging: Whether a writable release staging folder is mounted (ARC-10).
        scenario: Whether the decrypted scenario file is mounted (SYN-01).
    """

    name: str
    staging: bool
    scenario: bool


PROFILES = (
    Profile("build-world", staging=False, scenario=True),
    Profile("build-release", staging=True, scenario=False),
)
