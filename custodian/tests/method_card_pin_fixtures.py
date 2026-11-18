"""Invented S2-T09 record/artifact/config shapes; confirm these in pass 2.

No helper opens a public snapshot. Multi-value pins use JSON text inside the
plan's scalar-valued values dictionary. The generation artifact is an assumed
interchange shape, not a claim about the S2-T08 live output.
"""

import hashlib
import json

import yaml

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
    baseline = "# Invented method cards\n\nNo public value appears in this fixture.\n"
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
                "parent_contains_excluded": False,
                "parent_treatment": "clean",
            }
        configuration["pins"][pin] = settings
        values = {"value": "invented:" + pin}
        artifact["pins"].append(
            {
                "pin_id": pin,
                "values": values.copy(),
                "settings": settings.copy(),
                "source_lineage": [link.copy() for link in lineage],
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
                "source_lineage": [link.copy() for link in lineage],
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
        "methods_sha256": digest(baseline.encode()),
        "pins": rows,
    }
    paths = (
        tmp_path / "invented-source-checks.yaml",
        tmp_path / "invented-produced-pins.json",
        config_path,
        tmp_path / "invented-methods.md",
    )
    paths[3].write_text(baseline + blocks(rows), encoding="utf-8")
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
