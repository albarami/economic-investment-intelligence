"""Native manifest readers; no duplicate fetch, parser or latest-file fallback."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any

from .assembly import AssemblyError
from .assembly_io import local
from .fetch.allowlist import host_of
from .fetch.bounded import file_hash
from .fetch.registry import Entry
from .fetch.snapshots import read_snapshot
from .investment_contracts import PARAMETER_UNITS, parse_decimal, period_is_future

if TYPE_CHECKING:
    from .assembly_adapters import Production

NATIVE_SOURCES = frozenset(
    {
        "cepii_baci",
        "cepii_gravity",
        "atlas_complexity",
        "un_comtrade",
        "wb_wdi",
        "unctad_fdi",
        "imf_weo",
        "ilostat_qat",
    }
)


def read_native(build: Production, entry: Entry, identity: str) -> None:
    tables: dict[str, Any]
    manifest: dict[str, Any]
    if entry.source_id == "cepii_baci":
        from .baci.contracts import read_selected

        result = read_selected(build.cache, identity)
        manifest = result.manifest
        tables = {
            "pub_baci_trade": result.trade,
            "pub_baci_country": result.country,
            "pub_baci_product": result.product,
        }
        receipt = manifest["receipt"]
    elif entry.source_id == "cepii_gravity":
        from .gravity.contracts import read_selected as read_gravity

        gravity = read_gravity(build.cache, identity)
        manifest = gravity.manifest
        tables = {
            "pub_gravity_bilateral": gravity.bilateral,
            "pub_gravity_country": gravity.country,
        }
        receipt = manifest["receipt"]
    elif entry.source_id == "atlas_complexity":
        from .atlas.contracts import read_selected as read_atlas

        atlas = read_atlas(build.cache, identity)
        manifest = atlas.manifest
        tables = {
            name: getattr(atlas, attribute)
            for name, attribute in (
                ("pub_atlas_country_product_year", "country_product_year"),
                ("pub_atlas_cpy_country", "cpy_country"),
                ("pub_atlas_cpy_product", "cpy_product"),
                (
                    "pub_atlas_country_partner_product_year",
                    "country_partner_product_year",
                ),
                ("pub_atlas_cppy_country", "cppy_country"),
                ("pub_atlas_cppy_product", "cppy_product"),
            )
        }
        receipt = manifest["receipt"]
    elif entry.source_id == "un_comtrade":
        from .comtrade.assemble import assemble
        from .comtrade.policy import Policy
        from .fetch.terms_text import terms_text_sha256

        if not isinstance(entry.comtrade_policy, Policy):
            raise AssemblyError("assembly_native_policy_missing")
        snapshot = read_snapshot(local(build.cache, entry.key + "/manifests"), identity)
        trade = assemble(
            build.cache,
            entry.key,
            entry.comtrade_policy,
            manifest_sha256=identity,
            publisher=entry.publisher,
            licence_basis=entry.licence_basis,
            terms_sha256=terms_text_sha256(entry.terms_words.encode()),
        )
        tables = {"pub_comtrade_trade": trade.rows}
        receipt = snapshot.sidecar
        manifest = {}
    else:
        from .benchmarks.contracts import TABLES
        from .benchmarks.contracts import read_selected as read_benchmark

        if entry.source_id not in TABLES:
            raise AssemblyError("assembly_native_source_unknown")
        benchmark = read_benchmark(build.cache, entry.source_id, identity)
        tables = {TABLES[entry.source_id]: benchmark.rows}
        receipt = benchmark.receipt
        manifest = benchmark.manifest
    if not isinstance(receipt, dict):
        raise AssemblyError("assembly_lineage_missing")
    if receipt.get("source_id") != entry.source_id or receipt.get("key") != entry.key:
        raise AssemblyError("assembly_lineage_missing")
    build.receipts[entry.key] = receipt
    for name, rows in tables.items():
        build.table(name, [asdict(row) for row in rows], (entry.key,))
    if entry.source_id != "un_comtrade":
        relative = entry.key + "/" + identity + ".manifest.json"
        build.files[relative] = file_hash(local(build.cache, relative))


def _fetched_from(
    sidecar: dict[str, object],
    page_url: str,
    entry: Entry,
    pages: Sequence[Mapping[str, object]],
) -> bool:
    """True when an archived page's receipt shows it was fetched from page_url.

    A sub-page receipt keeps its URL exactly. The landing page is the entry's
    own fetch, whose receipt keeps the final address (build.py stores
    ``final_url``): a redirect on the entry's own host is that same page, bound
    to the entry's key here and to the pinned identity by the caller. The
    archive keeps the first receipt of a body, so a landing whose bytes equal
    another page's would carry that page's receipt: the receipt must be the
    entry fetch's own (only build.py writes ``terms_url`` on an investment
    receipt; the sub-page writer never does), its final address must name no
    page of the manifest, and the landing's digest no other page.
    """
    fetched = sidecar.get("fetch_url")
    if fetched == page_url:
        return True
    return (
        page_url == entry.url
        and sidecar.get("key") == entry.key
        and bool(entry.terms_url)
        and sidecar.get("terms_url") == entry.terms_url
        and isinstance(fetched, str)
        and host_of(entry.url) != ""
        and host_of(fetched) == host_of(entry.url)
        and all(page.get("url") != fetched for page in pages)
        and sum(page.get("sha256") == sidecar.get("sha256") for page in pages) == 1
    )


def read_investment(
    build: Production, entry: Entry, raw_identity: str, manifest_identity: str
) -> None:
    """Select the existing builder's archived table by an explicit reviewed manifest."""
    import json

    from .investment_build import (
        _bounds,
        load_source_spec,
        read_page_table,
        select_release,
        selected_page_rows,
        validate_investment,
        validate_page_rows,
    )
    from .investment_contracts import (
        SCHEMA_AGENCY,
        SCHEMA_FDI,
        SCHEMA_MANIFEST,
        InvestmentFailure,
        SourceEnvelope,
    )

    snapshot = read_snapshot(
        local(build.cache, entry.key + "/evidence"), manifest_identity
    )
    manifest = json.loads(snapshot.body)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != SCHEMA_MANIFEST
        or manifest.get("source_id") != entry.source_id
        or not isinstance(manifest.get("pages"), list)
    ):
        raise AssemblyError("assembly_investment_refused")
    primary = []
    for page in manifest["pages"]:
        raw = read_snapshot(local(build.cache, entry.key), page["sha256"])
        if raw.sidecar.get("source_id") != entry.source_id or not _fetched_from(
            raw.sidecar, page["url"], entry, manifest["pages"]
        ):
            raise AssemblyError("assembly_investment_refused")
        if page["url"] == entry.url:
            primary.append(page["sha256"])
    if primary != [raw_identity]:
        raise AssemblyError("assembly_investment_refused")
    refused = select_release(
        {"source_id": entry.source_id, "manifest_sha256": manifest_identity},
        reviewed=True,
    )
    if refused is not None:
        raise AssemblyError("assembly_investment_refused")
    table_snapshot = read_snapshot(
        local(build.cache, entry.key + "/evidence"), manifest["table_snapshot_identity"]
    )
    if table_snapshot.sha256 != manifest["table_sha256"]:
        raise AssemblyError("assembly_investment_refused")
    table = json.loads(table_snapshot.body)
    expected = SCHEMA_FDI if entry.source_id == "fdi_projects" else SCHEMA_AGENCY
    if (
        not isinstance(table, dict)
        or table.get("schema_version") != expected
        or table.get("source_id") != entry.source_id
        or not isinstance(table.get("rows"), list)
        or type(table.get("row_count")) is not int
        or table["row_count"] != len(table["rows"])
    ):
        raise AssemblyError("assembly_investment_refused")
    spec = load_source_spec(entry.source_id, url=entry.url, cache=build.cache)
    if isinstance(spec, InvestmentFailure):
        raise AssemblyError("assembly_investment_refused")
    envelope = SourceEnvelope(
        source_id=entry.source_id,
        publisher=manifest["publisher"],
        page_url=entry.url,
        licence_id=manifest["licence_id"],
        licence_basis=manifest["licence_basis"],
        decision_record=manifest["decision_record"],
        terms_sha256=manifest["terms_sha256"],
        terms_url=manifest["terms_url"],
        retrieved_utc=manifest["retrieved_utc"],
        page_sha256=raw_identity,
        method=manifest["parser_method"],
        method_version=manifest["parser_version"],
    )
    checked = validate_investment(
        tuple(table["rows"]), _bounds(entry, spec), spec.confirmation, envelope
    )
    if isinstance(checked, InvestmentFailure):
        raise AssemblyError("assembly_investment_refused")
    name = (
        "fdi_projects" if entry.source_id == "fdi_projects" else "pub_investqa_record"
    )
    if entry.source_id == "investqa_pages":
        page_rows, page_refusals = selected_page_rows(
            local(build.cache, entry.key), manifest["pages"], spec.furniture
        )
        page_table = read_page_table(
            local(build.cache, entry.key + "/evidence"), manifest
        )
        if isinstance(page_table, InvestmentFailure):
            raise AssemblyError(page_table.check)
        checked_pages = validate_page_rows(page_table.get("page_rows"), page_rows)
        if isinstance(checked_pages, InvestmentFailure):
            raise AssemblyError(checked_pages.check)
        if page_table.get("page_refusals") != page_refusals:
            raise AssemblyError("page_refusals_mismatch")
        checked = tuple(
            project_agency_records(
                checked, checked_pages, spec.activity_keys, build.lines
            )
        )
        build.table("pub_investqa_page", checked_pages, (entry.key,))
        for refusal in page_refusals:
            build.lines.append(
                "REFUSED pub_investqa_page "
                + str(refusal["page_key"])
                + " check="
                + str(refusal["check"])
                + " reason="
                + str(refusal["observed"])
            )
    build.table(name, checked, (entry.key,))
    for item in (snapshot, table_snapshot):
        relative = item.path.relative_to(build.cache).as_posix()
        build.files[relative] = item.sha256


