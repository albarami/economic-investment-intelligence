"""Invented Overture-shaped Parquet only; every place, name and id is made up."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
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
from eii_custodian.publicdata.places.review import load_attribution
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
# The source's building names shape: primary, a common map and rules entries.
BUILDING_NAMES = (
    'STRUCT("primary" VARCHAR, common MAP(VARCHAR, VARCHAR), rules STRUCT('
    "variant VARCHAR, language VARCHAR, value VARCHAR, between DOUBLE[], "
    "side VARCHAR)[])"
)
BUILDING_COLUMNS = (("id", "VARCHAR"), ("geometry", "BLOB"), ("names", BUILDING_NAMES))


def place(
    pid: str,
    lon: float,
    lat: float,
    name: str = "",
    arabic: str | None = None,
    dataset: str = "syn-source",
    confidence: float | None = 0.9,
    category: str = "district",
) -> dict[str, object]:
    """An invented place; its default category is one of the landmark areas."""
    common = {} if arabic is None else {"ar": arabic}
    return {
        "id": pid,
        "geometry": Point(lon, lat).wkb,
        "confidence": confidence,
        "names": {"primary": name, "common": common},
        "sources": [{"property": "", "dataset": dataset, "license": None}],
        "basic_category": category,
        "addresses": [{"freeform": "SYN street", "country": "SYN"}],
        "bbox": {"xmin": lon, "xmax": lon, "ymin": lat, "ymax": lat},
    }


def building(
    bid: str,
    west: float,
    south: float,
    size: float = 0.01,
    names: Mapping[str, object] | None = None,
) -> dict[str, object]:
    shape = box(west, south, west + size, south + size)
    return {"id": bid, "geometry": shape.wkb, "names": names}


def names_of(
    primary: str | None = None,
    common: Mapping[str, str] | None = None,
    rules: Sequence[str] = (),
) -> dict[str, object]:
    """A footprint's own names in the source's shape."""
    return {
        "primary": primary,
        "common": None if common is None else dict(common),
        "rules": [
            {
                "variant": "alternate",
                "language": None,
                "value": value,
                "between": None,
                "side": None,
            }
            for value in rules
        ],
    }


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
        with patch.object(keys_tool, "frame_boundary", return_value=BOUNDARY):
            return self.run_unpatched(*extra)

    def run_unpatched(self, *extra: str) -> tuple[int, str]:
        return self.streams(keys_tool.main, str(self.cache), str(self.review), *extra)

    def streams(self, main: Callable[[list[str]], int], *argv: str) -> tuple[int, str]:
        """Run one CLI; stderr must stay empty and stdout is returned."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        self.assertEqual(err.getvalue(), "")
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
            "landmark:0 matches=1 kept=true footprints=na "
            "inside=na written=true reason=ok basis=place_name excluded=0\n",
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
            "matches=0 kept=na footprints=na inside=na written=false reason=match_0",
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
            "matches=n kept=na footprints=na inside=na written=false reason=match_n",
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
            "building:0 matches=1 kept=true footprints=1 "
            "inside=true written=true reason=ok basis=place_point excluded=0\n",
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
            "matches=1 kept=true footprints=0 inside=na "
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
            "matches=1 kept=true footprints=n inside=na "
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
            "matches=1 kept=true footprints=1 inside=false "
            "written=false reason=outside_boundary",
            out,
        )

    def test_check_agrees_after_fill_and_flags_a_planted_mismatch(self) -> None:
        self.flagship_world([building("SYN-B-1", 51.1, 25.1)])
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(
            self.run_tool("--check"),
            (0, "building:0 check=true kept=true\n"),
        )
        rows = self.rows("flagship_candidates.yaml")
        rows[0]["record_key"] = "SYN-B-WRONG"
        self.review_files(flagship=rows)
        self.assertEqual(
            self.run_tool("--check"),
            (1, "building:0 check=false kept=true\n"),
        )

    def test_check_flags_a_wrong_source_id(self) -> None:
        self.flagship_world([building("SYN-B-1", 51.1, 25.1)])
        filled = spec(
            "building:0", "Syn Tower", source_id="places_ovt", record_key="SYN-B-1"
        )
        self.review_files(flagship=[filled])
        self.assertEqual(
            self.run_tool("--check"),
            (1, "building:0 check=false kept=true\n"),
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
            "landmark:0 matches=0 kept=false footprints=na "
            "inside=na written=false reason=excluded_by_keep_osm_not_merged "
            "basis=place_name excluded=1\n",
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
            "landmark:0 matches=0 kept=false footprints=na "
            "inside=na written=false reason=duplicate_dropped "
            "basis=place_name excluded=1\n",
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

    def drop_attribution_row(self) -> None:
        """The one change: the matching token's licence row is removed."""
        (self.review / "places_ovt_attribution.csv").write_text(
            "dataset_token,licence\n", encoding="utf-8"
        )

    def test_missing_attribution_row_withholds_the_key(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.drop_attribution_row()
        before = (self.review / "showcase_gazetteer.yaml").read_bytes()
        self.assertEqual(
            self.run_tool(),
            (
                0,
                "landmark:0 matches=0 kept=false footprints=na inside=na "
                "written=false reason=excluded_by_keep_attribution_missing "
                "basis=place_name excluded=1\n",
            ),
        )
        self.assertEqual((self.review / "showcase_gazetteer.yaml").read_bytes(), before)

    def test_check_fails_a_filled_key_whose_attribution_row_is_missing(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        filled = spec(
            "landmark:0", "Syn Souq", source_id="places_ovt", record_key="SYN-P-1"
        )
        self.review_files(gazetteer=[filled])
        self.assertEqual(
            self.run_tool("--check"), (0, "landmark:0 check=true kept=true\n")
        )
        self.drop_attribution_row()
        self.assertEqual(
            self.run_tool("--check"), (1, "landmark:0 check=false kept=false\n")
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
            (1, "landmark:0 check=false kept=false\n"),
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
            place("SYN-P-9", 51.5, 25.4, "F", dataset="syn-x"),
        ]
        self.cache_places(rows)
        located = _place_from_registry(self.cache, list(self.registry.values()))
        assert located is not None
        path, receipt = located
        places = read_place_file(path, "ar")
        fates = keys_tool.place_fates(
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
                "SYN-P-9": "excluded_by_keep_attribution_missing",
            },
        )


class FrameBoundary(World):
    """The real reader path over an invented municipality archive."""

    def cache_archive(self, body: bytes) -> None:
        write_cached(self.cache, self.registry["bnd_hdx"], body)

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
            "landmark:0", 1, True, None, None, "SYN-P-1", "ok", "place_name"
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

        changed = spec(
            "landmark:0", "Syn Souq", source_id="places_ovt", record_key="SYN-P-1"
        )
        with self.assertRaises(keys_tool.ReviewError) as caught:
            keys_tool.write_reviewed([(path, [changed], other)])
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


class RowBinding(World):
    """Each proposal fills only the row it came from (finding F-1)."""

    def two_rows(self, second_key: str) -> list[dict[str, object]]:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        rows = [spec("landmark:0", "Syn Tower"), spec(second_key, "Syn Souq")]
        self.review_files(gazetteer=rows)
        return rows

    def test_distinct_keys_fill_only_the_matched_row(self) -> None:
        self.two_rows("landmark:1")
        self.assertEqual(self.run_tool()[0], 0)
        stored = self.rows("showcase_gazetteer.yaml")
        self.assertEqual([row["record_key"] for row in stored], [None, "SYN-P-1"])

    def test_repeated_place_key_is_refused_before_writing(self) -> None:
        self.two_rows("landmark:0")
        before = (self.review / "showcase_gazetteer.yaml").read_bytes()
        self.assertEqual(self.run_tool(), (2, "REFUSED duplicate_place_key\n"))
        self.assertEqual((self.review / "showcase_gazetteer.yaml").read_bytes(), before)

    def test_repeated_place_key_is_refused_by_check(self) -> None:
        self.two_rows("landmark:0")
        self.assertEqual(self.run_tool("--check"), (2, "REFUSED duplicate_place_key\n"))

    def test_apply_binds_each_proposal_to_its_own_row(self) -> None:
        rows = [spec("landmark:0", "Syn Tower"), spec("landmark:0", "Syn Souq")]
        found = keys_tool.Proposal(
            "landmark:0", 1, True, None, None, "SYN-P-1", "ok", "place_name"
        )
        filled = keys_tool.apply(rows, [None, found], "places_ovt")
        self.assertEqual([row["record_key"] for row in filled], [None, "SYN-P-1"])


class SelectedParts(World):
    """Every selected, active building part verifies, or H1 refuses (F-3)."""

    def test_changed_body_of_a_selected_part_is_refused(self) -> None:
        self.cache_places([place("SYN-P-1", 51.105, 25.105, "Syn Tower")])
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1)])
        body = parquet(
            self.scratch, BUILDING_COLUMNS, [building("SYN-B-2", 51.1, 25.1)]
        )
        stored = write_cached(self.cache, self.registry[PARTS[1]], body)
        self.review_files(flagship=[spec("building:0", "Syn Tower")])
        before = (self.review / "flagship_candidates.yaml").read_bytes()
        stored.chmod(0o644)
        stored.write_bytes(body[:-1] + bytes([body[-1] ^ 1]))
        self.assertEqual(self.run_tool(), (2, "REFUSED buildings_file_unverified\n"))
        self.assertEqual(
            (self.review / "flagship_candidates.yaml").read_bytes(), before
        )


