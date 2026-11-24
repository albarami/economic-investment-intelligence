"""Invented single-file artefacts placed under ``artefacts/`` (decision 0096)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from public_assembly_fixture import approve, dump, inputs

from eii_custodian.release import artefacts as a
from eii_custodian.release import pinned, producer
from eii_custodian.release.artefacts import RECORD, place_artefact
from eii_custodian.release.assembly import build

TILES = "artefacts/routing/INVENTED-contract.tar"
FONT = "artefacts/fonts/INVENTED Stack/0-255.pbf"


def source(tmp_path: Path, body: bytes = b"INVENTED-artefact-bytes") -> Path:
    path = tmp_path / "INVENTED-source-files" / hashlib.sha256(body).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def record(cache: Path) -> dict:
    return json.loads((cache / RECORD).read_bytes())


def test_place_copies_one_regular_file_and_records_it(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    cache.mkdir()
    body = b"INVENTED-tile-extract"
    placed = place_artefact(cache, TILES, source(tmp_path, body))
    assert placed == dict(path=TILES, sha256=hashlib.sha256(body).hexdigest())
    assert (cache / TILES).read_bytes() == body
    assert record(cache) == dict(
        method="public-assembly.artefacts",
        method_version="1",
        tables={},
        artefacts=[placed],
    )
    font = place_artefact(cache, FONT, source(tmp_path, b"INVENTED-glyphs"))
    # The record is sorted by path; a placed path replaces its own entry only.
    replaced = place_artefact(cache, TILES, source(tmp_path, b"INVENTED-second"))
    assert record(cache)["artefacts"] == [font, replaced]
    assert sorted(p.name for p in (cache / "artefacts/routing").iterdir()) == [
        "INVENTED-contract.tar"
    ]


@pytest.mark.parametrize(
    "relative",
    [
        "/artefacts/routing/tiles.tar",
        "artefacts/../tiles.tar",
        "artefacts/routing/../../tiles.tar",
        "tables/tiles.tar",
        "INVENTED-source/tiles.tar",
        "artefacts",
        "artefacts/",
        "artefacts/routing/",
        "artefacts//tiles.tar",
        "artefacts/./tiles.tar",
        "./artefacts/tiles.tar",
        "artefacts\\tiles.tar",
        "artefacts/tiles\x00.tar",
        "artefacts/tiles\n.tar",
        "artefacts/tiles\x7f.tar",
        "artefacts/tiles\x85.tar",
        "artefacts/tiles\x9f.tar",
        "artefacts/e\u0301.tar",
        "artefacts/" + "a" * 256,
        "artefacts/" + "/".join(["a" * 200] * 6),
        "artefacts/.private/tiles.tar",
        "artefacts/.env",
        "",
        None,
        b"artefacts/tiles.tar",
    ],
)
def test_path_faults_are_refused_before_any_write(tmp_path, relative):
    cache = tmp_path / "INVENTED-cache"
    cache.mkdir()
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, relative, source(tmp_path))
    assert list(cache.iterdir()) == []


def test_symlinked_artefacts_folder_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    outside = tmp_path / "INVENTED-outside"
    outside.mkdir()
    cache.mkdir()
    (cache / "artefacts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert list(outside.iterdir()) == []
    assert not (cache / RECORD).exists()


@pytest.mark.parametrize("kind", ["folder", "fifo"])
def test_existing_folder_at_the_destination_is_refused(tmp_path, kind):
    cache = tmp_path / "INVENTED-cache"
    (cache / TILES).parent.mkdir(parents=True)
    if kind == "folder":
        (cache / TILES).mkdir()
    else:
        os.mkfifo(cache / TILES)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert not (cache / RECORD).exists()


def test_file_in_place_of_a_destination_folder_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    (cache / "artefacts").mkdir(parents=True)
    (cache / "artefacts/routing").write_bytes(b"INVENTED")
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert (cache / "artefacts/routing").read_bytes() == b"INVENTED"
    assert not (cache / RECORD).exists()


def _symlink(tmp_path: Path) -> Path:
    link = tmp_path / "INVENTED-link"
    link.symlink_to(source(tmp_path))
    return link


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / "INVENTED-folder"
    folder.mkdir()
    (folder / "INVENTED-member").write_bytes(b"INVENTED")
    return folder


def _fifo(tmp_path: Path) -> Path:
    fifo = tmp_path / "INVENTED-fifo"
    os.mkfifo(fifo)
    return fifo


def _missing(tmp_path: Path) -> Path:
    return tmp_path / "INVENTED-absent"


@pytest.mark.parametrize("make", [_symlink, _folder, _fifo, _missing])
def test_source_that_is_not_one_regular_file_is_refused(tmp_path, make):
    cache = tmp_path / "INVENTED-cache"
    cache.mkdir()
    with pytest.raises(ValueError, match=r"\Aartefact_not_regular\Z"):
        place_artefact(cache, TILES, make(tmp_path))
    assert list(cache.iterdir()) == []


_PART = st.text(
    alphabet=st.one_of(
        st.characters(categories=("Cc",)),
        st.sampled_from(
            [
                ".",
                "/",
                "\\",
                "a",
                "Z",
                "0",
                "-",
                " ",
                "\u00e9",
                "e",
                "\u0301",
                "\u0642",
                "\x00",
            ]
        ),
    ),
    max_size=12,
)


@settings(deadline=None)
@given(
    head=st.sampled_from(["artefacts/", "/artefacts/", "", "artefacts", "tables/"]),
    tail=_PART,
    repeat=st.integers(min_value=1, max_value=40),
)
@example(head="artefacts/", tail="a", repeat=255)
@example(head="artefacts/", tail="a", repeat=256)
@example(head="artefacts/", tail="..", repeat=1)
@example(head="artefacts/", tail="\u00e9", repeat=128)
@example(head="artefacts/", tail="\u00e9", repeat=127)
@example(head="artefacts/", tail="\u0642", repeat=1)
@example(head="artefacts/" + "/".join(["a" * 255] * 3) + "/", tail="b" * 246, repeat=1)
@example(head="artefacts/" + "/".join(["a" * 255] * 3) + "/", tail="b" * 247, repeat=1)
def test_any_relative_path_is_placed_inside_artefacts_or_refused(
    tmp_path_factory, head, tail, repeat
):
    relative = head + tail * repeat
    with tempfile.TemporaryDirectory(dir=tmp_path_factory.getbasetemp()) as folder:
        root = Path(folder)
        cache = root / "INVENTED-cache"
        cache.mkdir()
        try:
            placed = place_artefact(cache, relative, source(root))
        except ValueError as error:
            assert str(error) == "artefact_path_refused"
            assert list(cache.iterdir()) == []
            return
        parts = PurePosixPath(relative).parts
        assert all(unicodedata.category(c) != "Cc" for c in relative)
        assert placed["path"] == relative
        assert parts[0] == "artefacts" and len(parts) >= 2
        assert not {".", "..", ""} & set(relative.split("/"))
        assert (
            (cache / relative).resolve().is_relative_to((cache / "artefacts").resolve())
        )
        assert (cache / relative).is_file() and not (cache / relative).is_symlink()
        assert record(cache)["artefacts"] == [placed]


def placed_inputs(cache: Path, tmp_path: Path) -> dict:
    """Invented inputs whose spec lists the recorded single-file artefacts."""
    spec = inputs(cache)
    place_artefact(cache, TILES, source(tmp_path, b"INVENTED-tile-extract"))
    place_artefact(cache, FONT, source(tmp_path, b"INVENTED-glyphs"))
    spec["artefacts"] = record(cache)["artefacts"]
    dump(cache / producer.SPEC, spec)
    return spec


def refused(cache: Path, reason: str) -> None:
    with pytest.raises(ValueError, match=r"\A" + reason + r"\Z"):
        producer.prepare(cache)
    assert not (cache / "assembly/release_candidate.json").exists()


def test_artefacts_stays_ninth_and_routing_is_tenth_producer_phase():
    assert producer.PHASES[8] == "artefacts"
    assert producer.PHASES[9] == "routing" and len(producer.PHASES) == 10


def test_spec_hash_that_differs_from_the_record_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    spec = placed_inputs(cache, tmp_path)
    # The file and the spec agree; only the phase record differs.
    body = b"INVENTED-replaced-glyphs"
    (cache / FONT).write_bytes(body)
    spec["artefacts"][0]["sha256"] = hashlib.sha256(body).hexdigest()
    dump(cache / producer.SPEC, spec)
    refused(cache, "producer_hash_mismatch")


@pytest.mark.parametrize("change", ["omitted", "unrecorded", "duplicated"])
def test_spec_inventory_must_equal_the_record(tmp_path, change):
    cache = tmp_path / "INVENTED-cache"
    spec = placed_inputs(cache, tmp_path)
    if change == "omitted":
        spec["artefacts"].pop()
    elif change == "duplicated":
        spec["artefacts"].append(spec["artefacts"][0])
    else:
        path = "artefacts/INVENTED-unrecorded.json"
        digest = dump(cache / path, dict(method="INVENTED-evidence.v1"))
        spec["artefacts"].append(dict(path=path, sha256=digest))
    dump(cache / producer.SPEC, spec)
    refused(cache, "producer_chain_incomplete")


_DIGEST = "ab" * 32
RECORD_FAULTS = [
    dict(method="public-assembly.frame"),
    dict(method_version="2"),
    dict(tables={"INVENTED": []}),
    dict(artefacts={}),
    dict(artefacts=[["path", "sha256"]]),
    dict(artefacts=[dict(path=TILES)]),
    dict(artefacts=[dict(path=5, sha256=_DIGEST)]),
    dict(artefacts=[dict(path=TILES, sha256=5)]),
    dict(artefacts=[dict(path=TILES, sha256="INVENTED")]),
    dict(artefacts=[dict(path=TILES, sha256=_DIGEST)] * 2),
    dict(artefacts=[dict(path=TILES, sha256=_DIGEST), dict(path=FONT, sha256=_DIGEST)]),
    dict(extra="INVENTED"),
]


@pytest.mark.parametrize("fault", RECORD_FAULTS)
def test_malformed_record_is_refused_by_the_producer(tmp_path, fault):
    cache = tmp_path / "INVENTED-cache"
    placed_inputs(cache, tmp_path)
    dump(cache / RECORD, {**record(cache), **fault})
    refused(cache, "producer_schema_refused")


@pytest.mark.parametrize("table", ["fact_lineage", "source_registry", "INVENTED"])
@pytest.mark.parametrize("consumer", ["producer", "draft"])
def test_raw_record_tables_are_refused_before_publication(tmp_path, table, consumer):
    cache = tmp_path / "INVENTED-cache"
    from custodian.tests.test_release_spec_draft import setup as draft_inputs

    from eii_custodian.release.spec_draft import DRAFT, draft

    if consumer == "draft":
        _, listing = draft_inputs(cache)
    else:
        inputs(cache)
    dump(
        cache / RECORD,
        dict(
            method="public-assembly.artefacts",
            method_version="1",
            tables={table: []},
            artefacts=[],
        ),
    )
    if consumer == "producer":
        refused(cache, "producer_schema_refused")
    else:
        with pytest.raises(ValueError, match=r"\Aproducer_schema_refused\Z"):
            draft(cache, listing)
        assert not (cache / DRAFT).exists()
        assert not (cache / "assembly/release_candidate.json").exists()


@pytest.mark.parametrize(
    "fault", [*RECORD_FAULTS, ["method", "method_version", "tables", "artefacts"]]
)
def test_malformed_record_is_refused_before_a_new_placement(tmp_path, fault):
    cache = tmp_path / "INVENTED-cache"
    cache.mkdir()
    valid = dict(
        method="public-assembly.artefacts", method_version="1", tables={}, artefacts=[]
    )
    before = dump(
        cache / RECORD, {**valid, **fault} if isinstance(fault, dict) else fault
    )
    with pytest.raises(ValueError, match=r"\Aproducer_schema_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert hashlib.sha256((cache / RECORD).read_bytes()).hexdigest() == before
    assert not (cache / TILES).exists()


def test_record_path_outside_artefacts_keeps_the_producer_path_refusal(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    spec = placed_inputs(cache, tmp_path)
    path = "INVENTED-source/INVENTED-evidence.json"
    digest = dump(cache / path, dict(method="INVENTED-evidence.v1"))
    entry = dict(path=path, sha256=digest)
    dump(cache / RECORD, {**record(cache), "artefacts": [entry]})
    spec["artefacts"] = [entry]
    dump(cache / producer.SPEC, spec)
    refused(cache, "producer_path_refused")


def test_producer_assembly_and_startup_accept_single_file_artefacts(tmp_path):
    from eii_product.store.release_check import check_release
    from eii_product.store.startup import StartupRefusal, verify_artefacts

    cache = tmp_path / "INVENTED-cache"
    spec = placed_inputs(cache, tmp_path)
    approve(cache)
    document = producer.produce(cache)
    assert document["artefacts"] == spec["artefacts"]
    destination = tmp_path / "INVENTED-release"
    build(cache, destination)
    checked = check_release(destination)
    assert checked.document["artefacts"] == spec["artefacts"]
    verify_artefacts(checked)
    for item in spec["artefacts"]:
        assert (destination / item["path"]).read_bytes() == (
            cache / item["path"]
        ).read_bytes()
    (destination / "artefacts/routing/INVENTED-unlisted.tar").write_bytes(b"x")
    with pytest.raises(StartupRefusal, match=r"\Astartup_inventory_mismatch\Z"):
        verify_artefacts(checked)


@settings(deadline=None)
@given(control=st.characters(categories=("Cc",)))
def test_every_control_is_refused_without_writes(tmp_path_factory, control):
    with tempfile.TemporaryDirectory(dir=tmp_path_factory.getbasetemp()) as folder:
        root = Path(folder)
        cache = root / "cache"
        cache.mkdir()
        with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
            place_artefact(cache, "artefacts/a" + control, source(root))
        assert list(cache.iterdir()) == []


def published(tmp_path: Path, body: bytes) -> list[Path]:
    """Every regular file outside the source folder whose bytes contain ``body``."""
    return [
        path
        for path in tmp_path.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and "INVENTED-source-files" not in path.parts
        and body in path.read_bytes()
    ]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("stage", ["create", "replace"])
@pytest.mark.parametrize("phase", ["artefact", "record"])
@pytest.mark.parametrize("where", ["root", "parent", "leaf"])
@pytest.mark.parametrize("replacement", ["symlink", "real"])
def test_destination_swap_is_refused_without_target_write(
    tmp_path, monkeypatch, existing, stage, phase, where, replacement
):
    cache = tmp_path / "cache"
    cache.mkdir()
    if existing:
        place_artefact(cache, TILES, source(tmp_path, b"INVENTED-first"))
    body = b"INVENTED-artefact-bytes"
    src = source(tmp_path, body)
    digest = hashlib.sha256(body).hexdigest().encode()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = cache / (TILES if phase == "artefact" else RECORD)
    victim = {"root": cache, "parent": target.parent, "leaf": target}[where]
    original_open, original_rename = os.open, pinned._renameat2
    created = 0
    swapped = False

    def swap():
        nonlocal swapped
        swapped = True
        if victim.is_symlink() or victim.exists():
            victim.rename(tmp_path / "held")
        if replacement == "symlink":
            victim.symlink_to(
                elsewhere / "absent" if where == "leaf" else elsewhere,
                target_is_directory=where != "leaf",
            )
        elif where == "leaf":
            victim.write_bytes(b"INVENTED-substitute")
        else:
            victim.mkdir()

    def opening(path, flags, *args, **kwargs):
        nonlocal created
        if stage == "create" and flags & os.O_CREAT and not swapped:
            created += 1  # the artefact temporary is first, the record's second
            if created == (1 if phase == "artefact" else 2):
                swap()
        return original_open(path, flags, *args, **kwargs)

    def renaming(parent, name, destination, flags):
        if stage == "replace" and destination == target.name and not swapped:
            swap()
        return original_rename(parent, name, destination, flags)

    monkeypatch.setattr(a.os, "open", opening)
    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, src)
    assert swapped
    assert list(elsewhere.iterdir()) == []
    assert published(tmp_path, digest) == []
    if phase == "artefact":
        assert published(tmp_path, body) == []
    if where == "leaf" and replacement == "real":
        assert target.read_bytes() == b"INVENTED-substitute"
    assert not list(tmp_path.rglob("*.partial"))


@pytest.mark.parametrize("replacement", ["symlink", "real"])
def test_root_swap_spanning_the_record_read_is_refused(
    tmp_path, monkeypatch, replacement
):
    cache = tmp_path / "cache"
    cache.mkdir()
    place_artefact(cache, FONT, source(tmp_path, b"INVENTED-first"))
    outside = tmp_path / "outside"
    dump(
        outside / RECORD,
        dict(
            method="public-assembly.artefacts",
            method_version="1",
            tables={},
            artefacts=[dict(path="artefacts/INVENTED-outside", sha256="0" * 64)],
        ),
    )
    held = tmp_path / "held"
    original_open = os.open
    state = []

    def opening(path, flags, *args, **kwargs):
        if path == PurePosixPath(RECORD).name and not flags & os.O_CREAT:
            # The swap spans the record's read and its post-read check.
            state.append("read")
            cache.rename(held)
            if replacement == "symlink":
                cache.symlink_to(outside, target_is_directory=True)
            else:
                outside.rename(cache)
        elif state == ["read"]:
            state.append("restored")
            (cache.unlink() if cache.is_symlink() else cache.rename(outside))
            held.rename(cache)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(a.os, "open", opening)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert state[0] == "read"
    if state == ["read"]:
        (cache.unlink() if cache.is_symlink() else cache.rename(outside))
        held.rename(cache)
    assert b"INVENTED-outside" not in (cache / RECORD).read_bytes()
    assert not (cache / TILES).exists()


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("phase", ["artefact", "record"])
def test_cleanup_never_unlinks_a_name_the_rename_consumed(
    tmp_path, monkeypatch, existing, phase
):
    cache = tmp_path / "cache"
    cache.mkdir()
    if existing:
        place_artefact(cache, TILES, source(tmp_path, b"INVENTED-first"))
    target = cache / (TILES if phase == "artefact" else RECORD)
    original_rename = pinned._renameat2
    planted = []

    def renaming(parent, name, destination, flags):
        original_rename(parent, name, destination, flags)
        if destination == target.name and not planted:
            planted.append(target.parent / name)
            if flags == pinned.RENAME_EXCHANGE:
                # The exchange left the displaced leaf at the temporary name.
                planted[0].rename(tmp_path / "displaced")
            planted[0].write_bytes(b"INVENTED-planted")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    if existing:
        # The displaced leaf no longer carries its identity: roll back, refuse,
        # and leave the planted entry in place of the published one.
        with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
            place_artefact(cache, TILES, source(tmp_path))
        assert target.read_bytes() == b"INVENTED-planted"
    else:
        placed = place_artefact(cache, TILES, source(tmp_path))
        assert planted[0].read_bytes() == b"INVENTED-planted"
        assert record(cache)["artefacts"] == [placed]
    assert planted


@pytest.mark.parametrize(
    "where", ["ancestor", "root", "parent", "leaf", "dangling", "record"]
)
def test_other_symlink_destinations_are_refused(tmp_path, where):
    cache = tmp_path / "cache"
    cache.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    if where == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        cache = alias / "cache"
    elif where == "root":
        cache.rmdir()
        cache.symlink_to(elsewhere, target_is_directory=True)
    else:
        target = cache / (RECORD if where == "record" else TILES)
        if where == "parent":
            target = target.parent
        target.parent.mkdir(parents=True, exist_ok=True)
        if where == "record":
            stored = tmp_path / "other-record"
            dump(
                stored,
                dict(
                    method="public-assembly.artefacts",
                    method_version="1",
                    tables={},
                    artefacts=[],
                ),
            )
            target.symlink_to(stored)
        else:
            target.symlink_to(
                elsewhere / "absent" if where == "dangling" else elsewhere
            )
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert list(elsewhere.iterdir()) == []


@pytest.mark.parametrize("body", [b"", b"x" * ((1 << 20) + 1)])
def test_empty_and_multichunk_copies_keep_their_hash(tmp_path, body):
    cache = tmp_path / "cache"
    cache.mkdir()
    placed = place_artefact(cache, TILES, source(tmp_path, body))
    assert (cache / TILES).read_bytes() == body
    assert placed["sha256"] == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("stage", ["open", "hash"])
def test_source_swaps_keep_the_opened_bytes_and_hash(tmp_path, monkeypatch, stage):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = source(tmp_path)
    body = src.read_bytes()
    replacement = source(tmp_path, b"INVENTED-replacement")
    original_open, original_sha256 = os.open, hashlib.sha256

    def swap():
        if replacement.exists():
            os.replace(replacement, src)

    def opening(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if stage == "open" and Path(path) == src:
            swap()
        return descriptor

    class Digest:
        def __init__(self):
            self.inner = original_sha256()

        def update(self, chunk):
            self.inner.update(chunk)
            swap()

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(a.os, "open", opening)
    if stage == "hash":
        monkeypatch.setattr(a.hashlib, "sha256", Digest)
    placed = place_artefact(cache, TILES, src)
    assert src.read_bytes() == b"INVENTED-replacement"
    assert (cache / TILES).read_bytes() == body
    assert placed["sha256"] == original_sha256(body).hexdigest()


def test_missing_phase_with_matching_file_and_spec_is_refused(tmp_path):
    cache = tmp_path / "cache"
    placed_inputs(cache, tmp_path)
    (cache / RECORD).unlink()
    refused(cache, "producer_chain_incomplete")


@pytest.mark.parametrize("tamper", ["leaf", "temporary"])
@pytest.mark.parametrize("phase", ["artefact", "record"])
def test_entry_substitution_during_copy_is_refused(
    tmp_path, monkeypatch, tamper, phase
):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = source(tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"INVENTED-unchanged")
    original_fsync = os.fsync
    calls = 0

    def syncing(descriptor):
        nonlocal calls
        calls += 1
        if calls == (1 if phase == "artefact" else 2):
            target = cache / (TILES if phase == "artefact" else RECORD)
            if tamper == "temporary":
                target = next(
                    p for p in target.parent.iterdir() if p.name.startswith(".")
                )
                target.unlink()
            target.symlink_to(outside)
        return original_fsync(descriptor)

    monkeypatch.setattr(a.os, "fsync", syncing)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, src)
    assert outside.read_bytes() == b"INVENTED-unchanged"
    if tamper == "temporary":
        assert not (cache / (TILES if phase == "artefact" else RECORD)).is_symlink()
    assert (cache / RECORD).is_symlink() or not (cache / RECORD).is_file()
    # Cleanup unlinks the temporary name only while it holds the owned file:
    # a substituted temporary entry stays, unfollowed.
    left = list(cache.rglob("*.partial"))
    assert all(path.is_symlink() for path in left)
    assert len(left) == (tamper == "temporary")


def test_symlink_inserted_during_directory_open_is_not_followed(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    original_open = os.open
    swapped = False

    def opening(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == "routing" and not swapped:
            swapped = True
            parent = cache / "artefacts/routing"
            parent.rmdir()
            parent.symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(a.os, "open", opening)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, "artefacts/routing/nested/a", source(tmp_path))
    assert swapped
    assert list(outside.iterdir()) == []
    assert not (cache / RECORD).exists()


def test_temporary_collision_is_refused_without_overwriting_it(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    original_open = os.open
    planted = False
    collision = None

    def opening(path, flags, *args, **kwargs):
        nonlocal planted, collision
        if flags & os.O_CREAT and not planted:
            planted = True
            collision = cache / "artefacts/routing" / path
            descriptor = original_open(path, os.O_CREAT | os.O_WRONLY, 0o600, **kwargs)
            os.write(descriptor, b"INVENTED-collision")
            os.close(descriptor)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(a.os, "open", opening)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert planted
    assert collision.read_bytes() == b"INVENTED-collision"
    assert not (cache / RECORD).exists()


def test_root_substitution_before_destination_open_is_refused(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = source(tmp_path)
    held = tmp_path / "held"
    original_open = os.open

    def opening(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if Path(path) == src:
            cache.rename(held)
            cache.mkdir()
        return descriptor

    monkeypatch.setattr(a.os, "open", opening)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, src)
    assert list(cache.iterdir()) == []
    assert not (held / RECORD).exists()


def test_all_destination_io_uses_pinned_directory_descriptors(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = source(tmp_path)
    original_open, original_unlink = os.open, os.unlink
    original_rename = pinned._renameat2
    operations = set()

    def opening(path, flags, *args, **kwargs):
        if Path(path) != src:
            if flags & os.O_CREAT:
                assert kwargs["dir_fd"] is not None
                assert not Path(path).is_absolute()
                operations.add("temporary")
            elif flags & os.O_DIRECTORY:
                assert flags & os.O_NOFOLLOW
                operations.add("directory")
            else:
                assert kwargs["dir_fd"] is not None
                assert flags & os.O_NOFOLLOW
                operations.add("read")
        return original_open(path, flags, *args, **kwargs)

    def renaming(parent, name, destination, flags):
        assert isinstance(parent, int)
        assert Path(name).name == name and Path(destination).name == destination
        assert flags in (pinned.RENAME_NOREPLACE, pinned.RENAME_EXCHANGE)
        operations.add(flags)
        return original_rename(parent, name, destination, flags)

    def unlinking(path, *args, **kwargs):
        assert kwargs["dir_fd"] is not None
        assert Path(path).name == path
        operations.add("cleanup")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(a.os, "open", opening)
        context.setattr(pinned, "_renameat2", renaming)
        context.setattr(a.os, "unlink", unlinking)
        place_artefact(cache, TILES, src)
        assert operations == {"temporary", "directory", pinned.RENAME_NOREPLACE}
        place_artefact(cache, TILES, src)
    assert operations == {
        "temporary",
        "directory",
        "read",
        "cleanup",
        pinned.RENAME_NOREPLACE,
        pinned.RENAME_EXCHANGE,
    }


def test_failure_cleanup_preserves_a_substituted_destination(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    original_rename = pinned._renameat2
    target = cache / TILES

    def renaming(parent, name, destination, flags):
        original_rename(parent, name, destination, flags)
        if destination == target.name:
            target.rename(tmp_path / "held-file")
            target.write_bytes(b"INVENTED-substituted")

    monkeypatch.setattr(pinned, "_renameat2", renaming)
    with pytest.raises(ValueError, match=r"\Aartefact_path_refused\Z"):
        place_artefact(cache, TILES, source(tmp_path))
    assert target.read_bytes() == b"INVENTED-substituted"
    assert not (cache / RECORD).exists()
    assert not list(cache.rglob("*.partial"))


@settings(deadline=None)
@given(
    step=st.integers(min_value=0, max_value=60),
    where=st.sampled_from(["root", "parent", "leaf"]),
    phase=st.sampled_from(["artefact", "record"]),
    replacement=st.sampled_from(["symlink", "real"]),
    existing=st.booleans(),
)
def test_a_substitution_at_any_identity_step_never_escapes(
    tmp_path_factory, step, where, phase, replacement, existing
):
    """Swap root, parent or leaf at the n-th identity read: refuse or stay inside."""
    with tempfile.TemporaryDirectory(dir=tmp_path_factory.getbasetemp()) as folder:
        root = Path(folder)
        cache = root / "cache"
        cache.mkdir()
        if existing:
            place_artefact(cache, TILES, source(root, b"INVENTED-first"))
        elsewhere = root / "elsewhere"
        elsewhere.mkdir()
        target = cache / (TILES if phase == "artefact" else RECORD)
        victim = {"root": cache, "parent": target.parent, "leaf": target}[where]
        original = pinned._identity
        calls = 0

        def identity(parent, name):
            nonlocal calls
            calls += 1
            if calls == step:
                if victim.is_symlink() or victim.exists():
                    victim.rename(root / "held")
                if replacement == "symlink":
                    victim.symlink_to(elsewhere, target_is_directory=where != "leaf")
                elif where == "leaf":
                    victim.write_bytes(b"INVENTED-substitute")
                else:
                    victim.mkdir(parents=True)
            return original(parent, name)

        pinned._identity = identity
        try:
            placed = place_artefact(cache, TILES, source(root))
        except ValueError as error:
            # A record leaf replaced before it is pinned is a malformed record.
            malformed = (where, phase, replacement) == ("leaf", "record", "real")
            assert str(error) == "artefact_path_refused" or (
                malformed and str(error) == "producer_schema_refused"
            )
            placed = None
        finally:
            pinned._identity = original
        assert list(elsewhere.iterdir()) == []
        if placed is not None:
            # Success only when every swap preceded the pins it would defeat.
            assert (cache / TILES).read_bytes() == b"INVENTED-artefact-bytes"
            assert placed in record(cache)["artefacts"]