# Each language is read in its own wording; these are exact phrases, not translations.
PHRASES: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "rent_share": ("rent subsidy", "rental subsidy"),
        "rent_amount": ("rent allowance", "rental allowance"),
        "staff_share": ("salary subsidy", "staff cost subsidy"),
        "staff_amount": ("salary allowance", "staff cost allowance"),
        "other": ("tax exemption", "land offer"),
    },
    "ar": {
        "rent_share": ("دعم الإيجار", "دعم تكاليف الإيجار"),
        "rent_amount": ("بدل الإيجار",),
        "staff_share": ("دعم الرواتب", "دعم الأجور"),
        "staff_amount": ("بدل الرواتب", "بدل الأجور"),
        "other": ("إعفاء ضريبي", "تخصيص أرض"),
    },
}
_NUMBER = r"(?<![0-9.])[0-9]+(?:\.[0-9]+)?"
_DIGITS = str.maketrans(
    {
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
        "\u066b": ".",
    }
)


def _closed_terms(terms: tuple[str, ...], *, forward: bool = False) -> str:
    """Bound closed terms, allowing only the ruled Arabic affixes."""
    patterns = []
    for term in terms:
        token = re.escape(term)
        if re.search(r"[\u0600-\u06ff]", term):
            prefix = r"(?:و|ف|ب|ل|ال|وال|بال|فال|لل|وب|ول|وبال|ولل)?"
            suffix = r"(?:ة|ات|ين|ون)?" if forward else ""
            negation = r"(?<!(?<!\w)غير )" if forward else ""
            patterns.append(negation + r"(?<!\w)" + prefix + token + suffix + r"(?!\w)")
        else:
            patterns.append(r"(?<!\w)" + token + r"(?!\w)")
    return "(?:" + "|".join(patterns) + ")"


