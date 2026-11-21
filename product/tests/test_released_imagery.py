"""Released imagery only, with invented tiles and no acquisition-root reads."""

from base64 import b64decode
from pathlib import Path
from shutil import copytree
from unittest.mock import patch

import pytest

from eii_product.api.gis_imagery import ReleasedImagery

FIXTURE = Path(__file__).parent / "fixtures/released_imagery"
JPEG = (FIXTURE / "tile.jpg").read_bytes()


def test_release_carries_only_selected_verified_immutable_files(tmp_path):
    output, identity = released_fixture(tmp_path)
    # Only committed invented release bytes exist in the reader's world.
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


def released_fixture(tmp_path):
    output = copytree(FIXTURE / "release", tmp_path / "release")
    for path in (output / "objects").glob("*.b64"):
        path.with_suffix("").write_bytes(b64decode(path.read_bytes()))
        path.unlink()
    return output, next(output.glob("*.json")).stem


def test_object_hash_checks_bytes_outside_requested_member(tmp_path):
    import json

    output, identity = released_fixture(tmp_path)
    manifest = json.loads((output / (identity + ".json")).read_bytes())
    tile = manifest["tiles"]["1995-02/10/0/0"]
    path = output / "objects" / (tile["object_sha256"] + ".tar")
    body = bytearray(path.read_bytes())
    body[-1] ^= 1
    path.write_bytes(body)
    assert body[tile["offset"] : tile["offset"] + tile["bytes"]] == JPEG
    with pytest.raises(ValueError, match=r"^imagery_integrity$"):
        ReleasedImagery(output, identity).tile("1995-02", 10, 0, 0)


def test_member_hash_checks_intact_object_with_wrong_manifest_hash(tmp_path):
    import hashlib
    import json

    output, identity = released_fixture(tmp_path)
    manifest = json.loads((output / (identity + ".json")).read_bytes())
    manifest["tiles"]["1995-02/10/0/0"]["member_sha256"] = "0" * 64
    body = json.dumps(manifest).encode()
    identity = hashlib.sha256(body).hexdigest()
    (output / (identity + ".json")).write_bytes(body)
    with pytest.raises(ValueError, match=r"^imagery_integrity$"):
        ReleasedImagery(output, identity).tile("1995-02", 10, 0, 0)


def test_shard_hash_is_cached_and_file_change_invalidates_it(tmp_path):
    import hashlib
    import os

    output, identity = released_fixture(tmp_path)
    reader = ReleasedImagery(output, identity)
    path = next((output / "objects").glob("*.tar"))
    with patch("hashlib.file_digest", wraps=hashlib.file_digest) as hashed:
        assert reader.tile("1995-02", 10, 0, 0) == JPEG
        assert reader.tile("1995-02", 10, 0, 0) == JPEG
        assert hashed.call_count == 1
        stamp = path.stat().st_mtime_ns
        os.utime(path, ns=(stamp + 1, stamp + 1))
        assert reader.tile("1995-02", 10, 0, 0) == JPEG
        assert hashed.call_count == 2


def test_first_read_accepts_intact_object_when_relatime_updates_atime(tmp_path):
    import os
    import time

    output, identity = released_fixture(tmp_path)
    path = next((output / "objects").glob("*.tar"))
    old = time.time_ns() - 3600 * 1_000_000_000
    os.utime(path, ns=(old, old))
    assert ReleasedImagery(output, identity).tile("1995-02", 10, 0, 0) == JPEG


def test_change_during_hash_refuses_without_caching_pre_hash_identity(tmp_path):
    import hashlib
    import os

    from eii_product.api import gis_imagery

    output, identity = released_fixture(tmp_path)
    reader = ReleasedImagery(output, identity)
    path = next((output / "objects").glob("*.tar"))
    original_digest = hashlib.file_digest

    def change_after_hash(stream, algorithm):
        actual = original_digest(stream, algorithm)
        status = path.stat()
        os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000_000))
        return actual

    with patch.object(gis_imagery.hashlib, "file_digest", change_after_hash):
        with pytest.raises(ValueError, match=r"^imagery_integrity$"):
            reader.tile("1995-02", 10, 0, 0)
    assert not reader._verified
    assert reader.tile("1995-02", 10, 0, 0) == JPEG
