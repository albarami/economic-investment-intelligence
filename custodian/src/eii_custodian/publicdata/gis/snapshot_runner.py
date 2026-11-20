"""Dedicated resumable acquisition; ordinary/nightly public builds never enter it."""

from __future__ import annotations

import json
import re
import shutil
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib import import_module
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, utc
from eii_custodian.publicdata.fetch.transport import (
    BACKOFF_S,
    Response,
    Transport,
    TransportFault,
    open_gis_snapshot,
)

from .snapshot_archive import Archive, canonical, digest
from .snapshot_policy import (
    GENERATOR,
    SERVICES,
    SHARD_TILES,
    Pacer,
    SnapshotRefusal,
    check_capacity,
    check_url,
    configured_root,
    level_allowed,
    load_contract,
    lower_priority,
    run_lock,
    safe_child,
    service_url,
    tile_url,
)
from .snapshot_scheme import Scheme, enumerate_tiles, read_scheme

Clock = Callable[[], str]
Watch = Callable[[], None]
GIB = 1024**3


def _retry_wait(value: str, now: str) -> float:
    if not value:
        return 0
    if value.isascii() and value.isdigit():
        return float(value)
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            raise ValueError
        return max(
            0.0,
            (date - datetime.fromisoformat(now.replace("Z", "+00:00"))).total_seconds(),
        )
    except (ValueError, TypeError, OverflowError):
        raise SnapshotRefusal("retry_wait_invalid") from None


def request(
    url: str, transport: Transport, pace: Pacer, now: Clock, watch: Watch
) -> bytes:
    check_url(url)
    for attempt in range(4):
        watch()
        pace.wait()
        watch()
        try:
            response = transport(url)
        except TransportFault as error:
            if error.kind in {"redirect", "blocked_host"}:
                raise SnapshotRefusal("redirect_refused") from None
            response = Response(
                url, b"", (), evidence={"http_status": error.status or 503}
            )
        if response.hops or response.final_url != url:
            raise SnapshotRefusal("redirect_refused")
        check_url(response.final_url)
        status = response.evidence.get("http_status", 200)
        if status == 200:
            if not response.body or len(response.body) > 4 * 1024 * 1024:
                raise SnapshotRefusal("response_bytes_or_gap")
            return response.body
        if status not in {429, 500, 502, 503, 504} or attempt == 3:
            raise SnapshotRefusal("request_failed " + url)
        wait = max(
            BACKOFF_S[attempt],
            _retry_wait(response.headers.get("Retry-After", ""), now()),
        )
        pace.defer(wait)
    raise SnapshotRefusal("request_failed " + url)


def _input(archive: Path, name: str, body: bytes, now: str) -> str:
    identity = digest(body)
    side: dict[str, object] = {
        "source_id": "gis_imagery_history",
        "key": "gis_imagery_history",
        "retrieved_utc": now,
        "generator_version": GENERATOR,
    }
    publish_snapshot(
        safe_child(archive, f"inputs/{name}"), "json", body, side, identity=identity
    )
    return identity


def acquire(
    root: Path,
    date: str,
    land_qng: BaseGeometry,
    boundary_sha256: str,
    transport: Transport,
    pace: Pacer,
    now: Clock,
    watch: Watch,
    *,
    levels: tuple[int, ...] | None = None,
    expected_scheme: Scheme | None = None,
) -> tuple[str, ...]:
    """Only a locked low-priority supervisor calls this per-date worker in production."""
    for level in levels or ():
        level_allowed(level)
    metadata = request(service_url(date) + "?f=json", transport, pace, now, watch)
    scheme = read_scheme(metadata)
    if expected_scheme is not None and not scheme.compatible(expected_scheme):
        raise SnapshotRefusal("metadata_scheme_changed")
    selected_levels = scheme.levels if levels is None else levels
    tiles = enumerate_tiles(scheme, land_qng, levels=selected_levels)
    manifests = []
    for level in sorted(set(selected_levels)):
        selected = [list(tile.key()) for tile in tiles if tile.level == level]
        directory = safe_child(root, f"{date}/level-{level:02d}")
        enumeration: dict[str, Any] = {
            "date": date,
            "level": level,
            "metadata_sha256": digest(metadata),
            "boundary_sha256": boundary_sha256,
            "tiles": selected,
            "generator_version": GENERATOR,
            "inputs": {
                "metadata": digest(metadata),
                "boundary": digest(canonical(mapping(land_qng))),
            },
        }
        archive = Archive(directory, enumeration)
        _input(directory, "metadata", metadata, now())
        _input(directory, "boundary", canonical(mapping(land_qng)), now())
        count = (len(selected) + SHARD_TILES - 1) // SHARD_TILES
        for shard in range(count):
            watch()
            if archive.has_shard(shard):
                continue

            def bodies(
                keys: list[list[int]],
            ) -> Iterator[tuple[tuple[int, int, int], bytes]]:
                for lev, row, col in keys:
                    body = request(
                        tile_url(date, lev, row, col), transport, pace, now, watch
                    )
                    yield (lev, row, col), body

            archive.write_shard_stream(shard, bodies(archive.expected(shard)), now)
        manifests.append(archive.complete(list(range(count)), now()))
    return tuple(manifests)


