"""Load the committed source registry. Unknown fields are refused."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from eii_custodian.publicdata.fetch.cadence import Cadence, parse_cadence

LICENCE_BASES = frozenset(
    {"dataset", "portal_terms", "provider_terms", "owner_decision", "pending"}
)
# Ruling L-1001: a pending terms reading is a record, never a gate. These are
# the exact pending values the reader records; no other word is accepted.
LICENCE_BASIS_PENDING = "pending"
TERMS_READ_ON_PENDING = "pending"
TERMS_WORDS_PENDING = "terms to be read"
DECISION_RECORD = "0026"
_DATE_TEXT = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
_SKIP_LICENCE = "licen"
_SKIP_TERMS = "terms"
KINDS = frozenset(
    {
        "portal_dataset",
        "paged_layer",
        "https_file",
        "terms_page",
        "citation_only",
        "paged_cards",
        "comtrade_api",
        "besttime",
        "public_page",
        "awards_intake",
    }
)
# S2-T08 part B, mismatch class 4: the only row whose export wraps its polygon
# in a GeoJSON Feature (live shape pack of 2026-11-18, Mismatches item 4).
FEATURE_POLYGON_SOURCES = frozenset({"bnd_muni_2025"})
COLLECTED_FAMILIES = frozenset(
    {
        "trade_ext",
        "survey_ext",
        "price_ext",
        "hotel_ext",
        "talent_ext",
        "jobseekers",
        "utilities_ext",
        "coverage_ext",
        "fdi_stats",
        "completions_ext",
    }
)


def undeclared_public_split(entry: Entry, fields: list[str]) -> bool:
    """PUB-90: family files keep published splits only with their declaration."""
    if entry.source_id not in COLLECTED_FAMILIES:
        return False
    tokens = {token for field in fields for token in field.casefold().split("_")}
    sex = {"sex", "gender", "male", "female", "males", "females"}
    nationality = {"nationality", "nationalities", "qataris"}
    return bool(
        (tokens & sex and "sex" not in entry.public_splits)
        or (tokens & nationality and "nationality" not in entry.public_splits)
    )


BANNED_SOURCE_IDS = frozenset({"traffic_tomtom_flow", "traffic_tomtom_range"})
FIELDS = frozenset(
    {
        "refetch",
        "key",
        "source_id",
        "slug",
        "kind",
        "layer",
        "chain_intermediate_sha256",
        "title_en",
        "publisher",
        "licence_id",
        "licence_basis",
        "licence_url",
        "decision_record",
        "fetch_host",
        "url",
        "terms_url",
        "terms_words",
        "terms_read_on",
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
        "period",
        "tile",
        "sex",
        "age_code",
        "release",
        "year",
        "cell_units",
        "doi",
        "doi_confirmed",
        "acknowledgement",
        "point",
        "variables",
        "cache_role",
        "comtrade_policy",
    }
)
FILE_FIELDS = {
    "ntl_blackmarble": ("period", "tile", "release", "doi", "acknowledgement"),
    "worldpop_qat_agesex": (
        "sex",
        "age_code",
        "release",
        "year",
        "cell_units",
        "doi",
        "doi_confirmed",
    ),
    "weather_openmeteo": ("point", "variables", "cache_role"),
}
FILE_FIELD_NAMES = frozenset(name for names in FILE_FIELDS.values() for name in names)
SEX_CODES = frozenset({"f", "m"})
CELL_UNITS = frozenset({"people_per_cell", "density", "unconfirmed"})
CACHE_ROLES = frozenset({"generator_input"})
WEATHER_VARIABLES = frozenset(
    {
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "rain",
        "weather_code",
        "cloud_cover",
        "wind_speed_10m",
        "shortwave_radiation",
    }
)
PERIOD_TEXT = re.compile(r"\A[0-9]{4}-[0-9]{2}\Z")
TILE_TEXT = re.compile(r"\Ah[0-9]{2}v[0-9]{2}\Z")
YEAR_TEXT = re.compile(r"\A[0-9]{4}\Z")
REQUIRED = frozenset(
    {
        "refetch",
        "key",
        "source_id",
        "slug",
        "kind",
        "title_en",
        "publisher",
        "licence_id",
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
# Ruling L-1001: licence_basis, terms_words and terms_read_on are no longer
# required; a row without one of them loads as its pending record, and only a
# present non-string value still refuses.

_REGISTRY = Path(__file__).resolve().parents[4] / "publicdata" / "sources.yaml"
_UNCONFIRMED_REFETCH = Cadence("none", "frequency_unconfirmed", "")
_CONTRACT_SPLIT_SOURCES = frozenset(
    {"sec_hr_comp_occ", "wage_bands_priv", "ref_min_wage"}
)


def _splits_carried_by_columns(
    columns: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    """Sex and nationality splits implied by recorded column names."""
    names = {name for name, _kind in columns}
    carried: list[str] = []
    if names & {"sex", "gender"}:
        carried.append("sex")
    if any("nationality" in name for name in names):
        carried.append("nationality")
    return tuple(carried)


class RegistryError(Exception):
    """The registry document is not acceptable."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class FileFields:
    """The optional per-file metadata of one row; absent for every other row."""

    period: str = ""
    tile: str = ""
    sex: str = ""
    age_code: str = ""
    release: str = ""
    year: str = ""
    cell_units: str = ""
    doi: str = ""
    doi_confirmed: bool = False
    acknowledgement: str = ""
    point: tuple[float, float] | None = None
    variables: tuple[str, ...] = ()
    cache_role: str = ""