FLAGSHIP = "flagship_candidates.yaml"
GAZETTEER = "showcase_gazetteer.yaml"
LOADERS = {name: loader for name, _source, loader in keys_tool.FILES}


def stale_reload(target: str) -> keys_tool.Loader:
    """The target file's own loader, returning no row for a staged copy only."""

    def load(
        path: Path, cache: Path | None
    ) -> tuple[str, tuple[Mapping[str, object], ...]]:
        version, rows = LOADERS[target](path, cache)
        return (version, ()) if path.name.startswith(".review-") else (version, rows)

    return load


class Pair(World):
    """A valid flagship and gazetteer pair that fills one key in each file."""

    def setUp(self) -> None:
        super().setUp()
        self.cache_places(
            [
                place("SYN-P-1", 51.105, 25.105, "Syn Tower"),
                place("SYN-P-2", 51.2, 25.2, "Syn Souq"),
            ]
        )
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1)])

    def valid(self) -> dict[str, list[dict[str, object]]]:
        return {
            FLAGSHIP: [spec("building:0", "Syn Tower")],
            GAZETTEER: [spec("landmark:0", "Syn Souq")],
        }

    def files(self) -> dict[str, bytes]:
        return {item.name: item.read_bytes() for item in self.review.iterdir()}

    def write(self, rows: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
        self.review_files(flagship=rows[FLAGSHIP], gazetteer=rows[GAZETTEER])


class BothFilesStaged(Pair):
    """Both files are staged and reloaded before either is replaced (lens 2, 1)."""

    KINDS = ("aliases_form", "overwrite_refused", "duplicate_place_key")

    def plant(
        self, rows: dict[str, list[dict[str, object]]], name: str, kind: str
    ) -> None:
        """Change ONE input of one file so that file alone refuses with kind."""
        row = rows[name][0]
        if kind == "aliases_form":
            row["aliases"] = "syn alias"
        elif kind == "overwrite_refused":
            row["source_id"] = "bldg_ovt" if name == FLAGSHIP else "places_ovt"
        elif kind == "duplicate_place_key":
            rows[name].append(spec(str(row["place_key"]), "Syn Other"))

    def test_valid_pair_writes_both_and_leaves_no_staged_file(self) -> None:
        self.write(self.valid())
        before = set(self.files())
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(self.rows(FLAGSHIP)[0]["record_key"], "SYN-B-1")
        self.assertEqual(self.rows(GAZETTEER)[0]["record_key"], "SYN-P-2")
        self.assertEqual(set(self.files()), before)

    def test_refusal_in_the_second_file_changes_neither(self) -> None:
        for kind in self.KINDS:
            with self.subTest(kind=kind):
                rows = self.valid()
                self.plant(rows, GAZETTEER, kind)
                self.write(rows)
                before = self.files()
                self.assertEqual(self.run_tool(), (2, f"REFUSED {kind}\n"))
                self.assertEqual(self.files(), before)

    def test_reload_mismatch_of_the_second_file_changes_neither(self) -> None:
        self.write(self.valid())
        before = self.files()
        files = tuple(
            (name, source, stale_reload(name) if name == GAZETTEER else loader)
            for name, source, loader in keys_tool.FILES
        )
        with patch.object(keys_tool, "FILES", files):
            self.assertEqual(self.run_tool(), (2, "REFUSED reload_mismatch\n"))
        self.assertEqual(self.files(), before)

    def test_every_location_and_kind_changes_neither(self) -> None:
        """Exhaustive over the domain: kind x {first, second, both} files."""
        for kind in (*self.KINDS, "reload_mismatch"):
            for where in ((FLAGSHIP,), (GAZETTEER,), (FLAGSHIP, GAZETTEER)):
                with self.subTest(kind=kind, where=where):
                    rows = self.valid()
                    files = keys_tool.FILES
                    if kind == "reload_mismatch":
                        files = tuple(
                            (name, source, stale_reload(name) if name in where else f)
                            for name, source, f in keys_tool.FILES
                        )
                    else:
                        for name in where:
                            self.plant(rows, name, kind)
                    self.write(rows)
                    before = self.files()
                    with patch.object(keys_tool, "FILES", files):
                        run = self.run_tool()
                    self.assertEqual(run, (2, f"REFUSED {kind}\n"))
                    self.assertEqual(self.files(), before)


class SecondReplaceFailure(Pair):
    """A failed replacement restores every replaced target (lens 1, R1)."""

    def failing(
        self, target: str, failures: Mapping[str, int], at: int = 1
    ) -> contextlib.AbstractContextManager[object]:
        """target (a function of keys_tool.os or .shutil) raising PermissionError.

        failures maps a review file name, found in argument at, to the 1-based
        call on it that fails. For os.replace call 1 publishes the staged file
        and call 2 restores the original; for shutil.copymode call 1 stages and
        call 2 keeps the original.
        """
        module, name = target.split(".")
        owner = getattr(keys_tool, module)
        real = getattr(owner, name)
        calls: dict[str, int] = {}

        def fail(*args: str | Path) -> None:
            key = Path(args[at]).name
            calls[key] = calls.get(key, 0) + 1
            if failures.get(key) == calls[key]:
                raise PermissionError("syn")
            real(*args)

        return patch.object(owner, name, fail)

    def modes(self) -> dict[str, int]:
        return {item.name: item.stat().st_mode for item in self.review.iterdir()}

    def refused(self, failures: Mapping[str, int]) -> None:
        self.write(self.valid())
        before, modes = self.files(), self.modes()
        with self.failing("os.replace", failures):
            run = self.run_tool()
        self.assertEqual(run, (2, "REFUSED filesystem_refused\n"))
        self.assertEqual(self.files(), before)
        self.assertEqual(self.modes(), modes)

    def test_second_replacement_failure_restores_the_first(self) -> None:
        self.refused({GAZETTEER: 1})

    def test_first_replacement_failure_changes_neither(self) -> None:
        self.refused({FLAGSHIP: 1})

    def test_failed_restore_is_its_own_reason_and_keeps_the_original(self) -> None:
        self.write(self.valid())
        before = self.files()
        with self.failing("os.replace", {GAZETTEER: 1, FLAGSHIP: 2}):
            run = self.run_tool()
        self.assertEqual(run, (3, "FAILED rollback_failed\n"))
        after = self.files()
        self.assertEqual(after[GAZETTEER], before[GAZETTEER])
        kept = sorted(set(after) - set(before))
        self.assertEqual(len(kept), 1)
        self.assertEqual(after[kept[0]], before[FLAGSHIP])

    def test_failed_copy_of_the_second_original_changes_neither(self) -> None:
        self.write(self.valid())
        before = self.files()
        with self.failing("shutil.copymode", {GAZETTEER: 2}, at=0):
            run = self.run_tool()
        self.assertEqual(run, (2, "REFUSED filesystem_refused\n"))
        self.assertEqual(self.files(), before)


class CleanupNeverMasks(Pair):
    """A failed cleanup never replaces the error being unwound (lens 1, R1).

    The review directory turns read-only (0500) at one point, with real OS
    calls; its mode is restored before the files are read back.
    """

    @contextlib.contextmanager
    def read_only_from(self, target: str, after: bool = False) -> Iterator[None]:
        """os.replace of keys_tool makes the directory read-only around target."""
        mode, real = self.review.stat().st_mode, os.replace

        def replace(source: str | Path, destination: str | Path) -> None:
            hit = Path(destination).name == target
            if hit and not after:
                self.review.chmod(0o500)
            real(source, destination)
            if hit and after:
                self.review.chmod(0o500)

        try:
            with patch("review_place_keys.os.replace", replace):
                yield
        finally:
            self.review.chmod(mode)

    def test_read_only_directory_after_first_replacement_is_rollback_failed(
        self,
    ) -> None:
        self.write(self.valid())
        before = self.files()
        with self.read_only_from(GAZETTEER):
            run = self.run_tool()
        self.assertEqual(run, (3, "FAILED rollback_failed\n"))
        after = self.files()
        self.assertEqual(after[GAZETTEER], before[GAZETTEER])
        extra = set(after) - set(before)
        kept = [name for name in extra if after[name] == before[FLAGSHIP]]
        self.assertEqual(len(kept), 1)

    def test_read_only_directory_before_first_replacement_is_refused(self) -> None:
        """An OSError replacement changed nothing: no restore, so no rollback."""
        self.write(self.valid())
        before = self.files()
        with self.read_only_from(FLAGSHIP):
            run = self.run_tool()
        self.assertEqual(run, (2, "REFUSED filesystem_refused\n"))
        after = self.files()
        self.assertEqual(
            [after[FLAGSHIP], after[GAZETTEER]], [before[FLAGSHIP], before[GAZETTEER]]
        )

    def test_stage_cleanup_failure_keeps_the_reload_refusal(self) -> None:
        self.write(self.valid())
        before, mode = self.files(), self.review.stat().st_mode

        def load(
            path: Path, cache: Path | None
        ) -> tuple[str, tuple[Mapping[str, object], ...]]:
            if path.name.startswith(".review-"):
                self.review.chmod(0o500)
            return stale_reload(FLAGSHIP)(path, cache)

        files = tuple(
            (name, source, load if name == FLAGSHIP else loader)
            for name, source, loader in keys_tool.FILES
        )
        try:
            with patch.object(keys_tool, "FILES", files):
                run = self.run_tool()
        finally:
            self.review.chmod(mode)
        self.assertEqual(run, (2, "REFUSED reload_mismatch\n"))
        after = self.files()
        self.assertEqual(
            [after[FLAGSHIP], after[GAZETTEER]], [before[FLAGSHIP], before[GAZETTEER]]
        )

    def test_write_beside_cleanup_failure_keeps_its_own_error(self) -> None:
        self.write(self.valid())
        mode = self.review.stat().st_mode

        def copymode(source: Path, destination: Path) -> None:
            self.review.chmod(0o500)
            raise keys_tool.ReviewError("syn_copy_failed")

        try:
            with patch("review_place_keys.shutil.copymode", copymode):
                with self.assertRaises(keys_tool.ReviewError) as caught:
                    keys_tool.write_beside(self.review / FLAGSHIP, b"syn")
        finally:
            self.review.chmod(mode)
        self.assertEqual(caught.exception.reason, "syn_copy_failed")

    def test_discard_removes_the_rest_after_a_failure(self) -> None:
        blocked, loose = self.scratch / "syn-folder", self.scratch / "syn-file"
        blocked.mkdir()
        loose.write_bytes(b"syn")
        keys_tool.discard([blocked, loose])
        self.assertEqual([blocked.exists(), loose.exists()], [True, False])

    @settings(deadline=None)
    @given(st.lists(st.sampled_from(("blocked", "loose", "absent")), max_size=6))
    def test_discard_over_every_order_of_kinds(self, kinds: list[str]) -> None:
        """Every loose file goes; every blocked one stays; nothing escapes."""
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / f"syn-{index}" for index in range(len(kinds))]
            for path, kind in zip(paths, kinds, strict=True):
                if kind == "blocked":
                    path.mkdir()
                elif kind == "loose":
                    path.write_bytes(b"syn")
            keys_tool.discard(paths)
            exists = [path.exists() for path in paths]
            self.assertEqual(exists, [kind == "blocked" for kind in kinds])

    def test_cleanup_failure_after_both_replacements_keeps_the_success(self) -> None:
        """Both files are replaced: success (c), never a refusal of a change."""
        self.write(self.valid())
        before = set(self.files())
        with self.read_only_from(GAZETTEER, after=True):
            run = self.run_tool()
        self.assertEqual(run[0], 0)
        self.assertEqual(len(set(self.files()) - before), 2)
        self.assertEqual(self.rows(FLAGSHIP)[0]["record_key"], "SYN-B-1")
        self.assertEqual(self.rows(GAZETTEER)[0]["record_key"], "SYN-P-2")


