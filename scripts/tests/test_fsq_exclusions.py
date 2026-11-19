"""Invented footers only: a stale summary must not certify an exclusion."""

from __future__ import annotations

import hashlib
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import metadata_bytes
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX, select_partitions
from fsq_exclusions import CheckedFooter, _read_footer, check_exclusions


def group(name: str, *, near: bool) -> dict[str, object]:
    return {
        "file_path": name,
        "longitude": (51.0, 51.5) if near else (10.0, 11.0),
        "latitude": (25.0, 25.5) if near else (40.0, 41.0),
    }


class ExclusionTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, bytes, bytes]:
        summary_body = metadata_bytes(
            [group("near.parquet", near=True), group("far.parquet", near=False)],
            dataset_geo_bbox=None,
        )
        far_body = metadata_bytes([group("", near=False)], dataset_geo_bbox=None)
        summary, far = root / "summary.parquet", root / "far.parquet"
        summary.write_bytes(summary_body)
        far.write_bytes(far_body)
        return summary, far, summary_body, far_body

    def test_stale_excluded_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary = root / "summary.parquet"
            summary.write_bytes(
                metadata_bytes(
                    [
                        group("near.parquet", near=True),
                        group("far.parquet", near=False),
                    ],
                    dataset_geo_bbox=None,
                )
            )
            # Existing selection accepts the misleading summary and never sees far.
            self.assertEqual(
                select_partitions(summary.read_bytes(), "2025-01-10", FRAME_BOX).files,
                ("near.parquet",),
            )
            far = root / "far.parquet"
            far.write_bytes(
                metadata_bytes([group("", near=True)], dataset_geo_bbox=None)
            )
            with self.assertRaisesRegex(PlacesFsqError, "^summary_stale$"):
                check_exclusions(
                    summary,
                    {"far.parquet": far},
                    max_files=1,
                    max_footer_bytes=4096,
                )

    def test_complete_exclusion_has_exact_key_and_footer_digests(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            summary, far, summary_body, far_body = self.fixture(Path(folder))
            # Data pages are deliberately much larger than the footer budget.
            far.write_bytes(far_body[:4] + b"invented-page" * 10000 + far_body[4:])
            result = check_exclusions(
                summary,
                {"far.parquet": far},
                max_files=1,
                max_footer_bytes=len(summary_body),
            )
            self.assertEqual(result.selected, ("near.parquet",))
            self.assertEqual(
                result.summary_footer_sha256, hashlib.sha256(summary_body).hexdigest()
            )
            self.assertEqual(
                result.checked,
                (CheckedFooter("far.parquet", hashlib.sha256(far_body).hexdigest()),),
            )
            self.assertEqual(result.method, "fsq_exclusions.v1")
            self.assertEqual(result.release, "2025-01-10")

    def test_missing_extra_or_wrong_key_is_refused_before_file_access(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            summary, far, _, _ = self.fixture(Path(folder))
            for mapping in (
                {},
                {"near.parquet": far},
                {"far.parquet": far, "extra": far},
            ):
                with (
                    self.subTest(keys=tuple(mapping)),
                    patch("fsq_exclusions._read_footer", wraps=_read_footer) as reader,
                ):
                    with self.assertRaisesRegex(PlacesFsqError, "^exclusion_file_set$"):
                        check_exclusions(
                            summary, mapping, max_files=1, max_footer_bytes=4096
                        )
                    self.assertEqual(reader.call_count, 1)

    def test_file_budget_refuses_before_opening_any_excluded_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            summary = Path(folder) / "summary.parquet"
            summary.write_bytes(
                metadata_bytes(
                    [
                        group("near.parquet", near=True),
                        group("far.parquet", near=False),
                        group("other.parquet", near=False),
                    ],
                    dataset_geo_bbox=None,
                )
            )
            with patch("fsq_exclusions._read_footer", wraps=_read_footer) as reader:
                with self.assertRaisesRegex(PlacesFsqError, "^exclusion_file_limit$"):
                    check_exclusions(summary, {}, max_files=1, max_footer_bytes=4096)
                self.assertEqual(reader.call_count, 1)

    def test_invalid_budgets_refuse_before_any_file_access(self) -> None:
        for files, size in ((0, 4096), (-1, 4096), (True, 4096), (1, 11), (1, True)):
            with (
                self.subTest(files=files, size=size),
                patch("fsq_exclusions._read_footer") as reader,
            ):
                with self.assertRaisesRegex(
                    PlacesFsqError, "^exclusion_budget_invalid$"
                ):
                    check_exclusions(
                        Path("absent"), {}, max_files=files, max_footer_bytes=size
                    )
                reader.assert_not_called()

    def test_both_summary_and_excluded_footer_obey_byte_budget(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            summary, far, body, _ = self.fixture(Path(folder))
            with self.assertRaisesRegex(PlacesFsqError, "^exclusion_footer_limit$"):
                check_exclusions(
                    summary,
                    {"far.parquet": far},
                    max_files=1,
                    max_footer_bytes=len(body) - 1,
                )
            far.write_bytes(
                metadata_bytes([group("", near=False)] * 20, dataset_geo_bbox=None)
            )
            with self.assertRaisesRegex(PlacesFsqError, "^exclusion_footer_limit$"):
                check_exclusions(
                    summary,
                    {"far.parquet": far},
                    max_files=1,
                    max_footer_bytes=len(body),
                )

    def test_reader_seeks_over_pages_and_checks_limit_before_metadata_read(
        self,
    ) -> None:
        body = metadata_bytes([group("", near=False)], dataset_geo_bbox=None)
        stored = body[:4] + b"invented-page" * 10000 + body[4:]
        reads: list[tuple[int, int | None]] = []

        class Reader(io.BytesIO):
            def read(self, size: int | None = -1) -> bytes:
                reads.append((self.tell(), size))
                return super().read(size)

        with patch.object(Path, "open", return_value=Reader(stored)):
            self.assertEqual(_read_footer(Path("invented"), len(body)), body)
        self.assertEqual(
            reads,
            [
                (0, 4),
                (len(stored) - 8, 8),
                (len(stored) - len(body) + 4, len(body) - 12),
            ],
        )
        reads.clear()
        with patch.object(Path, "open", return_value=Reader(stored)):
            with self.assertRaisesRegex(PlacesFsqError, "^exclusion_footer_limit$"):
                _read_footer(Path("invented"), len(body) - 1)
        self.assertEqual(reads, [(0, 4), (len(stored) - 8, 8)])

    def test_malformed_envelopes_and_missing_files_are_named_refusals(self) -> None:
        valid = metadata_bytes([group("", near=False)], dataset_geo_bbox=None)
        bodies = (
            b"PAR1",
            b"nope" + valid[4:],
            valid[:-4] + b"nope",
            b"PAR1" + struct.pack("<I", 0) + b"PAR1",
            b"PAR1" + struct.pack("<I", 100) + b"PAR1",
        )
        with tempfile.TemporaryDirectory() as folder:
            summary, far, _, _ = self.fixture(Path(folder))
            for body in bodies:
                far.write_bytes(body)
                with self.subTest(body=body[:4]):
                    with self.assertRaisesRegex(
                        PlacesFsqError, "^metadata_unreadable$"
                    ):
                        check_exclusions(
                            summary,
                            {"far.parquet": far},
                            max_files=1,
                            max_footer_bytes=4096,
                        )
            far.unlink()
            with self.assertRaisesRegex(PlacesFsqError, "^exclusion_file_unreadable$"):
                check_exclusions(
                    summary, {"far.parquet": far}, max_files=1, max_footer_bytes=4096
                )

    def test_missing_coordinate_statistics_cannot_certify_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            summary, far, _, _ = self.fixture(Path(folder))
            missing = {**group("", near=False), "omit_latitude_stats": True}
            far.write_bytes(metadata_bytes([missing], dataset_geo_bbox=None))
            with self.assertRaisesRegex(PlacesFsqError, "^statistics_missing$"):
                check_exclusions(
                    summary, {"far.parquet": far}, max_files=1, max_footer_bytes=4096
                )

    def test_checks_all_exclusions_in_key_order_without_a_partial_result(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary = root / "summary.parquet"
            summary.write_bytes(
                metadata_bytes(
                    [
                        group("near.parquet", near=True),
                        group("z/far.parquet", near=False),
                        group("a/far.parquet", near=False),
                    ],
                    dataset_geo_bbox=None,
                )
            )
            a, z = root / "a.parquet", root / "z.parquet"
            far_body = metadata_bytes([group("", near=False)], dataset_geo_bbox=None)
            a.write_bytes(far_body)
            z.write_bytes(far_body)
            files = {"z/far.parquet": z, "a/far.parquet": a}
            result = check_exclusions(
                summary, files, max_files=2, max_footer_bytes=4096
            )
            self.assertEqual(
                tuple(row.name for row in result.checked),
                ("a/far.parquet", "z/far.parquet"),
            )
            z.write_bytes(metadata_bytes([group("", near=True)], dataset_geo_bbox=None))
            with self.assertRaisesRegex(PlacesFsqError, "^summary_stale$"):
                check_exclusions(summary, files, max_files=2, max_footer_bytes=4096)

    def test_short_trailer_and_metadata_reads_cannot_certify_exclusion(self) -> None:
        body = metadata_bytes([group("", near=False)], dataset_geo_bbox=None)
        metadata_length = len(body) - 12

        class ShortReader(io.BytesIO):
            def __init__(self, value: bytes, short_size: int) -> None:
                super().__init__(value)
                self.short_size = short_size

            def read(self, size: int | None = -1) -> bytes:
                value = super().read(size)
                return value[:-1] if size == self.short_size else value

        for short_size in (8, metadata_length):
            with (
                self.subTest(size=short_size),
                patch.object(Path, "open", return_value=ShortReader(body, short_size)),
            ):
                with self.assertRaisesRegex(PlacesFsqError, "^metadata_unreadable$"):
                    _read_footer(Path("invented"), 4096)


if __name__ == "__main__":
    unittest.main()
