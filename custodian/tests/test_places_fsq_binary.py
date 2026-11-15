"""Hand-encoded compact-protocol cases, independent of the fixture writer."""

import struct

import pytest

from eii_custodian.publicdata.places_fsq import footer as f
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError


def test_fsq_footer_slice_and_single_stop():
    assert f._footer_bytes(b"PAR1payload\x00\x01\x00\x00\x00PAR1") == b"\x00"
    assert f.read_summary(b"PAR1\x00\x01\x00\x00\x00PAR1") == f.SummaryFooter((), None)
    for data in [
        b"XXXX\x00\x01\x00\x00\x00PAR1",
        b"PAR1\x00\xff\xff\xff\xffPAR1",
        b"PAR1\x00\x02\x00\x00\x00PAR1",
    ]:
        with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
            f._footer_bytes(data)


@pytest.mark.parametrize(
    "value, encoded",
    [
        (0, b"\x00"),
        (-1, b"\xff" * 9 + b"\x01"),
        (1, b"\x01"),
        (128, b"\x80\x01"),
        (16385, b"\x81\x80\x01"),
        (-2, b"\xfe" + b"\xff" * 8 + b"\x01"),
        (1 << 65, b"\x80" * 9 + b"\x04"),
    ],
)
def test_fsq_unsigned_varint_bytes(value, encoded):
    buffer = bytearray()
    f._uvarint(buffer, value)
    assert bytes(buffer) == encoded
    assert f._FileReader(encoded)._varint() == (
        value if value >= 0 else (1 << 64) + value
    )


@pytest.mark.parametrize(
    "value, encoded",
    [
        (0, b"\x00"),
        (-1, b"\x01"),
        (64, b"\x80\x01"),
        (1 << 63, b"\x81" + b"\x80" * 8 + b"\x02"),
    ],
)
def test_fsq_zigzag_writer_bytes(value, encoded):
    buffer = bytearray()
    f._Writer._zigzag(buffer, value)
    assert bytes(buffer) == encoded


def test_fsq_long_and_short_field_headers():
    w = f._Writer()
    w._begin()
    for field in (1, 16, 16, 15, 31):
        w._field(field, 3)
    assert bytes(w.buffer) == b"\x13\xf3\x03\x20\x03\x1e\x03\x3e"
    r = f._FileReader(bytes(w.buffer) + b"\x00")
    r._begin()
    assert [r._header() for _ in range(6)] == [
        (3, 1),
        (3, 16),
        (3, 16),
        (3, 15),
        (3, 31),
        (None, 0),
    ]


@pytest.mark.parametrize(
    "size, expected",
    [(0, b"\x08"), (14, b"\xe8"), (15, b"\xf8\x0f"), (128, b"\xf8\x80\x01")],
)
def test_fsq_list_headers_by_hand(size, expected):
    w = f._Writer()
    w._list_header(8, size)
    assert bytes(w.buffer) == expected
    assert f._FileReader(expected + b"\x00" * size)._list_header() == (size, 8)


@pytest.mark.parametrize(
    "kind, data",
    [
        (1, b""),
        (2, b""),
        (3, b"\x7f"),
        (4, b"\x80\x01"),
        (5, b"\x80\x01"),
        (6, b"\x80\x01"),
        (7, b"abcdefgh"),
        (8, b"\x03abc"),
        (9, b"\x23ab"),
        (10, b"\x23ab"),
        (11, b"\x00"),
        (11, b"\x01\x38z\x01x"),
        (12, b"\x13a\x00"),
    ],
)
def test_fsq_skip_consumes_exact_payload(kind, data):
    reader = f._FileReader(data + b"end")
    reader._skip(kind)
    assert reader._take(3) == b"end"


def test_fsq_reader_replacement_decoding_and_empty_fields():
    assert f._FileReader(b"\x18\x01\xff\x00")._chunk() is None
    # Chunk's empty metadata produces an empty path and missing bounds.
    assert f._FileReader(b"\x3c\x00\x00")._chunk() == f.ChunkStat(
        "", (), None, None, None
    )
    chunk = f._FileReader(b"\x18\x01\xff\x2c\x00\x00")._chunk()
    assert chunk == f.ChunkStat("\ufffd", (), None, None, None)
    assert f._FileReader(b"\x18\x01\xff")._path() == ("\ufffd",)
    assert f._FileReader(b"\x18\x01\xff\x18\x01\xff\x00")._pair() == (
        "\ufffd",
        "\ufffd",
    )
    assert f._FileReader(b"\x00")._pair() == ("", None)
    assert f._FileReader(b"\x00")._row_group() == ()
    assert f._FileReader(b"\x00")._column() == ((), None, None, None, None, None)


@pytest.mark.parametrize(
    "method, data, expected",
    [
        ("_row_groups", b"\x21\x02\x01", []),
        ("_chunks", b"\x21\x02\x01", (None, None)),
        ("_path", b"\x21\x02\x01", ()),
        ("_geo_pairs", b"\x21\x02\x01", None),
        ("_column_orders", b"\x21\x02\x01", (False, False)),
    ],
)
def test_fsq_known_lists_skip_boolean_elements(method, data, expected):
    reader = f._FileReader(data + b"z")
    assert getattr(reader, method)() == expected
    assert reader._take(1) == b"z"