class InterruptedUnwinding(Pair):
    """A KeyboardInterrupt while unwinding never unlinks an original (R1, CF4)."""

    def scripted(
        self, script: Mapping[tuple[str, int], tuple[type[BaseException], bool]]
    ) -> contextlib.AbstractContextManager[object]:
        """os.replace raising script[(name, call)] = (error, after the real call)."""
        real, calls = os.replace, dict[str, int]()

        def replace(source: str | Path, destination: str | Path) -> None:
            name = Path(destination).name
            calls[name] = calls.get(name, 0) + 1
            error, after = script.get((name, calls[name]), (None, False))
            if error is not None and not after:
                raise error("syn")
            real(source, destination)
            if error is not None:
                raise error("syn")

        return patch("review_place_keys.os.replace", replace)

    def settled(self) -> tuple[int, str]:
        """run_tool, with an escaped interrupt failing the test, not the run."""
        try:
            return self.run_tool()
        except (KeyboardInterrupt, SystemExit) as escaped:
            self.fail(f"escaped {type(escaped).__name__}")

    def kept_original(self, before: Mapping[str, bytes]) -> None:
        """The gazetteer is unchanged; one extra file holds the flagship's bytes."""
        after = self.files()
        self.assertEqual(after[GAZETTEER], before[GAZETTEER])
        kept = sorted(set(after) - set(before))
        self.assertEqual(len(kept), 1)
        self.assertEqual(after[kept[0]], before[FLAGSHIP])

    def test_interrupted_restore_is_rollback_failed_and_keeps_the_original(
        self,
    ) -> None:
        self.write(self.valid())
        before = self.files()
        script = {
            (GAZETTEER, 1): (PermissionError, False),
            (FLAGSHIP, 2): (KeyboardInterrupt, False),
        }
        with self.scripted(script):
            run = self.settled()
        self.assertEqual(run, (3, "FAILED rollback_failed\n"))
        self.kept_original(before)

    def test_restore_that_escapes_keeps_every_original(self) -> None:
        self.write(self.valid())
        before = self.files()
        script = {(GAZETTEER, 1): (PermissionError, False)}
        with (
            self.scripted(script),
            patch.object(keys_tool, "restore", side_effect=KeyboardInterrupt),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.run_tool()
        after = self.files()
        self.assertIn(before[FLAGSHIP], after.values())
        self.assertEqual(after[GAZETTEER], before[GAZETTEER])

    def test_interrupt_around_the_second_replacement_changes_neither(self) -> None:
        """Before or after the real call: the interrupt passes, bytes unchanged."""
        for after in (False, True):
            with self.subTest(after=after):
                self.write(self.valid())
                before = self.files()
                with self.scripted({(GAZETTEER, 1): (KeyboardInterrupt, after)}):
                    with self.assertRaises(KeyboardInterrupt):
                        self.run_tool()
                self.assertEqual(self.files(), before)

    def test_system_exit_in_restore_is_rollback_failed(self) -> None:
        self.write(self.valid())
        before = self.files()
        script = {
            (GAZETTEER, 1): (PermissionError, False),
            (FLAGSHIP, 2): (SystemExit, False),
        }
        with self.scripted(script):
            run = self.settled()
        self.assertEqual(run, (3, "FAILED rollback_failed\n"))
        self.kept_original(before)


Fault = type[BaseException]
FAULTS: tuple[Fault, ...] = (OSError, KeyboardInterrupt)
Plan = dict[int, Fault]


class Stream:
    """A written file whose write and close are fault points; close always closes."""

    def __init__(self, inner: io.BufferedWriter, injector: Injector) -> None:
        self.inner, self.injector = inner, injector

    def __enter__(self) -> Stream:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, data: bytes) -> int:
        self.injector.point("write", None)
        return self.inner.write(data)

    def close(self) -> None:
        try:
            self.injector.point("close", None)
        finally:
            self.inner.close()


