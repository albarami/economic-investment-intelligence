"""The joined Entry schema preserves file defaults and refuses foreign metadata."""

import json
from dataclasses import asdict, replace

import pytest
from custodian.tests.fixtures.baci.invented import entry

from eii_custodian.publicdata.fetch.registry import FileFields, RegistryError, _entry


def manifest_entry(source_id):
    source = replace(entry(), source_id=source_id)
    row = json.loads(json.dumps(asdict(source)))
    for name in ("layer", "basis_note", "comtrade_policy"):
        row.pop(name)
    row["columns"] = [{"name": name, "type": kind} for name, kind in source.columns]
    row["refetch"].pop("family")
    return source, row


@pytest.mark.parametrize(
    "source_id", ["cepii_baci", "cepii_gravity", "atlas_complexity"]
)
def test_manifest_entry_preserves_all_file_defaults(source_id):
    source, row = manifest_entry(source_id)
    assert set(asdict(FileFields())) <= set(row)
    assert _entry(row) == source


@pytest.mark.parametrize(
    "source_id", ["cepii_baci", "cepii_gravity", "atlas_complexity"]
)
def test_manifest_entry_refuses_unknown_field(source_id):
    _, row = manifest_entry(source_id)
    row["SYN_unknown_field"] = "SYN-not-declared"
    with pytest.raises(RegistryError, match="unknown field SYN_unknown_field"):
        _entry(row)


@pytest.mark.parametrize(
    "source_id", ["cepii_baci", "cepii_gravity", "atlas_complexity"]
)
@pytest.mark.parametrize(
    "name,value",
    [("sex", "f"), ("doi_confirmed", 0), ("variables", ["temperature_2m"])],
)
def test_manifest_entry_refuses_nondefault_or_mistyped_file_field(
    source_id, name, value
):
    _, row = manifest_entry(source_id)
    row[name] = value
    with pytest.raises(RegistryError, match="does not use it"):
        _entry(row)
