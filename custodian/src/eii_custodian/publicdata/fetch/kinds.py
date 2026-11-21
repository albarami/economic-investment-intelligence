"""Fetcher kinds this task builds: portal, paged layer, HTTPS file, terms page."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlencode
from zipfile import BadZipFile, ZipFile

from eii_custodian.publicdata.fetch.allowlist import approve, host_of
from eii_custodian.publicdata.fetch.certificate_pins import PinError
from eii_custodian.publicdata.fetch.checks import (
    AttemptFailure,
    count_failure,
    period_failure,
    schema_failure,
)
from eii_custodian.publicdata.fetch.receipts import cache_directory
from eii_custodian.publicdata.fetch.registry import (
    COLLECTED_FAMILIES,
    Entry,
    RegistryError,
    undeclared_public_split,
)
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    MAX_RETRIES,
    BodyTooLarge,
    Response,
    Transport,
    TransportFault,
    public_address,
)

ARC_GIS_PAGE_SIZE = 2000
_EXPORT_SUFFIX = "/exports/json"
_CC_BY_4_TEXT = "CC BY"
_CC_BY_4_URL = "https://creativecommons.org/licenses/by/4.0/"
_SPACE_RUN = re.compile(r"\s+")
_TRADE_AUXILIARY_SOURCES = frozenset(
    {"un_comtrade", "cepii_baci", "cepii_gravity", "atlas_complexity"}
)

Read = Callable[[str], Response]


@dataclass(frozen=True)
class PinFailure(AttemptFailure):
    """A normalized fetch failure retaining a closed, blocking TLS diagnostic.

    Reviewed page adapters must not treat a certificate failure as an access
    obstacle eligible for a capture or an unavailable proof.
    """

    reason: str


def require_verified_chain(failure: AttemptFailure | None) -> None:
    """Preserve the page adapters' security refusal before any access fallback."""
    if isinstance(failure, PinFailure):
        raise PinError(failure.reason)


class _TenderOptions(TypedDict, total=False):
    award_cutoff: str | None
    cutoff_reason: str
    workbook_sha256: str | None


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
    period_first: str = ""
    period_last: str = ""
    periods_observed: bool = False
    terms_unread: str = ""
    coverage_note: str = ""
    auxiliary: tuple[Response, ...] = ()
    requests: tuple[dict[str, object], ...] = ()
    # Ruling L-1001: the observed licence when it differs from the registry
    # licence id, recorded with the date read pending a reviewer's record.
    licence_pending: str = ""
    # Ruling L-1016 (applying L-1001): a dataset-basis row whose portal states
    # no licence at all; the licence is recorded pending, never a gate.
    licence_unstated: bool = False


TERMS_HOST_UNLISTED = "host_unlisted"


def prepare(
    entry: Entry,
    transport: Transport,
    sleep: Callable[[float], None],
    cache: Path | None = None,
    registry_entries: tuple[Entry, ...] | None = None,
) -> Prepared:
    """Fetch one row through the transport seam and apply its declared checks."""
    if entry.kind == "register_file":
        return _failed(
            entry,
            AttemptFailure(1, "", "lead_shell_file_input", "lead shell", "absent"),
        )
    if entry.kind in {"public_page", "awards_intake"}:
        return _failed(
            entry,
            AttemptFailure(
                1, "", "build_context_required", "reviewed page dispatch", "absent"
            ),
        )
    if entry.kind == "besttime":
        return _failed(
            entry,
            AttemptFailure(
                1,
                "https://besttime.app/api/v1/forecasts",
                "build_context_required",
                "build-public context",
                "absent",
            ),
        )
    responses: list[Response] = []
    original = _reader(transport, sleep)

    def reader(url: str) -> Response:
        response = original(url)
        responses.append(response)
        return response

    if entry.key in {"places_ovt", "bldg_ovt"}:
        from eii_custodian.publicdata.fetch.listing import prepare_listing

        return prepare_listing(entry, reader, registry_entries)
    if entry.kind == "portal_dataset":
        result = _portal(entry, reader)
    elif entry.kind == "paged_layer":
        result = _paged(entry, reader)
    elif entry.kind == "terms_page":
        result = _terms(entry, reader)
    elif entry.kind == "paged_cards":
        result = _paged_cards(entry, sleep, cache)
    else:
        result = _file(entry, reader)
    if entry.source_id not in _TRADE_AUXILIARY_SOURCES:
        return result
    return replace(
        result, auxiliary=tuple(r for r in responses if r.body != result.body)
    )


