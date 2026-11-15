"""Tender cards, the merge, the release key and the pinned-chain fetch.

Dates, amounts, contact cleaning and the key are the comparisons this module owns.
The internal integer and the tender number stay inside the build and are dropped
before a release row.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from eii_custodian.publicdata.confirm_s2_t13 import CAVEAT
from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    TransportFault,
    open_https,
)
from eii_custodian.publicdata.singles.tenders_html import (
    PageShapeError,
    RawCard,
    RawPage,
    read_raw_page,
)

TENDER_HOST = "monaqasat.mof.gov.qa"
CHAIN_PATH = Path("data/public_chain/tenders_pub.intermediate.pem")
PAGE_SIZE = 20
PACE_S = 3
KIND = "paged_cards"
LIST_PATHS = (
    ("available", "AvailableMinistriesTenders"),
    ("closed", "ClosedTenders"),
    ("technically_opened", "TechnicallyOpenedTenders"),
    ("financially_opened", "FinanciallyOpenedTenders"),
    ("awarded", "AwardedTenders"),
    ("cancelled", "CancelledTenders"),
)
RELEASE_FIELDS = (
    "tender_key",
    "buying_entity",
    "buying_entity_ar",
    "category",
    "category_ar",
    "tender_type",
    "tender_type_ar",
    "title",
    "title_ar",
    "text_cleaned",
    "period",
    "closing_date",
    "award_date",
    "cancel_date",
    "cancel_reason",
    "cancel_reason_ar",
    "bond_qar",
    "documents_value_qar",
    "company_size",
    "lists",
)
_DATE = re.compile(r"\A[0-9]{2}/[0-9]{2}/[0-9]{4}\Z")
_GROUPED_AMOUNT = re.compile(r"\A[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}\Z")
_PLAIN_AMOUNT = re.compile(r"\A[0-9]+\.[0-9]{2}\Z")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DIGIT_RUN = re.compile(r"\+?[0-9]+(?:[ -][0-9]+)*")
_EIGHT = re.compile(r"(?<![0-9])[0-9]{8}(?![0-9])")
_SPACE = re.compile(r"\s+")
_MARK = "[...]"
_DIGIT_MIN = 7
_DIGIT_MAX = 15
_KEY_HEX = 16
_TENDER_KEY = re.compile(r"\Atnd_[0-9a-f]{16}(?:_[1-9][0-9]*)?\Z")
_MONEY = Decimal("0.01")
_DATE_FIELDS = frozenset({"award_date", "publish_date", "closing_date", "cancel_date"})
_AMOUNT_FIELDS = frozenset({"bond", "documents"})
_SPLIT = ("buying_entity", "category", "tender_type", "cancel_reason")
_SHARED = (
    "publish_date",
    "award_date",
    "closing_date",
    "cancel_date",
    "bond",
    "documents",
    "company_size",
)
_IDENTIFIER_COLUMNS = frozenset(
    {
        "tender_number",
        "internal_id",
        "portal_id",
        "reference_number",
        "tender_no",
    }
)
_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "award_date": "Award date",
        "publish_date": "Publish date",
        "category": "Requested Sector Type",
        "bond": "Tender Bond (QAR)",
        "documents": "Documents value (QR)",
        "buying_entity": "Ministry",
        "tender_type": "Type",
        "closing_date": "Close date",
        "cancel_date": "Cancel date",
        "cancel_reason": "Cancel reason",
        "company_size": "Company size",
    },
    "ar": {
        "award_date": "تاريخ الترسية",
        "category": "نوع القطاع المطلوب",
        "bond": "التأمين المؤقت (رق)",
        "documents": "قيمة الوثائق (رق)",
        "buying_entity": "الجهة",
        "tender_type": "النوع",
    },
}
_NOTICES = frozenset(
    {
        "The award decision can be appealed within 5 working days from the day following the award date",
        "يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية",
    }
)
_LIST_FIELDS = {
    "awarded": (
        "award_date",
        "category",
        "bond",
        "documents",
        "buying_entity",
        "tender_type",
    ),
    "available": (
        "publish_date",
        "category",
        "bond",
        "documents",
        "buying_entity",
        "tender_type",
        "closing_date",
    ),
    "closed": (
        "publish_date",
        "category",
        "bond",
        "documents",
        "buying_entity",
        "tender_type",
    ),
    "technically_opened": (
        "publish_date",
        "category",
        "bond",
        "documents",
        "buying_entity",
        "tender_type",
    ),
    "financially_opened": (
        "publish_date",
        "category",
        "bond",
        "documents",
        "buying_entity",
        "tender_type",
    ),
    "cancelled": (
        "category",
        "cancel_date",
        "cancel_reason",
        "buying_entity",
        "tender_type",
    ),
}
_BANNED_PATHS = (
    "/TenderDetails/",
    "/TenderCompaniesDetails/",
    "/TenderPurchasedCompaniesDetails/",
    "/FutureTenders/",
    "/SearchTenders/",
    "Bids",
    "/ChangeLang",
    "/GetTenderDetailsFile/",
    "/eservices/",
)
_SSL_OFF = (
    "CERT_" + "NONE",
    "check_hostname" + " = False",
    "check_hostname" + "=False",
    "_create_" + "unverified_context",
)
_CERT_SUFFIXES = (".pem", ".crt", ".cer", ".der")
_EN_HEADER = (("Accept-Language", "en-US,en;q=0.5"),)


class TenderError(Exception):
    """A tender page, merge or release check failed. The reason holds no value."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class TenderRow:
    """One release row of pub_tender. No internal integer and no tender number."""

    tender_key: str
    buying_entity: str | None
    buying_entity_ar: str | None
    category: str | None
    category_ar: str | None
    tender_type: str | None
    tender_type_ar: str | None
    title: str | None
    title_ar: str | None
    text_cleaned: bool
    period: str | None
    closing_date: str | None
    award_date: str | None
    cancel_date: str | None
    cancel_reason: str | None
    cancel_reason_ar: str | None
    bond_qar: Decimal | None
    documents_value_qar: Decimal | None
    company_size: str | None
    lists: str


