"""Invented Overture-shaped Parquet only; every place, name and id is made up."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from hypothesis import example, given, settings
from hypothesis import strategies as st
from shapely.geometry import Point, box

import h3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import review_attribution_tokens as tokens_tool
import review_place_keys as keys_tool
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.places.build import build_places
from eii_custodian.publicdata.places.integrate import _place_from_registry
from eii_custodian.publicdata.places.read import (
    ReadBuilding,
    ReadPlace,
    RecordLevel,
    read_place_file,
)
from eii_custodian.publicdata.review.cache_fixture import write_cached

# The custodian's own invented archive builder, loaded by name: the fixture is
# untyped and outside the type check's configured files.
invented_archive = importlib.import_module(
    "custodian.tests.fixtures.frame.invented"
).invented_archive
BOUNDARY = box(51.0, 25.0, 51.6, 25.6)
PLACES_KEY = "places_ovt/part-00014"
PARTS = ("bldg_ovt/part-00384", "bldg_ovt/part-00385")
SCHEMA = json.dumps({"overture-schema-pyspark": "2.0.0"})
PLACE_COLUMNS = (
    ("id", "VARCHAR"),
    ("geometry", "BLOB"),
    ("confidence", "DOUBLE"),
    ("names", 'STRUCT("primary" VARCHAR, common MAP(VARCHAR, VARCHAR))'),
    ("sources", "STRUCT(property VARCHAR, dataset VARCHAR, license VARCHAR)[]"),
    ("basic_category", "VARCHAR"),
    ("addresses", "STRUCT(freeform VARCHAR, country VARCHAR)[]"),
    ("bbox", "STRUCT(xmin DOUBLE, xmax DOUBLE, ymin DOUBLE, ymax DOUBLE)"),
)
BUILDING_COLUMNS = (("id", "VARCHAR"), ("geometry", "BLOB"))


def place(
    pid: str,
    lon: float,
    lat: float,
    name: str = "",
    arabic: str | None = None,
    dataset: str = "syn-source",
    confidence: float | None = 0.9,
) -> dict[str, object]:
    common = {} if arabic is None else {"ar": arabic}
    return {
        "id": pid,
        "geometry": Point(lon, lat).wkb,
        "confidence": confidence,
        "names": {"primary": name, "common": common},
        "sources": [{"property": "", "dataset": dataset, "license": None}],
        "basic_category": "syn_category",
        "addresses": [{"freeform": "SYN street", "country": "SYN"}],
        "bbox": {"xmin": lon, "xmax": lon, "ymin": lat, "ymax": lat},
    }


def building(
    bid: str, west: float, south: float, size: float = 0.01
) -> dict[str, object]:
    return {"id": bid, "geometry": box(west, south, west + size, south + size).wkb}


def parquet(
    folder: Path,
    columns: Sequence[tuple[str, str]],
    rows: Sequence[Mapping[str, object]],
) -> bytes:
    import duckdb

    path = folder / f"syn-{len(list(folder.iterdir()))}.parquet"
    connection = duckdb.connect()
    try:
        declared = ", ".join(f'"{name}" {kind}' for name, kind in columns)
        connection.execute(f"CREATE TABLE syn ({declared})")
        marks = ", ".join("?" for _ in columns)
        for row in rows:
            values = [row[name] for name, _kind in columns]
            connection.execute(f"INSERT INTO syn VALUES ({marks})", values)
        connection.execute(
            "COPY syn TO ? (FORMAT parquet, KV_METADATA {schema_versions: ?})",
            [str(path), SCHEMA],
        )
    finally:
        connection.close()
    return path.read_bytes()


def spec(
    key: str, name_en: str, name_ar: str = "", **extra: object
) -> dict[str, object]:
    row: dict[str, object] = {
        "place_key": key,
        "kind": key.split(":")[0],
        "name_en": name_en,
        "name_ar": name_ar,
        "aliases": None,
        "source_id": None,
        "record_key": None,
        "arabic_review": "pending native review",
    }
    row.update(extra)
    return row


class World(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.cache = self.root / "cache"
        self.review = self.root / "review"
        self.scratch = self.root / "scratch"
        for item in (self.cache, self.review, self.scratch):
            item.mkdir()
        (self.review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
        (self.review / "places_ovt_attribution.csv").write_text(
            "dataset_token,licence\nsyn-source,SYN-LICENCE\n", encoding="utf-8"
        )
        self.registry = {row.key: row for row in load_registry()}

    def cache_places(self, rows: Sequence[Mapping[str, object]]) -> None:
        body = parquet(self.scratch, PLACE_COLUMNS, rows)
        write_cached(self.cache, self.registry[PLACES_KEY], body)

    def cache_buildings(self, part: int, rows: Sequence[Mapping[str, object]]) -> None:
        body = parquet(self.scratch, BUILDING_COLUMNS, rows)
        write_cached(self.cache, self.registry[PARTS[part]], body)

    def review_files(
        self,
        flagship: Sequence[Mapping[str, object]] = (),
        gazetteer: Sequence[Mapping[str, object]] = (),
    ) -> None:
        for name, rows in (
            ("flagship_candidates.yaml", flagship),
            ("showcase_gazetteer.yaml", gazetteer),
        ):
            text = json.dumps(list(rows), ensure_ascii=False, indent=2) + "\n"
            (self.review / name).write_text(text, encoding="utf-8")

    def rows(self, name: str) -> list[dict[str, object]]:
        loaded = json.loads((self.review / name).read_text(encoding="utf-8"))
        assert isinstance(loaded, list)
        return loaded

    def run_tool(self, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        with (
            patch.object(keys_tool, "frame_boundary", return_value=BOUNDARY),
            contextlib.redirect_stdout(out),
        ):
            code = keys_tool.main([str(self.cache), str(self.review), *extra])
        return code, out.getvalue()


class GazetteerRows(World):
    def test_one_match_writes_place_id_and_prints_no_name_or_id(self) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.1, 25.1, "Syn  Souq "),
                place("SYN-P-2", 51.2, 25.2, "Other"),
            ]
        )
        self.review_files(gazetteer=[spec("landmark:0", "syn souq")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        row = self.rows("showcase_gazetteer.yaml")[0]
        self.assertEqual(
            (row["source_id"], row["record_key"]), ("places_ovt", "SYN-P-1")
        )
        self.assertEqual(
            out,
            "landmark:0 matches=1 kept=true attribution=true footprints=na "
            "inside=na written=true reason=ok\n",
        )
        for secret in ("SYN-P-1", "souq", "Souq", "51.1", "25.1"):
            self.assertNotIn(secret, out)

    def test_zero_matches_stays_null(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Tower")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("showcase_gazetteer.yaml")[0]["record_key"])
        self.assertIn(
            "matches=0 kept=na attribution=na footprints=na inside=na "
            "written=false reason=match_0",
            out,
        )

    def test_two_matches_stay_null(self) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.1, 25.1, "Syn Souq"),
                place("SYN-P-2", 51.2, 25.2, "SYN  SOUQ"),
            ]
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("showcase_gazetteer.yaml")[0]["record_key"])
        self.assertIn(
            "matches=n kept=na attribution=na footprints=na inside=na "
            "written=false reason=match_n",
            out,
        )

    def test_arabic_only_match_is_written(self) -> None:
        self.cache_places(
            [place("SYN-P-1", 51.1, 25.1, "Unrelated", arabic="سوق مخترع")]
        )
        self.review_files(
            gazetteer=[spec("landmark:0", "No English Match", "سوق  مخترع")]
        )
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(
            self.rows("showcase_gazetteer.yaml")[0]["record_key"], "SYN-P-1"
        )
        self.assertIn("written=true reason=ok", out)

    def test_alias_match_is_written(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Alias")])
        self.review_files(
            gazetteer=[spec("landmark:0", "Syn Main", aliases=["syn alias"])]
        )
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(
            self.rows("showcase_gazetteer.yaml")[0]["record_key"], "SYN-P-1"
        )

    def test_aliases_not_a_list_is_refused(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Alias")])
        self.review_files(
            gazetteer=[spec("landmark:0", "Syn Alias", aliases="syn alias")]
        )
        self.assertEqual(self.run_tool(), (2, "REFUSED aliases_form\n"))

    def test_filled_row_is_left_alone(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        filled = spec(
            "landmark:0", "Syn Souq", source_id="places_ovt", record_key="SYN-P-1"
        )
        self.review_files(gazetteer=[filled])
        before = (self.review / "showcase_gazetteer.yaml").read_bytes()
        self.assertEqual(self.run_tool(), (0, ""))
        self.assertEqual((self.review / "showcase_gazetteer.yaml").read_bytes(), before)


class FlagshipRows(World):
    def flagship_world(
        self, buildings: Sequence[Mapping[str, object]], lon: float = 51.105
    ) -> None:
        self.cache_places([place("SYN-P-1", lon, 25.105, "Syn Tower")])
        self.cache_buildings(0, buildings)
        self.review_files(flagship=[spec("building:0", "Syn Tower")])

    def test_point_in_one_footprint_inside_writes_building(self) -> None:
        self.flagship_world(
            [building("SYN-B-1", 51.1, 25.1), building("SYN-B-2", 51.3, 25.3)]
        )
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        row = self.rows("flagship_candidates.yaml")[0]
        self.assertEqual((row["source_id"], row["record_key"]), ("bldg_ovt", "SYN-B-1"))
        self.assertEqual(
            out,
            "building:0 matches=1 kept=true attribution=true footprints=1 "
            "inside=true written=true reason=ok\n",
        )

    def test_footprint_in_second_part_is_found(self) -> None:
        self.flagship_world([building("SYN-B-2", 51.3, 25.3)])
        self.cache_buildings(1, [building("SYN-B-9", 51.1, 25.1)])
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(
            self.rows("flagship_candidates.yaml")[0]["record_key"], "SYN-B-9"
        )

    def test_point_in_no_footprint_stays_null(self) -> None:
        self.flagship_world([building("SYN-B-2", 51.3, 25.3)])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("flagship_candidates.yaml")[0]["record_key"])
        self.assertIn(
            "matches=1 kept=true attribution=true footprints=0 inside=na "
            "written=false reason=footprint_0",
            out,
        )

    def test_point_in_two_footprints_stays_null(self) -> None:
        self.flagship_world(
            [building("SYN-B-1", 51.1, 25.1), building("SYN-B-2", 51.1, 25.1, 0.02)]
        )
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("flagship_candidates.yaml")[0]["record_key"])
        self.assertIn(
            "matches=1 kept=true attribution=true footprints=n inside=na "
            "written=false reason=footprint_n",
            out,
        )

    def test_footprint_outside_boundary_stays_null(self) -> None:
        self.flagship_world(
            [building("SYN-B-1", 51.59, 25.1, 0.04), building("SYN-B-2", 51.3, 25.3)],
            lon=51.595,
        )
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("flagship_candidates.yaml")[0]["record_key"])
        self.assertIn(
            "matches=1 kept=true attribution=true footprints=1 inside=false "
            "written=false reason=outside_boundary",
            out,
        )

    def test_check_agrees_after_fill_and_flags_a_planted_mismatch(self) -> None:
        self.flagship_world([building("SYN-B-1", 51.1, 25.1)])
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(
            self.run_tool("--check"),
            (0, "building:0 check=true kept=true attribution=true\n"),
        )
        rows = self.rows("flagship_candidates.yaml")
        rows[0]["record_key"] = "SYN-B-WRONG"
        self.review_files(flagship=rows)
        self.assertEqual(
            self.run_tool("--check"),
            (1, "building:0 check=false kept=true attribution=true\n"),
        )

    def test_check_flags_a_wrong_source_id(self) -> None:
        self.flagship_world([building("SYN-B-1", 51.1, 25.1)])
        filled = spec(
            "building:0", "Syn Tower", source_id="places_ovt", record_key="SYN-B-1"
        )
        self.review_files(flagship=[filled])
        self.assertEqual(
            self.run_tool("--check"),
            (1, "building:0 check=false kept=true attribution=true\n"),
        )


class BuildFilters(World):
    """A key is written only for a place the build's own filters keep."""

    def test_place_excluded_by_keep_stays_null_with_its_reason(self) -> None:
        self.cache_places(
            [place("SYN-P-1", 51.1, 25.1, "Syn Souq", dataset="OpenStreetMap")]
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("showcase_gazetteer.yaml")[0]["record_key"])
        self.assertEqual(
            out,
            "landmark:0 matches=1 kept=false attribution=na footprints=na "
            "inside=na written=false reason=excluded_by_keep_osm_not_merged\n",
        )

    def test_flagship_place_excluded_by_keep_stays_null(self) -> None:
        self.cache_places(
            [place("SYN-P-1", 51.105, 25.105, "Syn Tower", confidence=None)]
        )
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1)])
        self.review_files(flagship=[spec("building:0", "Syn Tower")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("flagship_candidates.yaml")[0]["record_key"])
        self.assertIn("written=false reason=excluded_by_keep_null_confidence", out)

    def test_duplicate_dropped_by_the_build_stays_null(self) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.1, 25.1, "Syn Souq", "سوق مخترع", confidence=0.5),
                place("SYN-P-2", 51.1001, 25.1, "Syn Market", "سوق مخترع"),
            ]
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIsNone(self.rows("showcase_gazetteer.yaml")[0]["record_key"])
        self.assertEqual(
            out,
            "landmark:0 matches=1 kept=false attribution=na footprints=na "
            "inside=na written=false reason=duplicate_dropped\n",
        )

    def test_the_keeper_of_a_duplicate_is_written(self) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.1, 25.1, "Syn Souq", "سوق مخترع", confidence=0.5),
                place("SYN-P-2", 51.1001, 25.1, "Syn Market", "سوق مخترع"),
            ]
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Market")])
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(
            self.rows("showcase_gazetteer.yaml")[0]["record_key"], "SYN-P-2"
        )

    def test_missing_attribution_is_reported_apart_and_the_key_written(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq", dataset="syn-x")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(
            self.rows("showcase_gazetteer.yaml")[0]["record_key"], "SYN-P-1"
        )
        self.assertEqual(
            out,
            "landmark:0 matches=1 kept=true attribution=false footprints=na "
            "inside=na written=true reason=ok\n",
        )
        self.assertEqual(
            self.run_tool("--check"),
            (0, "landmark:0 check=true kept=true attribution=false\n"),
        )

    def test_check_flags_a_key_whose_place_the_build_drops(self) -> None:
        self.cache_places(
            [place("SYN-P-1", 51.1, 25.1, "Syn Souq", dataset="OpenStreetMap")]
        )
        filled = spec(
            "landmark:0", "Syn Souq", source_id="places_ovt", record_key="SYN-P-1"
        )
        self.review_files(gazetteer=[filled])
        self.assertEqual(
            self.run_tool("--check"),
            (1, "landmark:0 check=false kept=false attribution=na\n"),
        )

    def test_kept_ids_equal_the_builds_own_shown_survivors(self) -> None:
        rows = [
            place("SYN-P-1", 51.1, 25.1, "A"),
            place("SYN-P-2", 51.7, 25.1, "B"),
            place("SYN-P-3", 51.2, 25.2, "C", dataset="OpenStreetMap"),
            place("SYN-P-4", 51.2, 25.3, "D", confidence=None),
            place("SYN-P-5", 51.3, 25.3, "", "اسم"),
            place("SYN-P-6", 51.4, 25.4, "Dup", confidence=0.5),
            place("SYN-P-7", 51.4001, 25.4, "dup"),
            place("SYN-P-8", 51.5, 25.5, "E", dataset=""),
        ]
        self.cache_places(rows)
        located = _place_from_registry(self.cache, list(self.registry.values()))
        assert located is not None
        path, receipt = located
        places = read_place_file(path, "ar")
        fates, attributed = keys_tool.place_fates(
            places, BOUNDARY, (("syn-source", "SYN-LICENCE"),)
        )
        grid = [
            {"cell": h3.str_to_int(h3.latlng_to_cell(float(p.lat), float(p.lon), 9))}
            for p in places
        ]
        built = build_places(
            path,
            arabic_tag="ar",
            boundary=BOUNDARY,
            grid=grid,
            attribution=(("syn-source", "SYN-LICENCE"),),
            places_receipt=receipt,
        )
        dropped = {
            part for p in built.places for part in p.merged_ids.split(";") if part
        }
        survivors = {p.place_id for p in built.places} - dropped
        self.assertEqual({k for k, v in fates.items() if v == "ok"}, survivors)
        self.assertEqual(
            fates,
            {
                "SYN-P-1": "ok",
                "SYN-P-2": "excluded_by_keep_outside_boundary",
                "SYN-P-3": "excluded_by_keep_osm_not_merged",
                "SYN-P-4": "excluded_by_keep_null_confidence",
                "SYN-P-5": "excluded_by_keep_name_missing",
                "SYN-P-6": "duplicate_dropped",
                "SYN-P-7": "ok",
                "SYN-P-8": "excluded_by_keep_source_provider_missing",
            },
        )
        self.assertEqual(
            attributed,
            frozenset(
                {"SYN-P-1", "SYN-P-2", "SYN-P-4", "SYN-P-5", "SYN-P-6", "SYN-P-7"}
            ),
        )


