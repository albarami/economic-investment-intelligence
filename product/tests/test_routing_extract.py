"""Only one regular checked extract becomes process-local routing configuration."""

import copy
import io
import json
import socket
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import strategies as st
from routing_release_fixture import TILES, invented_extract

from eii_product.api.area_context import RoutingSource, routing_from_release
from eii_product.config import ConfigError
from eii_product.store.release_check import CheckedRelease
from eii_product.store.startup import StartupRefusal, verify_artefacts
from eii_product.tools.routing import outline


@pytest.fixture(scope="module")
def extract(tmp_path_factory):
    folder = tmp_path_factory.mktemp("routing-extract")
    reference = invented_extract(folder / TILES)
    return folder, reference


def checked(folder, entries):
    return CheckedRelease(folder, {"artefacts": entries, "tables": []}, {})


def test_single_extract_has_local_config_and_no_release_write(extract):
    folder, reference = extract
    before = {
        p.relative_to(folder): p.read_bytes() for p in folder.rglob("*") if p.is_file()
    }
    source = routing_from_release(checked(folder, [reference]))
    assert source.tile_folder != folder / "artefacts/routing"
    config = json.loads((source.tile_folder / "config.json").read_bytes())
    assert config["mjolnir"]["tile_extract"] == str(folder / TILES)
    assert config["mjolnir"]["tile_dir"] == ""
    assert "tile_url" not in config["mjolnir"]
    assert before == {
        p.relative_to(folder): p.read_bytes() for p in folder.rglob("*") if p.is_file()
    }
    verify_artefacts(checked(folder, [reference]))
    assert outline(source.tile_folder, "walk", 5, 1.0, 1.0)
    assert outline(source.tile_folder, "drive", 10, 1.0, 1.0)


@pytest.mark.parametrize(
    "kind", ["zero-entries", "two-entries", "legacy-folder", "wrong-container"]
)
def test_entry_cardinality_and_legacy_folder_refused(extract, kind):
    folder, reference = extract
    entries = {
        "zero-entries": [],
        "two-entries": [reference, reference],
        "legacy-folder": [dict(reference, path="artefacts/routing/")],
        "wrong-container": None,
    }[kind]
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(checked(folder, entries))


def test_symlink_extract_refused(extract, tmp_path):
    path = tmp_path / TILES
    path.parent.mkdir(parents=True)
    path.symlink_to(extract[0] / TILES)
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(checked(tmp_path, [extract[1]]))


def test_symlink_parent_refused(extract, tmp_path):
    (tmp_path / "artefacts").symlink_to(
        extract[0] / "artefacts", target_is_directory=True
    )
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(checked(tmp_path, [extract[1]]))


@pytest.mark.parametrize("kind", ["missing", "directory", "corrupt"])
def test_extract_file_refusals(tmp_path, extract, kind):
    path = tmp_path / TILES
    path.parent.mkdir(parents=True)
    if kind == "directory":
        path.mkdir()
    elif kind == "corrupt":
        path.write_bytes(b"INVENTED-corrupt-tar")
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(checked(tmp_path, [extract[1]]))


def test_hash_mismatch_keeps_startup_reason(extract):
    folder, reference = extract
    with pytest.raises(StartupRefusal, match=r"^startup_artefact_mismatch$"):
        verify_artefacts(checked(folder, [{**reference, "sha256": "00" * 32}]))


def test_extract_routing_opens_no_connection(extract, monkeypatch):
    source = routing_from_release(checked(extract[0], [extract[1]]))
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("routing_network")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    for mode, minutes in (("walk", 5), ("drive", 10)):
        assert outline(source.tile_folder, mode, minutes, 1.0, 1.0)
    assert attempts == []
    with pytest.raises(AssertionError, match="routing_network"):
        socket.create_connection(("routing.invalid", 443))


@given(
    st.lists(
        st.sampled_from([TILES, "artefacts/routing/", "artefacts/other.tar"]),
        max_size=8,
    )
)
def test_exact_one_entry_property(extract, paths):
    folder, reference = extract
    entries = [dict(reference, path=p) for p in paths]
    routing_paths = [p for p in paths if p.startswith("artefacts/routing/")]
    if routing_paths == [TILES]:
        assert routing_from_release(checked(folder, entries)).tile_folder is not None
    else:
        with pytest.raises(ConfigError, match=r"^routing_tiles$"):
            routing_from_release(checked(folder, entries))