_DURATION = re.compile(
    _closed_terms(("for", "لمدة"))
    + rf"\s+({_NUMBER})\s+("
    + _closed_terms(
        ("month", "months", "year", "years", "شهر", "أشهر", "شهراً", "سنة", "سنوات")
    )
    + ")",
    re.I,
)
_PERIOD = re.compile(_closed_terms(("in", "في")) + r"\s+([0-9]{4})(?![0-9])", re.I)
_PERCENT = re.compile(rf"({_NUMBER})\s*([%٪])")
_AMOUNT = re.compile(
    rf"(?:({_closed_terms(('QAR',))})\s+({_NUMBER})|({_NUMBER})\s+({_closed_terms(('ريال قطري',))}))",
    re.I,
)
_MONTHLY = re.compile(_closed_terms(("per month", "monthly", "شهرياً", "شهريا")), re.I)
_ONCE = re.compile(_closed_terms(("one-off", "one time", "لمرة واحدة")), re.I)
_RANGE = re.compile(
    _closed_terms(("up to", "between", "حتى", "ما بين"))
    + r"|[0-9]\s*[-\u2013]\s*[0-9]",
    re.I,
)


@dataclass(frozen=True)
class Parameter:
    """A source-local parse; units remain stated for non-calculator rows."""

    key: str
    value: str | None
    unit: str | None
    duration: int | None
    period: str | None
    wording: str

    def comparable(self) -> tuple[object, ...]:
        unit = {"ريال قطري": "QAR", "٪": "%"}.get(self.unit or "", self.unit)
        if self.unit is not None and self.unit.casefold() == "qar":
            unit = "QAR"
        value = Decimal(self.value) if self.value is not None else None
        return self.key, value, unit, self.duration, self.period


