"""Closed Public-chain receipts shared by acquisition, resume and selection."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date as calendar_date
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.snapshots import Snapshot, publish_snapshot, utc

from .snapshot_policy import BASE, GENERATOR, SERVICES, SnapshotRefusal, service_url

COMMON = frozenset(
    {
        "source_id",
        "key",
        "publisher",
        "url",
        "licence_basis",
        "licence_id",
        "decision_record",
        "terms_words",
        "terms_read_on",
        "retrieved_utc",
        "generator_version",
        "sha256",
        "bytes",
        "kind",
        "imagery_date",
    }
)
EXTRA = {
    "metadata": frozenset(),
    "boundary": frozenset({"upstream_sha256", "method_version"}),
    "boundary-source": frozenset({"upstream_sha256", "method_version"}),
    "completion": frozenset(),
    "all-dates": frozenset(),
    "shard": frozenset(
        {
            "metadata_sha256",
            "boundary_sha256",
            "enumeration_sha256",
            "members",
            "gaps",
            "shard",
        }
    ),
}


def public_chain(kind: str, imagery_date: str, stamp: str) -> dict[str, Any]:
    if kind not in EXTRA or (imagery_date not in SERVICES and kind != "all-dates"):
        raise SnapshotRefusal("receipt_lineage")
    return {
        "source_id": "gis_imagery_history",
        "key": "gis_imagery_history",
        "publisher": "national GIS centre",
        "url": BASE if kind == "all-dates" else service_url(imagery_date),
        "licence_basis": "owner_decision",
        "licence_id": "",
        "decision_record": "0026",
        "terms_words": "terms to be read",
        "terms_read_on": "pending",
        "retrieved_utc": stamp,
        "generator_version": GENERATOR,
        "kind": kind,
        "imagery_date": imagery_date,
    }


def validate_receipt(snapshot: Snapshot, kind: str, imagery_date: str) -> None:
    side: dict[str, Any] = snapshot.sidecar
    try:
        if kind not in EXTRA or set(side) != COMMON | EXTRA[kind]:
            raise SnapshotRefusal("receipt_fields")
        if (
            side["kind"] != kind
            or side["imagery_date"] != imagery_date
            or side["generator_version"] != GENERATOR
            or side["sha256"] != snapshot.sha256
            or type(side["bytes"]) is not int
            or side["bytes"] != snapshot.path.stat().st_size
        ):
            raise SnapshotRefusal("receipt_identity")
        if any(not isinstance(side[key], str) for key in COMMON - {"bytes"}):
            raise SnapshotRefusal("receipt_fields")
        utc(side["retrieved_utc"])
        if side["terms_read_on"] != "pending":
            calendar_date.fromisoformat(side["terms_read_on"])
        if kind in {"boundary", "boundary-source"}:
            if (
                any(
                    not isinstance(side[key], str) or not side[key]
                    for key in (
                        "source_id",
                        "key",
                        "publisher",
                        "url",
                        "terms_words",
                        "method_version",
                    )
                )
                or not approve(side["url"]).ok
                or side["licence_basis"] not in {"dataset", "owner_decision"}
                or (side["licence_basis"] == "dataset" and not side["licence_id"])
                or (
                    side["licence_basis"] == "owner_decision"
                    and side["decision_record"] != "0026"
                )
            ):
                raise SnapshotRefusal("receipt_lineage")
            if kind == "boundary" and (
                imagery_date not in SERVICES
                or side["method_version"] != "gis-boundary-project-v1"
            ):
                raise SnapshotRefusal("receipt_lineage")
        else:
            expected = public_chain(kind, imagery_date, str(side["retrieved_utc"]))
            # A terms reading may be updated, but the recorded source/basis stays closed.
            for key in expected.keys() - {"terms_words", "terms_read_on"}:
                if side[key] != expected[key]:
                    raise SnapshotRefusal("receipt_lineage")
            if not isinstance(side["terms_words"], str) or not side["terms_words"]:
                raise SnapshotRefusal("receipt_lineage")
        if kind in {"boundary", "boundary-source"}:
            if (
                not isinstance(side["upstream_sha256"], str)
                or re.fullmatch(r"[a-f0-9]{64}", side["upstream_sha256"]) is None
                or not isinstance(side["method_version"], str)
                or not side["method_version"]
            ):
                raise SnapshotRefusal("receipt_lineage")
    except SnapshotRefusal:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise SnapshotRefusal("receipt_invalid") from None


def publish_public(
    directory: Path, body: bytes, side: Mapping[str, Any], identity: str
) -> Snapshot:
    """Existing immutable receipts must pass the same schema on resume."""
    from .snapshot_archive import read_checked

    if (directory / "index" / (identity + ".json")).exists():
        validate_receipt(
            read_checked(directory, identity), side["kind"], side["imagery_date"]
        )
    snapshot = publish_snapshot(directory, "json", body, dict(side), identity=identity)
    validate_receipt(snapshot, side["kind"], side["imagery_date"])
    return snapshot