def test_every_manifest_leaf_with_hostile_value(extract):
    folder, reference = extract
    for key in reference:
        for hostile in ({"toString": None}, 7, None, []):
            changed = copy.deepcopy(reference)
            changed[key] = hostile
            # The checked-release boundary owns digest validation; routing owns paths.
            if key == "sha256":
                with pytest.raises(
                    StartupRefusal, match=r"^startup_artefact_mismatch$"
                ):
                    verify_artefacts(checked(folder, [changed]))
            else:
                with pytest.raises(ConfigError, match=r"^routing_tiles$"):
                    routing_from_release(checked(folder, [changed]))


@pytest.mark.parametrize(
    "kind",
    [
        "empty",
        "index-empty",
        "no-index",
        "link",
        "index-size",
        "index-offset",
        "duplicate",
        "graph-name",
    ],
)
def test_structurally_invalid_tar_refused(tmp_path, extract, kind):
    path = tmp_path / "tiles.tar"
    with tarfile.open(extract[0] / TILES, "r:") as original:
        members = original.getmembers()
        bodies = {m.name: original.extractfile(m).read() for m in members}
    if kind == "no-index":
        members = members[1:]
    elif kind == "empty":
        members = []
    elif kind == "index-empty":
        members = members[:1]
        bodies["index.bin"] = b""
    elif kind == "duplicate":
        members.append(copy.copy(members[-1]))
        bodies["index.bin"] += b"\x00" * 16
    elif kind == "graph-name":
        bodies["INVENTED.gph"] = bodies[members[-1].name]
        members[-1].name = "INVENTED.gph"
    elif kind == "link":
        members[-1].type = tarfile.SYMTYPE
        members[-1].linkname = "INVENTED"
    elif kind == "index-size":
        bodies["index.bin"] = b"x"
    elif kind == "index-offset":
        bodies["index.bin"] = b"\x00" * len(bodies["index.bin"])
    with tarfile.open(path, "w") as archive:
        for member in members:
            body = bodies[member.name]
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
    if kind == "duplicate":
        from valhalla.baldr.utils.tar_index import write_tar_index

        write_tar_index(path)
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        RoutingSource.from_tiles(path, tmp_path)


@pytest.mark.parametrize("value", [None, "tiles.tar", [], 7])
def test_wrong_extract_type_refused(value, tmp_path):
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        RoutingSource.from_tiles(value, tmp_path)


@pytest.mark.parametrize("minutes", [20, 30])
def test_staffing_only_minutes_refused_elsewhere(minutes):
    from eii_product.tools.make_area import ArgumentError, validate_request

    request = dict(mode="drive", cutoff=minutes, latitude=1, longitude=1)
    assert validate_request(request, "staffing_and_pay").cutoff == minutes
    with pytest.raises(ArgumentError, match=r"^INVALID_ARGUMENT$"):
        validate_request(request, "site_check")


def test_drive_upper_limit_is_independent(monkeypatch):
    from eii_product.tools import make_area as area

    # Widen only the other guard's list so this plant reaches the hard limit.
    monkeypatch.setattr(area, "DRIVE_MINUTES", area.DRIVE_MINUTES | {31})
    with pytest.raises(area.ArgumentError, match=r"^INVALID_ARGUMENT$"):
        area.validate_request(
            dict(mode="drive", cutoff=31, latitude=1, longitude=1), "staffing_and_pay"
        )


@given(
    mode=st.sampled_from(["walk", "drive"]),
    minutes=st.integers(),
    staffing=st.booleans(),
)
def test_cutoffs_follow_the_closed_minute_domain(mode, minutes, staffing):
    from eii_product.tools.make_area import ArgumentError, validate_request

    playbook = "staffing_and_pay" if staffing else "site_check"
    accepted = minutes in {5, 10, 15} or (
        mode == "drive" and staffing and minutes in {20, 30}
    )
    request = dict(mode=mode, cutoff=minutes, latitude=1, longitude=1)
    if accepted:
        assert validate_request(request, playbook).cutoff == minutes
    else:
        with pytest.raises(ArgumentError, match=r"^INVALID_ARGUMENT$"):
            validate_request(request, playbook)


