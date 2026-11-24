"""Hand-made investment pages. Every name, figure and address is invented."""

from __future__ import annotations

import itertools
import json

from eii_custodian.publicdata.investment_contracts import PUBLISHED_FIELDS

ORIGIN = "invented"
DASHBOARD_URL = "https://dashboard.invalid/"
LANDING_URL = "https://agency.invalid/"
TERMS_URL = "https://terms.invalid/terms"
SECTOR_URL = "https://agency.invalid/sectors/invented-textiles"
OPPORTUNITY_URL = "https://agency.invalid/opportunities/invented-loom"
INCENTIVE_URL = "https://agency.invalid/incentives/invented-rent-ease"
SETUP_URL = "https://agency.invalid/setup/invented-steps"
LAW_URL = "https://agency.invalid/laws/invented-statute"
LAW_LINK = "https://statute.invalid/invented-statute"
TERMS_BODY = b"Invented terms page for the investment sources."
PROSE = "Invented prose that must stay off the record."
PHRASES = (
    "estimates of publicly announced projects",
    "does not capture all investment projects",
)
LABELS = ("Capex", "Mn", "USD")


class MadePage:
    """One invented dashboard page and the published tokens it carries."""

    def __init__(self, body: bytes, tokens: tuple[dict[str, str], ...]) -> None:
        self.body = body
        self.tokens = tokens


def invented_record(**overrides: object) -> dict[str, object]:
    """Return one invented project. Overrides replace named fields."""
    record: dict[str, object] = {
        "tech_level_id": 1,
        "src_state_name": "Invented State",
        "project_type_name": "Invented new site",
        "freezone_name": "",
        "city_id": 10,
        "city_name": "Invented Bay",
        "world_region_id": 1,
        "state_name": "Inv",
        "src_country_id": 10,
        "src_world_region_name": "Invented region",
        "lat": ("n", "10.123456789012"),
        "sub_sector_name": "Invented weaving",
        "function_name": "Invented making",
        "fdi_sector_id": 10,
        "src_world_region_id": 1,
        "src_state_id": 10,
        "country_name": "Inv",
        "description": "Invented caf\u00e9 note",
        "parent_company_name": "Invented Loom Parent",
        "tags": [],
        "naics_sub_sector_name": "Invented weaving",
        "project_year": 2024,
        "src_city_name": "Invented Source",
        "project_date": "2024-06-15",
        "function_id": 2,
        "sector_name": "Invented textiles",
        "src_country_name": "Inventedland",
        "investing_company_name": "Invented Loom Works",
        "state_abbr": "",
        "src_city_id": 11,
        "capex_currency": "USD",
        "sector_id": 12,
        "world_region_name": "Invented",
        "project_address": "Invented Bay",
        "project_id": 1001,
        "parent_company_website": "",
        "lng": ("n", "20.123456789012"),
        "state_id": 13,
        "fdi_sector_name": "Invented sector",
        "capex": ("n", "12.5"),
        "jobs": 40,
        "country_id": 14,
        "parent_company_id": 15,
        "project_type_id": 1,
        "province": "Inv",
        "project_month": 5,
    }
    record.update(overrides)
    return record


def published_tokens(record: dict[str, object]) -> dict[str, str]:
    """Return the canonical published token of each field, before null conversion."""
    return {name: _token(record[name]) for name in PUBLISHED_FIELDS}


