"""Activity spine and human review queue.

Status is always recomputed from the feeds, the ISIC classes and the review
file; a status written in the review file is never trusted. Only a 7-digit code
whose four-digit prefix is a known ISIC class, inside the review scope and
signed by a reviewer on an ISO date, can be mapped. Model decisions additionally
require a bound, independently audited batch under decision 0075.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import Entry, load_registry, parse_yaml
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.review.cache_fixture import read_cached, read_rows
from eii_custodian.publicdata.series.baskets import ACTIVITIES, reviewed_inputs
from eii_custodian.publicdata.series.parse import FIELD_MAP, confirmed_rows

STATUSES = (
    "mapped",
    "unreviewed",
    "not_mappable_legacy",
    "not_mappable_invalid_prefix",
    "not_mappable_rejected",
)
REASONS = (
    "reviewer_approved",
    "reviewer_rejected",
    "awaiting_human_review",
    "outside_review_scope",
    "legacy_code_length",
    "invalid_isic_prefix",
)
SPINE_COLUMNS = (
    "code",
    "code_length",
    "name_ar",
    "isic_class",
    "status",
    "reason",
    "reviewed_by_role",
    "reviewed_on",
)
TOP_CODES = 200
FOOD_PREFIX = "56"
PLAYBOOK_CLASSES = frozenset({"5510", "5610", "5630"})
CODE_SYSTEM_VERSION = "licence_codes_2025_05"
METHOD_VERSION = "activity_spine.v1"
FEED_KEYS = ("lic_active", "lic_cancelled")
_ISIC_FEED = "cls_isic4"
_ISIC_FIELDS = frozenset({"Code", "Description"})
_EVIDENCE_MARK = "EVIDENCE_ONLY:"
_DIGITS = re.compile(r"\A[0-9]+\Z")
_CLASS_DIGITS = re.compile(r"\A[0-9]{4}\Z")
_HIGHER_LEVEL = re.compile(r"\A(?:[A-Za-z]|[0-9]{2}|[0-9]{3})\Z")
_ISO_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_CLASS_TITLE = "class_title"
_REVIEW_TOKEN = re.compile(r"\A[0-9]+(?:\.[0-9]+)*\Z")
_BARE_RUN = re.compile(r"(?<![0-9])[0-9]{8}(?![0-9])|(?<![0-9])[0-9]{11}(?![0-9])")
_REVIEW_GROUP = 4
_DOTTED_LENGTHS = frozenset({8, 11})
_REVIEW = Path(__file__).resolve().parents[4] / "publicdata" / "review"


class SpineError(Exception):
    """The activity inputs or the review file are not acceptable."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ActivityRow:
    """One aggregated commerce code with its national counts and its feeds."""

    code: str
    name_ar: str
    active_count: int
    cancelled_count: int
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class IsicClass:
    """One ISIC Rev.4 class title."""

    code: str
    label_en: str
    label_ar: str


@dataclass(frozen=True)
class ReviewRow:
    """One row of the review file, with its claimed status."""

    code: str
    code_length: int
    name_ar: str
    isic_class: str
    status: str
    reason: str
    reviewed_by_role: str
    reviewed_on: str


@dataclass(frozen=True)
class SpineRow:
    """One derived spine row. The status here is recomputed, never claimed."""

    code: str
    code_length: int
    name_ar: str
    isic_class: str
    status: str
    reason: str
    reviewed_by_role: str
    reviewed_on: str


@dataclass(frozen=True)
class CoverageRow:
    """One status with its code count and its national active count."""

    status: str
    code_count: int
    active_count: int


@dataclass(frozen=True)
class ClassBucketCounts:
    """The four active-count buckets of PUB-67 with the other-length split."""

    seven_valid_prefix: int
    seven_invalid_prefix: int
    six_legacy: int
    other_length: int
    five_digit: int
    eight_digit: int
    total_active: int


@dataclass(frozen=True)
class Spine:
    """The spine rows by code, the coverage rows and the review queue."""

    rows: tuple[SpineRow, ...]
    coverage: tuple[CoverageRow, ...]
    queue: tuple[SpineRow, ...]


@dataclass(frozen=True)
class SupplierMembership:
    """Reviewed basket-supplier codes.

    ``complete`` false means the basket file is missing or unfinished. An empty
    complete membership is a real answer that there are no supplier codes, and
    only a caller who supplies that object may say so.
    """

    codes: tuple[str, ...]
    complete: bool


@dataclass(frozen=True)
class ReviewedBinding:
    """The version and input identities an approval was signed against.

    Each identity is the input name, its code and the SHA-256 of the
    meaning-bearing value as it stood when the reviewer signed; model decisions
    also bind the exact bytes of the independently audited batch file.
    """

    code_system_version: str
    input_sha256: tuple[tuple[str, str, str], ...]
    audit_sha256: str = ""


@dataclass(frozen=True)
class ReviewManifest:
    """Lineage for one spine build: version, source hashes and review hashes."""

    code_system_version: str
    method_version: str
    source_hashes: tuple[tuple[str, str], ...]
    review_sha256: str
    class_title_sha256: str


@dataclass(frozen=True)
class LeftOut:
    """Rows left out of one feed, counted by the code field's pattern class."""

    feed: str
    field: str
    pattern: str
    count: int


@dataclass(frozen=True)
class FeedRead:
    """One licence feed aggregated by activity code, with rows left out."""

    rows: tuple[ActivityRow, ...]
    left_out: tuple[LeftOut, ...] = ()