@dataclass(frozen=True)
class Entry:
    """One registry row. A decision-0017 family row is keyed source_id/slug.

    layer is the ArcGIS layer id of an available paged_layer row. An absent
    row may omit it rather than invent an id; other kinds refuse it.
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
    # A missing or blank terms_words loads as the unread-terms pending marker
    # TERMS_WORDS_PENDING ("terms to be read"); a missing or blank
    # terms_read_on loads as the exact pending value TERMS_READ_ON_PENDING
    # ("pending"). Ruling L-1001: both are records that hold no source back;
    # only a malformed non-empty date or a row without a required field is
    # refused.
    terms_words: str
    terms_read_on: str
    licence_url: str = ""
    layer: int | None = None
    terms_watch: bool = False
    basis_note: str = ""
    period: str = ""
    tile: str = ""
    sex: str = ""
    age_code: str = ""
    release: str = ""
    year: str = ""
    cell_units: str = ""
    doi: str = ""
    doi_confirmed: bool = False
    acknowledgement: str = ""
    point: tuple[float, float] | None = None
    variables: tuple[str, ...] = ()
    cache_role: str = ""
    chain_intermediate_sha256: str = ""
    comtrade_policy: object | None = None
    refetch: Cadence = _UNCONFIRMED_REFETCH


def registry_path() -> Path:
    """Return the committed sources.yaml path."""
    return _REGISTRY


def _refuse_undeclared_period_form(entries: tuple[Entry, ...]) -> None:
    """Refuse a family row that names a period field and does not name its form."""
    for entry in entries:
        if entry.source_id not in COLLECTED_FAMILIES:
            continue
        if entry.period_field and "form=" not in entry.period_field:
            raise RegistryError(f"{entry.source_id}: period_form")


def require_addition_completion(entries: tuple[Entry, ...]) -> None:
    """Refuse a decision-0017 family row that still lacks its declaration."""
    from eii_custodian.publicdata.additions.common import (
        ADDITION_FAMILIES,
        FIELD_UNCONFIRMED,
        AdditionError,
        parse_period_rule,
    )

    for entry in entries:
        if entry.source_id not in ADDITION_FAMILIES:
            continue
        if not entry.columns:
            raise RegistryError(f"{entry.key}: columns empty")
        if entry.row_count_min is None or entry.row_count_min != entry.row_count_max:
            raise RegistryError(f"{entry.key}: row count range not closed")
        if entry.period_first == "" or entry.period_last == "":
            raise RegistryError(f"{entry.key}: period bounds empty")
        try:
            rule = parse_period_rule(entry.period_field)
        except AdditionError as error:
            raise RegistryError(f"{entry.key}: {error.name}") from error
        declared = {name for name, _kind in entry.columns}
        if _period_name_undeclared(
            rule.field, declared, FIELD_UNCONFIRMED
        ) or _period_name_undeclared(rule.month_field, declared, FIELD_UNCONFIRMED):
            raise RegistryError(f"{entry.key}: period_field_undeclared")
        if entry.source_id == "active_nat_occ_act" and entry.public_splits != (
            "nationality",
            "sex",
        ):
            raise RegistryError(f"{entry.key}: split declaration")
        if (
            entry.source_id == "visitors_markets"
            and "nationality" not in entry.public_splits
        ):
            raise RegistryError(f"{entry.key}: split declaration")


def _period_name_undeclared(name: str, declared: set[str], marker: str) -> bool:
    """True when a period rule names a column the row does not declare.

    The registry marker is not a column name. An empty month is not a name.
    """
    if name == "" or name == marker:
        return False
    return name not in declared


def load_registry(path: Path | None = None) -> tuple[Entry, ...]:
    """Load sources.yaml with the safe loader and refuse unknown fields."""
    document = read_yaml(path if path is not None else _REGISTRY)
    if not isinstance(document, dict):
        raise RegistryError("registry root is not a map")
    extra = set(document) - {"sources", "forecast_series"}
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
    _refuse_undeclared_period_form(entries)
    if "forecast_series" in document:
        from .forecast_series import load_forecast_series

        load_forecast_series(document["forecast_series"], entries)
    require_addition_completion(entries)
    return entries


def nightly_blocked(
    entries: tuple[Entry, ...] | list[Entry],
    selected: tuple[str, ...],
) -> tuple[str, ...]:
    """Return selected ids whose nightly_live_fetch flag is false."""
    flags = {entry.source_id: entry.nightly_live_fetch for entry in entries}
    return tuple(name for name in selected if flags.get(name) is False)


def read_yaml(path: Path) -> object:
    """Load one YAML document with libyaml's C safe loader; no fallback.

    A malformed file raises RegistryError, the package's own error.
    """
    try:
        loaded: object = yaml.load(
            path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader
        )
    except yaml.YAMLError as exc:
        raise RegistryError("malformed yaml") from exc
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
    comtrade_policy = _comtrade_policy(row, kind)
    basis = _optional_text(row, "licence_basis")
    if basis == "":
        # Ruling L-1001: a missing or blank basis of use is recorded as
        # pending, never refused. A pending basis is never committable and
        # needs no decision record.
        basis = LICENCE_BASIS_PENDING
    if basis not in LICENCE_BASES:
        raise RegistryError("unknown licence_basis")
    record = _text(row, "decision_record")
    if basis == "owner_decision":
        if record != DECISION_RECORD:
            raise RegistryError("owner_decision needs a decision record")
    elif record != "":
        raise RegistryError("decision_record set without owner_decision")
    commit = _bool(row, "commit_allowed")
    if commit and basis != "dataset":
        raise RegistryError("cannot be committed")
    terms_words = _terms_words(row)
    terms_read_on = _terms_read_on(row)
    terms_watch = _terms_watch(row)
    basis_note = _basis_note(row)
    if terms_watch and basis_note.strip() == "":
        raise RegistryError("terms_watch set without basis_note")
    if terms_watch and _text(row, "terms_url").strip() == "":
        raise RegistryError("terms_watch set without terms_url")
    skip_reason = _text(row, "skip_reason")
    folded_skip = skip_reason.casefold()
    if _SKIP_LICENCE in folded_skip or _SKIP_TERMS in folded_skip:
        raise RegistryError("skip_reason names a licence or terms")
    file_fields = _file_fields(row, source_id)
    try:
        refetch = parse_cadence(row["refetch"], source_id=source_id)
    except ValueError as exc:
        raise RegistryError(str(exc)) from None
    columns = _columns(row.get("columns"))
    if source_id not in FEATURE_POLYGON_SOURCES and any(
        kind == "geojson_feature_polygon" for _name, kind in columns
    ):
        raise RegistryError(
            "geojson_feature_polygon is declared for bnd_muni_2025 only"
        )
    public_splits = _strings(row, "public_splits")
    if any(name in {"sex", "gender"} for name, _kind in columns):
        if "sex" not in public_splits:
            raise RegistryError("sex field requires public_splits sex")
    if any("nationality" in name for name, _kind in columns):
        if "nationality" not in public_splits:
            raise RegistryError("nationality field requires public_splits nationality")
    if (
        source_id in _CONTRACT_SPLIT_SOURCES
        and public_splits != _splits_carried_by_columns(columns)
    ):
        raise RegistryError("public_splits contract mismatch")
    return Entry(
        refetch=refetch,
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
        public_splits=public_splits,
        commit_allowed=commit,
        release_tables=_strings(row, "release_tables"),
        caveat_keys=_strings(row, "caveat_keys"),
        columns=columns,
        row_count_min=_optional_int(row, "row_count_min"),
        row_count_max=_optional_int(row, "row_count_max"),
        period_first=_optional_text(row, "period_first"),
        period_last=_optional_text(row, "period_last"),
        period_field=_optional_text(row, "period_field"),
        reconciliation=_text(row, "reconciliation"),
        skip_reason=skip_reason,
        extension=_text(row, "extension"),
        landing_url=_text(row, "landing_url"),
        terms_words=terms_words,
        terms_read_on=terms_read_on,
        licence_url=_optional_text(row, "licence_url"),
        layer=layer,
        terms_watch=terms_watch,
        basis_note=basis_note,
        period=file_fields.period,
        tile=file_fields.tile,
        sex=file_fields.sex,
        age_code=file_fields.age_code,
        release=file_fields.release,
        year=file_fields.year,
        cell_units=file_fields.cell_units,
        doi=file_fields.doi,
        doi_confirmed=file_fields.doi_confirmed,
        acknowledgement=file_fields.acknowledgement,
        point=file_fields.point,
        variables=file_fields.variables,
        cache_role=file_fields.cache_role,
        chain_intermediate_sha256=_chain_pin(row),
        comtrade_policy=comtrade_policy,
    )


def _file_fields(row: dict[object, object], source_id: str) -> FileFields:
    """Return the per-file metadata of one row, or nothing when the row holds none.

    The fields are optional together: a row either holds the whole group its
    source uses or none of it, and a field on any other source is refused.
    """
    present = {name for name in FILE_FIELD_NAMES if name in row}
    if source_id in {
        "cepii_baci",
        "cepii_gravity",
        "atlas_complexity",
        "wb_wdi",
        "unctad_fdi",
        "imf_weo",
        "ilostat_qat",
    }:
        # Trade and benchmark manifests serialize the complete joined Entry.
        # Their unused file slots must retain exactly the typed defaults, never metadata
        # belonging to a grid source. Registry rows still need no such slots.
        defaults = FileFields()
        if present == FILE_FIELD_NAMES and all(
            (
                isinstance(row[name], (list, tuple)) and not row[name]
                if name == "variables"
                else type(row[name]) is type(getattr(defaults, name))
                and row[name] == getattr(defaults, name)
            )
            for name in present
        ):
            return defaults
    allowed = set(FILE_FIELDS.get(source_id, ()))
    outside = present - allowed
    if outside:
        raise RegistryError(
            "file field on a row that does not use it: "
            + ",".join(sorted(str(item) for item in outside))
        )
    if not present:
        return FileFields()
    if present != allowed:
        raise RegistryError(
            "incomplete file metadata: " + ",".join(sorted(allowed - present))
        )
    return FileFields(
        period=_pattern(row, "period", PERIOD_TEXT) if "period" in present else "",
        tile=_pattern(row, "tile", TILE_TEXT) if "tile" in present else "",
        sex=_closed(row, "sex", SEX_CODES) if "sex" in present else "",
        age_code=_digits(row, "age_code") if "age_code" in present else "",
        release=_nonempty(row, "release") if "release" in present else "",
        year=_pattern(row, "year", YEAR_TEXT) if "year" in present else "",
        cell_units=(
            _closed(row, "cell_units", CELL_UNITS) if "cell_units" in present else ""
        ),
        doi=_nonempty(row, "doi") if "doi" in present else "",
        doi_confirmed=(
            _bool(row, "doi_confirmed") if "doi_confirmed" in present else False
        ),
        acknowledgement=(
            _nonempty(row, "acknowledgement") if "acknowledgement" in present else ""
        ),
        point=_point(row) if "point" in present else None,
        variables=_variables(row) if "variables" in present else (),
        cache_role=(
            _closed(row, "cache_role", CACHE_ROLES) if "cache_role" in present else ""
        ),
    )


def _pattern(row: dict[object, object], name: str, pattern: re.Pattern[str]) -> str:
    value = _text(row, name)
    if not pattern.match(value):
        raise RegistryError(f"{name} is not in the recorded form")
    return value


def _closed(row: dict[object, object], name: str, allowed: frozenset[str]) -> str:
    value = _text(row, name)
    if value not in allowed:
        raise RegistryError(f"{name} is not a recorded value")
    return value


def _digits(row: dict[object, object], name: str) -> str:
    value = _text(row, name)
    if not value.isdecimal() or not value.isascii():
        raise RegistryError(f"{name} is not a decimal code")
    return value


def _nonempty(row: dict[object, object], name: str) -> str:
    value = _text(row, name)
    if value.strip() == "":
        raise RegistryError(f"{name} is empty")
    return value


def _point(row: dict[object, object]) -> tuple[float, float]:
    value = row["point"]
    if not isinstance(value, list) or len(value) != 2:
        raise RegistryError("point is not a pair of numbers")
    pair: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise RegistryError("point is not a pair of numbers")
        pair.append(float(item))
    return (pair[0], pair[1])


def _variables(row: dict[object, object]) -> tuple[str, ...]:
    value = row["variables"]
    if not isinstance(value, list) or not value:
        raise RegistryError("variables is not a non-empty list of text")
    found: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in WEATHER_VARIABLES:
            raise RegistryError("variables is not a recorded value")
        found.append(item)
    if len(found) != len(set(found)):
        raise RegistryError("variables repeats a name")
    return tuple(found)


def _chain_pin(row: dict[object, object]) -> str:
    """An empty pin awaits the lead's reading; it never disables verification."""
    pin = _optional_text(row, "chain_intermediate_sha256")
    if pin and re.fullmatch(r"[a-f0-9]{64}", pin) is None:
        raise RegistryError("chain_intermediate_sha256 is not a SHA-256")
    return pin


