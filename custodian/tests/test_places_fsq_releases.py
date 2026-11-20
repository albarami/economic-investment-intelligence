"""Newest-release discovery and provenance on invented responses only."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.fixtures.places_fsq.invented import (
    bucket_listing,
    listing,
    place,
    write_places,
)
from custodian.tests.repository_root import repository_root
from custodian.tests.test_places_fsq import _grid, _release_entry

from eii_custodian.publicdata.fetch.build import run_build
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
    body = bucket_listing(
        "fsq-os-places/README.md",
        f"fsq-os-places/{_NEW}/places/SYN-new.parquet",
        f"fsq-os-places/{_OLD}/places/_metadata",
        f"fsq-os-places/{_NEW}/places/_metadata",
        "fsq-os-places/2030-12-31/places/_metadata",
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
    "keys,reason",
    [
        (("README.md",), "release_missing"),
        ((f"{_NEW}/SYN-other.parquet",), "release_key"),
        ((f"{_NEW}/places/_metadata",) * 2, "release_duplicate"),
        ((f"{_NEW}/places/SYN-part.parquet",) * 2, "release_duplicate"),
        (("2032-02-30/places/_metadata",), "release_invalid"),
        (("2032-4-05/places/_metadata",), "release_invalid"),
        ((f"https://invented.invalid/{_NEW}/",), "release_key"),
        ((f"https://data.source.coop/other/{_NEW}/",), "release_key"),
    ],
)
def test_bad_dated_candidates_fail_closed(keys: tuple[str, ...], reason: str) -> None:
    with pytest.raises(PlacesFsqError, match=rf"^{reason}$"):
        select_release(bucket_listing(*(f"fsq-os-places/{key}" for key in keys)))


def test_observed_bucket_shape_selects_metadata_backed_newest_release() -> None:
    # Lead's LISTING-SHAPE.md: same dated segments, invented keys and sizes.
    dates = ("2024-11-19", "2024-12-03", "2025-01-10", "2025-02-06")
    keys = ["fsq-os-places/README.md"]
    for release in reversed(dates):
        keys.extend(
            f"fsq-os-places/{release}/places/{name}"
            for name in ("SYN-part.parquet", "_metadata", "SYN-extra.txt")
        )
    assert select_release(bucket_listing(*keys)) == "2025-02-06"


@pytest.mark.parametrize("has_older", [False, True])
def test_plant_dated_folder_without_metadata_is_not_a_release(has_older: bool) -> None:
    keys = [f"fsq-os-places/{_NEW}/places/SYN-part.parquet"]
    if has_older:
        keys.append(f"fsq-os-places/{_OLD}/places/_metadata")
        assert select_release(bucket_listing(*keys)) == _OLD
    else:
        with pytest.raises(PlacesFsqError, match=r"^release_missing$"):
            select_release(bucket_listing(*keys))


@pytest.mark.parametrize(
    "declaration",
    [
        '<!DOCTYPE ListBucketResult SYSTEM "https://invented.invalid/SYN-dtd">',
        '<!DOCTYPE ListBucketResult [<!ENTITY SYN "fsq-os-places/">]>',
        '<?SYN-instruction reject="yes"?>',
    ],
    ids=["plant-doctype", "plant-entity-declaration", "plant-processing-instruction"],
)
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_plant_xml_declarations_are_refused(declaration: str, encoding: str) -> None:
    text = listing(f"{_NEW}/").decode().split("?>", 1)[1]
    body = (declaration + text).encode(encoding)
    with pytest.raises(PlacesFsqError, match=r"^release_listing$"):
        select_release(body)


@pytest.mark.parametrize("position", ["inside", "after"])
def test_plant_processing_instruction_anywhere_is_refused(position: str) -> None:
    body = listing(f"{_NEW}/")
    instruction = b"<?SYN-instruction?>"
    if position == "inside":
        body = body.replace(b"<Marker/>", b"<Marker/>" + instruction)
    else:
        body += instruction
    with pytest.raises(PlacesFsqError, match=r"^release_listing$"):
        select_release(body)


@pytest.mark.parametrize(
    "body,reason",
    [
        (bucket_listing(prefix="SYN-wrong/"), "release_prefix"),
        (bucket_listing("other/SYN-file"), "release_prefix"),
        (
            bucket_listing(namespace="https://invented.invalid/SYN-namespace"),
            "release_listing",
        ),
        (
            listing(f"{_NEW}/").replace(b"<Prefix>", b"<Prefix/><Prefix>"),
            "release_listing",
        ),
        (
            listing(f"{_NEW}/").replace(b"<IsTruncated>false</IsTruncated>", b""),
            "release_listing",
        ),
        (bucket_listing(truncated="False"), "release_listing"),
        (listing(f"{_NEW}/").replace(b"<Key>", b"<Key/><Key>"), "release_listing"),
        (b'<html><a href="2032-04-05/">SYN-release</a></html>', "release_listing"),
    ],
    ids=[
        "plant-prefix",
        "plant-key-prefix",
        "plant-namespace",
        "plant-double-prefix",
        "plant-missing-truncation",
        "plant-truncation-case",
        "plant-double-key",
        "plant-html",
    ],
)
def test_plant_bucket_shape_failures(body: bytes, reason: str) -> None:
    with pytest.raises(PlacesFsqError, match=rf"^{reason}$"):
        select_release(body)


def test_plant_truncated_listing_is_never_read_in_part() -> None:
    body = bucket_listing(
        f"fsq-os-places/{_NEW}/places/_metadata",
        "other/SYN-file",
        truncated="true",
    )
    with pytest.raises(PlacesFsqError, match=r"^release_truncated$"):
        select_release(body)


@pytest.mark.parametrize(
    "body,reason",
    [
        (bucket_listing(prefix="SYN-other/"), "release_prefix"),
        (bucket_listing(truncated="true"), "release_truncated"),
        (bucket_listing(f"fsq-os-places/{_NEW}/other/SYN-file"), "release_key"),
        (b"<?SYN-instruction?>" + listing(f"{_NEW}/"), "release_listing"),
    ],
    ids=[
        "plant-prefix-report",
        "plant-truncated-report",
        "plant-key-report",
        "plant-xml-report",
    ],
)
def test_build_public_reports_listing_reason_and_never_uses_cached_release(
    body: bytes, reason: str, tmp_path: Path
) -> None:
    entry = replace(_release_entry(), url=COPY_ROOT, terms_url="")
    cache = tmp_path / "cache"
    sentinel = cache / _STABLE_KEY / _OLD / "SYN-retained"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"SYN-unchanged")
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(url, body, ())

    result = run_build(
        (entry,), transport, cache, lambda: "2091-01-01T00:00:00Z", lambda _: None
    )
    assert result.failure is not None
    assert result.failure.check == reason
    assert any(
        line
        == f"FAIL {_STABLE_KEY} {COPY_ROOT} {reason} expected=newest dated release observed=none"
        for line in result.lines
    )
    assert f" {reason} " in result.failure.detail
    assert seen == [COPY_ROOT]
    assert sentinel.read_bytes() == b"SYN-unchanged"
    assert not (cache / _STABLE_KEY / _NEW).exists()


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
    archived = list((directory / "listings").glob("*.xml"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == bodies[COPY_ROOT]
    assert not list((directory / "listings").glob("*.html"))
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


def test_readme_s2_t15_paragraph_names_newest_release_at_refresh() -> None:
    root = repository_root(Path(__file__))
    readme = (root / "README.md").read_text(encoding="utf-8")
    paragraph = next(p for p in readme.split("\n\n") if p.startswith("Task S2-T15"))
    assert "release 2025-01-10" not in paragraph
    assert "newest dated release" in paragraph
    assert "keeping the stated pipeline limits" not in paragraph
    assert "parses hand-made Parquet" in paragraph


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


@pytest.mark.parametrize(
    "root",
    [
        (
            "SYN:ListBucketResult",
            ' xmlns:SYN="https://invented.invalid/SYN-namespace"'
            ' xmlns="http://s3.amazonaws.com/doc/2006-03-01/"',
        ),
        ("ListAllMyBucketsResult", ' xmlns="http://s3.amazonaws.com/doc/2006-03-01/"'),
    ],
    ids=["plant-root-namespace-only", "plant-root-name-only"],
)
def test_plant_root_alone_wrong_with_s3_children_is_refused(
    root: tuple[str, str],
) -> None:
    """Only the root guard refuses: every child stays in the S3 namespace."""
    tag, declarations = root
    body = (
        listing(f"{_NEW}/")
        .replace(
            b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">',
            f"<{tag}{declarations}>".encode(),
        )
        .replace(b"</ListBucketResult>", f"</{tag}>".encode())
    )
    assert f"<{tag}".encode() in body
    with pytest.raises(PlacesFsqError, match=r"^release_listing$"):
        select_release(body)
