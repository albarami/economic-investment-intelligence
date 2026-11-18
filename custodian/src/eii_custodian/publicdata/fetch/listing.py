"""Check Overture listings against registered whole-file parts; select no new parts."""

from __future__ import annotations

import base64
import json
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree as ET

from eii_custodian.publicdata.fetch import registry
from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.kinds import Prepared, Read, _call_url, _failed
from eii_custodian.publicdata.fetch.partitions import request_receipt
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.places.fetch import _recorded

HOST = "overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
PREFIXES = {
    "places_ovt": "release/2026-10-21.0/theme=places/type=place/",
    "bldg_ovt": "release/2026-10-21.0/theme=buildings/type=building/",
}
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def prepare_listing(
    entry: Entry, reader: Read, entries: tuple[Entry, ...] | None
) -> Prepared:
    """Hash every listing response and refuse any drift before storing anything."""
    prefix = PREFIXES[entry.key]
    base = "https://" + HOST + "/?list-type=2&prefix=" + prefix
    if entry.url != base:
        return _refuse(entry, "listing_url")
    expected: dict[str, tuple[int, str]] = {}
    for part in entries if entries is not None else registry.load_registry():
        if not part.key.startswith(entry.key + "/"):
            continue
        key = urlsplit(part.url).path.lstrip("/")
        recorded, invalid = _recorded(part)
        if (
            invalid is not None
            or recorded is None
            or not key.startswith(prefix)
            or host_of(part.url) != HOST
        ):
            return _refuse(entry, "listing_registered_part")
        expected[key] = recorded
    if not expected:
        return _refuse(entry, "listing_registered_part")
    found: set[str] = set()
    tokens: set[str] = set()
    requests: list[dict[str, object]] = []
    raw_pages: list[str] = []
    url = base
    while True:
        page, failure = _call_url(url, reader)
        if failure is not None or page is None:
            return _failed(entry, failure)
        if any(host_of(hop) != HOST for hop in (*page.hops, page.final_url)):
            return _refuse(entry, "listing_redirect")
        try:
            root = ET.fromstring(page.body)
        except ET.ParseError:
            return _refuse(entry, "listing_xml")
        if root.tag != _NS + "ListBucketResult":
            return _refuse(entry, "listing_xml")
        objects = root.findall(_NS + "Contents")
        for item in objects:
            key = item.findtext(_NS + "Key", "")
            if not key.startswith(prefix):
                return _refuse(entry, "listing_prefix")
            if key in found:
                return _refuse(entry, "listing_duplicate")
            found.add(key)
            if key in expected:
                size, etag = expected[key]
                if item.findtext(_NS + "Size") != str(size):
                    return _refuse(entry, "listing_size")
                if item.findtext(_NS + "ETag") != '"' + etag + '"':
                    return _refuse(entry, "listing_etag")
        requests.append(request_receipt(page, len(objects)))
        raw_pages.append(base64.b64encode(page.body).decode("ascii"))
        truncated = root.findtext(_NS + "IsTruncated")
        if truncated == "false":
            break
        token = root.findtext(_NS + "NextContinuationToken", "")
        if truncated != "true" or not token or token in tokens:
            return _refuse(entry, "listing_continuation")
        tokens.add(token)
        url = base + "&" + urlencode({"continuation-token": token})
    if not expected.keys() <= found:
        return _refuse(entry, "listing_missing")
    body = json.dumps({"listing_pages_base64": raw_pages}, sort_keys=True).encode()
    return Prepared(
        body,
        base,
        HOST,
        entry.publisher,
        "",
        len(found),
        "",
        None,
        requests=tuple(requests),
    )


def _refuse(entry: Entry, check: str) -> Prepared:
    return _failed(
        entry,
        AttemptFailure(1, entry.url, check, "registered release listing", "invalid"),
    )