def _quantity(text: str) -> tuple[str | None, str | None, str]:
    """Read one value token and its stated unit; leave all other text visible."""
    percent = _PERCENT.search(text)
    amount = _AMOUNT.search(text)
    if percent is not None:
        return percent[1], percent[2], text[: percent.start()] + text[percent.end() :]
    if amount is not None:
        return (
            amount[2] or amount[3],
            amount[1] or amount[4],
            text[: amount.start()] + text[amount.end() :],
        )
    return None, None, text


def classify_parameter(row: Mapping[str, object]) -> Parameter | None:
    """Parse a block independently; no phrase match never defaults to other."""
    heading = row.get("heading")
    items = json.loads(str(row.get("text_items")))
    if (
        not isinstance(heading, str)
        or not isinstance(items, list)
        or any(type(item) is not str for item in items)
    ):
        raise ValueError("parameter_text_shape")
    wording = "\n".join([heading, *items])
    text = wording.translate(_DIGITS)
    table = PHRASES.get(str(row.get("language")), {})
    matches = [
        key
        for key, phrases in table.items()
        if re.search(_closed_terms(phrases), text.casefold())
    ]
    if len(matches) != 1:
        return None
    key = matches[0]
    duration = None
    duration_match = _DURATION.search(text)
    if duration_match is not None:
        # {years} * {months/year} -> {months}; no money is amortised.
        with localcontext() as context:
            context.prec = max(28, len(duration_match[1]) + 4)
            months = Decimal(duration_match[1])
            if duration_match[2].casefold() in {"year", "years", "سنة", "سنوات"}:
                months *= Decimal(12)
        if months == months.to_integral_value():
            duration = int(months)
        text = text[: duration_match.start()] + text[duration_match.end() :]
    period_match = _PERIOD.search(text)
    period = period_match[1] if period_match else None
    if period_match is not None:
        text = text[: period_match.start()] + text[period_match.end() :]
    token, unit, rest = _quantity(text)
    # A bound or additional number is not a single stated value (L-2325.2c).
    if _RANGE.search(text) or re.search(_NUMBER, rest) or re.search(r"-\s*[0-9]", text):
        return Parameter("other", None, unit, duration, period, wording)
    value = token
    if token is not None and unit in {"%", "٪"}:
        # {percent} / {percent/share} -> dimensionless {share}.
        with localcontext() as context:
            context.prec = max(28, len(token) + 4)
            share = Decimal(token) / Decimal(100)
            share_text = format(share.normalize(), "f")
        if share > Decimal(1):
            return Parameter("other", None, unit, duration, period, wording)
        if key.endswith("_share"):
            value, unit = share_text, "ratio"
    elif token is not None and _MONTHLY.search(text) and not _ONCE.search(text):
        if key.endswith("_amount"):
            unit = "qar_per_month"
    if _ONCE.search(text):
        key, duration = "other", None
    if key != "other" and (value is None or unit != PARAMETER_UNITS[key]):
        key = "other"
    if value is not None and parse_decimal(value, precision=18, scale=4) is None:
        key, value = "other", None
    return Parameter(key, value, unit, duration, period, wording)


def parameter_is_forward(parameter: Parameter, retrieved: str) -> bool:
    """DAT-143/PUB-88 exclude future periods and source-labelled forecasts."""
    return bool(
        (parameter.period is not None and period_is_future(parameter.period, retrieved))
        or re.search(
            _closed_terms(
                ("forecast", "projected", "expected", "متوقع", "توقعات"), forward=True
            ),
            parameter.wording.casefold(),
        )
    )


