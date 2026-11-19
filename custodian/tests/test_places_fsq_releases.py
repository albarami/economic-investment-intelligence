"""Newest-release discovery and provenance on invented responses only."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.fixtures.places_fsq.invented import listing, place, write_places
from custodian.tests.repository_root import repository_root
from custodian.tests.test_places_fsq import _grid, _release_entry

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.places_fsq.assemble import build_places
from eii_custodian.publicdata.places_fsq.constants import ATTRIBUTION, COPY_ROOT
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.fetch import fetch_release
from eii_custodian.publicdata.places_fsq.footer import metadata_bytes
from eii_custodian.publicdata.places_fsq.policy import (
    CategoryMapping,
    product_categories,
)
from eii_custodian.publicdata.places_fsq.releases import (
    select_release,
    validate_release,
    validate_release_path,
)
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX, select_partitions

_OLD = "2031-02-03"
_NEW = "2032-04-05"
_STABLE_KEY = "places_fsq/copy"


@pytest.mark.parametrize("validator", ["receipt", "selection"])
@pytest.mark.parametrize(
    "file_path",
    [
        f"{_NEW}/places/part-{_OLD}.parquet",
        f"{_OLD}/places/part-{_NEW}.parquet",
        f"{_NEW}/places/part-2033-06-07.parquet",
        f"part-{_NEW}-copied-{_OLD}.parquet",
        f"{_NEW}/{_OLD}/places/part.parquet",
    ],
)
def test_every_date_in_receipt_and_selection_paths_must_match(
    file_path: str, validator: str
) -> None:
    body = metadata_bytes(
        [dict(file_path=file_path, longitude=(51.0, 51.5), latitude=(25.0, 25.5))],
        dataset_geo_bbox=None,
    )
    with pytest.raises(PlacesFsqError, match=r"^release_mismatch$"):
        if validator == "receipt":
            validate_release_path(file_path, _NEW)
        else:
            select_partitions(body, _NEW, FRAME_BOX)


@pytest.mark.parametrize(
    "file_path",
    [
        f"{_NEW}/places/part-{_NEW}.parquet",
        f"{_NEW}/{_NEW}/part.parquet",
        "part.parquet",
    ],
)
def test_equal_release_dates_and_undated_paths_remain_valid(file_path: str) -> None:
    validate_release_path(file_path, _NEW)
    body = metadata_bytes(
        [dict(file_path=file_path, longitude=(51.0, 51.5), latitude=(25.0, 25.5))],
        dataset_geo_bbox=None,
    )
    assert select_partitions(body, _NEW, FRAME_BOX).files == (file_path,)


def test_unordered_listing_selects_greatest_valid_calendar_date() -> None:
    body = listing(
        "README.md",
        f"{_OLD}/",
        f"{_NEW}/",
        "2030-12-31/",
        "notes/release-dates",
    )
    assert select_release(body) == _NEW
    assert validate_release(_NEW) == _NEW


@pytest.mark.parametrize("body", [b"\xff", b'<a href="x" href="y">x</a>'])
def test_malformed_listing_fails_closed(body: bytes) -> None:
    with pytest.raises(PlacesFsqError, match=r"^release_listing$"):
        select_release(body)


@pytest.mark.parametrize("release", ["", "2032-4-05", "2032-02-30", "not-a-date"])
def test_release_validation_refuses_empty_or_malformed_dates(release: str) -> None:
    with pytest.raises(PlacesFsqError, match=r"^release_invalid$"):
        validate_release(release)


def test_release_validation_refuses_a_non_string() -> None:
    value: Any = None
    with pytest.raises(PlacesFsqError, match=r"^release_invalid$"):
        validate_release(value)


@pytest.mark.parametrize(
    "hrefs,reason",
    [
        (("README.md", "notes/"), "release_missing"),
        ((_NEW, "2032-04-06/"), "release_link"),
        ((f"{_NEW}/", f"{_NEW}/"), "release_duplicate"),
        ((f"{COPY_ROOT}{_NEW}/", f"{_NEW}/"), "release_duplicate"),
        (("2032-02-30/",), "release_invalid"),
        (("2032-4-05/",), "release_invalid"),
        ((f"https://invented.invalid/{_NEW}/",), "release_link"),
        ((f"https://data.source.coop/other/{_NEW}/",), "release_link"),
    ],
)
def test_bad_dated_candidates_fail_closed(hrefs: tuple[str, ...], reason: str) -> None:
    with pytest.raises(PlacesFsqError, match=rf"^{reason}$"):
        select_release(listing(*hrefs))


def test_fetch_follows_listing_to_newest_metadata_partitions_and_data(
    tmp_path: Path,
) -> None:
    entry = replace(_release_entry(), url=COPY_ROOT, terms_url="")
    data = tmp_path / "new.parquet"
    write_places(data, [place()])
    summary = metadata_bytes(
        [
            dict(
                file_path=f"{_NEW}/places/new.parquet",
                longitude=(51.5, 51.5),
                latitude=(25.3, 25.3),
            )
        ],
        dataset_geo_bbox=None,
    )
    metadata_url = f"{COPY_ROOT}{_NEW}/places/_metadata"
    data_url = f"{COPY_ROOT}{_NEW}/places/new.parquet"
    bodies = {
        COPY_ROOT: listing(f"{_NEW}/", f"{_OLD}/"),
        metadata_url: summary,
        data_url: data.read_bytes(),
    }
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(url, bodies[url], ())

    result, failure = fetch_release(
        entry,
        transport,
        tmp_path / "cache",
        lambda: "2091-01-01T00:00:00Z",
        lambda _: None,
    )
    assert failure is None
    assert result is not None
    assert seen == [COPY_ROOT, metadata_url, data_url]
    directory = tmp_path / "cache" / _STABLE_KEY / _NEW
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["release"] == _NEW
    assert manifest["listing_sha256"]
    assert manifest["metadata_sha256"]
    assert result.digest
    for role in ("listings", "metadata", "files", "manifests"):
        receipt = json.loads(next((directory / role).glob("*.meta.json")).read_bytes())
        assert receipt["source_modified"] == _NEW
        assert receipt["period_first"] == _NEW
        assert receipt["period_last"] == _NEW
    expected_urls = {
        "listings": COPY_ROOT,
        "metadata": metadata_url,
        "files": data_url,
        "manifests": metadata_url,
    }
    for role, fetch_url in expected_urls.items():
        receipt = json.loads(next((directory / role).glob("*.meta.json")).read_bytes())
        assert receipt["fetch_url"] == fetch_url
    assert not (tmp_path / "cache" / _STABLE_KEY / _OLD).exists()


def test_listing_sign_in_and_metadata_from_another_release_store_nothing(
    tmp_path: Path,
) -> None:
    entry = replace(_release_entry(), url=COPY_ROOT, terms_url="")

    def sign_in(_url: str) -> Response:
        return Response(COPY_ROOT, b"Please sign in", ())

    assert (
        fetch_release(
            entry, sign_in, tmp_path / "signin", lambda: "clock", lambda _: None
        )[0]
        is None
    )
    assert not (tmp_path / "signin").exists()

    other = metadata_bytes(
        [
            dict(
                file_path=f"{_OLD}/places/old.parquet",
                longitude=(51.5, 51.5),
                latitude=(25.3, 25.3),
            )
        ],
        dataset_geo_bbox=None,
    )

    def wrong_metadata(url: str) -> Response:
        body = listing(f"{_NEW}/") if url == COPY_ROOT else other
        return Response(url, body, ())

    result, failure = fetch_release(
        entry,
        wrong_metadata,
        tmp_path / "wrong",
        lambda: "clock",
        lambda _: None,
    )
    assert result is None
    assert failure is not None and failure.check == "release_mismatch"
    assert not (tmp_path / "wrong").exists()


def test_registry_is_stable_and_dynamic_release_fields_are_not_fixed() -> None:
    row = next(entry for entry in load_registry() if entry.key == _STABLE_KEY)
    assert row.url == COPY_ROOT
    assert row.period_first == ""
    assert row.period_last == ""
    assert "2025-01-10" not in row.title_en
    assert row.terms_url == f"{COPY_ROOT}README.md"


def test_every_decision_0064_item_14_passage_states_the_new_rule() -> None:
    root = repository_root(Path(__file__))
    passages = {
        "docs/01_PROJECT_BRIEF.md": 2,
        "docs/02_ARCHITECTURE.md": 1,
        "docs/03_DATA_CONTRACTS.md": 3,
        "docs/04_PUBLIC_DATA_PACK.md": 6,
        "docs/07_ECONOMIC_METHODS.md": 2,
        "docs/08_BACKEND.md": 1,
        "docs/09_AI_ASSISTANT.md": 1,
        "docs/13_DEPLOYMENT_AND_OPERATIONS.md": 1,
        "docs/14_IMPLEMENTATION_PLAN.md": 2,
        "docs/16_DEMO_RUNBOOK.md": 1,
    }
    for name, count in passages.items():
        text = (root / name).read_text(encoding="utf-8")
        assert "2025-01-10" not in text, name
        assert "public copy is frozen" not in text, name
        assert text.count("newest dated release") >= count, name
    for name in (
        "custodian/publicdata/sources.yaml",
        "custodian/publicdata/review/places_fsq_policy.yaml",
    ):
        assert "2025-01-10" not in (root / name).read_text(encoding="utf-8")
    sources = (root / "custodian/publicdata/sources.yaml").read_text(encoding="utf-8")
    policy = (root / "custodian/publicdata/review/places_fsq_policy.yaml").read_text(
        encoding="utf-8"
    )
    assert "newest dated release at each refresh" in sources
    assert "newest_dated_at_each_refresh" in policy


def test_every_nonempty_category_identifier_requires_reviewed_mapping() -> None:
    mapping = (
        CategoryMapping(
            "SYN-mapped",
            "food",
            "map-1",
            "approved",
            "reviewer",
            "2030-01-01",
            "invented",
        ),
    )
    assert product_categories("SYN-mapped", mapping) == "food"
    assert product_categories("", mapping) is None
    for categories in ("SYN-other", "SYN-mapped;SYN-other"):
        with pytest.raises(PlacesFsqError, match=r"^category_unmapped$"):
            product_categories(categories, mapping)


def test_second_release_propagates_and_receipt_date_mismatch_refuses(
    tmp_path: Path,
) -> None:
    path = tmp_path / "new.parquet"
    write_places(path, [place()])
    digest = sha256_hex(path.read_bytes())
    arguments = dict(
        files={f"{_NEW}/places/new.parquet": path},
        expected_sha256={f"{_NEW}/places/new.parquet": digest},
        frame=FRAME_BOX,
        grid=_grid((51.5, 25.3)),
        places=(),
        mapping=(),
        labels=(),
        min_edit_distance=2,
        release=_NEW,
        attribution=ATTRIBUTION,
        receipt_sha256="a" * 64,
    )
    built = build_places(**arguments)
    assert built.release == _NEW
    assert built.rows[0].source_release == _NEW
    assert built.eligible[0].source_release == _NEW
    for bad in ("", "2032-02-30"):
        with pytest.raises(PlacesFsqError, match=r"^source_release$"):
            build_places(**(arguments | {"release": bad}))
    mismatched = arguments | {
        "files": {f"{_OLD}/places/new.parquet": path},
        "expected_sha256": {f"{_OLD}/places/new.parquet": digest},
    }
    with pytest.raises(PlacesFsqError, match=r"^source_release$"):
        build_places(**mismatched)