@dataclass(frozen=True)
class ClassRead:
    """ISIC classes from the real file, with higher levels left out."""

    classes: tuple[IsicClass, ...]
    left_out: tuple[LeftOut, ...] = ()


@dataclass(frozen=True)
class ActivityInputs:
    """The spine with the parsed activities and classes the graph also needs."""

    spine: Spine
    activities: tuple[ActivityRow, ...]
    classes: tuple[IsicClass, ...]
    manifest: ReviewManifest | None = None
    left_out: tuple[LeftOut, ...] = ()


def spine_path() -> Path:
    """Return the committed review file path."""
    return _REVIEW / "activity_spine.csv"


def allowlist_path() -> Path:
    """Return the committed category allow-list path."""
    return _REVIEW / "category_allowlist.csv"


def release_field(feed: str, column: str) -> str:
    """Read an EVIDENCE_ONLY: prefix as a mark on the release column, not part of its name."""
    found = [
        source
        for source, (_table, release) in FIELD_MAP[feed].items()
        if release.removeprefix(_EVIDENCE_MARK) == column
    ]
    if len(found) != 1:
        raise SpineError("activity column is not one field: " + column)
    return found[0]


def parse_isic_rows(rows: Iterable[Mapping[str, object]]) -> ClassRead:
    """Read Code and Description; a four-digit code is a class and higher levels are counted."""
    found: dict[str, IsicClass] = {}
    omitted: dict[str, int] = {}
    for row in rows:
        present = set(row)
        unknown = present - _ISIC_FIELDS
        missing = _ISIC_FIELDS - present
        if unknown:
            names = ",".join(sorted(str(item) for item in unknown))
            raise SpineError("unknown isic field " + names)
        if missing:
            raise SpineError("missing isic field " + ",".join(sorted(missing)))
        code = row["Code"]
        description = row["Description"]
        if not isinstance(code, str) or not isinstance(description, str):
            raise SpineError("isic field is not text")
        if _CLASS_DIGITS.match(code) is not None:
            if description == "":
                raise SpineError("isic class title is empty")
            item = IsicClass(code=code, label_en=description, label_ar="")
            held = found.get(code)
            if held is not None and held != item:
                raise SpineError("conflicting isic title for " + code)
            found[code] = item
            continue
        if _HIGHER_LEVEL.match(code) is not None:
            pattern = _pattern_class(code)
            omitted[pattern] = omitted.get(pattern, 0) + 1
            continue
        raise SpineError("isic code pattern is not a class or a higher level")
    return ClassRead(
        classes=tuple(found[code] for code in sorted(found)),
        left_out=_left_out(_ISIC_FEED, "Code", omitted),
    )


def entry_by_key(entries: Sequence[Entry], key: str) -> Entry:
    """Return the one registry entry of a key, or refuse a missing or doubled key."""
    found = [entry for entry in entries if entry.key == key]
    if not found:
        raise SpineError("registry key missing: " + key)
    if len(found) > 1:
        raise SpineError("registry key is not unique: " + key)
    return found[0]


def parse_feed_rows(rows: Iterable[Mapping[str, object]], entry: Entry) -> FeedRead:
    """Aggregate one confirmed licence feed by activity code.

    Municipality, year and month stay in the source row and are summed away.
    A code that is not a digit string is left out and counted by pattern class.
    """
    feed = entry.source_id
    if feed not in FEED_KEYS:
        raise SpineError("unknown activity feed " + feed)
    try:
        confirmed = confirmed_rows(entry, [dict(row) for row in rows])
    except ValueError as error:
        raise SpineError(str(error)) from error
    code_field = release_field(feed, "activity_code")
    name_field = release_field(feed, "activity_name_ar")
    count_column = "active_count" if feed == "lic_active" else "cancelled_count"
    count_field = release_field(feed, count_column)
    merged: dict[str, tuple[str, int]] = {}
    omitted: dict[str, int] = {}
    for row in confirmed:
        raw_code = row[code_field]
        name = _text(row[name_field], "activity_name_ar")
        count = _count(row[count_field], count_column)
        if not isinstance(raw_code, str) or _DIGITS.match(raw_code) is None:
            if not isinstance(raw_code, str):
                raise SpineError(feed + " field type: " + code_field)
            pattern = _pattern_class(raw_code)
            omitted[pattern] = omitted.get(pattern, 0) + 1
            continue
        held = merged.get(raw_code)
        if held is None:
            merged[raw_code] = (name, count)
            continue
        if held[0] != name:
            raise SpineError("conflicting activity name for " + raw_code)
        merged[raw_code] = (name, held[1] + count)
    parsed = tuple(
        ActivityRow(
            code=code,
            name_ar=name,
            active_count=count if feed == "lic_active" else 0,
            cancelled_count=count if feed == "lic_cancelled" else 0,
            source_ids=(feed,),
        )
        for code, (name, count) in sorted(merged.items())
    )
    return FeedRead(rows=parsed, left_out=_left_out(feed, code_field, omitted))


def read_cached_feed(cache: Path, entry: Entry, *, digest: str) -> FeedRead:
    """Read one cached licence feed into aggregated rows and the left-out report."""
    return parse_feed_rows(read_rows(read_cached(cache, entry, digest=digest)), entry)


def read_cached_classes(cache: Path, entry: Entry, *, digest: str) -> ClassRead:
    """Read the cached class file into classes and the left-out report."""
    if entry.source_id != _ISIC_FEED:
        raise SpineError("unknown class feed " + entry.source_id)
    return parse_isic_rows(read_rows(read_cached(cache, entry, digest=digest)))


