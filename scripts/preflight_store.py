"""Store selection lines and outcomes for preflight probes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    """One preflight output line."""

    severity: str
    check: str
    reason: str

    def text(self) -> str:
        """Return the formatted line."""
        return f"{self.severity} {self.check}: {self.reason}"


@dataclass(frozen=True)
class PgOutcome:
    """PostgreSQL probe result."""

    kind: str
    reason: str


@dataclass(frozen=True)
class DockerOutcome:
    """Docker probe result."""

    kind: str
    detail: str


@dataclass(frozen=True)
class Selection:
    """Chosen store and optional line."""

    line: Line | None
    store: str


def docker_phrase(docker: DockerOutcome) -> str:
    """Return the Docker phrase for a store-selection line."""
    kind = docker.kind
    detail = docker.detail
    if kind == "reachable":
        return f"Docker reachable (server {detail})"
    if kind == "unreachable":
        return "Docker not reachable"
    if kind == "not_found":
        return "Docker not found on PATH"
    if kind == "no_answer":
        return f"Docker gave no answer within {detail} s"
    if kind == "not_started":
        return f"Docker could not be started ({detail})"
    if kind == "not_probed":
        return "Docker not probed"
    msg = f"unknown docker kind {kind!r}"
    raise ValueError(msg)


def select_store(
    pg: PgOutcome | None,
    docker: DockerOutcome | None,
) -> Selection:
    """Apply the closed store-selection table."""
    if pg is None and docker is None:
        return Selection(None, "embedded")
    if pg is not None and docker is None:
        if pg.kind == "ok":
            return Selection(
                Line("PASS", "postgresql", pg.reason),
                "postgres",
            )
        if pg.kind == "fail":
            return Selection(
                Line("FAIL", "postgresql", pg.reason),
                "none",
            )
        msg = "inconsistent probe results"
        raise ValueError(msg)
    if pg is not None and docker is not None:
        if pg.kind != "absent":
            msg = "inconsistent probe results"
            raise ValueError(msg)
        phrase = docker_phrase(docker)
        reason = f"{pg.reason}; store embedded; {phrase}"
        return Selection(Line("WARN", "postgresql", reason), "embedded")
    msg = "inconsistent probe results"
    raise ValueError(msg)
