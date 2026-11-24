"""Further places source: selection, parse, fetch and the duplicate rule.

Fixtures are invented. No live response is read or stored.
"""

from __future__ import annotations

import json
import math
import os
import struct
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.fixtures.places_fsq.invented import (
    listing,
    place,
    point_wkb,
    write_places,
)
from custodian.tests.repository_root import repository_root
from custodian.tests.support.fetch_build import run_build

import h3
from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.places_fsq.assemble import EligiblePlace, build_places
from eii_custodian.publicdata.places_fsq.constants import (
    ATTRIBUTION,
    COPY_ROOT,
    COPYRIGHT_LINE,
    HOST_TERMS_NOTE,
    LICENCE_NAME,
    RELEASE_KEY,
)
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import metadata_bytes
from eii_custodian.publicdata.places_fsq.names import (
    _contains_words,
    check_labels,
    edit_distance,
)
from eii_custodian.publicdata.places_fsq.parse import account_rows, parse_file
from eii_custodian.publicdata.places_fsq.policy import (
    DUPLICATE_WITHIN_M,
    MAPPING_COLUMNS,
    PlaceStandIn,
    assert_policy,
    distance_m,
    duplicate_links,
    is_eligible,
    load_mapping,
    move_north,
    normalise_duplicate_name,
    product_categories,
)
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX, select_partitions

_PACKAGE = repository_root(Path(__file__)) / "custodian"
_RELEASE = "2025-01-10"
_MAPPING = _PACKAGE / "publicdata" / "review" / "places_fsq_categories.csv"
_POLICY = _PACKAGE / "publicdata" / "review" / "places_fsq_policy.yaml"
_README = (
    f'{COPYRIGHT_LINE}\nLicensed under the {LICENCE_NAME} (the "License").\n'
).encode()
_NEAR = {
    "file_path": "near.parquet",
    "longitude": (51.0, 51.4),
    "latitude": (25.0, 25.6),
    "geo_bbox": (1.0, 2.0, 3.0, 4.0),
}
_FAR = {
    "file_path": "far.parquet",
    "longitude": (10.0, 11.0),
    "latitude": (40.0, 41.0),
    "geo_bbox": (50.7, 24.4, 51.7, 26.2),
}
_EDGE = {
    "file_path": "edge.parquet",
    "longitude": (50.7, 50.7),
    "latitude": (24.4, 24.4),
    "geo_bbox": (0.0, 0.0, 1.0, 1.0),
}


def test_selects_only_files_whose_row_groups_meet_the_frame() -> None:
    """Row-group coordinate statistics select the files; a file's own geo bbox does not."""
    body = metadata_bytes((_NEAR, _FAR, _EDGE), dataset_geo_bbox=(0.0, 0.0, 1.0, 1.0))
    selected = select_partitions(body, release=_RELEASE, frame=FRAME_BOX)
    assert selected.files == ("edge.parquet", "near.parquet")
    ignored = {item.file_path: item.bbox for item in selected.ignored_geo}
    assert ignored[""] == (0.0, 0.0, 1.0, 1.0)
    assert ignored["far.parquet"] == (50.7, 24.4, 51.7, 26.2)
    assert ignored["near.parquet"] == (1.0, 2.0, 3.0, 4.0)


def test_metadata_with_no_file_for_the_frame_fetches_nothing(tmp_path: Path) -> None:
    """A summary that misses the frame refuses before any data file is requested."""
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    body = metadata_bytes((_FAR,), dataset_geo_bbox=(50.7, 24.4, 51.7, 26.2))
    with pytest.raises(PlacesFsqError, match=r"^no_file_for_frame$"):
        select_partitions(body, release=_RELEASE, frame=FRAME_BOX)
    entry = _release_entry()
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        response = listing(f"{_RELEASE}/") if url == entry.url else body
        return Response(final_url=url, body=response, hops=())

    outcome = run_build((entry,), transport, fixture_cache, _clock, _sleep)
    assert outcome.failure is not None
    assert outcome.failure.check == "no_file_for_frame"
    assert seen == [entry.url, f"{COPY_ROOT}{_RELEASE}/places/_metadata"]
    assert not (fixture_cache / RELEASE_KEY / "manifest.json").exists()


def test_a_different_release_in_the_summary_is_refused() -> None:
    """The release is the folder name. A newer folder is not fetched."""
    group = {
        "file_path": "2025-02-06/places/32.parquet",
        "longitude": (51.0, 51.4),
        "latitude": (25.0, 25.6),
        "geo_bbox": (0.0, 0.0, 1.0, 1.0),
    }
    body = metadata_bytes((group,), dataset_geo_bbox=None)
    with pytest.raises(PlacesFsqError, match=r"^release_mismatch$"):
        select_partitions(body, release=_RELEASE, frame=FRAME_BOX)


