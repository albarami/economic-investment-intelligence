"""Hand-made tender pages: parse, merge, key, fetch and the certificate pin."""

from __future__ import annotations

import hashlib
import json
import ssl
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem
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


def _cancelled(
    *,
    internal: int,
    title: str,
    when: str,
    reason: str,
    labels: dict[str, str] | None = None,
    sector: str = "Invented sector",
    entity: str = "Invented Entity",
    kind: str = "Invented type",
) -> str:
    name = {
        "sector": "Requested Sector Type",
        "when": "Cancel date",
        "reason": "Cancel reason",
        "entity": "Ministry",
        "kind": "Type",
    }
    if labels:
        name.update(labels)
    body = (
        '<div class="col-md-7 cards-col"><div class="col-header">'
        '<span class="card-label"><label>4/2024</label></span>'
        '<span class="card-title"><a target="_blank" '
        f'href="/TendersOnlineServices/TenderDetails/{internal}"> {title} </a></span>'
        "</div>"
        + _field(name["sector"], f"<label>{sector}</label>")
        + _field(name["when"], f"<span><label>{when}</label></span>")
        + _field(name["reason"], f"<span>{reason}</span>")
        + "</div>"
        + '<div class="col-md-3 cards-col"><div class="col-header">'
        + '<span class="card-label"><label>'
        + name["entity"]
        + '</label></span><span class="card-title"><span>'
        + entity
        + "</span></span></div>"
        + _field(name["kind"], f"<span>{kind}</span>")
        + "</div>"
    )
    return f'<tr><div class="row custom-cards">{body}</div></tr>'


# Portal labels from the 2026-11-15 addition, copied character for character.
_PUBLISH_AR = "تاريخ الطرح"
_CLOSE_AR = "تاريخ الإغلاق"
_CANCEL_DATE_AR = "تاريخ الإلغاء"
_CANCEL_REASON_AR = "سبب الإلغاء"
_SIZE_AR = "حجم الشركة"
_AR_CARD = {
    "award": "تاريخ الترسية",
    "sector": "نوع القطاع المطلوب",
    "bond": "التأمين المؤقت (رق)",
    "documents": "قيمة الوثائق (رق)",
    "entity": "الجهة",
    "kind": "النوع",
    "size": _SIZE_AR,
}
_AR_NOTICE = (
    "يمكن التظلم على قرار الترسية خلال 5 أيام عمل من اليوم التالي لتاريخ الترسية"
)


def _close_element(label: str, closing: str) -> str:
    """The closing date sits in ``span.card-label``, beside its value, in both languages."""
    return (
        '<div class="col-md-2 circle-container"><div><div>'
        f'<span class="card-label"><span>{label}</span><br><span>{closing}</span></span>'
        "</div></div></div>"
    )


def _arabic_values() -> dict[str, str]:
    return {
        "entity": "جهة مخترعة",
        "sector": "قطاع مخترع",
        "kind": "نوع مخترع",
    }


def _available_lang(
    lang: str, *, internal: int, title: str, published: str, closing: str
) -> str:
    """An available card. The closing date uses the same element in both languages."""
    if lang == "ar":
        card = _awarded(
            internal=internal,
            title=title,
            award=published,
            notice="",
            labels={**_AR_CARD, "award": _PUBLISH_AR},
            **_arabic_values(),
        )
        label = _CLOSE_AR
    else:
        card = _awarded(
            internal=internal, title=title, award=published, notice=""
        ).replace("Award date", "Publish date", 1)
        label = "Close date"
    return card.replace(
        '<div class="col-md-2 circle-container">',
        _close_element(label, closing) + '<div class="col-md-2 circle-container">',
        1,
    )


def _publish_card(lang: str, *, internal: int, title: str, published: str) -> str:
    """A card whose first date is the publish date: closed, or either opened list."""
    if lang == "ar":
        return _awarded(
            internal=internal,
            title=title,
            award=published,
            notice="",
            labels={**_AR_CARD, "award": _PUBLISH_AR},
            **_arabic_values(),
        )
    return _awarded(internal=internal, title=title, award=published, notice="").replace(
        "Award date", "Publish date", 1
    )