class FrameBoundary(World):
    """The real reader path over an invented municipality archive."""

    def cache_archive(self, body: bytes) -> None:
        write_cached(self.cache, self.registry["bnd_hdx"], body)

    def run_unpatched(self, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = keys_tool.main([str(self.cache), str(self.review), *extra])
        return code, out.getvalue()

    def test_invented_archive_boundary_is_the_municipality_union(self) -> None:
        self.cache_archive(invented_archive(bounds=(51.0, 25.0, 51.6, 25.6)))
        merged = keys_tool.frame_boundary(self.cache, list(self.registry.values()))
        self.assertTrue(merged.equals(BOUNDARY))
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        code, out = self.run_unpatched()
        self.assertEqual(code, 0)
        self.assertIn("written=true reason=ok", out)
        self.assertEqual(
            self.rows("showcase_gazetteer.yaml")[0]["record_key"], "SYN-P-1"
        )

    def test_zero_municipalities_is_refused(self) -> None:
        self.cache_archive(without_municipalities(invented_archive()))
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.assertEqual(self.run_unpatched(), (2, "REFUSED frame_boundary_missing\n"))

    def test_unreadable_archive_is_refused(self) -> None:
        self.cache_archive(b"SYN not an archive")
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.assertEqual(
            self.run_unpatched(), (2, "REFUSED frame_boundary_unreadable\n")
        )

    def test_reader_refusal_passes_through_with_its_own_reason(self) -> None:
        self.cache_archive(invented_archive(bounds=(51.0, 25.0, 51.6, 25.6)))
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        (self.review / "places_ovt_attribution.csv").write_text(
            "token,licence\n", encoding="utf-8"
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.assertEqual(self.run_unpatched(), (2, "REFUSED attribution_header\n"))
        self.assertIsNone(self.rows("showcase_gazetteer.yaml")[0]["record_key"])


def without_municipalities(body: bytes) -> bytes:
    """The same invented archive with an empty municipality level."""
    source = zipfile.ZipFile(io.BytesIO(body))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "qat_admin1.geojson":
                document = json.loads(data)
                document["features"] = []
                data = json.dumps(document).encode()
            archive.writestr(info, data)
    return stream.getvalue()


class Refusals(World):
    def test_unreceipted_places_file_is_refused(self) -> None:
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1)])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.assertEqual(self.run_tool(), (2, "REFUSED places_file_unreceipted\n"))

    def test_unreceipted_buildings_part_is_refused(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1)])
        (self.cache / PARTS[1]).mkdir(parents=True)
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.assertEqual(self.run_tool(), (2, "REFUSED buildings_file_unreceipted\n"))

    def test_missing_arabic_tag_is_refused(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        (self.review / "arabic_tag.txt").unlink()
        self.assertEqual(self.run_tool(), (2, "REFUSED arabic_tag_missing\n"))

    def test_overwrite_of_a_set_key_is_refused(self) -> None:
        proposal = keys_tool.Proposal(
            "landmark:0", 1, True, True, None, None, "SYN-P-1", "ok"
        )
        for field in ("record_key", "source_id"):
            filled = spec("landmark:0", "Syn Souq", **{field: "SYN-OTHER"})
            with self.assertRaises(keys_tool.ReviewError) as caught:
                keys_tool.apply([filled], [proposal], "places_ovt")
            self.assertEqual(caught.exception.reason, "overwrite_refused")

    def test_reload_mismatch_leaves_the_file_unchanged(self) -> None:
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        path = self.review / "showcase_gazetteer.yaml"
        before = path.read_bytes()

        def other(
            _path: Path, _cache: Path | None
        ) -> tuple[str, tuple[Mapping[str, object], ...]]:
            return "committed", ()

        with self.assertRaises(keys_tool.ReviewError) as caught:
            keys_tool.write_reviewed(path, [spec("landmark:0", "Syn Souq")], other)
        self.assertEqual(caught.exception.reason, "reload_mismatch")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            sorted(item.name for item in self.review.iterdir()),
            [
                "arabic_tag.txt",
                "flagship_candidates.yaml",
                "places_ovt_attribution.csv",
                "showcase_gazetteer.yaml",
            ],
        )

    def test_registry_without_boundary_source_is_refused(self) -> None:
        with self.assertRaises(keys_tool.ReviewError) as caught:
            keys_tool.frame_boundary(self.cache, ())
        self.assertEqual(caught.exception.reason, "frame_boundary_missing")