def _terms_watch(row: dict[object, object]) -> bool:
    """Return the compatibility flag. It changes nothing about fetch or terms."""
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


def _terms_words(row: dict[object, object]) -> str:
    """Return the publisher's words, or the unread-terms pending marker.

    A missing or blank value is the pending reading of ruling L-1001 and
    loads as TERMS_WORDS_PENDING, the marker the registry already uses for
    unread terms; only a present non-string value still refuses.
    """
    value = _optional_text(row, "terms_words")
    if value.strip() == "":
        return TERMS_WORDS_PENDING
    return value


def _terms_read_on(row: dict[object, object]) -> str:
    """Return the reading date, or the exact pending value "pending".

    A missing or blank date is the pending reading of ruling L-1001 and
    loads as TERMS_READ_ON_PENDING, and so does the marker itself when a
    stored entry is read back; a non-empty date that is not a real
    YYYY-MM-DD text date is a typing error and keeps its refusal.
    """
    value = _optional_text(row, "terms_read_on")
    if value.strip() == "" or value == TERMS_READ_ON_PENDING:
        return TERMS_READ_ON_PENDING
    return _calendar_date(row, "terms_read_on")


def _calendar_date(row: dict[object, object], name: str) -> str:
    """Return a YYYY-MM-DD date. A date object is refused as not text."""
    value = _text(row, name)
    if _DATE_TEXT.fullmatch(value) is None:
        raise RegistryError(f"{name} is not a date")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise RegistryError(f"{name} is not a date") from None
    return value


