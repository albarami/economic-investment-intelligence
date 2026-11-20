"""Invented compact footers for the second format fix pass."""

import math
import struct
import time

import pytest
from custodian.tests.fixtures.places_fsq.invented import listing

from eii_custodian.publicdata.places_fsq import footer as f
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.parse import _connect
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX, select_partitions


def envelope(payload):
    return b"PAR1" + payload + struct.pack("<I", len(payload)) + b"PAR1"


def ordered_footer(
    order, physical=5, low=51.0, high=51.5, *, nan=None, null=0, extra_int96=False
):
    """Hand-encode two compact ColumnChunks, independently of the footer writer.

    Fields: ColumnMetaData type/path/num_values/statistics; Statistics
    null_count/max_value/min_value/nan_count. All invented counts fit one byte.
    """

    def bound(value):
        if isinstance(value, bytes):
            return value
        if physical == 3:
            return struct.pack("<qi", int(value), 1)
        return struct.pack("<f" if physical == 4 else "<d", value)

    chunks = []
    for name, minimum, maximum in [
        (b"longitude", low, high),
        (b"latitude", 25.0, 25.5),
    ]:
        lower, upper = bound(minimum), bound(maximum)
        statistics = (
            b"\x36"
            + bytes([null << 1])
            + b"\x28"
            + bytes([len(upper)])
            + upper
            + b"\x18"
            + bytes([len(lower)])
            + lower
        )
        if nan is not None:
            statistics += b"\x36" + bytes([nan << 1])
        column = (
            b"\x15"
            + bytes([physical << 1])
            + b"\x29\x18"
            + bytes([len(name)])
            + name
            + b"\x26\x06\x7c"
            + statistics
            + b"\x00\x00"
        )
        chunks.append(b"\x18\x0cnear.parquet\x2c" + column + b"\x00")
    if extra_int96:
        # A valid third, non-coordinate INT96 column uses member 3.
        statistics = (
            b"\x36\x00\x28\x0c"
            + struct.pack("<qi", 2, 1)
            + b"\x18\x0c"
            + struct.pack("<qi", 1, 1)
            + b"\x00"
        )
        column = b"\x15\x06\x29\x18\x09timestamp\x26\x06\x7c" + statistics + b"\x00"
        chunks.append(b"\x18\x0cnear.parquet\x2c" + column + b"\x00")
    # FileMetaData row_groups followed by column_orders; each union is empty.
    union = bytes([(order << 4) | 12]) + b"\x00\x00"
    orders = union * 2 + (b"\x3c\x00\x00" if extra_int96 else b"")
    list_header = bytes([(len(chunks) << 4) | 12])
    return envelope(
        b"\x49\x1c\x19"
        + list_header
        + b"".join(chunks)
        + b"\x00"
        + b"\x39"
        + list_header
        + orders
        + b"\x00"
    )


@pytest.mark.parametrize("physical", [4, 5])
@pytest.mark.parametrize("order", [1, 2])
def test_fsq_float_orders_use_non_nan_bounds_with_control(order, physical):
    body = ordered_footer(order, physical, nan=0)
    chunks = f.read_summary(body).row_groups[0]
    assert [(c.minimum, c.maximum) for c in chunks] == [(51.0, 51.5), (25.0, 25.5)]
    assert select_partitions(body, "2032-04-05", FRAME_BOX).files == ("near.parquet",)


@pytest.mark.parametrize("physical", [4, 5])
@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("side", ["low", "high"])
def test_fsq_float_order_nan_bound_refuses_with_control(order, physical, side):
    body = ordered_footer(order, physical, **{side: float("nan")}, nan=1)
    chunk = f.read_summary(body).row_groups[0][0]
    if order == 2:
        assert (chunk.minimum, chunk.maximum) == (None, None)
    elif side == "low":
        assert (chunk.minimum, chunk.maximum) == (None, 51.5)
    else:
        assert (chunk.minimum, chunk.maximum) == (51.0, None)
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(body, "2032-04-05", FRAME_BOX)
    assert select_partitions(
        ordered_footer(order, physical, nan=1), "2032-04-05", FRAME_BOX
    ).files == ("near.parquet",)


