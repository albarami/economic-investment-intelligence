"""Build-only busyness integration, wholly invented and offline."""

import json

import pytest
from custodian.tests.test_publicdata_besttime_parse import encode, forecast, query
from custodian.tests.test_publicdata_besttime_review import CROSSWALK, REQUESTS, VENUES

from eii_custodian.publicdata.busyness.build import build_busyness
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import KeyedRequest, Response


def setup(tmp_path, count=1, *, address_cache=True):
    review = tmp_path / "review"
    review.mkdir()
    cache = tmp_path / "cache"
    (cache / "review").mkdir(parents=True)
    (review / "busy_besttime_requests.yaml").write_text(REQUESTS)
    (review / "busy_besttime_venues.csv").write_text(
        VENUES
        + "".join(
            f"SYN-place-{i},cafe,data-reviewer,2026-11-16\n" for i in range(count)
        )
    )
    (cache / "review/venue_busyness_crosswalk.csv").write_text(
        CROSSWALK
        + "".join(
            f"SYN-place-{i},SYN-venue-a,data-reviewer,2026-11-16,matched\n"
            for i in range(count)
        )
    )
    (cache / "places_s2_t06").mkdir()
    (cache / "places_s2_t06/pub_place.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "place_id": f"SYN-place-{i}",
                    "name": "Invented cafe",
                    "source_release": "2026-10-21.0",
                }
            )
            + "\n"
            for i in range(count)
        )
    )
    if address_cache:
        write_addresses(cache, count)
    env = {
        "BESTTIME_API_KEY_PRIVATE": "SYN-invented-private",
        "BESTTIME_API_KEY_PUBLIC": "SYN-invented-public",
        "EII_BESTTIME_RUN_CREDIT_LIMIT": "30",
    }
    entry = next(row for row in load_registry() if row.source_id == "busy_besttime")
    return entry, review, cache, env


def write_addresses(cache, count=1, addresses=None, identifier=None, *, extra_rows=()):
    import tempfile
    from dataclasses import replace
    from pathlib import Path

    import duckdb

    from eii_custodian.publicdata.places.fetch import FILE_KEYS
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    values = (
        addresses
        if addresses is not None
        else [
            {
                "freeform": "Invented street",
                "locality": "Invented town",
                "postcode": "Invented postal",
                "region": "Invented region",
                "country": "Invented country",
            }
        ]
    )
    with tempfile.TemporaryDirectory(dir=cache.parent) as folder:
        path = Path(folder) / "invented.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(
                "CREATE TABLE places (id VARCHAR, addresses STRUCT(freeform VARCHAR, locality VARCHAR, postcode VARCHAR, region VARCHAR, country VARCHAR)[])"
            )
            for i in range(count):
                connection.execute(
                    "INSERT INTO places VALUES (?, ?)",
                    [identifier or f"SYN-place-{i}", values],
                )
            for row in extra_rows:
                connection.execute("INSERT INTO places VALUES (?, ?)", row)
            connection.execute("COPY places TO ? (FORMAT PARQUET)", [str(path)])
        finally:
            connection.close()
        body = path.read_bytes()
    entry = next(row for row in load_registry() if row.key == FILE_KEYS[0])
    return write_cached(
        cache,
        replace(entry, publisher="Invented publisher"),
        body,
        retrieved_utc="2026-11-16T00:00:00Z",
    )


def run(entry, review, cache, env, answers=None):
    calls = []
    answers = [forecast(), query()] if answers is None else answers

    def transport(request):
        assert isinstance(request, KeyedRequest)
        calls.append(str(request))
        return Response(
            str(request), encode(answers[(len(calls) - 1) % len(answers)]), ()
        )

    digest = build_busyness(
        entry, transport, cache, lambda: "2026-11-16T00:00:00Z", env, review
    )
    manifest = json.loads((cache / "busy_besttime/manifest.json").read_text())
    body = cache / "busy_besttime" / (manifest["table_sha256"] + ".jsonl")
    return (
        calls,
        [json.loads(line) for line in body.read_text().splitlines()],
        manifest,
        digest,
    )


