"""S2-T13 evidence contract; no fetching and no source confirmation by inference.

S2-T19 supplies the registry Entry and its fetch sidecar, after a reviewer reads
terms for buying-entity/category use. It materializes an evidenced none_found
outcome in the registry too: its skip_reason is exactly "none_found" and its
release_tables is empty. Terms outcomes are not switch-offs under decision 0026;
a recorded visitor-readable source keeps an empty skip_reason and its release tables. S2-T08 calls completion_evidence before recording
both confirmations under PLN-25. Pending evidence never completes that gate.
The committed YAML uses JSON syntax (a YAML subset) and is read as strict JSON.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from eii_custodian.publicdata.fetch.allowlist import host_of, safe_https_shape
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.snapshots import utc

OUTCOMES = frozenset(
    {
        "not_yet_recorded",
        "terms_cover",
        "terms_absent",
        "terms_do_not_cover",
        "terms_forbid",
        "none_found",
    }
)
# Empty records a missing publisher basis, including pending/absent-terms evidence.
# The admitted registry basis is separately checked through basis_of_use.
BASES = frozenset({"dataset", "portal_terms", "provider_terms", ""})
RECORDED = OUTCOMES - {"not_yet_recorded", "none_found"}
CAVEAT = "No public tender source is recorded"


def _same_reviewed_origin(url: str, origin: str) -> bool:
    """Bind a reviewed URL to the HTTPS endpoint of the registered fetch URL."""
    if not safe_https_shape(url) or not safe_https_shape(origin):
        return False
    try:
        parts, registered = urlsplit(url), urlsplit(origin)
        return (
            # O11-O14 backslash/ASCII checks are parser-differential defence in depth.
            "\\" not in parts.netloc
            and "\\" not in registered.netloc
            and parts.netloc.isascii()
            and registered.netloc.isascii()
            and bool(host_of(origin))
            and host_of(url) == host_of(origin)
        )
    except ValueError:
        return False


@dataclass(frozen=True)
class Tender:
    """Review disposition bound to fetched page/terms hashes, never a keyword rule."""

    outcome: str = "not_yet_recorded"
    source_id: str = "tenders_pub"
    publisher: str = ""
    page: str = ""
    terms_url: str = ""
    retrieved_utc: str = ""
    terms_sha256: str = ""
    page_sha256: str = ""
    licence_id: str = ""
    licence_basis: str = ""
    period_first: str = ""
    period_last: str = ""
    review_ref: str = ""
    review_reason: str = ""
    intended_use: str = ""
    release_tables: tuple[str, ...] = ()
    shown: bool = False
    search_note: str = ""
    read_as_visitor: bool = False
    basis_of_use: str = ""
    decision_record: str = ""
    terms_words: str = ""
    terms_read_on: str = ""
    go_live_permission_needed: bool = False


@dataclass(frozen=True)
class WeightConfirmation:
    """Current C18 choice; changing admission needs file/licence/schema evidence."""

    people_method: str = "area"
    grid_source_id: str = "worldpop_qat_2020"
    grid_admitted: bool = False
    reason: str = "direct_url_unconfirmed"
    agesex_source_id: str = "worldpop_qat_agesex"
    agesex_is_weight: bool = False


@dataclass(frozen=True)
class Confirmation:
    tender: Tender
    weight: WeightConfirmation


@dataclass(frozen=True)
class Disposition:
    shown: bool
    status: str
    caveat: str


def _validate_tender(t: Tender) -> None:
    if t.outcome not in OUTCOMES or t.licence_basis not in BASES:
        raise ValueError("unknown outcome or forbidden licence basis")
    if t.shown is not (t.outcome in RECORDED):
        raise ValueError("shown does not match recorded visitor source")
    if t.outcome == "not_yet_recorded":
        if t.release_tables:
            raise ValueError("pending confirmation has release tables")
        return
    required = (
        t.page,
        t.retrieved_utc,
        t.page_sha256,
        t.review_ref,
        t.review_reason,
        t.intended_use,
    )
    if not all(value.strip() for value in required):
        raise ValueError("missing review or search evidence")
    if t.outcome == "none_found":
        if t.source_id or t.release_tables or not t.search_note.strip():
            raise ValueError("none_found requires search evidence and no release table")
        return
    if t.read_as_visitor is not True:
        raise ValueError("read_as_visitor must be true")
    if t.outcome == "terms_cover":
        if t.basis_of_use != t.licence_basis:
            raise ValueError("basis_of_use must match covering licence_basis")
        if t.decision_record != "":
            raise ValueError("decision_record must be empty for covering terms")
    else:
        if t.basis_of_use != "owner_decision":
            raise ValueError("basis_of_use must be owner_decision")
        if t.decision_record != "0026":
            raise ValueError("decision_record must be 0026")
    if t.outcome != "terms_absent" and not t.terms_words.strip():
        raise ValueError("terms_words missing")
    try:
        read_on = date.fromisoformat(t.terms_read_on)
    except ValueError as exc:
        raise ValueError("terms_read_on must be a real date") from exc
    if read_on.isoformat() != t.terms_read_on:
        raise ValueError("terms_read_on must use YYYY-MM-DD")
    if t.go_live_permission_needed is not (t.outcome != "terms_cover"):
        raise ValueError("go_live_permission_needed does not match terms reading")
    if not t.release_tables:
        raise ValueError("recorded source requires release_tables")
    if t.source_id != "tenders_pub" or not t.publisher.strip():
        raise ValueError("tender source identity missing")
    if t.outcome != "terms_absent" and not (
        t.terms_url.strip() and t.terms_sha256.strip()
    ):
        raise ValueError("missing terms evidence")
    if t.outcome == "terms_cover":
        covering = (
            t.terms_url,
            t.terms_sha256,
            t.licence_id,
            t.period_first,
            t.period_last,
        )
        if not all(value.strip() for value in covering) or t.licence_basis not in {
            "dataset",
            "portal_terms",
            "provider_terms",
        }:
            raise ValueError("missing covering terms evidence")


def _validate(c: Confirmation) -> None:
    _validate_tender(c.tender)
    if c.weight != WeightConfirmation():
        raise ValueError("weight confirmation is not the current area-only choice")


def _block(data: object, names: set[str]) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ValueError("confirmation block is not an object")
    if set(data) != names:
        missing = names - set(data)
        unknown = set(data) - names
        raise ValueError(
            f"missing fields {sorted(missing)}; unknown fields {sorted(unknown)}"
        )
    return {str(key): value for key, value in data.items()}


def load_confirmation(path: Path) -> Confirmation:
    """Read the task's closed record; reject missing blocks and malformed fields."""
    root = _block(json.loads(path.read_text(encoding="utf-8")), {"tender", "weight"})
    tender = _block(root["tender"], {f.name for f in fields(Tender)})
    weight = _block(root["weight"], {f.name for f in fields(WeightConfirmation)})
    strings: dict[str, str] = {}
    for name, value in tender.items():
        if name in {
            "shown",
            "release_tables",
            "read_as_visitor",
            "go_live_permission_needed",
        }:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{name} is not text")
        strings[name] = value
    flags: dict[str, bool] = {}
    for name in ("read_as_visitor", "go_live_permission_needed"):
        value = tender[name]
        if not isinstance(value, bool):
            raise ValueError(f"{name} is not a boolean")
        flags[name] = value
    shown, tables = tender["shown"], tender["release_tables"]
    if (
        not isinstance(shown, bool)
        or not isinstance(tables, list)
        or not all(isinstance(v, str) for v in tables)
    ):
        raise ValueError("invalid tender flags or tables")
    # Exact values and types: bools cannot be replaced by numeric JSON values.
    expected = WeightConfirmation()
    if any(
        type(weight[f.name]) is not type(getattr(expected, f.name))
        or weight[f.name] != getattr(expected, f.name)
        for f in fields(expected)
    ):
        raise ValueError("weight confirmation is not the current area-only choice")
    c = Confirmation(
        Tender(
            outcome=strings["outcome"],
            source_id=strings["source_id"],
            publisher=strings["publisher"],
            page=strings["page"],
            terms_url=strings["terms_url"],
            retrieved_utc=strings["retrieved_utc"],
            terms_sha256=strings["terms_sha256"],
            page_sha256=strings["page_sha256"],
            licence_id=strings["licence_id"],
            licence_basis=strings["licence_basis"],
            period_first=strings["period_first"],
            period_last=strings["period_last"],
            review_ref=strings["review_ref"],
            review_reason=strings["review_reason"],
            intended_use=strings["intended_use"],
            search_note=strings["search_note"],
            basis_of_use=strings["basis_of_use"],
            decision_record=strings["decision_record"],
            terms_words=strings["terms_words"],
            terms_read_on=strings["terms_read_on"],
            read_as_visitor=flags["read_as_visitor"],
            go_live_permission_needed=flags["go_live_permission_needed"],
            shown=shown,
            release_tables=tuple(tables),
        ),
        expected,
    )
    _validate(c)
    return c


