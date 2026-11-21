"""Closed national-centre snapshot boundary (decision 0079), never a provider switch."""

from __future__ import annotations

import errno
import fcntl
import json
import math
import os
import re
import socket
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

ROOT_ENV = "EII_GIS_SNAPSHOT_ROOT"
MACHINE_LOCK = "\0eii-gis-imagery-snapshot"
HOST = "services.gisqatar.org.qa"
BASE = f"https://{HOST}/server/rest/services/Imagery/"
SERVICES = dict(
    zip(
        (
            "1995-02",
            "2003-05",
            "2004-07",
            "2010-01",
            "2012-08",
            "2017-04",
            "2019-12",
            "2021-09",
            "2022-04",
            "2024-10",
            "2025-07",
        ),
        (
            "QatarOrtho_1995",
            "QatarSatelitte_2003",
            "QatarOrtho_2004",
            "QatarSatelitte_2010",
            "QatarSatelitte_2012",
            "QatarSatelitte_2017",
            "QatarSatelitte_2019",
            "QatarSatelitte_2021",
            "QatarOrtho",
            "QatarSatelitte2024",
            "QatarSatelitte",
        ),
        strict=True,
    )
)
MAX_LEVEL = 10
SHARD_TILES = 512
MAX_TILE_BYTES = 4 * 1024 * 1024
GENERATOR = "gis-snapshot-v1"
# A microsecond above the minimum keeps floating clock boundaries conservative.
REQUEST_INTERVAL = 0.100001


class SnapshotRefusal(ValueError):
    """Fixed reason only: no private path, credential or upstream message."""


def level_allowed(level: int) -> None:
    if type(level) is not int or not 0 <= level <= MAX_LEVEL:
        raise SnapshotRefusal(
            "level_11_deferred"
            if type(level) is int and level == 11
            else "level_refused"
        )


def service_url(date: str) -> str:
    if date not in SERVICES:
        raise SnapshotRefusal("date_refused")
    return BASE + SERVICES[date] + "/MapServer"


def tile_url(date: str, level: int, row: int, column: int) -> str:
    level_allowed(level)
    if any(type(n) is not int or n < 0 for n in (row, column)):
        raise SnapshotRefusal("tile_key_refused")
    return f"{service_url(date)}/tile/{level}/{row}/{column}"


def check_url(url: str) -> None:
    for date in SERVICES:
        service = service_url(date)
        if url == service + "?f=json":
            return
        suffix = url.removeprefix(service + "/tile/")
        if suffix != url and re.fullmatch(
            r"(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)", suffix
        ):
            level_allowed(int(suffix.split("/")[0]))
            return
    raise SnapshotRefusal("request_refused")


def configured_root(
    environ: Mapping[str, str],
    *,
    drive: Path = Path("/mnt/d"),
    drive_ready: Callable[[Path], bool] = Path.is_mount,
) -> Path:
    value = environ.get(ROOT_ENV, "")
    if not value:
        raise SnapshotRefusal("root_unset")
    root = Path(value)
    if (
        not root.is_absolute()
        or ".." in root.parts
        or root.parent != drive
        or root.name in {"data", ".private", ".env"}
    ):
        raise SnapshotRefusal("root_wrong_drive_or_placement")
    if root.resolve() != root or drive.resolve() != drive:
        raise SnapshotRefusal("root_escape")
    if not drive_ready(drive):
        raise SnapshotRefusal("root_drive_unmounted")
    return root


def safe_child(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        not root.is_absolute()
        or not path.is_relative_to(root)
        or ".." in Path(relative).parts
        or Path(relative).is_absolute()
    ):
        raise SnapshotRefusal("root_escape")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise SnapshotRefusal("root_escape")
    if not path.resolve().is_relative_to(root.resolve()):
        raise SnapshotRefusal("root_escape")
    return path