@dataclass(frozen=True)
class MergeResult:
    """Merged rows plus the two coverage counts."""

    rows: tuple[TenderRow, ...]
    one_language: int
    missing_period: int


@dataclass(frozen=True)
class Published:
    """Release rows, or the absence caveat and no row."""

    rows: tuple[TenderRow, ...]
    caveat: str


@dataclass(frozen=True)
class PageCall:
    """One page request the transport is asked to perform."""

    url: str
    headers: tuple[tuple[str, str], ...]
    verify_mode: int
    check_hostname: bool


@dataclass(frozen=True)
class PageBody:
    """The transport's answer. A status other than 200 is not a page."""

    status: int
    body: bytes
    final_url: str


@dataclass(frozen=True)
class ListReading:
    """The pager's last page at the first request and at the last request."""

    list_name: str
    language: str
    first_stated_last: int
    last_stated_last: int
    first_hour: str
    last_hour: str


@dataclass(frozen=True)
class FetchResult:
    """Rows loaded from the six lists, or none when the fetch raised."""

    rows: tuple[TenderRow, ...]
    coverage_note: str
    readings: tuple[ListReading, ...]


@dataclass(frozen=True)
class _Parsed:
    internal_id: int
    list_name: str
    language: str
    title: str
    values: Mapping[str, object]


def pattern_class(text: str) -> str:
    """Map each digit to 9 and each letter to a. Every other character stays."""
    chars: list[str] = []
    for char in text:
        if char.isascii() and char.isdecimal():
            chars.append("9")
        elif char.isascii() and char.isalpha():
            chars.append("a")
        else:
            chars.append(char)
    return "".join(chars)


