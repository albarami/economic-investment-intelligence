"""Hand-made tender pages: parse, merge, key, fetch and the certificate pin."""

from __future__ import annotations

import hashlib
import ssl
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.singles_entries import TENDER_TERMS, tender_entry

from eii_custodian.publicdata.confirm_s2_t13 import CAVEAT, load_confirmation
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    TransportFault,
    open_https,
)
from eii_custodian.publicdata.singles.tenders import (
    LIST_PATHS,
    PACE_S,
    PAGE_SIZE,
    RELEASE_FIELDS,
    TENDER_HOST,
    FetchResult,
    PageBody,
    PageCall,
    TenderError,
    chain_context,
    clean_free_text,
    fetch_tenders,
    normalise_text,
    page_count_failure,
    parse_amount,
    parse_date,
    pattern_class,
    prepare_free_text,
    publish_tenders,
    reject_release,
    rows_from_pages,
    ssl_switched_off,
    stated_last_page,
    tracked_certificate_paths,
)

ROOT = repository_root(Path(__file__))
NOTICE = (
    "The award decision can be appealed within 5 working days from the day "
    "following the award date"
)
HOST = f"https://{TENDER_HOST}"


def _mail() -> str:
    return "box" + "@" + "example.invalid"


def _field(label: str, inner: str) -> str:
    return (
        '<div class="cards-row"><span class="card-label"><label>'
        f'{label}</label></span><span class="card-title">{inner}</span></div>'
    )


def _page(cards: str, *, lang: str, path: str, last_page: int, current: int = 1) -> str:
    items: list[str] = []
    for number in range(1, last_page + 1):
        marker = " disabled" if number == current else ""
        items.append(
            f'<li class="page-item{marker}"><a class="page-link" '
            f'href="{path}/{number}">{number}</a></li>'
        )
    items.append(
        '<li class="page-item"><a class="page-link" '
        f'href="{path}/{current}"><i class="fa-solid fa-angle-right"></i></a></li>'
    )
    return (
        f'<html lang="{lang}"><head><meta charset="utf-8"><title>Invented</title></head><body>'
        '<div class="container uploading thispage-container"><div class="page-content">'
        '<form class="mb-4" method="post">'
        '<input name="__RequestVerificationToken" value="invented-token"></form>'
        '<div class="custom--table--responsive py-2"><table class="custom--table"><tbody>'
        f"{cards}</tbody></table></div>"
        '<nav aria-label="Page navigation"><ul class="pagination">'
        f"{''.join(items)}</ul></nav></div></div></body></html>"
    )


def _awarded(
    *,
    internal: int,
    title: str,
    award: str = "15/01/2024",
    sector: str = "Invented sector",
    bond: str = "1,234.50",
    documents: str = "12.00",
    entity: str = "Invented Entity",
    kind: str = "Invented type",
    number: str = "12/2024 note",
    sizes: tuple[str, ...] = (),
    notice: str = NOTICE,
    labels: dict[str, str] | None = None,
) -> str:
    name = {
        "award": "Award date",
        "sector": "Requested Sector Type",
        "bond": "Tender Bond (QAR)",
        "documents": "Documents value (QR)",
        "entity": "Ministry",
        "kind": "Type",
        "size": "Company size",
    }
    if labels:
        name.update(labels)
    appeal = ""
    if notice:
        appeal = (
            '<div class="col-header"><span class="card-label" style="x">'
            f"<label>{notice}</label></span></div>"
        )
    size = ""
    if sizes:
        words = "".join(
            f'<label class="card-title p-0 m-0">{word}</label>' for word in sizes
        )
        size = (
            '<div class="d-flex align-items-center justify-content-start '
            'flex-gap-12 col-md-10 mb-3">'
            f'<span class="card-label p-0 m-0">{name["size"]}</span>{words}</div>'
        )
    body = (
        '<div class="col-md-7 cards-col"><div class="col-header">'
        f'<span class="card-label"><label>{number}</label></span>'
        '<span class="card-title"><a target="_blank" '
        f'href="/TendersOnlineServices/TenderDetails/{internal}"> {title} </a>'
        '</span></div><div class="col-footer">'
        + _field(name["award"], f"<span><label>{award}</label></span>")
        + _field(name["sector"], f"<label>{sector}</label>")
        + _field(name["bond"], f"<span>{bond}</span>")
        + _field(name["documents"], f"<span>{documents}</span>")
        + "</div>"
        + appeal
        + '</div><div class="col-md-3 cards-col"><div class="col-header">'
        + '<span class="card-label"><label>'
        + name["entity"]
        + '</label></span><span class="card-title"><span>'
        + entity
        + '</span></span></div><div class="col-footer">'
        + _field(name["kind"], f"<span>{kind}</span>")
        + '</div></div><div class="col-md-2 circle-container">'
        + '<div class="flex-container-centered"><a class="btn btn-primary" target="_blank" '
        + f'href="/TendersOnlineServices/TenderCompaniesDetails/{internal}">Report</a>'
        + "</div></div>"
        + size
    )
    return f'<tr><div class="row custom-cards">{body}</div></tr>'