def test_besttime_build_rows_metadata_and_receipt(tmp_path):
    entry, review, cache, env = setup(tmp_path)
    calls, rows, manifest, digest = run(entry, review, cache, env)
    assert len(calls) == 2
    assert len(rows) == 168
    assert set(rows[0]) == {
        "place_id",
        "day_of_week",
        "hour",
        "busyness_index",
        "retrieved_on",
        "provider_updated_on",
        "source_id",
    }
    assert rows[0] == {
        "place_id": "SYN-place-0",
        "day_of_week": "monday",
        "hour": 6,
        "busyness_index": 0,
        "retrieved_on": "2026-11-16",
        "provider_updated_on": "2026-10-01",
        "source_id": "busy_besttime",
    }
    assert rows[18]["day_of_week"] == "monday" and rows[18]["hour"] == 0
    assert manifest["credits_used"] == 3
    assert len(manifest["answers"]) == 2
    assert all(len(a["sha256"]) == 64 for a in manifest["answers"])
    assert manifest["fact"] == {
        "provenance": "Public",
        "subject_type": "place_public",
        "evidence_status": "Observed",
        "unit": "relative_index",
        "label": "BestTime relative busyness",
        "caveat_key": "relative_busyness_not_people",
        "period_field": "retrieved_on",
        "update_field": "provider_updated_on",
        "missing_update_label": "update date not stated",
    }
    assert len(digest) == 64
    for path in cache.rglob("*"):
        if path.is_file() and "busy_besttime" in path.parts:
            text = path.read_text()
            assert "SYN-invented" not in text
            assert "Invented cafe" not in text
            assert "Invented address" not in text


@pytest.mark.parametrize(
    "variable",
    [
        "BESTTIME_API_KEY_PRIVATE",
        "BESTTIME_API_KEY_PUBLIC",
        "EII_BESTTIME_RUN_CREDIT_LIMIT",
    ],
)
def test_besttime_missing_environment_before_request(tmp_path, variable):
    entry, review, cache, env = setup(tmp_path)
    del env[variable]
    with pytest.raises(ValueError, match=variable):
        build_busyness(
            entry,
            lambda req: pytest.fail("request sent"),
            cache,
            lambda: "unused",
            env,
            review,
        )


@pytest.mark.parametrize("kind", ["place", "crosswalk", "cost"])
def test_besttime_review_preconditions_before_request(tmp_path, kind):
    entry, review, cache, env = setup(tmp_path)
    if kind == "place":
        (cache / "places_s2_t06/pub_place.jsonl").write_text("")
    elif kind == "crosswalk":
        (cache / "review/venue_busyness_crosswalk.csv").write_text(CROSSWALK)
    else:
        (review / "busy_besttime_requests.yaml").write_text(
            REQUESTS.replace("forecast_credits: 2", "forecast_credits:")
        )
    with pytest.raises(ValueError):
        build_busyness(
            entry,
            lambda req: pytest.fail("request sent"),
            cache,
            lambda: "unused",
            env,
            review,
        )


@pytest.mark.parametrize("count,meets", [(2, False), (3, True), (0, False)])
def test_besttime_coverage_and_empty_list(tmp_path, count, meets):
    entry, review, cache, env = setup(tmp_path, count)
    calls, rows, manifest, _ = run(entry, review, cache, env)
    assert len(calls) == count * 2
    assert len(rows) == count * 168
    assert manifest["coverage"]["asked"] == count
    assert manifest["coverage"]["with_figure"] == count
    if count:
        assert manifest["coverage"]["categories"]["cafe"]["reaches_minimum"] is meets
    else:
        assert manifest["coverage"]["categories"] == {}


@pytest.mark.parametrize(
    "limit,calls,rows", [(1, 0, 0), (2, 1, 168), (3, 2, 168), (4, 2, 168)]
)
def test_besttime_limit_stops_all_requests_and_receipt(tmp_path, limit, calls, rows):
    entry, review, cache, env = setup(tmp_path, 2)
    env["EII_BESTTIME_RUN_CREDIT_LIMIT"] = str(limit)
    seen, result, manifest, _ = run(entry, review, cache, env)
    assert len(seen) == calls
    assert len(result) == rows
    assert manifest["credits_used"] == (0 if calls == 0 else 2 if calls == 1 else 3)
    if calls == 1:
        assert result[0]["provider_updated_on"] is None