@pytest.mark.parametrize("physical", [4, 5])
@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("null", [0, 1])
def test_fsq_float_all_non_null_nan_has_no_bounds(order, physical, null):
    # num_values is three. Finite-looking stale bounds cannot contradict counts.
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(
            ordered_footer(order, physical, nan=3 - null, null=null),
            "2032-04-05",
            FRAME_BOX,
        )
    assert select_partitions(
        ordered_footer(order, physical, nan=2 - null, null=null),
        "2032-04-05",
        FRAME_BOX,
    ).files == ("near.parquet",)


@pytest.mark.parametrize("physical", [4, 5])
@pytest.mark.parametrize("side,value,sign", [("low", 0.0, -1), ("high", -0.0, 1)])
def test_fsq_type_order_zero_widens_but_total_order_keeps_sign(
    physical, side, value, sign
):
    changes = {"low": -1.0, "high": 1.0, side: value}
    chunk = f.read_summary(ordered_footer(1, physical, **changes)).row_groups[0][0]
    bound = chunk.minimum if side == "low" else chunk.maximum
    assert bound == 0.0 and math.copysign(1, bound) == sign
    control = f.read_summary(ordered_footer(2, physical, **changes, nan=0)).row_groups[
        0
    ][0]
    bound = control.minimum if side == "low" else control.maximum
    assert bound == 0.0 and math.copysign(1, bound) == -sign


@pytest.mark.parametrize(
    "order,physical",
    [
        (2, 0),
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 6),
        (2, 7),
        (3, 0),
        (3, 1),
        (3, 2),
        (3, 4),
        (3, 5),
        (3, 6),
        (3, 7),
    ],
)
def test_fsq_order_on_wrong_physical_type_refuses(order, physical):
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        f.read_summary(ordered_footer(order, physical))
    assert select_partitions(
        ordered_footer(2, 5, nan=0), "2032-04-05", FRAME_BOX
    ).files == ("near.parquet",)


def test_fsq_int96_timestamp_order_is_recognised_without_coordinate_coercion():
    # INT96 timestamp bytes cannot become geographic degrees. The order is valid.
    chunk = f.read_summary(
        ordered_footer(3, 3, low=bytes(12), high=b"\x01" + bytes(11))
    ).row_groups[0][0]
    assert chunk.column_order == 3
    assert (chunk.minimum, chunk.maximum) == (None, None)
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(ordered_footer(3, 3), "2032-04-05", FRAME_BOX)
    body = ordered_footer(2, nan=0, extra_int96=True)
    assert f.read_summary(body).row_groups[0][2].column_order == 3
    assert select_partitions(body, "2032-04-05", FRAME_BOX).files == ("near.parquet",)


@pytest.mark.parametrize("order", [4, 9])
def test_fsq_hand_encoded_unknown_order_still_refuses(order):
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(ordered_footer(order), "2032-04-05", FRAME_BOX)
    assert select_partitions(
        ordered_footer(2, nan=0), "2032-04-05", FRAME_BOX
    ).files == ("near.parquet",)


@pytest.mark.parametrize("before", [False, True])
def test_fsq_ieee_order_uses_modern_bounds_instead_of_deprecated(before):
    chunks = f.read_summary(summary(2, (10.0, 11.0), before=before)).row_groups[0]
    assert [(c.minimum, c.maximum) for c in chunks] == [(51.0, 51.5), (25.0, 25.5)]
    assert select_partitions(
        summary(2, (10.0, 11.0), before=before), "2032-04-05", FRAME_BOX
    ).files == ("near.parquet",)


def summary(
    order=1,
    deprecated=None,
    high=51.5,
    before=False,
    low=51.0,
    dropped=False,
    south=25.0,
    north=25.5,
):
    w = f._Writer()
    w._begin()

    def orders():
        w._field(7, 9)
        w._list_header(12, len(order) if isinstance(order, tuple) else 2)
        for member in order if isinstance(order, tuple) else (order, order):
            w._begin()
            w._field(member, 12)
            w._begin()
            w._end()
            w._end()

    if before and order is not None:
        orders()
    w._field(4, 9)
    w._list_header(12, 1)
    w._begin()
    w._field(1, 9)
    w._list_header(12, 3 if dropped else 2)
    if dropped:
        w._begin()
        w._end()
    for name, minimum, maximum in [
        ("longitude", low, high),
        ("latitude", south, north),
    ]:
        w._begin()
        w._binary(1, b"near.parquet")
        w._field(3, 12)
        w._begin()
        w._i32(1, 5)
        w._field(3, 9)
        w._list_header(8, 1)
        w._raw_binary(name.encode())
        w._field(12, 12)
        w._begin()
        if deprecated is not None:
            w._binary(1, struct.pack("<d", deprecated[1]))
            w._binary(2, struct.pack("<d", deprecated[0]))
        w._binary(5, struct.pack("<d", maximum))
        w._binary(6, struct.pack("<d", minimum))
        w._end()
        w._end()
        w._end()
    w._end()
    if not before and order is not None:
        orders()
    w._end()
    return envelope(bytes(w.buffer))