def _available(*, internal: int, published: str, closing: str, **kwargs: str) -> str:
    card = _awarded(internal=internal, award=published, notice="", **kwargs).replace(
        "Award date", "Publish date", 1
    )
    close = (
        '<div class="col-md-2 circle-container"><div><div>'
        '<span class="card-label"><span>Close date</span><br>'
        f"<span>{closing}</span></span></div></div></div>"
    )
    return card.replace(
        '<div class="col-md-2 circle-container">',
        close + '<div class="col-md-2 circle-container">',
        1,
    )


def _cancelled(*, internal: int, title: str, when: str, reason: str) -> str:
    body = (
        '<div class="col-md-7 cards-col"><div class="col-header">'
        '<span class="card-label"><label>4/2024</label></span>'
        '<span class="card-title"><a target="_blank" '
        f'href="/TendersOnlineServices/TenderDetails/{internal}"> {title} </a></span>'
        "</div>"
        + _field("Requested Sector Type", "<label>Invented sector</label>")
        + _field("Cancel date", f"<span><label>{when}</label></span>")
        + _field("Cancel reason", f"<span>{reason}</span>")
        + "</div>"
        + '<div class="col-md-3 cards-col"><div class="col-header">'
        + '<span class="card-label"><label>Ministry</label></span>'
        + '<span class="card-title"><span>Invented Entity</span></span></div>'
        + _field("Type", "<span>Invented type</span>")
        + "</div>"
    )
    return f'<tr><div class="row custom-cards">{body}</div></tr>'


def _awarded_page(cards: str, *, lang: str = "en", last_page: int = 1) -> str:
    return _page(
        cards,
        lang=lang,
        path="/TendersOnlineServices/AwardedTenders",
        last_page=last_page,
    )


def test_pattern_class_maps_digits_and_letters() -> None:
    assert pattern_class("12/Ab") == "99/aa"


def test_date_and_amount_parse_or_fail_with_the_pattern_class() -> None:
    assert parse_date("publish_date", "02/01/2024") == "2024-01-02"
    assert parse_date("publish_date", "") is None
    assert parse_date("publish_date", "29/02/2024") == "2024-02-29"
    with pytest.raises(TenderError) as bad_day:
        parse_date("publish_date", "32/01/2024")
    assert bad_day.value.reason == "publish_date 99/99/9999"
    with pytest.raises(TenderError) as leap:
        parse_date("publish_date", "29/02/2023")
    assert "29" not in leap.value.reason
    assert parse_amount("bond", "") is None
    assert parse_amount("bond", "1,234.50") == Decimal("1234.50")
    assert parse_amount("bond", "12,345.67") == Decimal("12345.67")
    assert parse_amount("bond", "0.00") == Decimal("0.00")
    with pytest.raises(TenderError) as amount:
        parse_amount("bond", "12.3")
    assert amount.value.reason == "bond 99.9"
    with pytest.raises(TenderError) as grouped:
        parse_amount("documents", "1,23.00")
    assert "1,23.00" not in grouped.value.reason


def test_cleaning_replaces_contact_shapes_and_leaves_other_text() -> None:
    mailed, changed = clean_free_text("See " + _mail() + " today")
    assert changed is True
    assert mailed == "See [...] today"
    eight, changed = clean_free_text("n " + ("1" * 8))
    assert changed is True
    assert "1" * 8 not in eight
    plus, changed = clean_free_text("n +12 345 678 end")
    assert changed is True
    assert plus == "n [...] end"
    hyphen, changed = clean_free_text("n 12-345-678 end")
    assert changed is True
    assert hyphen == "n [...] end"
    for length in (6, 16):
        raw = "1" * length
        assert clean_free_text(raw) == (raw, False)
    for length in (7, 15):
        assert clean_free_text("1" * length)[1] is True
    assert clean_free_text("year 2024 stays") == ("year 2024 stays", False)
    assert clean_free_text("cost 1,234.50 stays") == ("cost 1,234.50 stays", False)
    assert clean_free_text("n 12345 stays") == ("n 12345 stays", False)
    assert clean_free_text("Hello  world") == ("Hello  world", False)
    widened, changed = prepare_free_text("  Hello   world \n")
    assert widened == "Hello world"
    assert changed is False