_LIST_PUBLISHED = {
    "closed": "04/04/2024",
    "technically_opened": "05/05/2024",
    "financially_opened": "06/06/2024",
}


def _list_card(list_name: str, lang: str, internal: int) -> str:
    """One invented card for a list, in the language's own labels."""
    title = "Invented" if lang == "en" else "عنوان مخترع"
    if list_name == "available":
        return _available_lang(
            lang,
            internal=internal,
            title=title,
            published="02/03/2024",
            closing="20/03/2024",
        )
    if list_name == "cancelled":
        labels = None
        reason = "Invented reason"
        sector, entity, kind = "Invented sector", "Invented Entity", "Invented type"
        if lang == "ar":
            labels = {
                "sector": _AR_CARD["sector"],
                "when": _CANCEL_DATE_AR,
                "reason": _CANCEL_REASON_AR,
                "entity": _AR_CARD["entity"],
                "kind": _AR_CARD["kind"],
            }
            reason = "سبب مخترع"
            sector, entity, kind = "قطاع مخترع", "جهة مخترعة", "نوع مخترع"
        return _cancelled(
            internal=internal,
            title=title,
            when="07/07/2024",
            reason=reason,
            labels=labels,
            sector=sector,
            entity=entity,
            kind=kind,
        )
    if list_name == "awarded":
        extra = _arabic_values() if lang == "ar" else {}
        return _awarded(
            internal=internal,
            title=title,
            award="15/01/2024",
            labels=_AR_CARD if lang == "ar" else None,
            notice=_AR_NOTICE if lang == "ar" else NOTICE,
            **extra,
        )
    return _publish_card(
        lang,
        internal=internal,
        title=title,
        published=_LIST_PUBLISHED[list_name],
    )


def _list_html(list_name: str, lang: str, internal: int) -> str:
    slug = dict(LIST_PATHS)[list_name]
    return _page(
        _list_card(list_name, lang, internal),
        lang=lang,
        path=f"/TendersOnlineServices/{slug}",
        last_page=1,
    )


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
    # S2-T08 part B, mismatch 7: chain_context now inspects the file, so a
    # non-certificate stand-in is refused; an invented issuing intermediate
    # stands in for the reviewed chain. No host certificate is used.
    path = tmp_path / "SYN-chain.pem"
    body = intermediate_pem()
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
    assert tender.page == "https://monaqasat.mof.gov.qa/"
    assert (
        tender.page_sha256
        == "32bb9e85e12368d14fc668216a6bee0a35545f222b5a4299ff279900f28ad81d"
    )
    assert tender.terms_url == "https://monaqasat.mof.gov.qa/TermsOfUse"
    assert (
        tender.terms_sha256
        == "ec2df975cce3f9b1a5212e45a10d96c83d2fe1fd890dc56777a278f7ac46b0a1"
    )
    assert tender.retrieved_utc == "2026-11-14T07:44:16Z"
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


def test_paged_cards_never_reaches_the_file_reader(tmp_path: Path, monkeypatch) -> None:
    """J1: prepare hands a paged_cards row to the tender fetch. _file must not run."""
    from dataclasses import replace

    from eii_custodian.publicdata.fetch import kinds
    from eii_custodian.publicdata.fetch.kinds import prepare
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response

    def _file(entry, reader):  # type: ignore[no-untyped-def]
        raise AssertionError("paged_cards reached _file")

    monkeypatch.setattr(kinds, "_file", _file)
    path, pin = _chain(tmp_path)
    monkeypatch.setattr(
        "eii_custodian.publicdata.singles.tenders.CHAIN_PATH",
        path,
        raising=False,
    )
    entry = next(
        item
        for item in load_registry(ROOT / "custodian/publicdata/sources.yaml")
        if item.key == "tenders_pub"
    )
    entry = replace(
        entry,
        chain_intermediate_sha256=pin,
        url="https://monaqasat.mof.gov.qa/TendersOnlineServices/AvailableMinistriesTenders/9",
    )
    seen: list[str] = []

    def opener(url: str, headers=None, ssl_context=None):  # type: ignore[no-untyped-def]
        seen.append(url)
        return Response(final_url=url, body=b"", hops=())

    monkeypatch.setattr(
        "eii_custodian.publicdata.singles.tenders.open_https",
        opener,
        raising=False,
    )
    prepare(
        entry,
        lambda _url: (_ for _ in ()).throw(AssertionError("seam")),
        lambda _s: None,
    )
    assert seen
    assert "/9" not in seen[0]
    assert seen[0].startswith(
        "https://monaqasat.mof.gov.qa/TendersOnlineServices/AvailableMinistriesTenders/1"
    )


