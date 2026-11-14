"""Closed tables of the reference-notes check: files, libraries, fields, addresses, words."""

from __future__ import annotations

import re
from typing import NamedTuple

WEB = "web/REFERENCE_NOTES.md"
DOCS = "docs/REFERENCE_NOTES.md"
PINS = "pins.toml"
LINKS = {WEB: "../docs/REFERENCE_NOTES.md", DOCS: "../web/REFERENCE_NOTES.md"}
KINDS = ("READ", "OBSERVED", "PACK")
CONFIRMED = "not yet confirmed"
MEASURED = re.compile(
    r'confirmed: .+; PROGRESS\.md heading "S1-T[0-9]+ — .+: task log"'
)
UNVERIFIED = "not verified"
NOT_COVERED = "not covered: "
FENCES = ("```", "~~~")
HOW = "How to read these notes"
COVERAGE = "Pack statements and where each stands"
DATE_FLOOR = "2026-01-01"
OPENING = ("Used here", "The module")
ASSIGNED_OPENING = ("The owner decided",)
SETUP = ("Setup", "Same setup")
CLAIM_WORDS = (
    "works",
    "working",
    "passes",
    "passed",
    "fast",
    "faster",
    "slow",
    "safe",
    "safely",
    "better",
    "worse",
    "best",
    "approved",
)
QUOTE_WORDS = (3, 40)
ASSIGNED = "Confirmations assigned to this task"
ASSIGNED_SENTENCE = (
    "The owner decided on 2026-11-11 that the lead assigns each slice S0 requirement"
    " that no task owned to the nearest task; the lead assigned DES-25 and DES-45"
    " to S0-T13."
)
ASSIGNED_SUBS = ("Pages read", "Runs", "Font weights", "Icon package licence")
EXTRA_SECTIONS = {WEB: (ASSIGNED,), DOCS: ()}
WEIGHTS = ("400", "500", "600")
FAMILIES = {
    "IBM Plex Sans": ("@fontsource/ibm-plex-sans", "ibm-plex-sans-"),
    "IBM Plex Sans Arabic": (
        "@fontsource/ibm-plex-sans-arabic",
        "ibm-plex-sans-arabic-",
    ),
}
RULES = (
    "input",
    "cross-link",
    "section",
    "subsection",
    "table",
    "id",
    "address",
    "date",
    "kind",
    "source",
    "quote",
    "unverified",
    "unused",
    "claim-word",
    "confirmation",
    "pins-row",
    "pack-cite",
    "fence",
    "prose",
    "coverage",
    "assigned",
    "weights",
    "icon-licence",
)
TABLES = {
    "Pages read": ("Id", "Address", "Page title", "Date read"),
    "Runs": ("Id", "Package and version", "Date", "Command", "Output"),
    "Idioms that changed": (
        "Id",
        "Earlier form",
        "Current form",
        "Kind",
        "Source",
        "Quote",
    ),
    "Statements": ("Id", "Statement", "Kind", "Source", "Quote"),
    "Slice S1 confirmation": ("Field", "Value", "Rows in pins.toml", "Pack source"),
}
COVERAGE_HEADER = ("Pack claim", "Pack source", "Where")
ASSIGNED_TABLES = {
    "Font weights": (
        "Id",
        "Family",
        "Subset",
        "Weight",
        "Files found in the package",
        "Kind",
        "Package and version",
        "Date",
        "Source",
    ),
    "Icon package licence": (
        "Id",
        "Package and version",
        "Licence identifier",
        "Licence file",
        "Kind",
        "Source",
        "Quote",
        "Date",
    ),
}
ALL_TABLES = {**TABLES, **ASSIGNED_TABLES, COVERAGE: COVERAGE_HEADER}
PREFIX = {
    "Pages read": "P",
    "Runs": "R",
    "Idioms that changed": "I",
    "Statements": "S",
    "Font weights": "F",
    "Icon package licence": "C",
}
OFFICIAL = (
    ("maplibre.org", "/maplibre-gl-js/docs/"),
    ("github.com", "/maplibre/"),
    ("raw.githubusercontent.com", "/maplibre/"),
    ("deck.gl", "/docs/"),
    ("github.com", "/visgl/"),
    ("duckdb.org", "/docs/2.0/"),
    ("duckdb.org", "/2026/10/21/announcing-duckdb-200"),
    ("www.postgresql.org", "/docs/18/"),
    ("www.postgresql.org", "/support/versioning/"),
    ("hub.docker.com", "/_/postgres"),
    ("github.com", "/carbon-design-system/"),
    ("raw.githubusercontent.com", "/carbon-design-system/"),
    ("platform.claude.com", "/docs/en/"),
)


class Library(NamedTuple):
    """A library section: its heading, the pins.toml rows it must cite, its S1 fields."""

    name: str
    rows: tuple[str, ...]
    fields: tuple[str, ...]


LIBRARIES: dict[str, tuple[Library, ...]] = {
    WEB: (
        Library(
            "MapLibre GL JS 6",
            ("maplibre-gl", "@mapbox/mapbox-gl-rtl-text"),
            (
                "exact pin, last 5.x release and right-to-left plugin for the retreat",
                "spike result that chose between pin and retreat",
                "Arabic glyph route (glyph files or font-faces)",
                "hexagons under labels",
                "pixel-ratio cap value",
                "watermark mechanism",
            ),
        ),
        Library(
            "deck.gl 9.4",
            (
                "@deck.gl/core",
                "@deck.gl/layers",
                "@deck.gl/geo-layers",
                "@deck.gl/extensions",
            ),
            (
                "exact pin and retreat pin of the four layer packages",
                "spike result that chose between pin and retreat",
                "style extensions through H3HexagonLayer",
                "method for moving dashes",
                "load trial of 110,000 hexagons and 50,000 particles",
                "no code path enables WebGPU",
            ),
        ),
        Library(
            "deck.gl MapLibre module",
            ("@deck.gl/maplibre", "@deck.gl/mapbox"),
            (
                "exact pin and the retreat that replaces the module",
                "interleaved mode with the pinned MapLibre on WebGL2",
                "layers under labels through beforeId",
            ),
        ),
    ),
    DOCS: (
        Library(
            "DuckDB 2.0",
            ("duckdb",),
            (
                "exact pin, or the retreat series chosen instead",
                "path of the project-local extension directory",
                "need for geometry_always_xy",
                "text ordering by byte value, by the parity query",
                "threading guidance of the 2.0 Python interface",
                "copy mechanism from DuckDB to PostgreSQL",
                "files written by 2.0 when the retreat series is chosen",
            ),
        ),
        Library(
            "PostgreSQL 18",
            ("postgresql", "postgis", "postgis-image"),
            (
                "exact pin of PostgreSQL 18 and the PostGIS 3.6 line",
                "image digest of the PostGIS image",
                "data directory and volume path of that image",
                "first parity query on both stores",
            ),
        ),
        Library(
            "Claude API",
            ("anthropic", "claude-model"),
            (
                "SDK pin and written retreat pin",
                "model string",
                "thinking counts toward max_tokens",
                "inference geographies",
                "minimum cacheable prefix",
            ),
        ),
    ),
}
