"""PYTEST_DONT_REWRITE — validation-only local lineage and independent replay.

Never a release fact, acquisition path or cache override. Errors carry only
closed inventory IDs and fixed reasons; neither parser messages nor values.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from eii_core.calc.facts import Measure, SourceChain
from eii_core.calc.public_methods import coverage_share
from eii_core.calc.public_series import rounded
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.frame.build import read_cached
from eii_custodian.publicdata.frame.layers import layer_rows
from eii_custodian.publicdata.frame.measures import check_employment
from eii_custodian.publicdata.gis.layers import _parse_body
from eii_custodian.publicdata.stage import _LOCAL_FIELDS

from .restricted_cases import CASES, case_by_id

_DECIMAL = re.compile(r"-?\d+(?:\.\d+)?", re.ASCII)
_SHA = re.compile(r"[a-f0-9]{64}")


class ExpectationError(ValueError):
    """Value-free refusal at the local test boundary."""


def refuse(case, reason):
    raise ExpectationError(f"{case.case_id}:{reason}") from None


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key") from None
        result[key] = value
    return result


def _path(cache, relative, case):
    path = cache / relative
    if cache.is_symlink() or path.is_absolute() != cache.is_absolute():
        refuse(case, "path_refused")
    if not path.resolve().is_relative_to(cache.resolve()):
        refuse(case, "path_refused")
    for parent in (path, *path.parents):
        if parent.is_symlink():
            refuse(case, "path_refused")
        if parent == cache:
            break
    return path


def _json(cache, relative, case):
    path = _path(cache, relative, case)
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except FileNotFoundError:
        refuse(case, "missing_record")
    except (ValueError, OSError, UnicodeError):
        refuse(case, "record_invalid")


def precision(case):
    if case.case_id == "PUB-71":
        return {
            key: 1 if key == "national_1dp" else 0 for key in _LOCAL_FIELDS["PUB-71"]
        }
    return {"rows": 0}


def pins(cache, case):
    data = _json(cache, "method_pins.json", case)
    if not isinstance(data, dict):
        refuse(case, "source_pin_mismatch")
    result = {}
    for source in case.source_ids:
        digest = data.get(source)
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            refuse(case, "source_pin_mismatch")
        result[source] = digest
    return result


def load_expectation(cache, case):
    """Join local expectations only here, never in a replay reader."""
    case_by_id(case.case_id)
    data = _json(cache, "local_expectations/restricted_cases.json", case)
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "cases"}
        or data["version"] != "restricted.v1"
    ):
        refuse(case, "record_invalid")
    rows = data["cases"]
    if not isinstance(rows, dict) or set(rows) - {c.case_id for c in CASES}:
        refuse(case, "record_invalid")
    if case.case_id not in rows:
        refuse(case, "missing_record")
    record = rows[case.case_id]
    keys = {
        "method",
        "version",
        "period",
        "geography",
        "units",
        "expectation_origin",
        "source_shas",
        "record_sha256",
        "precision",
        "tolerance",
    }
    if case.case_id != "PUB-71":
        keys.add("expected")
    if not isinstance(record, dict) or set(record) != keys:
        refuse(case, "record_invalid")
    origin = record["expectation_origin"]
    if not isinstance(origin, str) or not origin.strip():
        refuse(case, "record_invalid")
    for key, value in (
        ("method", case.method),
        ("version", case.version),
        ("period", case.period),
        ("geography", list(case.geography)),
        ("units", case.units),
        ("precision", precision(case)),
    ):
        if record[key] != value:
            refuse(case, "record_invalid")
    expected = (
        _json(cache, "local_expectations/PUB-71.json", case)
        if case.case_id == "PUB-71"
        else record["expected"]
    )
    if not isinstance(expected, dict) or set(expected) != set(precision(case)):
        refuse(case, "record_invalid")
    if any(
        not isinstance(value, str)
        or not _DECIMAL.fullmatch(value)
        or not Decimal(value).is_finite()
        for value in expected.values()
    ):
        refuse(case, "record_invalid")
    if record["tolerance"] != dict.fromkeys(expected, "0"):
        refuse(case, "record_invalid")
    if any(type(value) is not int for value in record["precision"].values()):
        refuse(case, "record_invalid")
    if record["source_shas"] != pins(cache, case):
        refuse(case, "source_pin_mismatch")
    if record["record_sha256"] != hashlib.sha256(canonical(expected)).hexdigest():
        refuse(case, "record_checksum_mismatch")
    return expected


@dataclass(frozen=True)
class CaseLineage:
    case_id: str
    source_key: str
    method: str
    version: str
    publisher: str
    dataset: str
    fetch_url: str
    retrieved: str
    sha256: str
    licence_id: str
    licence_basis: str
    release_table: str | None

    def __post_init__(self):
        for name in (
            "case_id",
            "source_key",
            "method",
            "version",
            "publisher",
            "dataset",
            "fetch_url",
            "retrieved",
            "sha256",
            "licence_basis",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("lineage_invalid") from None
        if (
            not isinstance(self.licence_id, str)
            or not self.fetch_url.startswith(("https://", "http://"))
            or not _SHA.fullmatch(self.sha256)
        ):
            raise ValueError("lineage_invalid") from None
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.retrieved):
            raise ValueError("lineage_invalid") from None
        date.fromisoformat(self.retrieved)

    def source_chain(self):
        return SourceChain(
            self.source_key,
            self.release_table,
            self.method,
            self.version,
            self.publisher,
            self.dataset,
            self.fetch_url,
            self.licence_id,
            self.retrieved,
            self.sha256,
        )


def validate_lineage(chain, entry, case):
    if (chain.case_id, chain.source_key, chain.method, chain.version) != (
        case.case_id,
        entry.key,
        case.method,
        case.version,
    ):
        raise ValueError("lineage_identity") from None
    if (chain.licence_id, chain.licence_basis) != (
        entry.licence_id,
        entry.licence_basis,
    ):
        raise ValueError("lineage_licence") from None
    if (
        chain.release_table is not None
        and chain.release_table not in entry.release_tables
    ):
        raise ValueError("lineage_table") from None


def _receipt(entry, receipt, digest, case):
    for key, value in (
        ("source_id", entry.source_id),
        ("key", entry.key),
        ("licence_id", entry.licence_id),
        ("licence_basis", entry.licence_basis),
        ("sha256", digest),
    ):
        if receipt.get(key) != value:
            raise ValueError("receipt_invalid") from None
    for key in ("publisher", "title_en", "fetch_url", "retrieved_utc", "sha256"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            raise ValueError("receipt_invalid") from None
    if receipt.get("switched_off") is not False:
        raise ValueError("receipt_invalid") from None
    chain = CaseLineage(
        case.case_id,
        entry.key,
        case.method,
        case.version,
        receipt["publisher"],
        receipt["title_en"],
        receipt["fetch_url"],
        receipt["retrieved_utc"][:10],
        digest,
        receipt["licence_id"],
        receipt["licence_basis"],
        entry.release_tables[0] if entry.release_tables else None,
    )
    validate_lineage(chain, entry, case)
    return chain


@dataclass(frozen=True)
class Replay:
    values: dict[str, str]
    lineage: tuple[CaseLineage, ...]


def replay(cache, case):
    """Source-only replay. This signature deliberately has no expected record."""
    try:
        selected = pins(cache, case)
        registry = {entry.key: entry for entry in load_registry()}
        layers = {}
        chains = []
        for source in case.source_ids:
            entry = registry[source]
            _path(cache, source, case)
            payload, receipt = read_cached(cache, entry, digest=selected[source])
            chains.append(_receipt(entry, receipt, selected[source], case))
            layers[source] = layer_rows(source, payload)
        if case.case_id != "PUB-71":
            return Replay({"rows": str(len(layers[case.source_key]))}, tuple(chains))
        check_employment(layers)
        rows = layers[case.source_key]
        if len({row["ZONE_NO"] for row in rows}) != len(rows):
            raise ValueError("duplicate_zone") from None
        chain = chains[0].source_chain()

        def share(group, geography):
            private = sum(row["Private"] for row in group)
            total = sum(row["Total_Economic_active___15"] for row in group)

            def measure(value):
                return Measure(
                    Decimal(value),
                    "count",
                    case.period,
                    geography,
                    "national" if geography == "national" else "public",
                    "public",
                    (chain,),
                )

            result = coverage_share(measure(private), measure(total))
            return private, total, result["percent"]

        private, total, national = share(rows, "national")
        values = {
            "national_private": str(private),
            "national_all": str(total),
            "national_1dp": rounded(national.exact_unrounded, 1),
        }
        for zone in (69, 70):
            group = [row for row in rows if row["ZONE_NO"] == zone]
            if len(group) != 1:
                raise ValueError("zone_missing") from None
            _, _, result = share(group, f"zone:{zone}")
            if result.geography != f"zone:{zone}":
                raise ValueError("geography_invalid") from None
            values[f"zone_{zone}_0dp"] = rounded(result.exact_unrounded, 0)
        return Replay(values, tuple(chains))
    except ExpectationError:
        raise
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError):
        refuse(case, "source_invalid")


def read_gis(cache, case):
    """Verified GIS byte path, usable when its finding recipe is confirmed."""
    try:
        digest = pins(cache, case)[case.source_key]
        entry = next(e for e in load_registry() if e.key == case.source_key)
        _path(cache, entry.key, case)
        selected = read_snapshot(cache / entry.key, digest)
        chain = _receipt(entry, selected.sidecar, digest, case)
        return _parse_body(selected.body), chain
    except ExpectationError:
        raise
    except (ValueError, KeyError, TypeError, OSError):
        refuse(case, "source_invalid")


def boundary_finding_counts(layers):
    counts = {}
    for layer in layers:
        if layer.layer_id in counts:
            raise ValueError("duplicate_layer") from None
        counts[layer.layer_id] = len(layer.features)
    return counts


def h2_hour_counts(rows, *, period, hours, weight):
    """Explicit recipe only; no guessed real period, hour predicate or weight."""
    selected = total = 0
    for row in rows:
        if str(row["accident_year"]) != period:
            continue
        amount = 1 if weight is None else row[weight]
        if type(amount) is not int or amount < 0:
            raise ValueError("invalid_count") from None
        total += amount
        if row["accident_time"] in hours:
            selected += amount
    return selected, total


def compare(case, actual, expected):
    if set(actual) != set(expected) or any(
        Decimal(actual[key]) != Decimal(expected[key]) for key in expected
    ):
        refuse(case, "expectation_mismatch")


def summary_reasons(text, exit_code):
    """Validate the lead's captured default short summary, never launch a run."""
    failures = [
        line for line in text.splitlines() if line.startswith(("FAILED ", "ERROR "))
    ]
    reasons = set()
    for line in failures:
        found = re.fullmatch(r"FAILED .+ - ([A-Za-z0-9_-]+):([a-z_]+)", line)
        if found is None:
            raise ValueError("summary_unparsed") from None
        case_id, reason = found.groups()
        case_by_id(case_id)
        if reason not in {
            "awaiting_routine",
            "awaiting_expectation",
            "expectation_mismatch",
            "missing_record",
            "record_invalid",
            "record_checksum_mismatch",
            "source_pin_mismatch",
            "path_refused",
            "source_invalid",
        }:
            raise ValueError("summary_unparsed") from None
        reasons.add(case_id + ":" + reason)
    final = text.strip().splitlines()[-1] if text.strip() else ""
    count = re.fullmatch(
        r"(?:=+ )?(\d+) failed(?:, \d+ passed)? in [0-9.]+s(?: .*)?", final
    )
    if (
        exit_code != 1
        or count is None
        or int(count[1]) != len(failures)
        or len(reasons) != len(failures)
    ):
        raise ValueError("summary_counts") from None
    return reasons


def check_case(cache, case):
    """The only reporting boundary: default pytest output cannot expose values."""
    if case.status != "ready":
        pytest.fail(f"{case.case_id}:{case.status}", pytrace=False)
    try:
        expected = load_expectation(cache, case)
        actual = replay(cache, case)
        compare(case, actual.values, expected)
        return
    except ExpectationError as error:
        reason = str(error).split(":", 1)[-1]
        if reason not in {
            "missing_record",
            "record_invalid",
            "record_checksum_mismatch",
            "source_pin_mismatch",
            "path_refused",
            "source_invalid",
            "expectation_mismatch",
        }:
            reason = "source_invalid"
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError):
        reason = "source_invalid"
    # Outside the exception handler: even pytest's default chained-exception
    # rendering must have no original parser message or calculated value.
    pytest.fail(f"{case.case_id}:{reason}", pytrace=False)