def test_adapter_hands_the_verifying_context_to_open_https(
    tmp_path: Path, monkeypatch
) -> None:
    """J2: the pin is the registry field; the context chain_context built is opened."""
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.singles.tenders import (
        CHAIN_PATH,
        PageCall,
        tender_https,
    )

    path, pin = _chain(tmp_path)
    entry = next(
        item
        for item in load_registry(ROOT / "custodian/publicdata/sources.yaml")
        if item.key == "tenders_pub"
    )
    entry = replace(entry, chain_intermediate_sha256=pin)
    seen: list[object] = []

    def opener(url: str, headers=None, ssl_context=None):  # type: ignore[no-untyped-def]
        seen.append(ssl_context)
        return Response(final_url=url, body=b"", hops=())

    monkeypatch.setattr("eii_custodian.publicdata.singles.tenders.open_https", opener)
    call = PageCall(
        "https://monaqasat.mof.gov.qa/TendersOnlineServices/AwardedTenders/1",
        (("Accept-Language", "en-US,en;q=0.5"),),
        ssl.CERT_REQUIRED,
        True,
    )
    tender_https(entry, chain_file=path)(call)
    assert seen[0] is not None
    assert seen[0].verify_mode == ssl.CERT_REQUIRED  # type: ignore[attr-defined]
    assert seen[0].check_hostname is True  # type: ignore[attr-defined]
    assert CHAIN_PATH == Path("data/public_chain/tenders_pub.intermediate.pem")
    wrong = replace(entry, chain_intermediate_sha256="ab" * 32)
    seen.clear()
    with pytest.raises(TenderError) as mismatch:
        tender_https(wrong, chain_file=path)(call)
    assert mismatch.value.reason == "certificate_chain_incomplete"
    assert seen == []


def test_list_addresses_use_the_host_and_the_declared_names(tmp_path: Path) -> None:
    """J2: six list addresses come from the host and the list names, not a page number."""
    from eii_custodian.publicdata.singles.tenders import list_addresses

    host = "monaqasat.mof.gov.qa"
    addresses = list_addresses(host)
    assert len(addresses) == 6
    assert [item[1] for item in LIST_PATHS] == [
        address.rsplit("/", 2)[-2] for address in addresses
    ]
    assert all(
        address == f"https://{host}/TendersOnlineServices/{slug}/1"
        for (_name, slug), address in zip(LIST_PATHS, addresses, strict=True)
    )
    assert all("/9" not in address for address in addresses)


def test_fetched_pages_are_cached_with_one_receipt_per_list_and_language(
    tmp_path: Path,
) -> None:
    """J3: each page is stored as fetched; the receipt records LR-T6's bounds and hours."""
    _clock.step = 0  # type: ignore[attr-defined]
    english = _awarded_page(_awarded(internal=424201, title="Invented")).encode()
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
    cache = tmp_path / "cache"
    result, _slept = _run(fake, tmp_path, lists=("awarded",), cache=cache)
    stored = cache / "awarded" / "en" / "1.html"
    assert stored.read_bytes() == english
    receipt = json.loads((cache / "awarded" / "en.receipt.json").read_text())
    assert receipt["first_stated_last"] == result.readings[0].first_stated_last
    assert receipt["last_stated_last"] == result.readings[0].last_stated_last
    assert receipt["first_hour"] == result.readings[0].first_hour
    assert receipt["last_hour"] == result.readings[0].last_hour
    assert (cache / "awarded" / "ar.receipt.json").is_file()


