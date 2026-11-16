"""build-public: the only command that opens a public-source connection."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from eii_custodian.publicdata.baci.config import BaciError, Config, load_config
from eii_custodian.publicdata.fetch.build import CACHE_RELATIVE, run_build, utc_now
from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry
from eii_custodian.publicdata.fetch.report import log_line
from eii_custodian.publicdata.fetch.transport import (
    Response,
    StreamTransport,
    Transport,
    open_https,
    open_https_stream,
)

from . import exits, table

Sleeper = Callable[[float], None]


def run(
    root: Path,
    environ: Mapping[str, str],
    args: Sequence[str],
    transport: Transport | None = None,
    sleep: Sleeper | None = None,
    stream_transport: StreamTransport | None = None,
) -> int:
    """Fetch the registry. Extra arguments are a usage error and open nothing."""
    del environ
    if len(args) != 0:
        table.write_usage()
        return 2
    opener = open_https if transport is None else transport
    pause = time.sleep if sleep is None else sleep
    try:
        entries = load_registry()
    except RegistryError as exc:
        return exits.finish(1, "build-public", exc.detail)
    baci_config: Config | None = None
    stream = stream_transport
    if transport is None and any(entry.source_id == "cepii_baci" for entry in entries):
        try:
            baci_config = load_config()
        except BaciError:
            return exits.finish(
                1, "build-public", "cepii_baci configuration_unreadable NO_DATA"
            )
        reviewed = baci_config.reviewed_urls

        def reviewed_metadata(url: str) -> Response:
            if url in reviewed:
                return open_https(url, reviewed_urls=reviewed)
            return open_https(url)

        opener = reviewed_metadata
        if stream is None:
            stream = partial(open_https_stream, reviewed_urls=reviewed)
    outcome = run_build(
        entries,
        opener,
        root / CACHE_RELATIVE,
        utc_now,
        pause,
        stream_transport=stream,
        baci_config=baci_config,
    )
    for line in outcome.lines:
        print(line)
    print(log_line(f"{CACHE_RELATIVE}/build-log.json"))
    if outcome.failure is not None:
        return exits.finish(
            outcome.failure.code, "build-public", outcome.failure.detail
        )
    return 0