def _reader(transport: Transport, sleep: Callable[[float], None]) -> Read:
    def read(url: str) -> Response:
        fault: TransportFault | None = None
        for attempt in range(ATTEMPT_LIMIT):
            try:
                response = transport(url)
            except TransportFault as exc:
                # A size refusal is not retried: the same body would be read again.
                if exc.kind in {"blocked_host", "body_bytes"}:
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


def read_bounded(
    transport: Transport, sleep: Callable[[float], None], url: str
) -> tuple[Response | None, AttemptFailure | None]:
    """Read one URL through the existing retry and redirect checks."""
    return _call_url(url, _reader(transport, sleep))


def _call(
    entry: Entry, url: str, reader: Read
) -> tuple[Response | None, AttemptFailure | None]:
    del entry
    return _call_url(url, reader)


def _call_url(url: str, reader: Read) -> tuple[Response | None, AttemptFailure | None]:
    decision = approve(url)
    if not decision.ok:
        return None, AttemptFailure(1, url, "blocked_host", "allow-listed host", url)
    try:
        return reader(url), None
    except PinError as exc:
        reason = str(exc)
        if reason not in {
            "certificate_chain_incomplete",
            "certificate_host_mismatch",
            "certificate_review_pending",
            "tls_verification_disabled",
        }:
            reason = "certificate_chain_incomplete"
        return None, PinFailure(
            1,
            url,
            reason,
            "complete verified certificate chain",
            "unavailable",
            reason,
        )
    except _HopRefused as exc:
        return None, AttemptFailure(
            1, exc.url, "blocked_host", "allow-listed host", exc.url
        )
    except BodyTooLarge as exc:
        return None, AttemptFailure(
            1, exc.url, "body_bytes", f"at most {exc.ceiling} bytes", exc.observed
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
            1,
            exc.url,
            "http_status",
            "http success",
            str(exc.status)
            if exc.kind == "http" and exc.status is not None
            else "http status",
        )


def _portal(entry: Entry, reader: Read) -> Prepared:
    meta_url = _metadata_url(entry.url)
    meta, failure = _call(entry, meta_url, reader)
    if failure is not None or meta is None:
        return _failed(entry, failure)
    requests: tuple[dict[str, object], ...] = ()
    export: Response | None = None
    if entry.key != "accident":
        export, failure = _call(entry, entry.url, reader)
        if failure is not None or export is None:
            return _failed(entry, failure)
    info = portal_metadata(entry, meta)
    if info.failure is not None:
        return info
    publisher, modified = info.publisher, info.source_modified
    licence, licence_url = info.portal_licence, info.portal_licence_url
    if entry.key == "accident":
        from eii_custodian.publicdata.fetch.partitions import partition_export

        body, requests, failure = partition_export(entry, meta, reader)
        export = Response(entry.url, body, ())
    if failure is not None or export is None:
        return _failed(entry, failure)
    rows = _json_rows(export.body)
    counted = count_failure(entry, rows, export.final_url)
    if counted is not None:
        return _failed(entry, counted)
    schema = schema_failure(entry, rows, export.final_url)
    if schema is not None:
        return _failed(entry, schema)
    if rows is not None:
        for record in rows:
            if isinstance(record, dict) and undeclared_public_split(
                entry, list(record)
            ):
                return _failed(
                    entry,
                    AttemptFailure(
                        1,
                        export.final_url,
                        "public_split_undeclared",
                        "declared Public split",
                        "undeclared",
                    ),
                )
    period = period_failure(entry, rows, export.final_url)
    if period is not None:
        return _failed(entry, period)
    measured = _measure_failure(entry, rows, export.final_url)
    if measured is not None:
        return _failed(entry, measured)
    count = len(rows) if rows is not None else None
    try:
        first, last, saw_periods, coverage_note = _observed_periods(entry, rows)
    except FamilyPeriodError as exc:
        return _failed(
            entry,
            AttemptFailure(
                1, export.final_url, "period_label", exc.source_id, exc.field
            ),
        )
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
        first,
        last,
        saw_periods,
        coverage_note=coverage_note,
        requests=requests,
        licence_pending=info.licence_pending,
        licence_unstated=info.licence_unstated,
    )