def merge_feed_rows(
    active: Sequence[ActivityRow], cancelled: Sequence[ActivityRow]
) -> tuple[ActivityRow, ...]:
    """Join the two feeds by code, keeping the presence of each feed."""
    merged: dict[str, tuple[str, int, int, list[str]]] = {}
    for feed, rows in (("lic_active", active), ("lic_cancelled", cancelled)):
        for row in rows:
            held = merged.get(row.code)
            if held is None:
                merged[row.code] = (
                    row.name_ar,
                    row.active_count,
                    row.cancelled_count,
                    [feed],
                )
                continue
            if held[0] != row.name_ar:
                raise SpineError("conflicting activity name for " + row.code)
            sources = held[3]
            if feed not in sources:
                sources.append(feed)
            merged[row.code] = (
                held[0],
                held[1] + row.active_count,
                held[2] + row.cancelled_count,
                sources,
            )
    return tuple(
        ActivityRow(
            code=code,
            name_ar=held[0],
            active_count=held[1],
            cancelled_count=held[2],
            source_ids=tuple(feed for feed in FEED_KEYS if feed in held[3]),
        )
        for code, held in sorted(merged.items())
    )


def review_binding(
    code_system_version: str, classes: Sequence[IsicClass]
) -> ReviewedBinding:
    """Record the version and class-title identities a review was signed against."""
    return ReviewedBinding(
        code_system_version=code_system_version,
        input_sha256=tuple(
            (
                _CLASS_TITLE,
                row.code,
                _class_title_identity(row.code, row.label_en, row.label_ar),
            )
            for row in sorted(classes, key=lambda item: item.code)
        ),
    )


def binding_path(review_path: Path) -> Path:
    """Return the binding file stored beside a review file."""
    return review_path.with_name(review_path.stem + ".binding.json")


def basket_membership(
    baskets_document: object, activities: Sequence[ActivityRow]
) -> tuple[tuple[str, ...], SupplierMembership]:
    """Derive review scope only, never mapping approval, from reviewed baskets."""
    if not isinstance(baskets_document, dict) or not str(
        baskets_document.get("status", "")
    ).startswith("reviewed:"):
        raise SpineError("basket file is not reviewed")
    try:
        inputs = [
            item
            for activity in sorted(ACTIVITIES)
            for item in reviewed_inputs(baskets_document, activity)
        ]
    except ValueError as error:
        raise SpineError(str(error)) from error
    if {row["activity"] for row in baskets_document["activities"]} != PLAYBOOK_CLASSES:
        raise SpineError("playbook classes differ from the baskets")
    supplier_classes = {str(item["supplier_isic"]) for item in inputs}
    codes = {row.code for row in activities if len(row.code) == 7}
    for supplier in sorted(supplier_classes):
        if _CLASS_DIGITS.fullmatch(supplier) is None:
            raise SpineError("supplier class is not four digits: " + supplier)
        if not any(code[:4] == supplier for code in codes):
            raise SpineError("supplier class has no activity code: " + supplier)
    playbook = tuple(sorted(code for code in codes if code[:4] in PLAYBOOK_CLASSES))
    suppliers = tuple(sorted(code for code in codes if code[:4] in supplier_classes))
    return playbook, SupplierMembership(suppliers, True)


def read_activity_rows(
    cache: Path, entries: Sequence[Entry], selected: Mapping[str, str]
) -> tuple[tuple[ActivityRow, ...], tuple[tuple[str, str], ...], tuple[LeftOut, ...]]:
    """Read and verify both licence feeds, retaining their hashes and exclusions."""
    active_entry = entry_by_key(entries, "lic_active")
    cancelled_entry = entry_by_key(entries, "lic_cancelled")
    active_body = read_cached(
        cache, active_entry, digest=selected.get(active_entry.key, "")
    )
    cancelled_body = read_cached(
        cache, cancelled_entry, digest=selected.get(cancelled_entry.key, "")
    )
    active = parse_feed_rows(read_rows(active_body), active_entry)
    cancelled = parse_feed_rows(read_rows(cancelled_body), cancelled_entry)
    return (
        merge_feed_rows(active.rows, cancelled.rows),
        (
            _source_hash("lic_active", active_body.sidecar),
            _source_hash("lic_cancelled", cancelled_body.sidecar),
        ),
        active.left_out + cancelled.left_out,
    )


def load_activity_inputs(
    cache: Path,
    playbook_codes: Sequence[str],
    *,
    supplier_membership: SupplierMembership,
    registry: Sequence[Entry] | None = None,
    review_path: Path | None = None,
    code_system_version: str = CODE_SYSTEM_VERSION,
    selections: Mapping[str, str] | None = None,
) -> ActivityInputs:
    """Read the three cached keys, the review file and the spine they derive."""
    entries = load_registry() if registry is None else registry
    selected = reviewed_selections(cache) if selections is None else selections
    activities, feed_hashes, left_out = read_activity_rows(cache, entries, selected)
    class_entry = entry_by_key(entries, _ISIC_FEED)
    class_body = read_cached(
        cache, class_entry, digest=selected.get(class_entry.key, "")
    )
    class_read = parse_isic_rows(read_rows(class_body))
    path = review_path if review_path is not None else spine_path()
    reviews = read_review_csv(path)
    spine = build_spine(
        activities,
        class_read.classes,
        reviews,
        playbook_codes,
        supplier_membership=supplier_membership,
        code_system_version=code_system_version,
        reviewed_binding=load_recorded_binding(path, reviews),
        audit_path=path.with_name("activity_spine_audits.json"),
    )
    manifest = ReviewManifest(
        code_system_version=code_system_version,
        method_version=METHOD_VERSION,
        source_hashes=(*feed_hashes, _source_hash(_ISIC_FEED, class_body.sidecar)),
        review_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        class_title_sha256=_class_title_sha256(class_read.classes),
    )
    return ActivityInputs(
        spine=spine,
        activities=activities,
        classes=class_read.classes,
        manifest=manifest,
        left_out=left_out + class_read.left_out,
    )


