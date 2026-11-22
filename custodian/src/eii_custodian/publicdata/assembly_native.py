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
