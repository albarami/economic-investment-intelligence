"""Independent production phase contracts (approved plan r3 section 4 item 2).

Names here are not projected from the adapter map. Each phase owns one evidence
manifest; that manifest binds the builder's real files and source identities.
The spine also owns its two parquet files. Nested grids/places belong to frame.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .assembly import PHASES, AssemblyError


@dataclass(frozen=True)
class InventoryItem:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


INVENTORY = (
    InventoryItem(
        "intake_evidence",
        ("intake/awards_owner_scrape", "review/s2_t29_sources.yaml"),
        ("assembly/intake_evidence.json",),
    ),
    InventoryItem(
        "fetch_archive",
        ("registry", "transport", "intake_evidence"),
        ("assembly/fetch_archive.json",),
    ),
    InventoryItem(
        "investment_capture",
        ("fetch_archive", "investment_pages.yaml"),
        ("assembly/investment_capture.json",),
    ),
    InventoryItem(
        "reviewed_selections",
        ("snapshot_pins.json", "fetch_archive"),
        ("assembly/reviewed_selections.json",),
    ),
    InventoryItem(
        "frame",
        (
            "reviewed_selections",
            "frame_review",
            "build_date",
            "bldg_ovt_parts",
            "bldg_ovt_stac",
            "bnd_hdx",
        ),
        ("assembly/frame.json",),
    ),
    InventoryItem(
        "register_tables",
        ("frame", "register_bundle"),
        ("assembly/register_tables.json",),
    ),
    InventoryItem(
        "spine_graph",
        (
            "reviewed_selections",
            "frame",
            "activity_spine.csv",
            "baskets.yaml",
            "place_categories",
        ),
        (
            "assembly/spine_graph.json",
            "assembly/graph/graph_node.parquet",
            "assembly/graph/graph_edge.parquet",
        ),
    ),
    InventoryItem(
        "additions",
        ("reviewed_selections", "frame", "additions_review"),
        ("assembly/additions.json",),
    ),
    InventoryItem(
        "gis_property_singles",
        ("reviewed_selections", "frame", "property_use_map.csv", "tender_confirmation"),
        ("assembly/gis_property_singles.json",),
    ),
    InventoryItem(
        "fsq",
        (
            "reviewed_selections",
            "frame",
            "places_fsq_policy.yaml",
            "places_fsq_categories.csv",
        ),
        ("assembly/fsq.json",),
    ),
    InventoryItem(
        "series_stage",
        ("reviewed_selections", "frame", "series_review"),
        ("assembly/series_stage.json",),
    ),
    InventoryItem(
        "heights",
        (
            "reviewed_selections",
            "frame",
            "height_rules",
            "assets/buildings/buildings.geojson",
            "assets/buildings/manifest.buildings.json",
        ),
        ("assembly/heights.json",),
    ),
    InventoryItem(
        "trade_reconciliation",
        ("reviewed_selections", "trade_selection"),
        ("assembly/trade_reconciliation.json",),
    ),
    InventoryItem(
        "busyness",
        ("registry", "transport", "environment"),
        ("assembly/busyness.json",),
    ),
    InventoryItem(
        "final_audit",
        (
            "frame",
            "register_tables",
            "spine_graph",
            "additions",
            "gis_property_singles",
            "fsq",
            "series_stage",
            "heights",
            "trade_reconciliation",
            "busyness",
            "pack",
            "confirmations",
        ),
        ("assembly/final_audit.json",),
    ),
    InventoryItem(
        "draw",
        ("final_audit", "stored_numeric_fields", "seed"),
        (
            "assembly/draw.json",
            "assembly/draw_values.json",
            "assembly/draw_review_values.json",
            "assembly/build.json",
        ),
    ),
    InventoryItem(
        "reports",
        ("final_audit", "draw"),
        (
            "assembly/s2_t08_completeness.json",
            "assembly/s2_t08_terms.json",
            "assembly/s2_t08_coverage.json",
            "assembly/s2_t08_oi03.json",
            "assembly/s2_t08_confirmations.json",
            "assembly/s2_t08_investment.json",
            "assembly/s2_t08_draw.json",
        ),
    ),
)


def validate_inventory(
    adapters: Mapping[str, Callable[[], Mapping[str, str]]],
    inventory: tuple[InventoryItem, ...] = INVENTORY,
) -> None:
    """Reject omissions on either side before invoking any adapter."""
    outputs = [path for item in inventory for path in item.outputs]
    if (
        tuple(item.name for item in inventory) != PHASES
        or set(adapters) != {item.name for item in inventory}
        or any(not item.inputs or not item.outputs for item in inventory)
        or len(set(outputs)) != len(outputs)
    ):
        raise AssemblyError("assembly_inventory_invalid")