class Injector:
    """Counts each filesystem call of write_reviewed; plan[i] replaces call i.

    The fault is raised instead of the call. A call nested inside a counted
    one (a loader's own read) is not counted; os.replace inside restore is
    counted as "restore".
    """

    def __init__(self, plan: Plan) -> None:
        self.plan = plan
        self.calls: list[str] = []
        self.faulted: list[tuple[str, object]] = []
        self.active = self.restoring = False
        self.depth = 0

    def point(self, kind: str, subject: object) -> None:
        if kind == "replace" and self.restoring:
            kind = "restore"
        fault = self.plan.get(len(self.calls))
        self.calls.append(kind)
        if fault is not None:
            self.faulted.append((kind, subject))
            raise fault("syn")

    def wrap(self, kind: str, real: Callable[..., object]) -> Callable[..., object]:
        def call(*args: object, **kwargs: object) -> object:
            if not self.active or self.depth:
                return real(*args, **kwargs)
            self.point(kind, args[0] if args else None)
            self.depth += 1
            try:
                return real(*args, **kwargs)
            finally:
                self.depth -= 1

        return call

    def flagged(self, flag: str, real: Callable[..., object]) -> Callable[..., object]:
        def call(*args: object) -> object:
            setattr(self, flag, True)
            try:
                return real(*args)
            finally:
                setattr(self, flag, False)

        return call

    @contextlib.contextmanager
    def patched(self) -> Iterator[None]:
        opened = self.wrap("fdopen", os.fdopen)

        def fdopen(*args: object) -> object:
            stream = opened(*args)
            live = self.active and not self.depth
            return Stream(stream, self) if live else stream  # type: ignore[arg-type]

        counted = (
            (tempfile, "mkstemp"),
            (shutil, "copymode"),
            (os, "replace"),
            (Path, "read_bytes"),
            (Path, "unlink"),
        )
        files = tuple((n, s, self.wrap("reload", f)) for n, s, f in keys_tool.FILES)
        restore = self.flagged("restoring", keys_tool.restore)
        with contextlib.ExitStack() as stack:
            for owner, name in counted:
                real = getattr(owner, name)
                stack.enter_context(patch.object(owner, name, self.wrap(name, real)))
            stack.enter_context(patch.object(os, "fdopen", fdopen))
            stack.enter_context(patch.object(keys_tool, "FILES", files))
            stack.enter_context(patch.object(keys_tool, "restore", restore))
            active = self.flagged("active", keys_tool.write_reviewed)
            stack.enter_context(patch.object(keys_tool, "write_reviewed", active))
            yield


def decisive(injector: Injector) -> Plan:
    """The plan without its cleanup faults: every counted unlink is cleanup."""
    return {i: f for i, f in injector.plan.items() if injector.calls[i] != "unlink"}


