"""OI-131 declarations match recorded columns and the split-table contracts."""

from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.additions.build import _CATALOGUE
from eii_custodian.publicdata.additions.splits import _KEYS, _TABLES
from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry

from .test_registry_survivors import invented_row

_SOURCES = ("sec_hr_comp_occ", "wage_bands_priv", "ref_min_wage")


@pytest.mark.parametrize(
    "source_id", (*_SOURCES, "active_nat_occ_act", "visitors_markets")
)
def test_registry_splits_match_the_recorded_columns(source_id):
    entries = [entry for entry in load_registry() if entry.source_id == source_id]
    if source_id in _SOURCES:
        assert len(entries) == 1
        entry = entries[0]
        assert bool(entry.columns) == (source_id == "wage_bands_priv")
        names = {name for name, _kind in entry.columns}
        assert "sex" not in names
        assert "gender" not in names
        assert not any("nationality" in name for name in names)
        assert entry.public_splits == ()
        return

    review = (
        Path(__file__).resolve().parents[1] / "publicdata/review/additions_splits.yaml"
    )
    roles = yaml.safe_load(review.read_text(encoding="utf-8"))["roles"]
    assert {entry.key for entry in entries} == {
        key for key in roles if key.startswith(f"{source_id}/")
    }
    assert len(entries) == (6 if source_id == "active_nat_occ_act" else 4)
    for entry in entries:
        role = roles[entry.key]
        table = _TABLES[role["kind"]]
        columns, key = _CATALOGUE[table]
        assert entry.release_tables == (table,)
        assert key == _KEYS[role["kind"]]
        expected = {
            dimension
            for dimension, field in (
                ("nationality", "nationality_group"),
                ("sex", "sex"),
            )
            if field in dict(columns)
        }
        assert set(entry.public_splits) == expected, (
            f"public split mismatch: {entry.key}"
        )
        assert len(entry.public_splits) == len(expected), (
            f"duplicate split: {entry.key}"
        )
        names = {name for name, _kind in entry.columns}
        assert names, f"recorded columns missing: {entry.key}"
        if "measure" in role:
            assert role["measure"] in names
        if source_id == "active_nat_occ_act":
            # These dimensions are published in the slug, not in a record column.
            assert {"occupation", "economic_activity"} <= names
            assert role["nationality"] in {"qatari", "non_qatari"}
            assert role["sex"] in {"female", "male", "all"}
        else:
            # Mode-only arrivals use the contract's nationality_group=all.
            field = {
                "hotel": "nationality",
                "arrivals_region": "region",
                "arrivals_mode": "mode_of_entry",
                "arrivals_trends": "mode_of_transportation",
            }[role["kind"]]
            assert field in names


def test_declared_split_without_a_column_is_refused(tmp_path: Path):
    row = invented_row(
        key="wage_bands_priv",
        source_id="wage_bands_priv",
        public_splits=["sex"],
        release_tables=["pub_wage_table"],
        columns=[
            {"name": "year", "type": "string"},
            {"name": "wage_group", "type": "string"},
            {"name": "number_of_occupations", "type": "integer"},
        ],
    )
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}), encoding="utf-8")
    with pytest.raises(RegistryError) as caught:
        load_registry(path)
    assert str(caught.value) == "public_splits contract mismatch"
