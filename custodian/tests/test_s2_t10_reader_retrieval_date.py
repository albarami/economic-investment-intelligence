"""Standalone BACI, Atlas and Gravity reads hide the date-parser diagnostic."""

from __future__ import annotations

from pathlib import Path

import pytest


def _read_unparseable(source: str, tmp_path: Path) -> None:
    if source == "baci":
        from custodian.tests.test_baci import (
            _baci_selected_fixture,
            _baci_write_manifest,
        )

        from eii_custodian.publicdata.baci.config import BaciError
        from eii_custodian.publicdata.baci.contracts import read_selected

        directory, _selected, manifest = _baci_selected_fixture(tmp_path)
        manifest["receipt"]["retrieved_utc"] = "not-a-date"
        selected = _baci_write_manifest(directory, manifest)
        with pytest.raises(BaciError) as caught:
            read_selected(tmp_path, selected)
    else:
        from custodian.tests.test_gravity_atlas_review import acquire, modules, rewrite

        reader = modules(source)
        result = acquire(source, tmp_path)
        selected = rewrite(
            tmp_path,
            source,
            result.digest,
            lambda manifest: manifest["receipt"].update(retrieved_utc="not-a-date"),
        )
        error = getattr(reader.config, source.capitalize() + "Error")
        with pytest.raises(error) as caught:
            reader.contracts.read_selected(tmp_path, selected)
    assert str(caught.value) == "retrieval_date"
    assert "format" not in str(caught.value)


@pytest.mark.parametrize("source", ["baci", "atlas", "gravity"])
def test_unparseable_retrieval_date_names_the_field(
    tmp_path: Path, source: str
) -> None:
    _read_unparseable(source, tmp_path)