def test_config_write_failure_is_closed_and_cleans_storage(extract, monkeypatch):
    from pathlib import Path
    from tempfile import TemporaryDirectory

    storages = []

    def storage(**kwargs):
        result = TemporaryDirectory(**kwargs)
        storages.append(result)
        return result

    def failed(*args, **kwargs):
        raise OSError("INVENTED-private-path")

    monkeypatch.setattr("eii_product.api.area_context.TemporaryDirectory", storage)
    monkeypatch.setattr(Path, "write_text", failed)
    with pytest.raises(ConfigError, match=r"^operation_os_error$") as caught:
        RoutingSource.from_tiles(extract[0] / TILES, extract[0])
    assert caught.value.__context__ is None
    assert all(not Path(s.name).exists() for s in storages)


def test_generated_config_discards_network_and_ancillary_defaults(extract, monkeypatch):
    import valhalla

    original = valhalla.get_config

    def hostile_defaults(*args, **kwargs):
        config = copy.deepcopy(original(*args, **kwargs))
        config["mjolnir"]["tile_url"] = "https://routing.invalid/{tilePath}"
        return config

    monkeypatch.setattr(valhalla, "get_config", hostile_defaults)
    source = RoutingSource.from_tiles(extract[0] / TILES, extract[0])
    config = json.loads((source.tile_folder / "config.json").read_bytes())
    assert set(config["mjolnir"]) == {"tile_extract", "tile_dir"}
    assert config["additional_data"] == {}


def test_second_listed_routing_file_is_refused(extract, tmp_path):
    folder, reference = extract
    other = "artefacts/routing/other.tar"
    body = (folder / TILES).read_bytes()
    for relative in (TILES, other):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    release = checked(tmp_path, [reference, dict(reference, path=other)])
    verify_artefacts(release)
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(release)


def test_release_under_symlinked_ancestor_is_accepted(extract, tmp_path):
    real_parent = tmp_path / "real-parent"
    real_release = real_parent / "release"
    path = real_release / TILES
    path.parent.mkdir(parents=True)
    path.write_bytes((extract[0] / TILES).read_bytes())
    alias = tmp_path / "alias-parent"
    alias.symlink_to(real_parent, target_is_directory=True)
    release = alias / "release"
    source = routing_from_release(checked(release, [extract[1]]))
    config = json.loads((source.tile_folder / "config.json").read_bytes())
    assert config["mjolnir"]["tile_extract"] == str(path.resolve())
    verify_artefacts(checked(release, [extract[1]]))


@pytest.mark.parametrize("kind", ["outside", "traversal", "wrong-root-type"])
def test_extract_must_be_inside_release(extract, kind):
    root, _reference = extract
    path = root / TILES
    release = root
    if kind == "outside":
        release = root / "artefacts" / "routing" / "other"
    elif kind == "traversal":
        path = root / "artefacts" / ".." / TILES
    else:
        release = None
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        RoutingSource.from_tiles(path, release)


@given(
    depth=st.integers(min_value=0, max_value=5),
    inside=st.booleans(),
)
def test_symlink_scope_follows_release_boundary(extract, depth, inside):
    with TemporaryDirectory(dir=extract[0]) as temporary:
        base = Path(temporary)
        for _ in range(depth):
            base = base / "nested"
        release = base / "release"
        path = release / TILES
        path.parent.mkdir(parents=True)
        path.write_bytes((extract[0] / TILES).read_bytes())
        alias = base / "alias"
        alias.symlink_to(release, target_is_directory=True)
        if inside:
            root = base / "other-release"
            root.mkdir()
            (root / "artefacts").symlink_to(
                release / "artefacts", target_is_directory=True
            )
            with pytest.raises(ConfigError, match=r"^routing_tiles$"):
                routing_from_release(checked(root, [extract[1]]))
        else:
            source = routing_from_release(checked(alias, [extract[1]]))
            config = json.loads((source.tile_folder / "config.json").read_bytes())
            assert config["mjolnir"]["tile_extract"] == str(path.resolve())