@pytest.mark.parametrize("order", [None, 4, 9])
def test_fsq_orders_missing_or_unknown_refuse(order):
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(summary(order), "2025-01-10", FRAME_BOX)


@pytest.mark.parametrize("order", [None, 4, 9])
def test_fsq_deprecated_bounds_used_when_order_unknown(order):
    chunks = f.read_summary(summary(order, (10.0, 11.0))).row_groups[0]
    assert [(c.minimum, c.maximum) for c in chunks] == [(10.0, 11.0), (10.0, 11.0)]
    with pytest.raises(PlacesFsqError, match=r"^no_file_for_frame$"):
        select_partitions(summary(order, (10.0, 11.0)), "2025-01-10", FRAME_BOX)


@pytest.mark.parametrize("before", [False, True])
def test_fsq_type_order_wins_whatever_field_order(before):
    assert select_partitions(
        summary(1, (10.0, 11.0), before=before), "2025-01-10", FRAME_BOX
    ).files == ("near.parquet",)


def test_fsq_nan_maximum_is_missing(tmp_path):
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(summary(high=float("nan")), "2025-01-10", FRAME_BOX)

    from custodian.tests.fixtures.places_fsq.invented import place, write_places
    from custodian.tests.test_places_fsq import _clock, _release_entry, _replace, _sleep

    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.places_fsq.fetch import fetch_release

    # The served file really has an invented point inside the frame.
    path = tmp_path / "near.parquet"
    write_places(path, [place(longitude=51.5, latitude=25.3)])
    entry = _replace(_release_entry(), terms_url="")
    seen = []

    def transport(url):
        seen.append(url)
        if url == entry.url:
            body = listing("2025-01-10/")
        elif url.endswith("_metadata"):
            body = summary(high=float("nan"))
        else:
            body = path.read_bytes()
        return Response(url, body, ())

    result, failure = fetch_release(
        entry, transport, tmp_path / "cache", _clock, _sleep
    )
    assert result is None
    assert failure.check == "statistics_missing"
    assert seen == [
        entry.url,
        "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/_metadata",
    ]
    assert not (tmp_path / "cache").exists()


def test_fsq_boolean_containers_consume_elements():
    # Unknown field 1, then row_groups field 4 with hand-valued coordinates.
    for kind, payload in [
        (9, b"\x21\x02\x01"),
        (10, b"\x21\x02\x01"),
        (11, b"\x01\x11\x02\x01"),
    ]:
        body = envelope(bytes([0x10 | kind]) + payload + b"\x39" + summary()[5:-8])
        chunks = f.read_summary(body).row_groups[0]
        assert [(c.path, c.minimum, c.maximum) for c in chunks] == [
            (("longitude",), 51.0, 51.5),
            (("latitude",), 25.0, 25.5),
        ]


def test_fsq_container_size_is_bounded_before_loop():
    started = time.monotonic()
    # Huge declared size, only one byte left. A slow runner has half a second
    # for three bounded parses; an element loop must never be entered.
    try:
        for kind in (9, 10, 11):
            size = bytearray()
            f._uvarint(size, 200_000_000)
            payload = (b"\xf1" + size) if kind != 11 else (size + b"\x11")
            with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
                f.read_summary(envelope(bytes([0x10 | kind]) + payload + b"\x00"))
    finally:
        assert time.monotonic() - started < 0.5


@pytest.mark.parametrize("depth", [65, 3000])
def test_fsq_deep_struct_refuses_with_named_error(depth):
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        f.read_summary(envelope(b"\x1c" * (depth - 1) + b"\x00" * depth))


def test_fsq_depth_boundary_is_accepted():
    assert f.read_summary(envelope(b"\x1c" * 63 + b"\x00" * 64)).row_groups == ()


def test_fsq_deep_geo_is_unreadable_json():
    assert f._bbox_from_geo("[" * 100000 + "0" + "]" * 100000) is None


