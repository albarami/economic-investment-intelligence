"""Load the committed source registry. Unknown fields are refused."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

LICENCE_BASES = frozenset(
    {"dataset", "portal_terms", "provider_terms", "owner_decision", "none_stated"}
)
KINDS = frozenset(
    {"portal_dataset", "paged_layer", "https_file", "terms_page", "citation_only"}
)
BANNED_SOURCE_IDS = frozenset({"traffic_tomtom_flow", "traffic_tomtom_range"})
OWNER_DECISION_SOURCES = frozenset(
    {
        "fdi_projects",
        "investqa_pages",
        "census_zone_sector",
        "census_zone_occ",
        "census_zone_hh",
        "census_zone_lab",
        "census_district_pop",
        "bnd_zone_2020",
        "bnd_district_2020",
        "busy_gmaps",
    }
)
DECISION_RECORDS = frozenset({"0017", "0019"})
FIELDS = frozenset(
    {
        "key",
        "source_id",
        "slug",
        "kind",
        "layer",
        "title_en",
        "publisher",
        "licence_id",
        "licence_basis",
        "licence_url",
        "decision_record",
        "fetch_host",
        "url",
        "terms_url",
        "terms_forbid",
        "terms_watch",
        "basis_note",
        "landing_url",
        "nightly_live_fetch",
        "public_splits",
        "commit_allowed",
        "release_tables",
        "caveat_keys",
        "columns",
        "row_count_min",
        "row_count_max",
        "period_first",
        "period_last",
        "period_field",
        "reconciliation",
        "skip_reason",
        "extension",
    }
)
REQUIRED = frozenset(
    {
        "key",
        "source_id",
        "slug",
        "kind",
        "title_en",
        "publisher",
        "licence_id",
        "licence_basis",
        "decision_record",
        "fetch_host",
        "url",
        "terms_url",
        "landing_url",
        "nightly_live_fetch",
        "public_splits",
        "commit_allowed",
        "release_tables",
        "caveat_keys",
        "columns",
        "reconciliation",
        "skip_reason",
        "extension",
    }
)

_REGISTRY = Path(__file__).resolve().parents[4] / "publicdata" / "sources.yaml"


class RegistryError(Exception):
    """The registry document is not acceptable."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class Entry:
    """One registry row. A decision-0017 family row is keyed source_id/slug.

    layer is the ArcGIS layer id of a paged_layer row, required there with no
    default, and absent on every other kind.
    """

    key: str
    source_id: str
    slug: str
    kind: str
    title_en: str
    publisher: str
    licence_id: str
    licence_basis: str
    decision_record: str
    fetch_host: str
    url: str
    terms_url: str
    nightly_live_fetch: bool
    public_splits: tuple[str, ...]
    commit_allowed: bool
    release_tables: tuple[str, ...]
    caveat_keys: tuple[str, ...]
    columns: tuple[tuple[str, str], ...]
    row_count_min: int | None
    row_count_max: int | None
    period_first: str
    period_last: str
    period_field: str
    reconciliation: str
    skip_reason: str
    extension: str
    landing_url: str
    licence_url: str = ""
    layer: int | None = None
    terms_forbid: tuple[str, ...] = ()
    terms_watch: bool = False
    basis_note: str = ""


def registry_path() -> Path:
    """Return the committed sources.yaml path."""
    return _REGISTRY


def load_registry(path: Path | None = None) -> tuple[Entry, ...]:
    """Load sources.yaml with the safe loader and refuse unknown fields."""
    document = _read(path if path is not None else _REGISTRY)
    if not isinstance(document, dict):
        raise RegistryError("registry root is not a map")
    extra = set(document) - {"sources"}
    if extra:
        raise RegistryError(
            "unknown field " + ",".join(sorted(str(item) for item in extra))
        )
    rows = document.get("sources")
    if not isinstance(rows, list) or not rows:
        raise RegistryError("sources is empty")
    entries = tuple(_entry(row) for row in rows)
    keys = [entry.key for entry in entries]
    if len(keys) != len(set(keys)):
        raise RegistryError("duplicate key")
    return entries


def release_refused(entry: Entry, slot: str) -> bool:
    """True when a none_stated source is asked for a release slot."""
    if slot not in {"value", "share", "title", "geometry"}:
        raise RegistryError("unknown release slot")
    return entry.licence_basis == "none_stated"


def nightly_blocked(
    entries: tuple[Entry, ...] | list[Entry],
    selected: tuple[str, ...],
) -> tuple[str, ...]:
    """Return selected ids whose nightly_live_fetch flag is false."""
    flags = {entry.source_id: entry.nightly_live_fetch for entry in entries}
    return tuple(name for name in selected if flags.get(name) is False)