def parse_date(field: str, text: str) -> str | None:
    """Parse DD/MM/YYYY in Western digits. An empty value is null."""
    stripped = text.strip()
    if stripped == "":
        return None
    if _DATE.fullmatch(stripped) is None:
        raise TenderError(f"{field} {pattern_class(stripped)}")
    try:
        parsed = datetime.strptime(stripped, "%d/%m/%Y")
    except ValueError as exc:
        raise TenderError(f"{field} {pattern_class(stripped)}") from exc
    return parsed.date().isoformat()


def parse_amount(field: str, text: str) -> Decimal | None:
    """Parse an amount with thousands commas and exactly two decimals."""
    stripped = text.strip()
    if stripped == "":
        return None
    grouped = _GROUPED_AMOUNT.fullmatch(stripped) is not None
    plain = _PLAIN_AMOUNT.fullmatch(stripped) is not None
    if not grouped and not plain:
        raise TenderError(f"{field} {pattern_class(stripped)}")
    if "," in stripped and not grouped:
        raise TenderError(f"{field} {pattern_class(stripped)}")
    return Decimal(stripped.replace(",", ""))


def normalise_text(text: str) -> str:
    """Trim and collapse each run of whitespace to one space."""
    return _SPACE.sub(" ", text).strip()


def clean_free_text(text: str) -> tuple[str, bool]:
    """Replace an e-mail shape or a 7 to 15 digit run with the mark."""
    spans: list[tuple[int, int]] = [match.span() for match in _EMAIL.finditer(text)]
    for match in _DIGIT_RUN.finditer(text):
        if _overlaps(match.span(), spans):
            continue
        digits = sum(1 for char in match.group() if char in "0123456789")
        if _DIGIT_MIN <= digits <= _DIGIT_MAX:
            spans.append(match.span())
    if not spans:
        return text, False
    pieces: list[str] = []
    cursor = 0
    for start, end in sorted(spans):
        pieces.append(text[cursor:start])
        pieces.append(_MARK)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), True


def prepare_free_text(text: str) -> tuple[str, bool]:
    """Normalise whitespace, then apply contact cleaning. The flag is the cleaning."""
    return clean_free_text(normalise_text(text))


def page_count_failure(count: int, *, is_last: bool) -> str | None:
    """Fail a non-last page that is not 20 cards, or a last page of 0 or more than 20."""
    if is_last:
        if count == 0 or count > PAGE_SIZE:
            return "last_page_count"
        return None
    if count != PAGE_SIZE:
        return "page_count"
    return None


def stated_last_page(html: str) -> int:
    """Return the largest page number at the end of an ``a.page-link`` href."""
    return read_raw_page(html).stated_last


def rows_from_pages(*pages: tuple[str, str, str]) -> MergeResult:
    """Parse each (html, list, language) page and merge the cards."""
    cards: list[_Parsed] = []
    for html, list_name, language in pages:
        try:
            raw = read_raw_page(html)
        except PageShapeError as exc:
            raise TenderError(exc.reason) from exc
        if raw.language != language:
            raise TenderError("language")
        for card in raw.cards:
            cards.append(_interpret(card, list_name, language))
    return _merge(cards)


def publish_tenders(rows: Sequence[TenderRow], *, recorded: bool) -> Published:
    """Return the rows, or the absence caveat and an empty tuple."""
    if not recorded:
        return Published((), CAVEAT)
    reject_release([dict(row.__dict__) for row in rows])
    return Published(tuple(rows), "")


def reject_release(rows: Sequence[Mapping[str, object]]) -> None:
    """Fail a release table that holds an identifier column or a contact shape.

    ``tender_key`` is checked by its own pattern and is exempt from the contact scan.
    """
    for row in rows:
        if any(name in _IDENTIFIER_COLUMNS for name in row):
            raise TenderError("release_identifier")
        key = row.get("tender_key")
        if not isinstance(key, str) or _TENDER_KEY.fullmatch(key) is None:
            raise TenderError("tender_key")
        for name, value in row.items():
            if name == "tender_key" or not isinstance(value, str):
                continue
            if _EMAIL.search(value) is not None or _EIGHT.search(value) is not None:
                raise TenderError("release_contact")


