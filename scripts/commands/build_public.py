"""build-public: the only command that opens a public-source connection."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from cdse_key import cdse_credentials
from earthdata_key import VARIABLE, earthdata_token
from eii_custodian.publicdata.atlas.config import AtlasError
from eii_custodian.publicdata.atlas.config import Config as AtlasConfig
from eii_custodian.publicdata.atlas.config import load_config as load_atlas_config
from eii_custodian.publicdata.baci.config import BaciError, Config, load_config
from eii_custodian.publicdata.benchmarks.config import Policy as BenchmarkPolicy
from eii_custodian.publicdata.benchmarks.config import load_policies
from eii_custodian.publicdata.company_web.build import run_company_web
from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.build import (
    CACHE_RELATIVE,
    run_build,
    run_tenders_only,
    utc_now,
)
from eii_custodian.publicdata.fetch.certificate_pins import PinError
from eii_custodian.publicdata.fetch.own_run import OWN_RUN_CACHE_RELATIVE
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
from eii_custodian.publicdata.singles import tenders

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
    large_stream: StreamTransport | None = None,
) -> int:
    """Validate the arguments before any input or credential read.

    No argument, ``--seed N`` (the draw seed), ``--company-web``,
    ``--seed N --resume``, ``--tenders-only [--resume]``, ``--cdse-backup`` alone or
    ``--gis-imagery-snapshot`` alone;
    anything else is a usage error and opens nothing.
    """
    if tuple(args) == ("--company-web",):
        return run_company_web(
            root,
            environ,
            open_https if transport is None else transport,
            time.sleep if sleep is None else sleep,
        )
    if tuple(args) == ("--gis-imagery-snapshot",):
        from eii_custodian.publicdata.gis.snapshot_runner import run as run_snapshot

        return run_snapshot(environ)
    if tuple(args) == ("--cdse-backup",):
        credentials = cdse_credentials(environ)
        reason = (
            "credentials_absent" if credentials is None else "provider_contract_pending"
        )
        print(f"satellite_cdse_backup omitted: {reason}")
        return 0
    tenders_only = tuple(args) in {("--tenders-only",), ("--tenders-only", "--resume")}
    seed = 0
    resume = len(args) == 3 and args[2] == "--resume"
    if args and not tenders_only:
        if (
            (len(args) != 2 and not resume)
            or args[0] != "--seed"
            or re.fullmatch(r"[0-9]{1,20}", args[1]) is None
        ):
            table.write_usage()
            return 2
        seed = int(args[1])
    token = "" if tenders_only else earthdata_token(environ)
    opener = open_https if transport is None else transport
    if transport is None and token:
        opener = partial(open_https, token=token)
    pause = time.sleep if sleep is None else sleep
    bound = None if transport is not None else open_attempt
    slots = (
        None if tenders_only else slot_secrets(environ, injected=transport is not None)
    )
    try:
        entries = tuple(
            entry
            for entry in load_registry()
            if entry.kind not in {"cdse_backup", "company_web"}
        )
    except RegistryError as exc:
        return exits.finish(1, "build-public", exc.detail)
    if tenders_only:
        entries = tuple(entry for entry in entries if entry.key == "tenders_pub")
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
        if not tenders_only:
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
                benchmark_bound = partial(
                    open_https_stream, reviewed_urls=benchmark_urls
                )
        terms_urls = frozenset(entry.terms_url for entry in entries if entry.terms_url)

        def reviewed_metadata(url: str) -> Response:
            if url in terms_urls and host_of(url) == tenders.TENDER_HOST:
                # Reuse the tender adapter's inspected, registry-pinned chain
                # for this host's terms only. A missing chain stays a refusal.
                chain_rows = [
                    entry
                    for entry in entries
                    if entry.key == "tenders_pub"
                    and entry.fetch_host == tenders.TENDER_HOST
                ]
                if len(chain_rows) != 1:
                    raise PinError("certificate_chain_incomplete")
                return tenders.terms_https(chain_rows[0], url)
            for reviewed in groups:
                if url in reviewed:
                    return open_https(url, token=token, reviewed_urls=reviewed)
            return open_https(url, token=token)

        opener = reviewed_metadata
    if tenders_only:
        outcome = run_tenders_only(
            entries,
            opener,
            root / CACHE_RELATIVE,
            root / OWN_RUN_CACHE_RELATIVE,
            utc_now,
            pause,
            environ=environ,
            resume=len(args) == 2,
        )
        for line in outcome.lines:
            print(line)
        print(log_line(f"{OWN_RUN_CACHE_RELATIVE}/build-log.json"))
        return (
            exits.finish(outcome.failure.code, "build-public", outcome.failure.detail)
            if outcome.failure is not None
            else 0
        )
    outcome = run_build(
        entries,
        opener,
        root / CACHE_RELATIVE,
        utc_now,
        pause,
        stream_transport=stream,
        large_stream=(
            open_https_stream
            if transport is None and large_stream is None
            else large_stream
        ),
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
        environ=environ,
        seed=seed,
        resume=resume,
    )
    for line in outcome.lines:
        print(line)
    print(log_line(f"{CACHE_RELATIVE}/build-log.json"))
    if outcome.failure is not None:
        return exits.finish(
            outcome.failure.code, "build-public", outcome.failure.detail
        )
    return 0
