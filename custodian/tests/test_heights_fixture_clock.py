"""The height fixtures' zip bodies do not depend on the clock.

`test_two_runs_give_identical_file_hashes` builds the card's fixture twice and
compares the output files byte for byte; the manifest records each input's
hash, so a zip body that carried the wall-clock time of its writing made that
comparison fail whenever the two builds fell on either side of a two-second
boundary of the zip time field. Each writer is called here under two clocks
far apart and must give the same bytes.
"""

from __future__ import annotations

import io
import time
import zipfile
from collections.abc import Callable

import pytest
from custodian.tests.fixtures.heights import invented

EARLY = 1_800_000_000.0
LATE = EARLY + 86_400.0 + 3.0


def _at(
    monkeypatch: pytest.MonkeyPatch, moment: float, build: Callable[[], bytes]
) -> bytes:
    with monkeypatch.context() as patch:
        patch.setattr(time, "time", lambda: moment)
        return build()


def _members() -> dict[str, bytes]:
    return {"a.shp": b"\x00\x01shape", "a.dbf": b"dbf", "a.shx": b"shx"}


@pytest.mark.parametrize(
    "build",
    [
        lambda: invented.zip_members(_members()),
        lambda: invented.zip_members(_members(), zipfile.ZIP_STORED),
        lambda: invented.zip_members_duplicated(_members(), "a.dbf"),
        lambda: invented.zip_members_duplicated(_members(), "a.dbf", drop="shx"),
        lambda: invented.globfp_zip([(invented.square(0.05, 0.05, 0.6), "7")]),
    ],
    ids=["deflated", "stored", "duplicated", "duplicated-dropped", "globfp"],
)
def test_zip_bodies_do_not_carry_the_clock(
    monkeypatch: pytest.MonkeyPatch, build: Callable[[], bytes]
) -> None:
    assert _at(monkeypatch, EARLY, build) == _at(monkeypatch, LATE, build)


def test_the_compression_choice_is_kept() -> None:
    """The compression-method plant still packs with the method it names."""
    for method in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED):
        with zipfile.ZipFile(
            io.BytesIO(invented.zip_members(_members(), method))
        ) as archive:
            assert {info.compress_type for info in archive.infolist()} == {method}
