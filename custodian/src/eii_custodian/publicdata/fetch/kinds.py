"""Fetcher kinds this task builds: portal, paged layer, HTTPS file, terms page."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

from eii_custodian.publicdata.fetch.allowlist import approve, host_of
from eii_custodian.publicdata.fetch.checks import (
    AttemptFailure,
    count_failure,
    period_failure,
    schema_failure,
)
from eii_custodian.publicdata.fetch.registry import Entry, RegistryError
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    MAX_RETRIES,
    Response,
    Transport,
    TransportFault,
)

ARC_GIS_PAGE_SIZE = 2000
_EXPORT_SUFFIX = "/exports/json"
_FORBIDDEN = "forbids the use made here"
_FORBIDDEN_ALT = "forbid the use made here"
_CC_BY_4_TEXT = "CC BY"
_CC_BY_4_URL = "https://creativecommons.org/licenses/by/4.0/"
_SPACE_RUN = re.compile(r"\s+")

Read = Callable[[str], Response]


@dataclass(frozen=True)
class Prepared:
    """Bytes ready to store, or a failure that stores nothing."""

    body: bytes
    fetch_url: str
    fetch_host: str
    publisher: str
    source_modified: str
    row_count: int | None
    terms_sha256: str
    failure: AttemptFailure | None
    portal_licence: str = ""
    portal_licence_url: str = ""


def prepare(
    entry: Entry, transport: Transport, sleep: Callable[[float], None]
) -> Prepared:
    """Fetch one row through the transport seam and apply its declared checks."""
    reader = _reader(transport, sleep)
    if entry.kind == "portal_dataset":
        return _portal(entry, reader)
    if entry.kind == "paged_layer":
        return _paged(entry, reader)
    if entry.kind == "terms_page":
        return _terms(entry, reader)
    return _file(entry, reader)


def _reader(transport: Transport, sleep: Callable[[float], None]) -> Read:
    def read(url: str) -> Response:
        fault: TransportFault | None = None
        for attempt in range(ATTEMPT_LIMIT):
            try:
                response = transport(url)
            except TransportFault as exc:
                if exc.kind == "blocked_host":
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


def _refused_hop(response: Response) -> str | None:
    for url in (*response.hops, response.final_url):
        if not approve(url).ok:
            return url
    return None


class _HopRefused(Exception):
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(url)


def _call(
    entry: Entry, url: str, reader: Read
) -> tuple[Response | None, AttemptFailure | None]:
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
        return None, AttemptFailure(
            1, exc.url, "http_status", "http success", "http status"
        )


def _portal(entry: Entry, reader: Read) -> Prepared:
    meta_url = _metadata_url(entry.url)
    meta, failure = _call(entry, meta_url, reader)
    if failure is not None or meta is None:
        return _failed(entry, failure)
    export, failure = _call(entry, entry.url, reader)
    if failure is not None or export is None:
        return _failed(entry, failure)
    observed = _portal_meta(meta.body)
    if observed is None:
        return _failed(
            entry,
            AttemptFailure(
                1,
                meta.final_url,
                "metadata_unreadable",
                "portal metadata",
                "unreadable",
            ),
        )
    publisher, licence, licence_url, modified = observed
    if publisher == "":
        return _failed(
            entry,
            AttemptFailure(
                1,
                meta.final_url,
                "publisher_missing",
                entry.publisher or "publisher",
                "",
            ),
        )
    if not _same_publisher(publisher, entry.publisher):
        return _failed(
            entry,
            AttemptFailure(
                1, meta.final_url, "publisher_mismatch", entry.publisher, publisher
            ),
        )
    if licence == "":
        return _failed(
            entry,
            AttemptFailure(
                1,
                meta.final_url,
                "licence_missing",
                _licence_expected(entry.licence_id),
                _licence_observed("", licence_url),
            ),
        )
    if not _licence_matches(licence, licence_url, entry.licence_id):
        return _failed(
            entry,
            AttemptFailure(
                1,
                meta.final_url,
                "licence_mismatch",
                _licence_expected(entry.licence_id),
                _licence_observed(licence, licence_url),
            ),
        )
    rows = _json_rows(export.body)
    counted = count_failure(entry, rows, export.final_url)
    if counted is not None:
        return _failed(entry, counted)
    schema = schema_failure(entry, rows, export.final_url)
    if schema is not None:
        return _failed(entry, schema)
    period = period_failure(entry, rows, export.final_url)
    if period is not None:
        return _failed(entry, period)
    count = len(rows) if rows is not None else None
    return Prepared(
        export.body,
        export.final_url,
        host_of(export.final_url),
        publisher,
        modified,
        count,
        "",
        None,
        licence,
        licence_url,
    )


def _paged(entry: Entry, reader: Read) -> Prepared:
    layer = entry.layer
    if layer is None:
        raise RegistryError("paged_layer requires layer")
    count_url = _query(
        entry.url,
        layer,
        {"where": "1=1", "returnCountOnly": "true", "f": "json"},
    )
    counted, failure = _call(entry, count_url, reader)
    if failure is not None or counted is None:
        return _failed(entry, failure)
    total = _arcgis_count(counted.body)
    if total is None:
        return _failed(
            entry,
            AttemptFailure(1, counted.final_url, "short_total", "count", "unreadable"),
        )
    features: list[object] = []
    offset = 0
    final = counted.final_url
    while offset < total:
        page_url = _query(
            entry.url,
            layer,
            {
                "where": "1=1",
                "outFields": "*",
                "resultOffset": str(offset),
                "resultRecordCount": str(ARC_GIS_PAGE_SIZE),
                "f": "json",
            },
        )
        page, failure = _call(entry, page_url, reader)
        if failure is not None or page is None:
            return _failed(entry, failure)
        batch = _features(page.body)
        if batch is None:
            return _failed(
                entry,
                AttemptFailure(
                    1, page.final_url, "short_total", "features", "unreadable"
                ),
            )
        final = page.final_url
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        if len(batch) < ARC_GIS_PAGE_SIZE:
            break
    if len(features) != total:
        return _failed(
            entry,
            AttemptFailure(1, final, "short_total", str(total), str(len(features))),
        )
    body = json.dumps({"count": total, "features": features}, sort_keys=True).encode(
        "utf-8"
    )
    return Prepared(body, final, host_of(final), entry.publisher, "", total, "", None)


def _file(entry: Entry, reader: Read) -> Prepared:
    response, failure = _call(entry, entry.url, reader)
    if failure is not None or response is None:
        return _failed(entry, failure)
    rows = _json_rows(response.body)
    counted = count_failure(entry, rows, response.final_url)
    if counted is not None:
        return _failed(entry, counted)
    return Prepared(
        response.body,
        response.final_url,
        host_of(response.final_url),
        entry.publisher,
        "",
        len(rows) if rows is not None else None,
        "",
        None,
    )


def _terms(entry: Entry, reader: Read) -> Prepared:
    page, failure = _call(entry, entry.url, reader)
    if failure is not None or page is None:
        return _failed(entry, failure)
    terms_hash = ""
    if entry.terms_url:
        terms, failure = _call(entry, entry.terms_url, reader)
        if failure is not None or terms is None:
            return _failed(entry, failure)
        terms_hash = terms_text_sha256(terms.body)
        if _forbids(entry, terms.body):
            return _failed(
                entry,
                AttemptFailure(
                    1,
                    terms.final_url,
                    "terms_forbid",
                    "terms allow the use",
                    "terms forbid the use",
                ),
            )
    return Prepared(
        page.body,
        page.final_url,
        host_of(page.final_url),
        entry.publisher,
        "",
        None,
        terms_hash,
        None,
    )


def _forbids(entry: Entry, body: bytes) -> bool:
    if entry.source_id == "busy_gmaps" or entry.terms_watch:
        return False
    text = body.decode("utf-8", errors="replace").casefold()
    return _FORBIDDEN in text or _FORBIDDEN_ALT in text


@dataclass(frozen=True)
class RecordedTerms:
    """The terms page for a row that names terms_forbid. The source URL is not read."""

    sha256: str
    phrase_present: bool
    failure: AttemptFailure | None


def read_recorded_terms(
    entry: Entry, transport: Transport, sleep: Callable[[float], None]
) -> RecordedTerms:
    """Read terms_url through the transport seam and compare the recorded phrases."""
    reader = _reader(transport, sleep)
    terms, failure = _call(entry, entry.terms_url, reader)
    if failure is not None or terms is None:
        return RecordedTerms("", False, failure)
    return RecordedTerms(
        terms_text_sha256(terms.body),
        _phrase_present(terms.body, entry.terms_forbid),
        None,
    )


def _phrase_present(body: bytes, phrases: tuple[str, ...]) -> bool:
    """Return whether any phrase is present after case folding and collapsed space."""
    text = _folded(body.decode("utf-8", errors="replace"))
    return any(_folded(phrase) in text for phrase in phrases)


def _folded(value: str) -> str:
    """Fold case and collapse each run of white space to one space."""
    return _SPACE_RUN.sub(" ", value.casefold()).strip()


def _failed(entry: Entry, failure: AttemptFailure | None) -> Prepared:
    problem = (
        failure
        if failure is not None
        else AttemptFailure(
            1, entry.url, "check_failed", "passed check", "check failed"
        )
    )
    return Prepared(b"", problem.url, "", entry.publisher, "", None, "", problem)


def _metadata_url(export_url: str) -> str:
    if export_url.endswith(_EXPORT_SUFFIX):
        return export_url[: -len(_EXPORT_SUFFIX)]
    return export_url


def _portal_meta(body: bytes) -> tuple[str, str, str, str] | None:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    metas = loaded.get("metas")
    if not isinstance(metas, dict):
        return None
    default = metas.get("default")
    if not isinstance(default, dict):
        return None
    publisher = default.get("publisher")
    licence = default.get("license")
    licence_url = default.get("license_url")
    modified = default.get("modified")
    if not isinstance(publisher, str):
        publisher = ""
    if not isinstance(licence, str):
        licence = ""
    if not isinstance(licence_url, str):
        licence_url = ""
    if not isinstance(modified, str):
        modified = ""
    return publisher.strip(), licence.strip(), licence_url.strip(), modified.strip()


def _same_publisher(observed: str, expected: str) -> bool:
    """Return whether two publisher names match after case folding and space runs."""
    return _folded_publisher(observed) == _folded_publisher(expected)


def _folded_publisher(name: str) -> str:
    """Fold case and collapse each run of white space to one space."""
    return _SPACE_RUN.sub(" ", name.casefold()).strip()


def _licence_expected(licence_id: str) -> str:
    """Return the portal statement a registry licence id requires."""
    if licence_id == "CC-BY-4.0":
        return _licence_observed(_CC_BY_4_TEXT, _CC_BY_4_URL)
    return _licence_observed(licence_id, "")


def _licence_observed(text: str, url: str) -> str:
    """Return the portal licence text and URL as read."""
    return f"text:{text} url:{url}"


def _licence_matches(text: str, url: str, licence_id: str) -> bool:
    """CC-BY-4.0 passes only for the portal's own CC BY text and 4.0 URL."""
    if licence_id == "CC-BY-4.0":
        return text == _CC_BY_4_TEXT and url == _CC_BY_4_URL
    return text == licence_id


def _json_rows(body: bytes) -> list[object] | None:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if isinstance(loaded, list):
        return loaded
    if isinstance(loaded, dict):
        results = loaded.get("results")
        if isinstance(results, list):
            return results
    return None


def _arcgis_count(body: bytes) -> int | None:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    count = loaded.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return None
    return count


def _features(body: bytes) -> list[object] | None:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    features = loaded.get("features")
    if not isinstance(features, list):
        return None
    return features


def _query(base: str, layer: int, params: dict[str, str]) -> str:
    return base.rstrip("/") + f"/{layer}/query?" + urlencode(params)