def made_dashboard(
    records: tuple[dict[str, object], ...] | None = None,
    *,
    pushes: int = 1,
    drop_phrase: str = "",
    drop_label: str = "",
    prose: str = "",
    currency_text: str = "USD",
    raw_count: int | None = None,
    record_count: int | None = None,
    extra_key: str = "",
    omit_key: str = "",
    projects_value: object | None = None,
    omit_last_reference: bool = False,
    extra_chunk: bool = False,
    payload: bytes | None = None,
    bad_reference: str = "",
    document_override: bytes | None = None,
    noise_order: tuple[int, ...] | None = None,
    payload_at: int = 0,
    count_place: str = "metrics",
    inner_chunks: int = 1,
    duplicate_text: bool = False,
    shared_row_id: bool = False,
) -> MadePage:
    """Return a hand-made page in the live framing."""
    rows = records if records is not None else (invented_record(),)
    tokens = tuple(
        published_tokens(row) for row in rows if set(row) >= set(PUBLISHED_FIELDS)
    )
    if payload is None:
        payload = _payload(
            rows,
            currency_text=currency_text,
            raw_count=raw_count,
            record_count=record_count,
            extra_key=extra_key,
            omit_key=omit_key,
            projects_value=projects_value,
            omit_last_reference=omit_last_reference,
            extra_chunk=extra_chunk,
            bad_reference=bad_reference,
            document_override=document_override,
            count_place=count_place,
            inner_chunks=inner_chunks,
            duplicate_text=duplicate_text,
            shared_row_id=shared_row_id,
        )
    body = _wrap(
        payload,
        pushes=pushes,
        drop_phrase=drop_phrase,
        drop_label=drop_label,
        prose=prose,
        noise_order=noise_order,
        payload_at=payload_at,
    )
    return MadePage(body, tokens)


def dashboard_page(
    records: tuple[dict[str, object], ...] | None = None,
    *,
    pushes: int = 1,
    drop_phrase: str = "",
    drop_label: str = "",
    prose: str = "",
    currency_text: str = "USD",
    raw_count: int | None = None,
    record_count: int | None = None,
    extra_key: str = "",
    omit_key: str = "",
    projects_value: object | None = None,
    omit_last_reference: bool = False,
    extra_chunk: bool = False,
    payload: bytes | None = None,
    bad_reference: str = "",
    document_override: bytes | None = None,
    noise_order: tuple[int, ...] | None = None,
    payload_at: int = 0,
    count_place: str = "metrics",
    inner_chunks: int = 1,
    duplicate_text: bool = False,
    shared_row_id: bool = False,
) -> bytes:
    """Return the bytes of a hand-made dashboard page."""
    return made_dashboard(
        records,
        pushes=pushes,
        drop_phrase=drop_phrase,
        drop_label=drop_label,
        prose=prose,
        currency_text=currency_text,
        raw_count=raw_count,
        record_count=record_count,
        extra_key=extra_key,
        omit_key=omit_key,
        projects_value=projects_value,
        omit_last_reference=omit_last_reference,
        extra_chunk=extra_chunk,
        payload=payload,
        bad_reference=bad_reference,
        document_override=document_override,
        noise_order=noise_order,
        payload_at=payload_at,
        count_place=count_place,
        inner_chunks=inner_chunks,
        duplicate_text=duplicate_text,
        shared_row_id=shared_row_id,
    ).body


def page_from_script(script: str) -> bytes:
    """Return a page whose only script is the given text."""
    html = (
        "<!DOCTYPE html><html><body>"
        + _visible()
        + f"<script>{script}</script></body></html>"
    )
    return html.encode("utf-8")


def sector_page() -> bytes:
    """Return an invented sector page in the live heading structure."""
    return _agency_html(
        "<header><nav>Invented header</nav></header>"
        "<main>"
        "<section class='spotlight-inner'><h1>Invented first title</h1></section>"
        "<h1>Invented textiles</h1>"
        "<section class='section pattern-lg-1'>"
        "<h2>Invented call</h2><h2>Invented other call</h2></section>"
        "<section class='section pattern-dual'><h4>Invented dual</h4></section>"
        "<section class='whatsHappening'><h2>Invented news</h2></section>"
        "<h2>Invented weaving</h2>"
        "<p>Invented &amp;  loom</p>"
        "<ul><li><p>Invented listed paragraph</p></li>"
        "<li>Invented bare item</li></ul>"
        "<p>Invented share 12.5 percent</p>"
        '<a href="/files/invented.pdf">Invented document</a>'
        '<a href="https://statute.invalid/invented">Invented outside</a>'
        + _request_form()
        + "<form><p>Invented plain label</p>"
        + "<a href='/invented-plain'>Invented plain link</a></form>"
        + "<h2>Invented second block</h2><p>Invented second prose</p>"
        "<h2>Invented third block</h2>"
        "<h3>Invented lower</h3><p>Invented nested</p>"
        "<footer><section><form><p>Invented footer prose</p></form>"
        "<a href='/footer'>Invented footer link</a></section></footer>"
        "</main>"
    )