class DiskWatch:
    """Fail closed before start and every attempt/shard; no cost stop exists."""

    def __init__(
        self,
        root: Path,
        budget: Mapping[str, int],
        *,
        disk: Callable[[Path], Any] = shutil.disk_usage,
        transferred: Callable[[], int] = lambda: 0,
    ) -> None:
        self.root, self.budget, self.disk = root, budget, disk
        self.transferred = transferred
        self.existing = 0
        for path in root.rglob("*.tar"):
            safe_child(root, str(path.relative_to(root)))
            if path.is_file():
                self.existing += path.stat().st_size
        self.initial = (disk(Path("/")).free, disk(root.parent).free)
        self.started = time.monotonic()
        self.reported = False
        self.check()

    def check(self) -> None:
        system, data = self.disk(Path("/")).free, self.disk(self.root.parent).free
        # Only this acquisition's bytes reduce its remaining estimate. Other jobs
        # consuming the drive cannot lower the safety threshold.
        remaining = max(
            0, self.budget["remaining_bytes"] - self.existing - self.transferred()
        )
        check_capacity(
            system,
            data,
            remaining=remaining,
            staging=self.budget["staging_bytes"],
            reserve=self.budget["reserve_bytes"],
            system_reserve=self.budget["system_reserve_bytes"],
        )
        if time.monotonic() - self.started >= 3600 and not self.reported:
            self.reported = True
            print(
                json.dumps(
                    {
                        "event": "first_hour_disk",
                        "system_free_change": system - self.initial[0],
                        "data_free_change": data - self.initial[1],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )


class Measurements:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.started = time.monotonic()
        self.requests = self.bytes = self.failures = 0
        self.reported = False

    def __call__(self, url: str) -> Response:
        self.requests += 1
        try:
            response = self.transport(url)
        except TransportFault:
            self.failures += 1
            self.report()
            raise
        self.bytes += len(response.body)
        self.failures += int(response.evidence.get("http_status", 200) != 200)
        self.report()
        return response

    def report(self, *, final: bool = False) -> None:
        elapsed = time.monotonic() - self.started
        if final or (elapsed >= 3600 and not self.reported):
            self.reported = True
            print(
                json.dumps(
                    {
                        "event": "snapshot_measurement",
                        "requests": self.requests,
                        "elapsed_seconds": elapsed,
                        "bytes": self.bytes,
                        "failures": self.failures,
                        "requests_per_second": self.requests / elapsed
                        if elapsed
                        else 0,
                        "bytes_per_second": self.bytes / elapsed if elapsed else 0,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )


def pin_boundary(root: Path, body: bytes, expected: str) -> str:
    """Retain the reviewed source geometry and its Public chain, not only its hash."""
    try:
        side = json.loads(safe_child(root, "national-land.meta.json").read_bytes())
        fields = {
            "source_id",
            "key",
            "publisher",
            "fetch_url",
            "licence_basis",
            "licence_id",
            "decision_record",
            "terms_words",
            "terms_read_on",
            "retrieved_utc",
            "sha256",
            "method_version",
            "upstream_sha256",
        }
        if set(side) != fields or any(
            not isinstance(value, str) for value in side.values()
        ):
            raise SnapshotRefusal("boundary_lineage_invalid")
        if (
            side["sha256"] != expected
            or digest(body) != expected
            or re.fullmatch(r"[a-f0-9]{64}", side["upstream_sha256"]) is None
        ):
            raise SnapshotRefusal("boundary_lineage_hash")
        if not approve(side["fetch_url"]).ok or not all(
            side[name]
            for name in (
                "source_id",
                "key",
                "publisher",
                "terms_words",
                "method_version",
            )
        ):
            raise SnapshotRefusal("boundary_lineage_invalid")
        if (
            side["licence_basis"] not in {"dataset", "owner_decision"}
            or (side["licence_basis"] == "dataset" and not side["licence_id"])
            or (
                side["licence_basis"] == "owner_decision"
                and side["decision_record"] != "0026"
            )
        ):
            raise SnapshotRefusal("boundary_lineage_basis")
        utc(side["retrieved_utc"])
        if side["terms_read_on"] != "pending":
            datetime.fromisoformat(side["terms_read_on"])
        publish_snapshot(
            safe_child(root, "boundary-source"), "json", body, side, identity=expected
        )
        return expected
    except (OSError, ValueError, TypeError, KeyError):
        raise SnapshotRefusal("boundary_lineage_invalid") from None


def run(environ: Mapping[str, str]) -> int:
    """Lead-shell mode. Configuration is deliberately external; no cache fallback."""
    measured = Measurements(open_gis_snapshot)
    try:
        load_contract()
        root = configured_root(environ)
        with run_lock(root):
            lower_priority()
            # The lead stages only the reviewed public national-land boundary here.
            # No ordinary public-cache or private path is accepted as an argument.
            job = json.loads(safe_child(root, "job.json").read_bytes())
            if set(job) != {
                "boundary_sha256",
                "remaining_bytes",
                "staging_bytes",
                "reserve_bytes",
                "system_reserve_bytes",
            }:
                raise SnapshotRefusal("job_fields")
            budget = {
                name: job[name]
                for name in (
                    "remaining_bytes",
                    "staging_bytes",
                    "reserve_bytes",
                    "system_reserve_bytes",
                )
            }
            if (
                any(type(n) is not int for n in budget.values())
                or budget["remaining_bytes"] <= 0
                or budget["staging_bytes"] < 3 * GIB
                or budget["reserve_bytes"] < 5 * GIB
                or budget["system_reserve_bytes"] < 2 * GIB
            ):
                raise SnapshotRefusal("disk_budget_invalid")
            watch = DiskWatch(root, budget, transferred=lambda: measured.bytes)
            boundary = safe_child(root, "national-land.geojson").read_bytes()
            if digest(boundary) != job["boundary_sha256"]:
                raise SnapshotRefusal("boundary_identity_changed")
            boundary_source = pin_boundary(root, boundary, job["boundary_sha256"])
            document = json.loads(boundary)
            transform_geom = import_module("rasterio.warp").transform_geom
            land = shape(transform_geom("EPSG:4326", "EPSG:2932", document))

            def now() -> str:
                return datetime.now(UTC).isoformat()

            def checkpoint() -> None:
                watch.check()
                measured.report()

            def watched_sleep(seconds: float) -> None:
                until = time.monotonic() + seconds
                while time.monotonic() < until:
                    checkpoint()
                    remaining = until - time.monotonic()
                    if remaining > 0:
                        time.sleep(min(1.0, remaining))
                checkpoint()

            pace = Pacer(sleep=watched_sleep)
            # Establish one compatible scheme across every date before tile activation.
            schemes = [
                read_scheme(
                    request(
                        service_url(date) + "?f=json", measured, pace, now, checkpoint
                    )
                )
                for date in SERVICES
            ]
            if any(not scheme.compatible(schemes[0]) for scheme in schemes[1:]):
                raise SnapshotRefusal("metadata_scheme_changed")
            for scheme in schemes:
                enumerate_tiles(scheme, land, levels=(scheme.levels[0],))
            complete = {}
            for date in SERVICES:
                manifests = acquire(
                    root,
                    date,
                    land,
                    job["boundary_sha256"],
                    measured,
                    pace,
                    now,
                    checkpoint,
                    expected_scheme=schemes[0],
                )
                complete[date] = {
                    str(level): identity
                    for level, identity in zip(
                        schemes[0].levels, manifests, strict=True
                    )
                }
            body = canonical(
                {
                    "version": GENERATOR,
                    "dates": complete,
                    "complete": True,
                    "boundary_sha256": job["boundary_sha256"],
                    "boundary_source": boundary_source,
                }
            )
            publish_snapshot(
                safe_child(root, "all-dates"),
                "json",
                body,
                {
                    "source_id": "gis_imagery_history",
                    "key": "gis_imagery_history",
                    "retrieved_utc": now(),
                },
                identity=digest(body),
            )
            print("gis_imagery_history complete_manifest=" + digest(body), flush=True)
        return 0
    except SnapshotRefusal as error:
        print(
            "gis_imagery_history " + str(error) + "; resumable state retained",
            flush=True,
        )
        return 1
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        # Fixed diagnostic. Never include a path, configuration body or upstream error.
        print(
            "gis_imagery_history snapshot_refused; resumable state retained", flush=True
        )
        return 1
    finally:
        measured.report(final=True)