def portal_metadata(entry: Entry, meta: Response) -> Prepared:
    """Validate the same publisher and licence for buffered and streamed exports."""
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
    if (
        publisher == ""
        and entry.key == "bnd_muni_2025"
        and entry.publisher
        == "National open data portal (dataset publisher field empty, read 2026-11-16)"
        and entry.licence_basis == "portal_terms"
    ):
        publisher = entry.publisher
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
    licence_unstated = False
    if licence == "":
        if entry.licence_basis == "dataset":
            # Ruling L-1016 (applying L-1001): a publisher-terms reading is a
            # record, never a gate. A dataset row whose portal states no
            # licence fetches and is used; the licence is recorded pending
            # with the date read, and the build log names the absence. The
            # publisher_missing and publisher_mismatch refusals above stay.
            licence_unstated = True
        licence = ""
        licence_url = ""
    licence_pending = ""
    if licence and not _licence_matches(licence, licence_url, entry.licence_id):
        # Ruling L-1001 (decision 0059, PUB-09 and PUB-97): a licence different
        # from the registry is recorded with the date read, pending a
        # reviewer's record, and fails nothing. The receipt keeps the registry
        # licence beside the observed one; the build log names the difference.
        licence_pending = licence
    return Prepared(
        b"",
        entry.url,
        entry.fetch_host,
        publisher,
        modified,
        None,
        "",
        None,
        portal_licence=licence,
        portal_licence_url=licence_url,
        licence_pending=licence_pending,
        licence_unstated=licence_unstated,
    )


class FamilyPeriodError(Exception):
    """A family period label is missing. The message names the source and the field."""

    def __init__(self, source_id: str, field: str) -> None:
        self.source_id = source_id
        self.field = field
        super().__init__(f"{source_id} {field}")


def family_period_bounds(entry: Entry, rows: list[object]) -> tuple[str, str, str]:
    """Bounds, or a distinct-label count when a label does not parse.

    A missing or null label is a named refusal. The refusal carries no cell value.
    A family field without a declared form is a named refusal. It is not read as a date.
    ``published_label`` is not parsed and is not tried as another form: the same
    missing-label refusals apply, and present labels yield no bounds and the note
    ``distinct labels N``.
    """
    from eii_custodian.publicdata.additions.common import (
        AdditionError,
        parse_period_rule,
        parse_period_value,
    )

    if "form=" not in entry.period_field:
        raise FamilyPeriodError(entry.source_id, "period_form")
    rule = parse_period_rule(entry.period_field)
    field, form = rule.field, rule.form
    labels: list[object] = []
    for row in rows:
        if not isinstance(row, dict) or field not in row:
            raise FamilyPeriodError(entry.source_id, field)
        value = row[field]
        if value is None or value == "":
            raise FamilyPeriodError(entry.source_id, field)
        labels.append(value)
    if form == "published_label":
        return "", "", f"distinct labels {len(set(map(str, labels)))}"
    parsed: list[str] = []
    for label in labels:
        try:
            parsed.append(parse_period_value(label, form))
        except AdditionError:
            return "", "", f"distinct labels {len(set(map(str, labels)))}"
    ordered = sorted(parsed)
    return ordered[0], ordered[-1], ""


def _observed_periods(
    entry: Entry, rows: list[object] | None
) -> tuple[str, str, bool, str]:
    """Observed bounds from the period rule. An unconfirmed field stays blank."""
    from eii_custodian.publicdata.additions.common import (
        FIELD_UNCONFIRMED,
        observe_period_bounds,
        parse_period_rule,
    )

    if entry.source_id in COLLECTED_FAMILIES and rows is not None:
        if not entry.period_field:
            return "", "", True, ""
        first, last, note = family_period_bounds(entry, rows)
        return first, last, True, note
    if "form=" not in entry.period_field or rows is None:
        return "", "", False, ""
    rule = parse_period_rule(entry.period_field)
    if rule.field == FIELD_UNCONFIRMED:
        return "", "", True, ""
    first, last = observe_period_bounds(rows, rule)
    return first, last, True, ""