def opportunity_page() -> bytes:
    """Return an invented opportunities page with five h3 blocks."""
    items = "".join(
        f"<h3>Invented hall {name}</h3><p>Invented note {name}</p>"
        for name in ("one", "two", "three", "four", "five")
    )
    return _agency_html(
        "<main><h1>Invented halls</h1><h2>Invented list</h2>"
        + _request_form()
        + items
        + "</main>"
    )


def incentive_page() -> bytes:
    """Return an invented incentive page with four parameters and one step."""
    heads = "".join(
        f"<h4>Invented parameter {name}</h4><p>Invented wording {name}</p>"
        for name in ("one", "two", "three")
    )
    step = (
        "<h4>Invented parameter four</h4>"
        "<h3>Invented filing step</h3><p>Invented step prose</p>"
    )
    return _agency_html("<main><h1>Invented rent ease</h1>" + heads + step + "</main>")


def setup_page() -> bytes:
    """Return an invented set-up page with five h2 steps and one h3 step."""
    steps = "".join(
        f"<h2>Invented step {name}</h2><p>Invented step prose {name}</p>"
        for name in ("one", "two", "three", "four", "five")
    )
    return _agency_html(
        "<main><h1>Invented set up</h1>"
        + steps
        + "<h3>Invented inner step</h3><p>Invented inner prose</p></main>"
    )


def law_page(*, paragraph: bool = True) -> bytes:
    """Return an invented law page with one paragraph and one linked block."""
    prose = "<p>Invented statute prose</p>" if paragraph else ""
    return _agency_html(
        "<main>"
        "<section class='spotlight-inner'><h1>Invented laws</h1></section>"
        "<h1>Invented statute</h1>" + prose + "<h2>Invented chapter</h2>"
        '<a href="/files/invented.pdf">Invented document</a>'
        '<a href="https://statute.invalid/invented">Invented outside</a>'
        "</main>"
    )


def _request_form() -> str:
    """Return a request form inside a dialog, with invented labels and one link."""
    return (
        "<div class='modal-dialog'><div class='modal-content'>"
        "<div class='modal-body'><div class='content'><div class='form'>"
        "<form class='request-form'>"
        "<label>Invented request label</label>"
        "<input type='text'>"
        "<a href='/invented-request'>Invented request link</a>"
        "<button type='submit'>Invented request button</button>"
        "</form></div></div></div></div></div>"
    )