# Document 03 section 7.3: cache fields are consumed, never passed through.
_AGENCY_CACHE_FIELDS = frozenset(
    "record_type record_key page_key title heading level ordinal parent_ordinal "
    "text_items links page_url provenance source_id publisher licence_id "
    "licence_basis decision_record terms_sha256 terms_url retrieved_utc page_sha256 "
    "method method_version language".split()
)
_AGENCY_COLUMNS = (
    "record_type record_key parent_key sequence title_en title_ar reference "
    "link_url activity_keys parameter_key value unit duration_months as_stated "
    "period page_url source_id"
).split()
_AGENCY_TYPES = {
    ("page", "sector"): "sector",
    ("page", "opportunity"): "opportunity",
    ("page", "incentive"): "incentive",
    ("page", "setup"): None,
    ("page", "law"): "law",
    ("block", "sector_block"): None,
    ("block", "opportunity"): "opportunity",
    ("block", "incentive_parameter"): "incentive_parameter",
    ("block", "setup_step"): "setup_step",
    ("block", "law_block"): None,
    ("block", "block"): None,
}


def _agency_report(lines: list[str], url: str, check: str, reason: str) -> None:
    lines.append(f"OMITTED pub_investqa_record {url} check={check} reason={reason}")


def _agency_page_index(
    pages: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for page in pages:
        # extract_page already formed this with release_page_key, including
        # the Arabic page's declared English alternate. Never derive it again.
        key = str(page["page_key"])
        language = str(page["page_language"])
        url = str(page["page_url"])
        pair = result.setdefault(key, {})
        if language in pair and pair[language] != url:
            raise AssemblyError("assembly_agency_record_key_collision")
        pair[language] = url
    return result


def _agency_cache_groups(
    rows: Sequence[Mapping[str, object]], lines: list[str]
) -> dict[str, list[Mapping[str, object]]]:
    groups: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        if set(row) - _AGENCY_CACHE_FIELDS:
            raise AssemblyError("assembly_agency_record_unknown_field")
        ordinal = row.get("ordinal")
        if ordinal is not None and (type(ordinal) is not int or ordinal < 1):
            raise AssemblyError("assembly_agency_record_type_refused")
        grain = "page" if ordinal is None else "block"
        if (grain, str(row.get("record_type"))) not in _AGENCY_TYPES:
            raise AssemblyError("assembly_agency_record_type_refused")
        if (
            grain == "block"
            and row["record_type"] == "incentive_parameter"
            and row.get("language") == "ar"
            and classify_parameter(row) is None
        ):
            _agency_report(
                lines, str(row["page_url"]), "parameter_kind", "unclassified"
            )
        groups.setdefault(str(row["page_url"]), []).append(row)
    return groups


def _agency_title(row: Mapping[str, object]) -> str:
    field = "title" if row.get("ordinal") is None else "heading"
    title = row.get(field)
    if not isinstance(title, str) or not title:
        raise AssemblyError("assembly_agency_record_missing_title")
    return title


def _agency_project_row(
    row: Mapping[str, object],
    key: str,
    arabic: Mapping[str, object] | None,
    activities: Mapping[str, str],
) -> dict[str, object]:
    grain = "page" if row.get("ordinal") is None else "block"
    kind = str(row["record_type"])
    record_key = key if grain == "page" else f"{key}_{row['ordinal']}"
    result: dict[str, object] = dict.fromkeys(_AGENCY_COLUMNS)
    result.update(
        record_type=kind,
        record_key=record_key,
        title_en=_agency_title(row),
        title_ar=_agency_title(arabic) if arabic is not None else None,
        page_url=row["page_url"],
        source_id=row["source_id"],
    )
    if kind == "setup_step":
        result["sequence"] = row["ordinal"]
    if kind in {"sector", "opportunity"}:
        result["activity_keys"] = activities.get(record_key)
    return result


def _agency_parameter_row(
    row: Mapping[str, object],
    key: str,
    arabic: Mapping[str, object] | None,
    activities: Mapping[str, str],
    lines: list[str],
) -> dict[str, object] | None:
    parameter = classify_parameter(row)
    url = str(row["page_url"])
    if parameter is None:
        _agency_report(lines, url, "parameter_kind", "unclassified")
        return None
    if parameter_is_forward(parameter, str(row.get("retrieved_utc", ""))):
        _agency_report(lines, url, "parameter_period", "forward_looking")
        return None
    if arabic is not None:
        paired = classify_parameter(arabic)
        if paired is not None and parameter_is_forward(
            paired, str(arabic.get("retrieved_utc", ""))
        ):
            _agency_report(lines, url, "parameter_period", "forward_looking")
            return None
        if paired is None or parameter.comparable() != paired.comparable():
            _agency_report(lines, url, "parameter_pair", "pair_value_mismatch")
            return None
    else:
        lines.append(
            f"REPORT pub_investqa_record {url} check=parameter_pair reason=pair_missing"
        )
    result = _agency_project_row(row, key, arabic, activities)
    # Every other uses its source ordinal, stable even if an earlier row is omitted.
    suffix = f"other_{row['ordinal']}" if parameter.key == "other" else parameter.key
    result.update(
        record_key=f"{key}:{suffix}",
        parent_key=key,
        parameter_key=parameter.key,
        value=parameter.value,
        unit=parameter.unit,
        duration_months=parameter.duration,
        as_stated=parameter.wording,
        period=parameter.period,
    )
    return result


def _agency_project_page(
    key: str,
    english: Sequence[Mapping[str, object]],
    arabic: Sequence[Mapping[str, object]],
    activities: Mapping[str, str],
    lines: list[str],
) -> list[dict[str, object]]:
    """Pair blocks by kind and position only when both structures agree."""
    matched = [(row["record_type"], row["level"]) for row in english] == [
        (row["record_type"], row["level"]) for row in arabic
    ]
    result = []
    for row in english:
        grain = "page" if row.get("ordinal") is None else "block"
        if _AGENCY_TYPES[(grain, str(row["record_type"]))] is None:
            continue
        candidates = [
            item for item in english if item["record_type"] == row["record_type"]
        ]
        position = candidates.index(row)
        counterparts = [
            item for item in arabic if item["record_type"] == row["record_type"]
        ]
        counterpart = (
            counterparts[position]
            if position < len(counterparts) and (grain == "page" or matched)
            else None
        )
        if row["record_type"] == "incentive_parameter":
            counterparts = [
                item
                for item in arabic
                if item["record_type"] == "incentive_parameter"
                and item.get("ordinal") == row.get("ordinal")
            ]
            counterpart = counterparts[0] if counterparts else None
            projected = _agency_parameter_row(row, key, counterpart, activities, lines)
            if projected is not None:
                result.append(projected)
            continue
        projected = _agency_project_row(row, key, counterpart, activities)
        if arabic and counterpart is None:
            lines.append(
                f"NULLED pub_investqa_record {projected['record_key']} "
                f"{row['page_url']} check=title_ar reason=pair_unmatched"
            )
        if (
            row["record_type"] == "opportunity"
            and grain == "block"
            and any(
                item["record_type"] == "sector" and item.get("ordinal") is None
                for item in english
            )
        ):
            projected["parent_key"] = key
        result.append(projected)
    return result


def project_agency_records(
    rows: Sequence[Mapping[str, object]],
    pages: Sequence[Mapping[str, object]],
    activities: Mapping[str, str],
    lines: list[str],
) -> list[dict[str, object]]:
    """Project verified cache rows to DAT-143; never release their paragraphs."""
    from .investment_agency import release_page_key

    groups = _agency_cache_groups(rows, lines)
    key_pages = list(pages)
    known_urls = {page["page_url"] for page in pages}
    for url, records in groups.items():
        # Quotation refusal must not remove a resolvable typed record (0121.2).
        # An Arabic alternate cannot be guessed from its URL.
        if url not in known_urls and records[0].get("language") == "en":
            key = release_page_key(url)
            if key and key[0].isalpha():
                key_pages.append(
                    {"page_key": key, "page_language": "en", "page_url": url}
                )
    index = _agency_page_index(key_pages)
    resolved: set[str] = set()
    result = []
    for key, pair in index.items():
        english_url = pair.get("en", "")
        english = groups.get(english_url, [])
        if not english:
            continue
        arabic_url = pair.get("ar", "")
        arabic = groups.get(arabic_url, [])
        result.extend(_agency_project_page(key, english, arabic, activities, lines))
        resolved.update((english_url, arabic_url))
    for url in groups:
        if url not in resolved:
            _agency_report(lines, url, "record_key", "unresolved")
    keys = [row["record_key"] for row in result]
    if len(keys) != len(set(keys)):
        raise AssemblyError("assembly_agency_record_key_collision")
    return result