def test_tender_key_pattern_is_exempt_from_the_contact_scan() -> None:
    """J4: a well-formed key is not a contact; other strings still are."""
    between = "tnd_ab" + ("9" * 8) + "cdef01"
    all_digits = "tnd_" + ("4" * 16)
    keys = (
        "tnd_" + ("a" * 16),
        "tnd_" + ("a" * 16) + "_2",
        "tnd_" + "abcdef0123456789",
        between,
        all_digits,
    )
    for shaped in keys:
        reject_release([{"tender_key": shaped, "title": "Invented title"}])
    with pytest.raises(TenderError) as malformed:
        reject_release([{"tender_key": "tnd_" + ("g" * 16), "title": "Invented"}])
    assert malformed.value.reason == "tender_key"
    with pytest.raises(TenderError) as digits:
        reject_release(
            [{"tender_key": keys[0], "title": "Invented " + ("8" * 8) + " tail"}]
        )
    assert digits.value.reason == "release_contact"
    with pytest.raises(TenderError) as mail:
        reject_release([{"tender_key": keys[0], "buying_entity": _mail()}])
    assert mail.value.reason == "release_contact"


def test_committed_awarded_fixture_parses() -> None:
    html = (ROOT / "custodian/tests/fixtures/tenders/awarded_en.html").read_text(
        encoding="utf-8"
    )
    merged = rows_from_pages((html, "awarded", "en"))
    assert merged.rows[0].title == "Invented title"
    assert merged.rows[0].bond_qar == Decimal("1234.50")
    assert merged.missing_period == 1


def test_card_without_a_buying_entity_is_left_out_and_counted(tmp_path: Path) -> None:
    """A card whose English read has no Ministry is omitted, not a failed fetch."""
    _clock.step = 0  # type: ignore[attr-defined]
    english_card = _awarded(internal=424201, title="Invented").replace(
        '<span class="card-label"><label>Ministry</label></span>'
        '<span class="card-title"><span>Invented Entity</span></span>',
        "",
    )
    english = _awarded_page(english_card).encode()
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
    result, _slept = _run(
        _Fake({(url, "en"): english, (url, "ar"): arabic}),
        tmp_path,
        lists=("awarded",),
    )
    assert result.rows == ()
    assert "missing_buying_entity 1" in result.coverage_note


def test_five_other_lists_parse_in_arabic_and_merge() -> None:
    """N1a: each of the five other lists parses in Arabic and merges with its English card."""
    expected = {
        "available": ("2024-03-02", "2024-03-20", None),
        "closed": ("2024-04-04", None, None),
        "technically_opened": ("2024-05-05", None, None),
        "financially_opened": ("2024-06-06", None, None),
        "cancelled": (None, None, "2024-07-07"),
    }
    for index, list_name in enumerate(expected):
        internal = 424211 + index
        merged = rows_from_pages(
            (_list_html(list_name, "en", internal), list_name, "en"),
            (_list_html(list_name, "ar", internal), list_name, "ar"),
        )
        row = merged.rows[0]
        period, closing, cancel = expected[list_name]
        assert row.lists == list_name
        assert row.buying_entity == "Invented Entity"
        assert row.buying_entity_ar == "جهة مخترعة"
        assert row.category_ar == "قطاع مخترع"
        assert row.period == period
        assert row.closing_date == closing
        assert row.cancel_date == cancel
        if list_name == "cancelled":
            assert row.cancel_reason_ar == "سبب مخترع"


def test_closing_date_is_read_from_the_same_element_in_both_languages() -> None:
    """N1b: the available closing date is the inner span of span.card-label in both languages."""
    closing = "20/03/2024"
    pages: dict[str, str] = {}
    for lang, title in (("en", "Invented close"), ("ar", "إغلاق مخترع")):
        label = "Close date" if lang == "en" else _CLOSE_AR
        card = _available_lang(
            lang,
            internal=424221,
            title=title,
            published="02/03/2024",
            closing=closing,
        )
        element = (
            f'<span class="card-label"><span>{label}</span><br>'
            f"<span>{closing}</span></span>"
        )
        assert element in card
        pages[lang] = _page(
            card,
            lang=lang,
            path="/TendersOnlineServices/AvailableMinistriesTenders",
            last_page=1,
        )
    merged = rows_from_pages(
        (pages["en"], "available", "en"),
        (pages["ar"], "available", "ar"),
    )
    assert merged.rows[0].closing_date == "2024-03-20"
    other = pages["ar"].replace(closing, "21/03/2024", 1)
    with pytest.raises(TenderError) as clash:
        rows_from_pages(
            (pages["en"], "available", "en"),
            (other, "available", "ar"),
        )
    assert "closing_date" in clash.value.reason
    assert "available" in clash.value.reason
    assert "2024" not in clash.value.reason