def agency_plant(problem: str) -> bytes:
    """Return one invented page that breaks one content rule."""
    if problem == "no_main":
        return _agency_html("<h1>Invented textiles</h1><h2>Invented weaving</h2>")
    if problem == "no_title":
        return _agency_html(
            "<main><h2>Invented one</h2><h2>Invented two</h2>"
            "<h2>Invented three</h2></main>"
        )
    if problem == "empty_heading":
        return _agency_html("<main><h1> </h1><h2>Invented weaving</h2></main>")
    if problem == "short_sector":
        return _agency_html(
            "<main><h1>Invented textiles</h1><h2>Invented one</h2>"
            "<h2>Invented two</h2></main>"
        )
    if problem == "short_opportunity":
        return _agency_html("<main><h1>Invented halls</h1><h3>Invented one</h3></main>")
    if problem == "short_incentive":
        return _agency_html(
            "<main><h1>Invented rent ease</h1><h4>Invented one</h4></main>"
        )
    if problem == "short_setup":
        return _agency_html(
            "<main><h1>Invented set up</h1><h2>Invented one</h2></main>"
        )
    if problem == "law_without_paragraph":
        return law_page(paragraph=False)
    if problem == "table":
        return _agency_html(
            "<main><h1>Invented textiles</h1><table><tr><td>Invented</td></tr></table>"
            "<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2></main>"
        )
    if problem == "cut_after_minimum":
        return (
            b"<!DOCTYPE html><html><body><main><h1>Invented textiles</h1>"
            b"<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2>"
        )
    if problem == "cut_in_paragraph":
        return (
            b"<!DOCTYPE html><html><body><main><h1>Invented textiles</h1>"
            b"<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2>"
            b"<p>Invented"
        )
    if problem == "no_main_close":
        return (
            b"<!DOCTYPE html><html><body><main><h1>Invented textiles</h1>"
            b"<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2>"
            b"</html>"
        )
    if problem == "second_main":
        return (
            b"<!DOCTYPE html><html><body></body></html><main></main><main>"
            b"<h1>Invented textiles</h1>"
            b"<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2>"
        )
    if problem == "no_html_end":
        return (
            b"<!DOCTYPE html><html><body><main><h1>Invented textiles</h1>"
            b"<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2>"
            b"</main>"
        )
    if problem == "open_paragraph":
        return (
            b"<!DOCTYPE html><html><body><main><h1>Invented textiles</h1>"
            b"<h2>Invented one</h2><h2>Invented two</h2><h2>Invented three</h2>"
            b"<p>Invented</main></body></html>"
        )
    raise KeyError(problem)


def agency_bodies() -> dict[str, bytes]:
    """Return the closed synthetic inventory keyed by page URL."""
    return {
        SECTOR_URL: sector_page(),
        OPPORTUNITY_URL: opportunity_page(),
        INCENTIVE_URL: incentive_page(),
        SETUP_URL: setup_page(),
        LAW_URL: law_page(),
    }


def _payload(
    records: tuple[dict[str, object], ...],
    *,
    currency_text: str,
    raw_count: int | None,
    record_count: int | None,
    extra_key: str,
    omit_key: str,
    projects_value: object | None,
    omit_last_reference: bool,
    extra_chunk: bool,
    bad_reference: str,
    document_override: bytes | None,
    count_place: str,
    inner_chunks: int,
    duplicate_text: bool,
    shared_row_id: bool,
) -> bytes:
    document: dict[str, object] = {
        "clientProjects": list(records) if projects_value is None else projects_value,
        "indexBaseMetrics": {
            "indexBasePeriod": None,
            "indexBaseProjects": len(records),
            "indexBaseCapex": 0,
            "indexBaseJobs": 0,
        },
        "currencyText": currency_text,
        "latestDate": "2026-01-02T00:00:00.000Z",
    }
    if extra_key:
        document[extra_key] = "invented"
    if omit_key:
        document.pop(omit_key, None)
    blob = (
        document_override
        if document_override is not None
        else _dump(document).encode("utf-8")
    )
    chunks, spans, inside = _chunks(blob)
    ids = [f"a{index:x}" for index in range(len(chunks))]
    if omit_last_reference:
        refs = [
            row_id
            for row_id, (_start, end) in zip(ids, spans, strict=True)
            if end <= inside
        ]
    else:
        refs = ids
    count = len(records) if projects_value is None else 0
    stated_raw = count if raw_count is None else raw_count
    stated_recorded = count if record_count is None else record_count
    listed = [bad_reference] if bad_reference else [f"${row_id}" for row_id in refs]
    chunk_value = _chunk_value(listed, stated_raw, stated_recorded, count_place)
    if inner_chunks == 2:
        chunk_value = [*chunk_value, *chunk_value]
    chunk_row = _other("c", chunk_value)
    parts = [b":[]\n", b"b:[]\n"]
    parts.extend(
        _text(row_id, chunk) for row_id, chunk in zip(ids, chunks, strict=True)
    )
    if duplicate_text and ids:
        parts.append(_text(ids[0], b"invented-other-body"))
    if shared_row_id and ids:
        parts.append(_other(ids[0], []))
    parts.append(chunk_row)
    if extra_chunk:
        parts.append(_other("d", _chunk_value(["$a0"], 1, 1, "metrics")))
    parts.append(b"b:[0]\n")
    return b"".join(parts)