class ExhaustiveFaults(Pair):
    """Every fault at every filesystem call keeps the contract (R8, REVIEW-CF5).

    Outcomes: (a) both targets unchanged with ``REFUSED filesystem_refused``
    exit 2, or the interrupt passing through; (b) ``FAILED rollback_failed``
    exit 3, exactly when a restore failed, each target's original kept; (c)
    success. A leftover file is only one whose own unlink faulted, or (b)'s
    kept original.
    """

    CALLS = 30

    def setUp(self) -> None:
        super().setUp()
        self.write(self.valid())
        licences = load_attribution(self.review / keys_tool.ATTRIBUTION, None)
        inputs = keys_tool.load_inputs(
            self.cache, list(self.registry.values()), BOUNDARY, "ar", licences[1]
        )
        for name, value in (("load_inputs", inputs), ("load_registry", [])):
            patcher = patch.object(keys_tool, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.outcomes: dict[frozenset[tuple[int, Fault]], tuple[int, str] | str] = {}
        self.before, self.modes = self.files(), self.stats()
        self.success, control = self.case({})
        self.assertEqual(self.success[0], 0)
        self.published = self.files()
        self.control = control.calls

    def stats(self) -> dict[str, int]:
        return {item.name: item.stat().st_mode for item in self.review.iterdir()}

    def case(self, plan: Plan) -> tuple[tuple[int, str] | str, Injector]:
        for item in self.review.iterdir():
            if item.name.startswith(".review-"):
                item.unlink()
        self.write(self.valid())
        injector = Injector(plan)
        outcome: tuple[int, str] | str
        with injector.patched():
            try:
                outcome = self.run_tool()
            except KeyboardInterrupt:
                outcome = "KeyboardInterrupt"
        self.outcomes[frozenset(plan.items())] = outcome
        return outcome, injector

    def holds(self, outcome: tuple[int, str] | str, injector: Injector) -> None:
        after, targets = self.files(), (FLAGSHIP, GAZETTEER)
        extra = set(after) - set(self.before)
        kinds = [kind for kind, _subject in injector.faulted]
        unlinked = {Path(str(s)).name for k, s in injector.faulted if k == "unlink"}
        if outcome == (3, "FAILED rollback_failed\n"):
            self.assertIn("restore", kinds)
            originals = [self.before[name] for name in targets]
            for name in targets:
                kept = [after[item] for item in extra] + [after[name]]
                self.assertIn(self.before[name], kept)
            for item in extra - unlinked:
                self.assertIn(after[item], originals)
            return
        self.assertNotIn("restore", kinds, "a failed restore ends in rollback_failed")
        self.assertLessEqual(extra, unlinked)
        self.assertEqual(
            {n: self.stats()[n] for n in targets}, {n: self.modes[n] for n in targets}
        )
        if outcome == self.success:
            self.assertEqual(
                [after[n] for n in targets], [self.published[n] for n in targets]
            )
            return
        if outcome == "KeyboardInterrupt":
            self.assertIn(KeyboardInterrupt, decisive(injector).values())
        else:
            self.assertEqual(outcome, (2, "REFUSED filesystem_refused\n"))
        self.assertEqual([after[n] for n in targets], [self.before[n] for n in targets])

    def sweep(self, plans: Sequence[Plan]) -> list[tuple[Plan, Injector]]:
        """Run and check every plan, each in its own subtest."""
        done = []
        for plan in plans:
            label = ",".join(f"{i}:{f.__name__}" for i, f in sorted(plan.items()))
            with self.subTest(plan=label):
                outcome, injector = self.case(plan)
                done.append((plan, injector))
                self.holds(outcome, injector)
                self.assertEqual(outcome, self.decided(injector), "cleanup masked it")
        return done

    def decided(self, injector: Injector) -> tuple[int, str] | str:
        """The outcome of the same plan without its cleanup faults (CF6-01).

        A cleanup fault is suppressed and shifts no later call, so the
        outcome decided before cleanup, type and reason or exit and line,
        is the outcome of the whole plan.
        """
        plan = decisive(injector)
        if frozenset(plan.items()) not in self.outcomes:
            self.case(plan)
        return self.outcomes[frozenset(plan.items())]

    def deeper(self, runs: Sequence[tuple[Plan, Injector]]) -> list[Plan]:
        """One more fault at every later call of each run, of each kind."""
        return [
            {**plan, index: fault}
            for plan, injector in runs
            for index in range(max(plan) + 1, len(injector.calls))
            for fault in FAULTS
        ]

    def singles(self) -> list[Plan]:
        return [{index: fault} for index in range(self.CALLS) for fault in FAULTS]

    def test_the_success_run_has_every_counted_call(self) -> None:
        self.assertEqual(len(self.control), self.CALLS)
        writes = ["mkstemp", "fdopen", "write", "close", "copymode"]
        staged = [*writes, "reload"]
        kept = ["read_bytes", *writes]
        expected = [*staged, *staged, *kept, *kept, "replace", "replace"]
        self.assertEqual(self.control, [*expected, *["unlink"] * 4])

    def test_copy_failure_then_cleanup_interrupt_keeps_the_refusal(self) -> None:
        """CF6-01: the staged copy fails, then its own cleanup is interrupted."""
        outcome, injector = self.case({4: OSError, 5: KeyboardInterrupt})
        self.assertEqual([kind for kind, _ in injector.faulted], ["copymode", "unlink"])
        self.assertEqual(outcome, (2, "REFUSED filesystem_refused\n"))
        after = self.files()
        self.assertEqual({n: after[n] for n in self.before}, self.before)

    def test_every_single_fault(self) -> None:
        self.assertEqual(len(self.sweep(self.singles())), 60)

    def test_every_second_fault(self) -> None:
        firsts = self.sweep(self.singles())
        self.assertEqual(len(self.sweep(self.deeper(firsts))), 296)

    def test_every_later_fault_after_a_failed_restore(self) -> None:
        """REVIEW-CF5: cleanup, or a second interrupt, never replaces (b)."""
        pairs = self.sweep(self.deeper(self.sweep(self.singles())))
        failed = [run for run in pairs if "restore" in (k for k, _ in run[1].faulted)]
        self.assertEqual(len(self.sweep(self.deeper(failed))), 52)


SECRETS = ("SYN-P-1", "Syn Souq", "syn souq", "51.1", "25.1", "/")


class ClosedRefusals(World):
    """Expected failures print one closed reason and no text of the failure (F-4)."""

    def refused(self, run: tuple[int, str], reason: str) -> None:
        self.assertEqual(run, (2, f"REFUSED {reason}\n"))
        for secret in (*SECRETS, str(self.root)):
            self.assertNotIn(secret, run[1].removeprefix("REFUSED "))

    def world(self) -> None:
        self.cache_places([place("SYN-P-1", 51.1, 25.1, "Syn Souq")])
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])

    def test_malformed_yaml_is_refused_without_its_text(self) -> None:
        self.world()
        (self.review / "showcase_gazetteer.yaml").write_text(
            '- {place_key: "Syn Souq", name_en: [SYN-P-1, 51.1, 25.1\n',
            encoding="utf-8",
        )
        self.refused(self.run_tool(), "review_file_unparsable")

    def test_undecodable_review_file_is_refused(self) -> None:
        self.world()
        (self.review / "showcase_gazetteer.yaml").write_bytes(b"- \xff Syn Souq\n")
        self.refused(self.run_tool(), "review_file_unparsable")

    def test_oversized_attribution_field_is_refused(self) -> None:
        self.world()
        (self.review / "places_ovt_attribution.csv").write_text(
            "dataset_token,licence\nsyn-source," + "x" * 200_000 + "\n",
            encoding="utf-8",
        )
        self.refused(self.run_tool(), "review_file_unparsable")

    def test_missing_review_file_is_refused(self) -> None:
        self.world()
        (self.review / "flagship_candidates.yaml").unlink()
        self.refused(self.run_tool(), "filesystem_refused")

    def test_invalid_snapshot_pins_are_refused(self) -> None:
        self.world()
        (self.cache / "snapshot_pins.json").write_text(
            json.dumps({PLACES_KEY: "SYN-P-1 not a hash"}), encoding="utf-8"
        )
        self.refused(self.run_tool(), "snapshot_refused")

    def stale_receipt(self, tool: object) -> contextlib.AbstractContextManager[object]:
        """The located places file with a receipt whose hash no longer matches."""
        located = _place_from_registry(self.cache, list(self.registry.values()))
        assert located is not None
        path, receipt = located
        stale = dataclasses.replace(receipt, sha256="0" * 64)
        return patch.object(tool, "_place_from_registry", return_value=(path, stale))

    def test_h1_bytes_changed_after_location_are_refused(self) -> None:
        self.world()
        with self.stale_receipt(keys_tool):
            self.refused(self.run_tool(), "receipt_mismatch")

    def test_h2_bytes_changed_after_location_are_refused(self) -> None:
        self.world()
        output = self.scratch / "tokens.csv"
        with self.stale_receipt(tokens_tool):
            run = self.streams(tokens_tool.main, str(self.cache), str(output))
        self.refused(run, "receipt_mismatch")
        self.assertFalse(output.exists())

    def test_h2_missing_output_parent_is_refused(self) -> None:
        self.world()
        output = self.scratch / "absent" / "tokens.csv"
        run = self.streams(tokens_tool.main, str(self.cache), str(output))
        self.refused(run, "filesystem_refused")
        self.assertFalse(output.parent.exists())

    def test_h2_invalid_snapshot_pins_are_refused(self) -> None:
        self.world()
        (self.cache / "snapshot_pins.json").write_text(
            json.dumps({PLACES_KEY: "SYN-P-1 not a hash"}), encoding="utf-8"
        )
        output = self.scratch / "tokens.csv"
        run = self.streams(tokens_tool.main, str(self.cache), str(output))
        self.refused(run, "snapshot_refused")
        self.assertFalse(output.exists())


