"""Per-link acquisition receipts, independent of shape and comparison code.

Only state.json is mutable. Each acquisition has a fresh immutable archive;
invalid old bytes/receipts are retained, never repaired or overwritten.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from .award_checks import AwardError
from .page_html import ShapeError
from .page_schema import json_body
from .receipts import sha256_hex, sidecar_for
from .registry import Entry
from .snapshots import SnapshotError, publish_snapshot, read_snapshot
from .transport import Response

TRANSPORT_VERSION = "awards.https_proof@v1"


def _hash(value: object) -> str:
    return sha256_hex(json.dumps(value, sort_keys=True).encode())


def verify_legacy_proofs(cache: Path, entry: Entry) -> None:
    """Existing archive trust guards also cover pre-store proof objects."""
    directory = cache / entry.key / "proofs"
    for index in sorted((directory / "index").glob("*.json")):
        snapshot = read_snapshot(directory, index.stem)
        if (
            snapshot.sidecar.get("source_id") != entry.source_id
            or snapshot.sidecar.get("key") != entry.key
        ):
            raise SnapshotError("snapshot_conflict")


@dataclass
class ProofStore:
    root: Path
    entry: Entry
    declaration: Mapping[str, Any]
    stamp: str
    clock: Callable[[], str] | None = None

    def folder(self, url: str) -> Path:
        # Shape, columns, intake, pool width and comparison never enter identity.
        identity = _hash(
            {
                "transport": TRANSPORT_VERSION,
                "version": self.declaration.get("version", 1),
                "pins": self.declaration.get("pins", self.declaration.get("pin")),
                "max_bytes": self.declaration.get("max_bytes"),
                "url": url,
            }
        )
        folder = self.root / self.entry.key / "proof_store" / identity
        if not folder.resolve().is_relative_to(self.root.resolve()) or any(
            p.is_symlink() for p in (folder, *folder.parents) if p != self.root.parent
        ):
            raise SnapshotError("snapshot_path_invalid")
        return folder

    def load(self, url: str) -> bytes | None:
        folder = self.folder(url)
        if (folder / "state.json").is_symlink():
            raise SnapshotError("snapshot_path_invalid")
        try:
            state = json_body((folder / "state.json").read_bytes())
        except (OSError, ValueError):
            return None
        if not isinstance(state, dict) or set(state) != {"archive", "identity"}:
            return None
        if not isinstance(state["identity"], str):
            return None
        if (
            not isinstance(state["archive"], str)
            or re.fullmatch(r"[a-f0-9]{32}", state["archive"]) is None
        ):
            raise SnapshotError("snapshot_path_invalid")
        directory = folder / state["archive"]
        if directory.is_symlink() or any(p.is_symlink() for p in directory.rglob("*")):
            raise SnapshotError("snapshot_path_invalid")
        try:
            snapshot = read_snapshot(directory, state["identity"])
            side = snapshot.sidecar
            if (
                side.get("proof_url") != url
                or side.get("transport") != TRANSPORT_VERSION
                or side.get("source_id") != self.entry.source_id
                or side.get("key") != self.entry.key
                or not isinstance(side.get("upstream_sha256"), str)
                or re.fullmatch(r"[a-f0-9]{64}", str(side["upstream_sha256"])) is None
            ):
                return None
            return snapshot.body
        except SnapshotError as exc:
            if str(exc) not in {
                "snapshot_missing",
                "snapshot_hash_mismatch",
                "snapshot_index_invalid",
            }:
                raise
            return None

    def save(self, url: str, response: Response) -> bytes:
        body = response.body
        version_two = self.declaration.get("version") == 2
        if version_two:
            from .page_acquire import _html_without_form_secrets

            try:
                body = _html_without_form_secrets(body)
            except ShapeError:
                raise SnapshotError("proof_representation_refused") from None
        side = sidecar_for(
            self.entry,
            digest=sha256_hex(body),
            nbytes=len(body),
            fetch_url=response.final_url,
            fetch_host=self.entry.fetch_host,
            retrieved_utc=self.clock() if self.clock is not None else self.stamp,
            publisher=self.entry.publisher,
            source_modified="",
            row_count=None,
            terms_sha256="",
        )
        side.update(
            proof_url=url,
            transport=TRANSPORT_VERSION,
            upstream_sha256=sha256_hex(response.body),
            representation="form_secret_removed" if version_two else "original",
        )
        try:
            folder = self.folder(url)
            archive = uuid4().hex
            snapshot = publish_snapshot(folder / archive, "html", body, side)
            # Publish selection only after the immutable receipt and body verify.
            with NamedTemporaryFile(dir=folder, delete=False) as handle:
                pending = Path(handle.name)
                handle.write(
                    json.dumps(
                        {"archive": archive, "identity": snapshot.sha256}
                    ).encode()
                )
            pending.replace(folder / "state.json")
        except OSError:
            raise SnapshotError("snapshot_write_failed") from None

        return body

    def body(self, url: str, *, replay: bool) -> bytes | None:
        body = self.load(url)
        if body is None and replay:
            raise AwardError("proof_store_missing")
        return body
