"""S2-P76 guards, using only invented local review records."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.additions.property_venues import (
    VENUE_COLUMNS,
    load_venue_crosswalk,
)
from eii_custodian.publicdata.busyness.build import BuildInputError, _inputs
from eii_custodian.publicdata.places import PlacesError, build
from eii_custodian.publicdata.places.display import PubPlace
from eii_custodian.publicdata.places.review import (
    load_categories,
    load_showcase_areas,
    review_file_row,
)


def _area(**changes: object) -> dict[str, object]:
    return dict(
        place_key="SYN-AREA",
        mode="walk",
        cutoff_minutes=10,
        source_id="places_ovt",
        record_ref="SYN-PIN",
        **changes,
    )


def _gazetteer(area: dict[str, object]) -> dict[str, object]:
    return {
        **{name: area[name] for name in ("place_key", "source_id")},
        "record_key": area["record_ref"],
        "kind": "landmark",
        "name_en": "SYN Place",
        "name_ar": "مكان تجريبي",
        "aliases": None,
        "arabic_review": "pending native review",
    }


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[object]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


@pytest.mark.parametrize("second", ["restaurant", "other"])
def test_duplicate_category(tmp_path: Path, second: str) -> None:
    path = tmp_path / "categories.csv"
    _write_csv(
        path,
        ("basic_category", "category_class"),
        [("syn_food", "restaurant"), ("syn_food", second)],
    )
    with pytest.raises(PlacesError, match=r"^duplicate_category$"):
        load_categories(path, None)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("duplicate", "showcase_area_duplicate"),
        ("source", "showcase_area_source"),
        ("empty_source", "showcase_area_source"),
        ("unknown_source", "showcase_area_source"),
        ("pin", "showcase_area_gazetteer_mismatch"),
        ("key", "showcase_area_gazetteer_mismatch"),
    ],
)
def test_showcase_guard(tmp_path: Path, change: str, reason: str) -> None:
    row = _area()
    gazetteer = (_gazetteer(row),)
    rows = [row]
    if change == "duplicate":
        rows.append(dict(row))
    elif change in {"source", "empty_source", "unknown_source"}:
        row["source_id"] = {
            "source": "bldg_ovt",
            "empty_source": "",
            "unknown_source": "SYN-UNKNOWN",
        }[change]
        gazetteer = (_gazetteer(row),)
    elif change == "pin":
        row["record_ref"] = "SYN-OTHER"
    else:
        row["place_key"] = "SYN-OTHER"
    path = tmp_path / "areas.yaml"
    path.write_text(yaml.safe_dump(rows))
    with pytest.raises(PlacesError, match=f"^{reason}$"):
        load_showcase_areas(path, None, gazetteer=gazetteer)


def test_empty_and_matching_showcase(tmp_path: Path) -> None:
    path = tmp_path / "areas.yaml"
    for rows in ([], [_area()]):
        path.write_text(yaml.safe_dump(rows))
        loaded = load_showcase_areas(path, None, gazetteer=(_gazetteer(_area()),))[1]
        expected = [dict(row) for row in rows]
        for row in expected:
            row["record_key"] = row.pop("record_ref")
        assert loaded == tuple(expected)


@pytest.mark.parametrize(
    "key,reason",
    [
        ("1" * 8, "venue_key_digit_run"),
        ("1" * 11, "venue_key_digit_run"),
        ("venue:x" + "1" * 8 + ":1", "venue_key_digit_run"),
        ("venue:x:0", "venue_key_form"),
        ("venue:x:1000000", "venue_key_form"),
        ("venue:X:1", "venue_key_form"),
        ("venue:x:1\n", "venue_key_form"),
    ],
)
def test_venue_key_refusal(tmp_path: Path, key: str, reason: str) -> None:
    path = tmp_path / "venues.csv"
    _write_csv(
        path,
        VENUE_COLUMNS,
        [("visits_museum", "SYN Hall", key, "", "reviewer", "2026-11-20")],
    )
    with pytest.raises(AdditionError, match=f"^{reason}$"):
        load_venue_crosswalk(path)


def test_valid_venue_key(tmp_path: Path) -> None:
    path = tmp_path / "venues.csv"
    _write_csv(
        path,
        VENUE_COLUMNS,
        [
            (
                "visits_museum",
                "SYN Hall",
                "venue:visits_museum:1",
                "",
                "reviewer",
                "2026-11-20",
            )
        ],
    )
    assert load_venue_crosswalk(path)[0]["venue_key"] == "venue:visits_museum:1"


@pytest.mark.parametrize("target", ["review", "crosswalk", "places_dir", "places"])
def test_busyness_symlink(tmp_path: Path, target: str) -> None:
    cache = tmp_path / "cache"
    (cache / "review").mkdir(parents=True)
    (cache / "places_s2_t06").mkdir()
    crosswalk = cache / "review/venue_busyness_crosswalk.csv"
    crosswalk.write_text(
        "place_id,venue_key,reviewer_role,reviewed_on,match\nSYN-P,SYN-provider,reviewer,2026-11-20,matched\n"
    )
    places = cache / "places_s2_t06/pub_place.jsonl"
    places.write_text('{"place_id":"SYN-P","name":"SYN Place"}\n')
    path = {
        "review": crosswalk.parent,
        "crosswalk": crosswalk,
        "places_dir": places.parent,
        "places": places,
    }[target]
    destination = cache / "moved"
    path.rename(destination)
    path.symlink_to(destination, target_is_directory=destination.is_dir())
    with pytest.raises(BuildInputError, match=r"^cache_path_refused$"):
        _inputs(cache, tmp_path, ({"place_id": "SYN-P"},))


def _place(key: str, kind: str) -> PubPlace:
    return PubPlace(
        key,
        key,
        None,
        "syn_" + kind,
        kind,
        Decimal("51.5"),
        Decimal("25.3"),
        1,
        "SYN-release",
        "SYN-source",
        "SYN-licence",
        Decimal("0.8"),
        "",
    )


@pytest.mark.parametrize("included", [False, True])
@pytest.mark.parametrize("mapped", [False, True])
def test_places_food_service_required_population(included: bool, mapped: bool) -> None:
    """Food service is required exactly inside the walk, with either class route."""
    place = _place("SYN-FOOD", "food_service")
    classes = {place.category: "food_service"} if mapped else {}
    inside = frozenset({place.place_id}) if included else frozenset()
    assert build.required_verification((place,), inside, classes, story_ids=()) == (
        (place.place_id,) if included else ()
    )


def test_required_population() -> None:
    places = (
        _place("SYN-IN", "restaurant"),
        _place("SYN-OUT", "italian_restaurant"),
        _place("SYN-NONFOOD", "other"),
    )
    classes = {p.category: p.category_class for p in places}
    inside = frozenset({"SYN-IN", "SYN-NONFOOD"})
    assert build.required_verification(places, inside, classes, story_ids=()) == (
        "SYN-IN",
    )
    assert build.required_verification(
        places, inside, classes, story_ids=("SYN-STORY",)
    ) == ("SYN-IN", "SYN-STORY")


@given(
    st.lists(
        st.tuples(
            st.sampled_from(
                ["restaurant", "italian_restaurant", "food_service", "other"]
            ),
            st.booleans(),
        ),
        max_size=20,
    )
)
def test_population_order_and_duplicates(items: list[tuple[str, bool]]) -> None:
    places = tuple(_place(f"SYN-P-{i}", kind) for i, (kind, _) in enumerate(items))
    inside = frozenset(
        p.place_id for p, (_, included) in zip(places, items, strict=True) if included
    )
    classes = {p.category: p.category_class for p in places}
    expected = build.required_verification(
        places, inside, classes, story_ids=("SYN-STORY",)
    )
    assert expected == tuple(sorted(set(expected)))
    assert "SYN-STORY" in expected
    assert (
        build.required_verification(
            tuple(reversed(places)) + places,
            inside,
            classes,
            story_ids=("SYN-STORY", "SYN-STORY"),
        )
        == expected
    )
    for p, (kind, included) in zip(places, items, strict=True):
        assert (p.place_id in expected) == (included and kind != "other")


# File-backed examples retain isolation but cannot bound shared-runner I/O time.
@settings(deadline=None)
@given(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20),
    st.integers(min_value=1, max_value=999999),
)
def test_venue_key_domain(source: str, ordinal: int) -> None:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "venues.csv"
        key = f"venue:{source}:{ordinal}"
        _write_csv(
            path,
            VENUE_COLUMNS,
            [("visits_museum", "SYN Hall", key, "", "reviewer", "2026-11-20")],
        )
        assert load_venue_crosswalk(path)[0]["venue_key"] == key


def test_area_hostile_leaves(tmp_path: Path) -> None:
    """Every leaf of the valid area fixture meets each mandated hostile value."""
    path = tmp_path / "areas.yaml"
    for key in _area():
        for hostile in ({"toString": None}, 7, None, []):
            row = _area()
            row[key] = hostile
            path.write_text(yaml.safe_dump([row]))
            with pytest.raises(
                PlacesError,
                match=r"^(showcase_area|showcase_area_source|showcase_area_gazetteer_mismatch)$",
            ):
                load_showcase_areas(path, None, gazetteer=(_gazetteer(_area()),))


@pytest.mark.parametrize("overlap", [False, True])
@pytest.mark.parametrize("failure", [None, "provider_error"])
def test_required_counts_in_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overlap: bool, failure: str | None
) -> None:
    import json

    from custodian.tests.test_places_stage import _config, _one, _places, _review
    from shapely.geometry import box

    from eii_custodian.publicdata.places import stage
    from eii_custodian.publicdata.places.areas import AreaError, AreaResult

    review = _review(tmp_path, verified="", candidates=False)
    areas = [
        _area(),
        {**_area(), "place_key": "SYN-SECOND", "record_ref": "SYN-SECOND-PIN"},
    ]
    if failure is not None:
        areas.append(
            {
                **_area(),
                "place_key": "SYN-FAILED",
                "record_ref": "SYN-PIN",
            }
        )
    (review / "showcase_areas.yaml").write_text(yaml.safe_dump(areas))
    gazetteer = [_gazetteer(row) for row in areas]
    (review / "showcase_gazetteer.yaml").write_text(
        yaml.safe_dump([review_file_row(row) for row in gazetteer])
    )
    places = _places(
        tmp_path,
        [
            _one("SYN-PIN", 51.5, 25.3, "syn_other", "0.8"),
            _one("SYN-SECOND-PIN", 51.502, 25.3, "syn_other", "0.8"),
            _one("SYN-IN", 51.501, 25.301, "syn_restaurant", "0.8"),
            _one("SYN-OUT", 51.35, 25.15, "syn_restaurant", "0.8"),
        ],
    )

    class Areas:
        def area(self, point_key, point, mode, cutoff):
            if point_key == "SYN-FAILED":
                raise AreaError("SYN-polygon-failed")
            polygon = box(51.4995, 25.2995, 51.5015, 25.3015)
            if point_key != "SYN-AREA":
                polygon = (
                    box(51.4995, 25.2995, 51.5025, 25.3015)
                    if overlap
                    else box(51.5018, 25.2998, 51.5022, 25.3002)
                )
            return AreaResult(
                bytes(polygon.wkb),
                "SYN",
                "SYN",
                "SYN",
                "SYN",
                True,
            )

    monkeypatch.setattr(stage, "_provider", lambda config: Areas())
    outcome = stage.run_places_stage(_config(tmp_path, review, places))
    report = json.loads((outcome.directory / "build_report.json").read_text())
    by_area = {"SYN-AREA": 1, "SYN-SECOND": int(overlap)}
    if failure is not None:
        by_area["SYN-FAILED"] = 0
    assert report["required_verification"] == {
        "by_area": by_area,
        "total": 1,
    }
    assert outcome.complete is False
    assert report["complete"] is False
    assert report["decision"] == "pending"
    assert "census_comparison_pending" in report["report"]
    assert "fsq_pending" in report["report"]
    assert [note for note in report["report"] if note.startswith("showcase")] == (
        ["showcase area error: SYN-polygon-failed"] if failure is not None else []
    )


def test_cache_containment(tmp_path: Path) -> None:
    from eii_custodian.publicdata.heights.landmarks import checked_cache_path
    from eii_custodian.publicdata.heights.model import HeightError

    with pytest.raises(HeightError) as caught:
        checked_cache_path(tmp_path, Path("../SYN-outside"))
    assert caught.value.name == "landmark_heights"
    assert caught.value.detail == "cache_path_refused"


@pytest.mark.parametrize("kind", ["categories", "venues"])
def test_csv_hostile_leaves(tmp_path: Path, kind: str) -> None:
    """CSV has textual leaves; exercise each hostile value after CSV encoding."""
    columns = (
        ("basic_category", "category_class") if kind == "categories" else VENUE_COLUMNS
    )
    valid = (
        ["syn_food", "restaurant"]
        if kind == "categories"
        else [
            "visits_museum",
            "SYN Hall",
            "venue:visits_museum:1",
            "",
            "reviewer",
            "2026-11-20",
        ]
    )
    path = tmp_path / "rows.csv"
    for index in range(len(valid)):
        for hostile in ({"toString": None}, 7, None, []):
            values: list[object] = list(valid)
            values[index] = hostile
            _write_csv(path, columns, [values])
            try:
                result = (
                    load_categories(path, None)[1]
                    if kind == "categories"
                    else load_venue_crosswalk(path)
                )
            except PlacesError as exc:
                assert exc.reason in {"category_row", "unknown_category_class"}
            except AdditionError as exc:
                assert exc.name in {"unreviewed_venue", "venue_key_form", "period_form"}
            else:
                assert len(result) == 1


@settings(deadline=None)
@given(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
    st.sampled_from(["restaurant", "italian_restaurant", "other"]),
)
def test_category_duplicate_order(token: str, kind: str) -> None:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "categories.csv"
        for rows in (
            [(token, kind), (" " + token + " ", "restaurant")],
            [(token, "restaurant"), (token, kind)],
        ):
            _write_csv(path, ("basic_category", "category_class"), rows)
            with pytest.raises(PlacesError, match=r"^duplicate_category$"):
                load_categories(path, None)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("header", "venue_crosswalk"),
        ("missing_cell", "venue_crosswalk"),
        ("name", "unreviewed_venue"),
        ("key", "unreviewed_venue"),
        ("role", "unreviewed_venue"),
        ("date", "period_form"),
        ("duplicate", "venue_crosswalk_conflict"),
    ],
)
def test_venue_retained_refusals(tmp_path: Path, change: str, reason: str) -> None:
    columns = VENUE_COLUMNS
    row = [
        "visits_museum",
        "SYN Hall",
        "venue:visits_museum:1",
        "",
        "reviewer",
        "2026-11-20",
    ]
    if change == "header":
        columns = tuple(reversed(columns))
        row.reverse()
    elif change == "missing_cell":
        row = row[:-1]
    elif change != "duplicate":
        row[{"name": 1, "key": 2, "role": 4, "date": 5}[change]] = ""
    path = tmp_path / "venues.csv"
    _write_csv(path, columns, [row, row] if change == "duplicate" else [row])
    with pytest.raises(AdditionError, match=f"^{reason}$"):
        load_venue_crosswalk(path)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("place", "pub_place missing SYN-P"),
        ("crosswalk", "crosswalk missing SYN-P"),
        ("name", "pub_place name missing SYN-P"),
    ],
)
def test_busyness_retained_refusals(tmp_path: Path, change: str, reason: str) -> None:
    cache = tmp_path / "cache"
    (cache / "review").mkdir(parents=True)
    (cache / "places_s2_t06").mkdir()
    crosswalk = cache / "review/venue_busyness_crosswalk.csv"
    crosswalk.write_text(
        "place_id,venue_key,reviewer_role,reviewed_on,match\n"
        + (
            ""
            if change == "crosswalk"
            else "SYN-P,SYN-provider,reviewer,2026-11-20,matched\n"
        )
    )
    places = cache / "places_s2_t06/pub_place.jsonl"
    places.write_text(
        ""
        if change == "place"
        else (
            '{"place_id":"SYN-P","name":""}\n'
            if change == "name"
            else '{"place_id":"SYN-P","name":"SYN Place"}\n'
        )
    )
    with pytest.raises(BuildInputError, match=f"^{reason}$"):
        _inputs(cache, tmp_path, ({"place_id": "SYN-P"},))


@pytest.mark.parametrize("digits", range(1, 13))
def test_exact_digit_run_lengths(tmp_path: Path, digits: int) -> None:
    path = tmp_path / "venues.csv"
    key = "venue:x" + "1" * digits + ":1"
    _write_csv(
        path,
        VENUE_COLUMNS,
        [("visits_museum", "SYN Hall", key, "", "reviewer", "2026-11-20")],
    )
    if digits in {8, 11}:
        with pytest.raises(AdditionError, match=r"^venue_key_digit_run$"):
            load_venue_crosswalk(path)
    else:
        assert load_venue_crosswalk(path)[0]["venue_key"] == key


@pytest.mark.parametrize(
    "field,value", [("basic_category", ""), ("category_class", "syn_unknown")]
)
def test_category_retained_refusals(tmp_path: Path, field: str, value: str) -> None:
    row = {"basic_category": "syn_food", "category_class": "restaurant"}
    row[field] = value
    path = tmp_path / "categories.csv"
    _write_csv(path, tuple(row), [list(row.values())])
    reason = "category_row" if field == "basic_category" else "unknown_category_class"
    with pytest.raises(PlacesError, match=f"^{reason}$"):
        load_categories(path, None)


@pytest.mark.parametrize(
    "field,value",
    [("mode", "drive"), ("cutoff_minutes", 5), ("place_key", ""), ("place_key", 7)],
)
def test_area_retained_refusals(tmp_path: Path, field: str, value: object) -> None:
    row = _area()
    row[field] = value
    path = tmp_path / "areas.yaml"
    path.write_text(yaml.safe_dump([row]))
    with pytest.raises(PlacesError, match=r"^showcase_area$"):
        load_showcase_areas(path, None)
