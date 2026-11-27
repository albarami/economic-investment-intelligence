"""Native manifest readers; no duplicate fetch, parser or latest-file fallback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .assembly import AssemblyError
from .assembly_io import local
from .fetch.allowlist import host_of
from .fetch.bounded import file_hash
from .fetch.registry import Entry
from .fetch.snapshots import read_snapshot

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
    ("block", "incentive_parameter"): None,
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
        if grain == "block" and row["record_type"] == "incentive_parameter":
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
