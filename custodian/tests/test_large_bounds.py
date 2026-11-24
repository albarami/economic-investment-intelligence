"""L-1717: invented bounded streams, completeness and receipt evidence."""

import hashlib
import io
from dataclasses import replace

import pytest
from custodian.tests.test_large_intake import stream
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import large, registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot


@pytest.fixture(scope="module")
def entries():
    return {entry.key: entry for entry in registry.load_registry()}


@pytest.mark.parametrize(
    "key", [key for key in large.REQUIRED_KEYS if "ovt/" not in key]
)
def test_unconfirmed_bound_refuses_before_stream(entries, key):
    entry = replace(entries[key], stream_max_bytes=None)
    with pytest.raises(large.IntakeError, match=r"^bound_unconfirmed$"):
        large.receive(entry, lambda _url: pytest.fail("stream opened"), io.BytesIO())


GIB = 1024**3
# Ruling L-1723: the smallest whole number of GiB at or above four times each
# key's receipted bytes; reviewed by the lead, never derived from a header.
REVIEWED_CEILINGS = {
    "cus_imp_2019": 2 * GIB,
    "trade_ext/qatar-imports-2014-2018": 2 * GIB,
    "bldg_wsf3d": 8 * GIB,
    "bldg_gba/e050_n25_e055_n20": 1 * GIB,
    "bldg_gba/e050_n30_e055_n25": 1 * GIB,
}


def test_reviewed_ceilings_are_pinned(entries):
    keys = {key for key in large.REQUIRED_KEYS if "ovt/" not in key}
    assert set(REVIEWED_CEILINGS) == keys
    for key, ceiling in REVIEWED_CEILINGS.items():
        assert entries[key].stream_max_bytes == ceiling


def test_undeclared_short_body_refuses_before_read(entries):
    entry = replace(entries["bldg_wsf3d"], stream_max_bytes=20)

    def unread():
        pytest.fail("unverifiable body read")
        yield b"x" * 10

    sink = io.BytesIO()
    with pytest.raises(large.IntakeError, match=r"^length_undeclared$"):
        large.receive(entry, stream(entry, unread()), sink)
    assert sink.getvalue() == b""


@pytest.mark.parametrize("declared", [2, 4])
def test_declared_body_mismatch(entries, declared):
    entry = replace(entries["bldg_wsf3d"], stream_max_bytes=10)
    with pytest.raises(large.IntakeError, match=r"^length_mismatch$"):
        large.receive(entry, stream(entry, [b"abc"], declared), io.BytesIO())


def test_source_ceiling_refuses_declared_before_read(entries):
    entry = replace(entries["bldg_wsf3d"], stream_max_bytes=2)

    def unread():
        pytest.fail("over-ceiling body was read")
        yield b"abc"

    sink = io.BytesIO()
    with pytest.raises(large.IntakeError, match=r"^body_bytes$"):
        large.receive(entry, stream(entry, unread(), 3), sink)
    assert sink.getvalue() == b""


def test_source_ceiling_counts_before_writing_chunk(entries):
    entry = replace(entries["bldg_wsf3d"], stream_max_bytes=2)
    sink = io.BytesIO()
    with pytest.raises(large.IntakeError, match=r"^body_bytes$"):
        large.receive(entry, stream(entry, [b"a", b"bc"], 2), sink)
    assert sink.getvalue() == b"a"


@pytest.mark.parametrize("declared", [None, 3])
def test_receipt_records_closed_length_boolean(entries, tmp_path, declared):
    entry = replace(
        entries["places_ovt/part-00014"],
        basis_note="recorded_bytes: 3\nrecorded_etag: SYN-tag",
    )
    result = large.fetch_large(
        entry,
        lambda _url: pytest.fail("metadata read"),
        stream(entry, [b"SYN"], declared, '"SYN-tag"'),
        tmp_path,
        lambda: "2026-11-24T00:00:00Z",
        lambda _seconds: None,
    )
    receipt = read_snapshot(tmp_path / entry.key, result.digest).sidecar
    assert receipt["declared_length_present"] is (declared is not None)


@pytest.mark.parametrize(
    "bound", [True, False, 0, -1, "3", {}, [], {"toString": None}, 1.5]
)
def test_registry_rejects_bad_bound_leaf(entries, bound):
    document = registry.read_yaml(registry.registry_path())
    row = next(row for row in document["sources"] if row["key"] == "bldg_wsf3d")
    row["stream_max_bytes"] = bound
    with pytest.raises(registry.RegistryError, match=r"^stream_max_bytes$"):
        registry._entry(row)