def _measure_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Refuse measure text outside the reviewed missing-value list."""
    from eii_custodian.publicdata.additions.common import AdditionError, read_measure
    from eii_custodian.publicdata.additions.property_venues import missing_forms_for

    if rows is None:
        return None
    found = missing_forms_for(entry.key)
    if found is None:
        return None
    field, forms = found
    for row in rows:
        if not isinstance(row, dict):
            return AttemptFailure(1, url, "measure_unparsed", field, "measure_unparsed")
        try:
            read_measure(row.get(field), missing_forms=forms, integral=True)
        except AdditionError as error:
            return AttemptFailure(1, url, error.name, field, error.name)
    return None


def _paged(entry: Entry, reader: Read) -> Prepared:
    from eii_custodian.publicdata.gis.fields import declaration_for

    declared = declaration_for(entry.source_id)
    if declared is None:
        return _paged_undeclared(entry, reader)
    return _paged_declared(entry, reader, declared)


def _paged_undeclared(entry: Entry, reader: Read) -> Prepared:
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


def _paged_cards(
    entry: Entry, sleep: Callable[[float], None], cache: Path | None
) -> Prepared:
    """Hand a paged-card row to the tender fetch. The file reader is not used."""
    from datetime import UTC, datetime

    from eii_custodian.publicdata.singles.tenders import (
        CHAIN_PATH,
        TenderError,
        fetch_tenders,
        tender_https,
    )

    page_cache = None if cache is None else cache_directory(cache, entry.key)
    options: _TenderOptions = {}
    if entry.source_id == "tenders_pub":
        from .awards import intake_cutoff

        cutoff, reason, digest = (
            intake_cutoff(cache, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
            if cache is not None
            else (None, "intake_missing", None)
        )
        options = dict(
            award_cutoff=cutoff, cutoff_reason=reason, workbook_sha256=digest
        )
    try:
        _fetched = fetch_tenders(
            tender_https(entry, chain_file=CHAIN_PATH),
            chain_file=CHAIN_PATH,
            chain_sha256=entry.chain_intermediate_sha256,
            sleep=sleep,
            clock=lambda: datetime.now(UTC),
            host=entry.fetch_host,
            cache=page_cache,
            **options,
        )
    except TenderError as exc:
        return _failed(
            entry,
            AttemptFailure(1, entry.url, exc.reason, "", ""),
        )
    return Prepared(
        b"", entry.url, entry.fetch_host, entry.publisher, "", None, "", None
    )


def _file(entry: Entry, reader: Read) -> Prepared:
    """Fetch one HTTPS file. What is kept of the final address is its public form.

    A storage host answers a file request with a signed, time-limited redirect
    whose query holds credentials (rule 14): only scheme, host and path of
    the final address ever reach the receipt, the manifest, a check's error
    text or the log, and `hops` are never stored anywhere.
    """
    response, failure = _call(entry, entry.url, reader)
    if failure is not None or response is None:
        return _failed(entry, failure)
    final = public_address(response.final_url)
    if entry.extension == "xlsx" and not _workbook_container(response.body):
        return _failed(
            entry,
            AttemptFailure(
                1,
                response.final_url,
                "workbook_content",
                "OOXML workbook",
                "invalid body",
            ),
        )
    rows = _json_rows(response.body)
    counted = count_failure(entry, rows, final)
    if counted is not None:
        return _failed(entry, counted)
    return Prepared(
        response.body,
        final,
        host_of(final),
        entry.publisher,
        "",
        len(rows) if rows is not None else None,
        "",
        None,
    )


def _workbook_container(body: bytes) -> bool:
    """Recognise the workbook container, without extracting or parsing sheet values."""
    try:
        with ZipFile(BytesIO(body)) as archive:
            names = set(archive.namelist())
    except BadZipFile:
        return False
    return {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"} <= names


def _terms(entry: Entry, reader: Read) -> Prepared:
    page, failure = _call(entry, entry.url, reader)
    if failure is not None or page is None:
        return _failed(entry, failure)
    terms_hash, unread = _terms_fingerprint(entry, reader)
    return Prepared(
        page.body,
        page.final_url,
        host_of(page.final_url),
        entry.publisher,
        "",
        None,
        terms_hash,
        None,
        terms_unread=unread,
    )


def _terms_fingerprint(entry: Entry, reader: Read) -> tuple[str, str]:
    """Read a terms page once. A technical miss leaves the data page in use."""
    if not entry.terms_url:
        return "", ""
    if not approve(entry.terms_url).ok:
        return "", TERMS_HOST_UNLISTED
    terms, failure = _call(entry, entry.terms_url, reader)
    if failure is not None or terms is None:
        check = failure.check if failure is not None else "check_failed"
        return "", check
    return terms_text_sha256(terms.body), ""


@dataclass(frozen=True)
class TermsPage:
    """A terms-page fingerprint, or the failure that left the page unread."""

    sha256: str
    failure: AttemptFailure | None
    body: bytes = b""


def read_terms_page(
    entry: Entry, transport: Transport, sleep: Callable[[float], None]
) -> TermsPage:
    """Read terms_url and return its fingerprint, or a failure.

    The source URL is not read. A failure does not decide the row's data.
    """
    reader = _reader(transport, sleep)
    terms, failure = _call(entry, entry.terms_url, reader)
    if failure is not None or terms is None:
        return TermsPage("", failure)
    return TermsPage(terms_text_sha256(terms.body), None, terms.body)


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


def _paged_declared(
    entry: Entry,
    reader: Read,
    source: object,
) -> Prepared:
    """Page a declared GIS source at the layer answer's own maximum."""
    from eii_custodian.publicdata.gis.fields import SourceDecl

    if not isinstance(source, SourceDecl):
        raise RegistryError("gis declaration")
    host = host_of(entry.url)
    collected: list[dict[str, object]] = []
    final = entry.url
    total = 0
    for layer in source.layers:
        base = f"https://{host}{layer.service_path}"
        meta_url = base.rstrip("/") + f"/{layer.layer_id}?f=json"
        meta, failure = _call(entry, meta_url, reader)
        if failure is not None or meta is None:
            return _failed(entry, failure)
        if _token_demand(meta.body):
            return _unavailable(entry, meta.final_url)
        counted_url = _query(
            base,
            layer.layer_id,
            {"where": "1=1", "returnCountOnly": "true", "f": "json"},
        )
        counted, failure = _call(entry, counted_url, reader)
        if failure is not None or counted is None:
            return _failed(entry, failure)
        if _token_demand(counted.body):
            return _unavailable(entry, counted.final_url)
        layer_total = _arcgis_count(counted.body)
        if layer_total is None:
            return _failed(
                entry,
                AttemptFailure(
                    1, counted.final_url, "short_total", "count", "unreadable"
                ),
            )
        page_size, oid_name = _layer_page(meta.body)
        if page_size is None or oid_name is None:
            return _failed(
                entry,
                AttemptFailure(
                    1, meta.final_url, "schema_missing", "maxRecordCount", "missing"
                ),
            )
        out_fields = ",".join(field.name for field in layer.fields)
        features: list[dict[str, object]] = []
        offset = 0
        final = counted.final_url
        while offset < layer_total:
            page_url = _query(
                base,
                layer.layer_id,
                {
                    "where": "1=1",
                    "outFields": out_fields,
                    "orderByFields": oid_name,
                    "resultOffset": str(offset),
                    "resultRecordCount": str(page_size),
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "json",
                },
            )
            page, failure = _call(entry, page_url, reader)
            if failure is not None or page is None:
                return _failed(entry, failure)
            if _token_demand(page.body):
                return _unavailable(entry, page.final_url)
            batch = _feature_maps(page.body)
            if batch is None:
                return _failed(
                    entry,
                    AttemptFailure(
                        1, page.final_url, "short_total", "features", "unreadable"
                    ),
                )
            final = page.final_url
            refused = _inherit_page_reference(batch, page.body, page.final_url)
            if refused is None:
                refused = _declared_features(layer, batch, oid_name, page.final_url)
            if refused is not None:
                return _failed(entry, refused)
            features.extend(batch)
            if len(features) > layer_total:
                return _failed(
                    entry,
                    AttemptFailure(
                        1, final, "long_total", str(layer_total), str(len(features))
                    ),
                )
            offset += page_size
            if not batch:
                break
        if len(features) < layer_total:
            return _failed(
                entry,
                AttemptFailure(
                    1, final, "short_total", str(layer_total), str(len(features))
                ),
            )
        if len(features) > layer_total:
            return _failed(
                entry,
                AttemptFailure(
                    1, final, "long_total", str(layer_total), str(len(features))
                ),
            )
        total += layer_total
        collected.append(
            {
                "layer_id": layer.layer_id,
                "layer_name": layer.layer_name,
                "service_path": layer.service_path,
                "geometry": layer.geometry,
                "count": layer_total,
                "features": features,
            }
        )
    body = json.dumps({"layers": collected}, sort_keys=True).encode("utf-8")
    return Prepared(body, final, host, entry.publisher, "", total, "", None)