def test_fsq_connection_disables_geoparquet_conversion():
    connection = _connect()
    try:
        assert connection.execute(
            "SELECT value FROM duckdb_settings() WHERE name = 'enable_geoparquet_conversion'"
        ).fetchone() == ("false",)
    finally:
        connection.close()


def test_fsq_duplicate_basename_refused():
    groups = [
        dict(file_path=path, longitude=(51.0, 51.5), latitude=(25.0, 25.5))
        for path in ("a/first/near.parquet", "b/second/near.parquet")
    ]
    with pytest.raises(PlacesFsqError, match=r"^file_name_duplicate$"):
        select_partitions(
            f.metadata_bytes(groups, dataset_geo_bbox=None), "2025-01-10", FRAME_BOX
        )


def test_fsq_fetch_refuses_stale_summary_before_storage(tmp_path):
    from custodian.tests.fixtures.places_fsq.invented import place, write_places
    from custodian.tests.test_places_fsq import _clock, _release_entry, _replace, _sleep

    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.places_fsq.fetch import fetch_release

    path = tmp_path / "invented.parquet"
    write_places(
        path, [place()]
    )  # longitude 51.5, latitude 25.3, both singleton bounds
    entry = _replace(_release_entry(), terms_url="")

    def transport(url):
        if url == entry.url:
            body = listing("2025-01-10/")
        else:
            body = summary() if url.endswith("_metadata") else path.read_bytes()
        return Response(url, body, ())

    result, failure = fetch_release(
        entry, transport, tmp_path / "cache", _clock, _sleep
    )
    assert result is None
    assert failure is not None
    assert failure.check == "summary_stale"
    assert (failure.code, failure.expected, failure.observed) == (
        1,
        "summary coordinate bounds",
        "file bounds differ or missing",
    )
    assert (
        failure.url
        == "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/near.parquet"
    )
    assert not (tmp_path / "cache").exists()
    chunks = f.read_summary(path.read_bytes()).row_groups[0]
    assert {chunk.file_path for chunk in chunks} == {""}
    assert [(c.minimum, c.maximum) for c in chunks if c.path == ("longitude",)] == [
        (51.5, 51.5)
    ]
    assert [(c.minimum, c.maximum) for c in chunks if c.path == ("latitude",)] == [
        (25.3, 25.3)
    ]


def test_fsq_fetch_refuses_stale_latitude_only(tmp_path):
    from custodian.tests.fixtures.places_fsq.invented import place, write_places
    from custodian.tests.test_places_fsq import _clock, _release_entry, _replace, _sleep

    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.places_fsq.fetch import fetch_release

    path = tmp_path / "invented.parquet"
    write_places(path, [place(longitude=51.5, latitude=25.3)])
    entry = _replace(_release_entry(), terms_url="")
    released = summary(low=51.5, high=51.5, south=25.3, north=25.4)

    def transport(url):
        if url == entry.url:
            body = listing("2025-01-10/")
        else:
            body = released if url.endswith("_metadata") else path.read_bytes()
        return Response(url, body, ())

    result, failure = fetch_release(
        entry, transport, tmp_path / "cache", _clock, _sleep
    )
    assert result is None
    assert failure is not None
    assert failure.check == "summary_stale"
    assert (failure.code, failure.expected, failure.observed) == (
        1,
        "summary coordinate bounds",
        "file bounds differ or missing",
    )
    assert (
        failure.url
        == "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/near.parquet"
    )
    assert not (tmp_path / "cache").exists()
    stated = f.read_summary(released).row_groups[0]
    assert [(c.minimum, c.maximum) for c in stated if c.path == ("longitude",)] == [
        (51.5, 51.5)
    ]
    assert [(c.minimum, c.maximum) for c in stated if c.path == ("latitude",)] == [
        (25.3, 25.4)
    ]
    served = f.read_summary(path.read_bytes()).row_groups[0]
    assert [(c.minimum, c.maximum) for c in served if c.path == ("longitude",)] == [
        (51.5, 51.5)
    ]
    assert [(c.minimum, c.maximum) for c in served if c.path == ("latitude",)] == [
        (25.3, 25.3)
    ]


@pytest.mark.parametrize("order", [(1,), (1, 1, 1)])
def test_fsq_order_count_must_match_whole_row_group(order):
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(summary(order), "2025-01-10", FRAME_BOX)


