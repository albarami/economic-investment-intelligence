"""Complete upstream snapshots and paced, obstacle-stopping public access."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

from ..fc_register.acquire import eligible, obstacle
from ..fetch.allowlist import host_of
from ..fetch.receipts import sha256_hex
from ..fetch.snapshots import Snapshot, publish_snapshot, read_snapshot, utc
from ..fetch.transport import Response, Transport, TransportFault
from .contracts import VERSION, Company, WebError, digest, dump, lineage
from .scope import Manifest, company_requests


class Pacer:
    def __init__(
        self,
        sleep: Callable[[float], None],
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.sleep = sleep
        self.monotonic = monotonic
        self.previous: float | None = None

    def wait(self, delay: float) -> None:
        if not math.isfinite(delay) or delay < 2:
            raise WebError("pace_refused")
        if self.previous is not None:
            remaining = self.previous + delay - self.monotonic()
            if remaining > 0:
                self.sleep(remaining)
            if self.monotonic() < self.previous + delay:
                raise WebError("pace_refused")
        self.previous = self.monotonic()


@dataclass(frozen=True)
class Page:
    identity: str
    snapshot: Snapshot

    @property
    def body(self) -> bytes:
        return self.snapshot.body


def _directory(cache: Path, company_key: str) -> Path:
    return cache / "company_web" / "pages" / digest(company_key)


def archive_page(
    cache: Path, company_key: str, response: Response, meta: Mapping[str, Any]
) -> Page:
    lineage(response.body, meta)
    if (
        not response.body_sha256
        or response.body_sha256 != sha256_hex(response.body)
        or response.final_url != meta["fetch_url"]
    ):
        raise WebError("upstream_hash_refused")
    side = dict(meta, company_digest=digest(company_key))
    identity = digest(side)
    snapshot = publish_snapshot(
        _directory(cache, company_key), "html", response.body, side, identity=identity
    )
    return Page(identity, snapshot)


def load_page(cache: Path, company_key: str, identity: str) -> Page:
    snapshot = read_snapshot(_directory(cache, company_key), identity)
    lineage(snapshot.body, snapshot.sidecar)
    if snapshot.sidecar.get("company_digest") != digest(company_key):
        raise WebError("company_binding_refused")
    expected = digest(snapshot.sidecar)
    if expected != identity:
        raise WebError("page_identity_refused")
    return Page(identity, snapshot)


class Access:
    """One serial run; a blocked host is terminal, never retried or bypassed."""

    def __init__(
        self,
        manifest: Manifest,
        transport: Transport,
        cache: Path,
        clock: Callable[[], str],
        pace: Pacer,
    ) -> None:
        self.manifest, self.transport, self.cache, self.clock, self.pace = (
            manifest,
            transport,
            cache,
            clock,
            pace,
        )
        self.checked: dict[str, RobotFileParser | None] = {}
        self.stopped: dict[str, str] = {}
        self.delays: dict[str, float] = {}

    def _get(self, url: str, *, inspect: bool = True) -> Response:
        host = host_of(url)
        if host in self.stopped:
            raise WebError(self.stopped[host])
        delay = max(
            self.manifest.data["access"][host]["delay_seconds"],
            self.delays.get(host, 2),
        )
        self.pace.wait(delay)
        try:
            response = self.transport(url)
        except TransportFault as error:
            # eligible is reused for classification only, never capture/retry.
            if eligible(error.kind, error.status) or error.kind == "http":
                reason = "unavailable"
            elif error.kind in {"credentials", "credential_missing_or_not_accepted"}:
                reason = "obstacle"
            else:
                # Host, integrity, size and every unlisted failure are terminal.
                raise WebError("request_refused") from None
            self.stopped[host] = reason
            raise WebError(reason) from None
        from .scope import allowed

        if any(not allowed(u) for u in (*response.hops, response.final_url)):
            raise WebError("redirect_refused")
        if inspect and obstacle(response.body):
            self.stopped[host] = "obstacle"
            raise WebError("obstacle")
        return response

    def prepare(
        self, company: Company, *, search_url: str = "", page_url: str = ""
    ) -> None:
        if page_url and page_url not in self.manifest.urls(company.key):
            raise WebError("url_refused")
        urls = (
            (search_url,)
            if search_url
            else (page_url,)
            if page_url
            else self.manifest.urls(company.key)
        )
        for host in sorted({host_of(url) for url in urls}):
            if host in self.stopped:
                raise WebError(self.stopped[host])
            if host in self.checked:
                continue
            record = self.manifest.data["access"][host]
            words = {}
            retrieved = self.clock()
            utc(retrieved)
            with company_requests(
                self.manifest,
                company.key,
                search_url=search_url,
                company_name=company.name,
                access_host=host,
            ):
                for role in ("terms", "robots"):
                    url = record[role + "_url"]
                    if not url:
                        words[role] = "none found"
                        continue
                    try:
                        response = self._get(url)
                    except WebError as error:
                        if str(error) != "unavailable" or role == "robots":
                            raise
                        # Unread terms are recorded; never a reuse/licence gate.
                        self.stopped.pop(host, None)
                        words[role] = "unread"
                        continue
                    words[role] = response.body.decode("utf-8", errors="replace")
                    side = {
                        "source_id": "company_web",
                        "key": "company_web/access",
                        "retrieved_utc": retrieved,
                        "sha256": sha256_hex(response.body),
                        "bytes": len(response.body),
                        "fetch_url": response.final_url,
                        "publisher": host,
                        "licence_basis": "owner_decision",
                        "decision_record": "0026",
                        "method": VERSION,
                    }
                    publish_snapshot(
                        self.cache / "company_web" / "access" / digest(host) / role,
                        "txt",
                        response.body,
                        side,
                    )
            robot = None
            if words["robots"] != "none found":
                robot = RobotFileParser()
                robot.parse(words["robots"].splitlines())
                self.delays[host] = float(max(2, robot.crawl_delay("*") or 2))
            body = dump({"host": host, "retrieved_utc": retrieved, **words})
            publish_snapshot(
                self.cache / "company_web" / "access" / digest(host) / "record",
                "json",
                body,
                {
                    "source_id": "company_web",
                    "key": "company_web/access",
                    "retrieved_utc": retrieved,
                },
            )
            self.checked[host] = robot

    def allow(self, url: str) -> None:
        """Apply prepared robots rules before sending either a search or a page."""
        host = host_of(url)
        if host in self.stopped:
            raise WebError(self.stopped[host])
        robot = self.checked[host]
        if robot is not None and not robot.can_fetch("*", url):
            self.stopped[host] = "obstacle"
            raise WebError("obstacle")

    def page(self, company: Company, url: str) -> Page:
        self.prepare(company, page_url=url)
        self.allow(url)
        host = host_of(url)
        with company_requests(self.manifest, company.key):
            if url not in self.manifest.urls(company.key):
                raise WebError("url_refused")
            response = self._get(url, inspect=False)
        stamp = self.clock()
        # Real transport computes the full-body hash; injected fixtures do too.
        side = {
            "source_id": "company_web",
            "key": "company_web/" + digest(company.key),
            "sha256": response.body_sha256,
            "bytes": len(response.body),
            "retrieved_utc": stamp,
            "fetch_url": response.final_url,
            "original_url": url,
            "publisher": host,
            "licence_basis": "owner_decision",
            "licence_id": "not_stated",
            "decision_record": "0026",
            "method": VERSION,
            "extractor": self.manifest.data["reviewed_by"],
        }
        blocked = obstacle(response.body) is not None
        side["access_status"] = "obstacle" if blocked else "fetched"
        page = archive_page(self.cache, company.key, response, side)
        if blocked:
            self.stopped[host] = "obstacle"
            raise ArchivedObstacle(page)
        return page


class ArchivedObstacle(WebError):
    """A body was fetched and archived, but this host may not be read again."""

    def __init__(self, page: Page) -> None:
        self.page = page
        super().__init__("obstacle")