def read_place(
    pid: str, name: str, lon: float = 51.105, lat: float = 25.105
) -> ReadPlace:
    return ReadPlace(
        pid,
        name,
        None,
        "district",
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
            places, (), frozenset(), {p.place_id: "ok" for p in places}, {}
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
            {},
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
            fates = keys_tool.place_fates(places, BOUNDARY, licences)
            if not rows:
                self.assertEqual(fates, {})
                return
            built = build_places(
                path,
                arabic_tag="ar",
                boundary=BOUNDARY,
                grid=[
                    {"cell": h3.str_to_int(h3.latlng_to_cell(25.1, lon, 9))}
                    for lon, _d, _c, _l in plan
                ],
                attribution=licences,
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
        for n, (_lon, data, _conf, _label) in enumerate(plan):
            if data == "syn-x":
                self.assertNotEqual(fates[f"SYN-P-{n}"], "ok")


class AttributionTokens(World):
    def run_tokens(self, output: Path) -> tuple[int, str]:
        return self.streams(tokens_tool.main, str(self.cache), str(output))

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

    def test_each_withheld_token_changes_one_input(self) -> None:
        """Baseline lists one token; each case changes one input and lists none."""
        cases: tuple[dict[str, object], ...] = (
            {},
            {"lon": 51.9},
            {"dataset": ""},
            {"dataset": "OpenStreetMap"},
        )
        for n, change in enumerate(cases):
            with self.subTest(change=change):
                values: dict[str, object] = {"lon": 51.1, "dataset": "syn-a"}
                values.update(change)
                lon, dataset = values["lon"], values["dataset"]
                assert isinstance(lon, float) and isinstance(dataset, str)
                self.cache_places([place("SYN-P-1", lon, 25.1, "A", dataset=dataset)])
                output = self.scratch / f"tokens-{n}.csv"
                listed = 0 if change else 1
                self.assertEqual(self.run_tokens(output), (0, f"tokens={listed}\n"))

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


SPIRE = names_of("Syn Spire")
UNRELATED = place("SYN-P-9", 51.45, 25.45, "Syn Elsewhere")
NAMED_LINE = (
    "building:0 matches=na kept=na footprints=1 inside=true "
    "written=true reason=ok basis=building_name excluded=na\n"
)


class BuildingNameBasis(World):
    """A footprint's own name keys a building row first (L4 proposal 1).

    The valid world: SYN-B-1 carries the row's name, SYN-B-2 is unnamed and no
    place carries the name. Each negative test changes ONE input of it.
    """

    def world(
        self,
        first: Mapping[str, object] | None = SPIRE,
        second: Mapping[str, object] | None = None,
        places: Sequence[Mapping[str, object]] = (UNRELATED,),
        west: float = 51.1,
        size: float = 0.01,
    ) -> None:
        self.cache_places(places)
        self.cache_buildings(
            0,
            [
                building("SYN-B-1", west, 25.1, size, names=first),
                building("SYN-B-2", 51.3, 25.3, names=second),
            ],
        )
        self.review_files(flagship=[spec("building:0", "Syn Spire", "برج مخترع")])

    def outcome(self) -> tuple[tuple[int, str], object]:
        run = self.run_tool()
        return run, self.rows(FLAGSHIP)[0]["record_key"]

    def refused_line(
        self, reason: str, footprints: str = "n", inside: str = "na"
    ) -> str:
        return (
            f"building:0 matches=na kept=na footprints={footprints} inside={inside} "
            f"written=false reason={reason} basis=building_name excluded=na\n"
        )

    def test_own_primary_name_keys_the_footprint_and_prints_no_name(self) -> None:
        self.world()
        run, key = self.outcome()
        self.assertEqual((run, key), ((0, NAMED_LINE), "SYN-B-1"))
        self.assertEqual(self.rows(FLAGSHIP)[0]["source_id"], "bldg_ovt")
        for secret in ("SYN-B-1", "Syn Spire", "spire", "51.1", "25.1"):
            self.assertNotIn(secret, run[1])

    def test_common_and_rules_names_are_the_footprints_own_names(self) -> None:
        for label, names in (
            ("common", names_of("Syn Unrelated", {"ar": "برج  مخترع"})),
            ("rules", names_of(None, None, ["SYN SPIRE"])),
        ):
            with self.subTest(label=label):
                self.setUp()
                self.world(first=names)
                self.assertEqual(self.outcome(), ((0, NAMED_LINE), "SYN-B-1"))

    def test_no_named_footprint_falls_back_to_the_place_point(self) -> None:
        self.world(first=None, places=[place("SYN-P-1", 51.105, 25.105, "Syn Spire")])
        run, key = self.outcome()
        self.assertEqual(key, "SYN-B-1")
        self.assertIn("written=true reason=ok basis=place_point excluded=0", run[1])

    def test_two_named_footprints_are_building_name_n(self) -> None:
        self.world(second=names_of("syn  spire"))
        self.assertEqual(
            self.outcome(), ((0, self.refused_line("building_name_n")), None)
        )

    def test_a_second_footprint_equal_only_when_folded_is_refused(self) -> None:
        """Latin diacritics, Arabic tashkeel and tatweel each fold to one name."""
        for first, second, row in (
            ("Syn Spîre", "Syn Spire", "Syn Spîre"),
            ("سوق مخترع", "سُوق مخترع", "سوق مخترع"),
            ("سوق مخترع", "ســوق مخترع", "سوق مخترع"),
        ):
            for planted in (False, True):
                with self.subTest(first=first, second=second, planted=planted):
                    self.setUp()
                    other = names_of(second if planted else "Syn Other")
                    self.world(first=names_of(first), second=other)
                    self.review_files(flagship=[spec("building:0", row)])
                    expected: tuple[tuple[int, str], str | None]
                    if planted:
                        expected = (
                            (0, self.refused_line("building_name_folded_n", "1")),
                            None,
                        )
                    else:
                        expected = ((0, NAMED_LINE), "SYN-B-1")
                    self.assertEqual(self.outcome(), expected)

    def test_a_place_point_in_another_footprint_is_basis_conflict(self) -> None:
        for point, planted in (((51.105, 25.105), False), ((51.305, 25.305), True)):
            with self.subTest(planted=planted):
                self.setUp()
                self.world(places=[place("SYN-P-1", *point, "Syn Spire")])
                expected: tuple[tuple[int, str], str | None]
                if planted:
                    expected = (
                        (0, self.refused_line("basis_conflict", "1", "true")),
                        None,
                    )
                else:
                    expected = ((0, NAMED_LINE), "SYN-B-1")
                self.assertEqual(self.outcome(), expected)

    def test_a_place_point_in_an_outside_footprint_is_basis_conflict(self) -> None:
        outside = building("SYN-B-3", 51.59, 25.3, 0.04)
        self.cache_places([place("SYN-P-1", 51.595, 25.32, "Syn Spire")])
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1, names=SPIRE), outside])
        self.review_files(flagship=[spec("building:0", "Syn Spire")])
        self.assertEqual(
            self.outcome(),
            ((0, self.refused_line("basis_conflict", "1", "true")), None),
        )

    def test_the_one_named_footprint_outside_the_boundary_stays_null(self) -> None:
        self.world(west=51.59, size=0.04)
        self.assertEqual(
            self.outcome(),
            ((0, self.refused_line("outside_boundary", "1", "false")), None),
        )

    def test_a_part_without_a_names_column_is_refused(self) -> None:
        self.world()
        columns = BUILDING_COLUMNS[:2]
        rows = [{"id": "SYN-B-1", "geometry": box(51.1, 25.1, 51.11, 25.11).wkb}]
        write_cached(
            self.cache, self.registry[PARTS[0]], parquet(self.scratch, columns, rows)
        )
        before = (self.review / FLAGSHIP).read_bytes()
        self.assertEqual(self.run_tool(), (2, "REFUSED building_names_missing\n"))
        self.assertEqual((self.review / FLAGSHIP).read_bytes(), before)

    def test_a_names_column_of_the_wrong_form_is_refused(self) -> None:
        self.world()
        columns = (*BUILDING_COLUMNS[:2], ("names", "VARCHAR"))
        rows = [
            {
                "id": "SYN-B-1",
                "geometry": box(51.1, 25.1, 51.11, 25.11).wkb,
                "names": "Syn Spire",
            }
        ]
        write_cached(
            self.cache, self.registry[PARTS[0]], parquet(self.scratch, columns, rows)
        )
        self.assertEqual(self.run_tool(), (2, "REFUSED building_names_form\n"))
        self.assertIsNone(self.rows(FLAGSHIP)[0]["record_key"])

    def test_check_agrees_then_fails_once_a_second_footprint_is_named(self) -> None:
        self.world()
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(
            self.run_tool("--check"), (0, "building:0 check=true kept=na\n")
        )
        filled = self.rows(FLAGSHIP)
        self.world(second=names_of("Syn Spire"))
        self.review_files(flagship=filled)
        self.assertEqual(
            self.run_tool("--check"), (1, "building:0 check=false kept=na\n")
        )


