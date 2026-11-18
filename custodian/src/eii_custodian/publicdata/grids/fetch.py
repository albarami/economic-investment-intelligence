"""Fetch dispatch for the three S2-T14 sources: catalogue, file and archive."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from eii_custodian.publicdata.fetch.allowlist import approve, host_of
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.kinds import Prepared
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    MAX_RETRIES,
    Response,
    Transport,
    TransportFault,
)

ARCHIVE = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3/{year}/"
GRID_SOURCES = frozenset(
    {"ntl_blackmarble", "worldpop_qat_agesex", "weather_openmeteo"}
)
Read = Callable[[str], Response]


def prepare_grid(
    entry: Entry, transport: Transport, sleep: Callable[[float], None], token: str
) -> Prepared:
    """Fetch one S2-T14 row. The token reaches the archive host only."""
    reader = _reader(transport, sleep)
    if entry.source_id == "ntl_blackmarble":
        return _radiance(entry, reader, token)
    return _plain(entry, reader)


def _reader(transport: Transport, sleep: Callable[[float], None]) -> Read:
    def read(url: str) -> Response:
        fault: TransportFault | None = None
        for attempt in range(ATTEMPT_LIMIT):
            try:
                response = transport(url)
            except TransportFault as exc:
                if exc.kind in {"blocked_host", "credential_missing_or_not_accepted"}:
                    raise
                fault = exc
                if attempt < MAX_RETRIES:
                    sleep(BACKOFF_S[attempt])
                    continue
                break
            refused = _refused_hop(response)
            if refused is not None:
                raise _HopRefused(refused)
            return response
        assert fault is not None
        raise fault

    return read


class _HopRefused(Exception):
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(url)


def _refused_hop(response: Response) -> str | None:
    for url in (*response.hops, response.final_url):
        if not approve(url).ok:
            return url
    return None


def _call(url: str, reader: Read) -> tuple[Response | None, AttemptFailure | None]:
    decision = approve(url)
    if not decision.ok:
        return None, AttemptFailure(1, url, "blocked_host", "allow-listed host", url)
    try:
        return reader(url), None
    except _HopRefused as exc:
        return None, AttemptFailure(
            1, exc.url, "blocked_host", "allow-listed host", exc.url
        )
    except TransportFault as exc:
        if exc.kind == "unreachable":
            return None, AttemptFailure(
                6, exc.url, "unreachable", "reachable host", "unreachable"
            )
        if exc.kind == "blocked_host":
            return None, AttemptFailure(
                1, exc.url, "blocked_host", "allow-listed host", exc.url
            )
        if exc.kind == "credential_missing_or_not_accepted":
            return None, AttemptFailure(
                1,
                exc.url,
                exc.kind,
                "accepted credential",
                "credential missing or not accepted",
            )
        return None, AttemptFailure(
            1, exc.url, "http_status", "http success", "http status"
        )


def _plain(entry: Entry, reader: Read) -> Prepared:
    response, failure = _call(entry.url, reader)
    if failure is not None or response is None:
        return _failed(entry, failure)
    return Prepared(
        response.body,
        response.final_url,
        host_of(response.final_url),
        entry.publisher,
        "",
        None,
        "",
        None,
    )


def _radiance(entry: Entry, reader: Read, token: str) -> Prepared:
    if not token:
        return _failed(
            entry,
            AttemptFailure(
                1, entry.url, "credential_absent", "archive token", "absent"
            ),
        )
    year, failure = _call(entry.url, reader)
    if failure is not None or year is None:
        return _failed(entry, failure)
    day_url = day_folder(year.body, year.final_url, entry.period)
    if day_url is None:
        return _failed(
            entry,
            AttemptFailure(
                1,
                year.final_url,
                "day_missing",
                f"{entry.period} day folder",
                "no day folder",
            ),
        )
    day, failure = _call(day_url, reader)
    if failure is not None or day is None:
        return _failed(entry, failure)
    url = granule_name(day.body, day.final_url, entry.period, entry.tile)
    if url is None:
        return _failed(
            entry,
            AttemptFailure(
                1,
                day.final_url,
                "granule_missing",
                f"{entry.period} {entry.tile}",
                "no granule",
            ),
        )
    response, failure = _call(url, reader)
    if failure is not None or response is None:
        return _failed(entry, failure)
    return Prepared(
        response.body,
        response.final_url,
        host_of(response.final_url),
        entry.publisher,
        "",
        None,
        "",
        None,
    )


class _Links(HTMLParser):
    """Collect the href targets of one archive listing."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def _links(body: bytes) -> tuple[str, ...] | None:
    """Return the raw href targets of a listing, or None when it is malformed."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    parser = _Links()
    try:
        parser.feed(text)
        parser.close()
    except ValueError:
        return None
    return tuple(parser.hrefs)


def _wanted(base: str, href: str, path: str) -> str | None:
    """Resolve one wanted href, refusing an escape, an off-host hop or a stray path."""
    if ".." in urlsplit(href).path.split("/"):
        return None
    url = urljoin(base, href)
    if host_of(url) != host_of(base) or not approve(url).ok:
        return None
    if urlsplit(url).path != path:
        return None
    return url


def day_folder(body: bytes, base: str, period: str) -> str | None:
    """Return the one distinct day address of the month, or None."""
    links = _links(body)
    if links is None:
        return None
    stamp = datetime.strptime(period + "-01", "%Y-%m-%d")
    name = f"{stamp:%j}"
    found: set[str] = set()
    for href in links:
        path = urlsplit(href).path
        if not path.endswith("/") or path.rstrip("/").rsplit("/", 1)[-1] != name:
            continue
        url = _wanted(base, href, urlsplit(base).path + name + "/")
        if url is None:
            return None
        found.add(url)
    if len(found) != 1:
        return None
    return next(iter(found))


def granule_name(body: bytes, base: str, period: str, tile: str) -> str | None:
    """Return the one distinct granule address of the month and tile, or None."""
    links = _links(body)
    if links is None:
        return None
    stamp = datetime.strptime(period + "-01", "%Y-%m-%d")
    prefix = f"VNP46A3.A{stamp:%Y%j}.{tile}."
    found: set[str] = set()
    for href in links:
        name = urlsplit(href).path.rsplit("/", 1)[-1]
        if not name.startswith(prefix) or not name.endswith(".h5"):
            continue
        url = _wanted(base, href, urlsplit(base).path + name)
        if url is None:
            return None
        found.add(url)
    if len(found) != 1:
        return None
    return next(iter(found))


def _failed(entry: Entry, failure: AttemptFailure | None) -> Prepared:
    problem = (
        failure
        if failure is not None
        else AttemptFailure(
            1, entry.url, "check_failed", "passed check", "check failed"
        )
    )
    return Prepared(b"", problem.url, "", entry.publisher, "", None, "", problem)
