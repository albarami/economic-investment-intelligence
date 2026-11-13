"""Prove that only the transport module constructs a real opener."""

from __future__ import annotations

from pathlib import Path

OPENER_TOKENS = ("urllib.request", "urlopen", "http.client", "socket.create_connection")
TRANSPORT_REL = "custodian/src/eii_custodian/publicdata/fetch/transport.py"
SEAM_REL = "custodian/src/eii_custodian/publicdata/fetch/seam.py"
SCAN_ROOTS = ("custodian/src", "scripts/commands")
_SKIP = frozenset({TRANSPORT_REL, SEAM_REL})


def opener_hits(files: dict[str, str]) -> tuple[str, ...]:
    """Return paths, other than the transport module, whose text opens a connection."""
    hits: list[str] = []
    for path in sorted(files):
        if path in _SKIP:
            continue
        text = files[path]
        if any(token in text for token in OPENER_TOKENS):
            hits.append(path)
    return tuple(hits)


def scan_tree(root: Path) -> tuple[str, ...]:
    """Scan the custodian and command sources for an opener outside the transport."""
    files: dict[str, str] = {}
    for folder in SCAN_ROOTS:
        base = root / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            files[rel] = path.read_text(encoding="utf-8")
    return opener_hits(files)