def committed_activity_inputs(
    cache: Path, baskets: Path, review_path: Path | None = None
) -> tuple[ActivityInputs, tuple[str, ...], SupplierMembership, dict[str, str]]:
    """Build the inputs of one committed review folder from its baskets.

    This is the one sequence every caller of the committed review follows:
    the reviewed selections, both licence feeds, the basket membership of the
    reviewed baskets document, then the spine of that review. ``review_path``
    ``None`` means the committed review file. Returns the inputs, the playbook
    codes, the supplier membership and the reviewed selections.
    """
    selected = reviewed_selections(cache)
    entries = load_registry()
    activities, _, _ = read_activity_rows(cache, entries, selected)
    playbook, suppliers = basket_membership(
        parse_yaml(baskets.read_bytes()), activities
    )
    inputs = load_activity_inputs(
        cache,
        playbook,
        supplier_membership=suppliers,
        review_path=review_path,
        selections=selected,
    )
    return inputs, playbook, suppliers, selected


def read_review_csv(path: Path) -> tuple[ReviewRow, ...]:
    """Read the review file and refuse every malformed row."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != SPINE_COLUMNS:
            raise SpineError("review header is not the spine header")
        rows = tuple(_review_row(item) for item in reader)
    codes = [row.code for row in rows]
    if len(codes) != len(set(codes)):
        raise SpineError("duplicate review code")
    return rows


def write_review_csv(path: Path, rows: Sequence[SpineRow | ReviewRow]) -> None:
    """Write spine rows with the fixed header and column order."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(SPINE_COLUMNS)
        for row in rows:
            writer.writerow(
                (
                    encode_review_code(row.code),
                    row.code_length,
                    row.name_ar,
                    row.isic_class,
                    row.status,
                    row.reason,
                    row.reviewed_by_role,
                    row.reviewed_on,
                )
            )


def write_queue_csv(path: Path, rows: Sequence[SpineRow]) -> None:
    """Write the review queue with the same fixed header."""
    write_review_csv(path, rows)


def build_spine(
    activities: Sequence[ActivityRow],
    isic_classes: Sequence[IsicClass],
    reviews: Sequence[ReviewRow],
    playbook_codes: Sequence[str],
    *,
    supplier_membership: SupplierMembership,
    code_system_version: str = CODE_SYSTEM_VERSION,
    reviewed_binding: ReviewedBinding | None = None,
    audit_path: Path | None = None,
) -> Spine:
    """Derive every status, the coverage counts and the review queue."""
    if not isinstance(supplier_membership, SupplierMembership):
        raise SpineError("supplier membership is missing")
    if supplier_membership.complete is not True:
        raise SpineError("supplier membership is incomplete")
    by_code = _unique_activities(activities)
    classes = _unique_classes(isic_classes)
    reviewed = _unique_reviews(reviews)
    _require_reviewed_binding(reviewed_binding, classes, code_system_version, reviews)
    _require_model_audits(
        reviews,
        reviewed_binding,
        audit_path
        if audit_path is not None
        else _REVIEW / "activity_spine_audits.json",
    )
    playbook = tuple(sorted({_code(code) for code in playbook_codes}))
    suppliers = tuple(sorted({_code(code) for code in supplier_membership.codes}))
    for code in playbook:
        if code not in by_code:
            raise SpineError("playbook code absent from the feeds: " + code)
    for code in suppliers:
        if code not in by_code:
            raise SpineError("supplier code absent from the feeds: " + code)
    scope = _scope(by_code, playbook, suppliers)
    rows: list[SpineRow] = []
    for code in sorted(by_code):
        activity = by_code[code]
        held = reviewed.get(code)
        status, reason, isic_class = _derive(activity, classes, held, code in scope)
        role = ""
        on = ""
        if (
            status in _ACKNOWLEDGED
            and held is not None
            and _acknowledged(held, status, reason, activity)
        ):
            role = held.reviewed_by_role
            on = held.reviewed_on
        elif held is not None and status in {"mapped", "not_mappable_rejected"}:
            role = held.reviewed_by_role
            on = held.reviewed_on
        rows.append(
            SpineRow(
                code=code,
                code_length=len(code),
                name_ar=activity.name_ar,
                isic_class=isic_class,
                status=status,
                reason=reason,
                reviewed_by_role=role,
                reviewed_on=on,
            )
        )
    queue = tuple(
        row
        for row in sorted(
            rows,
            key=lambda item: (-by_code[item.code].active_count, item.code),
        )
        if row.code in scope and row.reviewed_by_role.strip() == ""
    )
    return Spine(rows=tuple(rows), coverage=_coverage(rows, by_code), queue=queue)


def finalise_spine(spine: Spine) -> Spine:
    """Refuse while any in-scope code still has no recorded review."""
    if spine.queue:
        missing = ",".join(row.code for row in spine.queue)
        raise SpineError("mandatory review missing: " + missing)
    return spine


