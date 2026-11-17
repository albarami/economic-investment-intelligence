"""The series stage reads the municipalities the same build's frame wrote.

Every municipality code, Arabic name and row here is invented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer
from custodian.tests.test_frame_census import entry
from custodian.tests.test_places_stage import _frame_review
from custodian.tests.test_public_series import series_cache

from eii_custodian.publicdata.fetch.receipts import (
    commit_pair,
    sha256_hex,
    sidecar_for,
)

_CODE = "SYN-M1"
_CODE_B = "SYN-M2"
_NAME = "بلدية وهمية أولى"
_NAME_B = "بلدية وهمية ثانية"
_FRAME_NAME = "اسم تجريبي"
_FRAME_CODE = "9"
_OUTPUT = Path("frame_s2_t02") / "municipalities.json"


def _output(
    cache: Path, rows: list[dict[str, object]], count: int | None = None
) -> Path:
    path = cache / _OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "count": len(rows) if count is None else count,
                "municipalities": rows,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _lic(cache: Path, source: str, name: str):
    rows = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )[source]
    for row in rows:
        row["lbldy"] = name
    return series_cache(cache, source, rows)


def test_finish_build_passes_frame_municipalities(tmp_path: Path) -> None:
    """With the frame output the licence rows carry the frame's codes."""
    from eii_custodian.publicdata.series.figures import finish_build

    _output(
        tmp_path,
        [
            {"municipality_code": _CODE, "name_ar": _NAME},
            {"municipality_code": _CODE_B, "name_ar": _NAME_B},
        ],
    )
    lic_entry, digest = _lic(tmp_path, "lic_issued", _NAME)
    lines = [f"PASS {lic_entry.key} sha256={digest} host=invented"]
    result = finish_build([lic_entry], tmp_path, lines)
    table = json.loads(
        (tmp_path / "series/internal/pub_licence_issued.json").read_text()
    )
    assert {row["municipality_code"] for row in table["rows"]} == {_CODE}
    coverage = json.loads((tmp_path / "series/internal/coverage.json").read_text())
    assert coverage["lic_issued.municipality_exact_match"] == []
    assert result is not None and result.source_id == "PUB-69"
    assert lines[-1] == "FAIL PUB-69 public_data selected-cache check"


def test_finish_build_without_frame_output_fails_closed(tmp_path: Path) -> None:
    """Absent output fails on municipality_frame_not_supplied, not a figure."""
    from eii_custodian.publicdata.series.figures import finish_build

    lic_entry, lic_digest = _lic(tmp_path, "lic_issued", _NAME)
    active_entry, active_digest = _lic(tmp_path, "lic_active", _NAME)
    lines = [
        f"PASS {lic_entry.key} sha256={lic_digest} host=invented",
        f"PASS {active_entry.key} sha256={active_digest} host=invented",
    ]
    result = finish_build([lic_entry, active_entry], tmp_path, lines)
    assert result is not None
    assert result.source_id == "series"
    assert result.check == "public_data"
    assert result.observed == "municipality_frame_absent"
    assert (
        lines[-1] == "FAIL series municipality_frame_not_supplied lic_active lic_issued"
    )
    assert not (tmp_path / "series/internal/pub_licence_issued.json").exists()