def _chunk_value(
    listed: list[str], raw: int, recorded: int, place: str
) -> list[dict[str, object]]:
    """Return the chunk row: an array whose payload holds the chunk list."""
    if place == "beside":
        payload: dict[str, object] = {
            "serializedDatasetChunks": listed,
            "rawRecordCount": raw,
            "recordCount": recorded,
            "sst": "invented",
        }
        return [{"payload": payload}]
    if place == "no_diagnostics":
        return [
            {
                "payload": {
                    "serializedDatasetChunks": listed,
                    "sst": "invented",
                }
            }
        ]
    if place == "no_metrics":
        diagnostics: dict[str, object] = {"note": "invented"}
    elif place == "raw_fraction":
        metrics = _metrics(raw, recorded, "metrics")
        metrics["rawRecordCount"] = 1.5
        diagnostics = {"metrics": metrics}
    elif place in {"metrics", "no_raw", "no_record"}:
        diagnostics = {"metrics": _metrics(raw, recorded, place)}
    else:
        raise KeyError(place)
    return [
        {
            "payload": {
                "diagnostics": diagnostics,
                "serializedDatasetChunks": listed,
                "sst": "invented",
            }
        }
    ]


def _metrics(raw: int, recorded: int, place: str) -> dict[str, object]:
    """Return metrics with the two counts among the other invented keys."""
    metrics: dict[str, object] = {
        "cache": "invented",
        "datasetNormalizeMs": 3,
        "normalizeMs": 4,
        "preparedCache": "invented",
        "rawBytes": 5,
    }
    if place != "no_raw":
        metrics["rawRecordCount"] = raw
    if place != "no_record":
        metrics["recordCount"] = recorded
    metrics["upstreamMs"] = 6
    return metrics