def test_registry_row_records_publisher_licence_terms_and_release() -> None:
    """The stable row selects a release at refresh and records it at runtime."""
    rows = [entry for entry in load_registry() if entry.source_id == "places_fsq"]
    placeholder = next(entry for entry in rows if entry.key == "places_fsq")
    release = next(entry for entry in rows if entry.key == RELEASE_KEY)
    assert placeholder.skip_reason == "fetcher_owned_by_S2-T15"
    assert placeholder.licence_id == "Apache-2.0"
    assert release.publisher == "Foursquare"
    assert release.licence_basis == "dataset"
    assert release.licence_id == "Apache-2.0"
    assert release.period_first == ""
    assert release.period_last == ""
    assert release.title_en.endswith("newest dated release at each refresh")
    assert HOST_TERMS_NOTE in release.basis_note
    assert COPYRIGHT_LINE in release.basis_note
    assert release.terms_url.endswith("/README.md")
    assert approve(release.url).ok
    assert "data.source.coop" in release.url
    assert rows[-1].key == RELEASE_KEY


def test_build_fetches_only_the_qatar_file_and_no_foreign_host(tmp_path: Path) -> None:
    """The command seam contacts the copy, the readme and the one selected file."""
    data = tmp_path / "near.parquet"
    write_places(data, [place()])
    actual = {**_NEAR, "longitude": (51.5, 51.5), "latitude": (25.3, 25.3)}
    body = metadata_bytes((actual,), dataset_geo_bbox=(0.0, 0.0, 1.0, 1.0))
    entry = _release_entry()
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == entry.url:
            return Response(final_url=url, body=listing(f"{_RELEASE}/"), hops=())
        if url.endswith("_metadata"):
            return Response(final_url=url, body=body, hops=())
        if url == entry.terms_url:
            return Response(final_url=url, body=_README, hops=())
        return Response(final_url=url, body=data.read_bytes(), hops=())

    os.environ["PLACES_FSQ_TOKEN"] = "planted-token-value"
    try:
        outcome = run_build((entry,), transport, tmp_path / "cache", _clock, _sleep)
        cache = tmp_path / "cache"
        stored = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in cache.rglob("*")
            if path.is_file() and path.suffix != ".parquet"
        )
    finally:
        del os.environ["PLACES_FSQ_TOKEN"]
    assert outcome.failure is None
    assert seen == [
        entry.url,
        f"{COPY_ROOT}{_RELEASE}/places/_metadata",
        entry.terms_url,
        "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/near.parquet",
    ]
    assert all(approve(url).ok for url in seen)
    assert (tmp_path / "cache" / RELEASE_KEY / _RELEASE / "manifest.json").is_file()
    assert "planted-token-value" not in stored


def test_foreign_redirect_or_login_demand_store_nothing(tmp_path: Path) -> None:
    """A hop off the list and a sign-in page each refuse."""
    entry = _release_entry()
    foreign = _run(
        entry, tmp_path / "foreign", _README, hops=("https://evil.example/x",)
    )
    assert foreign.failure is not None
    assert foreign.failure.check == "blocked_host"
    assert "evil.example" in foreign.failure.url
    login = _run(entry, tmp_path / "login", b"Please sign in to continue")
    assert login.failure is not None
    assert login.failure.check == "sign_in_demand"
    for folder in ("foreign", "login"):
        assert not (tmp_path / folder / RELEASE_KEY / "manifest.json").exists()