@pytest.mark.parametrize("kind", ["no_forecast", "not_found", "name", "id", "no_match"])
def test_besttime_no_figure_or_wrong_match_never_filled(tmp_path, kind):
    entry, review, cache, env = setup(tmp_path)
    value = forecast()
    if kind in {"no_forecast", "not_found"}:
        value = {
            "status": "Error",
            "venue_info": {"venue_id": "SYN-venue-a"} if kind == "no_forecast" else {},
        }
    elif kind == "name":
        value["venue_info"]["venue_name"] = "Other invented place"
    elif kind == "id":
        value["venue_info"]["venue_id"] = "SYN-other"
    else:
        path = cache / "review/venue_busyness_crosswalk.csv"
        path.write_text(path.read_text().replace(",matched", ",no_match"))
    _, rows, manifest, _ = run(entry, review, cache, env, [value])
    assert rows == []
    assert manifest["coverage"]["with_figure"] == 0
    assert manifest["coverage"]["reasons"]["SYN-place-0"] == (
        kind if kind in {"no_forecast", "not_found"} else "no_match"
    )


def test_besttime_changed_shape_loads_nothing(tmp_path):
    entry, review, cache, env = setup(tmp_path)
    broken = query()
    broken["analysis"]["week_raw"][0] = 101
    with pytest.raises(
        ValueError,
        match=r"busy_besttime https://besttime\.app/api/v1/forecasts/week/raw",
    ):
        run(entry, review, cache, env, [forecast(), broken])
    assert not (cache / "busy_besttime").exists()


def test_besttime_empty_list_without_credentials_or_costs(tmp_path):
    entry, review, cache, _env = setup(tmp_path, 0)
    (review / "busy_besttime_requests.yaml").unlink()
    calls, rows, manifest, _ = run(entry, review, cache, {})
    assert calls == [] and rows == []
    assert manifest["credits_used"] == 0


def test_besttime_dispatch_passes_environment(tmp_path, monkeypatch):
    from custodian.tests.support.fetch_build import run_build as support_run_build

    from eii_custodian.publicdata.busyness import build as busy

    entry, _review, cache, env = setup(tmp_path)
    seen = []

    def reader(entry_arg, transport, cache_arg, clock, environ):
        seen.append((entry_arg, cache_arg, environ))
        return "invented-digest"

    monkeypatch.setattr(busy, "build_busyness", reader)
    outcome = support_run_build(
        (entry,),
        lambda req: pytest.fail("generic transport"),
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda delay: None,
        environ=env,
    )
    assert outcome.failure is None
    assert seen == [(entry, cache, env)]


def test_besttime_kind_cannot_fall_through_to_generic_get():
    from eii_custodian.publicdata.fetch.kinds import prepare

    entry = next(row for row in load_registry() if row.source_id == "busy_besttime")
    result = prepare(
        entry, lambda req: pytest.fail("generic request"), lambda delay: None
    )
    assert result.failure is not None
    assert result.failure.check == "build_context_required"


@pytest.mark.parametrize("failure", ["hops", "final", "exception"])
def test_besttime_failed_transport_no_retry_or_load(tmp_path, failure):
    import traceback

    entry, review, cache, env = setup(tmp_path)
    seen = []

    def transport(req):
        seen.append(str(req))
        if failure == "exception":
            raise ValueError(env["BESTTIME_API_KEY_PRIVATE"])
        return Response(
            "https://evil.example/path" if failure == "final" else str(req),
            encode(forecast()),
            ("https://evil.example/path",) if failure == "hops" else (),
        )

    with pytest.raises(ValueError, match="request_failed") as caught:
        build_busyness(
            entry, transport, cache, lambda: "2026-11-16T00:00:00Z", env, review
        )
    assert len(seen) == 1
    assert caught.value.__context__ is None
    assert env["BESTTIME_API_KEY_PRIVATE"] not in "".join(
        traceback.format_exception(caught.value)
    )
    assert not (cache / "busy_besttime").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://evil.example"),
        ("commit_allowed", True),
        ("licence_basis", "owner_decision"),
    ],
)
def test_besttime_registry_guards_before_request(tmp_path, field, value):
    from dataclasses import replace

    entry, review, cache, env = setup(tmp_path)
    entry = replace(entry, **{field: value})
    with pytest.raises(ValueError):
        build_busyness(
            entry, lambda req: pytest.fail("sent"), cache, lambda: "unused", env, review
        )