def _unavailable(entry: Entry, url: str) -> Prepared:
    return _failed(
        entry, AttemptFailure(1, url, "unavailable", "no token", "token demand")
    )


def _token_demand(body: bytes) -> bool:
    """ArcGIS JSON error for a token or a sign-in. Any other body is not one."""
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(loaded, dict):
        return False
    error = loaded.get("error")
    if not isinstance(error, dict):
        return False
    code = error.get("code")
    message = error.get("message")
    text = message.casefold() if isinstance(message, str) else ""
    if code in (498, 499):
        return True
    return "token" in text or "sign in" in text or "signin" in text


def _layer_page(body: bytes) -> tuple[int | None, str | None]:
    """Read maxRecordCount and the single esriFieldTypeOID name."""
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(loaded, dict):
        return None, None
    page_size = loaded.get("maxRecordCount")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
        return None, None
    fields = loaded.get("fields")
    if not isinstance(fields, list):
        return None, None
    names: list[str] = []
    for field in fields:
        if not isinstance(field, dict) or field.get("type") != "esriFieldTypeOID":
            continue
        name = field.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    if len(names) != 1:
        return page_size, None
    return page_size, names[0]


def _feature_maps(body: bytes) -> list[dict[str, object]] | None:
    raw = _features(body)
    if raw is None:
        return None
    rows: list[dict[str, object]] = []
    for item in raw:
        row = _text_dict(item)
        if row is None:
            return None
        rows.append(row)
    return rows