def test_fsq_statistics_missing_bounds_and_deprecated_bytes():
    assert f._FileReader(b"\x00")._statistics(5) == (None, None, None, None)
    payload = (
        b"\x18\x08"
        + struct.pack("<d", 52.0)
        + b"\x18\x08"
        + struct.pack("<d", 50.0)
        + b"\x00"
    )
    assert f._FileReader(payload)._statistics(5) == (50.0, 52.0, 50.0, 52.0)
    assert f._FileReader(payload)._statistics(None) == (None, None, None, None)
    assert f._float(b"1234567", 5) is None
    assert f._float(struct.pack("<d", 1.0), 4) is None
    assert f._four((1, 2, 3, 4)) is None
    assert f._pair((True, 1)) is False
    assert f._pair(("x", 1)) is False
    assert f._bbox_from_geo('{"columns":{"x":1,"y":{}},"bbox":[1,2,3,4]}') == (
        1.0,
        2.0,
        3.0,
        4.0,
    )


def test_fsq_depth_restored_after_known_and_unknown_containers():
    for method in ("_column_orders", "_row_groups", "_chunks", "_path", "_geo_pairs"):
        reader = f._FileReader(b"\x01")
        reader._container_depth = 7
        getattr(reader, method)()
        assert reader._container_depth == 7
    reader = f._FileReader(b"\x01")
    reader._container_depth = 7
    reader._skip(9)
    assert reader._container_depth == 7
    reader = f._FileReader(b"")
    reader._last = [0] * 32
    reader._container_depth = 32
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        reader._begin()


@pytest.mark.parametrize(
    "method,fields,expected",
    [
        ("_row_group", b"\x15\x80\x01\x19\x01", ()),
        ("_chunk", b"\x15\x80\x01\x28\x00", None),
        ("_column", b"\x85\x80\x01\x49\x01", ((), None, None, None, None, None)),
        ("_pair", b"\x15\x00\x15\x00\x18\x00", ("", None)),
    ],
)
def test_fsq_wrong_field_types_remain_unknown(method, fields, expected):
    assert getattr(f._FileReader(fields + b"\x00"), method)() == expected


def test_fsq_statistics_skip_unknown_field_and_read_deprecated_only():
    # Field 6 with i32 type, and field 7 binary are both unknown statistics.
    assert f._FileReader(b"\x65\x80\x01\x18\x00\x00")._statistics(5) == (
        None,
        None,
        None,
        None,
    )
    assert f._FileReader(b"\x00")._statistics(None) == (None, None, None, None)
    assert f._unzigzag(1) == -1
    assert f._unzigzag(3) == -2
    # Shift limit is the existing reader's policy; this pass leaves it unchanged.
    assert f._FileReader(b"\x80" * 10 + b"\x01")._varint() == 1 << 70
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        f._FileReader(b"\x80" * 11 + b"\x01")._varint()


def test_fsq_container_size_counts_only_remaining_bytes():
    reader = f._FileReader(b"\x00\x21\x01")
    reader._take(1)
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        reader._list_header()
    assert f._FileReader(b"\x11\x01")._list_header() == (1, 1)


def test_fsq_map_size_refuses_at_read_site():
    reader = f._FileReader(b"\x05\x11\x01\x01\x01")
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        reader._skip(f._MAP)
    assert reader._at == 1


def test_fsq_non_geo_metadata_is_not_bbox():
    w = f._Writer()
    w._list_header(12, 1)
    w._key_value("not-geo", '{"bbox":[1,2,3,4]}')
    assert f._FileReader(bytes(w.buffer))._geo_pairs() is None


def test_fsq_writer_default_order_and_bbox_type():
    w = f._Writer()
    assert w.column_orders == (1, 1)
    assert w.deprecated_bounds is False
    w.file_metadata(
        (
            dict(
                file_path="a.parquet",
                longitude=(1.0, 2.0),
                latitude=(3.0, 4.0),
                geo_bbox=[1.0, 2.0, 3.0, 4.0],
            ),
        ),
        None,
    )
    assert (
        f._FileReader(bytes(w.buffer)).file_metadata().row_groups[0][0].geo_bbox is None
    )


def test_fsq_recursion_exception_is_always_named(monkeypatch):
    def exhausted(self):
        raise RecursionError("invented exhausted stack")

    monkeypatch.setattr(f._FileReader, "file_metadata", exhausted)
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        f.read_summary(b"PAR1\x00\x01\x00\x00\x00PAR1")


def test_fsq_wrong_order_field_kind_is_skipped():
    assert f._FileReader(
        b"\x78\x10" + b"a" * 16 + b"\x00"
    ).file_metadata() == f.SummaryFooter((), None)


def test_fsq_deep_geo_inside_footer_records_no_bbox():
    w = f._Writer()
    w._begin()
    w._field(5, 9)
    w._list_header(12, 1)
    w._key_value("geo", "[" * 100000 + "0" + "]" * 100000)
    w._end()
    assert f._FileReader(bytes(w.buffer)).file_metadata() == f.SummaryFooter((), None)


def test_fsq_footer_length_uses_unsigned_wire_primitive(monkeypatch):
    from types import SimpleNamespace

    # Exercise the wire type at its signed boundary without allocating a huge file.
    real_pack = struct.pack
    real_unpack_from = struct.unpack_from

    def pack(fmt, value):
        if fmt in ("<I", "<i"):
            assert real_pack(fmt, 1 << 31) == b"\x00\x00\x00\x80"
        return real_pack(fmt, value)

    def unpack_from(fmt, body, offset):
        assert struct.unpack(fmt, b"\x00\x00\x00\x80") == (1 << 31,)
        return real_unpack_from(fmt, body, offset)

    monkeypatch.setattr(
        f,
        "struct",
        SimpleNamespace(pack=pack, unpack_from=unpack_from, unpack=struct.unpack),
    )
    body = f.metadata_bytes([], dataset_geo_bbox=None)
    assert f.read_summary(body) == f.SummaryFooter((), None)
