"""Root product attributes and one-element scale, on invented files."""

from decimal import Decimal
from pathlib import Path

import h5py
import numpy as np
import pytest
from custodian.tests.fixtures.grids.invented import (
    FILE_ATTRIBUTES,
    write_night_root,
    write_scale_offset,
)

from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.night_lights import FIELD, GROUP, read_night_lights

_LAT = np.array([0.4, 0.2], dtype="float64")
_LON = np.array([0.1], dtype="float64")
_VALUES = np.array([[4.0], [-999.9]], dtype="float32")
_FLAGS = np.array([[0], [0]], dtype="uint8")
_PIXELS = [
    (Decimal("8.0"), 0, 0.4, 0.1),
    (None, 0, 0.2, 0.1),
]
_ROOT_NAMES = ("ShortName", "VersionID", "StartTime", "LocalGranuleID")


def _pixels(path: Path) -> list[tuple[Decimal | None, int, float, float]]:
    return [
        (pixel.value, pixel.quality, pixel.lat, pixel.lon)
        for pixel in read_night_lights(path.parent, path, "2024-01")
    ]


def _fields(
    source: h5py.File,
    *,
    quality: bool = True,
    field: bool = True,
    lat: bool = True,
    lon: bool = True,
) -> h5py.Dataset | None:
    fields = source.create_group(GROUP)
    if lat:
        fields.create_dataset("lat", data=_LAT)
    if lon:
        fields.create_dataset("lon", data=_LON)
    data = fields.create_dataset(FIELD, data=_VALUES) if field else None
    if quality:
        fields.create_dataset(FIELD + "_Quality", data=_FLAGS)
    return data


def _root(
    source: h5py.File, omit: str | None = None, *, also_group: bool = False
) -> None:
    write_night_root(source)
    if omit is not None:
        del source.attrs[omit]
    if also_group:
        target = source[FILE_ATTRIBUTES]
        for name in _ROOT_NAMES:
            if name in source.attrs:
                target.attrs[name] = source.attrs[name]


def _refuse(path: Path, message: str) -> None:
    with pytest.raises(GridError) as caught:
        read_night_lights(path.parent, path, "2024-01")
    assert str(caught.value) == message


def test_attributes_only_on_the_additional_group_are_refused(tmp_path: Path) -> None:
    """A planted file with the four attributes only on the additional group is refused.

    The product stores those attributes on the file root and leaves
    ``/HDFEOS/ADDITIONAL/FILE_ATTRIBUTES`` empty.
    """
    path = tmp_path / "SYN-old.h5"
    with h5py.File(path, "w") as source:
        attrs = source.create_group(FILE_ATTRIBUTES).attrs
        attrs["ShortName"] = np.bytes_(b"VNP46A3")
        attrs["VersionID"] = np.bytes_(b"002")
        attrs["StartTime"] = np.bytes_(b"2024-01-01 00:00:00")
        attrs["LocalGranuleID"] = np.bytes_(b"VNP46A3.A2024001.h23v06.002.SYN.h5")
        data = _fields(source)
        assert data is not None
        data.attrs["_FillValue"] = np.float32(-999.9)
        data.attrs["scale_factor"] = np.float64(2.0)
        data.attrs["offset"] = np.float64(0.0)
    _refuse(path, "ntl_blackmarble: product attribute missing")


@pytest.mark.parametrize("name", _ROOT_NAMES)
def test_each_missing_root_attribute_is_refused(tmp_path: Path, name: str) -> None:
    """A file that lacks one of the four root attributes is refused."""
    path = tmp_path / "SYN-missing.h5"
    with h5py.File(path, "w") as source:
        _root(source, omit=name)
        data = _fields(source)
        assert data is not None
        write_scale_offset(data, scale=2.0, offset=0.0)
    _refuse(path, "ntl_blackmarble: product attribute missing")


@pytest.mark.parametrize(
    ("kept", "message"),
    [
        ("quality", "ntl_blackmarble: quality missing"),
        ("field", "ntl_blackmarble: field missing"),
        ("lat", "ntl_blackmarble: lat missing"),
        ("lon", "ntl_blackmarble: lon missing"),
    ],
)
def test_missing_dataset_is_refused(tmp_path: Path, kept: str, message: str) -> None:
    """A missing field, quality, latitude or longitude is refused by name.

    The four root attributes are also copied onto the additional group, which
    the product leaves empty, so the refusal names the missing dataset.
    """
    path = tmp_path / "SYN-member.h5"
    with h5py.File(path, "w") as source:
        _root(source, also_group=True)
        data = _fields(
            source,
            quality=kept != "quality",
            field=kept != "field",
            lat=kept != "lat",
            lon=kept != "lon",
        )
        if data is not None:
            write_scale_offset(data, scale=2.0, offset=0.0)
    _refuse(path, message)


