"""Review-file mappings; a missing spelling is never inferred."""

import csv
import json
from pathlib import Path
from typing import Any

from .checks import FrameError, safe_key

DISTRICT_CROSSWALK_HEADER = ("name", "municipality_code", "district_keys", "basis")


def read_csv(
    path: Path, *, header: tuple[str, ...] | None = None
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        if header is None:
            return list(csv.DictReader(lines))
        reader = csv.reader(lines, strict=True)
        try:
            if next(reader, None) != list(header):
                raise FrameError("district_alias: CSV header")
            rows = []
            for row in reader:
                if len(row) != len(header):
                    raise FrameError("district_alias: CSV row width")
                rows.append(dict(zip(header, row, strict=True)))
            return rows
        except csv.Error as exc:
            raise FrameError("district_alias: CSV row width or syntax") from exc


def normalise_name(name: str) -> str:
    """L-222 N2: whitespace only; preserve case, letters, hyphens and words."""
    return " ".join(name.split())


def load_municipality_names(review: Path, known: set[str]) -> list[dict[str, str]]:
    rows = read_csv(review / "municipality_names.csv")
    seen: dict[str, str] = {}
    for row in rows:
        name = normalise_name(row["name"])
        key = row["municipality_code"]
        if key not in known:
            raise FrameError("municipality_names: unknown_key")
        if name in seen and seen[name] != key:
            raise FrameError("municipality_names: conflict")
        seen[name] = key
        row["name"] = name
    return rows


def municipality_key(name: str, rows: list[dict[str, str]]) -> str:
    keys = {
        row["municipality_code"]
        for row in rows
        if normalise_name(row["name"]) == normalise_name(name)
    }
    if len(keys) != 1:
        raise FrameError("unmapped municipality spelling")
    return safe_key(keys.pop())


def municipality_keys(
    source: str,
    records: list[dict[str, Any]],
    fields: tuple[str, ...],
    names: list[dict[str, str]],
    report_file: Path | None,
) -> list[str]:
    """One reviewed lookup for municipal tables, including bilingual agreement.

    Only the build report file receives unknown source spellings. Exceptions
    contain the source, field and distinct-spelling count, never those values.
    """
    known = {row["name"] for row in names}
    missing = {
        field: sorted(
            {r[field] for r in records if normalise_name(r[field]) not in known}
        )
        for field in fields
    }
    missing = {field: values for field, values in missing.items() if values}
    if missing:
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(
                json.dumps({source: missing}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        raise FrameError(
            "; ".join(
                f"{source}: {field}: {len(values)} unmapped spellings"
                for field, values in missing.items()
            )
        )
    result = []
    for record in records:
        keys = {municipality_key(record[field], names) for field in fields}
        if len(keys) != 1:
            raise FrameError(f"{source}: municipality name disagreement")
        result.append(keys.pop())
    return result


def check_district_crosswalk(rows: list[dict[str, str]], known: set[str]) -> None:
    """Every reviewed district key belongs to the selected frame."""
    for row in rows:
        keys = {safe_key(key) for key in row["district_keys"].split(";")}
        if not keys <= known:
            raise FrameError("district_crosswalk: outside_frame")


def district_keys(
    name: str,
    municipality_code: str,
    rows: list[dict[str, str]],
    known: set[str],
) -> tuple[tuple[str, ...], str | None]:
    matches = [
        row
        for row in rows
        if normalise_name(row["name"]) == normalise_name(name)
        and row["municipality_code"] == municipality_code
    ]
    if not matches:
        return (), "unmatched_district"
    if len(matches) != 1:
        raise FrameError("duplicate district mapping")
    check_district_crosswalk(matches, known)
    return tuple(safe_key(key) for key in matches[0]["district_keys"].split(";")), None


def check_zones(
    rows: list[dict[str, str]],
    observed: dict[str, set[str]],
    frame_zones: set[str] | None = None,
) -> None:
    codes = [row["zone_code"] for row in rows]
    if len(set(codes)) != len(codes):
        raise FrameError("duplicate zone code")
    if frame_zones is not None:
        matched = {row["zone_code"] for row in rows if row["status"] == "matched"}
        if not frame_zones <= matched:
            raise FrameError("frame zone not matched")
        if not matched <= frame_zones:
            raise FrameError("matched zone outside frame")
    for row in rows:
        safe_key(row["zone_code"])
        if row["status"] not in {"matched", "absent_in_source", "merged", "no_polygon"}:
            raise FrameError("invalid zone status")
    for source, values in observed.items():
        listed = {row.get(source, "") for row in rows}
        if not values <= listed:
            raise FrameError(f"{source}: unlisted zone")


def greater_doha_keys(review: Path, known: set[str]) -> set[str]:
    names = load_municipality_names(review, known)
    result: set[str] = set()
    for row in read_csv(review / "greater_doha_municipalities.csv"):
        key = municipality_key(row["name"], names)
        if key in result:
            raise FrameError("Greater Doha: duplicate municipality")
        result.add(key)
    return result


def check_municipality_names(
    records: list[dict[str, str]], names: list[dict[str, str]]
) -> None:
    for row in records:
        for field in ("name_en", "name_ar", "layer_name_en", "layer_name_ar"):
            try:
                key = municipality_key(row[field], names)
            except FrameError as exc:
                raise FrameError(
                    f"municipality source spelling: {field}: unmapped"
                ) from exc
            if key != row["municipality_code"]:
                raise FrameError(f"municipality source spelling: {field}: wrong code")


def district_free_zones(review: Path) -> set[str]:
    result = set()
    for row in read_csv(review / "zones_without_districts.csv"):
        if (
            set(row) != {"zone_code", "reason"}
            or row["reason"] != "no_district_in_boundary_source"
        ):
            raise FrameError("district-free reason")
        key = safe_key(row["zone_code"])
        if key in result:
            raise FrameError("duplicate district-free zone")
        result.add(key)
    return result


def observed_zones(
    inventory: dict[str, dict[str, tuple[str, ...]]],
) -> dict[str, set[str]]:
    return {
        source: set(values[field])
        for source, values in inventory.items()
        for field in ("zone_number", "ZONE_NO", "KEY_NO", "ZONENO", "zone_code")
        if field in values
    }


def propose_reviews(
    review: Path,
    output: Path | None,
    frame_zones: set[str],
    inventory: dict[str, dict[str, tuple[str, ...]]],
    report: list[str],
) -> None:
    """Numeric correspondences for human review only; never loaded as mappings."""
    committed = read_csv(review / "zone_crosswalk.csv")
    observed = observed_zones(inventory)
    for source, tokens in sorted(observed.items()):
        missing = tokens - {row.get(source, "") for row in committed}
        report.append(f"{source}: {len(missing)} unlisted zone numbers")
    if output is None:
        return
    output.mkdir(parents=True, exist_ok=True)
    columns = sorted(
        observed.keys()
        | {key for row in committed for key in row} - {"zone_code", "status"}
    )
    rows = [dict(row) for row in committed]
    represented = {zone_number(row["zone_code"]) for row in committed}
    tokens = frame_zones | {
        zone_number(token) for values in observed.values() for token in values
    }
    for token in sorted(tokens):
        missing_sources = {
            source: sorted(
                value
                for value in values
                if zone_number(value) == token
                and value not in {row.get(source, "") for row in committed}
            )
            for source, values in observed.items()
        }
        count = max((len(values) for values in missing_sources.values()), default=0)
        if token in represented and count == 0:
            continue
        for position in range(max(1, count)):
            rows.append(
                {
                    "zone_code": token,
                    "status": "matched" if token in frame_zones else "unmatched",
                    **{
                        source: values[position]
                        for source, values in missing_sources.items()
                        if position < len(values)
                    },
                }
            )
    with (output / "proposed_zone_crosswalk.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["zone_code", *columns, "status"])
        writer.writeheader()
        writer.writerows(rows)
    with (output / "proposed_population_indicators.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["indicator", "mapped_indicator"])
        writer.writeheader()
        writer.writerows(
            {"indicator": name, "mapped_indicator": ""}
            for name in inventory.get("pop_muni", {}).get("indicator", ())
        )


def zone_number(token: str) -> str:
    """Compare decimal zone numbers only, retaining source tokens in columns."""
    return str(int(token)) if token.isascii() and token.isdecimal() else token
