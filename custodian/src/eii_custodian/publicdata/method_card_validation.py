"""MTH-03 source checks and fail-closed S2/S7 completion evidence.

Pass 1 defines an explicit interchange contract for invented fixtures. The live
S2-T08 artifact/config adapters and their plan-r2 module placement need
confirmation. This module never produces a pin, calculates a public figure, or
opens a source snapshot. An artifact comparison is additional to independent
source replay and a different maker's review, never a replacement for either.

Card synchronization binds only the document sections this record governs:
section 3 and cards C5, C6, C7 and C14, each found by its exact heading text.
``governed_sections_sha256`` covers exactly those spans with their checked
``method-pin`` blocks removed, so an unrelated edit elsewhere in the document
cannot turn the suite red, while an unchecked, moved or changed value inside a
governed span cannot pass. Makers are a closed set compared by exact member.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast

import yaml

from eii_custodian.publicdata.fetch.registry import Entry

Scalar = str | int | bool
MAKERS = frozenset(
    {
        "Anthropic",
        "OpenAI",
        "Google",
        "Moonshot AI",
        "xAI",
        "Zhipu AI",
        "DeepSeek",
        "Alibaba",
        "Cognition",
        "Cursor",
    }
)
GOVERNED_HEADINGS = (
    "## 3. Shared interval method and reliability mark",
    "### C5 Customs supplier lens",
    "### C6 Typical neighbours",
    "### C7 Shared reach between two doors",
    "### C14 Sale price per square metre",
)
ANCHOR_HEADINGS = {
    "wilson": GOVERNED_HEADINGS[0],
    "c5": GOVERNED_HEADINGS[1],
    "c6": GOVERNED_HEADINGS[2],
    "c7": GOVERNED_HEADINGS[3],
    "c14": GOVERNED_HEADINGS[4],
}
REQUIRED_PINS = frozenset(
    """wilson.period c5.hhi c5.prior12 c5.latest12 c5.trend
    c6.seed c6.release_sha256 c6.category_ids c6.candidate_set c6.box
    c6.confidence_min c6.radius_m c6.permutations c6.fdr c6.min_neighbours
    c6.min_clq c6.max_shown c6.expected_clq c6.expected_p c6.expected_q
    c7.coordinates c7.modes c7.cutoffs c7.speed_regime c7.district_weights
    c7.shared_b_given_a c7.shared_a_given_b c14.medians_2024 c14.medians_2025""".split()
)
# The 16 "none named" setting pins of the pass-1 source map: wilson.period
# and the C6/C7 settings whose only evidence is the recorded configuration
# itself. A configuration pin is checked by its recorded settings and their
# hash, never by an invented source lineage; c6.release_sha256 is a
# places_ovt source pin with lineage, so it is not one of them.
CONFIGURATION_PINS = frozenset(
    {
        "wilson.period",
        "c6.seed",
        "c6.category_ids",
        "c6.candidate_set",
        "c6.box",
        "c6.confidence_min",
        "c6.radius_m",
        "c6.permutations",
        "c6.fdr",
        "c6.min_neighbours",
        "c6.min_clq",
        "c6.max_shown",
        "c7.coordinates",
        "c7.modes",
        "c7.cutoffs",
        "c7.speed_regime",
    }
)
_SHA = re.compile(r"[a-f0-9]{64}")
_HEADING = re.compile(r"^(#{1,6}) ")
_BLOCK = re.compile(
    r"^<!-- method-pin:([a-z0-9_.]+) -->\n(.*?)\n<!-- /method-pin:\1 -->\n",
    re.M | re.S,
)


@dataclass(frozen=True)
class SourceLineageRef:
    source_id: str
    sha256: str
    publisher: str
    licence_id: str
    retrieved_utc: str
    method_id: str


@dataclass(frozen=True)
class CheckedPinEntry:
    pin_id: str
    card_anchor: str
    builder_maker: str
    reviewer_maker: str
    review_date: str
    checked_against_source: bool
    source_lineage: tuple[SourceLineageRef, ...]
    settings_sha256: str | None
    values: dict[str, Scalar]
    unpinned_reason: str | None


def _mapping(value: object, fields: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("pin_record_mapping")
    if fields is not None and set(value) != fields:
        raise ValueError("pin_record_fields")
    return cast(dict[str, object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("pin_record_text")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError("pin_record_hash")
    return value


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        raise ValueError("pin_input_unreadable") from None


def _load_json(body: bytes) -> dict[str, object]:
    try:
        return _mapping(json.loads(body))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("pin_json_invalid") from None


def _values(value: object) -> dict[str, Scalar]:
    result = _mapping(value)
    if any(
        not key or type(item) not in (str, int, bool) for key, item in result.items()
    ):
        raise ValueError("pin_value_type")
    return cast(dict[str, Scalar], result)


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        raise ValueError("pin_json_invalid") from None


def _registry_by_source(registry: Sequence[Entry]) -> dict[str, tuple[Entry, ...]]:
    by_source: dict[str, list[Entry]] = {}
    for row in registry:
        by_source.setdefault(row.source_id, []).append(row)
    return {key: tuple(rows) for key, rows in by_source.items()}


def _resolve_lineage(
    lineage: tuple[SourceLineageRef, ...],
    *,
    registry_by_source: Mapping[str, tuple[Entry, ...]],
    receipts_by_key: Mapping[str, Mapping[str, object]],
) -> None:
    for ref in lineage:
        candidates = registry_by_source.get(ref.source_id)
        if not candidates:
            raise ValueError("pin_lineage_source_unknown")
        matches: list[Entry] = []
        missing_receipt = False
        wrong_hash = False
        for entry in candidates:
            receipt = receipts_by_key.get(entry.key)
            if not isinstance(receipt, Mapping):
                missing_receipt = True
                continue
            receipt_hash = receipt.get("sha256")
            if not isinstance(receipt_hash, str):
                missing_receipt = True
                continue
            if receipt_hash == ref.sha256:
                matches.append(entry)
            else:
                wrong_hash = True
        if len(matches) > 1:
            raise ValueError("pin_lineage_source_ambiguous")
        if len(matches) == 1:
            continue
        if wrong_hash:
            raise ValueError("pin_lineage_receipt_mismatch")
        if missing_receipt:
            raise ValueError("pin_lineage_receipt_missing")
        raise ValueError("pin_lineage_source_unknown")


def _lineage(
    value: object,
    *,
    registry_by_source: Mapping[str, tuple[Entry, ...]] | None = None,
    receipts_by_key: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[SourceLineageRef, ...]:
    if not isinstance(value, list):
        raise ValueError("pin_lineage")
    rows = []
    for item in value:
        row = _mapping(item, set(SourceLineageRef.__dataclass_fields__))
        fields = {key: _text(item) for key, item in row.items()}
        _sha(fields["sha256"])
        try:
            retrieved = datetime.fromisoformat(fields["retrieved_utc"])
            if retrieved.utcoffset() is None:
                raise ValueError("retrieval_timezone")
        except ValueError:
            raise ValueError("pin_lineage_date") from None
        rows.append(SourceLineageRef(**fields))
    if len(set(rows)) != len(rows):
        raise ValueError("pin_lineage_duplicate")
    lineage = tuple(rows)
    if lineage and (registry_by_source is not None and receipts_by_key is not None):
        _resolve_lineage(
            lineage,
            registry_by_source=registry_by_source,
            receipts_by_key=receipts_by_key,
        )
    return lineage


def _entry(
    value: object,
    *,
    registry_by_source: Mapping[str, tuple[Entry, ...]] | None = None,
    receipts_by_key: Mapping[str, Mapping[str, object]] | None = None,
) -> CheckedPinEntry:
    row = _mapping(value, set(CheckedPinEntry.__dataclass_fields__))
    pin = _text(row["pin_id"])
    if pin not in REQUIRED_PINS or row["card_anchor"] != pin.split(".")[0]:
        raise ValueError("pin_unknown_or_anchor")
    builder = _text(row["builder_maker"])
    if builder not in MAKERS:
        raise ValueError("pin_maker_unknown")
    checked = row["checked_against_source"]
    if type(checked) is not bool:
        raise ValueError("pin_review_result")
    values = _values(row["values"])
    lineage = _lineage(
        row["source_lineage"],
        registry_by_source=registry_by_source,
        receipts_by_key=receipts_by_key,
    )
    if checked:
        reviewer = row["reviewer_maker"]
        if not isinstance(reviewer, str) or reviewer not in MAKERS:
            raise ValueError("pin_maker_unknown")
        if reviewer == builder:
            raise ValueError("pin_reviewer_missing_or_same_maker")
        review_date = _text(row["review_date"])
        try:
            if date.fromisoformat(review_date).isoformat() != review_date:
                raise ValueError("review_date_format")
        except ValueError:
            raise ValueError("pin_review_date") from None
        # A configuration pin is checked by its recorded settings and their
        # hash, never by an invented source lineage: empty lineage is
        # accepted only for a configuration pin and refused for a source pin.
        if (
            not values
            or row["unpinned_reason"] is not None
            or (pin not in CONFIGURATION_PINS and not lineage)
        ):
            raise ValueError("pin_checked_evidence_missing")
        settings_hash = _sha(row["settings_sha256"])
        reason = None
    else:
        if (
            values
            or lineage
            or row["settings_sha256"] is not None
            or row["reviewer_maker"] != ""
            or row["review_date"] != ""
        ):
            raise ValueError("pin_unpinned_carries_evidence")
        reason = _text(row["unpinned_reason"])
        reviewer, review_date, settings_hash = "", "", None
    return CheckedPinEntry(
        pin,
        pin.split(".")[0],
        builder,
        reviewer,
        review_date,
        checked,
        lineage,
        settings_hash,
        values,
        reason,
    )


def _record(
    path: Path,
    *,
    registry_by_source: Mapping[str, tuple[Entry, ...]] | None = None,
    receipts_by_key: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[dict[str, CheckedPinEntry], str]:
    try:
        loaded = yaml.safe_load(_read(path))
    except yaml.YAMLError:
        raise ValueError("pin_yaml_invalid") from None
    record = _mapping(
        loaded,
        {"schema_version", "governed_sections", "governed_sections_sha256", "pins"},
    )
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise ValueError("pin_schema_version")
    sections = record["governed_sections"]
    if (
        not isinstance(sections, list)
        or any(not isinstance(item, str) for item in sections)
        or sections != list(GOVERNED_HEADINGS)
    ):
        raise ValueError("card_sync_sections_unrecorded")
    baseline = _sha(record["governed_sections_sha256"])
    pins = record["pins"]
    if not isinstance(pins, list):
        raise ValueError("pin_record_list")
    entries = [
        _entry(
            item,
            registry_by_source=registry_by_source,
            receipts_by_key=receipts_by_key,
        )
        for item in pins
    ]
    by_id = {entry.pin_id: entry for entry in entries}
    if len(by_id) != len(entries) or set(by_id) != REQUIRED_PINS:
        raise ValueError("pin_missing_or_duplicate")
    return by_id, baseline


def _heading_level(line: str) -> int | None:
    match = _HEADING.match(line)
    return None if match is None else len(match.group(1))


def _inside(start: int, end: int, span: tuple[int, int]) -> bool:
    return span[0] <= start and end <= span[1]


def _governed_spans(document: str) -> dict[str, tuple[int, int]]:
    """Character spans of the governed sections, found by exact heading text.

    Each span runs from its heading line up to the next heading of the same
    or a higher level, or to the end of the document. A heading that is
    absent or duplicated fails the check closed.
    """
    lines = document.splitlines(keepends=True)
    starts: list[int] = []
    headings: list[tuple[int, int]] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        level = _heading_level(line)
        if level is not None:
            headings.append((offset, level))
        offset += len(line)
    spans: dict[str, tuple[int, int]] = {}
    for heading in GOVERNED_HEADINGS:
        found = [
            position
            for position, line in enumerate(lines)
            if line.rstrip("\r\n") == heading
        ]
        if len(found) != 1:
            raise ValueError("card_sync_section_missing")
        start = starts[found[0]]
        level = len(heading) - len(heading.lstrip("#"))
        end = len(document)
        for position, other in headings:
            if position > start and other <= level:
                end = position
                break
        spans[heading] = (start, end)
    return spans


def _c5_settings(settings: dict[str, object], entry: CheckedPinEntry) -> None:
    prior, latest = settings.get("prior_months"), settings.get("latest_months")
    if prior != [f"2024-{month:02}" for month in range(1, 13)]:
        raise ValueError("c5_window_prior_2024_required")
    if not isinstance(latest, list) or len(latest) != 12:
        raise ValueError("c5_window_latest_twelve_required")
    # Only window identity is checked here, never a numerical trend or HHI.
    calendar = [f"{year}-{month:02}" for year in (2025, 2026) for month in range(1, 13)]
    if latest not in [calendar[start : start + 12] for start in range(13)]:
        raise ValueError("c5_window_latest_2025_2026_required")
    # The parent review is per basket line, matching the per-line c5 values:
    # a released line without a reviewed parent, or a review without its
    # released line, is a missing parent review.
    lines = settings.get("lines")
    if (
        not isinstance(lines, dict)
        or not lines
        or any(not isinstance(key, str) or not key for key in lines)
    ):
        raise ValueError("c5_parent_review_missing")
    if set(entry.values) != set(lines):
        raise ValueError("c5_parent_review_missing")
    for line, review in lines.items():
        if (
            not isinstance(review, dict)
            or set(review) != {"parent_contains_excluded", "parent_treatment"}
            or type(review["parent_contains_excluded"]) is not bool
        ):
            raise ValueError("c5_parent_review_missing")
        contaminated = review["parent_contains_excluded"]
        treatment = review["parent_treatment"]
        if contaminated and treatment not in ("includes excluded lines", "withheld"):
            raise ValueError("c5_parent_requires_includes excluded lines_or_withheld")
        if not contaminated and treatment != "clean":
            raise ValueError("c5_parent_treatment")
        # MTH-30/PUB-44 wording: an earlier-period value over a parent that
        # also holds excluded lines is marked "includes excluded lines" or
        # withheld. Only the prior-12 and trend pins carry the mark.
        if entry.pin_id in ("c5.prior12", "c5.trend"):
            value = entry.values[line]
            if treatment == "withheld":
                if value != "NO_DATA:includes excluded lines":
                    raise ValueError("c5_parent_withheld_value")
            elif treatment == "includes excluded lines":
                if not isinstance(value, str) or not value.endswith(
                    ";caveat=includes excluded lines"
                ):
                    raise ValueError("c5_parent_visible_label_missing")
            elif isinstance(value, str) and (
                "NO_DATA:includes excluded lines" in value
                or ";caveat=includes excluded lines" in value
            ):
                raise ValueError("c5_parent_treatment")


def validate_source_check_record(
    record_path: Path,
    s2_t08_artifact_path: Path,
    generation_config_path: Path,
    *,
    registry: Sequence[Entry] | None = None,
    receipts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, CheckedPinEntry]:
    """Validate all required entries; pending rows do not require live inputs.

    A checked row binds exact values, complete lineage and recorded settings to
    the supplied producer artifact and the SHA-256 of the actual config bytes.
    The same schema-valid pending record is deliberately rejected by completion.
    """
    registry_by_source = _registry_by_source(registry) if registry is not None else None
    receipts_by_key = dict(receipts) if receipts is not None else None
    entries, _ = _record(
        record_path,
        registry_by_source=registry_by_source,
        receipts_by_key=receipts_by_key,
    )
    checked = [entry for entry in entries.values() if entry.checked_against_source]
    needs_resolution = any(entry.source_lineage for entry in checked)
    if needs_resolution and (registry_by_source is None or receipts_by_key is None):
        raise ValueError("pin_lineage_context_missing")
    if not checked:
        return entries
    config_body = _read(generation_config_path)
    config = _mapping(_load_json(config_body), {"schema_version", "pins"})
    artifact = _mapping(
        _load_json(_read(s2_t08_artifact_path)), {"schema_version", "pins"}
    )
    if any(
        type(row["schema_version"]) is not int or row["schema_version"] != 1
        for row in (config, artifact)
    ):
        raise ValueError("pin_schema_version")
    settings_by_pin = _mapping(config["pins"])
    produced_rows = artifact["pins"]
    if not isinstance(produced_rows, list) or set(settings_by_pin) - REQUIRED_PINS:
        raise ValueError("pin_artifact_fields")
    produced = {}
    for item in produced_rows:
        row = _mapping(item, {"pin_id", "values", "settings", "source_lineage"})
        pin = _text(row["pin_id"])
        if pin not in REQUIRED_PINS or pin in produced:
            raise ValueError("pin_artifact_duplicate_or_unknown")
        produced[pin] = row
    for entry in checked:
        if entry.settings_sha256 != hashlib.sha256(config_body).hexdigest():
            raise ValueError("pin_settings_hash_mismatch")
        produced_row = produced.get(entry.pin_id)
        if produced_row is None:
            raise ValueError("pin_artifact_missing")
        if _canonical(_values(produced_row["values"])) != _canonical(entry.values):
            raise ValueError("pin_value_mismatch")
        if (
            _lineage(
                produced_row["source_lineage"],
                registry_by_source=registry_by_source,
                receipts_by_key=receipts_by_key,
            )
            != entry.source_lineage
        ):
            raise ValueError("pin_lineage_mismatch")
        settings = _mapping(settings_by_pin.get(entry.pin_id))
        if _canonical(_mapping(produced_row["settings"])) != _canonical(settings):
            raise ValueError("pin_unrecorded_setting")
        if entry.pin_id in CONFIGURATION_PINS and any(
            key not in settings or _canonical(settings[key]) != _canonical(value)
            for key, value in entry.values.items()
        ):
            raise ValueError("pin_unrecorded_setting")
        if entry.pin_id.startswith("c5."):
            _c5_settings(settings, entry)
    return entries


def verify_method_cards_sync(record_path: Path, methods_doc_path: Path) -> None:
    """Refuse unchecked, duplicate, missing, moved or changed values.

    Every ``method-pin`` block must sit inside the governed span of its own
    card anchor, and the governed spans' block-free bytes must hash to the
    record's ``governed_sections_sha256``.
    """
    entries, baseline_hash = _record(record_path)
    try:
        document = _read(methods_doc_path).decode("utf-8")
    except UnicodeError:
        raise ValueError("card_sync_encoding") from None
    spans = _governed_spans(document)
    seen: set[str] = set()
    for match in _BLOCK.finditer(document):
        pin, raw = match.groups()
        entry = entries.get(pin)
        if pin in seen or entry is None or not entry.checked_against_source:
            raise ValueError("card_sync_unchecked_or_duplicate")
        span = spans.get(ANCHOR_HEADINGS[entry.card_anchor])
        if span is None or not _inside(match.start(), match.end(), span):
            if any(
                _inside(match.start(), match.end(), other) for other in spans.values()
            ):
                raise ValueError("card_sync_wrong_anchor")
            raise ValueError("card_sync_block_outside_sections")
        try:
            values = _values(json.loads(raw))
        except (ValueError, TypeError):
            raise ValueError("card_sync_value_invalid") from None
        if _canonical(values) != _canonical(entry.values):
            raise ValueError("card_sync_value_mismatch")
        seen.add(pin)
    expected = {pin for pin, entry in entries.items() if entry.checked_against_source}
    baseline = "".join(
        _BLOCK.sub("", document[spans[section][0] : spans[section][1]])
        for section in GOVERNED_HEADINGS
    )
    if seen != expected:
        raise ValueError("card_sync_missing_block")
    if "method-pin:" in baseline:
        raise ValueError("card_sync_malformed_block")
    if hashlib.sha256(baseline.encode("utf-8")).hexdigest() != baseline_hash:
        raise ValueError("card_sync_baseline_or_missing_value")


def completion_evidence(
    record_path: Path,
    s2_t08_artifact_path: Path,
    generation_config_path: Path,
    methods_doc_path: Path,
    *,
    gate: Literal["S2", "S7"],
    registry: Sequence[Entry] | None = None,
    receipts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, CheckedPinEntry]:
    """The MTH-03 check for either slice gate; an open item never clears it."""
    if gate not in ("S2", "S7"):
        raise ValueError("pin_gate_unknown")
    entries, _ = _record(
        record_path,
        registry_by_source=_registry_by_source(registry)
        if registry is not None
        else None,
        receipts_by_key=dict(receipts) if receipts is not None else None,
    )
    if any(not entry.checked_against_source for entry in entries.values()):
        raise ValueError(
            gate
            + ":unpinned:"
            + ",".join(
                sorted(
                    pin
                    for pin, entry in entries.items()
                    if not entry.checked_against_source
                )
            )
        )
    entries = validate_source_check_record(
        record_path,
        s2_t08_artifact_path,
        generation_config_path,
        registry=registry,
        receipts=receipts,
    )
    verify_method_cards_sync(record_path, methods_doc_path)
    return entries
