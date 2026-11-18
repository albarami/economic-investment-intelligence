"""Invented S2-T09 record/artifact/config shapes; confirm these in pass 2.

No helper opens a public snapshot. Multi-value pins use JSON text inside the
plan's scalar-valued values dictionary. The generation artifact is an assumed
interchange shape, not a claim about the S2-T08 live output.

The invented methods document carries the five governed sections of the sync
check, one per card anchor, and the record's hash covers exactly those spans,
mirroring the production definition for the invented layout.

The c5 pin values are per basket line and the c5 settings carry the per-line
parent review under the same line names; the data replay tests use the same
line names ("pasta", "other"). A configuration pin (the 16 "none named"
setting pins) carries no source lineage: its evidence is the recorded
configuration itself, so the record and the artifact rows hold an empty
lineage for it.
"""

import hashlib
import json

import yaml

from eii_custodian.publicdata.method_card_validation import CONFIGURATION_PINS

PIN_GROUPS = {
    "wilson": ("period",),
    "c5": ("hhi", "prior12", "latest12", "trend"),
    "c6": (
        "seed",
        "release_sha256",
        "category_ids",
        "candidate_set",
        "box",
        "confidence_min",
        "radius_m",
        "permutations",
        "fdr",
        "min_neighbours",
        "min_clq",
        "max_shown",
        "expected_clq",
        "expected_p",
        "expected_q",
    ),
    "c7": (
        "coordinates",
        "modes",
        "cutoffs",
        "speed_regime",
        "district_weights",
        "shared_b_given_a",
        "shared_a_given_b",
    ),
    "c14": ("medians_2024", "medians_2025"),
}
PINS = tuple(f"{group}.{slot}" for group, slots in PIN_GROUPS.items() for slot in slots)
PRIOR = [f"2024-{month:02}" for month in range(1, 13)]
LATEST = [f"2025-{month:02}" for month in range(7, 13)] + [
    f"2026-{month:02}" for month in range(1, 7)
]
# The same line names as the data replay's LINES; every line starts clean.
C5_LINES = ("pasta", "other")
SECTION_PROSE = "No public value appears in this fixture."
SECTIONS = (
    ("wilson", "## 3. Shared interval method and reliability mark"),
    ("c5", "### C5 Customs supplier lens"),
    ("c6", "### C6 Typical neighbours"),
    ("c7", "### C7 Shared reach between two doors"),
    ("c14", "### C14 Sale price per square metre"),
)
SECTION_HEADINGS = tuple(heading for _, heading in SECTIONS)


def governed_sections():
    """The governed heading list every schema-valid record must carry."""
    return list(SECTION_HEADINGS)


def methods_document(rows):
    """The invented methods document: governed sections with checked blocks."""
    parts = ["# Invented method cards\n\n"]
    for anchor, heading in SECTIONS:
        if anchor == "c5":
            # Section 3 ends before the card sections, as in the methods doc.
            parts.append("## 4. Version 1 method cards\n\n")
        parts.append(heading + "\n\n" + SECTION_PROSE + "\n")
        parts.append(
            blocks(
                [
                    row
                    for row in rows
                    if row["pin_id"].split(".")[0] == anchor
                    and row["checked_against_source"]
                ]
            )
        )
    parts.append("## 5. Method cards added by decisions 0016 and 0017\n")
    return "".join(parts)


def governed_baseline():
    """SHA-256 over the five block-free governed spans, concatenated in order."""
    return digest(
        b"".join(
            (heading + "\n\n" + SECTION_PROSE + "\n").encode("utf-8")
            for _, heading in SECTIONS
        )
    )


def digest(body):
    return hashlib.sha256(body).hexdigest()


def write_yaml(path, value):
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def case(tmp_path):
    """Complete invented record, with a different maker's fixture-only review."""
    lineage = [
        {
            "source_id": "invented_public_file",
            "sha256": digest(b"invented public rows"),
            "publisher": "invented publisher",
            "licence_id": "invented-licence",
            "retrieved_utc": "2026-11-18T00:00:00Z",
            "method_id": "invented.method@v1",
        }
    ]
    configuration = {"schema_version": 1, "pins": {}}
    artifact = {"schema_version": 1, "pins": []}
    rows = []
    for pin in PINS:
        settings = {"fixture_setting": "invented", "value": "invented:" + pin}
        if pin.startswith("c5."):
            settings = {
                "prior_months": PRIOR,
                "latest_months": LATEST,
                "lines": {
                    line: {
                        "parent_contains_excluded": False,
                        "parent_treatment": "clean",
                    }
                    for line in C5_LINES
                },
            }
        configuration["pins"][pin] = settings
        values = (
            {line: "invented:" + pin + ":" + line for line in C5_LINES}
            if pin.startswith("c5.")
            else {"value": "invented:" + pin}
        )
        # A configuration pin is checked by its recorded settings, never by an
        # invented source lineage, so its record and artifact rows hold none.
        pin_lineage = (
            [] if pin in CONFIGURATION_PINS else [link.copy() for link in lineage]
        )
        artifact["pins"].append(
            {
                "pin_id": pin,
                "values": values.copy(),
                "settings": settings.copy(),
                "source_lineage": pin_lineage.copy(),
            }
        )
        rows.append(
            {
                "pin_id": pin,
                "card_anchor": pin.split(".")[0],
                "builder_maker": "OpenAI",
                "reviewer_maker": "Google",
                "review_date": "2026-11-18",
                "checked_against_source": True,
                "source_lineage": pin_lineage.copy(),
                "settings_sha256": None,
                "values": values.copy(),
                "unpinned_reason": None,
            }
        )
    config_path = write_json(tmp_path / "invented-generation.json", configuration)
    for row in rows:
        row["settings_sha256"] = digest(config_path.read_bytes())
    record = {
        "schema_version": 1,
        "governed_sections": governed_sections(),
        "governed_sections_sha256": governed_baseline(),
        "pins": rows,
    }
    paths = (
        tmp_path / "invented-source-checks.yaml",
        tmp_path / "invented-produced-pins.json",
        config_path,
        tmp_path / "invented-methods.md",
    )
    paths[3].write_text(methods_document(rows), encoding="utf-8")
    save(paths, record, artifact)
    return paths, record, artifact, configuration


def blocks(rows):
    return "".join(
        f"<!-- method-pin:{row['pin_id']} -->\n"
        + json.dumps(row["values"], sort_keys=True, ensure_ascii=False)
        + f"\n<!-- /method-pin:{row['pin_id']} -->\n"
        for row in rows
        if row["checked_against_source"]
    )


def save(paths, record, artifact):
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)


def pending(row):
    row.update(
        reviewer_maker="",
        review_date="",
        checked_against_source=False,
        source_lineage=[],
        settings_sha256=None,
        values={},
        unpinned_reason="awaiting the live public build of S2-T08 part B",
    )