TECHNICAL_SKIP_REASONS = frozenset(
    {
        "publisher_or_schema_unconfirmed",
        "cache_fields_unconfirmed",
        "adapter_unavailable",
        "schema_unconfirmed",
        "direct_url_unconfirmed",
        "page_list_unconfirmed",
        "overture_bucket_not_opened",
        "certificate_chain_incomplete",
    }
)


def _technical_reason(reason: str) -> bool:
    """A layer may be omitted only for this closed vocabulary, one token or several."""
    tokens = [part.strip() for part in reason.split(";") if part.strip()]
    return bool(tokens) and all(token in TECHNICAL_SKIP_REASONS for token in tokens)


def _comtrade_policy(row: dict[object, object], kind: str) -> object | None:
    """Return the closed policy. Any other kind refuses the field."""
    if kind != "comtrade_api":
        if "comtrade_policy" in row:
            raise RegistryError("comtrade_policy on a row that is not comtrade_api")
        return None
    if "comtrade_policy" not in row:
        raise RegistryError("comtrade_api requires comtrade_policy")
    from eii_custodian.publicdata.comtrade.policy import PolicyError, parse_policy

    try:
        return parse_policy(row["comtrade_policy"])
    except PolicyError as exc:
        raise RegistryError(exc.detail) from None


def _layer(row: dict[object, object], kind: str) -> int | None:
    if kind != "paged_layer":
        if "layer" in row:
            raise RegistryError("layer on a row that is not paged_layer")
        return None
    if "layer" not in row or row["layer"] is None:
        if _technical_reason(_text(row, "skip_reason")):
            return None
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
        if kind not in {
            "integer",
            "number",
            "string",
            "object",
            "point_2d",
            "geojson_geometry",
            "geojson_feature_polygon",
        }:
            raise RegistryError("unknown column type")
        found.append((name, kind))
    return tuple(found)