def test_arabic_company_size_reaches_the_merged_row() -> None:
    """N1c: an Arabic company-size block parses and its size reaches the merged row."""
    english = _awarded_page(_awarded(internal=424231, title="Invented"))
    arabic = _page(
        _awarded(
            internal=424231,
            title="عنوان",
            labels=_AR_CARD,
            notice=_AR_NOTICE,
            sizes=("Narrow", "Wide"),
        ),
        lang="ar",
        path="/TendersOnlineServices/AwardedTenders",
        last_page=1,
    )
    merged = rows_from_pages((english, "awarded", "en"), (arabic, "awarded", "ar"))
    assert merged.rows[0].company_size == "Narrow|Wide"


def test_arabic_label_outside_the_closed_list_names_list_and_position() -> None:
    """N1e: an unknown Arabic label fails by list and position, never by its text."""
    planted = "تسمية مخترعة"
    card = _available_lang(
        "ar",
        internal=424241,
        title="عنوان",
        published="02/03/2024",
        closing="20/03/2024",
    ).replace("نوع القطاع المطلوب", planted, 1)
    html = _page(
        card,
        lang="ar",
        path="/TendersOnlineServices/AvailableMinistriesTenders",
        last_page=1,
    )
    with pytest.raises(TenderError) as bad:
        rows_from_pages((html, "available", "ar"))
    assert bad.value.reason == "available label 2"
    assert planted not in bad.value.reason


def test_build_stores_each_tender_page_and_no_empty_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The build path stores every list page in both languages, and no empty body."""
    from dataclasses import replace

    import yaml

    from eii_custodian.publicdata.fetch.build import fetch_entry
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.singles import tenders as tender_mod

    chain, pin = _chain(tmp_path)
    monkeypatch.setattr(tender_mod, "CHAIN_PATH", chain)
    document = yaml.safe_load(
        (ROOT / "custodian/publicdata/sources.yaml").read_text(encoding="utf-8")
    )
    row = next(item for item in document["sources"] if item["key"] == "tenders_pub")
    registry = tmp_path / "registry.yaml"
    registry.write_text(yaml.safe_dump({"sources": [row]}), encoding="utf-8")
    entry = replace(load_registry(registry)[0], chain_intermediate_sha256=pin)
    pages: dict[str, dict[str, bytes]] = {}
    for index, (list_name, slug) in enumerate(LIST_PATHS):
        url = f"{HOST}/TendersOnlineServices/{slug}/1"
        pages[url] = {
            lang: _list_html(list_name, lang, 424301 + index).encode()
            for lang in ("en", "ar")
        }

    def transport(address: str, headers=None, ssl_context=None):  # type: ignore[no-untyped-def]
        language = "en" if headers and "Accept-Language" in headers else "ar"
        return Response(final_url=address, body=pages[address][language], hops=())

    monkeypatch.setattr(tender_mod, "open_https", transport)
    cache = tmp_path / "public-cache"
    assert (
        fetch_entry(
            entry,
            lambda _address: (_ for _ in ()).throw(AssertionError("file seam")),
            cache,
            lambda: "2026-11-15T00:00:00Z",
            lambda _seconds: None,
        )
        is None
    )
    empty = cache / entry.key / f"{sha256_hex(b'')}.html"
    for list_name, slug in LIST_PATHS:
        url = f"{HOST}/TendersOnlineServices/{slug}/1"
        for lang in ("en", "ar"):
            stored = cache / entry.key / list_name / lang / "1.html"
            assert stored.is_file() and stored.read_bytes() == pages[url][lang], (
                f"{list_name} {lang} missing; empty body stored={empty.is_file()}"
            )
            assert (cache / entry.key / list_name / f"{lang}.receipt.json").is_file()
    assert not empty.is_file()
    assert not any(
        path.stat().st_size == 0 for path in cache.rglob("*") if path.is_file()
    )