def test_besttime_pending_terms_words_still_build(tmp_path):
    """Ruling L-1001: pending terms words never refuse the busyness build."""
    from dataclasses import replace

    entry, review, cache, env = setup(tmp_path)
    entry = replace(entry, terms_words="")
    calls, rows, manifest, _digest = run(entry, review, cache, env)
    assert calls
    assert rows
    assert manifest["source"]["terms_words"] == ""


@pytest.mark.parametrize("field", ["name"])
def test_besttime_blank_place_field_refused(tmp_path, field):
    entry, review, cache, env = setup(tmp_path)
    path = cache / "places_s2_t06/pub_place.jsonl"
    row = json.loads(path.read_text())
    row[field] = " "
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match=field):
        build_busyness(
            entry, lambda req: pytest.fail("sent"), cache, lambda: "unused", env, review
        )


def test_besttime_empty_list_needs_no_place_or_crosswalk_file(tmp_path):
    entry, review, cache, _env = setup(tmp_path, 0)
    (cache / "review/venue_busyness_crosswalk.csv").unlink()
    (cache / "places_s2_t06/pub_place.jsonl").unlink()
    assert run(entry, review, cache, {})[2]["coverage"]["asked"] == 0


@pytest.mark.parametrize("found", [True, False])
def test_besttime_reason_totals_and_sidecar_credit_total(tmp_path, found):
    entry, review, cache, env = setup(tmp_path)
    _, _, manifest, _ = run(
        entry,
        review,
        cache,
        env,
        [
            {
                "status": "Error",
                "venue_info": {"venue_id": "SYN-venue-a"} if found else {},
            }
        ],
    )
    assert manifest["coverage"]["without_figure"] == int(found)
    assert manifest["coverage"]["not_found"] == int(not found)
    assert manifest["source"]["credits_used"] == 2
    side = next((cache / "busy_besttime").glob("*.meta.json"))
    assert json.loads(side.read_text())["credits_used"] == 2


def test_besttime_build_failure_names_missing_place(tmp_path, monkeypatch):
    from custodian.tests.support.fetch_build import run_build as support_run_build

    from eii_custodian.publicdata.busyness import build as busy

    entry, review, cache, env = setup(tmp_path)
    (cache / "places_s2_t06/pub_place.jsonl").write_text("")
    actual = busy.build_busyness
    monkeypatch.setattr(
        busy,
        "build_busyness",
        lambda entry, transport, cache, clock, environ: actual(
            entry, transport, cache, clock, environ, review
        ),
    )
    outcome = support_run_build(
        (entry,),
        lambda req: pytest.fail("sent"),
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda delay: None,
        environ=env,
    )
    assert outcome.failure is not None
    assert "SYN-place-0" in outcome.failure.detail
    assert "busy_besttime" in outcome.failure.detail


def test_besttime_command_environment_reaches_build(tmp_path, monkeypatch):
    from custodian.tests.method_pin_config_fixture import stage_tracked_configuration

    stage_tracked_configuration(tmp_path)

    import commands.build_public as build_public
    from eii_custodian.publicdata.fetch.build import BuildOutcome

    seen = []

    def build(entries, transport, cache, clock, sleep, *, environ, **kwargs):
        seen.append(environ)
        return BuildOutcome((), None)

    monkeypatch.setattr(build_public, "run_build", build)
    environ = {"EII_BESTTIME_RUN_CREDIT_LIMIT": "3"}
    assert (
        build_public.run(
            tmp_path, environ, (), transport=lambda req: pytest.fail("sent")
        )
        == 0
    )
    assert seen == [environ]


