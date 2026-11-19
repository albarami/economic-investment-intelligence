"""Named layer parsers bind their real outputs to application tables."""

import json
from pathlib import Path

from custodian.tests.test_gis_layers import _grid, _point
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata.assembly_reports import draw_tables
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.review.cache_fixture import write_cached


def test_landmarks_extend_the_catalogued_gazetteer_with_bound_sources(
    tmp_path: Path,
) -> None:
    row = entry(source="gis_landmarks", release_tables=("gazetteer",))
    base = entry(source="bnd_hdx", release_tables=("gazetteer",))
    body = {
        "layers": [
            {
                "features": [
                    {
                        "attributes": {"ENAME": "SYN MARK", "ANAME": "SYN MARK AR"},
                        "geometry": _point(10.25, 20.5),
                    }
                ]
            }
        ]
    }
    identity = write_cached(tmp_path, row, json.dumps(body).encode()).stem
    state = context(tmp_path, (row,))
    state.selected = {row.key: identity}
    state.receipts = {base.key: receipt(base)}
    state.frame_result = FrameResult({"grid_cell": _grid(10.25, 20.5)}, [], {})
    state.table(
        "gazetteer", [{"place_key": "SYN-base", "lon": 10.25, "lat": 20.5}], (base.key,)
    )
    state.record("frame", {"tables": state.tables})
    state.gis_property_singles()
    assert set(state.tables) == {"gazetteer"}
    assert len(state.tables["gazetteer"]) == 2
    assert state.tables["gazetteer"][1]["name_en"] == "SYN MARK"
    assert state.table_sources["gazetteer"] == {row.key, base.key}
    assert state.source_tables[row.key] == ["gazetteer"]
    assert draw_tables(state) == {}
    assert state.draw_exclusions == [
        {
            "table": "gazetteer",
            "sources": [base.key, row.key],
            "reason": "assembly_draw_lineage_ambiguous",
        }
    ]


def test_changed_frame_gazetteer_cannot_be_hidden_by_later_phase(
    tmp_path: Path,
) -> None:
    import pytest

    from eii_custodian.publicdata.assembly import AssemblyError

    row = entry(source="bnd_hdx", release_tables=("gazetteer",))
    state = context(tmp_path, (row,))
    state.receipts = {row.key: receipt(row)}
    state.table("gazetteer", [{"place_key": "SYN-base"}], (row.key,))
    state.record("frame", {"tables": state.tables})
    state.tables["gazetteer"] = [{"place_key": "SYN-replacement"}]
    state.record("gis_property_singles", {"tables": state.tables})
    with pytest.raises(AssemblyError, match="assembly_table_duplicate"):
        draw_tables(state)