def test_missing_data_group_is_refused(tmp_path: Path) -> None:
    """A file with no data group is refused by name."""
    path = tmp_path / "SYN-group.h5"
    with h5py.File(path, "w") as source:
        _root(source, also_group=True)
    _refuse(path, "ntl_blackmarble: data group missing")


def test_array_and_scalar_scales_return_the_same_pixels(tmp_path: Path) -> None:
    """A one-element scale and a scalar scale return the same hand-written pixels.

    Latitude descends. The fill value stays missing, so the scale is not applied
    to it. The scalar file is a planted form: the product stores one-element
    arrays. Both files also copy the four root attributes onto the additional
    group, which the product leaves empty.
    """
    array_path = tmp_path / "SYN-array.h5"
    scalar_path = tmp_path / "SYN-scalar.h5"
    with h5py.File(array_path, "w") as source:
        _root(source, also_group=True)
        data = _fields(source)
        assert data is not None
        write_scale_offset(data, scale=2.0, offset=0.0)
    with h5py.File(scalar_path, "w") as source:
        _root(source, also_group=True)
        data = _fields(source)
        assert data is not None
        data.attrs["_FillValue"] = np.float32(-999.9)
        data.attrs["scale_factor"] = np.float64(2.0)
        data.attrs["offset"] = np.float64(0.0)
    assert _pixels(array_path) == _PIXELS
    assert _pixels(scalar_path) == _PIXELS


@pytest.mark.parametrize(
    "scale",
    [
        np.array([2.0, 3.0], dtype="float64"),
        np.array([], dtype="float64"),
        np.bytes_(b"2"),
    ],
    ids=["two-elements", "empty", "text"],
)
def test_scale_that_is_not_one_number_is_refused(tmp_path: Path, scale: object) -> None:
    """An empty scale, a two-element scale, or a text scale is refused.

    A two-element scale is a planted file the product does not ship. The four
    root attributes are also copied onto the additional group, which the
    product leaves empty.
    """
    path = tmp_path / "SYN-shape.h5"
    with h5py.File(path, "w") as source:
        _root(source, also_group=True)
        data = _fields(source)
        assert data is not None
        write_scale_offset(data, scale=2.0, offset=0.0)
        data.attrs["scale_factor"] = scale
    _refuse(path, "ntl_blackmarble: attribute shape")


@pytest.mark.parametrize(
    "scale",
    [np.array([2], dtype="int64"), np.array([2], dtype="uint16")],
    ids=["signed", "unsigned"],
)
def test_one_element_integer_scale_matches_the_hand_written_pixels(
    tmp_path: Path, scale: np.ndarray
) -> None:
    """A one-element signed or unsigned scale yields the same pixels as scale 2.

    The product stores a floating-point scale. These integer kinds are one number
    each, converted through the text of that number.
    """
    path = tmp_path / "SYN-int.h5"
    with h5py.File(path, "w") as source:
        _root(source)
        data = _fields(source)
        assert data is not None
        write_scale_offset(data, scale=2.0, offset=0.0)
        data.attrs["scale_factor"] = scale
    assert _pixels(path) == _PIXELS


def test_text_root_attributes_return_the_hand_written_pixels(tmp_path: Path) -> None:
    """Text root attributes decode to the same pixels.

    A planted file: the product stores the four product attributes as byte strings.
    """
    path = tmp_path / "SYN-text-root.h5"
    with h5py.File(path, "w") as source:
        source.attrs["ShortName"] = "VNP46A3"
        source.attrs["VersionID"] = "002"
        source.attrs["StartTime"] = "2024-01-01 00:00:00"
        source.attrs["LocalGranuleID"] = "VNP46A3.A2024001.h23v06.002.SYN.h5"
        source.create_group(FILE_ATTRIBUTES)
        data = _fields(source)
        assert data is not None
        write_scale_offset(data, scale=2.0, offset=0.0)
    assert _pixels(path) == _PIXELS


def test_missing_scale_attribute_is_refused(tmp_path: Path) -> None:
    """A field without scale_factor is refused, and no KeyError leaves the reader."""
    path = tmp_path / "SYN-scale.h5"
    with h5py.File(path, "w") as source:
        _root(source, also_group=True)
        data = _fields(source)
        assert data is not None
        write_scale_offset(data, scale=2.0, offset=0.0)
        del data.attrs["scale_factor"]
    _refuse(path, "ntl_blackmarble: attribute missing")