def _chunks(blob: bytes) -> tuple[list[bytes], list[tuple[int, int]], int]:
    inside = next(
        (index + 1 for index, byte in enumerate(blob) if byte >= 0x80), len(blob) // 2
    )
    points = sorted(
        {
            0,
            max(1, len(blob) // 3),
            inside,
            max(inside + 1, (2 * len(blob)) // 3),
            len(blob),
        }
    )
    spans = [(start, end) for start, end in itertools.pairwise(points) if start != end]
    return [blob[start:end] for start, end in spans], spans, inside


def _text(row_id: str, chunk: bytes) -> bytes:
    return f"{row_id}:T{len(chunk):x},".encode("ascii") + chunk


def _other(row_id: str, body: object) -> bytes:
    encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return f"{row_id}:".encode("ascii") + encoded + b"\n"


# Invented stand-ins for the other inline scripts of the facts note's section 1.
# None of them is a payload script. The bootstrap body is the one the note gives.
_NOISE = (
    '<script id="gtag-bootstrap">window.dataLayer=window.dataLayer||[];'
    "function gtag(){dataLayer.push(arguments);}</script>",
    "<script>requestAnimationFrame(function(){return;});</script>",
    "<script>$RB=[];$RV=function(a){$RB.push(a);};</script>",
    "<script>(self.__next_f=self.__next_f||[]).push([0])</script>",
)


def _wrap(
    payload: bytes,
    *,
    pushes: int,
    drop_phrase: str,
    drop_label: str,
    prose: str,
    noise_order: tuple[int, ...] | None = None,
    payload_at: int = 0,
) -> bytes:
    text = payload.decode("utf-8", "surrogateescape")
    parts = [text] if pushes == 1 else [text[: len(text) // 2], text[len(text) // 2 :]]
    payloads = []
    for part in parts:
        argument = json.dumps([1, part], separators=(",", ":"), ensure_ascii=True)
        payloads.append(f"<script>self.__next_f.push({argument})</script>")
    if noise_order is None:
        scripts = [_NOISE[3], *payloads]
    else:
        noise = [_NOISE[index] for index in noise_order]
        at = min(max(payload_at, 0), len(noise))
        scripts = [*noise[:at], *payloads, *noise[at:]]
    html = (
        "<!DOCTYPE html><html><body>"
        + _visible(drop_phrase, drop_label, prose)
        + "".join(scripts)
    )
    html += "</body></html>"
    return html.encode("utf-8")


def _visible(drop_phrase: str = "", drop_label: str = "", prose: str = "") -> str:
    labels = " ".join(word for word in LABELS if word != drop_label)
    phrases = "".join(f"<p>{phrase}</p>" for phrase in PHRASES if phrase != drop_phrase)
    extra = f"<p>{prose}</p>" if prose else ""
    return f"<p>{labels}</p>{phrases}{extra}"


def _dump(value: object) -> str:
    if isinstance(value, dict):
        parts = [
            json.dumps(key, ensure_ascii=False) + ":" + _dump(value[key])
            for key in value
        ]
        return "{" + ",".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_dump(item) for item in value) + "]"
    return _page_token(value)


def _page_token(value: object) -> str:
    if isinstance(value, tuple) and value[0] == "n":
        return str(value[1])
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise TypeError(type(value))


def _token(value: object) -> str:
    if isinstance(value, tuple) and value[0] == "n":
        return str(value[1])
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(_token(item) for item in value) + "]"
    raise TypeError(type(value))


def _agency_html(inner: str) -> bytes:
    html = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"></head><body>'
        + inner
        + "</body></html>"
    )
    return html.encode("utf-8")


def quotation_page(language: str = "en", extra: str = "") -> bytes:
    """Invented content with inline nodes, furniture and a declared counterpart."""
    content = "Invented café" if language == "en" else "نص مخترع ١٢"
    return (
        f'<!DOCTYPE html><html lang="{language}"><head><meta charset="utf-8">'
        '<link rel="alternate" hreflang="en" href="/en/invented-page">'
        "</head><body><main><h1>Invented title</h1>"
        f'<p>{content} <a href="/invented-link">link</a> tail.</p>'
        "<div>First <span>inline</span> last.</div><p>Second.</p>"
        "<aside>Excluded side menu</aside><svg><text>Excluded vector</text></svg>"
        '<div hidden>Excluded hidden</div><div aria-hidden="true">Excluded aria</div>'
        '<section class="cookie">Excluded consent</section>'
        "<form><label>Excluded form</label></form><!-- Excluded comment -->"
        f"{extra}</main></body></html>"
    ).encode()


def furniture_div_page() -> bytes:
    """A furniture class on a div, and on a section for contrast."""
    return quotation_page(
        extra='<div class="whatsHappening">Invented developments</div>'
        '<section class="whatsHappening">Invented section furniture</section>'
    )


def heading_button_page() -> bytes:
    """A button inside a heading outside any form, and two control buttons."""
    return quotation_page(
        extra='<h2><button class="collapse-title">Invented chapter</button></h2>'
        "<div><button>Invented control</button></div>"
        "<form><h2><button>Invented form control</button></h2></form>"
    )


def inline_point_page() -> bytes:
    """An inline element's end directly followed by a full stop."""
    return quotation_page(extra='<p>Invented <a href="/invented-here">here</a>.</p>')