def test_a_licence_different_from_the_registry_is_recorded_pending(
    tmp_path: Path,
) -> None:
    """Ruling L-1001 (PUB-97): a licence text that differs from the registry is
    archived with its hash and the date read, pending a reviewer's record, and
    the release completes."""
    from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256

    data = tmp_path / "near.parquet"
    write_places(data, [place()])
    actual = {**_NEAR, "longitude": (51.5, 51.5), "latitude": (25.3, 25.3)}
    body = metadata_bytes((actual,), dataset_geo_bbox=(0.0, 0.0, 1.0, 1.0))
    entry = _release_entry()

    def transport(url: str) -> Response:
        if url == entry.url:
            return Response(final_url=url, body=listing(f"{_RELEASE}/"), hops=())
        if url.endswith("_metadata"):
            return Response(final_url=url, body=body, hops=())
        if url == entry.terms_url:
            return Response(final_url=url, body=b"Proprietary terms only.", hops=())
        return Response(final_url=url, body=data.read_bytes(), hops=())

    os.environ["PLACES_FSQ_TOKEN"] = "planted-token-value"
    try:
        outcome = run_build((entry,), transport, tmp_path / "licence", _clock, _sleep)
    finally:
        del os.environ["PLACES_FSQ_TOKEN"]
    assert outcome.failure is None
    manifest = json.loads(
        (tmp_path / "licence" / RELEASE_KEY / _RELEASE / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["licence_review"] == "pending"
    assert manifest["terms_sha256"] == terms_text_sha256(b"Proprietary terms only.")
    assert manifest["retrieved_utc"] == _clock()


def test_missing_terms_do_not_stop_the_fetch_and_missing_basis_is_pending(
    tmp_path: Path,
) -> None:
    """Decision 0026 and ruling L-1001: terms that are absent do not stop the
    fetch; a row without the licence_basis key loads as the pending record."""
    data = tmp_path / "near.parquet"
    write_places(data, [place()])
    actual = {**_NEAR, "longitude": (51.5, 51.5), "latitude": (25.3, 25.3)}
    body = metadata_bytes((actual,), dataset_geo_bbox=None)
    entry = _release_entry()
    bare = _replace(entry, terms_url="")
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == bare.url:
            return Response(final_url=url, body=listing(f"{_RELEASE}/"), hops=())
        if url.endswith("_metadata"):
            return Response(final_url=url, body=body, hops=())
        return Response(final_url=url, body=data.read_bytes(), hops=())

    outcome = run_build((bare,), transport, tmp_path / "cache", _clock, _sleep)
    assert outcome.failure is None
    assert entry.terms_url not in seen
    text = (_PACKAGE / "publicdata" / "sources.yaml").read_text(encoding="utf-8")
    planted = tmp_path / "registry.yaml"
    planted.write_text(
        text.replace('    licence_basis: "dataset"\n', "", 1), encoding="utf-8"
    )
    loaded = load_registry(planted)
    first = [entry for entry in loaded if entry.source_id == "lic_active"]
    assert first[0].licence_basis == "pending"


def test_parser_keeps_source_fields_and_refuses_invented_ones(tmp_path: Path) -> None:
    """The table takes the source fields. A rating, a staff field and a bad axis do not."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place(
                fsq_category_ids=["cccccccccccccccceeee0001"],
                fsq_category_labels=["Invented leaf"],
            )
        ],
    )
    row = parse_file(path)[0]
    assert row.name_ar is None
    assert row.category_ids == "cccccccccccccccceeee0001"
    assert row.category_labels == "Invented leaf"
    assert row.lon == Decimal("51.500000")
    assert row.date_created == date(2020, 1, 2)
    assert row.date_closed is None
    swapped = tmp_path / "swapped.parquet"
    write_places(
        swapped,
        [
            place(
                longitude=25.3,
                latitude=51.5,
                geometry=point_wkb(51.5, 25.3),
            )
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^axes_swapped$"):
        parse_file(swapped)
    wide = tmp_path / "wide.parquet"
    write_places(wide, [place(latitude=91.0, geometry=point_wkb(51.5, 91.0))])
    with pytest.raises(PlacesFsqError, match=r"^latitude$"):
        parse_file(wide)
    rated = tmp_path / "rated.parquet"
    write_places(rated, [place()], extra={"rating": "DOUBLE"})
    with pytest.raises(PlacesFsqError, match=r"^rating$"):
        parse_file(rated)
    staff = tmp_path / "staff.parquet"
    write_places(staff, [place()], extra={"staff_count": "INTEGER"})
    with pytest.raises(PlacesFsqError, match=r"^staff_count$"):
        parse_file(staff)
    broken = tmp_path / "date.parquet"
    write_places(broken, [place(date_created="2020-13-01")])
    with pytest.raises(PlacesFsqError, match=r"^date_created$"):
        parse_file(broken)
    uneven = tmp_path / "lists.parquet"
    write_places(
        uneven,
        [place(fsq_category_ids=["aa", "bb"], fsq_category_labels=["Only"])],
    )
    with pytest.raises(PlacesFsqError, match=r"^category_list_length$"):
        parse_file(uneven)
    marked = tmp_path / "semi.parquet"
    write_places(marked, [place(fsq_category_labels=["A;B"])])
    with pytest.raises(PlacesFsqError, match=r"^category_labels$"):
        parse_file(marked)
    remote = Path("https://data.source.coop/fused/fsq-os-places/file.parquet")
    with pytest.raises(PlacesFsqError, match=r"^remote_path$"):
        parse_file(remote)


def test_mixed_frame_and_country_rows_are_counted_and_left_out(tmp_path: Path) -> None:
    """A row that passes one of the two tests is coverage, not a table row."""
    path = tmp_path / "mixed.parquet"
    write_places(
        path,
        [
            place(fsq_place_id="dddddddddddddddddddd000a"),
            place(
                fsq_place_id="dddddddddddddddddddd000b",
                country="AE",
                longitude=51.4,
                latitude=25.2,
            ),
            place(
                fsq_place_id="dddddddddddddddddddd000c",
                country="QA",
                longitude=10.0,
                latitude=40.0,
            ),
        ],
    )
    account = account_rows(parse_file(path), FRAME_BOX)
    assert [row.fsq_place_id for row in account.kept] == ["dddddddddddddddddddd000a"]
    assert account.point_not_country == 1
    assert account.country_not_point == 1


def test_duplicate_keeps_the_main_place_and_hides_the_copy(tmp_path: Path) -> None:
    """PUB-51 at 50 m, either name, and the main places row stays."""
    north_lon, north_lat = _at_distance(DUPLICATE_WITHIN_M)
    beyond_lon, beyond_lat = move_north(51.5, 25.3, DUPLICATE_WITHIN_M + 30)
    assert distance_m(51.5, 25.3, north_lon, north_lat) <= DUPLICATE_WITHIN_M
    assert distance_m(51.5, 25.3, beyond_lon, beyond_lat) > DUPLICATE_WITHIN_M
    same = PlaceStandIn("place-a", "Invented Cafe", None, 51.5, 25.3, False)
    other_language = PlaceStandIn(
        "place-b", "Other Invented", "Invented Bakery", north_lon, north_lat, False
    )
    showcase = PlaceStandIn("place-c", "Invented Stall", None, 51.5, 25.4, True)
    path = tmp_path / "dup.parquet"
    write_places(
        path,
        [
            place(fsq_place_id="eeeeeeeeeeeeeeeeeeee000a", name="  invented   cafe "),
            place(
                fsq_place_id="eeeeeeeeeeeeeeeeeeee000b",
                name="invented bakery",
                longitude=north_lon,
                latitude=north_lat,
            ),
            place(
                fsq_place_id="eeeeeeeeeeeeeeeeeeee000c",
                name="Invented Cafe",
                longitude=beyond_lon,
                latitude=beyond_lat,
            ),
            place(
                fsq_place_id="eeeeeeeeeeeeeeeeeeee000d",
                name="Invented Stall",
                longitude=51.5,
                latitude=25.4,
            ),
        ],
    )
    built = _build(
        path,
        (same, other_language, showcase),
        extra=((north_lon, north_lat), (beyond_lon, beyond_lat), (51.5, 25.4)),
    )
    shown = {item.row.fsq_place_id for item in built.eligible}
    assert "eeeeeeeeeeeeeeeeeeee000a" not in shown
    assert "eeeeeeeeeeeeeeeeeeee000b" not in shown
    assert "eeeeeeeeeeeeeeeeeeee000d" not in shown
    assert "eeeeeeeeeeeeeeeeeeee000c" in shown
    assert built.duplicates[2].in_showcase is True
    assert built.places == (same, other_language, showcase)
    assert all(item.source_release == _RELEASE for item in built.eligible)
    assert all(item.attribution == ATTRIBUTION for item in built.eligible)
    assert built.rows[0].name_ar is None
    assert built.coverage.name_ar_null == len(built.rows)
    assert built.coverage.name_ar_filled == 0
    assert normalise_duplicate_name("  Invented   Cafe ") == "invented cafe"
    closed = tmp_path / "closed.parquet"
    write_places(closed, [place(date_closed="2024-01-08")])
    hidden = _build(closed, ())
    assert hidden.rows[0].date_closed == date(2024, 1, 8)
    assert hidden.eligible == ()
    assert hidden.coverage.closed_not_shown == 1


def test_category_mapping_is_reviewed_and_unmapped_is_refused(
    tmp_path: Path,
) -> None:
    """The committed file is a header. An unmapped identifier refuses assembly."""
    assert load_mapping(_MAPPING, frozenset()) == ()
    header = _MAPPING.read_text(encoding="utf-8").strip()
    assert header == ",".join(MAPPING_COLUMNS)
    approved = _mapping(
        tmp_path / "approved.csv",
        [
            "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented"
        ],
    )
    mapping = load_mapping(approved, frozenset({"food"}))
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place(
                fsq_category_ids=["cccccccccccccccceeee0001"],
                fsq_category_labels=["Invented leaf"],
            ),
        ],
    )
    built = _build(path, (), mapping=mapping)
    by_id = {item.row.fsq_place_id: item for item in built.eligible}
    assert by_id["abcdabcdabcdabcdabcdabcd"].product_categories == "food"
    assert by_id["abcdabcdabcdabcdabcdabcd"].row.category_labels == "Invented leaf"
    assert built.coverage.unmapped_places == 0
    write_places(
        path,
        [
            place(
                fsq_category_ids=["dddddddddddddddddddd0009"],
                fsq_category_labels=["Unmapped leaf"],
            ),
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^category_unmapped$"):
        _build(path, (), mapping=mapping)
    unsigned = _mapping(
        tmp_path / "unsigned.csv",
        [
            "cccccccccccccccceeee0001,food,fsq-map-1,pending,reviewer,2026-11-14,invented"
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^mapping_unsigned$"):
        load_mapping(unsigned, frozenset({"food"}))
    unknown = _mapping(
        tmp_path / "unknown.csv",
        [
            "cccccccccccccccceeee0001,made-up,fsq-map-1,approved,reviewer,2026-11-14,invented"
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^mapping_unknown_target$"):
        load_mapping(unknown, frozenset({"food"}))
    conflict = _mapping(
        tmp_path / "conflict.csv",
        [
            "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented",
            "cccccccccccccccceeee0001,shop,fsq-map-1,approved,reviewer,2026-11-14,invented",
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^mapping_conflict$"):
        load_mapping(conflict, frozenset({"food", "shop"}))


def test_collision_check_covers_copy_names_including_a_hidden_duplicate() -> None:
    """A fictional label that matches a copy name fails. A public pair does not."""
    names = ("Invented Cafe", "Invented Cafe")
    assert check_labels(("Zedqun Label",), names, 3).ok
    assert check_labels(("Invented Cafe",), names, 3).ok is False
    assert check_labels(("invented cafe SYN",), names, 3).ok is False
    assert check_labels(("Cafe",), names, 3).ok is False
    assert check_labels(("Invented Caff",), names, 2).ok is False
    assert (
        check_labels(
            ("\u0625\u062e\u062a\u0628\u0627\u0631",),
            ("\u0627\u062e\u062a\u0628\u0627\u0631",),
            2,
        ).ok
        is False
    )
    safe = check_labels(("Zedqun Label",), names, 2)
    assert safe.ok
    assert safe.collisions == ()


def test_reviewed_policy_file_matches_the_enforced_rules(tmp_path: Path) -> None:
    """The committed policy is the reviewed record of the rules the code enforces."""
    assert_policy(_POLICY)
    planted = tmp_path / "policy.yaml"
    planted.write_text(
        _POLICY.read_text(encoding="utf-8").replace("distance_m: 50", "distance_m: 10"),
        encoding="utf-8",
    )
    with pytest.raises(PlacesFsqError, match=r"^policy_disagrees$"):
        assert_policy(planted)
    for old, new in (
        ('release: "newest_dated_at_each_refresh"', 'release: "2025-01-10"'),
        ('metadata_file: "<release>/places/_metadata"', 'metadata_file: "fixed"'),
        (
            "category_mapping: every_nonempty_identifier_reviewed",
            "category_mapping: partial_allowed",
        ),
        ("snapshots: every_dated_release_retained", "snapshots: latest_only"),
    ):
        planted.write_text(
            _POLICY.read_text(encoding="utf-8").replace(old, new), encoding="utf-8"
        )
        with pytest.raises(PlacesFsqError, match=r"^policy_disagrees$"):
            assert_policy(planted)


def test_a_bad_receipt_refuses_the_table(tmp_path: Path) -> None:
    """The manifest hash is checked. A substituted file is not parsed into the table."""
    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    with pytest.raises(PlacesFsqError, match=r"^receipt_mismatch$"):
        build_places(
            files={"near.parquet": path},
            expected_sha256={"near.parquet": "0" * 64},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3)),
            places=(),
            mapping=(),
            labels=(),
            min_edit_distance=3,
            release=_RELEASE,
            attribution=ATTRIBUTION,
            receipt_sha256="abc",
        )


def test_selection_refuses_a_bad_summary_and_keeps_a_file_without_geo() -> None:
    """A missing path, missing statistics and an empty summary each refuse."""
    plain = dict(_NEAR)
    plain["geo_bbox"] = None
    bare = metadata_bytes((plain,), dataset_geo_bbox=None)
    selected = select_partitions(bare, release=_RELEASE, frame=FRAME_BOX)
    assert selected.files == ("near.parquet",)
    assert selected.ignored_geo == ()
    empty = metadata_bytes((), dataset_geo_bbox=None)
    with pytest.raises(PlacesFsqError, match=r"^no_file_for_frame$"):
        select_partitions(empty, release=_RELEASE, frame=FRAME_BOX)
    nameless = dict(_NEAR)
    nameless["file_path"] = ""
    with pytest.raises(PlacesFsqError, match=r"^file_path_missing$"):
        select_partitions(
            metadata_bytes((nameless,), dataset_geo_bbox=None),
            release=_RELEASE,
            frame=FRAME_BOX,
        )
    unstated = dict(_NEAR)
    unstated["omit_latitude_stats"] = True
    with pytest.raises(PlacesFsqError, match=r"^statistics_missing$"):
        select_partitions(
            metadata_bytes((unstated,), dataset_geo_bbox=None),
            release=_RELEASE,
            frame=FRAME_BOX,
        )


def test_parser_refuses_wrong_types_and_a_geometry_that_is_not_a_swap(
    tmp_path: Path,
) -> None:
    """Each declared type and each geometry form is checked on its own."""
    plants = {
        "longitude": "VARCHAR",
        "latitude": "INTEGER",
        "geometry": "VARCHAR",
        "date_created": "INTEGER",
        "fsq_category_ids": "VARCHAR",
    }
    values = {
        "longitude": "51.5",
        "latitude": 25,
        "geometry": "not-wkb",
        "date_created": 2020012,
        "fsq_category_ids": "one",
    }
    missing = tmp_path / "missing.parquet"
    write_places(missing, [place()], drop=("geometry",))
    with pytest.raises(PlacesFsqError, match=r"^geometry$"):
        parse_file(missing)
    optional = tmp_path / "optional.parquet"
    write_places(
        optional, [place(address="Invented street")], extra={"address": "VARCHAR"}
    )
    assert parse_file(optional)[0].name == "Invented Cafe"
    for column, kind in plants.items():
        path = tmp_path / f"{column}.parquet"
        write_places(path, [place(**{column: values[column]})], types={column: kind})
        with pytest.raises(PlacesFsqError, match=column):
            parse_file(path)
    shifted = tmp_path / "shifted.parquet"
    write_places(shifted, [place(geometry=point_wkb(51.0, 25.0))])
    with pytest.raises(PlacesFsqError, match=r"^geometry$"):
        parse_file(shifted)
    eastern = tmp_path / "eastern.parquet"
    write_places(
        eastern,
        [place(geometry=struct.pack(">BIdd", 0, 1, 51.5, 25.3))],
    )
    assert parse_file(eastern)[0].lon == Decimal("51.500000")
    with_srid = tmp_path / "srid.parquet"
    write_places(
        with_srid,
        [place(geometry=struct.pack("<BIIdd", 1, 1 | (1 << 29), 4326, 51.5, 25.3))],
    )
    assert parse_file(with_srid)[0].lat == Decimal("25.300000")
    line = tmp_path / "line.parquet"
    write_places(line, [place(geometry=struct.pack("<BIdd", 1, 2, 51.5, 25.3))])
    with pytest.raises(PlacesFsqError, match=r"^geometry$"):
        parse_file(line)
    blank = tmp_path / "blank.parquet"
    write_places(
        blank,
        [
            place(
                fsq_place_id=None,
                name=None,
                fsq_category_ids=None,
                fsq_category_labels=None,
            )
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^fsq_place_id$"):
        parse_file(blank)
    named = tmp_path / "named.parquet"
    write_places(named, [place(fsq_place_id="abcdabcdabcdabcdabcdabce", name=None)])
    with pytest.raises(PlacesFsqError, match=r"^name$"):
        parse_file(named)
    undated = tmp_path / "undated.parquet"
    write_places(undated, [place(date_created="2020-1-02")])
    with pytest.raises(PlacesFsqError, match=r"^date_created$"):
        parse_file(undated)
    remote = Path("s3://bucket/places.parquet")
    with pytest.raises(PlacesFsqError, match=r"^remote_path$"):
        parse_file(remote)
    outside = tmp_path / "outside.parquet"
    write_places(
        outside,
        [
            place(
                fsq_place_id="dddddddddddddddddddd000d",
                country="AE",
                longitude=10.0,
                latitude=40.0,
            )
        ],
    )
    account = account_rows(parse_file(outside), FRAME_BOX)
    assert account.kept == ()
    assert account.point_not_country == 0
    assert account.country_not_point == 0
    quiet = tmp_path / "quiet.parquet"
    write_places(
        quiet,
        [place(fsq_category_ids=None, fsq_category_labels=None)],
    )
    parsed = parse_file(quiet)[0]
    assert parsed.category_ids == ""
    assert parsed.category_labels == ""
    assert is_eligible(parsed, FRAME_BOX, ()) is True
    assert is_eligible(parse_file(outside)[0], FRAME_BOX, ()) is False


def test_fetch_refuses_transport_faults_sign_in_and_unreadable_metadata(
    tmp_path: Path,
) -> None:
    """A transport fault, a sign-in page and an unreadable summary each refuse.

    Ruling L-1001 (PUB-97): a licence text that differs from the registry no
    longer refuses the release; the pending record it leaves is proved by the
    test that reads one to the end.
    """
    entry = _release_entry()
    blocked = _fault(
        entry, tmp_path / "blocked", TransportFault("blocked_host", entry.url)
    )
    assert blocked.failure is not None
    assert blocked.failure.check == "blocked_host"
    quiet = _fault(entry, tmp_path / "quiet", TransportFault("unreachable", entry.url))
    assert quiet.failure is not None
    assert quiet.failure.check == "unreachable"
    signed = _run(entry, tmp_path / "signed", _README, metadata=b"Please sign in")
    assert signed.failure is not None
    assert signed.failure.check == "sign_in_demand"
    other = _run(entry, tmp_path / "other", _README, metadata=b"not a parquet file")
    assert other.failure is not None
    assert other.failure.check == "metadata_unreadable"


def test_table_mapping_and_names_cover_the_remaining_plants(tmp_path: Path) -> None:
    """Attribution, an empty name, a bad mapping and the distance argument each refuse."""
    path = tmp_path / "places.parquet"
    write_places(path, [place(name="  ")])
    hidden = _build(path, ())
    assert hidden.eligible == ()
    with pytest.raises(PlacesFsqError, match=r"^attribution$"):
        build_places(
            files={"near.parquet": path},
            expected_sha256={"near.parquet": sha256_hex(path.read_bytes())},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3)),
            places=(),
            mapping=(),
            labels=(),
            min_edit_distance=3,
            release=_RELEASE,
            attribution="wrong",
            receipt_sha256="a" * 64,
        )
    with pytest.raises(PlacesFsqError, match=r"^receipt_mismatch$"):
        build_places(
            files={},
            expected_sha256={},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3)),
            places=(),
            mapping=(),
            labels=(),
            min_edit_distance=3,
            release=_RELEASE,
            attribution=ATTRIBUTION,
            receipt_sha256="a" * 64,
        )
    header = tmp_path / "header.csv"
    header.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(PlacesFsqError, match=r"^mapping_header$"):
        load_mapping(header, frozenset())
    repeated = _mapping(
        tmp_path / "same.csv",
        [
            "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented",
            "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented",
        ],
    )
    with pytest.raises(PlacesFsqError, match=r"^mapping_conflict$"):
        load_mapping(repeated, frozenset({"food"}))
    assert product_categories("", ()) is None
    listed = tmp_path / "list.yaml"
    listed.write_text("- release: 2025-01-10\n", encoding="utf-8")
    with pytest.raises(PlacesFsqError, match=r"^policy_disagrees$"):
        assert_policy(listed)
    changed = tmp_path / "country.yaml"
    changed.write_text(
        _POLICY.read_text(encoding="utf-8").replace("country: QA", "country: AE"),
        encoding="utf-8",
    )
    with pytest.raises(PlacesFsqError, match=r"^policy_disagrees$"):
        assert_policy(changed)
    flagged = tmp_path / "flag.yaml"
    flagged.write_text(
        _POLICY.read_text(encoding="utf-8").replace(
            "distance_m: 50", "distance_m: true"
        ),
        encoding="utf-8",
    )
    with pytest.raises(PlacesFsqError, match=r"^policy_disagrees$"):
        assert_policy(flagged)
    with pytest.raises(PlacesFsqError, match=r"^edit_distance$"):
        check_labels(("Zedqun",), ("Invented Cafe",), True)
    with pytest.raises(PlacesFsqError, match=r"^edit_distance$"):
        check_labels(("Zedqun",), ("Invented Cafe",), 0)
    blank = parse_file(path)[0]
    assert (
        duplicate_links((blank,), (PlaceStandIn("p", "   ", None, 51.5, 25.3, False),))
        == ()
    )


def test_a_place_without_a_real_copy_release_date_is_refused(tmp_path: Path) -> None:
    """An eligible place carries the actual folder date; malformed dates refuse."""
    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    digest = sha256_hex(path.read_bytes())
    with pytest.raises(PlacesFsqError, match=r"^source_release$"):
        build_places(
            files={"near.parquet": path},
            expected_sha256={"near.parquet": digest},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3)),
            places=(),
            mapping=(),
            labels=(),
            min_edit_distance=3,
            release="",
            attribution=ATTRIBUTION,
            receipt_sha256="a" * 64,
        )
    with pytest.raises(PlacesFsqError, match=r"^source_release$"):
        build_places(
            files={"near.parquet": path},
            expected_sha256={"near.parquet": digest},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3)),
            places=(),
            mapping=(),
            labels=(),
            min_edit_distance=3,
            release="2024-13-03",
            attribution=ATTRIBUTION,
            receipt_sha256="a" * 64,
        )
    built = build_places(
        files={"near.parquet": path},
        expected_sha256={"near.parquet": digest},
        frame=FRAME_BOX,
        grid=_grid((51.5, 25.3)),
        places=(),
        mapping=(),
        labels=(),
        min_edit_distance=3,
        release="2025-01-10",
        attribution=ATTRIBUTION,
        receipt_sha256="a" * 64,
    )
    assert len(built.eligible) == 1
    assert built.eligible[0].source_release == "2025-01-10"
    assert built.eligible[0].row.source_release == "2025-01-10"
    with pytest.raises(TypeError):
        EligiblePlace(
            row=built.eligible[0].row,
            product_categories=None,
            attribution=ATTRIBUTION,
            receipt_sha256="a" * 64,
        )


def test_world_build_name_function_refuses_a_label_that_collides_only_with_a_hidden_table_name(
    tmp_path: Path,
) -> None:
    """The function the world build will call refuses a label that hits only one table name.

    The inventory is every name of the new table, including a row hidden as a duplicate.
    """
    hidden = "Zedqun Hidden"
    shown = "Zedqun Shown"
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place(
                fsq_place_id="aaaaaaaaaaaaaaaaaaaa000a",
                name=hidden,
                longitude=51.5,
                latitude=25.3,
            ),
            place(
                fsq_place_id="aaaaaaaaaaaaaaaaaaaa000b",
                name=shown,
                longitude=51.5,
                latitude=25.4,
            ),
        ],
    )
    stand_in = PlaceStandIn("place-hidden", hidden, None, 51.5, 25.3, False)
    digest = sha256_hex(path.read_bytes())
    built = build_places(
        files={"near.parquet": path},
        expected_sha256={"near.parquet": digest},
        frame=FRAME_BOX,
        grid=_grid((51.5, 25.3), (51.5, 25.4)),
        places=(stand_in,),
        mapping=(),
        labels=("Qorvex Marker",),
        min_edit_distance=2,
        release="2025-01-10",
        attribution=ATTRIBUTION,
        receipt_sha256="a" * 64,
    )
    assert {row.name for row in built.rows} == {hidden, shown}
    assert {item.row.name for item in built.eligible} == {shown}
    assert built.names.ok
    assert built.names.collisions == ()
    table_names = tuple(row.name for row in built.rows)
    assert hidden in table_names
    assert shown in table_names
    assert check_labels((hidden,), (shown,), 2).ok is True
    assert check_labels((hidden,), (hidden,), 2).ok is False
    assert check_labels((hidden,), table_names, 2).ok is False
    with pytest.raises(PlacesFsqError, match=r"^name_collision$"):
        build_places(
            files={"near.parquet": path},
            expected_sha256={"near.parquet": digest},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3), (51.5, 25.4)),
            places=(stand_in,),
            mapping=(),
            labels=(hidden,),
            min_edit_distance=2,
            release="2025-01-10",
            attribution=ATTRIBUTION,
            receipt_sha256="a" * 64,
        )


def test_name_distance_and_empty_labels_match_hand_counts() -> None:
    """Counts below were written out by hand. An empty label is not a collision."""
    assert edit_distance("cafe", "cafe") == 0
    assert edit_distance("", "") == 0
    assert edit_distance("", "ab") == 2
    assert edit_distance("ab", "") == 2
    assert edit_distance("cafe", "caff") == 1
    assert edit_distance("a", "ab") == 1
    assert edit_distance("ab", "a") == 1
    assert edit_distance("ab", "b") == 1
    assert edit_distance("abc", "x") == 3
    assert edit_distance("kitten", "sitting") == 3
    assert check_labels(("",), ("ab",), 3).ok is True
    assert check_labels(("a",), ("SYN",), 2).ok is True
    hidden_after = check_labels(("Cafe",), ("SYN", "Cafe"), 2)
    assert hidden_after.ok is False
    assert hidden_after.collisions == ("Cafe",)
    assert check_labels(("caff",), ("cafe",), 1).ok is True
    assert check_labels(("zzzz",), ("cafe",), 1).ok is True
    assert check_labels(("aa bb",), ("cc dd ee",), 2).ok is True
    assert _window_contains(("aa", "bb"), ("aa", "bb")) is True
    assert _window_contains(("xx", "yy", "zz"), ("aa",)) is False
    assert _window_contains(("aa", "bb"), ("cc", "dd", "ee")) is False
    assert _contains_words((), ("aa",)) is False
    assert _contains_words(("aa",), ()) is False
    with pytest.raises(PlacesFsqError) as bad_type:
        check_labels(("Zedqun",), ("Cafe",), True)
    assert bad_type.value.reason == "edit_distance"
    with pytest.raises(PlacesFsqError) as too_small:
        check_labels(("Zedqun",), ("Cafe",), 0)
    assert too_small.value.reason == "edit_distance"


def _window_contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """The whole-word window used by the collision check, called for one pair."""
    from eii_custodian.publicdata.places_fsq.names import _window

    return _window(haystack, needle)


def _at_distance(metres: float) -> tuple[float, float]:
    """A point whose measured distance is within `metres`, on the closed edge."""
    lon, lat = move_north(51.5, 25.3, metres)
    for _ in range(10_000):
        if distance_m(51.5, 25.3, lon, lat) <= metres:
            return lon, lat
        lat = math.nextafter(lat, 0.0)
    raise AssertionError("distance did not fall to the requested metres")


def test_a_grid_without_the_kept_cells_counts_the_exclusion(tmp_path: Path) -> None:
    """A kept row whose cell is absent from the grid is counted and withheld."""
    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    built = _build(path, (), grid=_grid((0.0, 0.0)))
    assert built.rows == built.eligible == ()
    assert built.coverage.no_cell == 1


def _build(
    path: Path,
    places: tuple[PlaceStandIn, ...],
    mapping: tuple[object, ...] = (),
    extra: tuple[tuple[float, float], ...] = (),
    *,
    grid: list[dict[str, object]] | None = None,
    labels: tuple[str, ...] = (),
):
    points = ((51.5, 25.3), (51.5, 25.4), *extra)
    return build_places(
        files={"near.parquet": path},
        expected_sha256={"near.parquet": sha256_hex(path.read_bytes())},
        frame=FRAME_BOX,
        grid=_grid(*points) if grid is None else grid,
        places=places,
        mapping=mapping,
        labels=labels,
        min_edit_distance=3,
        release=_RELEASE,
        attribution=ATTRIBUTION,
        receipt_sha256="a" * 64,
    )


def _grid(*points: tuple[float, float]) -> list[dict[str, object]]:
    return [
        {"cell": h3.str_to_int(h3.latlng_to_cell(lat, lon, 9))} for lon, lat in points
    ]


def _release_entry():
    return next(entry for entry in load_registry() if entry.key == RELEASE_KEY)


def _replace(entry, **changes):
    values = entry.__dict__ | changes
    return type(entry)(**values)


def _clock() -> str:
    return "2026-11-14T12:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _fault(entry, cache: Path, fault: TransportFault):
    def transport(url: str) -> Response:
        raise fault

    return run_build((entry,), transport, cache, _clock, _sleep)


def _run(
    entry,
    cache: Path,
    terms: bytes,
    hops: tuple[str, ...] = (),
    metadata: bytes | None = None,
):
    body = (
        metadata_bytes((_NEAR,), dataset_geo_bbox=None)
        if metadata is None
        else metadata
    )
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == entry.url:
            return Response(final_url=url, body=listing(f"{_RELEASE}/"), hops=hops)
        if url.endswith("_metadata"):
            return Response(final_url=url, body=body, hops=())
        if url == entry.terms_url:
            return Response(final_url=url, body=terms, hops=())
        return Response(final_url=url, body=b"PAR1-not-used", hops=())

    outcome = run_build((entry,), transport, cache, _clock, _sleep)
    outcome_seen = seen
    assert all("evil.example" not in url for url in outcome_seen)
    return outcome


def _mapping(path: Path, rows: list[str]) -> Path:
    path.write_text(
        ",".join(MAPPING_COLUMNS) + "\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )
    return path