HOSTILE: tuple[object, ...] = ({"toString": None}, 7, None, [])
NAME_LEAVES = ("primary", "common.ar", "rules.0.value")


def leaf_paths(value: object, prefix: str = "") -> list[str]:
    """Every leaf and container path of a names value, the root excluded."""
    found = []
    items: list[tuple[str, object]] = []
    if isinstance(value, dict):
        items = [(str(key), item) for key, item in value.items()]
    elif isinstance(value, list):
        items = [(str(index), item) for index, item in enumerate(value)]
    for key, item in items:
        path = f"{prefix}{key}"
        found.append(path)
        found.extend(leaf_paths(item, path + "."))
    return found


def set_path(value: object, path: str, new: object) -> object:
    """A deep copy of value with the item at path replaced by new."""
    copied = json.loads(json.dumps(value))
    holder = copied
    parts = path.split(".")
    for part in parts[:-1]:
        holder = holder[int(part)] if isinstance(holder, list) else holder[part]
    last = parts[-1]
    if isinstance(holder, list):
        holder[int(last)] = new
    else:
        holder[last] = new
    return copied


class FootprintNamesForm(unittest.TestCase):
    """Exhaustive leaf mutation of the stored names value (L-1603)."""

    KINDS: tuple[dict[str, object], ...] = (
        names_of("Syn Spire", {"ar": "برج مخترع"}, ["Syn Alt"]),
        {"primary": "Syn Spire", "common": None, "rules": None},
    )

    def test_every_leaf_times_every_hostile_value_is_refused_or_read(self) -> None:
        cases = 0
        for kind in self.KINDS:
            for path in leaf_paths(kind):
                for hostile in HOSTILE:
                    with self.subTest(path=path, hostile=hostile):
                        cases += 1
                        mutated = set_path(kind, path, hostile)
                        try:
                            read = keys_tool.footprint_names(mutated)
                        except keys_tool.ReviewError as caught:
                            self.assertEqual(caught.reason, "building_names_form")
                            continue
                        self.assertLessEqual(read, keys_tool.footprint_names(kind))
                        if path in NAME_LEAVES:
                            self.assertIsNone(hostile, "a non-text name is read")
        self.assertEqual(cases, 4 * (10 + 3))

    def test_a_struct_without_its_named_fields_is_refused(self) -> None:
        kind = self.KINDS[0]
        rule = {"variant": "alternate", "language": None, "between": None}
        for planted in (
            {"common": None, "rules": None},
            {"primary": "Syn Spire", "rules": None},
            {"primary": "Syn Spire", "common": None},
            {**kind, "rules": [rule]},
        ):
            with self.subTest(planted=planted):
                with self.assertRaises(keys_tool.ReviewError) as caught:
                    keys_tool.footprint_names(planted)
                self.assertEqual(caught.exception.reason, "building_names_form")

    def test_the_root_of_every_hostile_form_is_refused_or_empty(self) -> None:
        for hostile in (*HOSTILE, "Syn Spire", b"syn"):
            with self.subTest(hostile=hostile):
                if hostile is None:
                    self.assertEqual(keys_tool.footprint_names(hostile), frozenset())
                    continue
                with self.assertRaises(keys_tool.ReviewError) as caught:
                    keys_tool.footprint_names(hostile)
                self.assertEqual(caught.exception.reason, "building_names_form")

    def test_valid_names_are_primary_common_and_rules_values(self) -> None:
        self.assertEqual(
            keys_tool.footprint_names(self.KINDS[0]),
            frozenset({"Syn Spire", "برج مخترع", "Syn Alt"}),
        )
        self.assertEqual(
            keys_tool.footprint_names(names_of(" ", {"ar": ""}, ["\t"])), frozenset()
        )


