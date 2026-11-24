"""Adapt stored S2 tables and authenticated receipts to the reviewed envelope.

The local release spec supplies schemas, build metadata and explicit receipt
references, never rows or citations. Approval is supplied by another maker over
the exact prepared envelope; this adapter cannot mint or refresh an approval.
"""

from __future__ import annotations

import errno
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from eii_core.manifest import ColumnSpec, by_name, canonical_json, schema_document
from eii_core.reasons import reason
from eii_core.source_chain import ChainTable, SourceChainRefusal, require_public_chain
from eii_custodian.publicdata.assembly_io import local
from eii_custodian.publicdata.assembly_reports import require_complete
from eii_custodian.publicdata.fetch.allowlist import approve as approve_url
from eii_custodian.publicdata.fetch.registry import PUBLIC_RECEIPT_KINDS
from eii_custodian.publicdata.fetch.snapshots import utc
from eii_custodian.publicdata.grids.build import FACT_LINEAGE, SOURCE_REGISTRY
from eii_custodian.release import pinned
from eii_custodian.release.approval import approval_reason
from eii_custodian.release.assembly import decode, read_assembly
from eii_custodian.release.public_only import (
    TableWrite,
    WriterRefusal,
    _refuse_scalars,
    _refuse_table,
)

SPEC = "review/release_spec.json"
APPROVAL = "review/release_approval.json"
PHASES = (
    "reviewed_selections",
    "frame",
    "spine_graph",
    "gis_property_singles",
    "fsq",
    "series_stage",
    "additions",
    "busyness",
    "artefacts",
    "routing",
)
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_COMMIT = re.compile(r"[a-f0-9]{40}\Z")
_SOURCE_FIELDS = (
    "source_id",
    "publisher",
    "licence_id",
    "licence_basis",
    "retrieved_utc",
    "sha256",
    "fetch_url",
)
_REGISTRY_COLUMNS = (
    ColumnSpec("source_id", "string", False),
    ColumnSpec("kind", "string", False),
    ColumnSpec("title", "string", False),
    ColumnSpec("publisher", "string", False),
    ColumnSpec("url", "string", False),
    ColumnSpec("licence", "string", False),
    ColumnSpec("licence_basis", "string", False),
    ColumnSpec("retrieved_on", "date", False),
    ColumnSpec("sha256", "string", False),
    ColumnSpec("commit_allowed", "bool", False),
    ColumnSpec("attribution", "string", False),
    ColumnSpec("public_splits", "string", True),
)
_LINEAGE_COLUMNS = tuple(
    ColumnSpec(name, "string", nullable)
    for name, nullable in (
        ("lineage_id", False),
        ("table_name", False),
        ("partition_id", True),
        ("measure", True),
        ("breakdown", True),
        ("family_role", True),
        ("source_id", False),
        ("input_class", False),
        ("transform", False),
        ("rules_version_id", True),
    )
)


def _path(cache: Path, name: str) -> Path:
    try:
        if not isinstance(name, str) or any(
            part == ".private" or part.startswith(".env") for part in Path(name).parts
        ):
            raise ValueError
        return local(cache, name)
    except ValueError as error:
        raise ValueError(reason(error, "producer_path_refused")) from None


def _decode(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body, parse_float=Decimal)
        if not isinstance(value, dict):
            raise ValueError
    except (ValueError, UnicodeError) as error:
        raise ValueError(reason(error, "producer_schema_refused")) from None
    return value


def _load(cache: Path, name: str) -> bytes | None:
    """The bytes of ``name`` read through ``pinned``'s descriptors, or None.

    ``_path`` checks the name first; the read then walks the pinned cache with
    no-follow descriptors, so a root, parent or leaf swapped after the check is
    refused as ``producer_path_refused`` rather than read from elsewhere. Only
    an entry that does not exist is absent.
    """
    _path(cache, name)
    try:
        with (
            pinned.root(cache, "producer_path_refused") as root,
            pinned.target(root, name, create=False) as leaf,
        ):
            return pinned.read(leaf)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError("producer_path_refused") from None
        raise ValueError("producer_receipt_missing") from None