@contextmanager
def run_lock(root: Path, *, name: str = MACHINE_LOCK) -> Iterator[None]:
    try:
        machine = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    except OSError:
        raise SnapshotRefusal("lock_unavailable") from None
    try:
        try:
            machine.bind(name)
        except OSError as error:
            raise SnapshotRefusal(
                "run_locked" if error.errno == errno.EADDRINUSE else "lock_unavailable"
            ) from None
        root.mkdir(parents=True, exist_ok=True)
        path = safe_child(root, ".run.lock")
        try:
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        except OSError:
            raise SnapshotRefusal("lock_unavailable") from None
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise SnapshotRefusal(
                    "run_locked"
                    if error.errno in {errno.EAGAIN, errno.EACCES}
                    else "lock_unavailable"
                ) from None
            yield
        finally:
            os.close(fd)
    finally:
        machine.close()


class Pacer:
    """One sequential limiter for metadata, tile attempts and retries; no bursts."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.clock = clock
        self.sleep = sleep
        self.last: float | None = None
        self.next = self.clock() + REQUEST_INTERVAL

    def record_start(self, now: float) -> None:
        if not math.isfinite(now) or (self.last is not None and now - self.last < 0.1):
            raise SnapshotRefusal("rate_exceeded")
        self.last = now
        self.next = now + REQUEST_INTERVAL

    def wait(self) -> None:
        while self.clock() < self.next:
            self.sleep(self.next - self.clock())
        self.record_start(self.clock())

    def defer(self, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise SnapshotRefusal("retry_wait_invalid")
        self.next = max(self.next, self.clock() + seconds)


def _ionice() -> None:
    done = subprocess.run(
        ["/usr/bin/ionice", "-c", "3", "-p", str(os.getpid())],
        capture_output=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    if done.returncode != 0:
        raise OSError("priority unavailable")
    proof = subprocess.run(
        ["/usr/bin/ionice", "-p", str(os.getpid())],
        capture_output=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    if proof.returncode != 0 or not proof.stdout.startswith(b"idle"):
        raise OSError("priority unavailable")


def _nice() -> None:
    os.nice(max(0, 19 - os.getpriority(os.PRIO_PROCESS, 0)))
    if os.getpriority(os.PRIO_PROCESS, 0) < 19:
        raise OSError("priority unavailable")


def lower_priority(
    nice: Callable[[], None] = _nice, ionice: Callable[[], None] = _ionice
) -> None:
    try:
        nice()
        ionice()
    except (OSError, subprocess.SubprocessError):
        raise SnapshotRefusal("priority_unavailable") from None


def check_capacity(
    system_free: int,
    data_free: int,
    *,
    remaining: int,
    staging: int,
    reserve: int,
    system_reserve: int,
) -> None:
    if any(
        type(n) is not int or n < 0
        for n in (system_free, data_free, remaining, staging, reserve, system_reserve)
    ):
        raise SnapshotRefusal("disk_budget_invalid")
    if system_free < system_reserve or data_free < remaining + staging + reserve:
        raise SnapshotRefusal("disk_safety_stop")


def load_contract(path: Path | None = None) -> dict[str, object]:
    """The dedicated eleven-date registry, closed independently of live metadata."""
    selected = (
        Path(__file__).resolve().parents[4] / "publicdata/review/gis_snapshot.json"
        if path is None
        else path
    )
    try:
        row = json.loads(selected.read_bytes())
    except (OSError, ValueError):
        raise SnapshotRefusal("contract_unreadable") from None
    expected: dict[str, object] = {
        "version": 1,
        "source_id": "gis_imagery_history",
        "publisher": "national GIS centre",
        "licence_basis": "owner_decision",
        "decision_record": "0026",
        "authority": "0079",
        "max_level": 10,
        "requests_per_second": 10,
        "tile_pixels": 512,
        "format": "JPEG",
        "crs": "EPSG:2932",
        "ordinary_build": False,
        "nightly_live_fetch": False,
        "root_variable": ROOT_ENV,
        "services": [{"date": date, "url": service_url(date)} for date in SERVICES],
    }
    if row != expected or canonical_types(row) != canonical_types(expected):
        raise SnapshotRefusal("contract_refused")
    return expected


def canonical_types(row: object) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))
