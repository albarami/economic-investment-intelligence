"""Durable fetch progress, scoped to one interrupted seeded build and checkout.

Only receipt- or page-meta-proven inputs can be reused. The journal is never
an assembly result or a substitute for an existing receipt's own hash.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from eii_custodian.publicdata.busyness.security import assert_clean

from .bounded import file_hash
from .registry import Entry
from .snapshots import read_snapshot, utc

RUN_NAME = "build-run.json"


class ResumeError(ValueError):
    """A closed refusal name; never upstream text or a private path."""


def repository_head(root: Path | None = None) -> str:
    """Read this code checkout's HEAD without a child inheriting credentials.

    Support detached heads, ordinary clones and linked worktrees, including
    packed refs. Only git's HEAD/ref metadata is read, never its configuration.
    """
    metadata = (
        root if root is not None else Path(__file__).resolve().parents[5]
    ) / ".git"
    try:
        if metadata.is_file():
            pointer = metadata.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir: "):
                raise ResumeError("resume_head_unavailable")
            metadata = (metadata.parent / pointer.removeprefix("gitdir: ")).resolve()
        head = (metadata / "HEAD").read_text(encoding="ascii").strip()
        if head.startswith("ref: "):
            ref = head.removeprefix("ref: ")
            if not ref.startswith("refs/") or ".." in ref.split("/"):
                raise ResumeError("resume_head_unavailable")
            common_file = metadata / "commondir"
            common = (
                (metadata / common_file.read_text(encoding="utf-8").strip()).resolve()
                if common_file.is_file()
                else metadata
            )
            loose = common / ref
            if loose.is_file():
                head = loose.read_text(encoding="ascii").strip()
            else:
                head = ""
                for line in (
                    (common / "packed-refs").read_text(encoding="ascii").splitlines()
                ):
                    parts = line.split(" ")
                    if len(parts) == 2 and parts[1] == ref:
                        head = parts[0]
                        break
    except (OSError, UnicodeError):
        raise ResumeError("resume_head_unavailable") from None
    if re.fullmatch(r"[a-f0-9]{40}", head) is None:
        raise ResumeError("resume_head_unavailable")
    return head


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("object_required")
    return value


@dataclass
class RunRecord:
    cache: Path
    row: dict[str, Any]
    resuming: bool
    fetch_lines: list[str] = field(default_factory=list, repr=False)
    environ: Mapping[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def begin(
        cls,
        cache: Path,
        entries: Sequence[Entry],
        seed: int,
        started: str,
        *,
        resume: bool,
        environ: Mapping[str, str] | None = None,
    ) -> RunRecord:
        head = repository_head()
        path = cache / RUN_NAME
        if resume:
            if not path.is_file():
                raise ResumeError("resume_record_missing")
            try:
                row = _object(path)
                if (
                    row.get("version") != 1
                    or not isinstance(row.get("entries"), dict)
                    or type(row.get("seed")) is not int
                    or not isinstance(row.get("head"), str)
                    or re.fullmatch(r"[a-f0-9]{40}", row["head"]) is None
                    or row.get("state") not in {"interrupted", "complete"}
                ):
                    raise ValueError("invalid_record")
                utc(row.get("started_utc"))
                if set(row["entries"]) != {entry.key for entry in entries}:
                    raise ValueError("changed_entries")
                if any(
                    not isinstance(item, dict)
                    or type(item.get("completed")) is not bool
                    for item in row["entries"].values()
                ):
                    raise ValueError("invalid_entries")
            except (OSError, ValueError, TypeError):
                raise ResumeError("resume_record_invalid") from None
            if row["state"] != "interrupted":
                raise ResumeError("resume_not_interrupted")
            if row["seed"] != seed:
                raise ResumeError("resume_seed_mismatch")
            if row["head"] != head:
                raise ResumeError("resume_head_mismatch")
            return cls(cache, row, True, environ=environ or {})
        utc(started)
        run = cls(
            cache,
            {
                "version": 1,
                "started_utc": started,
                "seed": seed,
                "head": head,
                # Remains interrupted on a structured failure, exception or
                # killed process. Only successful full assembly completes it.
                "state": "interrupted",
                "entries": {e.key: {"completed": False} for e in entries},
            },
            False,
            environ=environ or {},
        )
        run.write()
        return run

    def write(self) -> None:
        """Flush before atomic replacement, then flush the directory entry."""
        assert_clean(self.environ, self.row)
        self.cache.mkdir(parents=True, exist_ok=True)
        partial = self.cache / ".build-run.json.partial"
        with partial.open("w", encoding="utf-8") as handle:
            json.dump(self.row, handle, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, self.cache / RUN_NAME)
        descriptor = os.open(self.cache, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def finish(self) -> None:
        self.row["state"] = "complete"
        self.write()

    def note(self, entry: Entry) -> None:
        """Record completion without pretending unsupported layouts have proof."""
        self.row["entries"][entry.key] = {"completed": True}
        self.write()

    def fetched(self, entry: Entry, state: dict[str, object]) -> None:
        """Bind the fetched result to immutable primary and auxiliary receipts."""
        item: dict[str, Any] = {"completed": True}
        if entry.kind == "paged_cards":
            try:
                item.update(fetch=state, page_meta=self._page_meta(entry, state))
            except (OSError, ValueError, KeyError, TypeError):
                item["reuse_unavailable"] = "page_receipt_unproven"
            self.row["entries"][entry.key] = item
            self.write()
            return
        try:
            directory = self._local(entry.key, entry)
            if entry.key in {"places_ovt", "bldg_ovt"}:
                directory /= "listing"
            digest = state["digest"]
            if not isinstance(digest, str):
                raise ValueError("digest_required")
            primary = read_snapshot(directory, digest)
            snapshots = [(directory, digest)]
            for index in sorted(
                (self.cache / entry.key / "inputs" / "index").glob("*.json")
            ):
                snapshot = read_snapshot(index.parent.parent, index.stem)
                snapshots.append((index.parent.parent, index.stem))
            proofs = []
            for folder, identity in snapshots:
                snapshot = read_snapshot(folder, identity)
                paths = [
                    folder / "index" / f"{identity}.json",
                    snapshot.receipt_path,
                    snapshot.path,
                ]
                # The ordinary reader also publishes compatibility aliases.
                # Verify them independently, since downstream readers may use
                # them. Their hashes are bound by the primary index/receipt.
                if folder == directory:
                    paths.extend(
                        (
                            folder / f"{identity}.{entry.extension}",
                            folder / f"{identity}.meta.json",
                        )
                    )
                proofs.append(
                    {
                        "directory": folder.relative_to(self.cache).as_posix(),
                        "identity": identity,
                        "publisher": snapshot.sidecar["publisher"],
                        "retrieved_utc": snapshot.sidecar["retrieved_utc"],
                        "files": {
                            p.relative_to(self.cache).as_posix(): file_hash(p)
                            for p in paths
                        },
                    }
                )
            item.update(
                fetch=state, proofs=proofs, publisher=primary.sidecar["publisher"]
            )
        except (OSError, ValueError, KeyError, TypeError):
            # No proof means no reuse. Fetch success itself remains recorded;
            # an adapter with a different receipt layout must refetch.
            item["reuse_unavailable"] = "receipt_unproven"
        self.row["entries"][entry.key] = item
        self.write()

    def reuse(self, entry: Entry, lines: list[str]) -> dict[str, Any] | None:
        """Rehash all selected input bytes; stale or unproven input is refetched."""
        if not self.resuming:
            return None
        item = self.row["entries"][entry.key]
        if not item["completed"]:
            return None
        if entry.kind == "paged_cards":
            return self._reuse_pages(entry, item, lines)
        try:
            state = item["fetch"]
            proofs = item["proofs"]
            if (
                not self._valid_state(state)
                or not isinstance(proofs, list)
                or not proofs
            ):
                raise ValueError("proof_required")
            started = utc(self.row["started_utc"])
            for position, proof in enumerate(proofs):
                if (
                    not isinstance(proof, dict)
                    or not isinstance(proof.get("files"), dict)
                    or not proof["files"]
                ):
                    raise ValueError("proof_required")
                folder = self._local(proof["directory"], entry)
                snapshot = read_snapshot(folder, proof["identity"])
                required = {
                    folder / "index" / f"{proof['identity']}.json",
                    snapshot.receipt_path,
                    snapshot.path,
                }
                if position == 0:
                    required.update(
                        {
                            folder / f"{proof['identity']}.{entry.extension}",
                            folder / f"{proof['identity']}.meta.json",
                        }
                    )
                if set(proof["files"]) != {
                    p.relative_to(self.cache).as_posix() for p in required
                }:
                    raise ValueError("proof_files_missing")
                side = snapshot.sidecar
                if (
                    side["publisher"] != proof["publisher"]
                    or side["retrieved_utc"] != proof["retrieved_utc"]
                    or utc(side["retrieved_utc"]) < started
                ):
                    raise ValueError("lineage_changed")
                for name, digest in proof["files"].items():
                    path = self._local(name, entry)
                    if (
                        path.stat().st_mtime < started.timestamp()
                        or file_hash(path) != digest
                    ):
                        raise ValueError("stored_bytes_changed")
            primary = read_snapshot(
                self._local(proofs[0]["directory"], entry), state["digest"]
            )
            if (
                primary.sidecar["source_id"] != entry.source_id
                or primary.sidecar["retrieved_utc"] != state["retrieved_utc"]
                or primary.sidecar["publisher"] != item["publisher"]
                or primary.sidecar["fetch_host"] != state["fetch_host"]
            ):
                raise ValueError("lineage_changed")
        except (OSError, ValueError, KeyError, TypeError):
            # Invalidate before refetch so another interruption cannot restore
            # an earlier completion marker after a partially failed fetch.
            self._invalidate(entry, lines)
            return None
        lines.append(
            f"REUSE {entry.key} interrupted_start={self.row['started_utc']} "
            f"publisher={primary.sidecar['publisher']} "
            f"retrieved_utc={primary.sidecar['retrieved_utc']} sha256={primary.sha256}"
        )
        return cast(dict[str, Any], state)

    @staticmethod
    def _valid_state(state: object) -> bool:
        if not isinstance(state, dict):
            return False
        fields = {
            "digest",
            "fetch_host",
            "retrieved_utc",
            "terms_sha256",
            "terms_unread",
            "licence_pending",
            "licence_unstated",
        }
        return (
            set(state) == fields
            and all(
                isinstance(state[name], str) for name in fields - {"licence_unstated"}
            )
            and type(state["licence_unstated"]) is bool
        )

    def _page_meta(self, entry: Entry, state: dict[str, object]) -> dict[str, object]:
        """Record each mutable portal page against its list's original receipt.

        Unlike standard snapshots, this adapter has list receipts without byte
        hashes. Its per-page meta hashes therefore live in the durable run
        record, with the publisher and retrieval time of the completed fetch.
        Neither the page nor its original list receipt is rewritten.
        """
        from eii_custodian.publicdata.singles.tenders import LIST_PATHS

        paths = []
        for name, _ in LIST_PATHS:
            for language in ("en", "ar"):
                prefix = f"{entry.key}/{name}/{language}"
                receipt = self._local(prefix + ".receipt.json", entry)
                reading = _object(receipt)
                count = reading.get("pages_read", reading.get("first_stated_last"))
                if (
                    reading.get("list_name") != name
                    or reading.get("language") != language
                    or type(count) is not int
                    or count <= 0
                ):
                    raise ValueError("page_receipt_invalid")
                paths.append(receipt)
                paths.extend(
                    self._local(f"{prefix}/{number}.html", entry)
                    for number in range(1, count + 1)
                )
        html = sorted(
            path
            for name, _ in LIST_PATHS
            for language in ("en", "ar")
            for path in self._local(f"{entry.key}/{name}/{language}", entry).glob(
                "*.html"
            )
        )
        if {p for p in paths if p.suffix == ".html"} != set(html):
            raise ValueError("page_inventory_invalid")
        return {
            "publisher": entry.publisher,
            "retrieved_utc": state["retrieved_utc"],
            "sha256": state["digest"],
            "files": {
                p.relative_to(self.cache).as_posix(): file_hash(p) for p in paths
            },
        }

    def _reuse_pages(
        self, entry: Entry, item: dict[str, Any], lines: list[str]
    ) -> dict[str, Any] | None:
        try:
            state = item["fetch"]
            saved = item["page_meta"]
            started = utc(self.row["started_utc"])
            if (
                not self._valid_state(state)
                or not isinstance(saved, dict)
                or state["fetch_host"] != entry.fetch_host
                or saved.get("publisher") != entry.publisher
                or utc(saved.get("retrieved_utc")) < started
                or state.get("retrieved_utc") != saved["retrieved_utc"]
                or state.get("digest") != saved["sha256"]
            ):
                raise ValueError("page_meta_invalid")
            # Compute the closed inventory from the receipts again, and hash
            # every page and receipt, including any added or missing page.
            current = self._page_meta(entry, state)
            if current != saved:
                raise ValueError("page_meta_changed")
            for name in saved["files"]:
                if self._local(name, entry).stat().st_mtime < started.timestamp():
                    raise ValueError("page_file_old")
        except (OSError, ValueError, KeyError, TypeError):
            self._invalidate(entry, lines)
            return None
        lines.append(
            f"REUSE {entry.key} interrupted_start={self.row['started_utc']} "
            f"publisher={saved['publisher']} retrieved_utc={saved['retrieved_utc']} "
            f"sha256={saved['sha256']}"
        )
        return cast(dict[str, Any], state)

    def _invalidate(self, entry: Entry, lines: list[str]) -> None:
        self.row["entries"][entry.key] = {"completed": False}
        self.write()
        lines.append(f"REFETCH {entry.key} resume_input_unproven")

    def _local(self, name: str, entry: Entry) -> Path:
        root = (self.cache / entry.key).resolve()
        path = self.cache / name
        if not root.is_relative_to(
            self.cache.resolve()
        ) or not path.resolve().is_relative_to(root):
            raise ValueError("resume_path_invalid")
        return path
