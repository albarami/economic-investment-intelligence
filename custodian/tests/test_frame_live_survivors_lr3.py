"""LR3 verifies remapped municipality boundaries handed to the grid builder."""

from custodian.tests.test_frame_live_survivors import _world

from eii_custodian.publicdata.frame import live
from eii_custodian.publicdata.frame.build import build_frame


def test_grid_receives_remapped_municipality_code(tmp_path, monkeypatch):
    prepared = _world(tmp_path)
    real_grid = live.build_grid
    seen = []

    def checked_grid(municipalities, *args, **kwargs):
        seen.extend((item.key, item.municipality_code) for item in municipalities)
        return real_grid(municipalities, *args, **kwargs)

    monkeypatch.setattr(live, "build_grid", checked_grid)
    result = build_frame(prepared.cache, prepared.entries, prepared.review)
    assert seen == [("9", "9")]
    assert result.tables["municipality"][0]["municipality_code"] == "9"
