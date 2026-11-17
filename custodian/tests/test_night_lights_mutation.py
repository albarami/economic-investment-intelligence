"""Hand-written night-lights results that kill surviving numeric mutants."""

from decimal import Decimal

import h5py
import numpy as np
import pytest
from custodian.tests.fixtures.grids.invented import (
    checksummed_night_file,
    night_file,
    write_night_root,
    write_scale_offset,
)
from shapely.geometry import box

from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.night_lights import (
    FIELD,
    GROUP,
    Pixel,
    aggregate,
    area_mean,
    read_night_lights,
)

CELL = {1: box(-1, -1, 1, 1)}


def test_bytes_product_attributes_decode_and_keep_the_scaled_value(tmp_path):
    """A byte-string product attribute decodes as utf-8 and the pixel stays 3."""
    path = tmp_path / "SYN.h5"
    with h5py.File(path, "w") as source:
        write_night_root(source)
        fields = source.create_group(GROUP)
        fields.create_dataset("lat", data=np.array([0.5], dtype="float64"))
        fields.create_dataset("lon", data=np.array([0.1], dtype="float64"))
        data = fields.create_dataset(FIELD, data=np.array([[3]], dtype="float32"))
        write_scale_offset(data, offset=0.0)
        fields.create_dataset(FIELD + "_Quality", data=np.array([[0]], dtype="uint8"))
    pixels = read_night_lights(tmp_path, path, "2024-01")
    assert [(pixel.value, pixel.quality) for pixel in pixels] == [(Decimal("3.0"), 0)]


def test_scale_factor_multiplies_before_the_offset(tmp_path):
    """Raw 4 with scale 2 and offset 0 is 8; latitude descends; fill is not scaled."""
    path = tmp_path / "SYN.h5"
    with h5py.File(path, "w") as source:
        write_night_root(source)
        fields = source.create_group(GROUP)
        fields.create_dataset("lat", data=np.array([0.4, 0.2], dtype="float64"))
        fields.create_dataset("lon", data=np.array([0.1], dtype="float64"))
        data = fields.create_dataset(
            FIELD, data=np.array([[4], [-999.9]], dtype="float32")
        )
        write_scale_offset(data, scale=2.0, offset=0.0)
        fields.create_dataset(
            FIELD + "_Quality", data=np.array([[0], [0]], dtype="uint8")
        )
    pixels = read_night_lights(tmp_path, path, "2024-01")
    assert pixels[0].lat > pixels[1].lat
    assert [pixel.value for pixel in pixels] == [Decimal("8.0"), None]


def test_north_bound_keeps_a_centre_on_the_edge(tmp_path):
    """A centre whose latitude equals the north bound stays inside the window."""
    path = night_file(tmp_path / "SYN.h5")
    pixels = read_night_lights(tmp_path, path, "2024-01", (-1.0, -1.0, 10.0, 0.5))
    assert pixels[0].lat == 0.5
    assert pixels[0].value == Decimal("4.0")
    assert len(pixels) == 6


def test_longitude_outside_the_window_returns_no_pixels(tmp_path):
    """Latitudes in range and longitudes outside the window yield no pixels."""
    path = night_file(tmp_path / "SYN.h5")
    assert read_night_lights(tmp_path, path, "2024-01", (9.0, -1.0, 10.0, 1.0)) == []


def test_two_poor_pixels_and_two_fills_add_their_counts():
    """Each excluded pixel adds one to its count."""
    poor = aggregate(
        [
            Pixel("SYN-a", 0, 0, Decimal(1), 1),
            Pixel("SYN-b", 0.1, 0, Decimal(1), 1),
        ],
        CELL,
        "2024-01",
    )
    assert poor.excluded["poor"] == 2
    assert poor.rows == []
    filled = aggregate(
        [
            Pixel("SYN-c", 0, 0, None, 0),
            Pixel("SYN-d", 0.1, 0, None, 0),
        ],
        CELL,
        "2024-01",
    )
    assert filled.excluded["radiance_fill"] == 2
    assert filled.rows == []


def test_half_up_tie_quantizes_away_from_zero():
    """0.00025 to four decimal places is 0.0003 under half-up."""
    result = aggregate(
        [Pixel("SYN-tie", 0, 0, Decimal("0.00025"), 0)],
        CELL,
        "2024-01",
    )
    assert result.rows == [
        {
            "cell": 1,
            "period": "2024-01",
            "radiance": Decimal("0.0003"),
            "source_id": "ntl_blackmarble",
        }
    ]


def test_area_mean_of_two_cells_is_their_unweighted_sum_over_two():
    """The area mean of 0.0001 and 0.0003 is 0.0002."""
    assert area_mean(
        [
            {"cell": 1, "radiance": Decimal("0.0001")},
            {"cell": 2, "radiance": Decimal("0.0003")},
        ]
    ) == Decimal("0.0002")


def test_row_window_stops_before_the_damaged_checksum_row(tmp_path):
    """A checksummed chunk on the next row is outside the row stop and is not read."""
    path = checksummed_night_file(
        tmp_path / "SYN-rows.h5", chunks=(1, 3), damaged_chunk=(2, 0)
    )
    pixels = read_night_lights(tmp_path, path, "2024-01", (-9.0, -9.0, 9.0, 2.0))
    assert pixels == [
        Pixel("0:0", 0.1, 0.5, Decimal("0.00"), 0),
        Pixel("0:1", 0.2, 0.5, Decimal("0.10"), 0),
        Pixel("0:2", 0.3, 0.5, Decimal("0.20"), 0),
        Pixel("1:0", 0.1, 1.5, Decimal("0.30"), 0),
        Pixel("1:1", 0.2, 1.5, Decimal("0.40"), 0),
        Pixel("1:2", 0.3, 1.5, Decimal("0.50"), 0),
    ]


def test_column_window_stops_before_the_damaged_checksum_column(tmp_path):
    """A checksummed chunk on the next column is outside the column stop and is not read."""
    path = checksummed_night_file(
        tmp_path / "SYN-cols.h5", chunks=(4, 1), damaged_chunk=(0, 1)
    )
    pixels = read_night_lights(tmp_path, path, "2024-01", (-9.0, -9.0, 0.15, 9.0))
    assert pixels == [
        Pixel("0:0", 0.1, 0.5, Decimal("0.00"), 0),
        Pixel("1:0", 0.1, 1.5, Decimal("0.30"), 0),
        Pixel("2:0", 0.1, 2.5, Decimal("0.60"), 0),
        Pixel("3:0", 0.1, 3.5, Decimal("0.90"), 0),
    ]


class _RadianceDecimal(Decimal):
    """Invented subclass: area_mean accepts Decimal itself and refuses this."""


@pytest.mark.parametrize(
    "radiance",
    [
        _RadianceDecimal("1"),
        3,
        True,
        1.5,
        np.float32(1.5),
        "1.5",
        None,
    ],
    ids=["subclass", "int", "bool", "float", "numpy", "text", "none"],
)
def test_area_mean_refuses_a_radiance_that_is_not_exactly_decimal(radiance):
    """Each non-Decimal radiance is refused by name before any sum."""
    with pytest.raises(GridError) as caught:
        area_mean([{"cell": 1, "radiance": radiance}])
    assert str(caught.value) == "ntl_blackmarble: radiance not decimal"