def test_page_count_bounds() -> None:
    assert PAGE_SIZE == 20
    assert page_count_failure(20, is_last=False) is None
    assert page_count_failure(19, is_last=False) == "page_count"
    assert page_count_failure(21, is_last=False) == "page_count"
    assert page_count_failure(1, is_last=True) is None
    assert page_count_failure(20, is_last=True) is None
    assert page_count_failure(0, is_last=True) == "last_page_count"
    assert page_count_failure(21, is_last=True) == "last_page_count"


def test_awarded_page_reads_fields_and_drops_the_notice_and_token() -> None:
    html = _awarded_page(
        _awarded(
            internal=424201,
            title="Invented &amp;\n title",
            sizes=("Small", "Medium"),
        )
        + _awarded(
            internal=424202,
            title=".",
            award="",
            sector="",
            bond="",
            documents="",
            entity="Invented Entity Two",
            notice="",
            number="7/2024",
        )
    )
    assert stated_last_page(html) == 1
    merged = rows_from_pages((html, "awarded", "en"))
    assert merged.missing_period == 2
    first, second = merged.rows
    assert first.title == "Invented & title"
    assert first.text_cleaned is False
    assert first.award_date == "2024-01-15"
    assert first.category == "Invented sector"
    assert first.bond_qar == Decimal("1234.50")
    assert first.documents_value_qar == Decimal("12.00")
    assert first.buying_entity == "Invented Entity"
    assert first.tender_type == "Invented type"
    assert first.company_size == "Small|Medium"
    assert first.lists == "awarded"
    assert first.period is None
    assert "invented-token" not in str(first)
    assert "Report" not in str(first)
    assert second.title == "."
    assert second.award_date is None
    assert second.category is None
    assert second.bond_qar is None
    assert second.buying_entity == "Invented Entity Two"


def test_unknown_or_missing_label_names_the_list_and_position() -> None:
    html = _awarded_page(
        _awarded(internal=424201, title="Invented", labels={"sector": "Invented label"})
    )
    with pytest.raises(TenderError) as bad:
        rows_from_pages((html, "awarded", "en"))
    assert bad.value.reason == "awarded label 2"
    missing = _awarded_page(_awarded(internal=424201, title="Invented")).replace(
        _field("Type", "<span>Invented type</span>"), ""
    )
    with pytest.raises(TenderError) as gone:
        rows_from_pages((missing, "awarded", "en"))
    assert gone.value.reason.startswith("awarded label")
    assert "Invented type" not in gone.value.reason


def test_bad_amount_on_a_card_names_the_field_and_pattern() -> None:
    html = _awarded_page(_awarded(internal=424201, title="Invented", bond="12.3"))
    with pytest.raises(TenderError) as bad:
        rows_from_pages((html, "awarded", "en"))
    assert bad.value.reason == "bond 99.9"


def test_languages_merge_and_conflicts_name_lists_not_values() -> None:
    english = _awarded_page(
        _awarded(internal=424201, title="Invented title", entity="Invented Entity")
    )
    arabic = _page(
        _awarded(
            internal=424201,
            title="عنوان مخترع",
            entity="جهة مخترعة",
            sector="قطاع مخترع",
            kind="نوع مخترع",
            labels={
                "award": "تاريخ الترسية",
                "sector": "نوع القطاع المطلوب",
                "bond": "التأمين المؤقت (رق)",
                "documents": "قيمة الوثائق (رق)",
                "entity": "الجهة",
                "kind": "النوع",
            },
            notice="يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية",
        ),
        lang="ar",
        path="/TendersOnlineServices/AwardedTenders",
        last_page=1,
    )
    merged = rows_from_pages((english, "awarded", "en"), (arabic, "awarded", "ar"))
    row = merged.rows[0]
    assert row.buying_entity == "Invented Entity"
    assert row.buying_entity_ar == "جهة مخترعة"
    assert row.title_ar == "عنوان مخترع"
    assert row.category_ar == "قطاع مخترع"
    assert merged.one_language == 0
    clash = _page(
        _awarded(internal=424201, title="Invented title", sector="Other sector"),
        lang="en",
        path="/TendersOnlineServices/ClosedTenders",
        last_page=1,
    ).replace("Award date", "Publish date", 1)
    with pytest.raises(TenderError) as bad:
        rows_from_pages((english, "awarded", "en"), (clash, "closed", "en"))
    assert "category" in bad.value.reason
    assert "awarded" in bad.value.reason and "closed" in bad.value.reason
    assert "Other sector" not in bad.value.reason