def read_place(
    pid: str, name: str, lon: float = 51.105, lat: float = 25.105
) -> ReadPlace:
    return ReadPlace(
        pid,
        name,
        None,
        "syn",
        Decimal(str(lon)),
        Decimal(str(lat)),
        None,
        "null",
        RecordLevel(None, "absent"),
        b"",
    )


def read_building(bid: str, west: float) -> ReadBuilding:
    shape = box(west, 25.1, west + 0.01, 25.11)
    return ReadBuilding(bid, Decimal("0"), Decimal("0"), bytes(shape.wkb))


WORDS = st.sampled_from(["syn", "SYN", "souq", "Souq", "tower"])
NAMES = st.lists(WORDS, min_size=0, max_size=3).flatmap(
    lambda words: st.sampled_from([" ", "  ", "\t"]).map(
        lambda gap: gap + gap.join(words)
    )
)


class Properties(unittest.TestCase):
    @given(st.lists(NAMES, max_size=6), NAMES)
    def test_written_exactly_when_one_normalised_name_matches(
        self, names: list[str], target: str
    ) -> None:
        places = tuple(read_place(f"SYN-P-{n}", name) for n, name in enumerate(names))
        inputs = keys_tool.Inputs(
            places, (), frozenset(), {p.place_id: "ok" for p in places}, frozenset()
        )
        folded = " ".join(target.split()).casefold()
        oracle = [
            n
            for n, name in enumerate(names)
            if folded and " ".join(name.split()).casefold() == folded
        ]
        result = keys_tool.propose(spec("landmark:0", target), "places_ovt", inputs)
        expected = f"SYN-P-{oracle[0]}" if len(oracle) == 1 else None
        self.assertEqual(result.key, expected)
        self.assertEqual(result.matches, len(oracle))

    @given(st.lists(st.tuples(st.booleans(), st.booleans()), max_size=4))
    def test_building_written_only_for_one_covering_inside_footprint(
        self, plan: list[tuple[bool, bool]]
    ) -> None:
        buildings = tuple(
            read_building(f"SYN-B-{n}", 51.1 if covers else 51.3 + n * 0.02)
            for n, (covers, _inside) in enumerate(plan)
        )
        inside = frozenset(f"SYN-B-{n}" for n, (_c, flag) in enumerate(plan) if flag)
        inputs = keys_tool.Inputs(
            (read_place("SYN-P-1", "Syn Tower"),),
            buildings,
            inside,
            {"SYN-P-1": "ok"},
            frozenset(),
        )
        result = keys_tool.propose(spec("building:0", "syn tower"), "bldg_ovt", inputs)
        covering = [n for n, (covers, _flag) in enumerate(plan) if covers]
        ok = len(covering) == 1 and plan[covering[0]][1]
        self.assertEqual(result.key, f"SYN-B-{covering[0]}" if ok else None)
        self.assertEqual(result.footprints, len(covering))