def class_members(
    activities: Sequence[ActivityRow],
    isic_classes: Sequence[IsicClass],
    reviews: Sequence[ReviewRow],
    playbook_codes: Sequence[str],
    *,
    isic_class: str,
    supplier_membership: SupplierMembership,
    code_system_version: str = CODE_SYSTEM_VERSION,
    reviewed_binding: ReviewedBinding | None = None,
    audit_path: Path | None = None,
) -> tuple[str, ...]:
    """Return the codes whose reviewed decision is ``mapped`` to one class.

    The spine is built here by ``build_spine``, so a recorded reviewer role is
    an admitted signature only after the audit rules of decision 0075 have
    run; membership is selected from that result alone, never from a spine a
    caller held. A class with no admitted row is a refusal, never an empty
    answer.
    """
    if not isinstance(isic_class, str) or isic_class not in {
        row.code for row in isic_classes
    }:
        raise SpineError("class is not in the classification: " + str(isic_class))
    spine = build_spine(
        activities,
        isic_classes,
        reviews,
        playbook_codes,
        supplier_membership=supplier_membership,
        code_system_version=code_system_version,
        reviewed_binding=reviewed_binding,
        audit_path=audit_path,
    )
    members = tuple(
        sorted(
            row.code
            for row in spine.rows
            if row.status == "mapped" and row.isic_class == isic_class
        )
    )
    if not members:
        raise SpineError("class has no admitted mapped code: " + isic_class)
    return members


def class_bucket_counts(
    activities: Sequence[ActivityRow], isic_classes: Sequence[IsicClass]
) -> ClassBucketCounts:
    """Reconcile the national active counts into the four published buckets."""
    by_code = _unique_activities(activities)
    classes = _unique_classes(isic_classes)
    seven_valid = 0
    seven_invalid = 0
    six_legacy = 0
    other = 0
    five = 0
    eight = 0
    total = 0
    for code, activity in by_code.items():
        active = activity.active_count
        total += active
        if len(code) == 7:
            if code[:4] in classes:
                seven_valid += active
            else:
                seven_invalid += active
            continue
        if len(code) == 6:
            six_legacy += active
            continue
        other += active
        if len(code) == 5:
            five += active
        elif len(code) == 8:
            eight += active
    return ClassBucketCounts(
        seven_valid_prefix=seven_valid,
        seven_invalid_prefix=seven_invalid,
        six_legacy=six_legacy,
        other_length=other,
        five_digit=five,
        eight_digit=eight,
        total_active=total,
    )


def load_seed_reviews() -> tuple[ReviewRow, ...]:
    """Read the committed review file."""
    return read_review_csv(spine_path())


def _derive(
    activity: ActivityRow,
    classes: Mapping[str, IsicClass],
    review: ReviewRow | None,
    in_scope: bool,
) -> tuple[str, str, str]:
    if len(activity.code) != 7:
        return ("not_mappable_legacy", "legacy_code_length", "")
    prefix = activity.code[:4]
    if prefix not in classes:
        return ("not_mappable_invalid_prefix", "invalid_isic_prefix", "")
    if not in_scope:
        return ("unreviewed", "outside_review_scope", "")
    if review is None:
        return ("unreviewed", "awaiting_human_review", "")
    if review.status == "mapped":
        _require_sign_off(review, "mapped")
        _require_decision(review, "mapped", "reviewer_approved", activity)
        if review.isic_class != prefix:
            raise SpineError("signed class differs from the prefix: " + activity.code)
        return ("mapped", "reviewer_approved", prefix)
    if review.status == "not_mappable_rejected":
        _require_sign_off(review, "rejected")
        _require_decision(
            review, "not_mappable_rejected", "reviewer_rejected", activity
        )
        return ("not_mappable_rejected", "reviewer_rejected", "")
    if review.status == "unreviewed":
        return ("unreviewed", "awaiting_human_review", review.isic_class)
    raise SpineError("review status is not a decision: " + activity.code)


_ACKNOWLEDGED = frozenset({"not_mappable_legacy", "not_mappable_invalid_prefix"})


def _source_hash(source_id: str, sidecar: Mapping[str, object]) -> tuple[str, str]:
    digest = sidecar.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise SpineError("source receipt has no hash: " + source_id)
    return (source_id, digest)