def _registry_binds(tender: Tender, registry: Entry) -> bool:
    """Registry fields both the shown and the own-run pending bindings compare."""
    return (
        registry.source_id == "tenders_pub"
        and registry.publisher == tender.publisher
        and registry.terms_url == tender.terms_url
        and registry.licence_id == tender.licence_id
        and registry.licence_basis == tender.basis_of_use
        and registry.decision_record == tender.decision_record
        and registry.period_first == tender.period_first
        and registry.period_last == tender.period_last
        and registry.release_tables == tender.release_tables
        and registry.skip_reason == ""
    )


def tender_disposition(
    tender: Tender, registry: Entry | None, receipt: Mapping[str, object] | None
) -> Disposition:
    """Shown requires matching registry and fetched evidence, not review alone."""
    _validate_tender(tender)
    withheld = Disposition(False, "NO_DATA", CAVEAT)
    if tender.outcome not in RECORDED or registry is None or receipt is None:
        return withheld
    expected = {
        "source_id": tender.source_id,
        "key": registry.key,
        "publisher": tender.publisher,
        "licence_id": tender.licence_id,
        "licence_basis": tender.basis_of_use,
        "decision_record": tender.decision_record or None,
        "period_first": tender.period_first or None,
        "period_last": tender.period_last or None,
        "terms_sha256": tender.terms_sha256 or None,
        "fetch_url": registry.url,
        "fetch_host": registry.fetch_host,
        "release_tables": list(tender.release_tables),
        "switched_off": False,
    }
    registry_matches = (
        _registry_binds(tender, registry)
        and registry.key == tender.source_id
        and registry.fetch_host.casefold() == host_of(registry.url)
        and _same_reviewed_origin(tender.page, registry.url)
        and (
            (tender.outcome == "terms_absent" and not tender.terms_url)
            or _same_reviewed_origin(tender.terms_url, registry.url)
        )
        and bool(registry.basis_note.strip())
    )
    digest = receipt.get("sha256")
    retrieved = receipt.get("retrieved_utc")
    try:
        utc(retrieved)
    except ValueError:
        return withheld
    if (
        not registry_matches
        or any(receipt.get(k) != v for k, v in expected.items())
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        return withheld
    return Disposition(True, "SHOWN", "")


def own_run_pending(
    confirmation: Confirmation,
    registry: Entry | None,
    receipt: Mapping[str, object] | None,
) -> bool:
    """Allow the own-run source's true absence (decision 0084), never a receipt.

    The binding is every registry field the review records in the same form,
    the terms words and reading date included. The present-receipt binding
    of ``tender_disposition`` also compares the full page address and the basis note's words; S2-P40 rebinds those two and
    is not on this base, so the absent case binds the page's host (the
    registry address's host and fetch host both) and a non-empty basis note.
    """
    from .fetch.allowlist import host_of
    from .fetch.own_run import is_own_run_entry

    _validate(confirmation)
    t = confirmation.tender
    return (
        registry is not None
        and receipt is None
        and t.outcome in RECORDED
        and is_own_run_entry(registry)
        and registry.key == t.source_id
        and _registry_binds(t, registry)
        and registry.terms_words == t.terms_words
        and registry.terms_read_on == t.terms_read_on
        and host_of(registry.url) == registry.fetch_host == host_of(t.page)
        and bool(registry.basis_note.strip())
    )


def completion_evidence(
    confirmation: Confirmation,
    registry: Entry | None,
    receipt: Mapping[str, object] | None,
) -> Confirmation:
    """S2-T08 handoff: both confirmations plus the S2-T19 registry disposition.

    This validates supplied evidence, not the truth of a human review. The lead
    must supply that review and the registry-fetched evidence under PUB-01.
    """
    _validate(confirmation)
    t = confirmation.tender
    if t.outcome == "not_yet_recorded":
        raise ValueError("incomplete tender confirmation")
    if t.outcome in RECORDED:
        if (
            not own_run_pending(confirmation, registry, receipt)
            and not tender_disposition(t, registry, receipt).shown
        ):
            raise ValueError("registry and fetched evidence do not confirm tender")
    elif (
        registry is None
        or registry.source_id != "tenders_pub"
        or registry.skip_reason != t.outcome
        or registry.release_tables
    ):
        raise ValueError(
            "registry must record the disabled source or evidenced absence"
        )
    return confirmation