LONS = st.sampled_from([51.1, 51.1001, 51.7])
DATASETS = st.sampled_from(["syn-source", "syn-x", "OpenStreetMap", ""])
CONFIDENCES = st.sampled_from([0.5, 0.9, None])
LABELS = st.sampled_from(["Dup", " dup", "Other", ""])
PLACE_PLANS = st.lists(
    st.tuples(LONS, DATASETS, CONFIDENCES, LABELS), min_size=0, max_size=5
)


class FatesOracle(unittest.TestCase):
    """place_fates against the build's own build_places over the whole plan space."""

    @settings(max_examples=40, deadline=None)
    @given(PLACE_PLANS)
    @example([(51.1, "syn-source", 0.5, "Dup"), (51.1001, "syn-x", 0.9, " dup")])
    @example([])
    def test_fates_equal_the_builds_survivors(
        self, plan: list[tuple[float, str, float | None, str]]
    ) -> None:
        with tempfile.TemporaryDirectory() as name:
            rows = [
                place(f"SYN-P-{n}", lon, 25.1, label, dataset=data, confidence=conf)
                for n, (lon, data, conf, label) in enumerate(plan)
            ]
            places: tuple[ReadPlace, ...] = ()
            if rows:
                entries = load_registry()
                entry = next(row for row in entries if row.key == PLACES_KEY)
                write_cached(
                    Path(name), entry, parquet(Path(name), PLACE_COLUMNS, rows)
                )
                located = _place_from_registry(Path(name), entries)
                assert located is not None
                path, receipt = located
                places = read_place_file(path, "ar")
            licences = (("syn-source", "SYN-LICENCE"),)
            fates, attributed = keys_tool.place_fates(places, BOUNDARY, licences)
            if not rows:
                self.assertEqual((fates, attributed), ({}, frozenset()))
                return
            every = tuple((token, "SYN-LICENCE") for token in ("syn-source", "syn-x"))
            built = build_places(
                path,
                arabic_tag="ar",
                boundary=BOUNDARY,
                grid=[
                    {"cell": h3.str_to_int(h3.latlng_to_cell(25.1, lon, 9))}
                    for lon, _d, _c, _l in plan
                ],
                attribution=every,
                places_receipt=receipt,
            )
        dropped = {
            part for p in built.places for part in p.merged_ids.split(";") if part
        }
        survivors = {p.place_id for p in built.places} - dropped
        self.assertEqual({k for k, v in fates.items() if v == "ok"}, survivors)
        self.assertEqual(set(fates), {f"SYN-P-{n}" for n in range(len(plan))})
        for key in dropped:
            self.assertEqual(fates[key], "duplicate_dropped")
        self.assertEqual(
            attributed,
            frozenset(
                f"SYN-P-{n}"
                for n, (_l, data, _c, _n) in enumerate(plan)
                if data == "syn-source"
            ),
        )