class FateFirstCounting(World):
    """Only places the build keeps count for match_0 and match_n (proposal 2)."""

    def world(self, second_lon: float) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.1, 25.1, "Syn Souq"),
                place("SYN-P-2", second_lon, 25.1, "Syn Souq"),
            ]
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])

    def test_an_excluded_namesake_is_not_counted(self) -> None:
        self.world(51.7)
        self.assertEqual(
            self.run_tool(),
            (
                0,
                "landmark:0 matches=1 kept=true footprints=na inside=na "
                "written=true reason=ok basis=place_name excluded=1\n",
            ),
        )
        self.assertEqual(self.rows(GAZETTEER)[0]["record_key"], "SYN-P-1")

    def test_a_kept_namesake_is_match_n(self) -> None:
        self.world(51.2)
        self.assertEqual(
            self.run_tool(),
            (
                0,
                "landmark:0 matches=n kept=na footprints=na inside=na "
                "written=false reason=match_n basis=place_name excluded=0\n",
            ),
        )
        self.assertIsNone(self.rows(GAZETTEER)[0]["record_key"])

    def test_two_excluded_matches_are_match_0(self) -> None:
        self.cache_places(
            [
                place("SYN-P-1", 51.7, 25.1, "Syn Souq"),
                place("SYN-P-2", 51.8, 25.1, "Syn Souq"),
            ]
        )
        self.review_files(gazetteer=[spec("landmark:0", "Syn Souq")])
        self.assertEqual(
            self.run_tool(),
            (
                0,
                "landmark:0 matches=0 kept=na footprints=na inside=na "
                "written=false reason=match_0 basis=place_name excluded=n\n",
            ),
        )


class LandmarkCategories(World):
    """A gazetteer row resolves only to an area category (proposal 3)."""

    def test_each_area_category_is_written(self) -> None:
        for category in sorted(keys_tool.LANDMARK_CATEGORIES):
            with self.subTest(category=category):
                self.setUp()
                self.cache_places(
                    [place("SYN-P-1", 51.1, 25.1, "Syn Quarter", category=category)]
                )
                self.review_files(gazetteer=[spec("landmark:0", "Syn Quarter")])
                self.assertEqual(self.run_tool()[0], 0)
                self.assertEqual(self.rows(GAZETTEER)[0]["record_key"], "SYN-P-1")

    def test_a_shop_named_like_the_landmark_is_refused(self) -> None:
        for category in ("syn_electronics_store", "District", " district"):
            with self.subTest(category=category):
                self.setUp()
                self.cache_places(
                    [place("SYN-P-1", 51.1, 25.1, "Syn Quarter", category=category)]
                )
                self.review_files(gazetteer=[spec("landmark:0", "Syn Quarter")])
                self.assertEqual(
                    self.run_tool(),
                    (
                        0,
                        "landmark:0 matches=1 kept=true footprints=na inside=na "
                        "written=false reason=landmark_category_refused "
                        "basis=place_name excluded=0\n",
                    ),
                )
                self.assertIsNone(self.rows(GAZETTEER)[0]["record_key"])

    def test_check_fails_a_stored_key_of_a_shop(self) -> None:
        filled = spec(
            "landmark:0", "Syn Quarter", source_id="places_ovt", record_key="SYN-P-1"
        )
        for category, expected in (
            ("district", (0, "landmark:0 check=true kept=true\n")),
            ("syn_electronics_store", (1, "landmark:0 check=false kept=true\n")),
        ):
            with self.subTest(category=category):
                self.setUp()
                self.cache_places(
                    [place("SYN-P-1", 51.1, 25.1, "Syn Quarter", category=category)]
                )
                self.review_files(gazetteer=[filled])
                self.assertEqual(self.run_tool("--check"), expected)

    def test_a_building_row_takes_no_category_rule(self) -> None:
        self.cache_places(
            [place("SYN-P-1", 51.105, 25.105, "Syn Tower", category="syn_shop")]
        )
        self.cache_buildings(0, [building("SYN-B-1", 51.1, 25.1)])
        self.review_files(flagship=[spec("building:0", "Syn Tower")])
        self.assertEqual(self.run_tool()[0], 0)
        self.assertEqual(self.rows(FLAGSHIP)[0]["record_key"], "SYN-B-1")


class FoldedEmptyNames(unittest.TestCase):
    """A name of combining marks alone folds to nothing and matches nothing."""

    def test_a_name_of_marks_alone_matches_no_footprint(self) -> None:
        named = {"SYN-B-0": frozenset({"\u0300"}), "SYN-B-1": frozenset({"\u0302"})}
        inputs = keys_tool.Inputs(
            (), (footprint_box(0), footprint_box(1)), frozenset(), {}, named
        )
        result = keys_tool.propose(spec("building:0", "\u0301"), "bldg_ovt", inputs)
        self.assertEqual((result.reason, result.basis), ("match_0", "place_point"))


# Each invented name with its N0 class and an independent N1 class.
NAME_TABLE = (
    ("Syn Spire", 0, 0),
    ("SYN  spire", 0, 0),
    ("Syn Spîre", 1, 0),
    ("syn spíre", 2, 0),
    ("سوق مخترع", 3, 3),
    ("سُوق مخترع", 4, 3),
    ("ســوق مخترع", 5, 3),
    ("Syn Other", 6, 6),
)
FOOTPRINTS = st.lists(
    st.tuples(st.none() | st.integers(0, len(NAME_TABLE) - 1), st.booleans()),
    max_size=5,
)


def footprint_box(index: int) -> ReadBuilding:
    return read_building(f"SYN-B-{index}", 51.1 + index * 0.02)


class BuildingNameProperty(unittest.TestCase):
    """propose against a class-table oracle over footprint plans (L-1389)."""

    @settings(deadline=None)
    @given(
        FOOTPRINTS, st.integers(0, len(NAME_TABLE) - 1), st.none() | st.integers(0, 4)
    )
    @example([(0, True), (2, True)], 0, None)
    @example([(0, True), (None, True)], 0, 1)
    @example([], 0, None)
    def test_key_and_reason_follow_the_oracle(
        self, plan: list[tuple[int | None, bool]], target: int, at: int | None
    ) -> None:
        text, n0, n1 = NAME_TABLE[target]
        buildings = tuple(footprint_box(index) for index in range(len(plan)))
        named = {
            f"SYN-B-{index}": frozenset({NAME_TABLE[name][0]})
            for index, (name, _inside) in enumerate(plan)
            if name is not None
        }
        inside = frozenset(f"SYN-B-{i}" for i, (_n, flag) in enumerate(plan) if flag)
        places: tuple[ReadPlace, ...] = ()
        if at is not None and at < len(plan):
            places = (read_place("SYN-P-1", text, 51.1 + at * 0.02 + 0.005),)
        inputs = keys_tool.Inputs(places, buildings, inside, {"SYN-P-1": "ok"}, named)
        result = keys_tool.propose(spec("building:0", text), "bldg_ovt", inputs)
        exact = [
            i
            for i, (n, _f) in enumerate(plan)
            if n is not None and NAME_TABLE[n][1] == n0
        ]
        folded = [
            i
            for i, (n, _f) in enumerate(plan)
            if n is not None and NAME_TABLE[n][2] == n1
        ]
        point = at if places else None
        expected: tuple[str | None, str, str]
        if len(exact) > 1:
            expected = (None, "building_name_n", "building_name")
        elif len(folded) > 1:
            expected = (None, "building_name_folded_n", "building_name")
        elif exact and not plan[exact[0]][1]:
            expected = (None, "outside_boundary", "building_name")
        elif exact and point is not None and point != exact[0]:
            expected = (None, "basis_conflict", "building_name")
        elif exact:
            expected = (f"SYN-B-{exact[0]}", "ok", "building_name")
        elif point is None:
            expected = (None, "match_0", "place_point")
        elif plan[point][1]:
            expected = (f"SYN-B-{point}", "ok", "place_point")
        else:
            expected = (None, "outside_boundary", "place_point")
        self.assertEqual((result.key, result.reason, result.basis), expected)


if __name__ == "__main__":
    unittest.main()