@pytest.mark.parametrize("bound", [None, 1, 7, 2**80])
def test_registry_loads_bound_through_closed_schema(monkeypatch, bound):
    document = registry.read_yaml(registry.registry_path())
    source = next(row for row in document["sources"] if row["key"] == "bldg_wsf3d")
    source["stream_max_bytes"] = bound
    monkeypatch.setattr(registry, "read_yaml", lambda _path: document)
    loaded = {entry.key: entry for entry in registry.load_registry()}
    assert loaded["bldg_wsf3d"].stream_max_bytes == bound


@pytest.mark.parametrize("field", ["stream_max_bytes", "declared_length", "chunk"])
@pytest.mark.parametrize("hostile", [{"toString": None}, 7, None, []])
def test_hostile_stream_leaves_have_closed_outcomes(entries, field, hostile):
    entry = replace(entries["bldg_wsf3d"], stream_max_bytes=10)
    declared, chunks = 1, [b"x"]
    reason = None
    if field == "stream_max_bytes":
        entry = replace(entry, stream_max_bytes=hostile)
        if hostile != 7:
            reason = "bound_unconfirmed"
    elif field == "declared_length":
        declared = hostile
        reason = (
            "length_undeclared"
            if hostile is None
            else ("length_mismatch" if hostile == 7 else "declared_length")
        )
    else:
        chunks = [hostile]
        reason = "stream_chunk"
    if reason:
        with pytest.raises(large.IntakeError, match=f"^{reason}$"):
            large.receive(entry, stream(entry, chunks, declared), io.BytesIO())
    else:
        assert (
            large.receive(entry, stream(entry, chunks, declared), io.BytesIO()).nbytes
            == 1
        )


@pytest.mark.parametrize("reason", ["bound_unconfirmed", "length_undeclared"])
def test_new_intake_reasons_stay_closed_in_assembly(reason):
    from eii_custodian.publicdata.assembly_refusals import closed_reason

    assert closed_reason("require_complete", large.IntakeError(reason)) == reason


def test_bound_schema_reason_stays_closed_in_assembly():
    from eii_custodian.publicdata.assembly_refusals import closed_reason

    assert (
        closed_reason("require_complete", registry.RegistryError("stream_max_bytes"))
        == "stream_max_bytes"
    )


def test_repeated_snapshot_records_each_length_observation(entries, tmp_path):
    import json

    entry = replace(
        entries["places_ovt/part-00014"],
        basis_note="recorded_bytes: 3\nrecorded_etag: SYN-tag",
    )
    for declared in (None, 3):
        large.fetch_large(
            entry,
            lambda _url: pytest.fail("metadata read"),
            stream(entry, [b"SYN"], declared, '"SYN-tag"'),
            tmp_path,
            lambda: "2026-11-24T00:00:00Z",
            lambda _seconds: None,
        )
    checks = [
        json.loads(path.read_text())
        for path in (tmp_path / entry.key / "checks").glob("*.json")
    ]
    assert {check["declared_length_present"] for check in checks} == {True, False}


@given(
    chunks=st.lists(st.binary(max_size=8), max_size=8),
    declared=st.one_of(st.none(), st.integers(min_value=0, max_value=70)),
    bound=st.integers(min_value=1, max_value=70),
    exact=st.booleans(),
)
@example(chunks=[b"a", b"bc"], declared=3, bound=3, exact=False)
@example(chunks=[b"abc"], declared=None, bound=3, exact=True)
@example(chunks=[b"a", b"bc"], declared=None, bound=3, exact=False)
@example(chunks=[], declared=0, bound=1, exact=False)
@example(chunks=[b"", b"a", b""], declared=1, bound=1, exact=False)
@example(chunks=[b"a", b"bc"], declared=2, bound=2, exact=False)
def test_chunk_splits_accept_iff_complete_and_bounded(
    entries, chunks, declared, bound, exact
):
    body = b"".join(chunks)
    if exact:
        entry = replace(
            entries["places_ovt/part-00014"],
            basis_note=f"recorded_bytes: {bound}\nrecorded_etag: SYN-tag",
        )
    else:
        entry = replace(entries["bldg_wsf3d"], stream_max_bytes=bound)
    complete = len(body) == (bound if exact else declared)
    accepted = bool(body) and complete and len(body) <= bound
    if exact and declared is not None:
        accepted = accepted and declared == bound
    sink = io.BytesIO()
    try:
        received = large.receive(
            entry, stream(entry, chunks, declared, '"SYN-tag"'), sink
        )
    except large.IntakeError as error:
        assert not accepted
        assert str(error) in {
            "body_bytes",
            "length_undeclared",
            "length_mismatch",
            "size_mismatch",
            "empty_body",
        }
    else:
        assert accepted
        assert sink.getvalue() == body
        assert received.sha256 == hashlib.sha256(body).hexdigest()
        assert received.declared_length_present is (declared is not None)
    assert len(sink.getvalue()) <= bound
