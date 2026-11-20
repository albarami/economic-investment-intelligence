"""Closed lead-shell stages; private cache artifacts and count-only diagnostics."""

from __future__ import annotations

import csv
import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..fc_register.names import contribution as financial_contribution
from ..fetch.allowlist import host_of
from ..fetch.build import CACHE_RELATIVE, utc_now
from ..fetch.page_records import selected_page
from ..fetch.receipts import sha256_hex
from ..fetch.registry import load_registry
from ..fetch.snapshots import SnapshotError, publish_snapshot, read_snapshot
from ..fetch.transport import Transport, TransportFault
from .contracts import (
    FIELDS,
    VERSION,
    Candidate,
    Company,
    WebError,
    digest,
    dump,
    loads,
)
from .evidence import Outcome, PageOutcome, reconcile
from .fetch import Access, ArchivedObstacle, Pacer, load_page
from .names import contribution
from .parse import extract
from .review import reviewer_bundle
from .scope import Manifest, company_requests, identity
from .search import companies, request_url, search


def _cache_input(cache: Path, value: str) -> Path:
    path = Path(value)
    if (
        not value
        or not path.resolve().is_relative_to(
            (cache / "company_web" / "input").resolve()
        )
        or path.is_symlink()
    ):
        raise WebError("input_path_refused")
    return path


