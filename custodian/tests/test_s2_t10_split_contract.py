"""The three single-source wage rows declare only splits their columns carry."""

from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry

from .test_registry_survivors import invented_row

_SOURCES = ("sec_hr_comp_occ", "wage_bands_priv", "ref_min_wage")


def test_registry_splits_match_the_recorded_columns():
    entries = {entry.source_id: entry for entry in load_registry()}
    for source_id in _SOURCES:
        entry = entries[source_id]
        names = {name for name, _kind in entry.columns}
        assert "sex" not in names
        assert "gender" not in names
        assert not any("nationality" in name for name in names)
        assert entry.public_splits == ()


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