def _read(path: Path) -> object:
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _entry(row: object) -> Entry:
    if not isinstance(row, dict):
        raise RegistryError("entry is not a map")
    unknown = set(row) - FIELDS
    if unknown:
        raise RegistryError(
            "unknown field " + ",".join(sorted(str(item) for item in unknown))
        )
    missing = REQUIRED - set(row)
    if missing:
        raise RegistryError("missing field " + ",".join(sorted(missing)))
    source_id = _text(row, "source_id")
    if source_id in BANNED_SOURCE_IDS:
        raise RegistryError("traffic provider has no registry row")
    kind = _text(row, "kind")
    if kind not in KINDS:
        raise RegistryError("unknown kind")
    layer = _layer(row, kind)
    basis = _text(row, "licence_basis")
    if basis not in LICENCE_BASES:
        raise RegistryError("unknown licence_basis")
    record = _text(row, "decision_record")
    if basis == "owner_decision":
        if source_id not in OWNER_DECISION_SOURCES:
            raise RegistryError("owner_decision source is not admitted")
        if record not in DECISION_RECORDS:
            raise RegistryError("owner_decision needs a decision record")
    elif record != "":
        raise RegistryError("decision_record set without owner_decision")
    commit = _bool(row, "commit_allowed")
    if commit and basis == "none_stated":
        raise RegistryError("none_stated cannot be committed")
    terms_forbid = _terms_forbid(row)
    terms_watch = _terms_watch(row)
    basis_note = _basis_note(row)
    if terms_watch and terms_forbid:
        raise RegistryError("terms_watch and terms_forbid together")
    if terms_watch and basis_note.strip() == "":
        raise RegistryError("terms_watch set without basis_note")
    if terms_watch and _text(row, "terms_url").strip() == "":
        raise RegistryError("terms_watch set without terms_url")
    return Entry(
        key=_text(row, "key"),
        source_id=source_id,
        slug=_text(row, "slug"),
        kind=kind,
        title_en=_text(row, "title_en"),
        publisher=_text(row, "publisher"),
        licence_id=_text(row, "licence_id"),
        licence_basis=basis,
        decision_record=record,
        fetch_host=_text(row, "fetch_host"),
        url=_text(row, "url"),
        terms_url=_text(row, "terms_url"),
        nightly_live_fetch=_bool(row, "nightly_live_fetch"),
        public_splits=_strings(row, "public_splits"),
        commit_allowed=commit,
        release_tables=_strings(row, "release_tables"),
        caveat_keys=_strings(row, "caveat_keys"),
        columns=_columns(row.get("columns")),
        row_count_min=_optional_int(row, "row_count_min"),
        row_count_max=_optional_int(row, "row_count_max"),
        period_first=_optional_text(row, "period_first"),
        period_last=_optional_text(row, "period_last"),
        period_field=_optional_text(row, "period_field"),
        reconciliation=_text(row, "reconciliation"),
        skip_reason=_text(row, "skip_reason"),
        extension=_text(row, "extension"),
        landing_url=_text(row, "landing_url"),
        licence_url=_optional_text(row, "licence_url"),
        layer=layer,
        terms_forbid=terms_forbid,
        terms_watch=terms_watch,
        basis_note=basis_note,
    )


def _terms_watch(row: dict[object, object]) -> bool:
    """Return whether the row watches its terms page without switching off."""
    if "terms_watch" not in row:
        return False
    value = row["terms_watch"]
    if not isinstance(value, bool):
        raise RegistryError("terms_watch is not a boolean")
    return value


def _basis_note(row: dict[object, object]) -> str:
    """Return the basis-of-use note. Absent means none was recorded."""
    if "basis_note" not in row or row["basis_note"] is None:
        return ""
    value = row["basis_note"]
    if not isinstance(value, str) or value.strip() == "":
        raise RegistryError("basis_note is not text")
    return value


def _terms_forbid(row: dict[object, object]) -> tuple[str, ...]:
    """Return the recorded phrases. A bad value, or one without a terms URL, is refused."""
    if "terms_forbid" not in row:
        return ()
    value = row["terms_forbid"]
    if value is None or value == []:
        raise RegistryError("terms_forbid is empty")
    if not isinstance(value, list):
        raise RegistryError("terms_forbid is not a list of non-empty strings")
    phrases: list[str] = []
    for item in value:
        if not isinstance(item, str) or item.strip() == "":
            raise RegistryError("terms_forbid is not a list of non-empty strings")
        phrases.append(item)
    terms_url = row.get("terms_url")
    if not isinstance(terms_url, str) or terms_url.strip() == "":
        raise RegistryError("terms_forbid set without terms_url")
    return tuple(phrases)


def _layer(row: dict[object, object], kind: str) -> int | None:
    if kind != "paged_layer":
        if "layer" in row:
            raise RegistryError("layer on a row that is not paged_layer")
        return None
    if "layer" not in row or row["layer"] is None:
        raise RegistryError("paged_layer requires layer")
    value = row["layer"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryError("layer is not an integer")
    if value < 0:
        raise RegistryError("layer is negative")
    return value


def _text(row: dict[object, object], name: str) -> str:
    value = row[name]
    if not isinstance(value, str):
        raise RegistryError(f"{name} is not text")
    return value


def _optional_text(row: dict[object, object], name: str) -> str:
    if name not in row or row[name] is None:
        return ""
    value = row[name]
    if not isinstance(value, str):
        raise RegistryError(f"{name} is not text")
    return value


def _bool(row: dict[object, object], name: str) -> bool:
    value = row[name]
    if not isinstance(value, bool):
        raise RegistryError(f"{name} is not a boolean")
    return value


def _optional_int(row: dict[object, object], name: str) -> int | None:
    if name not in row or row[name] is None:
        return None
    value = row[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryError(f"{name} is not an integer")
    return value


def _strings(row: dict[object, object], name: str) -> tuple[str, ...]:
    value = row[name]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RegistryError(f"{name} is not a list of text")
    return tuple(item for item in value if isinstance(item, str))


def _columns(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise RegistryError("columns is not a list")
    found: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise RegistryError("column is not a map")
        extra = set(item) - {"name", "type"}
        if extra:
            raise RegistryError("unknown column field")
        name = item.get("name")
        kind = item.get("type")
        if not isinstance(name, str) or not isinstance(kind, str):
            raise RegistryError("column name or type is not text")
        if kind not in {"integer", "number", "string"}:
            raise RegistryError("unknown column type")
        found.append((name, kind))
    return tuple(found)