def input_companies(cache: Path, environ: Mapping[str, str]) -> tuple[Company, ...]:
    """Lead only: public register stand-in shape; no workbook path or reader."""
    register_path = environ.get("EII_REGISTER_FILE", "")
    if not register_path:
        raise WebError("register_input_missing")
    # The owner-authorised public register input is read here, never by a model.
    with Path(register_path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        allowed = {
            "company_name",
            "registration_number",
            "licence_number",
            "address",
            "website",
            "activity",
        }
        if (
            set(columns) - allowed
            or "company_name" not in columns
            or len(set(columns)) != len(columns)
        ):
            raise WebError("register_shape_refused")
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise WebError("register_shape_refused")
    entry = next(e for e in load_registry() if e.source_id == "fc_register")
    financial = financial_contribution(cache, entry)
    # The pinned contribution is verified before any name is read or searched.
    selected = selected_page(cache, entry)
    if financial.lineage.get("snapshot_identity") != selected.sha256:
        raise WebError("financial_binding_refused")
    payload = json.loads(selected.body)
    financial_names = tuple(
        row["company_name"] or row["company_name_ar"] for row in payload["rows"]
    )
    if any(name not in financial.names for name in financial_names):
        raise WebError("financial_binding_refused")
    return companies(rows, financial_names)


def _publish(folder: Path, role: str, payload: object, stamp: str) -> str:
    body = dump(payload)
    return publish_snapshot(
        folder / role,
        "json",
        body,
        {
            "source_id": "company_web",
            "key": "company_web/" + role,
            "retrieved_utc": stamp,
            "sha256": sha256_hex(body),
            "method": VERSION,
        },
    ).sha256


def _read(folder: Path, role: str, selected: str) -> dict[str, Any]:
    value = json.loads(read_snapshot(folder / role, selected).body)
    if not isinstance(value, dict):
        raise WebError("run_record_refused")
    return value


def _company_binding(inputs: tuple[Company, ...]) -> str:
    return digest(
        [(c.key, digest(c.name), c.source, dict(c.register_fields)) for c in inputs]
    )


def _search_stage(
    inputs: tuple[Company, ...],
    plan: Manifest,
    access: Access,
    clock: Callable[[], str],
) -> dict[str, object]:
    rows = []
    for company in inputs:
        status = "searched"
        urls: tuple[str, ...] = ()
        request_sha256 = ""
        try:
            url = request_url(company, plan)
            request_sha256 = sha256_hex(url.encode())
            access.prepare(company, search_url=url)
            access.allow(url)
            with company_requests(
                plan, company.key, search_url=url, company_name=company.name
            ):
                result = search(company, plan, access._get, clock, access.pace.sleep)
            urls = result.urls
        except (WebError, TransportFault) as error:
            reason = str(error) if isinstance(error, WebError) else "unavailable"
            if reason not in {"obstacle", "unavailable", "input_refused"}:
                raise
            status = reason
        rows.append(
            {
                "company_key": company.key,
                "request_sha256": request_sha256,
                "status": status,
                "urls": urls,
            }
        )
    return {
        "company_binding": _company_binding(inputs),
        "provider": plan.data["provider"],
        "manifest_sha256": plan.sha256,
        "extractor": plan.data["reviewed_by"],
        "rows": rows,
    }


def _field_audit(status: str, candidates: tuple[Candidate, ...]) -> dict[str, str]:
    proposed = {c.field for c in candidates}
    return {
        name: "proposed"
        if name in proposed
        else "missing"
        if status == "matched"
        else "refused_block"
        if status == "field_refused"
        else "not_extracted"
        for name in sorted(FIELDS)
    }


def _fetch_stage(
    inputs: tuple[Company, ...],
    plan: Manifest,
    access: Access,
    searched: Mapping[str, Any],
    folder: Path,
    clock: Callable[[], str],
) -> dict[str, object]:
    if (
        searched["company_binding"] != _company_binding(inputs)
        or searched["provider"] != plan.data["provider"]
        or searched["extractor"] != plan.data["reviewed_by"]
    ):
        raise WebError("search_binding_refused")
    by_key = {r["company_key"]: r for r in searched["rows"]}
    if len(by_key) != len(inputs) or set(by_key) != {c.key for c in inputs}:
        raise WebError("company_binding_refused")
    outcomes: list[dict[str, Any]] = []
    for company in inputs:
        row = by_key[company.key]
        if company.input_refused:
            if (
                row["status"] != "input_refused"
                or row["request_sha256"]
                or row["urls"]
                or plan.urls(company.key)
            ):
                raise WebError("search_binding_refused")
            outcomes.append(
                {
                    "company_key": company.key,
                    "search_status": "input_refused",
                    "pages": [],
                }
            )
            continue
        if row["request_sha256"] != sha256_hex(
            request_url(company, plan).encode()
        ) or set(plan.urls(company.key)) - set(row["urls"]):
            raise WebError("search_binding_refused")
        pages = []
        for url in row["urls"]:
            status, selected, bundle_identity = "not_selected", "", ""
            proposed: tuple[Candidate, ...] = ()
            if url in plan.urls(company.key):
                try:
                    page = access.page(company, url)
                    selected = page.identity
                    try:
                        selectors = plan.data["selectors"].get(host_of(url))
                        result = extract(
                            page.body,
                            company,
                            page.snapshot.sidecar,
                            selectors=selectors,
                            selectors_reviewed=selectors is not None,
                        )
                        status, proposed = result.status, result.candidates
                        if result.status == "matched":
                            bundle_identity = _publish(
                                folder,
                                "bundles/" + digest((company.key, selected)),
                                reviewer_bundle(company.name, result),
                                clock(),
                            )
                    except WebError:
                        status, proposed, bundle_identity = "field_refused", (), ""
                except ArchivedObstacle as error:
                    status, selected = "obstacle", error.page.identity
                except WebError as error:
                    if str(error) not in {"obstacle", "unavailable"}:
                        raise
                    status = str(error)
            pages.append(
                {
                    "url": url,
                    "status": status,
                    "identity": selected,
                    "proposed": [c.digest for c in proposed],
                    "fields": _field_audit(status, proposed),
                    "reviewer_bundle": bundle_identity,
                }
            )
        outcomes.append(
            {"company_key": company.key, "search_status": row["status"], "pages": pages}
        )
    return {
        "company_binding": _company_binding(inputs),
        "manifest_sha256": plan.sha256,
        "extractor": plan.data["reviewed_by"],
        "outcomes": outcomes,
    }


def _review_stage(
    inputs: tuple[Company, ...],
    plan: Manifest,
    fetched: Mapping[str, Any],
    searched: Mapping[str, Any],
    access: Access,
    reviews: Mapping[str, Any],
) -> dict[str, object]:
    if (
        fetched["company_binding"] != _company_binding(inputs)
        or fetched["manifest_sha256"] != plan.sha256
        or fetched["extractor"] != plan.data["reviewed_by"]
    ):
        raise WebError("fetch_binding_refused")
    by_key = {c.key: c for c in inputs}
    outcomes = []
    candidates: list[Candidate] = []
    for row in fetched["outcomes"]:
        company = by_key[row["company_key"]]
        pages = []
        for p in row["pages"]:
            proposed: tuple[Candidate, ...] = ()
            if p["identity"] and p["status"] == "obstacle":
                page = load_page(access.cache, company.key, p["identity"])
                if page.snapshot.sidecar.get("access_status") != "obstacle":
                    raise WebError("obstacle_binding_refused")
            elif p["identity"]:
                page = load_page(access.cache, company.key, p["identity"])
                if page.snapshot.sidecar["original_url"] != p["url"]:
                    raise WebError("page_binding_refused")
                selectors = plan.data["selectors"].get(host_of(p["url"]))
                try:
                    result = extract(
                        page.body,
                        company,
                        page.snapshot.sidecar,
                        selectors=selectors,
                        selectors_reviewed=selectors is not None,
                    )
                    bundle = (
                        sha256_hex(dump(reviewer_bundle(company.name, result)))
                        if result.status == "matched"
                        else ""
                    )
                except WebError:
                    if p["status"] != "field_refused":
                        raise
                else:
                    if result.status != p["status"]:
                        raise WebError("extraction_binding_refused")
                    proposed = result.candidates
                    if bundle and p["reviewer_bundle"] != bundle:
                        raise WebError("bundle_binding_refused")
            if [c.digest for c in proposed] != p["proposed"] or p[
                "fields"
            ] != _field_audit(p["status"], proposed):
                raise WebError("extraction_binding_refused")
            candidates.extend(proposed)
            pages.append(PageOutcome(p["url"], p["status"], proposed, p["identity"]))
        outcomes.append(Outcome(company.key, row["search_status"], tuple(pages)))
    expected_urls = {r["company_key"]: r["urls"] for r in searched["rows"]}
    evidence = reconcile(
        tuple(by_key), expected_urls, outcomes, reviews, identity(fetched["extractor"])
    )
    # Keep web fields separate; do not overwrite any register field.
    inventory = contribution(
        tuple(c for c in evidence.retained if c.field == "name"),
        reviews,
        fetched["extractor"],
    )
    return {
        "counts": evidence.counts,
        "retained": [asdict(c) for c in evidence.retained],
        "name_inventory": asdict(inventory),
        "reviews": reviews,
        "extractor": fetched["extractor"],
        "manifest_sha256": plan.sha256,
    }


def run_company_web(
    root: Path,
    environ: Mapping[str, str],
    transport: Transport,
    sleep: Callable[[float], None],
    *,
    clock: Callable[[], str] = utc_now,
    monotonic: Callable[[], float] = time.monotonic,
) -> int:
    """Only the opt-in command calls this; errors disclose no upstream values."""
    try:
        stage = environ.get("EII_COMPANY_WEB_STAGE", "")
        run_id = environ.get("EII_COMPANY_WEB_RUN_ID", "")
        if (
            stage not in {"inventory", "search", "fetch", "review"}
            or re.fullmatch(r"[a-z][a-z-]{0,39}", run_id) is None
        ):
            raise WebError("run_configuration_missing")
        cache = root / CACHE_RELATIVE
        inputs = input_companies(cache, environ)
        folder = cache / "company_web" / "runs" / run_id
        stamp = clock()
        if stage == "inventory":
            selected = _publish(
                folder,
                stage,
                {
                    "companies": [asdict(c) for c in inputs],
                    "company_binding": _company_binding(inputs),
                },
                stamp,
            )
        else:
            path = _cache_input(cache, environ.get("EII_COMPANY_WEB_MANIFEST", ""))
            plan = Manifest.load(
                path, environ.get("EII_COMPANY_WEB_MANIFEST_SHA256", "")
            )
            publish_snapshot(
                cache / "company_web" / "manifests",
                "json",
                plan.raw,
                {
                    "source_id": "company_web",
                    "key": "company_web/manifest",
                    "retrieved_utc": stamp,
                    "sha256": plan.sha256,
                    "reviewed_utc": plan.data["reviewed_utc"],
                },
            )
            inputs = tuple(c for c in inputs if c.key in plan.data["companies"])
            if set(plan.data["companies"]) != {c.key for c in inputs}:
                raise WebError("company_binding_refused")
            access = Access(plan, transport, cache, clock, Pacer(sleep, monotonic))
            if stage == "search":
                payload = _search_stage(inputs, plan, access, clock)
            else:
                searched = _read(
                    folder, "search", environ.get("EII_COMPANY_WEB_SEARCH_SHA256", "")
                )
                if searched["company_binding"] != _company_binding(inputs):
                    raise WebError("search_binding_refused")
                if stage == "fetch":
                    payload = _fetch_stage(
                        inputs, plan, access, searched, folder, clock
                    )
                else:
                    fetched = _read(
                        folder, "fetch", environ.get("EII_COMPANY_WEB_FETCH_SHA256", "")
                    )
                    reviews: dict[str, Any] = {}
                    if environ.get("EII_COMPANY_WEB_REVIEWS"):
                        review_path = _cache_input(
                            cache, environ["EII_COMPANY_WEB_REVIEWS"]
                        )
                        raw = review_path.read_bytes()
                        if sha256_hex(raw) != environ.get(
                            "EII_COMPANY_WEB_REVIEWS_SHA256"
                        ):
                            raise WebError("review_hash_refused")
                        reviews = loads(raw)
                        if not isinstance(reviews, dict):
                            raise WebError("review_shape_refused")
                    payload = _review_stage(
                        inputs, plan, fetched, searched, access, reviews
                    )
                    payload["search_identity"] = environ[
                        "EII_COMPANY_WEB_SEARCH_SHA256"
                    ]
                    payload["fetch_identity"] = environ["EII_COMPANY_WEB_FETCH_SHA256"]
            selected = _publish(folder, stage, payload, stamp)
        # A convenience receipt is not an input selection: consumers require explicit hashes.
        folder.mkdir(parents=True, exist_ok=True)
        selection = folder / "selection.json"
        previous = json.loads(selection.read_bytes()) if selection.exists() else {}
        selection.write_bytes(dump(dict(previous, **{stage: selected})))
        print("company_web stage_complete; evidence_cached")
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, SnapshotError):
        # Fixed diagnostic: never print register/query/page/provider/error values.
        print("company_web refused; lead_review_required")
        return 1
