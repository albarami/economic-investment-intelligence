"""Explicit verified snapshot selection and streaming release assembly seams.

build-release remains a placeholder; no ordinary release requires this root.
"""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from eii_custodian.publicdata.fetch.snapshots import SnapshotError

from .snapshot_archive import (
    Selection,
    _immutable,
    canonical,
    digest,
    read_checked,
    verify_selection,
)
from .snapshot_policy import (
    GENERATOR,
    SERVICES,
    SnapshotRefusal,
    configured_root,
    safe_child,
)
from .snapshot_scheme import read_scheme


def reviewed_inputs(
    environ: Mapping[str, str],
) -> tuple[Path, tuple[Selection, ...], tuple[tuple[Path, str], ...]]:
    """Read only an explicitly selected complete all-date manifest, never latest."""
    root = configured_root(environ)
    try:
        selected = json.loads(safe_child(root, "release-selection.json").read_bytes())
        if (
            set(selected) != {"manifest_sha256"}
            or re.fullmatch(r"[a-f0-9]{64}", selected["manifest_sha256"]) is None
        ):
            raise SnapshotRefusal("release_selection_invalid")
        manifest = read_checked(
            safe_child(root, "all-dates"), selected["manifest_sha256"]
        )
        body = json.loads(manifest.body)
        if (
            set(body)
            != {"version", "dates", "complete", "boundary_sha256", "boundary_source"}
            or body.get("complete") is not True
            or body.get("version") != GENERATOR
            or set(body.get("dates", {})) != set(SERVICES)
        ):
            raise SnapshotRefusal("release_selection_incomplete")
        selections = []
        for date in SERVICES:
            levels = body["dates"][date]
            if (
                not isinstance(levels, dict)
                or "10" not in levels
                or any(key not in {str(n) for n in range(11)} for key in levels)
            ):
                raise SnapshotRefusal("release_selection_incomplete")
            for level in sorted(int(key) for key in levels):
                identity = levels[str(level)]
                selection = verify_selection(
                    safe_child(root, f"{date}/level-{level:02d}"), identity
                )
                if selection.date != date:
                    raise SnapshotRefusal("release_selection_identity")
                enumeration = json.loads(
                    read_checked(
                        safe_child(root, f"{date}/level-{level:02d}/completion"),
                        identity,
                    ).body
                )["enumeration"]
                if (
                    set(enumeration.get("inputs", {})) != {"metadata", "boundary"}
                    or enumeration["level"] != level
                    or enumeration["boundary_sha256"] != body["boundary_sha256"]
                ):
                    raise SnapshotRefusal("release_selection_identity")
                metadata = read_checked(
                    safe_child(root, f"{date}/level-{level:02d}/inputs/metadata"),
                    enumeration["metadata_sha256"],
                )
                if set(levels) != {str(n) for n in read_scheme(metadata.body).levels}:
                    raise SnapshotRefusal("release_selection_incomplete")
                selections.append(selection)
        boundary = read_checked(
            safe_child(root, "boundary-source"), body["boundary_source"]
        )
        if boundary.sha256 != body["boundary_sha256"]:
            raise SnapshotRefusal("release_selection_identity")
        boundary_files = (
            (boundary.path, boundary.sha256),
            (boundary.receipt_path, digest(boundary.receipt_path.read_bytes())),
        )
        selections[0] = replace(
            selections[0], files=selections[0].files + boundary_files
        )
        # Shared bytes bind once; never the acquisition directory or its mutable indexes.
        files = {sha: path for selection in selections for path, sha in selection.files}
        files[manifest.sha256] = manifest.path
        files[digest(manifest.receipt_path.read_bytes())] = manifest.receipt_path
        return (
            root,
            tuple(selections),
            tuple((path, sha) for sha, path in sorted(files.items())),
        )
    except SnapshotRefusal:
        raise
    except (OSError, ValueError, TypeError, KeyError, SnapshotError):
        raise SnapshotRefusal("release_selection_integrity") from None


def assemble(selections: Sequence[Selection], output: Path) -> str:
    """Carry selected archive objects and credits into release staging, in bounds."""
    from eii_custodian.publicdata.fetch.bounded import file_hash, publish_complete

    output.mkdir(parents=True, exist_ok=True)
    objects = safe_child(output, "objects")
    objects.mkdir(exist_ok=True)
    tiles: dict[str, object] = {}
    sources = []
    for selection in selections:
        for path, sha in selection.files:
            if file_hash(path) != sha:
                raise SnapshotRefusal("release_selection_integrity")
            target = safe_child(
                objects, sha + (".tar" if path.suffix == ".tar" else ".json")
            )
            with tempfile.TemporaryDirectory(prefix=".imagery-", dir=output) as folder:
                staged = Path(folder) / "object"
                shutil.copyfile(path, staged)
                if file_hash(staged) != sha:
                    raise SnapshotRefusal("release_selection_integrity")
                publish_complete(
                    staged,
                    target,
                    lambda reason: (_ for _ in ()).throw(
                        SnapshotRefusal("release_write_failed")
                    ),
                )
        for snapshot in selection.shards:
            # Recheck before parsing; keep one shard in flight, never all imagery bytes.
            if file_hash(snapshot.path) != snapshot.sha256:
                raise SnapshotRefusal("release_selection_integrity")
            with tarfile.open(snapshot.path, "r:") as archive:
                proofs = snapshot.sidecar["members"]
                if not isinstance(proofs, list):
                    raise SnapshotRefusal("release_selection_integrity")
                for item, proof in zip(archive.getmembers(), proofs, strict=True):
                    key = selection.date + "/" + item.name.removesuffix(".jpg")
                    if (
                        key in tiles
                        or not isinstance(proof, dict)
                        or item.name != proof.get("name")
                    ):
                        raise SnapshotRefusal("release_selection_integrity")
                    tiles[key] = {
                        "object_sha256": snapshot.sha256,
                        "offset": item.offset_data,
                        "bytes": item.size,
                        "member_sha256": proof["sha256"],
                    }
            sources.append(
                {
                    name: snapshot.sidecar[name]
                    for name in (
                        "publisher",
                        "source_id",
                        "url",
                        "licence_basis",
                        "decision_record",
                        "terms_words",
                        "terms_read_on",
                        "retrieved_utc",
                        "imagery_date",
                        "metadata_sha256",
                        "boundary_sha256",
                        "enumeration_sha256",
                        "generator_version",
                    )
                }
            )
    if not tiles:
        raise SnapshotRefusal("release_selection_empty")
    body = canonical(
        {
            "version": GENERATOR,
            "tiles": tiles,
            "sources": sources,
            "coverage": "selected_complete_manifests",
            "numerical_evidence": False,
        }
    )
    identity = digest(body)
    _immutable(safe_child(output, identity + ".json"), body)
    return identity


def inside_selections(selections: Sequence[Selection]) -> tuple[Selection, ...]:
    """Use only individual read-only sandbox destinations after host verification."""
    result = []
    for selection in selections:
        mapped = {
            path: Path("/imagery")
            / (sha + (".tar" if path.suffix == ".tar" else ".json"))
            for path, sha in selection.files
        }
        shards = tuple(
            replace(
                snap, path=mapped[snap.path], receipt_path=mapped[snap.receipt_path]
            )
            for snap in selection.shards
        )
        result.append(
            replace(
                selection,
                files=tuple((mapped[path], sha) for path, sha in selection.files),
                shards=shards,
            )
        )
    return tuple(result)