@pytest.mark.parametrize(
    "payload,reason",
    [
        ("missing", "municipality_frame_absent"),
        ("empty", "municipality_frame_absent"),
        ("unreadable", "municipality_frame_absent"),
        ("malformed", "municipality_frame_absent"),
        ("non_dict", "municipality_frame_absent"),
        ([{"municipality_code": "", "name_ar": _NAME}], "municipality_field_empty"),
        ([{"municipality_code": _CODE, "name_ar": ""}], "municipality_field_empty"),
        (
            [
                {"municipality_code": _CODE, "name_ar": _NAME},
                {"municipality_code": _CODE, "name_ar": _NAME_B},
            ],
            "municipality_code_repeated",
        ),
        (
            [
                {"municipality_code": _CODE, "name_ar": _NAME},
                {"municipality_code": _CODE_B, "name_ar": _NAME},
            ],
            "municipality_name_repeated",
        ),
        ("count", "municipality_count_mismatch"),
    ],
)
def test_frame_municipalities_refusals(
    tmp_path: Path, payload: object, reason: str
) -> None:
    """Each planted violation reaches only its own fixed refusal."""
    from eii_custodian.publicdata.series.frame import (
        MunicipalityFrameRefused,
        frame_municipalities,
    )

    if payload == "empty":
        _output(tmp_path, [])
    elif payload == "unreadable":
        _output(tmp_path, [{"municipality_code": _CODE, "name_ar": _NAME}]).chmod(0)
    elif payload == "malformed":
        _output(tmp_path, [{"municipality_code": _CODE, "name_ar": _NAME}]).write_bytes(
            b"not-json"
        )
    elif payload == "non_dict":
        _output(tmp_path, []).write_text("[1]", encoding="utf-8")
    elif payload == "count":
        _output(tmp_path, [{"municipality_code": _CODE, "name_ar": _NAME}], count=2)
    elif payload != "missing":
        _output(tmp_path, payload)  # type: ignore[arg-type]
    with pytest.raises(MunicipalityFrameRefused) as found:
        frame_municipalities(tmp_path)
    assert found.value.reason == reason


def test_frame_then_stage_supplies_municipalities(tmp_path: Path) -> None:
    """The real order of fetch/build.py: the frame, then the stage, joins."""
    from eii_custodian.publicdata.places.integrate import frame_when_ready
    from eii_custodian.publicdata.stage import run_stage

    cache = tmp_path / "data" / "public_cache"
    review = tmp_path / "custodian" / "publicdata" / "review"
    review.mkdir(parents=True)
    _frame_review(review)
    (review / "showcase_gazetteer.yaml").write_text("[]\n", encoding="utf-8")
    (review / "flagship_candidates.yaml").write_text("[]\n", encoding="utf-8")
    entries = [
        entry(name) for name in ("bnd_hdx", "bnd_zone_2020", "bnd_district_2020")
    ]
    for source in entries:
        body = (
            invented_archive()
            if source.source_id == "bnd_hdx"
            else json.dumps(invented_layer(source.source_id)).encode()
        )
        digest = sha256_hex(body)
        receipt = sidecar_for(
            source,
            digest=digest,
            nbytes=len(body),
            fetch_url=source.url,
            fetch_host=source.fetch_host,
            retrieved_utc="2026-11-14T00:00:00Z",
            publisher=source.publisher,
            source_modified="",
            row_count=None,
            terms_sha256="",
        )
        commit_pair(cache / source.key, digest, source.extension, body, receipt)
    lic_entry, digest = _lic(cache, "lic_issued", _FRAME_NAME)
    entries.append(lic_entry)
    lines = [f"PASS {lic_entry.key} sha256={digest} host=invented"]
    frame_when_ready(cache, entries, lines)
    written = json.loads((cache / _OUTPUT).read_text(encoding="utf-8"))
    assert written == {
        "count": 1,
        "municipalities": [
            {
                "municipality_code": _FRAME_CODE,
                "name_en": "Invented municipality",
                "name_ar": _FRAME_NAME,
            }
        ],
    }
    outcome = run_stage(cache, build_entries=entries, build_lines=lines)
    assert outcome.failure is not None
    assert outcome.failure.source_id == "PUB-69"
    assert lines[-1] == "FAIL PUB-69 public_data selected-cache check"
    table = json.loads((cache / "series/internal/pub_licence_issued.json").read_text())
    assert {row["municipality_code"] for row in table["rows"]} == {_FRAME_CODE}


def test_frame_when_ready_drops_stale_output(tmp_path: Path) -> None:
    """A run that builds no frame leaves no output for the stage to read."""
    from eii_custodian.publicdata.places.integrate import frame_when_ready

    cache = tmp_path / "data" / "public_cache"
    _output(cache, [{"municipality_code": _CODE, "name_ar": _NAME}])
    frame_when_ready(cache, [entry("bnd_hdx")], [])
    assert not (cache / _OUTPUT).exists()
