"""Local output bounds and supported serialization, with invented values."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from shapely.geometry import Point

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_io import (
    bound_files,
    local,
    read_object,
    write_record,
)


@pytest.mark.parametrize(
    "name", ["../outside", "/outside", "a/../../outside", "a//b", ".", ""]
)
def test_local_path_refuses_escaping_or_noncanonical_names(
    tmp_path: Path, name: str
) -> None:
    with pytest.raises(AssemblyError):
        local(tmp_path, name)


def test_local_symlink_is_refused_even_when_it_stays_inside(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to("real", target_is_directory=True)
    with pytest.raises(AssemblyError):
        write_record(tmp_path, "alias/output.json", {})


def test_supported_values_and_hash_bound_files(tmp_path: Path) -> None:
    @dataclass
    class Example:
        amount: Decimal

    result = write_record(
        tmp_path,
        "assembly/output.json",
        {
            "amount": Example(Decimal("1.25")),
            "day": date(2026, 1, 1),
            "shape": Point(0, 0),
            "wkb": b"a",
        },
    )
    record = read_object(tmp_path, "assembly/output.json")
    assert record["amount"] == {"amount": "1.25"}
    assert record["day"] == "2026-01-01"
    assert record["wkb"] == {"wkb_hex": "61"}
    assert record["shape"]["wkb_hex"] == Point(0, 0).wkb.hex()
    bound_files(tmp_path, result)
    (tmp_path / "assembly/output.json").write_text("{}")
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        bound_files(tmp_path, result)


@pytest.mark.parametrize("body", [b"[]", b"{", b"\xff"])
def test_reader_refuses_invalid_utf8_json_or_nonobject(
    tmp_path: Path, body: bytes
) -> None:
    (tmp_path / "body.json").write_bytes(body)
    with pytest.raises(AssemblyError, match="assembly_input_refused"):
        read_object(tmp_path, "body.json")


def test_missing_files_and_unsupported_serialization_are_refused(
    tmp_path: Path,
) -> None:
    with pytest.raises(AssemblyError):
        bound_files(tmp_path, {"absent": "0" * 64})
    with pytest.raises(AssemblyError):
        write_record(tmp_path, "out.json", {"object": object()})
    assert not (tmp_path / "out.json").exists()


def test_symlink_cache_root_is_not_an_output_root(tmp_path: Path) -> None:
    root = tmp_path / "actual"
    root.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(root, target_is_directory=True)
    with pytest.raises(AssemblyError):
        write_record(linked, "file.json", {})
    assert not (root / "file.json").exists()