def list_page(host: str, slug: str, number: int) -> str:
    """One list address from the host and the declared list name."""
    return f"https://{host}/TendersOnlineServices/{slug}/{number}"


def list_addresses(host: str) -> tuple[str, ...]:
    """The six first-page addresses. A registry page number is not an input."""
    return tuple(list_page(host, slug, 1) for _name, slug in LIST_PATHS)


def tender_https(
    entry: Entry, *, chain_file: Path | None = None
) -> Callable[[PageCall], PageBody]:
    """Hand the verifying context from ``chain_context`` to ``open_https``."""
    path = CHAIN_PATH if chain_file is None else chain_file
    context = chain_context(path, entry.chain_intermediate_sha256)

    def transport(call: PageCall) -> PageBody:
        response = open_https(call.url, headers=dict(call.headers), ssl_context=context)
        return PageBody(status=200, body=response.body, final_url=response.final_url)

    return transport


def chain_context(path: Path, pin: str) -> ssl.SSLContext:
    """Add the pinned stand-in to the default verifying context, or refuse."""
    if not path.is_file():
        raise TenderError("certificate_chain_incomplete")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != pin.lower():
        raise TenderError("certificate_chain_incomplete")
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise TenderError("certificate_chain_incomplete")
    try:
        context.load_verify_locations(cafile=str(path))
    except ssl.SSLError:
        # A pinned stand-in that is not a certificate does not extend trust.
        # The handshake then fails closed. A real intermediate file loads.
        return context
    return context


def fetch_tenders(
    transport: Callable[[PageCall], PageBody],
    *,
    chain_file: Path,
    chain_sha256: str,
    sleep: Callable[[float], None],
    clock: Callable[[], datetime],
    lists: tuple[str, ...] | None = None,
    only_urls: tuple[str, ...] | None = None,
    host: str = TENDER_HOST,
    cache: Path | None = None,
) -> FetchResult:
    """Fetch the six lists in both languages through the injected transport."""
    chosen = tuple(item[0] for item in LIST_PATHS) if lists is None else lists
    context = chain_context(chain_file, chain_sha256)
    if only_urls is not None:
        flags = (int(context.verify_mode), bool(context.check_hostname))
        for url in only_urls:
            _refuse(url)
            transport(PageCall(url, (), flags[0], flags[1]))
        raise TenderError("refused_path")
    for name in chosen:
        if name not in dict(LIST_PATHS):
            raise TenderError("refused_path")
    call_flags = (int(context.verify_mode), bool(context.check_hostname))
    collected: list[tuple[str, str, str]] = []
    stored: list[tuple[str, str, int, bytes]] = []
    readings: list[ListReading] = []
    started = False
    for language in ("en", "ar"):
        for list_name, slug in LIST_PATHS:
            if list_name not in chosen:
                continue
            first_body, first_hour = _get(
                transport,
                list_page(host, slug, 1),
                language,
                call_flags,
                sleep,
                clock,
                pace=started,
            )
            started = True
            first_text = first_body.decode("utf-8")
            stored.append((list_name, language, 1, first_body))
            first_raw = _checked_page(first_text, language)
            bound = first_raw.stated_last
            _require_count(len(first_raw.cards), is_last=bound == 1)
            pages = [(1, first_text, first_raw, first_hour)]
            for number in range(2, bound + 1):
                body, hour = _get(
                    transport,
                    list_page(host, slug, number),
                    language,
                    call_flags,
                    sleep,
                    clock,
                    pace=True,
                )
                text = body.decode("utf-8")
                stored.append((list_name, language, number, body))
                raw = _checked_page(text, language)
                _require_count(len(raw.cards), is_last=number == bound)
                pages.append((number, text, raw, hour))
            last_raw = pages[-1][2]
            readings.append(
                ListReading(
                    list_name,
                    language,
                    bound,
                    last_raw.stated_last,
                    pages[0][3],
                    pages[-1][3],
                )
            )
            for _number, text, _raw, _hour in pages:
                collected.append((text, list_name, language))
    merged = rows_from_pages(*collected)
    if cache is not None:
        _write_pages(cache, stored, readings)
    return FetchResult(merged.rows, _coverage(merged, readings), tuple(readings))