def test_besttime_all_days_and_values_stay_on_own_venue(tmp_path):
    entry, review, cache, env = setup(tmp_path, 2)
    first = forecast()
    second = forecast()
    second["analysis"][0]["day_raw"][0] = 100
    stored = query()
    stored["analysis"]["week_raw"][0] = 100
    _, rows, _, _ = run(entry, review, cache, env, [first, query(), second, stored])
    assert {row["day_of_week"] for row in rows} == {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
    assert [rows[i * 24]["day_of_week"] for i in range(7)] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    assert rows[0]["busyness_index"] == 0
    assert rows[168]["busyness_index"] == 100
    assert rows[168]["place_id"] == "SYN-place-1"


def test_besttime_missing_keys_failure_log_is_key_free(tmp_path, monkeypatch):
    from custodian.tests.support.fetch_build import run_build as support_run_build

    from eii_custodian.publicdata.busyness import build as busy

    entry, review, cache, env = setup(tmp_path)
    del env["BESTTIME_API_KEY_PRIVATE"]
    actual = busy.build_busyness
    monkeypatch.setattr(
        busy,
        "build_busyness",
        lambda entry, transport, cache, clock, environ: actual(
            entry, transport, cache, clock, environ, review
        ),
    )
    outcome = support_run_build(
        (entry,),
        lambda req: pytest.fail("sent"),
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda delay: None,
        environ=env,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "BESTTIME_API_KEY_PRIVATE"
    assert "api_key_public=" not in (cache / "build-log.json").read_text()


def test_besttime_input_secret_is_not_logged(tmp_path, monkeypatch):
    from custodian.tests.support.fetch_build import run_build as support_run_build

    from eii_custodian.publicdata.busyness import build as busy

    entry, _review, cache, env = setup(tmp_path)

    def refuse(*args):
        raise busy.BuildInputError(env["BESTTIME_API_KEY_PRIVATE"])

    monkeypatch.setattr(busy, "build_busyness", refuse)
    outcome = support_run_build(
        (entry,),
        lambda req: pytest.fail("sent"),
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda delay: None,
        environ=env,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "secret_in_input"
    assert env["BESTTIME_API_KEY_PRIVATE"] not in (cache / "build-log.json").read_text()


@pytest.mark.parametrize("kind", ["not_overture", "absent_record", "empty_entry"])
def test_besttime_address_absent_not_asked_and_other_venue_unaffected(tmp_path, kind):
    entry, review, cache, env = setup(tmp_path, 2)
    path = cache / "places_s2_t06/pub_place.jsonl"
    places = [json.loads(line) for line in path.read_text().splitlines()]
    if kind == "not_overture":
        places[0]["source_release"] = "invented-other-release"
    elif kind == "absent_record":
        places[0]["place_id"] = "SYN-place-absent"
        for file in (
            review / "busy_besttime_venues.csv",
            cache / "review/venue_busyness_crosswalk.csv",
        ):
            file.write_text(file.read_text().replace("SYN-place-0", "SYN-place-absent"))
    else:
        # Assemble both invented venues before publishing the immutable snapshot.
        write_addresses(
            cache,
            1,
            [{"freeform": "", "locality": "", "country": "Invented country"}],
            "SYN-place-0",
            extra_rows=(
                (
                    "SYN-place-1",
                    [
                        {
                            "freeform": "Invented street",
                            "locality": None,
                            "postcode": None,
                            "region": None,
                            "country": None,
                        }
                    ],
                ),
            ),
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in places))
    calls, rows, manifest, _ = run(entry, review, cache, env)
    assert len(calls) == 2
    assert {row["place_id"] for row in rows} == {"SYN-place-1"}
    assert manifest["coverage"]["asked"] == 1
    assert manifest["coverage"]["not_asked"] == 1
    assert manifest["coverage"]["reasons"] == {
        places[0]["place_id"]: "venue_address_absent"
    }


def test_besttime_address_receipt_checked_before_parquet(tmp_path, monkeypatch):
    from eii_custodian.publicdata.places import read
    from eii_custodian.publicdata.places.fetch import FILE_KEYS
    from eii_custodian.publicdata.places.integrate import _opened_place

    entry, review, cache, env = setup(tmp_path)
    source, _receipt = _opened_place(cache, FILE_KEYS[0])
    source.write_bytes(b"invented corrupt file")
    monkeypatch.setattr(
        read, "_connect", lambda: pytest.fail("parquet opened before receipt")
    )
    with pytest.raises(ValueError, match="places_file_digest"):
        build_busyness(
            entry, lambda req: pytest.fail("sent"), cache, lambda: "unused", env, review
        )
    assert not (cache / "busy_besttime").exists()


@pytest.mark.parametrize(
    "parts, expected",
    [
        (
            [
                {
                    "freeform": "Invented street",
                    "locality": "Invented town",
                    "country": "Invented country",
                },
                {"freeform": "Invented ignored"},
            ],
            "Invented street, Invented town, Invented country",
        ),
        (
            [{"freeform": None, "locality": "Invented town", "country": ""}],
            "Invented town",
        ),
        (
            [{"freeform": "Invented street", "locality": "", "country": None}],
            "Invented street",
        ),
    ],
)
def test_besttime_composed_address_transport_only(tmp_path, parts, expected):
    entry, review, cache, env = setup(tmp_path)
    write_addresses(cache, addresses=parts)
    before = {p: p.read_bytes() for p in cache.rglob("*") if p.is_file()}
    calls = []

    def transport(request):
        calls.append(request)
        if len(calls) == 1:
            assert request.parameters == {
                "venue_name": "Invented cafe",
                "venue_address": expected,
            }
        return Response(
            str(request), encode(forecast() if len(calls) == 1 else query()), ()
        )

    build_busyness(entry, transport, cache, lambda: "2026-11-16T00:00:00Z", env, review)
    assert len(calls) == 2
    for path in cache.rglob("*"):
        if path.is_file() and path not in before:
            assert b"Invented street" not in path.read_bytes()
            assert b"Invented town" not in path.read_bytes()
            assert b"Invented country" not in path.read_bytes()
    assert all(path.read_bytes() == body for path, body in before.items())


@pytest.mark.parametrize(
    "addresses",
    [
        [],
        [None],
        [
            {"freeform": "", "locality": "", "country": ""},
            {"freeform": "Invented ignored", "locality": "", "country": ""},
        ],
    ],
)
def test_besttime_empty_first_address_not_asked(tmp_path, addresses):
    entry, review, cache, env = setup(tmp_path)
    write_addresses(cache, addresses=addresses if addresses is not None else [])
    calls, rows, manifest, _ = run(entry, review, cache, env, [])
    assert calls == []
    assert rows == []
    assert manifest["coverage"]["asked"] == 0
    assert manifest["coverage"]["not_asked"] == 1
    assert manifest["coverage"]["reasons"] == {"SYN-place-0": "venue_address_absent"}


def test_besttime_no_overture_cache_not_asked(tmp_path):
    entry, review, cache, env = setup(tmp_path, address_cache=False)
    calls, rows, manifest, _ = run(entry, review, cache, env, [])
    assert calls == [] and rows == []
    assert manifest["coverage"]["reasons"] == {"SYN-place-0": "venue_address_absent"}


def test_besttime_incomplete_address_receipt_before_parquet(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import (
        read_snapshot,
        reviewed_selections,
    )
    from eii_custodian.publicdata.places import PlacesError, read
    from eii_custodian.publicdata.places.fetch import FILE_KEYS

    entry, review, cache, env = setup(tmp_path)
    directory = cache / FILE_KEYS[0]
    digest = reviewed_selections(cache)[FILE_KEYS[0]]
    meta = read_snapshot(directory, digest).receipt_path
    receipt = json.loads(meta.read_text())
    receipt["publisher"] = ""
    meta.write_text(json.dumps(receipt))
    # Keep the archive envelope consistent so the missing-publisher plant reaches
    # the original receipt completeness check before any Parquet read.
    index = directory / "index" / (digest + ".json")
    row = json.loads(index.read_text())
    row["receipt_sha256"] = sha256_hex(meta.read_bytes())
    index.write_text(json.dumps(row))
    monkeypatch.setattr(read, "_connect", lambda: pytest.fail("parquet opened"))
    with pytest.raises(PlacesError, match="receipt_missing"):
        build_busyness(
            entry, lambda req: pytest.fail("sent"), cache, lambda: "unused", env, review
        )


def test_besttime_empty_venue_list_never_reads_address_cache(tmp_path):
    from eii_custodian.publicdata.places.fetch import FILE_KEYS
    from eii_custodian.publicdata.places.integrate import _opened_place

    entry, review, cache, env = setup(tmp_path, 0)
    source, _receipt = _opened_place(cache, FILE_KEYS[0])
    source.write_bytes(b"invented corrupt file")
    calls, rows, manifest, _ = run(entry, review, cache, env, [])
    assert calls == [] and rows == []
    assert manifest["coverage"]["asked"] == 0
    assert manifest["coverage"]["not_asked"] == 0
