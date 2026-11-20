"""Closed company fields and deterministic, hash-bound lineage; no row diagnostics."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from typing import Any
from urllib.parse import unquote, urlsplit

from ..fetch.receipts import sha256_hex
from ..fetch.snapshots import utc

VERSION = "company_web@v1"
FIELDS = frozenset({"name", "address", "website", "activity"})
DIGEST = re.compile(r"[a-f0-9]{64}")
_FORBIDDEN = re.compile(
    r"(?<!\d)(?:\d{8}|\d{11})(?!\d)|[\w.+-]+@[\w.-]+|"
    r"\b(?:tel|telephone|phone|fax|mobile|mr|mrs|ms|dr|prof|"
    r"person|employee|salary|salaries|wage|wages|chief|director|manager|"
    r"job.?title|ceo|cfo|cto)\b",
    re.IGNORECASE,
)


class WebError(ValueError):
    """Only closed reason tokens may cross the diagnostic boundary."""


def dump(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True) + "\n").encode()


def loads(body: str | bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise WebError("duplicate_property_refused")
            result[key] = value
        return result

    return json.loads(body, object_pairs_hook=unique)


def digest(value: object) -> str:
    return sha256_hex(dump(value))


def safe_text(field_name: str, value: object) -> str:
    if field_name not in FIELDS or not isinstance(value, str) or not value.strip():
        raise WebError("field_refused")
    decoded = unicodedata.normalize("NFKC", value)
    while True:
        next_decoded = unicodedata.normalize("NFKC", unquote(decoded))
        if next_decoded == decoded:
            break
        decoded = next_decoded
    if _FORBIDDEN.search(decoded) or any(ord(c) < 32 for c in value):
        raise WebError("field_refused")
    if field_name == "website":
        checked_url(value)
    return value


def checked_url(url: str, *, query: bool = False) -> str:
    from ..fetch.allowlist import approve_closed, host_of

    try:
        parts = urlsplit(url)
        if (
            not approve_closed(url, hosts=frozenset({host_of(url)}), selectors=()).ok
            and not query
        ) or (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 443)
            or parts.fragment
            or any(ord(c) <= 32 for c in url)
        ):
            raise WebError("url_refused")
    except ValueError:
        raise WebError("url_refused") from None
    return url


def lineage(body: bytes, meta: Mapping[str, Any]) -> None:
    if (
        meta.get("source_id") != "company_web"
        or meta.get("sha256") != sha256_hex(body)
        or meta.get("bytes") != len(body)
        or meta.get("method") != VERSION
        or meta.get("licence_basis") != "owner_decision"
        or meta.get("decision_record") != "0026"
        or not meta.get("licence_id")
        or not meta.get("publisher")
        or not meta.get("key")
        or not isinstance(meta.get("extractor"), dict)
    ):
        raise WebError("lineage_refused")
    try:
        utc(meta.get("retrieved_utc"))
        checked_url(str(meta["fetch_url"]))
        checked_url(str(meta["original_url"]))
    except (ValueError, KeyError):
        raise WebError("lineage_refused") from None


@dataclass(frozen=True)
class Company:
    key: str = dc_field(repr=False)
    name: str = dc_field(repr=False)
    source: str
    register_fields: Mapping[str, str] = dc_field(repr=False)

    def __post_init__(self) -> None:
        safe_text("name", self.name)
        if not self.key or self.source not in {"register", "fc_register"}:
            raise WebError("company_refused")
        if set(self.register_fields) - FIELDS:
            raise WebError("register_field_refused")


@dataclass(frozen=True)
class Candidate:
    company_key: str = dc_field(repr=False)
    field: str
    value: str = dc_field(repr=False)
    page_sha256: str
    fragment_sha256: str
    parser: str
    url: str = dc_field(repr=False)
    retrieved_utc: str
    publisher: str = dc_field(repr=False)
    licence_basis: str
    extractor_sha256: str
    conflict: bool = False

    def validate(self) -> None:
        safe_text(self.field, self.value)
        # URL paths and publisher text are output too; never rely on check_docs.
        safe_text("address", self.url)
        safe_text("name", self.publisher)
        checked_url(self.url)
        utc(self.retrieved_utc)
        if (
            not self.company_key
            or self.parser != VERSION
            or self.licence_basis != "owner_decision"
            or DIGEST.fullmatch(self.page_sha256) is None
            or DIGEST.fullmatch(self.fragment_sha256) is None
            or DIGEST.fullmatch(self.extractor_sha256) is None
        ):
            raise WebError("candidate_refused")

    @property
    def digest(self) -> str:
        self.validate()
        return digest(asdict(self))


@dataclass(frozen=True)
class Extraction:
    status: str
    candidates: tuple[Candidate, ...]
    fragment: bytes = dc_field(repr=False)
    page_sha256: str
    url: str = dc_field(repr=False)
