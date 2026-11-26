"""The production inventory is independent of the executable adapter map."""

from dataclasses import replace

import pytest

from eii_custodian.publicdata.assembly import PHASES, AssemblyError
from eii_custodian.publicdata.assembly_inventory import (
    INVENTORY,
    validate_inventory,
)

CONTRACTED_TRADE_AND_BENCHMARK_TABLES = frozenset(
    """
pub_atlas_country_partner_product_year pub_atlas_country_product_year
pub_atlas_cppy_country pub_atlas_cppy_product pub_atlas_cpy_country
pub_atlas_cpy_product pub_gravity_bilateral pub_gravity_country pub_baci_trade
pub_baci_country pub_baci_product pub_wdi_benchmark pub_unctad_fdi_benchmark
pub_weo_benchmark pub_ilostat_benchmark
""".split()
)


def test_contracted_trade_and_benchmark_tables_are_in_actual_catalogue() -> None:
    from pathlib import Path

    from eii_custodian.publicdata.completeness import table_catalogue

    catalogue = table_catalogue(
        Path("docs/03_DATA_CONTRACTS.md").read_text(encoding="utf-8")
    )
    assert CONTRACTED_TRADE_AND_BENCHMARK_TABLES <= catalogue


def test_inventory_has_each_phase_and_explicit_inputs_and_outputs() -> None:
    assert tuple(item.name for item in INVENTORY) == PHASES
    assert all(item.inputs and item.outputs for item in INVENTORY)
    assert len({path for item in INVENTORY for path in item.outputs}) == sum(
        len(item.outputs) for item in INVENTORY
    )
    validate_inventory({name: lambda: {} for name in PHASES})


@pytest.mark.parametrize("missing", PHASES)
def test_missing_adapter_is_refused_before_execution(missing: str) -> None:
    adapters = {name: lambda: {} for name in PHASES if name != missing}
    with pytest.raises(AssemblyError, match="assembly_inventory_invalid"):
        validate_inventory(adapters)


def test_uninventoried_adapter_is_refused() -> None:
    adapters = {name: lambda: {} for name in (*PHASES, "another_builder")}
    with pytest.raises(AssemblyError, match="assembly_inventory_invalid"):
        validate_inventory(adapters)


def test_duplicate_inventory_and_wrong_order_are_refused() -> None:
    adapters = {name: lambda: {} for name in PHASES}
    for inventory in (
        INVENTORY + INVENTORY[:1],
        tuple(reversed(INVENTORY)),
        (replace(INVENTORY[0], outputs=INVENTORY[1].outputs), *INVENTORY[1:]),
    ):
        with pytest.raises(AssemblyError, match="assembly_inventory_invalid"):
            validate_inventory(adapters, inventory)


def test_actual_pack_identity_and_trade_extension_share_one_comtrade_identity() -> None:
    from pathlib import Path

    from eii_custodian.publicdata.assembly_sources import FAMILY_COUNTS
    from eii_custodian.publicdata.completeness import pack_sources

    pack = pack_sources(Path("docs/04_PUBLIC_DATA_PACK.md").read_text(), FAMILY_COUNTS)
    assert "un_comtrade" in pack.sources
    assert sum(len(pack.sources[source]) for source in FAMILY_COUNTS) == 77


def test_same_block_duplicate_identity_is_still_refused() -> None:
    from eii_custodian.publicdata.completeness import pack_sources

    text = "### 2.1 Identity\n| id | name | publisher | how | licence |\n| `un_comtrade` | A | B | C | D |\n| `un_comtrade` | A | B | C | D |\n### 2.3 Trade\n### 2.4 Pages\n"
    with pytest.raises(ValueError, match="pack_source_duplicate"):
        pack_sources(text, {})


def test_fixed_pack_inventory_catches_joint_source_omission() -> None:
    from custodian.tests.test_source_completeness import entry, receipt

    from eii_custodian.publicdata.assembly_sources import PACK_IDENTITIES
    from eii_custodian.publicdata.completeness import Pack, check

    row = entry(source="util_elec", release_tables=())
    assert "util_elec" in PACK_IDENTITIES
    record = check(
        entries=[],
        pack=Pack({}, frozenset()),
        inventory={"util_elec": PACK_IDENTITIES["util_elec"]},
        catalogue=frozenset(),
        receipts={},
        outputs={},
        absences={},
        cached_source_ids=(),
    )
    assert any(
        item["id"] == "util_elec" and item["state"] == "failed" for item in record
    )
    valid = check(
        entries=[row],
        pack=Pack({"util_elec": ()}, frozenset()),
        inventory={"util_elec": ()},
        catalogue=frozenset(),
        receipts={row.key: receipt(row)},
        outputs={},
        absences={},
        cached_source_ids=(),
    )
    assert not [item for item in valid if item["state"] == "failed"]


def test_seed_and_draw_log_is_a_declared_draw_output() -> None:
    draw = next(item for item in INVENTORY if item.name == "draw")
    assert "assembly/build.json" in draw.outputs


def test_closed_component_inventory_admits_leaf_only_families_and_refuses_omissions() -> (
    None
):
    from custodian.tests.test_source_completeness import entry, receipt

    from eii_custodian.publicdata.completeness import Pack, check

    rows = [
        entry(source="family", key="family/SYN-a", release_tables=()),
        entry(source="family", key="family/SYN-b", release_tables=()),
    ]
    expected = frozenset(row.key for row in rows)

    def inspect(items):
        return check(
            entries=items,
            pack=Pack({"family": ()}, frozenset()),
            inventory={"family": ()},
            catalogue=frozenset(),
            receipts={row.key: receipt(row) for row in items},
            outputs={},
            absences={},
            cached_source_ids=(),
            component_keys={"family": expected},
        )

    assert not [row for row in inspect(rows) if row["state"] == "failed"]
    assert [row for row in inspect(rows[:1]) if row["state"] == "failed"]
    assert [
        row
        for row in inspect(
            [*rows, entry(source="family", key="family/SYN-c", release_tables=())]
        )
        if row["state"] == "failed"
    ]