class AttributionTokens(World):
    def run_tokens(self, output: Path) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tokens_tool.main([str(self.cache), str(output)])
        return code, out.getvalue()

    def test_distinct_tokens_with_counts_and_no_value_printed(self) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.1, 25.1, "A", dataset="syn-b"),
                place("SYN-P-2", 51.2, 25.2, "B", dataset="syn-a"),
                place("SYN-P-3", 51.3, 25.3, "C", dataset="syn-a"),
                place("SYN-P-4", 51.3, 25.3, "D", dataset=""),
                place("SYN-P-5", 51.3, 25.3, "E", dataset="OpenStreetMap"),
                place("SYN-P-6", 51.9, 25.3, "F", dataset="syn-outside"),
            ]
        )
        output = self.scratch / "tokens.csv"
        self.assertEqual(self.run_tokens(output), (0, "tokens=2\n"))
        self.assertEqual(
            output.read_text(encoding="utf-8"), "token,count\nsyn-a,2\nsyn-b,1\n"
        )

    def test_review_file_name_is_refused(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "A")])
        output = self.scratch / "places_ovt_attribution.csv"
        self.assertEqual(
            self.run_tokens(output), (2, "REFUSED output_is_review_file\n")
        )
        self.assertFalse(output.exists())

    def test_existing_worksheet_is_refused(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "A")])
        output = self.scratch / "tokens.csv"
        output.write_text("kept\n", encoding="utf-8")
        self.assertEqual(self.run_tokens(output), (2, "REFUSED output_exists\n"))
        self.assertEqual(output.read_text(encoding="utf-8"), "kept\n")

    def test_unreceipted_places_file_is_refused(self) -> None:
        self.assertEqual(
            self.run_tokens(self.scratch / "tokens.csv"),
            (2, "REFUSED places_file_unreceipted\n"),
        )


if __name__ == "__main__":
    unittest.main()
