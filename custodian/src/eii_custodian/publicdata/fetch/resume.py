"""Durable fetch progress, scoped to one interrupted seeded build.

Version 2 binds each reuse-capable entry to a per-entry fingerprint of the
code and inputs that produced it, replacing the whole-checkout HEAD gate:
only receipt- or page-meta-proven inputs with a matching fingerprint can be
reused, and any doubt refetches. The journal is never an assembly result or
a substitute for an existing receipt's own hash.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from eii_custodian.publicdata.busyness.security import assert_clean

from .bounded import file_hash
from .fingerprint import (
    CodeRoots,
    FingerprintUnavailable,
    RunScan,
    _canonical,
    busyness_inputs,
    default_roots,
    scan_run,
)
from .registry import Entry
from .snapshots import read_snapshot, utc

RUN_NAME = "build-run.json"
JOURNAL_VERSION = 2


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
    clock: Callable[[], str] = field(default=lambda: "", repr=False)
    scan: RunScan | None = field(default=None, repr=False)

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
        clock: Callable[[], str] | None = None,
        roots: CodeRoots | None = None,
        large: bool = False,
    ) -> RunRecord:
        head = repository_head()
        path = cache / RUN_NAME
        if resume:
            if not path.is_file():
                raise ResumeError("resume_record_missing")
            try:
                row = _object(path)
            except (OSError, ValueError, TypeError):
                raise ResumeError("resume_record_invalid") from None
            if row.get("version") == 1:
                # A version-1 journal binds reuse to a whole-checkout HEAD that
                # is no longer the rule. A different recorded head keeps its
                # old refusal name; any other version-1 record simply cannot
                # prove per-entry reuse and is refetched.
                old_head = row.get("head")
                if (
                    isinstance(old_head, str)
                    and re.fullmatch(r"[a-f0-9]{40}", old_head) is not None
                    and old_head != head
                ):
                    raise ResumeError("resume_head_mismatch")
                raise ResumeError("resume_record_unproven")
            try:
                if (
                    row.get("version") != JOURNAL_VERSION
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
            try:
                scan = scan_run(
                    entries, roots or default_roots(), large=large, cache=cache
                )
            except (FingerprintUnavailable, OSError):
                # Any doubt refetches (L-1379): an unavailable proof never
                # refuses a resume build; it leaves every item marked
                # resume_fingerprint_unavailable and refetched.
                scan = None
            return cls(
                cache,
                row,
                True,
                environ=environ or {},
                clock=clock or (lambda: ""),
                scan=scan,
            )
        utc(started)
        try:
            scan = scan_run(entries, roots or default_roots(), large=large, cache=cache)
        except (FingerprintUnavailable, OSError):
            # Same ruling for an ordinary run: the build fetches with no
            # fingerprint and every fetched item is marked unavailable.
            scan = None
        run = cls(
            cache,
            {
                "version": JOURNAL_VERSION,
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
            clock=clock or (lambda: ""),
            scan=scan,
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
        """Bind the fetched result to receipts and its code/input fingerprint."""
        item: dict[str, Any] = {"completed": True}
        fingerprint, refusal = self._fingerprint(entry)
        if refusal is not None:
            item["reuse_unavailable"] = refusal
        elif entry.kind == "paged_cards":
            try:
                item.update(fetch=state, page_meta=self._page_meta(entry, state))
            except (OSError, ValueError, KeyError, TypeError):
                item["reuse_unavailable"] = "page_receipt_unproven"
            else:
                item["fingerprint"] = fingerprint
        else:
            self._fetch_proofs(entry, item, state, fingerprint)
        self.row["entries"][entry.key] = item
        self.write()

    def _fetch_proofs(
        self,
        entry: Entry,
        item: dict[str, Any],
        state: dict[str, object],
        fingerprint: dict[str, Any] | None,
    ) -> None:
        """Bind the fetched result to immutable primary and auxiliary receipts."""
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
                fetch=state,
                proofs=proofs,
                publisher=primary.sidecar["publisher"],
                fingerprint=fingerprint,
            )
        except (OSError, ValueError, KeyError, TypeError):
            # No proof means no reuse. Fetch success itself remains recorded;
            # an adapter with a different receipt layout must refetch.
            item["reuse_unavailable"] = "receipt_unproven"

    def _fingerprint(self, entry: Entry) -> tuple[dict[str, Any] | None, str | None]:
        """The begin-time fingerprint, re-proved at fetched() before storing."""
        scan = self.scan
        if scan is None:
            return None, "resume_fingerprint_unavailable"
        record = scan.records.get(entry.key)
        if record is None:
            return None, "resume_fingerprint_unavailable"
        if not scan.closure_intact() or scan.unexpected_loaded():
            return None, "resume_fingerprint_unproven"
        if entry.kind == "besttime" and record.get("busyness") != busyness_inputs(
            self.cache, "production"
        ):
            return None, "resume_fingerprint_unproven"
        if entry.source_id == "tenders_pub":
            triple = self._intake_triple(entry)
            if triple is None:
                return None, "resume_fingerprint_unproven"
            record = {**record, "intake": triple}
        return record, None

    def _intake_triple(self, entry: Entry) -> list[Any] | None:
        """The intake triple stored in the awarded list's own receipts."""
        values = []
        for language in ("en", "ar"):
            receipt = self._local(f"{entry.key}/awarded/{language}.receipt.json", entry)
            try:
                reading = _object(receipt)
            except (OSError, ValueError, TypeError):
                return None
            values.append(
                [
                    reading.get("award_cutoff"),
                    reading.get("cutoff_reason"),
                    reading.get("workbook_sha256"),
                ]
            )
        return values[0] if values[0] == values[1] else None

    def _fingerprint_matches(self, entry: Entry, item: dict[str, Any]) -> bool:
        """The stored fingerprint must equal this run's begin-time record."""
        if self.scan is None:
            return False
        stored = item.get("fingerprint")
        if not isinstance(stored, dict):
            return False
        current = self.scan.records.get(entry.key)
        if current is None:
            return False
        if entry.kind == "besttime" and current.get("busyness") != busyness_inputs(
            self.cache, "production"
        ):
            return False
        if entry.source_id == "tenders_pub":
            try:
                from .awards import intake_cutoff

                cutoff, reason, workbook = intake_cutoff(self.cache, self.clock())
            except Exception:
                return False
            current = {**current, "intake": [cutoff, reason, workbook]}
        return _canonical(stored) == _canonical(current)

    def reuse(self, entry: Entry, lines: list[str]) -> dict[str, Any] | None:
        """Rehash all selected input bytes; stale or unproven input is refetched."""
        if not self.resuming:
            return None
        item = self.row["entries"][entry.key]
        if not item["completed"]:
            return None
        if not self._fingerprint_matches(entry, item):
            self._invalidate(entry, lines)
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
            if utc(state["retrieved_utc"]) < started:
                raise ValueError("lineage_changed")
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
                if position == 0 and snapshot.sha256 != state["digest"]:
                    raise ValueError("lineage_changed")
                # Equal-byte publication keeps the original primary receipt.
                # Only this run's proven fetch of that digest admits its age;
                # auxiliary receipts have no such per-fetch digest proof.
                kept_receipt = position == 0 and utc(side["retrieved_utc"]) < started
                if (
                    side["publisher"] != proof["publisher"]
                    or side["retrieved_utc"] != proof["retrieved_utc"]
                    or (utc(side["retrieved_utc"]) < started and not kept_receipt)
                ):
                    raise ValueError("lineage_changed")
                for name, digest in proof["files"].items():
                    path = self._local(name, entry)
                    if (
                        path.stat().st_mtime < started.timestamp() and not kept_receipt
                    ) or file_hash(path) != digest:
                        raise ValueError("stored_bytes_changed")
            primary = read_snapshot(
                self._local(proofs[0]["directory"], entry), state["digest"]
            )
            if (
                primary.sidecar["source_id"] != entry.source_id
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
        from .awards import intake_cutoff

        manifest = self.cache / "intake/awards_owner_scrape/intake.json"
        return {
            "publisher": entry.publisher,
            "retrieved_utc": state["retrieved_utc"],
            "sha256": state["digest"],
            "intake": {
                "manifest_sha256": file_hash(manifest) if manifest.is_file() else None,
                "cutoff": list(
                    intake_cutoff(self.cache, cast(str, state["retrieved_utc"]))
                ),
            },
            "files": {
                p.relative_to(self.cache).as_posix(): file_hash(p) for p in paths
            },
        }

    def _reuse_pages(
        self, entry: Entry, item: dict[str, Any], lines: list[str]
    ) -> dict[str, Any] | None:
        try:
            state = self.proven_pages(entry, item)
        except (OSError, ValueError, KeyError, TypeError):
            self._invalidate(entry, lines)
            return None
        saved = item["page_meta"]
        lines.append(
            f"REUSE {entry.key} interrupted_start={self.row['started_utc']} "
            f"publisher={saved['publisher']} retrieved_utc={saved['retrieved_utc']} "
            f"sha256={saved['sha256']}"
        )
        return state

    def proven_pages(
        self, entry: Entry, item: dict[str, Any], *, legacy_intake: bool = False
    ) -> dict[str, Any]:
        """Check a completed page set without mutating any journal."""
        state = item["fetch"]
        saved = item["page_meta"]
        if not self._valid_state(state) or not isinstance(saved, dict):
            raise ValueError("page_meta_changed")
        started = utc(self.row["started_utc"])
        current = self._page_meta(entry, state)
        if legacy_intake and "intake" not in saved:
            # Earlier journals had page proofs but no intake fingerprint. A
            # handoff checks the archive's readings against the current main
            # intake separately; ordinary resume never gets this exception.
            saved = {**saved, "intake": current["intake"]}
        if (
            state["fetch_host"] != entry.fetch_host
            or saved.get("publisher") != entry.publisher
            or utc(saved.get("retrieved_utc")) < started
            or state.get("retrieved_utc") != saved["retrieved_utc"]
            or state.get("digest") != saved["sha256"]
            or current != saved
        ):
            raise ValueError("page_meta_changed")
        for name in saved["files"]:
            if self._local(name, entry).stat().st_mtime < started.timestamp():
                raise ValueError("page_file_old")
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
