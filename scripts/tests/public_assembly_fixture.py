"""Invented Public build outputs; no real cache or network input."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import public_release_fixture as fixture

from eii_core.manifest import canonical_json
from eii_custodian.publicdata.fetch.snapshots import publish_snapshot
from eii_custodian.publicdata.gate_report import CONFIRMATION_TASKS
from eii_custodian.release import producer


def dump(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(cache: Path) -> dict[str, Any]:
    """Only invented bytes, using the existing fetcher's receipt archive shape."""
    body = b'[{"period":"2026","value":"25.00"}]'
    receipt = dict(
        source_id="INVENTED-source",
        key="INVENTED-source",
        kind="portal_dataset",
        title_en="INVENTED-credit-series",
        publisher="INVENTED-publisher",
        fetch_url="https://invented.invalid/credit",
        licence_id="INVENTED-licence",
        licence_basis="dataset",
        retrieved_utc="2026-01-02T00:00:00Z",
        public_splits=[],
        commit_allowed=False,
        switched_off=False,
    )
    snapshot = publish_snapshot(cache / "INVENTED-source", "json", body, receipt)
    source = dict(
        format="sidecar",
        receipt=dict(
            path=snapshot.receipt_path.relative_to(cache).as_posix(),
            sha256=hashlib.sha256(snapshot.receipt_path.read_bytes()).hexdigest(),
        ),
        body=dict(
            path=snapshot.path.relative_to(cache).as_posix(),
            sha256=snapshot.sha256,
        ),
    )
    dump(
        cache / "assembly/gis_property_singles.json",
        dict(
            method="public-assembly.gis_property_singles",
            method_version="1",
            source_chain={
                "INVENTED-source": dict(snapshot.sidecar),
            },
            table_sources={"pub_bank_credit": ["INVENTED-source"]},
            tables={
                "pub_bank_credit": [dict(period="2026", value="25.00")],
            },
        ),
    )
    dump(
        cache / "assembly/final_audit.json",
        dict(
            completeness=[dict(state="in use")],
            terms=[dict(own_words_state="pending")],
            oi03=dict(state="recorded"),
            confirmations=[
                dict(task=task, state="recorded") for task in CONFIRMATION_TASKS
            ],
            regressions=dict(missing=[], mismatch=""),
        ),
    )
    spec = dict(
        version=1,
        scalars=dict(fixture._scalars(), code_version="cd" * 20),
        sources={"INVENTED-source": source},
        tables=[
            dict(
                name="pub_bank_credit",
                phase="gis_property_singles",
                columns=[
                    dict(name="period", logical_type="string", nullable=False),
                    dict(name="value", logical_type="decimal(18,2)", nullable=False),
                ],
                source_keys=["INVENTED-source"],
            )
        ],
        artefacts=[],
    )
    dump(cache / "review/release_spec.json", spec)
    return spec


def approve(cache: Path) -> dict[str, Any]:
    candidate = producer.prepare(cache)
    review = dict(
        verdict="APPROVED",
        builder="INVENTED-builder",
        reviewer="INVENTED-other-maker",
        code_version=candidate["scalars"]["code_version"],
        input_sha256=hashlib.sha256(canonical_json(candidate).encode()).hexdigest(),
    )
    dump(cache / "review/release_approval.json", review)
    return candidate
