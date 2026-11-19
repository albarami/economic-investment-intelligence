"""Finite, reviewed multi-input acquisition and immutable page table envelopes."""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urljoin

from .allowlist import approve, host_of
from .certificate_pins import Pin, PinError, load_pin, page_transport
from .kinds import read_bounded
from .page_archive import staged_source
from .page_html import Node, ShapeError, Tree
from .page_requests import PIN_HOSTS, check_target, page_context, page_requests
from .page_schema import SCHOOL_FIELDS, json_body, path, period, scalar, typed, validate
from .page_shapes import page_end, parse
from .receipts import sha256_hex, sidecar_for
from .registry import LICENCE_BASES, Entry
from .snapshots import Snapshot, SnapshotError, publish_snapshot, read_snapshot, utc
from .terms_text import terms_text_sha256
from .transport import Response, Transport, metadata_limit

METHOD = "page_acquire.fetch@v2"
# .overnight/IN/EVIDENCE-shapes.md, Live reads / L1 school layer query:
# the evidenced response top keys. No other envelope member enters the cache.
SCHOOL_QUERY_KEYS = frozenset(
    {
        "objectIdFieldName",
        "geometryType",
        "spatialReference",
        "hasZ",
        "hasM",
        "fields",
        "features",
        "exceededTransferLimit",
    }
)


def _html_without_form_secrets(body: bytes) -> bytes:
    root = Tree(body).root

    def render(node: Node) -> str:
        if (
            node.tag == "input"
            and node.attrs.get("name") == "__RequestVerificationToken"
        ):
            return ""
        text = "".join(
            html.escape(c)
            if isinstance(c, str) and node.tag not in {"script", "style"}
            else (c if isinstance(c, str) else render(c))
            for c in node.children
        )
        if node.tag == "root":
            return text
        attrs = "".join(
            " " + k + ('="' + html.escape(v, quote=True) + '"' if v is not None else "")
            for k, v in node.attrs.items()
        )
        start = "<" + node.tag + attrs + ">"
        if node.tag in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            return start
        return start + text + "</" + node.tag + ">"

    return render(root).encode()


def validate_entry(entry: Entry, review: Mapping[str, Any]) -> None:
    validate(review)
    expected_kind = {
        "fc_register": "fc_company_cards",
        "insurance_tables": "xlsx_sheet",
        "events_visit_qatar": "embedded_json",
        "events_qncc": "embedded_json",
        "suppliers_tawteen": "refusal",
        "manateq_tariffs": "html_blocks",
        "monaqasat_classified": "html_table",
        "schools_private_directory": "arcgis_query",
        "awards_owner_scrape": "html_table",
    }
    if expected_kind.get(entry.source_id) != review["kind"]:
        raise ShapeError("schema_missing")
    if entry.commit_allowed:
        raise ShapeError("commit_refused")
    # Ruling L-1001: pending terms fields (words, reading date) and a pending
    # basis of use (blank or the recorded "pending" value) are records and
    # never refuse the fetch; an unknown basis still does.
    if (
        not entry.publisher
        or (entry.licence_basis not in LICENCE_BASES and entry.licence_basis != "")
        or (entry.licence_basis == "owner_decision" and entry.decision_record != "0026")
    ):
        raise ShapeError("receipt_missing")
    urls = review["reviewed_urls"]
    if (
        not isinstance(urls, list)
        or not urls
        or any(not isinstance(u, str) for u in urls)
        or entry.url != review["url"]
        or entry.url not in urls
    ):
        raise ShapeError("blocked_host")
    for url in urls:
        decision = approve(url)
        # L-914: refusal URLs are non-fetched evidence metadata only. Exempt
        # the host check alone; scheme and credential refusals still apply.
        if not decision.ok and (
            review["kind"] != "refusal" or decision.reason != "host_refused"
        ):
            raise ShapeError("blocked_host")
    if review["columns"] != [[n, k] for n, k in entry.columns]:
        raise ShapeError("schema_missing")
    if (entry.row_count_min is not None or entry.row_count_max is not None) and review[
        "bounds_basis"
    ] != "observed":
        raise ShapeError("bounds_unconfirmed")