def _write_pages(
    cache: Path,
    stored: Sequence[tuple[str, str, int, bytes]],
    readings: Sequence[ListReading],
) -> None:
    """Store each page as fetched, and one receipt per list and language."""
    for list_name, language, number, body in stored:
        dest = cache / list_name / language / f"{number}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    for reading in readings:
        payload = {
            "list_name": reading.list_name,
            "language": reading.language,
            "first_stated_last": reading.first_stated_last,
            "last_stated_last": reading.last_stated_last,
            "first_hour": reading.first_hour,
            "last_hour": reading.last_hour,
        }
        path = cache / reading.list_name / f"{reading.language}.receipt.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def ssl_switched_off(files: Mapping[str, str]) -> tuple[str, ...]:
    """Return lines under publicdata that switch certificate checks off."""
    hits: list[str] = []
    for path in sorted(files):
        if "publicdata/" not in path:
            continue
        for number, line in enumerate(files[path].splitlines(), start=1):
            if any(token in line for token in _SSL_OFF):
                hits.append(f"{path}:{number}")
    return tuple(hits)


def tracked_certificate_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Return custodian paths whose suffix is a certificate file."""
    hits: list[str] = []
    for path in paths:
        if path.startswith("custodian/") and path.endswith(_CERT_SUFFIXES):
            hits.append(path)
    return tuple(hits)


def _overlaps(span: tuple[int, int], spans: Sequence[tuple[int, int]]) -> bool:
    start, end = span
    return any(
        start < other_end and other_start < end for other_start, other_end in spans
    )


def _interpret(card: RawCard, list_name: str, language: str) -> _Parsed:
    expected = _LIST_FIELDS[list_name]
    labels = _LABELS[language]
    pairs = [(label, value) for label, value in card.pairs if label not in _NOTICES]
    company: str | None = None
    size_label = labels.get("company_size")
    if pairs and size_label is not None and pairs[-1][0] == size_label:
        company = pairs[-1][1] or None
        pairs = pairs[:-1]
    if len(pairs) < len(expected):
        raise TenderError(f"{list_name} label {len(pairs) + 1}")
    if len(pairs) > len(expected):
        raise TenderError(f"{list_name} label {len(expected) + 1}")
    values: dict[str, object] = {}
    for index, field in enumerate(expected, start=1):
        wanted = labels.get(field)
        if wanted is None:
            raise TenderError(f"{list_name} label {index}")
        got, raw = pairs[index - 1]
        if got != wanted:
            raise TenderError(f"{list_name} label {index}")
        values[field] = _parse_field(field, raw)
    if company is not None:
        values["company_size"] = company
    return _Parsed(card.internal_id, list_name, language, card.title, values)


def _parse_field(field: str, raw: str) -> object:
    if field in _DATE_FIELDS:
        return parse_date(field, raw)
    if field in _AMOUNT_FIELDS:
        return parse_amount(field, raw)
    if raw == "":
        return None
    return raw


def _merge(cards: Sequence[_Parsed]) -> MergeResult:
    grouped: dict[int, list[_Parsed]] = {}
    for card in cards:
        grouped.setdefault(card.internal_id, []).append(card)
    pending: list[tuple[int, TenderRow]] = []
    one_language = 0
    for internal in sorted(grouped):
        group = grouped[internal]
        languages = {card.language for card in group}
        if len(languages) == 1:
            one_language += 1
        row = _row_for(group)
        pending.append((internal, row))
    rows = assign_tender_keys(pending)
    missing = sum(1 for row in rows if row.period is None)
    return MergeResult(rows, one_language, missing)


def _row_for(group: Sequence[_Parsed]) -> TenderRow:
    titles = _texts(group, "title")
    reasons = _field_by_language(group, "cancel_reason")
    title, title_flag = _clean_side(titles.get("en"))
    title_ar, title_ar_flag = _clean_side(titles.get("ar"))
    reason, reason_flag = _clean_side(reasons.get("en"))
    reason_ar, reason_ar_flag = _clean_side(reasons.get("ar"))
    entities = _field_by_language(group, "buying_entity")
    categories = _field_by_language(group, "category")
    kinds = _field_by_language(group, "tender_type")
    return TenderRow(
        tender_key="",
        buying_entity=_as_text(entities.get("en")),
        buying_entity_ar=_as_text(entities.get("ar")),
        category=_as_text(categories.get("en")),
        category_ar=_as_text(categories.get("ar")),
        tender_type=_as_text(kinds.get("en")),
        tender_type_ar=_as_text(kinds.get("ar")),
        title=title,
        title_ar=title_ar,
        text_cleaned=title_flag or title_ar_flag or reason_flag or reason_ar_flag,
        period=_as_text(_shared(group, "publish_date", "period")),
        closing_date=_as_text(_shared(group, "closing_date", "closing_date")),
        award_date=_as_text(_shared(group, "award_date", "award_date")),
        cancel_date=_as_text(_shared(group, "cancel_date", "cancel_date")),
        cancel_reason=reason,
        cancel_reason_ar=reason_ar,
        bond_qar=_as_decimal(_shared(group, "bond", "bond_qar")),
        documents_value_qar=_as_decimal(
            _shared(group, "documents", "documents_value_qar")
        ),
        company_size=_as_text(_shared(group, "company_size", "company_size")),
        lists=_lists(group),
    )


def _texts(group: Sequence[_Parsed], _name: str) -> dict[str, object]:
    found: dict[str, list[tuple[str, object]]] = {"en": [], "ar": []}
    for card in group:
        found[card.language].append((card.list_name, card.title))
    return {language: _pick(items, "title") for language, items in found.items()}


def _field_by_language(group: Sequence[_Parsed], field: str) -> dict[str, object]:
    found: dict[str, list[tuple[str, object]]] = {"en": [], "ar": []}
    for card in group:
        if field in card.values:
            found[card.language].append((card.list_name, card.values[field]))
    return {language: _pick(items, field) for language, items in found.items()}


def _shared(group: Sequence[_Parsed], field: str, column: str) -> object:
    items = [
        (card.list_name, card.values[field]) for card in group if field in card.values
    ]
    return _pick(items, column)


def _pick(items: Sequence[tuple[str, object]], column: str) -> object:
    if not items:
        return None
    _first_list, chosen = items[0]
    names = [items[0][0]]
    for list_name, value in items[1:]:
        if value != chosen:
            names.append(list_name)
            ordered = [name for name, _slug in LIST_PATHS if name in set(names)]
            raise TenderError(column + " " + " ".join(ordered))
    return chosen


def _clean_side(value: object) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    cleaned, changed = prepare_free_text(str(value))
    return cleaned, changed


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    raise TenderError("amount")


def _lists(group: Sequence[_Parsed]) -> str:
    present = {card.list_name for card in group}
    return "|".join(name for name, _slug in LIST_PATHS if name in present)


def assign_tender_keys(items: Sequence[tuple[int, TenderRow]]) -> tuple[TenderRow, ...]:
    """Key each row from its release columns. Ties gain ``_2``, ``_3`` and so on."""
    groups: dict[str, list[tuple[int, TenderRow]]] = {}
    for internal, row in items:
        groups.setdefault(_canonical(row), []).append((internal, row))
    assigned: list[tuple[int, TenderRow]] = []
    for canon, group in groups.items():
        ordered = sorted(group, key=lambda item: item[0])
        base = "tnd_" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:_KEY_HEX]
        for index, (internal, row) in enumerate(ordered):
            key = base if index == 0 else f"{base}_{index + 1}"
            assigned.append((internal, replace(row, tender_key=key)))
    assigned.sort(key=lambda item: item[0])
    return tuple(row for _internal, row in assigned)


def _canonical(row: TenderRow) -> str:
    payload: dict[str, object] = {}
    for name in RELEASE_FIELDS:
        if name == "tender_key":
            continue
        value = getattr(row, name)
        if isinstance(value, Decimal):
            value = format(value.quantize(_MONEY), "f")
        payload[name] = value
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _refuse(url: str) -> None:
    decision = approve(url)
    if not decision.ok:
        raise TenderError("host_refused")
    path = urlsplit(url).path
    if any(piece in path for piece in _BANNED_PATHS):
        raise TenderError("refused_path")
    prefixes = tuple(f"/TendersOnlineServices/{slug}/" for _name, slug in LIST_PATHS)
    if not path.startswith(prefixes):
        raise TenderError("refused_path")


def _checked_page(text: str, language: str) -> RawPage:
    try:
        raw = read_raw_page(text)
    except PageShapeError as exc:
        raise TenderError(exc.reason) from exc
    if raw.language != language:
        raise TenderError("language")
    return raw


def _require_count(count: int, *, is_last: bool) -> None:
    reason = page_count_failure(count, is_last=is_last)
    if reason is not None:
        raise TenderError(reason)


def _get(
    transport: Callable[[PageCall], PageBody],
    url: str,
    language: str,
    flags: tuple[int, bool],
    sleep: Callable[[float], None],
    clock: Callable[[], datetime],
    *,
    pace: bool,
) -> tuple[bytes, str]:
    _refuse(url)
    if pace:
        sleep(float(PACE_S))
    headers = _EN_HEADER if language == "en" else ()
    call = PageCall(url, headers, flags[0], flags[1])
    for attempt in range(ATTEMPT_LIMIT):
        try:
            body = transport(call)
        except ssl.SSLError as exc:
            raise TenderError("certificate_chain_incomplete") from exc
        except TransportFault as exc:
            if _ssl_failure(exc):
                raise TenderError("certificate_chain_incomplete") from exc
            if attempt + 1 == ATTEMPT_LIMIT:
                raise TenderError("http_status") from exc
            sleep(BACKOFF_S[attempt])
            continue
        if body.status != 200:
            if attempt + 1 == ATTEMPT_LIMIT:
                raise TenderError("http_status")
            sleep(BACKOFF_S[attempt])
            continue
        hour = clock().strftime("%Y-%m-%dT%H")
        return body.body, hour
    raise TenderError("http_status")


def _ssl_failure(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        reason = getattr(current, "reason", None)
        if isinstance(reason, ssl.SSLError):
            return True
        current = current.__cause__
    return False


def _coverage(merged: MergeResult, readings: Sequence[ListReading]) -> str:
    parts = [
        f"one language {merged.one_language}",
        f"without publication date {merged.missing_period}",
    ]
    for reading in readings:
        if reading.first_stated_last != reading.last_stated_last:
            parts.append(
                f"{reading.list_name} {reading.language} "
                f"{reading.first_stated_last} {reading.last_stated_last}"
            )
    return "; ".join(parts)


__all__ = [
    "KIND",
    "LIST_PATHS",
    "PACE_S",
    "PAGE_SIZE",
    "RELEASE_FIELDS",
    "TENDER_HOST",
    "FetchResult",
    "PageBody",
    "PageCall",
    "TenderError",
    "TenderRow",
    "assign_tender_keys",
    "chain_context",
    "clean_free_text",
    "fetch_tenders",
    "normalise_text",
    "page_count_failure",
    "parse_amount",
    "parse_date",
    "pattern_class",
    "prepare_free_text",
    "publish_tenders",
    "read_raw_page",
    "reject_release",
    "rows_from_pages",
    "ssl_switched_off",
    "stated_last_page",
    "tracked_certificate_paths",
]
