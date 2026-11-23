"""Review loaders. Invented rows stay in the test, not in the committed files."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.review import (
    Verification,
    accept_verification,
    latest_status,
    load_attribution,
    load_categories,
    load_flagship_candidates,
    load_showcase_areas,
    load_showcase_gazetteer,
    load_verified_places,
)

_HEADER = "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
_BUILD = date(2026, 11, 14)
_REPO = repository_root(Path(__file__)) / "custodian" / "publicdata" / "review"
_CDLA = "CDLA-Permissive-2.0"
_REVIEWED_ATTRIBUTION = (
    ("AllThePlaces", "CC0-1.0", "Data from AllThePlaces. Available under CC0 1.0."),
    (
        "Foursquare",
        "Apache-2.0",
        "Data from Foursquare. Copyright 2024 Foursquare Labs, Inc. All rights"
        " reserved. Available under Apache 2.0. Foursquare data was transformed to"
        " the Overture schema. Changed: 2026-03-18. NOTICE.txt.",
    ),
    ("Microsoft", _CDLA, "Data from Microsoft. Available under CDLA Permissive 2.0."),
    (
        "OpenTravel",
        _CDLA,
        "Data from OpenTravel Alliance. Available under CDLA Permissive 2.0.",
    ),
    ("PinMeTo", _CDLA, "Data from PinMeTo. Available under CDLA Permissive 2.0."),
    ("Uberall", _CDLA, "Data from Uberall. Available under CDLA Permissive 2.0."),
    ("meta", _CDLA, "Data from Meta. Available under CDLA Permissive 2.0."),
)


def test_committed_attribution_holds_the_seven_reviewed_tokens() -> None:
    """The committed table loads as exactly the reviewed tokens, texts and licences."""
    origin, rows = load_attribution(_REPO / "places_ovt_attribution.csv", None)
    assert origin == "committed"
    assert rows == tuple((token, text) for token, _, text in _REVIEWED_ATTRIBUTION)
    for _, licence_id, text in _REVIEWED_ATTRIBUTION:
        assert f" Available under {licence_id.replace('-', ' ')}." in text


def test_committed_review_files_are_headers_only() -> None:
    """The still-unfilled files hold a header or an empty list and no invented row."""
    verified = (_REPO / "verified_places.csv").read_text(encoding="utf-8")
    assert verified == _HEADER
    assert (_REPO / "places_ovt_categories.csv").read_text(encoding="utf-8") == (
        "basic_category,category_class\n"
    )
    assert json.loads((_REPO / "showcase_areas.yaml").read_text(encoding="utf-8")) == []
    origin, rows = load_verified_places(
        _REPO / "verified_places.csv", None, frozenset(), _BUILD
    )
    assert origin == "committed"
    assert rows == ()
    area_origin, areas = load_showcase_areas(_REPO / "showcase_areas.yaml", None)
    assert area_origin == "committed"
    assert areas == ()
    gazetteer_origin, specs = load_showcase_gazetteer(
        _REPO / "showcase_gazetteer.yaml", None
    )
    assert gazetteer_origin == "committed"
    assert len(specs) == 4
    candidate_origin, candidates = load_flagship_candidates(
        _REPO / "flagship_candidates.yaml", None
    )
    assert candidate_origin == "committed"
    assert len(candidates) == 7


def test_statuses_round_trip_and_the_latest_date_wins(tmp_path: Path) -> None:
    """All four statuses load. A later date replaces an earlier one."""
    path = tmp_path / "verified_places.csv"
    path.write_text(
        _HEADER
        + "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,tenant_directory\n"
        + "SYN-P-A,2026-02-01,reviewer,https://example.invalid/a,closed_or_moved,official_website\n"
        + "SYN-P-B,2026-01-01,reviewer,https://example.invalid/b,not_found,public_authority\n"
        + "SYN-P-C,2026-01-01,reviewer,https://example.invalid/c,duplicate,tenant_directory\n",
        encoding="utf-8",
    )
    origin, rows = load_verified_places(
        path, None, frozenset({"SYN-P-A", "SYN-P-B", "SYN-P-C"}), _BUILD
    )
    assert origin == "committed"
    assert {row.status for row in rows} == {
        "verified_open",
        "closed_or_moved",
        "not_found",
        "duplicate",
    }
    latest = latest_status(rows)
    assert latest["SYN-P-A"].status == "closed_or_moved"
    assert latest["SYN-P-A"].check_date == "2026-02-01"


def test_cache_copy_is_the_copy_that_is_recorded(tmp_path: Path) -> None:
    """When a cache file exists, the loader reads it and records that origin."""
    committed = tmp_path / "committed.csv"
    cache = tmp_path / "cache.csv"
    committed.write_text(_HEADER, encoding="utf-8")
    cache.write_text(
        _HEADER
        + "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    origin, rows = load_verified_places(
        committed, cache, frozenset({"SYN-P-A"}), _BUILD
    )
    assert origin == "cache"
    assert rows[0].place_id == "SYN-P-A"


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (
            "SYN-P-MISSING,2026-01-01,reviewer,https://example.invalid/a,verified_open,tenant_directory\n",
            "orphan_place_id",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,tenant_directory\n"
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/b,not_found,tenant_directory\n",
            "duplicate_place_date",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,invented,tenant_directory\n",
            "unknown_status",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,,verified_open,tenant_directory\n",
            "missing_link",
        ),
        (
            "SYN-P-A,2026-01-01,,https://example.invalid/a,verified_open,tenant_directory\n",
            "missing_role",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,review_site\n",
            "verification_source_refused",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,delivery_platform\n",
            "verification_source_refused",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,booking_platform\n",
            "verification_source_refused",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,map_search\n",
            "verification_source_refused",
        ),
        (
            "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,syn_unlisted_source\n",
            "verification_source_unknown",
        ),
    ],
)
def test_verification_plants(tmp_path: Path, row: str, reason: str) -> None:
    """Each review guard has one planted row."""
    path = tmp_path / "verified_places.csv"
    path.write_text(_HEADER + row, encoding="utf-8")
    with pytest.raises(PlacesError, match=reason):
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD)


def test_white_space_role_is_refused_on_both_paths(tmp_path: Path) -> None:
    """A role of white space only is missing on the file and in memory."""
    path = tmp_path / "verified_places.csv"
    path.write_text(
        _HEADER
        + "SYN-P-A,2026-11-14,   ,https://example.invalid/a,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError, match="missing_role"):
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD)
    row = Verification(
        "SYN-P-A",
        "2026-11-14",
        "   ",
        "https://example.invalid/a",
        "verified_open",
        "tenant_directory",
    )
    with pytest.raises(PlacesError, match="missing_role"):
        accept_verification(row, frozenset({"SYN-P-A"}), _BUILD)


@pytest.mark.parametrize(
    "check_date",
    ["", "2026-11-1", "2026-13-01", "2026-11-15", "2026" + "1114"],
)
def test_check_date_must_be_a_hyphenated_day_on_or_before_the_build(
    tmp_path: Path, check_date: str
) -> None:
    """Empty, unpadded, impossible, future and basic-form dates are refused."""
    path = tmp_path / "verified_places.csv"
    path.write_text(
        _HEADER
        + f"SYN-P-A,{check_date},reviewer,https://syn.example/check,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError, match="bad_check_date"):
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD)


def test_the_build_date_is_accepted_and_the_later_day_wins(tmp_path: Path) -> None:
    """2026-11-14 loads. The later of two earlier days is the latest status."""
    path = tmp_path / "verified_places.csv"
    path.write_text(
        _HEADER
        + "SYN-P-A,2026-11-14,reviewer,https://syn.example/check,verified_open,tenant_directory\n"
        + "SYN-P-B,2026-11-01,reviewer,https://syn.example/check,verified_open,tenant_directory\n"
        + "SYN-P-B,2026-11-01,reviewer,https://syn.example/other,not_found,tenant_directory\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError, match="duplicate_place_date"):
        load_verified_places(path, None, frozenset({"SYN-P-A", "SYN-P-B"}), _BUILD)
    single = tmp_path / "one.csv"
    single.write_text(
        _HEADER
        + "SYN-P-A,2026-10-31,reviewer,https://syn.example/check,not_found,tenant_directory\n"
        + "SYN-P-A,2026-11-01,reviewer,https://syn.example/check,verified_open,official_website\n",
        encoding="utf-8",
    )
    _origin, rows = load_verified_places(single, None, frozenset({"SYN-P-A"}), _BUILD)
    assert latest_status(rows)["SYN-P-A"].check_date == "2026-11-01"
    accepted = tmp_path / "today.csv"
    accepted.write_text(
        _HEADER
        + "SYN-P-A,2026-11-14,reviewer,https://syn.example/check,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    _origin, rows = load_verified_places(accepted, None, frozenset({"SYN-P-A"}), _BUILD)
    assert rows[0].check_date == "2026-11-14"


@pytest.mark.parametrize(
    "link",
    [
        "http://syn.example/check",
        "/check",
        "https://",
        "syn.example/check",
        "ftp://syn.example/check",
    ],
)
def test_verification_link_must_be_absolute_https(tmp_path: Path, link: str) -> None:
    """Anything other than an absolute https address with a host refuses the file."""
    path = tmp_path / "verified_places.csv"
    path.write_text(
        _HEADER
        + f"SYN-P-A,2026-11-14,reviewer,{link},verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError, match="link_form"):
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD)


def test_showcase_area_accepts_only_a_ten_minute_walk(tmp_path: Path) -> None:
    """A walk of ten minutes loads. A drive, or another cut-off, refuses the file."""
    path = tmp_path / "showcase_areas.yaml"
    path.write_text(
        "- place_key: SYN-LAND\n"
        "  mode: walk\n"
        "  cutoff_minutes: 10\n"
        "  source_id: places_ovt\n"
        "  record_key: SYN-P-A\n",
        encoding="utf-8",
    )
    origin, rows = load_showcase_areas(path, None)
    assert origin == "committed"
    assert rows[0]["cutoff_minutes"] == 10
    path.write_text(path.read_text().replace("walk", "drive"), encoding="utf-8")
    with pytest.raises(PlacesError, match="showcase_area"):
        load_showcase_areas(path, None)


def test_unknown_category_class_is_refused(tmp_path: Path) -> None:
    """A class outside the closed set refuses the file."""
    path = tmp_path / "places_ovt_categories.csv"
    path.write_text(
        "basic_category,category_class\nsyn_restaurant,palace\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError, match="unknown_category_class"):
        load_categories(path, None)
    good = tmp_path / "good.csv"
    good.write_text(
        "basic_category,category_class\nsyn_restaurant,restaurant\nsyn_italian,italian_restaurant\n",
        encoding="utf-8",
    )
    origin, rows = load_categories(good, None)
    assert origin == "committed"
    assert rows == (
        ("syn_restaurant", "restaurant"),
        ("syn_italian", "italian_restaurant"),
    )


def test_attribution_is_keyed_on_the_token(tmp_path: Path) -> None:
    """The table is the dataset token and the licence text."""
    path = tmp_path / "places_ovt_attribution.csv"
    path.write_text(
        "dataset_token,licence\nsyn-source,SYN-LICENCE\n",
        encoding="utf-8",
    )
    origin, rows = load_attribution(path, None)
    assert origin == "committed"
    assert rows == (("syn-source", "SYN-LICENCE"),)


def test_a_repeated_attribution_token_is_refused(tmp_path: Path) -> None:
    """Two licences for one dataset token refuse the attribution file."""
    path = tmp_path / "places_ovt_attribution.csv"
    path.write_text(
        "dataset_token,licence\nsyn-source,SYN-LICENCE\nsyn-source,SYN-LICENCE-B\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError, match="duplicate_token"):
        load_attribution(path, None)
