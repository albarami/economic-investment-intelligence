"""Places stage of the public build. It writes files only after every check."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from shapely import point_on_surface
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.geometry import Boundary
from eii_custodian.publicdata.frame.geometry import index as index_boundaries
from eii_custodian.publicdata.frame.live import resolve_reviewed_specs
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.area_files import FileAreaProvider
from eii_custodian.publicdata.places.area_requests import area_requests
from eii_custodian.publicdata.places.build import build_places
from eii_custodian.publicdata.places.display import CAVEAT_KEY, CensusFigure, PubPlace
from eii_custodian.publicdata.places.flagship import (
    CheckRecord,
    decision_from_mapping,
    validate_decision,
)
from eii_custodian.publicdata.places.read import (
    FileReceipt,
    load_boundary_buildings,
)
from eii_custodian.publicdata.places.read import (
    iter_building_file as read_building_file,
)
from eii_custodian.publicdata.places.read import (
    iter_place_file as read_place_file,
)
from eii_custodian.publicdata.places.review import (
    DISTRICT_SOURCE,
    STATUSES,
    Verification,
    load_attribution,
    load_categories,
    load_flagship_candidates,
    load_showcase_areas,
    load_showcase_gazetteer,
)
from eii_custodian.publicdata.places_fsq.parse import ParsedRow
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX

PLACE_COLUMNS = (
    "place_id",
    "name",
    "name_ar",
    "category",
    "lon",
    "lat",
    "cell",
    "source_release",
    "source_provider",
    "licence",
    "confidence",
    "merged_ids",
)
VERIFICATION_COLUMNS = (
    "place_id",
    "check_date",
    "reviewer_role",
    "verification_link",
    "status",
    "source_id",
)
_OUTPUTS = (
    "pub_place.jsonl",
    "pub_place_verification.jsonl",
    "place_points.json",
    "build_report.json",
    "flagship_check.json",
)
_CAVEAT_FILES = ("place_points.json", "build_report.json", "flagship_check.json")
_PLACES_SOURCE = "places_ovt"
_BUILDINGS_SOURCE = "bldg_ovt"


def _district_points(
    specs: Sequence[Mapping[str, object]],
    districts: Sequence[Boundary],
    boundary: BaseGeometry,
) -> list[dict[str, object]]:
    """Point rows for reviewed district-member landmarks.

    Each member must name one archive district inside the frame boundary; the
    landmark's point is the point on surface of the member polygons' union.
    """
    wanted = [item for item in specs if item.get("source_id") == DISTRICT_SOURCE]
    if not wanted:
        return []
    geoms = _district_geoms(districts)
    rows: list[dict[str, object]] = []
    for item in wanted:
        members = item.get("members")
        if not isinstance(members, list):
            raise PlacesError("landmark_members_empty")
        union = unary_union(
            [_district_member(geoms, member, boundary) for member in sorted(members)]
        )
        point = point_on_surface(union)
        lon, lat = f"{point.x:.6f}", f"{point.y:.6f}"
        stored = Point(float(lon), float(lat))
        if not union.covers(stored) or not boundary.covers(stored):
            raise PlacesError("landmark_point_outside")
        rows.append(
            {
                "caveat_key": CAVEAT_KEY,
                "lat": lat,
                "lon": lon,
                "record_key": item["record_key"],
                "source_id": DISTRICT_SOURCE,
            }
        )
    return rows


def _district_geoms(districts: Sequence[Boundary]) -> dict[str, BaseGeometry]:
    """Index archive districts by key; a duplicate key is the closed refusal."""
    try:
        return index_boundaries(list(districts))
    except FrameError as exc:
        if str(exc) != "duplicate boundary key":
            raise
        raise PlacesError("landmark_member_duplicate") from exc


def _district_member(
    geoms: Mapping[str, BaseGeometry], member: object, boundary: BaseGeometry
) -> BaseGeometry:
    """One archive district polygon, inside the frame boundary, or a refusal."""
    geometry = geoms.get(member) if isinstance(member, str) else None
    if geometry is None:
        raise PlacesError("landmark_member_unknown")
    if not boundary.covers(geometry):
        raise PlacesError("landmark_member_outside")
    return geometry


@dataclass(frozen=True)
class StageConfig:
    """Inputs the stage does not invent. The Arabic tag is required."""

    cache: Path
    review: Path
    arabic_tag: str
    boundary: BaseGeometry
    grid: Sequence[Mapping[str, object]]
    zones: Mapping[str, BaseGeometry]
    places_path: Path
    places_receipt: FileReceipt
    census: CensusFigure | None = None
    build_date: date | None = None
    fsq_rows: tuple[ParsedRow, ...] | None = None
    fsq_release: str = ""
    fsq_licence: str = ""
    buildings_paths: tuple[Path, ...] = ()
    buildings_receipts: tuple[FileReceipt, ...] = ()
    districts: Sequence[Boundary] = ()


@dataclass(frozen=True)
class StageOutcome:
    """Paths written under places_s2_t06, and whether the build is complete."""

    directory: Path
    complete: bool
    report: tuple[str, ...]


def run_places_stage(config: StageConfig) -> StageOutcome:
    """Build places after boundary, grid and zones exist, and write the files."""
    if not isinstance(config.arabic_tag, str) or config.arabic_tag.strip() == "":
        raise PlacesError("arabic_tag_missing")
    directory = config.cache / "places_s2_t06"
    provider = _provider(config)
    attribution = load_attribution(config.review / "places_ovt_attribution.csv", None)
    categories = load_categories(config.review / "places_ovt_categories.csv", None)
    gazetteer = load_showcase_gazetteer(
        config.review / "showcase_gazetteer.yaml", None
    )[1]
    areas = load_showcase_areas(
        config.review / "showcase_areas.yaml", None, gazetteer=gazetteer
    )
    verified_path = config.review / "verified_places.csv"
    known_later: set[str] = set()
    result = build_places(
        config.places_path,
        arabic_tag=config.arabic_tag,
        boundary=config.boundary,
        grid=config.grid,
        attribution=attribution[1],
        categories=categories[1],
        verified_path=verified_path if verified_path.is_file() else None,
        verified_cache=None,
        buildings_paths=config.buildings_paths,
        buildings_receipts=config.buildings_receipts,
        places_receipt=config.places_receipt,
        zones=config.zones,
        area_provider=provider,
        showcase_areas=areas[1],
        candidates=load_flagship_candidates(
            config.review / "flagship_candidates.yaml", None
        )[1],
        fsq_rows=config.fsq_rows,
        fsq_release=config.fsq_release,
        fsq_licence=config.fsq_licence,
        build_date=config.build_date,
        census=config.census,
    )
    known_later.update(place.place_id for place in result.places)
    verifications = result.verifications
    points = _points(result.places, _buildings(config))
    specs = (
        *gazetteer,
        *load_flagship_candidates(config.review / "flagship_candidates.yaml", None)[1],
    )
    district_points = _district_points(specs, config.districts, config.boundary)
    resolved, notes = resolve_review(
        specs,
        _point_index([*points, *district_points]),
        config.grid,
    )
    points.extend(district_points)
    report = (*result.report, *notes)
    check_text = _check_text(result.flagship, _manifest_sha(config.cache))
    decision = _decision_against_file(config.review, check_text)
    files = {
        "pub_place.jsonl": render_place_rows(result.places),
        "pub_place_verification.jsonl": render_verification_rows(
            verifications, frozenset(known_later)
        ),
        "place_points.json": _json(points),
        "build_report.json": _json(
            {
                "caveat_key": CAVEAT_KEY,
                "complete": result.complete,
                "decision": decision,
                "report": list(report),
                "resolved": [row["place_key"] for row in resolved],
                "shown": sorted(result.shown_ids),
                "required_verification": {
                    "by_area": dict(result.required_verification_by_area),
                    "total": result.required_verification_total,
                },
            }
        ),
        "flagship_check.json": check_text,
    }
    commit_files(directory, files)
    return StageOutcome(directory, result.complete, report)


def render_place_rows(places: Sequence[PubPlace]) -> str:
    """One canonical line per row, in the contract column order."""
    rows = [_place_row(place) for place in places]
    if not rows:
        return ""
    return "".join(_line(row) for row in rows)


def render_verification_rows(
    rows: Sequence[Verification], known: frozenset[str]
) -> str:
    """Store a verification only when its place was written and its status is one of four."""
    rendered = [_verification_row(row, known) for row in rows]
    if not rendered:
        return ""
    return "".join(_line(row) for row in rendered)


def commit_files(directory: Path, files: Mapping[str, str]) -> None:
    """Write every file, or none, after the caveat key is present on each."""
    for name in _OUTPUTS:
        if name not in files:
            raise PlacesError("caveat_missing")
        if name in _CAVEAT_FILES and CAVEAT_KEY not in files[name]:
            raise PlacesError("caveat_missing")
    directory.mkdir(parents=True, exist_ok=True)
    for name in _OUTPUTS:
        (directory / name).write_text(files[name], encoding="utf-8")


def validate_recorded_decision(
    decision: Mapping[str, object], record_path: Path
) -> None:
    """Validate a decision against the check file, including its manifest digest."""
    loaded = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PlacesError("decision_fields")
    core = {
        "candidate_key": decision.get("candidate_key"),
        "digest": decision.get("digest"),
        "provisional": decision.get("provisional"),
    }
    parsed = decision_from_mapping(core)
    body = loaded.get("body")
    passed = loaded.get("passed_keys")
    record = CheckRecord(
        body if isinstance(body, dict) else {},
        str(loaded.get("digest")),
        loaded.get("passing_evidence") is True,
        tuple(passed) if isinstance(passed, list) else (),
    )
    validate_decision(parsed, record)
    if decision.get("manifest_sha256") != loaded.get("manifest_sha256"):
        raise PlacesError("stale_manifest")


def resolve_review(
    specs: Sequence[Mapping[str, object]],
    points: Mapping[tuple[str, str], Mapping[str, object]],
    grid: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    """Resolve filled keys. A key that names nothing is record_missing."""
    report: list[str] = []
    try:
        resolved = resolve_reviewed_specs(
            [dict(item) for item in specs],
            {key: dict(value) for key, value in points.items()},
            [dict(row) for row in grid],
            report,
        )
    except FrameError as exc:
        if "missing source point" not in str(exc):
            raise
        raise PlacesError("record_missing") from exc
    return resolved, tuple(report)


def _provider(config: StageConfig) -> FileAreaProvider | None:
    if not (config.cache / "places_s2_t06" / "areas" / "manifest.json").is_file():
        return None
    requests = area_requests(config.review, _source_points(config))
    return FileAreaProvider(
        config.cache,
        (FRAME_BOX.west, FRAME_BOX.south, FRAME_BOX.east, FRAME_BOX.north),
        requests,
    )


def _buildings(config: StageConfig) -> tuple[tuple[str, str, str, str], ...]:
    if not config.buildings_paths:
        return ()
    buildings, _receipts, _outside = load_boundary_buildings(
        config.buildings_paths, config.buildings_receipts, config.boundary
    )
    return tuple(
        ("bldg_ovt", building.building_id, f"{building.lon:.6f}", f"{building.lat:.6f}")
        for building in buildings
    )


def _points(
    places: Sequence[PubPlace],
    buildings: Sequence[tuple[str, str, str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for place in places:
        rows.append(
            {
                "caveat_key": CAVEAT_KEY,
                "lat": f"{place.lat:.6f}",
                "lon": f"{place.lon:.6f}",
                "record_key": place.place_id,
                "source_id": "places_ovt",
            }
        )
    for source, key, lon, lat in buildings:
        rows.append(
            {
                "caveat_key": CAVEAT_KEY,
                "lat": lat,
                "lon": lon,
                "record_key": key,
                "source_id": source,
            }
        )
    return rows


def _point_index(
    points: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    found: dict[tuple[str, str], dict[str, object]] = {}
    for item in points:
        source = item.get("source_id")
        record = item.get("record_key")
        if isinstance(source, str) and isinstance(record, str):
            found[(source, record)] = {"lon": item["lon"], "lat": item["lat"]}
    return found


def _place_row(place: PubPlace) -> dict[str, object]:
    if place.source_provider == "" or place.licence == "" or place.confidence is None:
        raise PlacesError("pub_place_field")
    return {
        "place_id": place.place_id,
        "name": place.name,
        "name_ar": place.name_ar,
        "category": place.category,
        "lon": f"{place.lon:.6f}",
        "lat": f"{place.lat:.6f}",
        "cell": place.cell,
        "source_release": place.source_release,
        "source_provider": place.source_provider,
        "licence": place.licence,
        "confidence": f"{place.confidence:.4f}",
        "merged_ids": place.merged_ids,
    }


def _verification_row(row: Verification, known: frozenset[str]) -> dict[str, object]:
    if row.place_id not in known:
        raise PlacesError("orphan_place_id")
    if row.status not in STATUSES:
        raise PlacesError("unknown_status")
    return {
        "place_id": row.place_id,
        "check_date": row.check_date,
        "reviewer_role": row.reviewer_role,
        "verification_link": row.verification_link,
        "status": row.status,
        "source_id": row.source_id,
    }


def _check_text(record: CheckRecord | None, manifest_sha: str) -> str:
    if record is None:
        body: dict[str, object] = {
            "candidates": [],
            "method": "places.flagship.v1",
            "passing_evidence": False,
            "provider_given": False,
            "provisional": True,
        }
        digest = ""
        evidence = False
        passed: tuple[str, ...] = ()
    else:
        body = record.body
        digest = record.digest
        evidence = record.passing_evidence
        passed = record.passed_keys
    return _json(
        {
            "body": body,
            "caveat_key": CAVEAT_KEY,
            "digest": digest,
            "manifest_sha256": manifest_sha,
            "passed_keys": list(passed),
            "passing_evidence": evidence,
        }
    )


def _decision_against_file(review: Path, check_text: str) -> str:
    """Validate a recorded decision against the check file, or report its reason."""
    path = review / "flagship.yaml"
    if not path.is_file():
        return "pending"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return "pending"
    with TemporaryDirectory(prefix="syn-check-") as folder:
        check = Path(folder) / "flagship_check.json"
        check.write_text(check_text, encoding="utf-8")
        try:
            validate_recorded_decision(loaded, check)
        except PlacesError as exc:
            return exc.reason
    return str(loaded["candidate_key"])


def _source_points(config: StageConfig) -> dict[tuple[str, str], tuple[float, float]]:
    found: dict[tuple[str, str], tuple[float, float]] = {}
    for place in read_place_file(config.places_path, config.arabic_tag):
        found[(_PLACES_SOURCE, place.place_id)] = (float(place.lon), float(place.lat))
    box = (FRAME_BOX.west, FRAME_BOX.south, FRAME_BOX.east, FRAME_BOX.north)
    for path in config.buildings_paths:
        for building in read_building_file(path, frame_box=box):
            found[(_BUILDINGS_SOURCE, building.building_id)] = (
                float(building.lon),
                float(building.lat),
            )
    return found


def _manifest_sha(cache: Path) -> str:
    path = cache / "places_s2_t06" / "areas" / "manifest.json"
    if not path.is_file():
        return ""
    return sha256_hex(path.read_bytes())


def _json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n"


def _line(row: Mapping[str, object]) -> str:
    return json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
