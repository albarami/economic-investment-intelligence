"""build-public: the only command that opens a public-source connection."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from eii_custodian.publicdata.atlas.config import AtlasError
from eii_custodian.publicdata.atlas.config import Config as AtlasConfig
from eii_custodian.publicdata.atlas.config import load_config as load_atlas_config
from eii_custodian.publicdata.baci.config import BaciError, Config, load_config
from eii_custodian.publicdata.fetch.build import CACHE_RELATIVE, run_build, utc_now
from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry
from eii_custodian.publicdata.fetch.report import log_line
from eii_custodian.publicdata.fetch.transport import (
    Response,
    SlotSecrets,
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


def slot_secrets(environ: Mapping[str, str], *, injected: bool) -> SlotSecrets | None:
    """Read the two slot names only when this command itself opens the connection."""
    if injected:
        return None
    return SlotSecrets(
        primary=environ.get(PRIMARY_ENV, ""),
        secondary=environ.get(SECONDARY_ENV, ""),
    )


def run(
    root: Path,
    environ: Mapping[str, str],
    args: Sequence[str],
    transport: Transport | None = None,
    sleep: Sleeper | None = None,
    stream_transport: StreamTransport | None = None,
    gravity_stream: StreamTransport | None = None,
    atlas_stream: StreamTransport | None = None,
) -> int:
    """Fetch the registry. Extra arguments are a usage error and open nothing."""
    if len(args) != 0:
        table.write_usage()
        return 2
    opener = open_https if transport is None else transport
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
        if groups:

            def reviewed_metadata(url: str) -> Response:
                for reviewed in groups:
                    if url in reviewed:
                        return open_https(url, reviewed_urls=reviewed)
                return open_https(url)

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
        opener=bound,
        slots=slots,
    )
    for line in outcome.lines:
        print(line)
    print(log_line(f"{CACHE_RELATIVE}/build-log.json"))
    if outcome.failure is not None:
        return exits.finish(
            outcome.failure.code, "build-public", outcome.failure.detail
        )
    return 0
