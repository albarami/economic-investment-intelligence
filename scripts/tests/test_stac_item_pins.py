"""Pin proposals on invented, receipted snapshots only."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import stac_item_pins as pins
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.review.cache_fixture import write_cached


@pytest.fixture
def fixture(tmp_path: Path) -> tuple[Path, Entry]:
    entry = replace(
        next(e for e in load_registry() if e.key == "bldg_ovt/stac-collection"),
        url="https://syn.invalid/collection.json",
    )
    cache = tmp_path / "cache"
    return cache, entry


def store(cache: Path, entry: Entry, body: bytes = b"SYN snapshot") -> str:
    return write_cached(cache, entry, body, select=False).stem


def test_proposal_only_adds_absent_keys_and_leaves_same_pin(
    fixture: tuple[Path, Entry],
) -> None:
    cache, entry = fixture
    digest = store(cache, entry)
    assert pins.propose(cache, (entry,)) == {entry.key: digest}
    path = cache / "snapshot_pins.json"
    original = json.dumps({entry.key: digest, "SYN-other": "a" * 64}).encode()
    path.write_bytes(original)
    assert pins.propose(cache, (entry,)) == {}
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "case,reason",
    [
        ("zero", "stac_pin_snapshot_missing"),
        ("two", "stac_pin_snapshot_ambiguous"),
        ("receipt", "snapshot_hash_mismatch"),
        ("body", "snapshot_hash_mismatch"),
        ("different", "stac_pin_conflict"),
        ("key", "stac_pin_snapshot_key"),
        ("source", "stac_pin_snapshot_key"),
    ],
)
def test_each_refusal(fixture: tuple[Path, Entry], case: str, reason: str) -> None:
    cache, entry = fixture
    if case != "zero":
        digest = store(cache, entry)
    if case == "two":
        store(cache, entry, b"SYN second snapshot")
    elif case in {"receipt", "body"}:
        snapshot = read_snapshot(cache / entry.key, digest)
        path = snapshot.receipt_path if case == "receipt" else snapshot.path
        path.write_bytes(
            path.read_bytes() + b" "
            if case == "receipt"
            else b"X" + path.read_bytes()[1:]
        )
    elif case == "different":
        (cache / "snapshot_pins.json").write_text(json.dumps({entry.key: "a" * 64}))
    elif case in {"key", "source"}:
        # One input changed: a receipted snapshot's declared identity.
        import shutil

        shutil.rmtree(cache / entry.key)
        changed = (
            replace(entry, key="SYN-other")
            if case == "key"
            else replace(entry, source_id="SYN-other")
        )
        store(cache, changed)
        if case == "key":
            (cache / changed.key).rename(cache / entry.key)
    with pytest.raises(ValueError, match=r"^" + reason + "$"):
        pins.propose(cache, (entry,))


def test_output_never_writes_pins_and_never_overwrites(
    fixture: tuple[Path, Entry], tmp_path: Path
) -> None:
    cache, entry = fixture
    digest = store(cache, entry)
    for output in (cache / "snapshot_pins.json", cache / "other.json"):
        with pytest.raises(ValueError, match=r"^stac_pin_output_in_cache$"):
            pins.write_proposal(cache, (entry,), output)
        assert not output.exists()
    output = tmp_path / "proposal.json"
    output.write_bytes(b"SYN existing")
    with pytest.raises(FileExistsError, match="File exists"):
        pins.write_proposal(cache, (entry,), output)
    assert output.read_bytes() == b"SYN existing"
    output.unlink()
    pins.write_proposal(cache, (entry,), output)
    assert json.loads(output.read_bytes()) == {entry.key: digest}
    assert not (cache / "snapshot_pins.json").exists()


@given(
    st.lists(st.binary(min_size=1, max_size=40), min_size=1, max_size=3, unique=True)
)
def test_snapshot_cardinality_property(
    tmp_path_factory: pytest.TempPathFactory, bodies: list[bytes]
) -> None:
    # A new directory per example avoids a history shared by generated cases.
    cache = tmp_path_factory.mktemp("pins")
    entry = next(e for e in load_registry() if e.key == "bldg_ovt/stac-collection")
    for body in bodies:
        store(cache, entry, body)
    if len(bodies) == 1:
        assert pins.propose(cache, (entry,)) == {entry.key: sha256_hex(bodies[0])}
    else:
        with pytest.raises(ValueError, match=r"^stac_pin_snapshot_ambiguous$"):
            pins.propose(cache, (entry,))


def test_cli_success_and_fixed_failure(
    fixture: tuple[Path, Entry],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache, entry = fixture
    monkeypatch.setattr(pins, "load_registry", lambda path: (entry,))
    output = tmp_path / "proposed.json"
    assert pins.main([str(cache), str(output)]) == 1
    assert capsys.readouterr().err == "stac_item_pins: proposal_refused\n"
    assert not output.exists()
    digest = store(cache, entry)
    assert pins.main([str(cache), str(output)]) == 0
    assert json.loads(output.read_bytes()) == {entry.key: digest}
    assert pins.main([str(cache), str(output)]) == 1
    assert capsys.readouterr().err == "stac_item_pins: proposal_refused\n"


def test_non_stac_entries_are_not_pin_targets(fixture: tuple[Path, Entry]) -> None:
    cache, entry = fixture
    other = replace(entry, key="bldg_ovt/part-00288")
    store(cache, other)
    assert pins.propose(cache, (other,)) == {}