def test_period_comes_only_from_publish_date() -> None:
    awarded = _awarded_page(
        _awarded(internal=424201, title="Invented", award="15/01/2024")
    )
    available = _page(
        _available(
            internal=424201,
            title="Invented",
            published="02/03/2024",
            closing="20/03/2024",
        ),
        lang="en",
        path="/TendersOnlineServices/AvailableMinistriesTenders",
        last_page=1,
    )
    merged = rows_from_pages((awarded, "awarded", "en"), (available, "available", "en"))
    row = merged.rows[0]
    assert row.period == "2024-03-02"
    assert row.closing_date == "2024-03-20"
    assert row.award_date == "2024-01-15"
    assert row.lists == "available|awarded"
    assert merged.missing_period == 0
    other = _page(
        _awarded(internal=424201, title="Invented", award="04/04/2024"),
        lang="en",
        path="/TendersOnlineServices/ClosedTenders",
        last_page=1,
    )
    # Closed cards publish "Publish date", not "Award date".
    closed = other.replace("Award date", "Publish date").replace(
        "15/01/2024", "01/01/2024"
    )
    with pytest.raises(TenderError) as bad:
        rows_from_pages((available, "available", "en"), (closed, "closed", "en"))
    assert "period" in bad.value.reason
    assert "available" in bad.value.reason and "closed" in bad.value.reason
    assert "2024" not in bad.value.reason


def test_cancel_reason_is_cleaned_and_one_language_is_counted() -> None:
    reason = "Call " + _mail()
    html = _page(
        _cancelled(
            internal=424201,
            title="Invented " + ("2" * 8),
            when="01/04/2024",
            reason=reason,
        ),
        lang="en",
        path="/TendersOnlineServices/CancelledTenders",
        last_page=1,
    )
    merged = rows_from_pages((html, "cancelled", "en"))
    row = merged.rows[0]
    assert row.period is None
    assert row.cancel_date == "2024-04-01"
    assert row.cancel_reason == "Call [...]"
    assert row.text_cleaned is True
    assert _mail() not in (row.title or "")
    assert "2" * 8 not in (row.title or "")
    assert merged.one_language == 1
    assert merged.missing_period == 1


def test_keys_are_stable_and_ties_gain_a_suffix() -> None:
    cards = "".join(
        _awarded(internal=number, title="Same invented title")
        for number in (424203, 424201, 424202)
    )
    html = _awarded_page(cards)
    first = rows_from_pages((html, "awarded", "en"))
    second = rows_from_pages((html, "awarded", "en"))
    keys = [row.tender_key for row in first.rows]
    assert keys == [row.tender_key for row in second.rows]
    assert len(keys) == 3
    base = [key for key in keys if not key.endswith(("_2", "_3"))]
    assert len(base) == 1
    assert base[0].startswith("tnd_")
    assert len(base[0]) == 4 + 16
    assert base[0] + "_2" in keys
    assert base[0] + "_3" in keys
    other = rows_from_pages(
        (
            _awarded_page(_awarded(internal=424201, title="Different invented")),
            "awarded",
            "en",
        )
    )
    assert other.rows[0].tender_key != base[0]
    assert not hasattr(first.rows[0], "internal_id")
    assert "12/2024" not in "".join(
        str(value) for value in first.rows[0].__dict__.values()
    )


def test_release_check_rejects_a_planted_contact_or_identifier_column() -> None:
    clean = rows_from_pages(
        (_awarded_page(_awarded(internal=424201, title="Invented")), "awarded", "en")
    )
    reject_release([row.__dict__ for row in clean.rows])
    planted = dict(clean.rows[0].__dict__)
    planted["title"] = _mail()
    with pytest.raises(TenderError) as mail:
        reject_release([planted])
    assert mail.value.reason == "release_contact"
    planted["title"] = "Invented"
    planted["buying_entity"] = "1" * 8
    with pytest.raises(TenderError) as digits:
        reject_release([planted])
    assert digits.value.reason == "release_contact"
    planted["buying_entity"] = "Invented Entity"
    planted["tender_number"] = "12/2024"
    with pytest.raises(TenderError) as column:
        reject_release([planted])
    assert column.value.reason == "release_identifier"


