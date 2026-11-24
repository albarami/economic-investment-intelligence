"""Engine-free invented startup and operation fixtures."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core/src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "product/src"))

from eii_core.manifest import ColumnSpec, schema_hash
from eii_core.source_chain import SOURCE_KEYS, ChainTable, require_public_chain
from eii_product.store import loader
from eii_product.store.release_check import CheckedRelease, digest_rows, manifest_rows
from eii_product.store.startup import Snapshot

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = "ab" * 32
COMMIT = "cd" * 20
APPLICATION = "ef" * 32


class WorkspaceCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".overnight/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)


def snapshots(
    folder: Path,
) -> tuple[CheckedRelease, dict[str, Any], Snapshot, Snapshot]:
    source = dict(
        source_id="INVENTED-source",
        publisher="INVENTED-publisher",
        title="INVENTED-dataset",
        url="https://invented.invalid/data",
        licence="INVENTED-licence",
        licence_basis="dataset",
        retrieved_on="2026-11-20",
        sha256="bc" * 32,
    )
    schemas = {
        "source_registry": tuple(
            ColumnSpec(name, "string", False) for name in (*SOURCE_KEYS, "kind")
        ),
        "fact_lineage": tuple(
            ColumnSpec(name, "string", False)
            for name in (
                "lineage_id",
                "source_id",
                "table_name",
                "transform",
                "input_class",
            )
        ),
    }
    source_rows = {
        "source_registry": [dict(source, kind="public_dataset")],
        "fact_lineage": [],
    }
    require_public_chain(
        [source],
        tuple(ChainTable(name, tuple(rows)) for name, rows in source_rows.items()),
    )
    document: dict[str, Any] = dict(
        release_id=IDENTITY,
        release_kind="public_only",
        code_version=COMMIT,
        release_contract_version="v1",
        build_id="INVENTED-build",
        built_at="2026-11-20T00:00:00Z",
        rules_version_id="INVENTED-rules",
        engine_versions={"duckdb": "2.0.0", "postgis_target": "3.6", "python": "3.14"},
        sources=[source],
        artefacts=[],
        tables=[
            dict(
                name=name,
                file="tables/" + name + ".parquet",
                grain="INVENTED-metadata-grain",
                row_count=len(source_rows[name]),
                provenance_class="lineage",
                sha256="bc" * 32,
                schema_sha256=schema_hash(columns),
            )
            for name, columns in schemas.items()
        ],
    )
    checked = CheckedRelease(folder, document, schemas)
    rows: dict[str, Any] = {
        **source_rows,
        "release_manifest": manifest_rows(document),
    }
    receipt = dict(
        state="complete",
        release_id=IDENTITY,
        engines=["embedded", "postgres"],
        tables=sorted(rows),
        row_counts={n: len(r) for n, r in rows.items()},
        digests={
            n: digest_rows(r, loader._columns(checked, n), loader._key(n))
            for n, r in rows.items()
        },
    )
    return (
        checked,
        receipt,
        Snapshot(copy.deepcopy(rows), frozenset(rows)),
        Snapshot(copy.deepcopy(rows), frozenset(rows)),
    )


def fixture_reads(
    checked: CheckedRelease, receipt: dict[str, Any], left: Snapshot
) -> ExitStack:
    """Patch IO only; the startup verifier, parity and manifest logic run unchanged."""
    stack = ExitStack()
    stack.enter_context(
        patch("eii_product.store.startup.check_release", return_value=checked)
    )
    stack.enter_context(
        patch("eii_product.store.startup.read_receipt", return_value=receipt)
    )
    stack.enter_context(
        patch(
            "eii_product.store.loader._parquet_rows",
            side_effect=lambda path, columns: left.rows[path.stem],
        )
    )
    return stack