def _class_title_sha256(classes: Sequence[IsicClass]) -> str:
    lines = [
        row.code + "\t" + row.label_en + "\t" + row.label_ar
        for row in sorted(classes, key=lambda item: item.code)
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def binding_required(reviews: Sequence[ReviewRow]) -> bool:
    """A mapped claim or any signed row must carry the binding it was signed with."""
    return any(
        row.status == "mapped" or row.reviewed_by_role.strip() != "" for row in reviews
    )


def load_recorded_binding(
    review_path: Path, reviews: Sequence[ReviewRow]
) -> ReviewedBinding | None:
    """Load the binding beside a review file, and require it when a row is signed."""
    path = binding_path(review_path)
    if not path.is_file():
        if binding_required(reviews):
            raise SpineError("review binding is missing")
        return None
    return read_review_binding(path)


def read_review_binding(path: Path) -> ReviewedBinding:
    """Read the version and class-title identities stored with a review."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpineError("review binding is not readable") from error
    if not isinstance(payload, dict):
        raise SpineError("review binding is not an object")
    if set(payload) not in (
        {"code_system_version", "inputs"},
        {"code_system_version", "inputs", "audit_sha256"},
    ):
        raise SpineError("review binding fields are not the contract")
    audit_hash = payload.get("audit_sha256", "")
    if "audit_sha256" in payload and (
        not isinstance(audit_hash, str) or _SHA256.fullmatch(audit_hash) is None
    ):
        raise SpineError("review binding audit hash is not a sha256")
    version = payload["code_system_version"]
    if not isinstance(version, str) or version.strip() == "":
        raise SpineError("review binding has no code-system version")
    inputs = payload["inputs"]
    if not isinstance(inputs, list):
        raise SpineError("review binding inputs are not a list")
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {"code", "name", "sha256"}:
            raise SpineError("review binding input fields are not the contract")
        name = item["name"]
        code = item["code"]
        digest = item["sha256"]
        if name != _CLASS_TITLE:
            raise SpineError("review binding input is not a class title")
        if not isinstance(code, str) or _DIGITS.match(code) is None or len(code) != 4:
            raise SpineError("review binding class code is not four digits")
        if not isinstance(digest, str) or _SHA256.match(digest) is None:
            raise SpineError("review binding hash is not a sha256")
        key = (name, code)
        if key in seen:
            raise SpineError("review binding repeats an input")
        seen.add(key)
        found.append((name, code, digest))
    return ReviewedBinding(
        code_system_version=version,
        input_sha256=tuple(sorted(found)),
        audit_sha256=audit_hash,
    )


_MODEL_PREFIX = "model review:"
_MODEL_LIKE = re.compile(r"\s*model[\W_]*review", re.IGNORECASE)
_MODEL_ROLE = re.compile(
    r"model review: ([A-Za-z][A-Za-z0-9_-]*) ([^,\r\n]+), ([^,\r\n]+)"
)
_MODEL_DECISIONS = frozenset({"mapped", "not_mappable_rejected"})
# Decision 0103: a model-signed derived acknowledgement row is audited exactly
# like a model-signed mapped or rejected row.
_MODEL_SIGNED_STATUSES = _MODEL_DECISIONS | _ACKNOWLEDGED
_AUDIT_FIELDS = frozenset(
    {
        "batch_id",
        "codes",
        "review_rows_sha256",
        "seed",
        "sampled_codes",
        "signer_role",
        "auditor_role",
        "errors",
        "audit_date",
    }
)


@dataclass(frozen=True)
class ActivityAudit:
    """One independently audited batch, never a mapping decision itself."""

    batch_id: str
    codes: tuple[str, ...]
    review_rows_sha256: str
    seed: int
    sampled_codes: tuple[str, ...]
    signer_role: str
    auditor_role: str
    audit_date: date


def audit_rows_sha256(reviews: Sequence[ReviewRow]) -> str:
    """Hash signed rows: code-ordered objects with every ReviewRow field.

    Canonical bytes are UTF-8 JSON, ensure_ascii=False, sort_keys=True,
    separators=(",", ":"), no trailing newline. Codes use their decoded form.
    """
    body = json.dumps(
        [asdict(row) for row in sorted(reviews, key=lambda row: row.code)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def audit_sample(codes: Sequence[str], seed: int) -> tuple[str, ...]:
    """Rank codes by SHA-256 of ASCII seed:code; take thirty, then code-sort.

    Ties break by code. A smaller batch is sampled in full. Input order has
    no effect, and no process RNG state or Python random algorithm is involved.
    """
    ranked = sorted(
        codes,
        key=lambda code: (
            hashlib.sha256(f"{seed}:{code}".encode("ascii")).digest(),
            code,
        ),
    )
    return tuple(sorted(ranked[: min(30, len(ranked))]))


def audit_maker(role: object) -> str:
    """Validate a decision-0075 role and return its case-folded maker token."""
    match = _MODEL_ROLE.fullmatch(role) if isinstance(role, str) else None
    if match is None or any(part != part.strip() for part in match.groups()):
        raise SpineError("model audit role is malformed")
    return match.group(1).casefold()


def _audit_codes(value: object, detail: str, *, nonempty: bool) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or any(
            not isinstance(code, str) or re.fullmatch(r"[0-9]{6,7}", code) is None
            for code in value
        )
        or len(set(value)) != len(value)
    ):
        raise SpineError(detail)
    return tuple(value)


def _audit_record(value: object) -> ActivityAudit:
    if not isinstance(value, dict) or set(value) != _AUDIT_FIELDS:
        raise SpineError("model audit record fields are invalid")
    batch_id = value["batch_id"]
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise SpineError("model audit batch id is invalid")
    codes = _audit_codes(value["codes"], "model audit codes are invalid", nonempty=True)
    sampled = _audit_codes(
        value["sampled_codes"], "model audit sampled codes are invalid", nonempty=False
    )
    seed = value["seed"]
    if type(seed) is not int or not 1000000000 <= seed <= 4294967295:
        raise SpineError("model audit seed is out of range")
    errors = value["errors"]
    if type(errors) is not int or errors != 0:
        raise SpineError("model audit errors are not zero")
    signer, auditor = value["signer_role"], value["auditor_role"]
    if audit_maker(signer) == audit_maker(auditor):
        raise SpineError("model audit makers are not different")
    on = value["audit_date"]
    try:
        if not isinstance(on, str) or _ISO_DATE.fullmatch(on) is None:
            raise ValueError
        audit_date = date.fromisoformat(on)
    except ValueError as error:
        raise SpineError("model audit date is invalid") from error
    digest = value["review_rows_sha256"]
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise SpineError("model audit review rows hash is invalid")
    return ActivityAudit(
        batch_id, codes, digest, seed, sampled, signer, auditor, audit_date
    )


def _require_model_audits(
    reviews: Sequence[ReviewRow],
    binding: ReviewedBinding | None,
    path: Path,
) -> None:
    for row in reviews:
        if (
            row.status in _MODEL_SIGNED_STATUSES
            and _MODEL_LIKE.match(row.reviewed_by_role)
            and _MODEL_ROLE.fullmatch(row.reviewed_by_role) is None
        ):
            raise SpineError("model review role is malformed")
    signed = {
        row.code: row
        for row in reviews
        if row.status in _MODEL_SIGNED_STATUSES
        and row.reviewed_by_role.startswith(_MODEL_PREFIX)
    }
    if not signed and (binding is None or not binding.audit_sha256):
        return
    if binding is None or not binding.audit_sha256:
        raise SpineError("model audit binding is missing")
    try:
        body = path.read_bytes()
        payload = json.loads(body)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpineError("model audit file is not readable") from error
    if hashlib.sha256(body).hexdigest() != binding.audit_sha256:
        raise SpineError("model audit file hash differs from binding")
    if not isinstance(payload, list):
        raise SpineError("model audit list is invalid")
    if not payload:
        if signed:
            raise SpineError("model audit has no records")
        return
    batches = tuple(_audit_record(value) for value in payload)
    if len({batch.batch_id for batch in batches}) != len(batches):
        raise SpineError("model audit batch id is duplicated")
    for code in signed:
        membership = sum(code in batch.codes for batch in batches)
        if membership == 0:
            raise SpineError("model review code has no audited batch")
        if membership > 1:
            raise SpineError("model review code has multiple audited batches")
    for batch in batches:
        if any(code not in signed for code in batch.codes):
            raise SpineError("model audit code is not a signed model decision")
        batch_rows = tuple(signed[code] for code in batch.codes)
        if any(row.reviewed_by_role != batch.signer_role for row in batch_rows):
            raise SpineError("model audit signer differs from review")
        if audit_rows_sha256(batch_rows) != batch.review_rows_sha256:
            raise SpineError("model audit review rows hash differs")
        if len(batch.sampled_codes) != min(30, len(batch.codes)):
            raise SpineError("model audit sample size differs")
        if batch.sampled_codes != audit_sample(batch.codes, batch.seed):
            raise SpineError("model audit sample differs from seed draw")
        for row in batch_rows:
            _require_sign_off(row, "model")
        if any(
            batch.audit_date < date.fromisoformat(row.reviewed_on) for row in batch_rows
        ):
            raise SpineError("model audit predates signing")


def _class_title_identity(code: str, label_en: str, label_ar: str) -> str:
    return hashlib.sha256(f"{code}\t{label_en}\t{label_ar}".encode()).hexdigest()


def _require_reviewed_binding(
    binding: ReviewedBinding | None,
    classes: Mapping[str, IsicClass],
    code_system_version: str,
    reviews: Sequence[ReviewRow],
) -> None:
    """Bind approved and rejected judgements to their classification titles."""
    if binding is None:
        if binding_required(reviews):
            raise SpineError("review binding is missing")
        return
    if binding.code_system_version != code_system_version:
        raise SpineError("code-system version differs from the reviewed version")
    recorded = {
        code: digest
        for name, code, digest in binding.input_sha256
        if name == _CLASS_TITLE
    }
    for review in reviews:
        if review.status not in {"mapped", "not_mappable_rejected"}:
            continue
        class_code = review.isic_class if review.status == "mapped" else review.code[:4]
        current = classes.get(class_code)
        if current is None and review.status == "mapped":
            continue
        present = (
            _class_title_identity(current.code, current.label_en, current.label_ar)
            if current is not None
            else ""
        )
        if recorded.get(class_code) != present:
            raise SpineError("classification title differs from the reviewed title")


def _acknowledged(
    review: ReviewRow | None,
    status: str,
    reason: str,
    activity: ActivityRow,
) -> bool:
    """A non-mappable code is reviewed only by its own signed acknowledgement."""
    if review is None or review.status != status:
        return False
    _require_sign_off(review, status)
    _require_decision(review, status, reason, activity)
    return True


def _require_decision(
    review: ReviewRow, status: str, reason: str, activity: ActivityRow
) -> None:
    if review.reason != reason:
        raise SpineError(f"{status} decision without the {reason} reason")
    if review.name_ar != activity.name_ar:
        raise SpineError("signed name differs from the cached name: " + activity.code)


def _require_sign_off(review: ReviewRow, decision: str) -> None:
    if review.reviewed_by_role.strip() == "":
        raise SpineError(f"{decision} decision without a reviewer role")
    if _ISO_DATE.match(review.reviewed_on) is None:
        raise SpineError(f"{decision} decision without an ISO review date")
    try:
        date.fromisoformat(review.reviewed_on)
    except ValueError as error:
        raise SpineError(f"{decision} decision with a malformed date") from error


def _scope(
    by_code: Mapping[str, ActivityRow],
    playbook: Sequence[str],
    suppliers: Sequence[str],
) -> frozenset[str]:
    ranked = sorted(
        (row for row in by_code.values() if row.active_count > 0),
        key=lambda row: (-row.active_count, row.code),
    )
    chosen = {row.code for row in ranked[:TOP_CODES]}
    chosen.update(
        code for code in by_code if len(code) == 7 and code.startswith(FOOD_PREFIX)
    )
    chosen.update(
        code for code in by_code if len(code) == 7 and code[:4] in PLAYBOOK_CLASSES
    )
    chosen.update(playbook)
    chosen.update(suppliers)
    return frozenset(chosen)


def _coverage(
    rows: Sequence[SpineRow], by_code: Mapping[str, ActivityRow]
) -> tuple[CoverageRow, ...]:
    counts = {status: [0, 0] for status in STATUSES}
    for row in rows:
        counts[row.status][0] += 1
        counts[row.status][1] += by_code[row.code].active_count
    return tuple(
        CoverageRow(
            status=status,
            code_count=counts[status][0],
            active_count=counts[status][1],
        )
        for status in STATUSES
    )


def _unique_activities(
    activities: Sequence[ActivityRow],
) -> dict[str, ActivityRow]:
    found: dict[str, ActivityRow] = {}
    for row in activities:
        _code(row.code)
        _text(row.name_ar, "name_ar")
        _count(row.active_count, "active_count")
        _count(row.cancelled_count, "cancelled_count")
        for source in row.source_ids:
            if source not in FEED_KEYS:
                raise SpineError("unknown activity source " + source)
        if len(set(row.source_ids)) != len(row.source_ids):
            raise SpineError("duplicate activity source " + row.code)
        if row.code in found:
            raise SpineError("duplicate activity code " + row.code)
        found[row.code] = row
    return found


def _unique_classes(classes: Sequence[IsicClass]) -> dict[str, IsicClass]:
    found: dict[str, IsicClass] = {}
    for row in classes:
        if len(_code(row.code)) != 4:
            raise SpineError("isic class is not four digits")
        if row.code in found:
            raise SpineError("duplicate isic class " + row.code)
        found[row.code] = row
    return found


def _unique_reviews(reviews: Sequence[ReviewRow]) -> dict[str, ReviewRow]:
    found: dict[str, ReviewRow] = {}
    for row in reviews:
        _check_review(row)
        if row.code in found:
            raise SpineError("duplicate review code " + row.code)
        found[row.code] = row
    return found


def _check_review(row: ReviewRow) -> None:
    _code(row.code)
    if _length(row.code_length) != len(row.code):
        raise SpineError("code_length does not match the code " + row.code)
    _text(row.name_ar, "name_ar")
    if row.status not in STATUSES:
        raise SpineError("unknown status " + row.status)
    if row.reason not in REASONS:
        raise SpineError("reason is not a closed key")
    if row.isic_class != "" and len(_code(row.isic_class)) != 4:
        raise SpineError("isic_class is not four digits")
    _optional_text(row.reviewed_by_role, "role")
    if row.reviewed_on != "":
        if _ISO_DATE.match(row.reviewed_on) is None:
            raise SpineError("reviewed_on is not an ISO date")
        try:
            date.fromisoformat(row.reviewed_on)
        except ValueError as error:
            raise SpineError("reviewed_on is not a real date") from error


def encode_review_code(code: str) -> str:
    """Write a review-file code in reversible groups of four when required."""
    if len(code) not in _DOTTED_LENGTHS:
        return code
    groups = [
        code[index : index + _REVIEW_GROUP]
        for index in range(0, len(code), _REVIEW_GROUP)
    ]
    return ".".join(groups)


def decode_review_code(token: object) -> str:
    """Decode one review-file code and refuse a bare eight- or eleven-digit run."""
    if not isinstance(token, str) or _REVIEW_TOKEN.match(token) is None:
        raise SpineError("code is not a digit string")
    if _BARE_RUN.search(token) is not None:
        raise SpineError("review file holds a bare digit run")
    raw = token.replace(".", "")
    if encode_review_code(raw) != token:
        raise SpineError("review code is not the reversible dotted form")
    return raw


def _review_row(row: Mapping[str, object]) -> ReviewRow:
    code = decode_review_code(row.get("code"))
    length = _length(row.get("code_length"))
    if length != len(code):
        raise SpineError("code_length does not match the code " + code)
    status = _text(row.get("status"), "status")
    if status not in STATUSES:
        raise SpineError("unknown status " + status)
    reason = _text(row.get("reason"), "reason")
    if reason not in REASONS:
        raise SpineError("reason is not a closed key")
    isic_class = _optional_text(row.get("isic_class"), "isic_class")
    if isic_class != "" and len(_code(isic_class)) != 4:
        raise SpineError("isic_class is not four digits")
    reviewed_on = _optional_text(row.get("reviewed_on"), "reviewed_on")
    if reviewed_on != "" and _ISO_DATE.match(reviewed_on) is None:
        raise SpineError("reviewed_on is not an ISO date")
    return ReviewRow(
        code=code,
        code_length=length,
        name_ar=_text(row.get("name_ar"), "name_ar"),
        isic_class=isic_class,
        status=status,
        reason=reason,
        reviewed_by_role=_optional_text(row.get("reviewed_by_role"), "role"),
        reviewed_on=reviewed_on,
    )


def _pattern_class(code: str) -> str:
    if code == "":
        return "empty"
    marks: list[str] = []
    for char in code:
        if "0" <= char <= "9":
            marks.append("9")
        elif char.isalpha():
            marks.append("a")
        else:
            marks.append("?")
    return "".join(marks)


def _left_out(feed: str, field: str, omitted: Mapping[str, int]) -> tuple[LeftOut, ...]:
    return tuple(
        LeftOut(feed=feed, field=field, pattern=pattern, count=count)
        for pattern, count in sorted(omitted.items())
    )


def _code(value: object) -> str:
    if not isinstance(value, str) or _DIGITS.match(value) is None:
        raise SpineError("code is not a digit string")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise SpineError(name + " is not text")
    return value


def _optional_text(value: object, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SpineError(name + " is not text")
    return value


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SpineError(name + " is not a non-negative integer")
    return value


def _length(value: object) -> int:
    if isinstance(value, str) and _DIGITS.match(value) is not None:
        return int(value)
    return _count(value, "code_length")