def test_absence_writes_no_row_and_carries_the_caveat() -> None:
    published = publish_tenders((), recorded=False)
    assert published.rows == ()
    assert published.caveat == CAVEAT
    assert published.caveat == "No public tender source is recorded"


def test_list_paths_page_size_and_registry_entry() -> None:
    assert LIST_PATHS == (
        ("available", "AvailableMinistriesTenders"),
        ("closed", "ClosedTenders"),
        ("technically_opened", "TechnicallyOpenedTenders"),
        ("financially_opened", "FinanciallyOpenedTenders"),
        ("awarded", "AwardedTenders"),
        ("cancelled", "CancelledTenders"),
    )
    assert PACE_S == 3
    assert TENDER_HOST == "monaqasat.mof.gov.qa"
    assert RELEASE_FIELDS[0] == "tender_key"
    assert "period" in RELEASE_FIELDS
    assert "tender_number" not in RELEASE_FIELDS
    entry = tender_entry()
    assert entry.fetch_host == TENDER_HOST
    assert entry.licence_basis == "owner_decision"
    assert entry.decision_record == "0026"
    assert entry.skip_reason == ""
    assert entry.release_tables == ("pub_tender",)
    assert entry.kind == "paged_cards"
    assert entry.terms_words == TENDER_TERMS
    assert entry.terms_read_on == "2026-11-14"
    pack = (ROOT / "docs/04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    assert TENDER_TERMS in pack


def _chain(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "chain-stand-in"
    body = b"invented-chain-stand-in"
    path.write_bytes(body)
    return path, hashlib.sha256(body).hexdigest()


def _clock() -> datetime:
    _clock.step += 1
    return datetime(2026, 11, 14, _clock.step % 24, 0, tzinfo=UTC)


_clock.step = 0  # type: ignore[attr-defined]


class _Fake:
    def __init__(
        self, pages: dict[tuple[str, str], bytes], *, status: int = 200
    ) -> None:
        self.pages = pages
        self.status = status
        self.calls: list[PageCall] = []
        self.fail_ssl = False

    def __call__(self, call: PageCall) -> PageBody:
        self.calls.append(call)
        if self.fail_ssl:
            raise ssl.SSLError("certificate verify failed")
        language = (
            "en" if any(name == "Accept-Language" for name, _ in call.headers) else "ar"
        )
        body = self.pages.get((call.url, language), b"")
        return PageBody(status=self.status, body=body, final_url=call.url)


def _run(
    fake: object, tmp_path: Path, **kwargs: object
) -> tuple[FetchResult, list[float]]:
    path, pin = _chain(tmp_path)
    slept: list[float] = []
    result = fetch_tenders(
        fake,
        chain_file=path,
        chain_sha256=pin,
        sleep=slept.append,
        clock=_clock,
        **kwargs,
    )
    return result, slept


def test_fetch_reads_both_languages_behind_the_fake_transport(tmp_path: Path) -> None:
    _clock.step = 0  # type: ignore[attr-defined]
    card = _awarded(internal=424201, title="Invented")
    english = _awarded_page(card).encode()
    arabic = _page(
        _awarded(
            internal=424201,
            title="عنوان",
            labels={
                "award": "تاريخ الترسية",
                "sector": "نوع القطاع المطلوب",
                "bond": "التأمين المؤقت (رق)",
                "documents": "قيمة الوثائق (رق)",
                "entity": "الجهة",
                "kind": "النوع",
            },
            notice="يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية",
        ),
        lang="ar",
        path="/TendersOnlineServices/AwardedTenders",
        last_page=1,
    ).encode()
    url = f"{HOST}/TendersOnlineServices/AwardedTenders/1"
    fake = _Fake({(url, "en"): english, (url, "ar"): arabic})
    result, slept = _run(fake, tmp_path, lists=("awarded",))
    assert len(result.rows) == 1
    assert result.rows[0].buying_entity == "Invented Entity"
    assert result.rows[0].title_ar == "عنوان"
    assert [call.headers for call in fake.calls] == [
        (("Accept-Language", "en-US,en;q=0.5"),),
        (),
    ]
    assert all(
        call.verify_mode == ssl.CERT_REQUIRED and call.check_hostname
        for call in fake.calls
    )
    assert slept == [PACE_S]
    assert result.coverage_note
    assert "0" in result.coverage_note


def test_later_stated_last_is_recorded_and_not_followed(tmp_path: Path) -> None:
    labels = {
        "award": "تاريخ الترسية",
        "sector": "نوع القطاع المطلوب",
        "bond": "التأمين المؤقت (رق)",
        "documents": "قيمة الوثائق (رق)",
        "entity": "الجهة",
        "kind": "النوع",
    }
    notice = (
        "يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية"
    )

    def cards(start: int, count: int, language: str) -> str:
        pieces: list[str] = []
        for offset in range(count):
            pieces.append(
                _awarded(
                    internal=start + offset,
                    title="Invented" if language == "en" else "عنوان",
                    labels=labels if language == "ar" else None,
                    notice=NOTICE if language == "en" else notice,
                )
            )
        return "".join(pieces)

    base = f"{HOST}/TendersOnlineServices/AwardedTenders"
    pages: dict[tuple[str, str], bytes] = {}
    for language in ("en", "ar"):
        pages[(f"{base}/1", language)] = _page(
            cards(424201, 20, language),
            lang=language,
            path="/TendersOnlineServices/AwardedTenders",
            last_page=2,
        ).encode()
        pages[(f"{base}/2", language)] = _page(
            cards(424301, 1, language),
            lang=language,
            path="/TendersOnlineServices/AwardedTenders",
            last_page=4,
            current=2,
        ).encode()
    fake = _Fake(pages)
    result, _slept = _run(fake, tmp_path, lists=("awarded",))
    urls = [call.url for call in fake.calls]
    assert urls == [f"{base}/1", f"{base}/2", f"{base}/1", f"{base}/2"]
    assert "awarded en 2 4" in result.coverage_note
    assert "awarded ar 2 4" in result.coverage_note
    assert len(result.rows) == 21


def test_chain_missing_or_unpinned_refuses_before_a_request(tmp_path: Path) -> None:
    fake = _Fake({})
    slept: list[float] = []
    with pytest.raises(TenderError) as missing:
        fetch_tenders(
            fake,
            chain_file=tmp_path / "absent-stand-in",
            chain_sha256="0" * 64,
            sleep=slept.append,
            clock=_clock,
            lists=("awarded",),
        )
    assert missing.value.reason == "certificate_chain_incomplete"
    assert fake.calls == []
    path, pin = _chain(tmp_path)
    with pytest.raises(TenderError) as mismatch:
        fetch_tenders(
            fake,
            chain_file=path,
            chain_sha256="ab" * 32,
            sleep=slept.append,
            clock=_clock,
            lists=("awarded",),
        )
    assert mismatch.value.reason == "certificate_chain_incomplete"
    assert fake.calls == []
    context = chain_context(path, pin)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_chain_change_refuses_and_loads_nothing(tmp_path: Path) -> None:
    fake = _Fake({})
    fake.fail_ssl = True
    with pytest.raises(TenderError) as changed:
        _run(fake, tmp_path, lists=("awarded",))
    assert changed.value.reason == "certificate_chain_incomplete"
    assert fake.calls


def test_detail_and_report_urls_are_refused_before_a_request(tmp_path: Path) -> None:
    fake = _Fake({})
    for path in (
        f"{HOST}/TendersOnlineServices/TenderDetails/424201",
        f"{HOST}/TendersOnlineServices/TenderCompaniesDetails/424201",
    ):
        fake.calls.clear()
        with pytest.raises(TenderError) as refused:
            _run(fake, tmp_path, only_urls=(path,))
        assert refused.value.reason == "refused_path"
        assert fake.calls == []


def test_rows_from_pages_refuses_a_different_language() -> None:
    html = _awarded_page(_awarded(internal=424201, title="Invented"))
    with pytest.raises(TenderError) as mismatch:
        rows_from_pages((html, "awarded", "ar"))
    assert mismatch.value.reason == "language"


def test_page_without_a_language_attribute_fails() -> None:
    html = _awarded_page(_awarded(internal=424201, title="Invented")).replace(
        'lang="en"', 'class="page"', 1
    )
    with pytest.raises(TenderError) as missing:
        rows_from_pages((html, "awarded", "en"))
    assert missing.value.reason == "language"


def test_arabic_available_fails_closed_without_invented_labels() -> None:
    card = _available(
        internal=424201, published="02/01/2024", closing="03/02/2024", title="عنوان"
    )
    html = _page(
        card,
        lang="ar",
        path="/TendersOnlineServices/AvailableMinistriesTenders",
        last_page=1,
    )
    with pytest.raises(TenderError) as missing:
        rows_from_pages((html, "available", "ar"))
    assert missing.value.reason.startswith("available label")
    assert "عنوان" not in missing.value.reason


def test_a_list_url_carrying_a_banned_piece_is_refused(tmp_path: Path) -> None:
    fake = _Fake({})
    url = f"{HOST}/TendersOnlineServices/AwardedTenders/Bids"
    with pytest.raises(TenderError) as refused:
        _run(fake, tmp_path, only_urls=(url,))
    assert refused.value.reason == "refused_path"
    assert fake.calls == []


def test_context_that_does_not_verify_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def weak() -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    monkeypatch.setattr(ssl, "create_default_context", weak)
    path, pin = _chain(tmp_path)
    with pytest.raises(TenderError) as refused:
        chain_context(path, pin)
    assert refused.value.reason == "certificate_chain_incomplete"


def test_open_https_refuses_a_context_that_does_not_verify() -> None:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(TransportFault) as fault:
        open_https(f"{HOST}/", ssl_context=context)
    assert fault.value.kind == "unreachable"


def test_off_list_host_is_refused_before_a_request(tmp_path: Path) -> None:
    fake = _Fake({})
    with pytest.raises(TenderError) as refused:
        _run(
            fake,
            tmp_path,
            only_urls=("https://evil.example/TendersOnlineServices/AwardedTenders/1",),
        )
    assert refused.value.reason == "host_refused"
    assert fake.calls == []


def test_short_page_and_wrong_language_and_status_fail_closed(tmp_path: Path) -> None:
    cards = "".join(
        _awarded(internal=424200 + index, title=f"Invented {index}")
        for index in range(1, 20)
    )
    short = _page(
        cards,
        lang="en",
        path="/TendersOnlineServices/AwardedTenders",
        last_page=2,
    ).encode()
    url = f"{HOST}/TendersOnlineServices/AwardedTenders/1"
    fake = _Fake({(url, "en"): short})
    with pytest.raises(TenderError) as count:
        _run(fake, tmp_path, lists=("awarded",))
    assert count.value.reason == "page_count"
    wrong = _awarded_page(
        _awarded(internal=424201, title="Invented"), lang="ar"
    ).encode()
    fake = _Fake({(url, "en"): wrong, (url, "ar"): wrong})
    with pytest.raises(TenderError) as language:
        _run(fake, tmp_path, lists=("awarded",))
    assert language.value.reason == "language"
    fake = _Fake({}, status=500)
    with pytest.raises(TenderError) as status:
        _run(fake, tmp_path, lists=("awarded",))
    assert status.value.reason == "http_status"
    assert len(fake.calls) == ATTEMPT_LIMIT
    assert status.value.reason


def test_retry_backoff_then_a_page_is_accepted(tmp_path: Path) -> None:
    html = _awarded_page(_awarded(internal=424201, title="Invented")).encode()
    arabic = _page(
        _awarded(
            internal=424201,
            title="عنوان",
            labels={
                "award": "تاريخ الترسية",
                "sector": "نوع القطاع المطلوب",
                "bond": "التأمين المؤقت (رق)",
                "documents": "قيمة الوثائق (رق)",
                "entity": "الجهة",
                "kind": "النوع",
            },
            notice="يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية",
        ),
        lang="ar",
        path="/TendersOnlineServices/AwardedTenders",
        last_page=1,
    ).encode()
    pages = {"en": html, "ar": arabic}

    class _Flaky:
        def __init__(self) -> None:
            self.n = 0

        def __call__(self, call: PageCall) -> PageBody:
            self.n += 1
            if self.n < ATTEMPT_LIMIT:
                return PageBody(status=500, body=b"", final_url=call.url)
            language = (
                "en"
                if any(name == "Accept-Language" for name, _ in call.headers)
                else "ar"
            )
            return PageBody(status=200, body=pages[language], final_url=call.url)

    result, slept = _run(_Flaky(), tmp_path, lists=("awarded",))
    assert len(result.rows) == 1
    assert slept == [1.0, 2.0, 4.0, PACE_S]
    assert list(BACKOFF_S) == [1.0, 2.0, 4.0]


def test_transport_fault_retries_with_the_backoff(tmp_path: Path) -> None:
    html = _awarded_page(_awarded(internal=424201, title="Invented")).encode()
    arabic = _page(
        _awarded(
            internal=424201,
            title="عنوان",
            labels={
                "award": "تاريخ الترسية",
                "sector": "نوع القطاع المطلوب",
                "bond": "التأمين المؤقت (رق)",
                "documents": "قيمة الوثائق (رق)",
                "entity": "الجهة",
                "kind": "النوع",
            },
            notice=(
                "يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية"
            ),
        ),
        lang="ar",
        path="/TendersOnlineServices/AwardedTenders",
        last_page=1,
    ).encode()
    pages = {"en": html, "ar": arabic}

    class _Faulty:
        def __init__(self) -> None:
            self.n = 0

        def __call__(self, call: PageCall) -> PageBody:
            self.n += 1
            if self.n < ATTEMPT_LIMIT:
                raise TransportFault("http", call.url)
            language = (
                "en"
                if any(name == "Accept-Language" for name, _ in call.headers)
                else "ar"
            )
            return PageBody(status=200, body=pages[language], final_url=call.url)

    result, slept = _run(_Faulty(), tmp_path, lists=("awarded",))
    assert len(result.rows) == 1
    assert slept[:3] == [1.0, 2.0, 4.0]


def test_ssl_scan_and_certificate_suffixes_fail_on_a_plant() -> None:
    assert ssl_switched_off(
        {"custodian/src/eii_custodian/publicdata/plant.py": "mode = ssl.CERT_NONE\n"}
    )
    assert ssl_switched_off(
        {"custodian/src/eii_custodian/publicdata/plant.py": "check_hostname = False\n"}
    )
    assert ssl_switched_off(
        {
            "custodian/src/eii_custodian/publicdata/plant.py": (
                "ssl._create_unverified_context()\n"
            )
        }
    )
    files: dict[str, str] = {}
    base = ROOT / "custodian/src/eii_custodian/publicdata"
    for path in base.rglob("*.py"):
        files[path.relative_to(ROOT).as_posix()] = path.read_text(encoding="utf-8")
    assert ssl_switched_off(files) == ()
    planted = [
        "custodian/invented.pem",
        "custodian/invented.crt",
        "custodian/invented.cer",
        "custodian/invented.der",
        "custodian/src/ok.py",
    ]
    assert tracked_certificate_paths(planted) == (
        "custodian/invented.pem",
        "custodian/invented.crt",
        "custodian/invented.cer",
        "custodian/invented.der",
    )
    listed = subprocess.check_output(
        ["git", "ls-files", "custodian"], cwd=ROOT, text=True
    ).splitlines()
    assert tracked_certificate_paths(listed) == ()


def test_confirmation_block_records_the_visitor_portal() -> None:
    tender = load_confirmation(
        ROOT / "custodian/publicdata/review/s2_t13_confirmation.yaml"
    ).tender
    assert tender.outcome == "terms_do_not_cover"
    assert tender.outcome != "none_found"
    assert tender.terms_words == TENDER_TERMS
    assert tender.terms_read_on == "2026-11-14"
    assert tender.basis_of_use == "owner_decision"
    assert tender.decision_record == "0026"
    assert tender.read_as_visitor is True
    assert tender.shown is True
    assert tender.release_tables == ("pub_tender",)
    assert tender.go_live_permission_needed is True
    for path in (
        "/TendersOnlineServices/AvailableMinistriesTenders/<n>",
        "/TendersOnlineServices/ClosedTenders/<n>",
        "/TendersOnlineServices/TechnicallyOpenedTenders/<n>",
        "/TendersOnlineServices/FinanciallyOpenedTenders/<n>",
        "/TendersOnlineServices/AwardedTenders/<n>",
        "/TendersOnlineServices/CancelledTenders/<n>",
    ):
        assert path in tender.search_note
    assert "page size 20" in tender.search_note
    assert "2026-11-14" in tender.search_note


def test_future_page_has_no_cards() -> None:
    html = _page(
        "<tr><td>Invented planned row</td></tr>",
        lang="en",
        path="/TendersOnlineServices/FutureTenders",
        last_page=1,
    )
    from eii_custodian.publicdata.singles.tenders import read_raw_page

    assert read_raw_page(html).cards == ()


def test_normalise_collapses_whitespace() -> None:
    assert normalise_text("  a \n b  ") == "a b"


def test_committed_awarded_fixture_parses() -> None:
    html = (ROOT / "custodian/tests/fixtures/tenders/awarded_en.html").read_text(
        encoding="utf-8"
    )
    merged = rows_from_pages((html, "awarded", "en"))
    assert merged.rows[0].title == "Invented title"
    assert merged.rows[0].bond_qar == Decimal("1234.50")
    assert merged.missing_period == 1