def _text_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        result[key] = item
    return result


def _declared_features(
    layer: object,
    features: list[dict[str, object]],
    oid_name: str,
    url: str,
) -> AttemptFailure | None:
    from eii_custodian.publicdata.gis.fields import NEVER_TAKEN, LayerDecl

    if not isinstance(layer, LayerDecl):
        return AttemptFailure(1, url, "schema_missing", "layer", "missing")
    declared = {field.name: field for field in layer.attribute_fields}
    for feature in features:
        attributes = _text_dict(feature.get("attributes"))
        if attributes is None:
            return AttemptFailure(1, url, "schema_missing", "attributes", "missing")
        for name in attributes:
            if name in NEVER_TAKEN:
                return AttemptFailure(1, url, "never_taken", "absent", name)
        if oid_name in attributes:
            return AttemptFailure(1, url, "object_id_field", "absent", oid_name)
        for name in attributes:
            if name not in declared:
                return AttemptFailure(1, url, "extra_field", "declared", name)
        for field in layer.attribute_fields:
            if field.name not in attributes:
                return AttemptFailure(1, url, "schema_missing", field.name, "missing")
            if not _json_kind_ok(attributes[field.name], field.json_kind):
                return AttemptFailure(
                    1,
                    url,
                    "schema_retyped",
                    f"{field.name}:{field.json_kind}",
                    _json_seen(attributes[field.name]),
                )
        geometry = _text_dict(feature.get("geometry"))
        if geometry is None:
            return AttemptFailure(
                1, url, "schema_missing", layer.geometry_field, "missing"
            )
        if not _wkid_4326(geometry):
            return AttemptFailure(1, url, "spatial_reference", "4326", "other")
    return None


def _inherit_page_reference(
    features: list[dict[str, object]], body: bytes, url: str
) -> AttemptFailure | None:
    """Copy a page's validated EPSG:4326 reference into geometries lacking one.

    S2-T08 part B, mismatch class 1: a declared layer's server states the
    reference once at the page's top level. Only a page reference that passes
    ``_wkid_4326`` is copied; a geometry whose own reference disagrees with a
    stated page reference refuses. ``_declared_features`` still checks every
    geometry, so a missing, boolean or other reference refuses there.
    """
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    stated = isinstance(loaded, dict) and "spatialReference" in loaded
    page = loaded.get("spatialReference") if stated else None
    valid = _wkid_4326({"spatialReference": page})
    for feature in features:
        geometry = _text_dict(feature.get("geometry"))
        if geometry is None:
            continue
        if "spatialReference" not in geometry:
            if valid and isinstance(page, dict):
                geometry["spatialReference"] = dict(page)
                feature["geometry"] = geometry
        elif stated and not (valid and _wkid_4326(geometry)):
            return AttemptFailure(1, url, "spatial_reference", "4326", "conflicting")
    return None


def _wkid_4326(geometry: dict[str, object]) -> bool:
    reference = geometry.get("spatialReference")
    if not isinstance(reference, dict):
        return False
    wkid = reference.get("wkid")
    return isinstance(wkid, int) and not isinstance(wkid, bool) and wkid == 4326


def _json_kind_ok(value: object, kind: str) -> bool:
    if value is None:
        return True
    if kind == "string":
        return isinstance(value, str)
    if kind in {"integer", "date"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _json_seen(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "other"
