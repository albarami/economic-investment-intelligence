"""Released imagery only, with invented tiles and no acquisition-root reads."""

from unittest.mock import patch

import pytest
from custodian.tests.test_gis_snapshot import JPEG, STAMP, fixture_archive

from eii_custodian.publicdata.gis.snapshot_archive import verify_selection
from eii_custodian.publicdata.gis.snapshot_release import assemble
from eii_product.api.gis_imagery import ReleasedImagery


def test_release_carries_only_selected_verified_immutable_files(tmp_path):
    acquisition = tmp_path / "acquisition"
    acquisition.mkdir()
    archive, _ = fixture_archive(acquisition)
    manifest = archive.complete([0], STAMP)
    selection = verify_selection(acquisition, manifest)
    output = tmp_path / "release"
    identity = assemble((selection,), output)
    # Remove acquisition entirely from the reader's world; product never imports it.
    with patch("socket.socket.connect", side_effect=AssertionError("network")):
        reader = ReleasedImagery(output, identity)
        assert reader.tile("1995-02", 10, 0, 0) == JPEG
        assert reader.tile("2003-05", 10, 0, 0) is None
        with pytest.raises(ValueError, match="level_11_deferred"):
            reader.tile("1995-02", 11, 0, 0)
    assert reader.credit["publisher"] == "national GIS centre"
    assert reader.credit["licence_basis"] == "owner_decision"
    path = next((output / "objects").glob("*.tar"))
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        reader.tile("1995-02", 10, 0, 0)


def test_manifest_is_explicit_and_cannot_escape_or_be_mutated(tmp_path):
    with pytest.raises(ValueError):
        ReleasedImagery(tmp_path, "../x")
    with pytest.raises(ValueError):
        ReleasedImagery(tmp_path, "a" * 64)