def fetch(
    entry: Entry,
    review: Mapping[str, Any],
    transport: Transport,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Snapshot:
    from .page_records import cache_directory, record_failure

    validate_entry(entry, review)
    cache_directory(cache, entry)
    stamp = clock()
    utc(stamp)
    if review["kind"] == "refusal":
        shape = review["shape"]
        utc(shape["observed_utc"])
        record_failure(cache, entry, shape["observed_utc"], shape["reason"])
        raise ShapeError(shape["reason"])
    if review["hold"] is not None:
        raise ShapeError(review["hold"])
    if review["max_bytes"] is None:
        raise ShapeError("acquisition_bound_unconfirmed")
    pins: dict[str, Pin] = {}
    reviewed_hosts = {host_of(url) for url in review["reviewed_urls"]}
    for spec in review["pins"]:
        if not isinstance(spec, dict) or spec.get("host") in pins:
            raise ShapeError("schema_missing")
        if spec.get("host") not in reviewed_hosts:
            raise PinError("certificate_host_mismatch")
        pins[spec["host"]] = load_pin(cache, entry.source_id, spec)
    inputs: list[tuple[Response, str, bytes, str]] = []
    shape = review["shape"]
    base_frame = tuple(review["reviewed_urls"])

    def _read(
        url: str,
        extension: str,
        *,
        extra: tuple[str, ...] = (),
        projection: bool = False,
    ) -> Response:
        frame = base_frame + extra
        if url not in frame or not approve(url).ok:
            raise ShapeError("blocked_host")
        captured = False
        with (
            page_requests(frame, pins),
            page_transport(
                None,
                browser=entry.source_id == "schools_private_directory"
                and url != entry.terms_url,
            ),
        ):
            check_target(url)
            if host_of(url) in PIN_HOSTS:
                page_context(host_of(url))
            with metadata_limit(review["max_bytes"]):
                response, failure = read_bounded(transport, sleep, url)
            from ..fc_register.acquire import eligible, obstacle
            from . import certificate_pins

            # Security checks precede obstacle classification, so a valid
            # capture cannot rescue a refused redirect, pin or oversized body.
            if response is not None:
                for target in (*response.hops, response.final_url):
                    check_target(target)
                    if host_of(target) in PIN_HOSTS:
                        page_context(host_of(target))
                if len(response.body) > review["max_bytes"]:
                    raise ShapeError("metadata_bytes")
            enabled = (
                entry.source_id == "schools_private_directory"
                and url != entry.terms_url
            )
            obstacle_reason = obstacle(response.body) if response is not None else None
            reason = failure.check if failure else obstacle_reason
            if reason or response is None:
                status = (
                    int(failure.observed)
                    if failure and failure.observed in {"403", "429", "503"}
                    else None
                )
                can_capture = eligible(
                    "http" if reason == "http_status" else reason or "access_failed",
                    status,
                )
                if not enabled or not can_capture:
                    raise ShapeError(
                        "unavailable" if obstacle_reason else reason or "access_failed"
                    )
                pin = pins.get(host_of(url))
                capture = (
                    certificate_pins.load_capture(
                        cache, entry.source_id, pin, max_bytes=review["max_bytes"]
                    )
                    if pin
                    else None
                )
                if capture is None:
                    raise ShapeError(reason or "access_failed")
                response, evidence = certificate_pins.admit_capture(capture, url)
                response = replace(response, evidence={"capture": evidence})
                captured = True
            if captured:
                for target in (*response.hops, response.final_url):
                    check_target(target)
                    if host_of(target) in PIN_HOSTS:
                        page_context(host_of(target))
        if len(response.body) > review["max_bytes"]:
            raise ShapeError("metadata_bytes")
        if any(
            x in response.body.lower()
            for x in (b"sign in", b"sign-in", b"robot check", b"paywall")
        ):
            raise ShapeError("unavailable")
        body = response.body
        representation = "original"
        if extension == "html":
            # The portal's hidden form credential never enters an archive.
            body = _html_without_form_secrets(body)
            representation = "form_secret_removed"
        if not projection:
            inputs.append((response, extension, body, representation))
        return response

    def read(
        url: str,
        extension: str,
        *,
        extra: tuple[str, ...] = (),
        projection: bool = False,
    ) -> Response:
        try:
            return _read(url, extension, extra=extra, projection=projection)
        except (ShapeError, PinError, SnapshotError) as exc:
            if (
                entry.source_id == "schools_private_directory"
                and url != entry.terms_url
            ):
                record_failure(cache, entry, stamp, str(exc))
            raise

    rows: list[dict[str, object]] = []
    coverage: list[dict[str, str]] = []
    kind = review["kind"]
    if kind == "fc_company_cards":
        from ..fc_register.acquire import pages as acquire_pages
        from ..fc_register.parse import fragment

        try:
            acquired = acquire_pages(
                transport, cache, pins, shape, review["max_bytes"], sleep
            )
            for response in acquired:
                inputs.append((response, "json", response.body, "fc_company_pane@v1"))
                rows.extend(fragment(response.body)["rows"])
        except (ShapeError, PinError, SnapshotError) as exc:
            record_failure(cache, entry, stamp, str(exc))
            if isinstance(exc, SnapshotError):
                raise ShapeError(str(exc)) from None
            raise
    elif kind in {"xlsx_sheet", "html_blocks"} and shape["discovery"] is not None:
        discovery = shape["discovery"]
        response = read(discovery["url"], "json", projection=True)
        listing = json_body(response.body)
        records = path(listing, discovery["record_path"])
        if not isinstance(records, list):
            raise ShapeError("schema_missing")
        if discovery["count_header"] is not None:
            try:
                count = int(response.headers[discovery["count_header"]])
                pages = int(response.headers[discovery["pages_header"]])
            except (ValueError, KeyError, TypeError):
                raise ShapeError("paging_incomplete") from None
            if count != len(records) or pages != 1:
                raise ShapeError("paging_incomplete")
        elif (
            isinstance(listing, dict)
            and isinstance(listing.get("d"), dict)
            and ("__next" in listing["d"] or "__count" in listing["d"])
        ):
            raise ShapeError("paging_incomplete")
        links = []
        projected = []
        for record in records:
            link = path(record, discovery["link_path"])
            if not isinstance(link, str):
                raise ShapeError("schema_missing")
            link = urljoin(discovery["url"], quote(link, safe=":/%"))
            links.append(link)
            item: dict[str, object] = {"url": link}
            if discovery["length_path"] is not None:
                length = path(record, discovery["length_path"])
                if (
                    not isinstance(length, str)
                    or not length.isascii()
                    or not length.isdigit()
                ):
                    raise ShapeError("schema_missing")
                item["length"] = int(length)
            if discovery["modified_path"] is not None:
                modified = path(record, discovery["modified_path"])
                if not isinstance(modified, str):
                    raise ShapeError("schema_missing")
                item["source_modified"] = modified
            projected.append(item)
        if len(set(links)) != len(links):
            raise ShapeError("paging_incomplete")
        # SharePoint's expanded Author/Editor/MetaInfo values are outside our input.
        projected_body = json.dumps(projected, sort_keys=True).encode()
        inputs.append((response, "json", projected_body, "reviewed_projection"))
        selected = (
            [review["url"]]
            if kind == "xlsx_sheet"
            else [p["url"] for p in shape["pages"]]
        )
        if any(link not in links for link in selected):
            raise ShapeError("blocked_host")
        if kind == "xlsx_sheet":
            response = read(review["url"], "xlsx")
            expected = next(i["length"] for i in projected if i["url"] == review["url"])
            if len(response.body) != expected:
                raise ShapeError("schema_missing")
            rows = parse(response.body, review)
        else:
            for page in shape["pages"]:
                response = read(page["url"], "html")
                page_rows = parse(response.body, review, url=page["url"])
                modification = next(
                    item.get("source_modified")
                    for item in projected
                    if item["url"] == page["url"]
                )
                for row in page_rows:
                    row["page_url"] = page["url"]
                    row["source_modified"] = modification
                rows.extend(page_rows)
                coverage.append({"url": page["url"], "state": page["state"]})
    elif kind == "arcgis_query":
        response = read(review["url"], "json")
        metadata = json_body(response.body)
        try:
            maximum = metadata["maxRecordCount"]
            advanced = metadata["advancedQueryCapabilities"]
            if (
                type(maximum) is not int
                or maximum < 1
                or shape["page_size"] > maximum
                or advanced["supportsPagination"] is not True
                or advanced["supportsOrderBy"] is not True
                or metadata["geometryType"] != shape["geometry"]
                or metadata["objectIdField"] != "objectid"
                or metadata["extent"]["spatialReference"]["wkid"]
                != shape["spatial_reference"]
            ):
                raise ShapeError("schema_missing")
        except (KeyError, TypeError):
            raise ShapeError("schema_missing") from None
        query_url = shape["layer"] + "/query"
        count_url = (
            query_url
            + "?"
            + urlencode({"where": "1=1", "returnCountOnly": "true", "f": "json"})
        )
        response = read(count_url, "json", extra=(count_url,), projection=True)
        count_body = json_body(response.body)
        # EVIDENCE-shapes.md, O6 schools: count.json has only {"count": ...}.
        if not isinstance(count_body, dict) or set(count_body) - {"count"}:
            raise ShapeError("school_field_refused")
        count_value = count_body.get("count")
        if type(count_value) is not int or count_value < 0:
            raise ShapeError("paging_incomplete")
        count = count_value
        inputs.append((response, "json", response.body, "original"))
        offset = 0
        last_id = None
        while offset < count:
            size = min(shape["page_size"], count - offset)
            address = (
                query_url
                + "?"
                + urlencode(
                    {
                        "where": "1=1",
                        "outFields": ",".join(SCHOOL_FIELDS),
                        "orderByFields": "objectid",
                        "returnGeometry": "true",
                        "resultOffset": offset,
                        "resultRecordCount": size,
                        "f": "json",
                    }
                )
            )
            # Response attributes are checked before read() adds anything to inputs.
            response = read(address, "json", extra=(address,), projection=True)
            obj = json_body(response.body)
            if not isinstance(obj, dict) or set(obj) - SCHOOL_QUERY_KEYS:
                raise ShapeError("school_field_refused")
            if (
                obj.get("geometryType") != shape["geometry"]
                or obj.get("spatialReference", {}).get("wkid")
                != shape["spatial_reference"]
            ):
                raise ShapeError("schema_missing")
            if "fields" in obj and (
                not isinstance(obj["fields"], list)
                or [f.get("name") for f in obj["fields"]] != list(SCHOOL_FIELDS)
            ):
                raise ShapeError("school_field_refused")
            records = path(obj, shape["record_path"])
            if not isinstance(records, list) or len(records) != size:
                raise ShapeError("paging_incomplete")
            for record in records:
                if not isinstance(record, dict) or set(record) != {
                    "attributes",
                    "geometry",
                }:
                    raise ShapeError("schema_missing")
                attrs = path(record, shape["attribute_path"])
                if not isinstance(attrs, dict) or set(attrs) != set(SCHOOL_FIELDS):
                    raise ShapeError("school_field_refused")
                typed(attrs, shape["record_schema"])
                geometry = record["geometry"]
                if not isinstance(geometry, dict) or set(geometry) != {"x", "y"}:
                    raise ShapeError("schema_missing")
                for coordinate in geometry.values():
                    if type(coordinate) not in {int, float} and not hasattr(
                        coordinate, "is_finite"
                    ):
                        raise ShapeError("schema_missing")
                    scalar(coordinate, "number")
                identifier = attrs["objectid"]
                if last_id is not None and identifier <= last_id:
                    raise ShapeError("paging_incomplete")
                last_id = identifier
                row = {
                    name: scalar(attrs[name], typ) for name, typ in review["columns"]
                }
                row["geometry"] = {
                    axis: scalar(v, "number") for axis, v in geometry.items()
                }
                rows.append(row)
            offset += len(records)
            if obj.get("exceededTransferLimit") is not (offset < count):
                raise ShapeError("paging_incomplete")
            inputs.append((response, "json", response.body, "original"))
    elif kind == "html_table" and shape["profile"] == "classified":
        response = read(review["url"], "html")
        total, last = page_end(response.body, shape)
        if total < 1 or last > total:
            raise ShapeError("paging_incomplete")
        seen: set[str] = set()
        for page in range(1, last + 1):
            address = shape["path_template"].format(page=page)
            if page == 1:
                if address != review["url"]:
                    raise ShapeError("blocked_host")
            else:
                response = read(address, "html", extra=(address,))
                if page_end(response.body, shape) != (total, last):
                    raise ShapeError("paging_incomplete")
            part = parse(response.body, review)
            if not part or len(rows) + len(part) > total:
                raise ShapeError("paging_incomplete")
            for row in part:
                identifier = str(row[review["columns"][1][0]])
                if identifier in seen:
                    raise ShapeError("paging_incomplete")
                seen.add(identifier)
            rows.extend(part)
            if len(rows) == total and page != last:
                raise ShapeError("paging_incomplete")
        if len(rows) != total:
            raise ShapeError("paging_incomplete")
    else:
        extension = "xlsx" if kind == "xlsx_sheet" else "html"
        response = read(review["url"], extension)
        rows = parse(response.body, review)
    first, last_period = period(rows, review["period_fields"])
    if entry.period_last and (last_period is None or last_period < entry.period_last):
        raise ShapeError("stale_period")
    if (entry.row_count_min is not None and len(rows) < entry.row_count_min) or (
        entry.row_count_max is not None and len(rows) > entry.row_count_max
    ):
        raise ShapeError("row_count")
    # Terms must use the same reviewed URL/pin policy. They are optional evidence,
    # never a reason to turn off a visitor-readable source.
    terms_hash: str | None = None
    terms_unread = ""
    if entry.terms_url:
        try:
            terms = read(entry.terms_url, "html", projection=kind == "fc_company_cards")
            terms_hash = terms_text_sha256(terms.body)
        except ShapeError as exc:
            if str(exc) not in {
                "unreachable",
                "http_status",
                "access_failed",
                "unavailable",
            }:
                raise
            terms_unread = str(exc)
    destination = cache
    with staged_source(cache, entry.key) as stage:
        lineage = []
        for index, (response, extension, body, representation) in enumerate(inputs):
            side = sidecar_for(
                entry,
                digest=sha256_hex(body),
                nbytes=len(body),
                fetch_url=response.final_url,
                fetch_host=host_of(response.final_url),
                retrieved_utc=stamp,
                publisher=entry.publisher,
                source_modified="",
                row_count=None,
                terms_sha256=terms_hash or "",
            )
            side.update(
                upstream_sha256=response.body_sha256
                if representation == "fc_company_pane@v1"
                else sha256_hex(response.body),
                **dict(response.evidence),
                representation=representation,
                as_of=stamp[:10],
            )
            key = "inputs/input-" + str(index)
            snapshot = publish_snapshot(stage / entry.key / key, extension, body, side)
            lineage.append(
                {
                    "key": key,
                    "identity": snapshot.sha256,
                    "sha256": snapshot.sha256,
                    "upstream_sha256": response.body_sha256
                    if representation == "fc_company_pane@v1"
                    else sha256_hex(response.body),
                    **dict(response.evidence),
                    "extension": extension,
                    "representation": representation,
                    "url": response.final_url,
                }
            )
        payload = {
            "version": 2,
            "source_id": entry.source_id,
            "rows": rows,
            "inputs": lineage,
            "as_of": stamp[:10],
            "publisher_date": review["publisher_date"],
            "period_first": first,
            "period_last": last_period,
            "retrieved_utc": stamp,
            "method": METHOD,
            "provenance": "Public",
            "completeness": "unknown",
            "coverage": coverage,
        }
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        side = sidecar_for(
            entry,
            digest=sha256_hex(body),
            nbytes=len(body),
            fetch_url=entry.url,
            fetch_host=host_of(entry.url),
            retrieved_utc=stamp,
            publisher=entry.publisher,
            source_modified=review["publisher_date"] or "",
            row_count=len(rows),
            terms_sha256=terms_hash or "",
        )
        side.update(
            as_of=stamp[:10],
            period_first=first,
            period_last=last_period,
            method=METHOD,
            inputs=lineage,
            terms_unread=terms_unread,
        )
        result = publish_snapshot(stage / entry.key, "json", body, side)
    return read_snapshot(destination / entry.key, result.sha256)