def _required(cache: Path, name: str) -> bytes:
    body = _load(cache, name)
    if body is None:
        raise ValueError("producer_receipt_missing")
    return body


def _record(body: bytes, name: str, files: dict[str, str]) -> dict[str, Any]:
    value = _decode(body)
    files[name] = hashlib.sha256(body).hexdigest()
    return value


def _read(cache: Path, name: str, files: dict[str, str]) -> dict[str, Any]:
    return _record(_required(cache, name), name, files)


def _bound(cache: Path, ref: Any, files: dict[str, str]) -> bytes:
    if (
        not isinstance(ref, dict)
        or set(ref) != {"path", "sha256"}
        or not isinstance(ref["sha256"], str)
        or _HASH.fullmatch(ref["sha256"]) is None
    ):
        raise ValueError("producer_schema_refused")
    body = _required(cache, ref["path"])
    if hashlib.sha256(body).hexdigest() != ref["sha256"]:
        raise ValueError("producer_hash_mismatch")
    files[ref["path"]] = ref["sha256"]
    return body


def _source(
    cache: Path, key: str, ref: Any, files: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(ref, dict) or set(ref) != {"format", "receipt", "body"}:
        raise ValueError("producer_schema_refused")
    try:
        receipt = json.loads(_bound(cache, ref["receipt"], files))
        if ref["format"] == "manifest":
            receipt = receipt["receipt"]
        elif ref["format"] != "sidecar":
            raise ValueError("producer_receipt_format_invalid")
        if not isinstance(receipt, dict):
            raise ValueError("producer_receipt_shape_invalid")
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise ValueError(reason(error, "producer_receipt_shape_invalid")) from None
    if receipt.get("kind") not in PUBLIC_RECEIPT_KINDS or any(
        receipt.get(field, "public") != "public"
        for field in ("origin", "provenance", "input_class")
    ):
        raise ValueError("producer_non_public")
    body = _bound(cache, ref["body"], files)
    refusal = _receipt_reason(receipt, key)
    if refusal is not None:
        raise ValueError(refusal)
    if receipt["sha256"] != hashlib.sha256(body).hexdigest():
        raise ValueError("producer_receipt_body_hash_mismatch")
    url = approve_url(receipt["fetch_url"])
    if (
        not url.host
        or url.reason not in {"", "host_refused"}
        or any(ord(character) <= 32 for character in receipt["fetch_url"])
    ):
        raise ValueError("producer_receipt_url_invalid")
    try:
        retrieved = utc(receipt["retrieved_utc"]).date().isoformat()
    except ValueError as error:
        raise ValueError(reason(error, "producer_receipt_date_invalid")) from None
    row = dict(
        source_id=key,
        kind="reviewed_config"
        if receipt["kind"] == "reviewed_config"
        else "public_document"
        if receipt["kind"] in {"public_document", "public_page", "terms_page"}
        else "public_dataset",
        title=receipt["title_en"],
        publisher=receipt["publisher"],
        url=receipt["fetch_url"],
        licence=receipt["licence_id"],
        licence_basis=receipt["licence_basis"],
        retrieved_on=retrieved,
        sha256=receipt["sha256"],
        commit_allowed=receipt.get("commit_allowed", False),
        attribution=receipt["publisher"],
        public_splits=";".join(receipt.get("public_splits", [])) or None,
    )
    return row, receipt


def _receipt_reason(receipt: dict[str, Any], key: str) -> str | None:
    """Name the missing field without ever copying its supplied value."""
    for field, code in (
        ("source_id", "producer_receipt_source_id_invalid"),
        ("publisher", "producer_receipt_publisher_invalid"),
        ("retrieved_utc", "producer_receipt_retrieved_utc_invalid"),
        ("sha256", "producer_receipt_sha256_invalid"),
        ("fetch_url", "producer_receipt_fetch_url_invalid"),
        ("title_en", "producer_receipt_title_en_invalid"),
        ("key", "producer_receipt_key_invalid"),
    ):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            return code
    if receipt["key"] != key:
        return "producer_receipt_key_mismatch"
    if receipt.get("switched_off", False) is not False:
        return "producer_receipt_switched_off"
    if not isinstance(receipt.get("licence_id"), str):
        return "producer_receipt_licence_id_invalid"
    if not isinstance(receipt.get("licence_basis"), str):
        return "producer_receipt_licence_basis_invalid"
    if not (receipt["licence_id"].strip() or receipt["licence_basis"].strip()):
        return "producer_receipt_licence_missing"
    return None


def _table(
    name: str, columns: tuple[ColumnSpec, ...], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    return dict(name=name, columns=schema_document(columns), rows=rows)


def _columns(value: Any) -> tuple[ColumnSpec, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("producer_schema_refused")
    result = tuple(ColumnSpec(**column) for column in value)
    if len({column.name for column in result}) != len(result) or any(
        not isinstance(column.name, str)
        or not column.name
        or not isinstance(column.logical_type, str)
        or type(column.nullable) is not bool
        for column in result
    ):
        raise ValueError("producer_schema_refused")
    try:
        schema_document(result)
    except ValueError as error:
        raise ValueError(reason(error, "producer_schema_refused")) from None
    return result


def _value(value: Any, column: ColumnSpec) -> Any:
    """Encode typed source values without implicit driver coercion or rounding."""
    if value is None:
        if not column.nullable:
            raise ValueError("producer_schema_refused")
        return None
    logical = column.logical_type
    if logical.startswith("decimal("):
        if type(value) not in (str, int, Decimal):
            raise ValueError("producer_schema_refused")
        try:
            number = Decimal(value)
        except InvalidOperation as error:
            raise ValueError(reason(error, "producer_schema_refused")) from None
        if not number.is_finite():
            raise ValueError("producer_schema_refused")
        precision, scale = map(int, logical[8:-1].split(","))
        parts = number.as_tuple()
        exponent = int(parts.exponent)
        digits = list(parts.digits)
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        if (
            scale > precision
            or precision < 1
            or (
                digits
                and (-exponent > scale or len(digits) + exponent > precision - scale)
            )
        ):
            raise ValueError("producer_schema_refused")
        return str(value)
    if logical in {"int", "cell"}:
        if type(value) is not int or not -(2**63) <= value < 2**63:
            raise ValueError("producer_schema_refused")
    elif logical == "bool":
        if type(value) is not bool:
            raise ValueError("producer_schema_refused")
    elif logical in {"string", "month", "date", "timestamp"}:
        if not isinstance(value, str):
            raise ValueError("producer_schema_refused")
        try:
            decode(value, column)
        except (ValueError, TypeError) as error:
            raise ValueError(reason(error, "producer_schema_refused")) from None
    elif logical == "geometry":
        try:
            decode(value, column)
        except (ValueError, TypeError) as error:
            raise ValueError(reason(error, "producer_schema_refused")) from None
    return value


def _lineage(name: str, keys: list[str], transform: str) -> list[dict[str, Any]]:
    return [
        dict(
            lineage_id="lin_" + name,
            table_name=name,
            partition_id=None,
            measure=None,
            breakdown=None,
            family_role=None,
            source_id=key,
            input_class="public",
            transform=transform,
            rules_version_id=None,
        )
        for key in keys
    ]


def _phase(cache: Path, name: str, files: dict[str, str]) -> dict[str, Any] | None:
    """The phase record ``name`` and its tables, or None if it was not written."""
    relative = "assembly/" + name + ".json"
    body = _load(cache, relative)
    if body is None:
        return None
    data = _record(body, relative, files)
    if name == "artefacts":
        from eii_custodian.release.artefacts import recorded

        recorded(data)
    if name == "spine_graph":
        from eii_custodian.publicdata.review.cache_fixture import read_parquet

        tables = {}
        for table in ("graph_node", "graph_edge"):
            relative = "assembly/graph/" + table + ".parquet"
            body = _required(cache, relative)
            files[relative] = hashlib.sha256(body).hexdigest()
            tables[table] = list(read_parquet(body))
        data["tables"] = tables
    phase_tables = data.get("tables")
    if isinstance(phase_tables, dict):
        data["tables"] = {
            name: rows
            for name, rows in phase_tables.items()
            if name not in {FACT_LINEAGE, SOURCE_REGISTRY}
        }
    return data


def _source_key(tag: Any, keys: list[str], receipts: dict[str, Any]) -> str:
    matches = (
        [key for key in keys if tag in {key, receipts[key]["source_id"]}]
        if tag
        else keys
    )
    if len(matches) != 1:
        raise ValueError("producer_chain_incomplete")
    return matches[0]


def _recorded_artefacts(phases: dict[str, Any]) -> dict[str, str]:
    """Map each path of the ``artefacts`` phase record to its placed hash."""
    if "artefacts" not in phases:
        return {}
    from eii_custodian.release.artefacts import recorded

    return {item["path"]: item["sha256"] for item in recorded(phases["artefacts"])}


def _routing_chain(
    phases: dict[str, Any], artefacts: list[Any], receipts: dict[str, Any]
) -> None:
    """Bind the routing file to its build method and authenticated OSM receipt."""
    from eii_custodian.publicdata.places.area_files import ENGINE_PIN, ROAD_KEY

    routing = [ref for ref in artefacts if ref["path"] == "artefacts/routing/tiles.tar"]
    if not routing:
        return
    data = phases.get("routing", {})
    link = data.get("source_chain", {}).get(ROAD_KEY, {})
    if (
        data.get("method") != "public-assembly.routing"
        or data.get("method_version") != "1"
        or data.get("engine_version") != ENGINE_PIN
        or routing != [data.get("artefact")]
        or ROAD_KEY not in receipts
        or any(link.get(field) != receipts[ROAD_KEY][field] for field in _SOURCE_FIELDS)
    ):
        raise ValueError("producer_chain_incomplete")


def _candidate(cache: Path, fc_register_sha256: str | None) -> dict[str, Any]:
    files: dict[str, str] = {}
    spec = _read(cache, SPEC, files)
    if (
        set(spec) != {"version", "scalars", "sources", "tables", "artefacts"}
        or type(spec["version"]) is not int
        or spec["version"] != 1
    ):
        raise ValueError("producer_schema_refused")
    scalars = spec["scalars"]
    if (
        not isinstance(scalars, dict)
        or set(scalars)
        != {
            "build_id",
            "built_at",
            "code_version",
            "engine_versions",
            "release_contract_version",
            "release_kind",
            "rules_version_id",
        }
        or not isinstance(scalars["code_version"], str)
        or _COMMIT.fullmatch(scalars["code_version"]) is None
        or any(
            not isinstance(scalars.get(key), str) or not scalars[key].strip()
            for key in (
                "build_id",
                "built_at",
                "release_contract_version",
                "rules_version_id",
            )
        )
        or scalars["release_contract_version"] != "release.v1"
    ):
        raise ValueError("producer_schema_refused")
    _refuse_scalars(scalars)
    require_complete(_read(cache, "assembly/final_audit.json", files))
    if not isinstance(spec["sources"], dict) or not spec["sources"]:
        raise ValueError("producer_chain_incomplete")
    registry, receipts = {}, {}
    for key, ref in sorted(spec["sources"].items()):
        registry[key], receipts[key] = _source(cache, key, ref, files)
    phases = {}
    for phase in PHASES:
        data = _phase(cache, phase, files)
        if data is not None:
            phases[phase] = data
    owners: dict[str, str] = {}
    for phase, data in phases.items():
        if not isinstance(data.get("tables"), dict):
            raise ValueError("producer_schema_refused")
        for name, rows in data["tables"].items():
            if name in owners:
                # S2 appends GIS gateways to the frame gazetteer. The combined
                # stored rows must retain the complete earlier prefix.
                previous = phases[owners[name]]["tables"][name]
                if not (
                    name == "gazetteer"
                    and phase == "gis_property_singles"
                    and owners[name] == "frame"
                    and isinstance(rows, list)
                    and rows[: len(previous)] == previous
                ):
                    raise ValueError("producer_schema_refused")
            owners[name] = phase
    if not isinstance(spec["tables"], list) or not spec["tables"]:
        raise ValueError("producer_chain_incomplete")
    tables, lineage, used = [], [], set()
    for item in spec["tables"]:
        if not isinstance(item, dict) or set(item) != {
            "name",
            "phase",
            "columns",
            "source_keys",
        }:
            raise ValueError("producer_schema_refused")
        name, phase, keys = item["name"], item["phase"], item["source_keys"]
        catalogue = by_name(name)
        if (
            catalogue is None
            or catalogue.manifest_class in {"protected", "simulated", "lineage"}
            or catalogue.writer == "privacy"
        ):
            raise ValueError("producer_table_refused")
        if name in used or phase not in phases or owners.get(name) != phase:
            raise ValueError("producer_schema_refused")
        data = phases[phase]
        if (
            data.get("method") != "public-assembly." + phase
            or data.get("method_version") != "1"
            or not isinstance(keys, list)
            or not keys
            or len(set(keys)) != len(keys)
            or any(key not in receipts for key in keys)
        ):
            raise ValueError("producer_chain_incomplete")
        for key in keys:
            link = data.get("source_chain", {}).get(key, {})
            if any(link.get(field) != receipts[key][field] for field in _SOURCE_FIELDS):
                raise ValueError("producer_chain_incomplete")
        bindings = data.get("table_sources", {})
        if name in bindings and set(bindings[name]) != set(keys):
            raise ValueError("producer_chain_incomplete")
        if "source_tables" in data:
            declared = {
                key for key, names in data["source_tables"].items() if name in names
            }
            if declared != set(keys):
                raise ValueError("producer_chain_incomplete")
        columns = _columns(item["columns"])
        if catalogue.manifest_class == "public" and not any(
            column.name == "source_id" for column in columns
        ):
            columns += (ColumnSpec("source_id", "string", False),)
        original = data.get("tables", {}).get(name)
        if not isinstance(original, list):
            raise ValueError("producer_schema_refused")
        rows = []
        for original_row in original:
            row = dict(original_row)
            lineage_node = name == "graph_node" and row.get("node_type") in {
                "source",
                "table",
                "release",
            }
            lineage_edge = name == "graph_edge" and row.get("edge_type") in {
                "sourced_from",
                "contains",
            }
            allowed = (
                {"public", "lineage"} if lineage_node or lineage_edge else {"public"}
            )
            if row.get("provenance", "public") not in allowed or any(
                row.get(field, "public") != "public"
                for field in ("origin", "input_class")
            ):
                raise ValueError("producer_non_public")
            if any(column.name == "source_id" for column in columns):
                tag = row.get("source_key") or row.get("source_id")
                row["source_id"] = _source_key(tag, keys, receipts)
            if "source_ids" in row:
                if not isinstance(row["source_ids"], str) or not row["source_ids"]:
                    raise ValueError("producer_chain_incomplete")
                for tag in row["source_ids"].split(";"):
                    _source_key(tag, keys, receipts)
            if set(row) != {column.name for column in columns}:
                raise ValueError("producer_schema_refused")
            rows.append(
                {column.name: _value(row[column.name], column) for column in columns}
            )
        tables.append(_table(name, columns, rows))
        lineage.extend(
            _lineage(
                name,
                sorted(keys),
                "eii_custodian.publicdata.assembly_adapters.Production."
                + phase
                + "@"
                + data["method_version"],
            )
        )
        used.add(name)
    # An omitted phase table cannot disappear merely by omitting its spec entry.
    actual = {name for data in phases.values() for name in data.get("tables", {})}
    if actual != used:
        raise ValueError("producer_chain_incomplete")
    all_keys = sorted(registry)
    for name in ("fact_lineage", "source_registry"):
        lineage.extend(
            _lineage(name, all_keys, "eii_custodian.release.producer.prepare@1")
        )
    tables.extend(
        [
            _table(
                "source_registry",
                _REGISTRY_COLUMNS,
                [registry[key] for key in all_keys],
            ),
            _table("fact_lineage", _LINEAGE_COLUMNS, lineage),
        ]
    )
    sources = [
        {
            key: row[key]
            for key in (
                "source_id",
                "publisher",
                "title",
                "url",
                "licence",
                "licence_basis",
                "retrieved_on",
                "sha256",
            )
        }
        for row in registry.values()
    ]
    held = []
    for table in tables:
        columns = tuple(ColumnSpec(**column) for column in table["columns"])
        decoded_rows = tuple(
            {column.name: decode(row[column.name], column) for column in columns}
            for row in table["rows"]
        )
        _refuse_table(TableWrite(table["name"], columns, decoded_rows))
        held.append(ChainTable(table["name"], decoded_rows))
    require_public_chain(sources, held)
    artefacts = spec["artefacts"]
    if not isinstance(artefacts, list):
        raise ValueError("producer_schema_refused")
    recorded = _recorded_artefacts(phases)
    _routing_chain(phases, artefacts, receipts)
    for ref in artefacts:
        if not ref["path"].startswith("artefacts/"):
            raise ValueError("producer_path_refused")
        # Decision 0096: the spec copies the placed record; never a typed hash.
        if recorded.get(ref["path"], ref["sha256"]) != ref["sha256"]:
            raise ValueError("producer_hash_mismatch")
        _bound(cache, ref, files)
    if sorted(ref["path"] for ref in artefacts) != sorted(recorded):
        raise ValueError("producer_chain_incomplete")
    candidate = dict(
        version=1,
        scalars=scalars,
        sources=sources,
        tables=sorted(tables, key=lambda table: table["name"]),
        artefacts=sorted(artefacts, key=lambda ref: ref["path"]),
        files=files,
    )
    if fc_register_sha256 is not None:
        # Computed by the lead's release build from the file's bytes (L-1509).
        if type(fc_register_sha256) is not str or not _HASH.fullmatch(
            fc_register_sha256
        ):
            raise ValueError("producer_schema_refused")
        candidate["listed_inputs"] = [
            dict(name="fc_register", sha256=fc_register_sha256)
        ]
    return candidate


def _write(cache: Path, name: str, value: object, exists: str | None = None) -> None:
    """Publish one output through the pinned descriptors of ``pinned``; with an
    ``exists`` reason, never replace a leaf and refuse an existing one so."""
    _path(cache, name)
    try:
        with (
            pinned.root(cache, "producer_path_refused") as root,
            pinned.target(root, name) as leaf,
            pinned.publish(leaf, replace=exists is None) as stream,
        ):
            stream.write(canonical_json(value).encode())
    except FileExistsError:
        raise ValueError(exists or "producer_path_refused") from None
    except OSError:
        raise ValueError("producer_path_refused") from None


def prepare(cache: Path, *, fc_register_sha256: str | None = None) -> dict[str, Any]:
    """Write the deterministic candidate for independent review, never approval.

    ``fc_register_sha256`` is the hash the release build computed from the
    register file's bytes; the spec never supplies one.
    """
    try:
        document = _candidate(cache, fc_register_sha256)
    except (
        SourceChainRefusal,
        WriterRefusal,
        KeyError,
        TypeError,
        AttributeError,
    ) as error:
        raise ValueError(reason(error)) from None
    _write(cache, "assembly/release_candidate.json", document)
    return document


def produce(cache: Path, *, fc_register_sha256: str | None = None) -> dict[str, Any]:
    """Materialise only the exact independently approved candidate and review."""
    document = prepare(cache, fc_register_sha256=fc_register_sha256)
    approval = _path(cache, APPROVAL)
    if not approval.exists() and not approval.is_symlink():
        raise ValueError("candidate_written_approval_missing")
    review = _read(cache, APPROVAL, {})
    refusal = approval_reason(
        review,
        document["scalars"]["code_version"],
        hashlib.sha256(canonical_json(document).encode()).hexdigest(),
    )
    if refusal is not None:
        raise ValueError(refusal)
    _write(cache, "assembly/release.json", document)
    _write(cache, "assembly/release_review.json", review)
    return read_assembly(cache)
