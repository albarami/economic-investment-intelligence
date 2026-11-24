"""Backend origin markers survive the audience removal (S3-T18, decision 0035 item 3).

Every fixture here is invented: no release, file, table or record of a real
build is read. Each marker at each level has its own planted removal, and a
planted false official or measured claim fails on its own.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from eii_product.backend_origin import (
    GENERATED_ORIGINS,
    LEVELS,
    MARKER_KEYS,
    REFUSAL_CODES,
    BackendOriginRefusal,
    claim_word_in,
    require_generated_output,
    require_markers,
    require_truthful_chain,
)

GENERATOR = "aleph_world_generator"
VERSION = "v0.0.1-invented"


def _markers(origin: str = "synthetic") -> dict[str, Any]:
    return {"origin": origin, "generator_name": GENERATOR, "generator_version": VERSION}


def _release(origin: str = "synthetic") -> dict[str, Any]:
    record = {"record_key": "SYN-R-ALEPH", **_markers(origin)}
    table = {"name": "aleph_invented_table", "records": [record], **_markers(origin)}
    file = {"path": "invented/aleph.parquet", "tables": [table], **_markers(origin)}
    return {"release_id": "rel-aleph-invented", "files": [file], **_markers(origin)}


def _chain() -> dict[str, Any]:
    return {
        "method": "aleph_count_method",
        "method_version": "m1",
        "pipeline": GENERATOR,
        "pipeline_version": VERSION,
        "label_en": "People in the drawn area",
        "label_ar": "الأشخاص في المنطقة المرسومة",
        "inputs": [
            {"publisher": "Aleph Public Works Office", "dataset": "Invented page"}
        ],
    }


def _level_of(release: dict[str, Any], level: str) -> dict[str, Any]:
    node = release
    for step in ("files", "tables", "records")[: LEVELS.index(level)]:
        node = node[step][0]
    return node


def test_a_whole_generated_output_passes_and_is_left_unchanged() -> None:
    for origin in sorted(GENERATED_ORIGINS):
        release = _release(origin)
        before = copy.deepcopy(release)
        require_generated_output(release)
        assert release == before


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("key", MARKER_KEYS)
def test_a_planted_removal_of_each_marker_at_each_level_fails(
    level: str, key: str
) -> None:
    release = _release()
    del _level_of(release, level)[key]
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_generated_output(release)
    assert refusal.value.code == "marker_missing"
    assert refusal.value.where.endswith(f".{key}")
    depth = LEVELS.index(level)
    assert refusal.value.where.count("[0]") == depth


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("key", MARKER_KEYS)
def test_a_blank_marker_fails(level: str, key: str) -> None:
    release = _release()
    _level_of(release, level)[key] = "  "
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_generated_output(release)
    assert refusal.value.code == "marker_blank"


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("origin", ["public", "Synthetic", "suppressed", "measured"])
def test_an_origin_that_is_not_a_generated_class_fails(level: str, origin: str) -> None:
    release = _release()
    _level_of(release, level)["origin"] = origin
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_generated_output(release)
    assert refusal.value.code == "origin_not_generated"


def test_a_marker_is_never_inherited_from_the_level_above() -> None:
    release = _release()
    del release["files"][0]["tables"][0]["records"][0]["origin"]
    assert release["files"][0]["tables"][0]["origin"] == "synthetic"
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_generated_output(release)
    assert refusal.value.where == "release.files[0].tables[0].records[0].origin"


@pytest.mark.parametrize("child", ["files", "tables", "records"])
def test_a_level_without_its_children_fails(child: str) -> None:
    release = _release()
    parent = _level_of(release, LEVELS[("files", "tables", "records").index(child)])
    parent[child] = []
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_generated_output(release)
    assert refusal.value.code == "level_shape"


def test_an_unknown_level_and_an_unknown_code_fail() -> None:
    with pytest.raises(BackendOriginRefusal):
        require_markers("bundle", _markers())
    with pytest.raises(ValueError):
        BackendOriginRefusal("made_up", "here")
    assert "claim_word" in REFUSAL_CODES


def test_a_truthful_chain_names_its_pipeline_and_keeps_public_inputs() -> None:
    chain = _chain()
    before = copy.deepcopy(chain)
    require_truthful_chain(chain, _markers())
    assert chain == before
    assert chain["inputs"][0]["publisher"] == "Aleph Public Works Office"


@pytest.mark.parametrize(
    "key", ["method", "method_version", "pipeline", "pipeline_version"]
)
def test_a_chain_without_its_method_or_pipeline_fails(key: str) -> None:
    chain = _chain()
    del chain[key]
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_truthful_chain(chain, _markers())
    assert refusal.value.code == "pipeline_missing"


@pytest.mark.parametrize(
    ("key", "value"),
    [("pipeline", "another_generator"), ("pipeline_version", "v9")],
)
def test_a_chain_naming_another_producer_fails(key: str, value: str) -> None:
    chain = _chain()
    chain[key] = value
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_truthful_chain(chain, _markers())
    assert refusal.value.code == "pipeline_mismatch"


def test_a_planted_outside_publisher_fails() -> None:
    chain = _chain()
    chain["publisher"] = "Aleph Statistics Office"
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_truthful_chain(chain, _markers())
    assert refusal.value.code == "outside_publisher"


CLAIMS = [
    ("method", "official_count_method"),
    ("method", "Measured presence"),
    ("label_en", "Ministry figures for the area"),
    ("label_en", "Observed from a real register"),
    ("caveat_text", "Government data"),
    ("label_ar", "عدد رسمي في المنطقة"),
    ("label_ar", "عدد مُقاس"),
    ("label_ar", "أرقام الوزارة"),
    ("pipeline", GENERATOR),
]


@pytest.mark.parametrize(("key", "value"), CLAIMS[:-1])
def test_a_planted_false_official_or_measured_claim_fails(key: str, value: str) -> None:
    chain = _chain()
    chain[key] = value
    with pytest.raises(BackendOriginRefusal) as refusal:
        require_truthful_chain(chain, _markers())
    assert refusal.value.code == "claim_word"
    assert refusal.value.where == f"chain.{key}"


@pytest.mark.parametrize(
    "value",
    [
        "aleph_count_method",
        "People in the drawn area",
        "Observed",
        "Estimated people present",
        "الأشخاص في المنطقة المرسومة",
        "unofficially_named_column",
    ],
)
def test_ordinary_method_and_label_words_are_not_claims(value: str) -> None:
    assert claim_word_in(value) is False


def _refusal_of(plant: Callable[[dict[str, Any]], None]) -> str:
    release = _release()
    plant(release)
    try:
        require_generated_output(release)
    except BackendOriginRefusal as refusal:
        return refusal.code
    return "passed"


def test_each_planted_removal_fails_only_its_own_check() -> None:
    def drop_origin(release: dict[str, Any]) -> None:
        del release["origin"]

    def blank_name(release: dict[str, Any]) -> None:
        release["generator_name"] = ""

    def public_origin(release: dict[str, Any]) -> None:
        release["origin"] = "public"

    def nothing(release: dict[str, Any]) -> None:
        return None

    assert _refusal_of(drop_origin) == "marker_missing"
    assert _refusal_of(blank_name) == "marker_blank"
    assert _refusal_of(public_origin) == "origin_not_generated"
    assert _refusal_of(nothing) == "passed"
