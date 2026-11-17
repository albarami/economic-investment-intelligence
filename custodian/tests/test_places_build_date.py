"""PO-LR3-2: build-start UTC date reaches the real verification loader."""

import csv
import json
from dataclasses import replace
from datetime import date

import pytest
from custodian.tests.test_places_build_survivors import _pub_place
from custodian.tests.test_places_stage import _frame_stage_fixture

from eii_custodian.publicdata.fetch import build as fetch
from eii_custodian.publicdata.fetch.snapshots import read_snapshot, reviewed_selections
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.review import (
    VERIFIED_COLUMNS,
    load_verified_places,
)


def _ready(tmp_path):
    cache, review, output, entries = _frame_stage_fixture(tmp_path)
    # The production locator expects this repository-shaped layout.
    original_cache = cache
    cache = tmp_path / "data/public_cache"
    cache.parent.mkdir()
    original_cache.rename(cache)
    target = tmp_path / "custodian/publicdata/review"
    target.parent.mkdir(parents=True)
    review.rename(target)
    entries = [replace(e, skip_reason="", terms_url="") for e in entries]
    return cache, target, output, entries


def _run(cache, entries, timestamp, monkeypatch):
    def already_fetched(
        entry, transport, cache, clock, sleep, token, *, registry_entries
    ):
        selected = reviewed_selections(cache)[entry.key]
        meta = read_snapshot(cache / entry.key, selected).sidecar
        return fetch._Fetched(meta["sha256"], entry.fetch_host, clock(), "", ""), None

    monkeypatch.setattr(fetch, "_fetch_row", already_fetched)
    monkeypatch.setattr(fetch, "is_place_file", lambda _: False)
    calls = []

    def clock():
        calls.append(timestamp)
        # Retrieval clocks may cross midnight; build date must stay at start.
        return timestamp if len(calls) == 1 else "2026-11-19T00:00:00Z"

    outcome = fetch.run_build(entries, object(), cache, clock, lambda _: None)
    return outcome, calls


def test_build_start_utc_midnight_to_real_places_loader(tmp_path, monkeypatch):
    """PO-LR3-2: adjacent 23:59:59Z/00:00:00Z runs accept same-day checks."""
    cache, review, _, entries = _ready(tmp_path)
    # No showcase gate is allowed to mask the verification loader's result.
    (review / "showcase_gazetteer.yaml").write_text("[]\n")
    path = review / "verified_places.csv"
    for timestamp, expected in (
        ("2026-11-17T23:59:59Z", date(2026, 11, 17)),
        ("2026-11-18T00:00:00Z", date(2026, 11, 18)),
    ):
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(VERIFIED_COLUMNS)
            writer.writerow(
                [
                    "SYN-LAND",
                    expected.isoformat(),
                    "SYN reviewer",
                    "https://example.org/check",
                    "verified_open",
                    "official_website",
                ]
            )
        observed = []
        from eii_custodian.publicdata.places import build as places

        def recording_loader(committed, cache_path, ids, build_date, observed=observed):
            observed.append(build_date)
            return load_verified_places(committed, cache_path, ids, build_date)

        monkeypatch.setattr(places, "load_verified_places", recording_loader)
        outcome, calls = _run(cache, entries, timestamp, monkeypatch)
        assert observed == [expected]
        assert len(calls) == len(entries) + 1
        assert not any("bad_check_date" in line for line in outcome.lines)
        output = cache / "places_s2_t06/pub_place_verification.jsonl"
        assert json.loads(output.read_text())["check_date"] == expected.isoformat()


@pytest.mark.parametrize(
    "timestamp",
    [
        "bad",
        "2026-11-17",
        "2026-11-17T00:00:00",
        "2026-11-17T00:00:00+03:00",
        "2026-02-30T00:00:00Z",
    ],
)
def test_malformed_build_clock_refused(tmp_path, monkeypatch, timestamp):
    cache, _, _, entries = _ready(tmp_path)
    with pytest.raises(ValueError, match="build-start UTC"):
        _run(cache, entries, timestamp, monkeypatch)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("header", "verified_header"),
        ("zero", "verified_header"),
        ("future", "bad_check_date"),
        ("malformed", "bad_check_date"),
        ("orphan", "orphan_place_id"),
        ("duplicate", "duplicate_place_date"),
        ("status", "unknown_status"),
        ("omitted_date", "bad_check_date"),
        ("empty", None),
        ("earlier", None),
        ("same_day", None),
    ],
)
def test_build_date_verification_guards(tmp_path, plant, reason):
    from eii_custodian.publicdata.places.build import _verifications

    path = tmp_path / "verified_places.csv"
    row = [
        "SYN-LAND",
        "2026-11-17",
        "SYN reviewer",
        "https://example.org/check",
        "verified_open",
        "official_website",
    ]
    if plant == "future":
        row[1] = "2026-11-18"
    elif plant == "malformed":
        row[1] = "not-a-date"
    elif plant == "orphan":
        row[0] = "SYN-ORPHAN"
    elif plant == "status":
        row[4] = "made-up"
    elif plant == "earlier":
        row[1] = "2026-11-16"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(VERIFIED_COLUMNS)
        if plant not in ("empty", "omitted_date"):
            writer.writerow(row)
            if plant == "duplicate":
                writer.writerow(row)
    if plant == "zero":
        path.write_text("")
    elif plant == "header":
        path.write_text("wrong,header\n")
    build_date = None if plant == "omitted_date" else date(2026, 11, 17)

    def invoke():
        return _verifications(
            (), path, None, (_pub_place(place_id="SYN-LAND"),), build_date
        )

    if reason:
        with pytest.raises(PlacesError) as error:
            invoke()
        assert error.value.reason == reason
    else:
        rows = invoke()
        assert len(rows) == (0 if plant == "empty" else 1)


def test_midnight_planted_previous_date_refused_by_real_loader(tmp_path, monkeypatch):
    """PO-LR3-2 plant: retaining yesterday at midnight refuses today's check."""
    from eii_custodian.publicdata.places import integrate

    cache, review, _, entries = _ready(tmp_path)
    (review / "showcase_gazetteer.yaml").write_text("[]\n")
    with (review / "verified_places.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(VERIFIED_COLUMNS)
        writer.writerow(
            [
                "SYN-LAND",
                "2026-11-18",
                "SYN reviewer",
                "https://example.org/check",
                "verified_open",
                "official_website",
            ]
        )
    real_stage = integrate.run_places_before_gazetteer

    def planted(*args, **kwargs):
        assert kwargs["build_date"] == date(2026, 11, 18)
        kwargs["build_date"] = date(2026, 11, 17)
        return real_stage(*args, **kwargs)

    monkeypatch.setattr(integrate, "run_places_before_gazetteer", planted)
    outcome, _ = _run(cache, entries, "2026-11-18T00:00:00Z", monkeypatch)
    assert "stage places bad_check_date" in outcome.lines
    assert not (cache / "places_s2_t06/place_points.json").exists()
