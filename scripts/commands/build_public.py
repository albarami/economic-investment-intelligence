"""build-public: the only command that opens a public-source connection."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from earthdata_key import VARIABLE, earthdata_token
from eii_custodian.publicdata.atlas.config import AtlasError
from eii_custodian.publicdata.atlas.config import Config as AtlasConfig
from eii_custodian.publicdata.atlas.config import load_config as load_atlas_config
from eii_custodian.publicdata.baci.config import BaciError, Config, load_config
from eii_custodian.publicdata.benchmarks.config import Policy as BenchmarkPolicy
from eii_custodian.publicdata.benchmarks.config import load_policies
from eii_custodian.publicdata.fetch.build import CACHE_RELATIVE, run_build, utc_now
from eii_custodian.publicdata.fetch.registry import (
    RegistryError,
    load_registry,
)
from eii_custodian.publicdata.fetch.report import log_line
from eii_custodian.publicdata.fetch.transport import (
    Response,
    SlotReader,
    StreamTransport,
    Transport,
    open_attempt,
    open_https,
    open_https_stream,
)
from eii_custodian.publicdata.gravity.config import Config as GravityConfig
from eii_custodian.publicdata.gravity.config import GravityError
from eii_custodian.publicdata.gravity.config import load_config as load_gravity_config

from . import exits, table

Sleeper = Callable[[float], None]
PRIMARY_ENV = "COMTRADE_PRIMARY_API_KEY"
SECONDARY_ENV = "COMTRADE_SECONDARY_API_KEY"


class _SlotAccess:
    """Reads one slot variable at the moment a permitted request is sent."""

    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = environ

    def read_slot(self, slot: str) -> str:
        """Return the selected slot's variable. The other slot is not read."""
        if slot == "primary":
            name = PRIMARY_ENV
        elif slot == "secondary":
            name = SECONDARY_ENV
        else:
            return ""
        try:
            return self._environ[name]
        except KeyError:
            return ""

    def __repr__(self) -> str:
        return "_SlotAccess(redacted)"

    def __getstate__(self) -> object:
        raise TypeError("credential accessor is not serializable")


def slot_secrets(environ: Mapping[str, str], *, injected: bool) -> SlotReader | None:
    """Pass a reader only when this command itself opens the connection."""
    if injected:
        return None
    return _SlotAccess(environ)


def run(
    root: Path,
    environ: Mapping[str, str],
    args: Sequence[str],
    transport: Transport | None = None,
    sleep: Sleeper | None = None,
    stream_transport: StreamTransport | None = None,
    gravity_stream: StreamTransport | None = None,
    atlas_stream: StreamTransport | None = None,
    benchmark_stream: StreamTransport | None = None,
) -> int:
    """Fetch the registry. Extra arguments are a usage error and open nothing."""
    if len(args) != 0:
        table.write_usage()
        return 2
    token = earthdata_token(environ)
    opener = open_https if transport is None else transport
    if transport is None and token:
        opener = partial(open_https, token=token)
    pause = time.sleep if sleep is None else sleep
    bound = None if transport is not None else open_attempt
    slots = slot_secrets(environ, injected=transport is not None)
    try:
        entries = load_registry()
    except RegistryError as exc:
        return exits.finish(1, "build-public", exc.detail)
    baci_config: Config | None = None
    gravity_config: GravityConfig | None = None
    atlas_config: AtlasConfig | None = None
    stream = stream_transport
    gravity_bound = gravity_stream
    atlas_bound = atlas_stream
    benchmark_bound = benchmark_stream
    benchmark_policies: dict[str, BenchmarkPolicy] | None = None
    if transport is None:
        groups: list[tuple[str, ...]] = []
        if any(entry.source_id == "cepii_baci" for entry in entries):
            try:
                baci_config = load_config()
            except BaciError:
                return exits.finish(
                    1, "build-public", "cepii_baci configuration_unreadable NO_DATA"
                )
            groups.append(baci_config.reviewed_urls)
            if stream is None:
                stream = partial(
                    open_https_stream, reviewed_urls=baci_config.reviewed_urls
                )
        if any(entry.source_id == "cepii_gravity" for entry in entries):
            try:
                gravity_config = load_gravity_config()
            except GravityError:
                return exits.finish(
                    1, "build-public", "cepii_gravity configuration_unreadable NO_DATA"
                )
            groups.append(gravity_config.reviewed_urls)
            if gravity_bound is None:
                gravity_bound = partial(
                    open_https_stream, reviewed_urls=gravity_config.reviewed_urls
                )
        if any(entry.source_id == "atlas_complexity" for entry in entries):
            try:
                atlas_config = load_atlas_config()
            except AtlasError:
                return exits.finish(
                    1,
                    "build-public",
                    "atlas_complexity configuration_unreadable NO_DATA",
                )
            groups.append(atlas_config.reviewed_urls)
            if atlas_bound is None:
                atlas_bound = partial(
                    open_https_stream, reviewed_urls=atlas_config.reviewed_urls
                )
        try:
            benchmark_policies = load_policies()
        except ValueError:
            return exits.finish(
                1, "build-public", "benchmark configuration_unreadable NO_DATA"
            )
        benchmark_urls = tuple(
            dict.fromkeys(
                url
                for policy in benchmark_policies.values()
                for url in policy.reviewed_urls
            )
        )
        groups.append(benchmark_urls)
        if benchmark_bound is None:
            benchmark_bound = partial(open_https_stream, reviewed_urls=benchmark_urls)
        if groups:

            def reviewed_metadata(url: str) -> Response:
                for reviewed in groups:
                    if url in reviewed:
                        return open_https(url, token=token, reviewed_urls=reviewed)
                return open_https(url, token=token)

            opener = reviewed_metadata
    outcome = run_build(
        entries,
        opener,
        root / CACHE_RELATIVE,
        utc_now,
        pause,
        stream_transport=stream,
        baci_config=baci_config,
        gravity_config=gravity_config,
        atlas_config=atlas_config,
        gravity_stream=gravity_bound,
        atlas_stream=atlas_bound,
        benchmark_policies=benchmark_policies,
        benchmark_stream=benchmark_bound,
        opener=bound,
        slots=slots,
        token=token,
        key_name=VARIABLE,
    )
    for line in outcome.lines:
        print(line)
    print(log_line(f"{CACHE_RELATIVE}/build-log.json"))
    if outcome.failure is not None:
        return exits.finish(
            outcome.failure.code, "build-public", outcome.failure.detail
        )
    return 0