def test_fsq_dropped_chunk_does_not_shift_column_orders():
    selected = select_partitions(
        summary((9, 1, 1), dropped=True), "2025-01-10", FRAME_BOX
    )
    assert selected.files == ("near.parquet",)
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(summary((1, 9, 1), dropped=True), "2025-01-10", FRAME_BOX)


@pytest.mark.parametrize(
    "changes",
    [
        dict(low=float("nan")),
        dict(order=None, deprecated=(float("nan"), 51.0)),
        dict(order=None, deprecated=(51.0, float("nan"))),
    ],
)
def test_fsq_nan_in_each_bound_is_missing(changes):
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(summary(**changes), "2025-01-10", FRAME_BOX)


@pytest.mark.parametrize(
    "kind, header", [(9, b"\x19"), (10, b"\x1a"), (11, b"\x01\xb1")]
)
def test_fsq_container_depth_boundary(kind, header):
    # FileMetaData counts as depth one; each nested container adds one.
    # Map keys recurse, boolean values follow on unwinding.
    def payload(count):
        if kind == 11:
            return (
                bytes([0x10 | kind])
                + header * (count - 1)
                + b"\x00"
                + b"\x01" * (count - 1)
                + b"\x00"
            )
        return bytes([0x10 | kind]) + header * (count - 1) + b"\x01" + b"\x00"

    assert f.read_summary(envelope(payload(63))).row_groups == ()
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        f.read_summary(envelope(payload(64)))


def test_fsq_writer_emits_orders_and_optional_deprecated_pair():
    groups = [
        dict(file_path="near.parquet", longitude=(51.0, 51.5), latitude=(25.0, 25.5))
    ]
    for orders in [None, (9, 9), (4, 4)]:
        with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
            select_partitions(
                f.metadata_bytes(groups, dataset_geo_bbox=None, column_orders=orders),
                "2025-01-10",
                FRAME_BOX,
            )
        assert select_partitions(
            f.metadata_bytes(
                groups,
                dataset_geo_bbox=None,
                column_orders=orders,
                deprecated_bounds=True,
            ),
            "2025-01-10",
            FRAME_BOX,
        ).files == ("near.parquet",)

    assert select_partitions(
        f.metadata_bytes(groups, dataset_geo_bbox=None, column_orders=(2, 2)),
        "2025-01-10",
        FRAME_BOX,
    ).files == ("near.parquet",)


def test_fsq_list_header_refuses_huge_size_at_read_site():
    size = bytearray()
    f._uvarint(size, 1 << 62)
    started = time.monotonic()
    with pytest.raises(PlacesFsqError, match=r"^metadata_unreadable$"):
        f._FileReader(b"\xf1" + size)._list_header()
    assert time.monotonic() - started < 3.0


def test_fsq_coordinate_bounds_union_includes_unselected_row_groups():
    from eii_custodian.publicdata.places_fsq.select import coordinate_bounds

    groups = [
        dict(file_path="near.parquet", longitude=(51.0, 51.5), latitude=(25.0, 25.5)),
        dict(file_path="near.parquet", longitude=(10.0, 11.0), latitude=(20.0, 21.0)),
        dict(file_path="other.parquet", longitude=(-10.0, -5.0), latitude=(-3.0, -1.0)),
    ]
    body = f.metadata_bytes(groups, dataset_geo_bbox=None)
    assert coordinate_bounds(body, "near.parquet") == (10.0, 51.5, 20.0, 25.5)
    assert coordinate_bounds(body, "other.parquet") == (-10.0, -5.0, -3.0, -1.0)
    assert coordinate_bounds(body) == (-10.0, 51.5, -3.0, 25.5)
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        coordinate_bounds(body, "missing.parquet")
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        coordinate_bounds(f.metadata_bytes([], dataset_geo_bbox=None))


def test_fsq_repeated_and_non_struct_column_order_are_unknown():
    groups = [
        dict(file_path="near.parquet", longitude=(51.0, 51.5), latitude=(25.0, 25.5))
    ]
    # Build unknown union variants directly: two member-1 fields, then a bool member.
    for union in [b"\x1c\x00\x0c\x02\x00\x00", b"\x11\x00"]:
        w = f._Writer()
        w.column_orders = None
        w.file_metadata(tuple(groups), None)
        # The writer ends with field 6; field 7 is delta one.
        payload = bytes(w.buffer[:-1]) + b"\x19\x2c" + union + union + b"\x00"
        with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
            select_partitions(envelope(payload), "2025-01-10", FRAME_BOX)
