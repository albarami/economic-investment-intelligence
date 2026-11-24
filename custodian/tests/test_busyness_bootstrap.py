"""S2-P79: invented bootstrap identities, no provider access."""

import json
from dataclasses import replace

import pytest
from custodian.tests.support.payload_leaves import leaves, replace_leaf
from custodian.tests.test_publicdata_besttime_build import setup
from custodian.tests.test_publicdata_besttime_parse import encode, forecast
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.busyness import build, review
from eii_custodian.publicdata.fetch.transport import Response

STAMP = "2026-11-16T00:00:00Z"


@pytest.fixture(autouse=True)
def invented_hosts(monkeypatch):
    from eii_custodian.publicdata.busyness import parse

    for module in (build, parse):
        monkeypatch.setattr(
            module, "FORECAST_URL", "https://provider.invalid/forecasts"
        )
        monkeypatch.setattr(
            module, "QUERY_URL", "https://provider.invalid/forecasts/week/raw"
        )


def pending(tmp_path, count=1):
    entry, reviews, cache, env = setup(tmp_path, count)
    path = cache / "review" / review.CROSSWALK_FILE
    path.write_text(
        path.read_text().replace("SYN-venue-a,", ",").replace(",matched", ",pending")
    )
    return replace(entry, url=build.FORECAST_URL), reviews, cache, env


def acquire(tmp_path, *, answer=None, limit="30", count=1):
    entry, reviews, cache, env = pending(tmp_path, count)
    env["EII_BESTTIME_RUN_CREDIT_LIMIT"] = limit
    seen = []

    def transport(request):
        seen.append(str(request))
        return Response(
            str(request), encode(forecast() if answer is None else answer), ()
        )

    digest = build.build_busyness(
        entry, transport, cache, lambda: STAMP, env, reviews, bootstrap=True
    )
    return cache, env, seen, digest


def test_busyness_pending_is_closed_and_unknown(tmp_path):
    _, _, cache, _ = pending(tmp_path)
    assert (
        review.load_crosswalk(cache / "review" / review.CROSSWALK_FILE)[0]["match"]
        == "pending"
    )


def test_busyness_bootstrap_minimal_handoff_no_publication(tmp_path):
    cache, env, seen, digest = acquire(tmp_path)
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE

    rows = json.loads((cache / HANDOFF_FILE).read_text())
    assert rows == [
        {
            "place_id": "SYN-place-0",
            "venue_id": "SYN-venue-a",
            "venue_name": "Invented cafe",
            "sha256": build.sha256_hex(encode(forecast())),
            "retrieved_utc": STAMP,
        }
    ]
    assert len(seen) == 1
    assert len(digest) == 64
    assert not (cache / "busy_besttime/manifest.json").exists()
    assert not list((cache / "busy_besttime").glob("*.jsonl"))
    report = json.loads((cache / "busy_besttime/bootstrap-run.json").read_text())
    assert report["credits_used"] == 2
    assert report["coverage"]["with_figure"] == 0
    for path in (cache / "busy_besttime").rglob("*"):
        if path.is_file():
            assert "analysis" not in path.read_text()
            assert all(
                value not in path.read_text()
                for key, value in env.items()
                if "API_KEY" in key
            )


def test_busyness_pending_ordinary_build_sends_nothing(tmp_path):
    entry, reviews, cache, env = pending(tmp_path)
    build.build_busyness(
        entry, lambda request: pytest.fail("sent"), cache, lambda: STAMP, env, reviews
    )
    manifest = json.loads((cache / "busy_besttime/manifest.json").read_text())
    assert manifest["coverage"]["reasons"] == {"SYN-place-0": "no_match"}


def test_busyness_bootstrap_missing_identity(tmp_path):
    answer = forecast()
    answer["venue_info"]["venue_id"] = ""
    with pytest.raises(ValueError, match="changed_shape"):
        acquire(tmp_path, answer=answer)


def test_busyness_bootstrap_false_match_cannot_confirm(tmp_path):
    answer = forecast()
    answer["venue_info"]["venue_name"] = "Other invented venue"
    cache, env, _, _ = acquire(tmp_path, answer=answer)
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE, confirm_handoff

    path = cache / "review" / review.CROSSWALK_FILE
    before = path.read_bytes()
    digest = build.sha256_hex((cache / HANDOFF_FILE).read_bytes())
    with pytest.raises(ValueError, match="handoff_name_mismatch"):
        confirm_handoff(cache, digest, "lead-reviewer", "2026-11-16", env)
    assert path.read_bytes() == before


def test_busyness_confirmed_handoff_changes_cache_only(tmp_path):
    cache, env, _, _ = acquire(tmp_path)
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE, confirm_handoff

    digest = build.sha256_hex((cache / HANDOFF_FILE).read_bytes())
    confirm_handoff(cache, digest, "lead-reviewer", "2026-11-16", env)
    row = review.load_crosswalk(cache / "review" / review.CROSSWALK_FILE)[0]
    assert row == {
        "place_id": "SYN-place-0",
        "venue_key": "SYN-venue-a",
        "reviewer_role": "lead-reviewer",
        "reviewed_on": "2026-11-16",
        "match": "matched",
    }


def test_busyness_bootstrap_over_cap(tmp_path):
    cache, _, seen, _ = acquire(tmp_path, limit="3", count=2)
    report = json.loads((cache / "busy_besttime/bootstrap-run.json").read_text())
    assert len(seen) == 1
    assert report["credits_used"] == 2
    assert report["coverage"]["reasons"]["SYN-place-1"] == "credit_limit"


def candidate():
    return {
        "place_id": "SYN-place-0",
        "venue_id": "SYN-venue-a",
        "venue_name": "Invented cafe",
        "sha256": "a" * 64,
        "retrieved_utc": STAMP,
    }


@pytest.mark.parametrize(
    "kind,code",
    [
        ("root", "handoff_schema"),
        ("row", "handoff_schema"),
        ("extra", "handoff_schema"),
        ("missing", "handoff_schema"),
        ("type", "handoff_schema"),
        ("blank", "handoff_schema"),
        ("duplicate", "handoff_duplicate"),
        ("digest", "handoff_digest"),
        ("time", "handoff_time"),
    ],
)
def test_busyness_handoff_refusals(tmp_path, kind, code):
    from eii_custodian.publicdata.busyness.handoff import write_handoff

    rows = [candidate()]
    if kind == "root":
        rows = {}
    elif kind == "row":
        rows = [7]
    elif kind == "extra":
        rows[0]["analysis"] = forecast()["analysis"]
    elif kind == "missing":
        del rows[0]["venue_id"]
    elif kind == "type":
        rows[0]["venue_id"] = []
    elif kind == "blank":
        rows[0]["venue_id"] = " "
    elif kind == "duplicate":
        rows.append(candidate())
    elif kind == "digest":
        rows[0]["sha256"] = "invalid"
    elif kind == "time":
        rows[0]["retrieved_utc"] = "2026-11-16"
    with pytest.raises(ValueError, match=f"^{code}$"):
        write_handoff(tmp_path, rows, {})
    assert not (tmp_path / "busy_besttime").exists()


@pytest.mark.parametrize("field", ["venue_id", "venue_name"])
def test_busyness_handoff_secret_never_written(tmp_path, field):
    from eii_custodian.publicdata.busyness.handoff import write_handoff

    row = candidate()
    row[field] = "SYN-secret-marker"
    with pytest.raises(ValueError, match=r"secret_in_output$"):
        write_handoff(
            tmp_path, [row], {"BESTTIME_API_KEY_PRIVATE": "SYN-secret-marker"}
        )
    assert not (tmp_path / "busy_besttime").exists()


@pytest.mark.parametrize("alias", ["directory", "file", "partial"])
def test_busyness_cache_alias_refused(tmp_path, alias):
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE, write_handoff

    other = tmp_path / "other"
    other.mkdir()
    if alias == "directory":
        (tmp_path / "busy_besttime").symlink_to(other, target_is_directory=True)
    else:
        (tmp_path / "busy_besttime").mkdir()
        target = tmp_path / (HANDOFF_FILE + (".partial" if alias == "partial" else ""))
        target.symlink_to(other / "original")
    with pytest.raises(ValueError, match=r"^handoff_cache_alias$"):
        write_handoff(tmp_path, [candidate()], {})
    assert list(other.iterdir()) == []


@pytest.mark.parametrize(
    "kind,code",
    [
        ("hash", "handoff_changed"),
        ("reviewer", "handoff_reviewer"),
        ("date", "handoff reviewed_on: expected ISO date text"),
        ("source", "handoff_inputs_changed"),
        ("report_hash", "handoff_inputs_changed"),
        ("not_pending", "handoff_not_pending"),
        ("unknown_place", "handoff_not_pending"),
        ("report_root", "handoff_inputs_changed"),
    ],
)
def test_busyness_confirmation_refusals(tmp_path, kind, code):
    from eii_custodian.publicdata.busyness.handoff import (
        HANDOFF_FILE,
        confirm_handoff,
        input_hashes,
    )

    cache, env, _, _ = acquire(tmp_path)
    path = cache / "review" / review.CROSSWALK_FILE
    report_path = cache / "busy_besttime/bootstrap-run.json"
    report = json.loads(report_path.read_text())
    digest = build.sha256_hex((cache / HANDOFF_FILE).read_bytes())
    role, date = "lead-reviewer", "2026-11-16"
    if kind == "hash":
        digest = "b" * 64
    elif kind == "reviewer":
        role = " "
    elif kind == "date":
        date = "2026-02-30"
    elif kind == "source":
        (cache / "places_s2_t06/pub_place.jsonl").write_text("changed")
    elif kind == "report_hash":
        report["handoff_sha256"] = "b" * 64
    elif kind in {"not_pending", "unknown_place"}:
        path.write_text(
            path.read_text()
            .replace(",pending", ",no_match")
            .replace("SYN-place-0,,", "SYN-place-0,SYN-venue-a,")
            if kind == "not_pending"
            else path.read_text().replace("SYN-place-0", "SYN-place-other")
        )
        report["inputs"] = input_hashes(cache)
    elif kind == "report_root":
        report = []
    report_path.write_text(json.dumps(report))
    before = path.read_bytes()
    with pytest.raises(ValueError, match=f"^{code}$"):
        confirm_handoff(cache, digest, role, date, env)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["forecast", "query"])
def test_busyness_second_request_each_kind_refused(kind):
    from eii_custodian.publicdata.busyness.policy import CreditBudget

    budget = CreditBudget(10)
    budget.reserve("SYN-a", "forecast", 2)
    if kind == "query":
        budget.reserve("SYN-a", "query", 1)
    with pytest.raises(ValueError, match=r"^duplicate request$"):
        budget.reserve("SYN-a", kind, 1)


@pytest.mark.parametrize(
    "key,state", [("SYN-fake", "pending"), ("", "matched"), (" ", "no_match")]
)
def test_busyness_pending_identity_pair_closed(tmp_path, key, state):
    from custodian.tests.test_publicdata_besttime_review import CROSSWALK

    path = tmp_path / "crosswalk.csv"
    path.write_text(CROSSWALK + f"SYN-a,{key},lead-reviewer,2026-11-16,{state}\n")
    with pytest.raises(ValueError, match=r"venue_key: empty only for pending$"):
        review.load_crosswalk(path)


@pytest.mark.parametrize("field", ["venue_id", "venue_name"])
@pytest.mark.parametrize("value", ["", " "])
def test_busyness_empty_identity_refused(field, value):
    from eii_custodian.publicdata.busyness.parse import parse_forecast

    answer = forecast()
    answer["venue_info"][field] = value
    with pytest.raises(ValueError, match=r"changed_shape$"):
        parse_forecast(encode(answer))


def test_busyness_fingerprint_binds_selection_and_handoff(tmp_path, monkeypatch):
    from custodian.tests.test_fetch_fingerprint import _stub_roots

    from eii_custodian.publicdata.fetch.fingerprint import scan_run
    from eii_custodian.publicdata.fetch.resume import RunRecord

    entry, _, cache, _ = pending(tmp_path)
    roots = _stub_roots(
        tmp_path,
        monkeypatch,
        brancher=lambda e, large: "besttime",
        branch_roots={"besttime": ("syn_adapter_a",)},
    )
    scan = scan_run([entry], roots, large=False, cache=cache)
    first = scan.records[entry.key]
    assert first is not None
    run = RunRecord(cache, {}, True, scan=scan)
    assert run._fingerprint(entry)[1] is None
    assert run._fingerprint_matches(entry, {"fingerprint": first})
    bootstrap = scan_run(
        [entry], roots, large=False, cache=cache, busyness_phase="bootstrap"
    )
    assert bootstrap.records[entry.key] != first
    (cache / "busy_besttime").mkdir()
    (cache / "busy_besttime/identity-handoff.json").write_text("[]")
    second = scan_run([entry], roots, large=False, cache=cache)
    assert second.records[entry.key] != first
    run = RunRecord(cache, {}, True, scan=scan)
    assert not run._fingerprint_matches(entry, {"fingerprint": first})
    assert run._fingerprint(entry)[1] == "resume_fingerprint_unproven"
    unbound = scan_run([entry], roots, large=False)
    assert unbound.records[entry.key] is None


def test_busyness_bootstrap_command_explicit_only(tmp_path, monkeypatch, capsys):
    import commands.build_public as command

    entry, reviews, cache, env = pending(tmp_path)
    # Place this invented cache on the command's fixed cache path.
    monkeypatch.setattr(command, "CACHE_RELATIVE", "cache")
    monkeypatch.setattr(command, "load_registry", lambda: (entry,))
    actual = build.build_busyness
    calls = []

    def reader(*args, **kwargs):
        calls.append(kwargs.get("bootstrap", False))
        return actual(*args, review=reviews, **kwargs)

    monkeypatch.setattr(build, "build_busyness", reader)

    def transport(request):
        return Response(str(request), encode(forecast()), ())

    assert (
        command.run(tmp_path, env, ["--busyness-bootstrap"], transport=transport) == 0
    )
    assert calls == [True]
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE

    digest = build.sha256_hex((cache / HANDOFF_FILE).read_bytes())
    assert (
        command.run(
            tmp_path,
            env,
            ["--busyness-confirm", digest, "lead-reviewer", "2026-11-16"],
            transport=lambda req: pytest.fail("confirmation sent"),
        )
        == 0
    )
    assert "identity_confirmed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "args",
    [
        ["--busyness-bootstrap", "--resume"],
        ["--busyness-bootstrap", "--seed", "1"],
        ["--busyness-confirm"],
        ["--seed", "1", "--busyness-bootstrap"],
    ],
)
def test_busyness_bootstrap_bad_selection_refused_before_inputs(
    tmp_path, args, monkeypatch, capsys
):
    import commands.build_public as command

    monkeypatch.setattr(command, "load_registry", lambda: pytest.fail("registry read"))
    assert (
        command.run(tmp_path, {}, args, transport=lambda req: pytest.fail("sent")) == 2
    )
    assert "usage error" in capsys.readouterr().err


def test_busyness_exhaustive_hostile_payload_leaves():
    from custodian.tests.test_publicdata_besttime_parse import query

    from eii_custodian.publicdata.busyness.handoff import validate_handoff
    from eii_custodian.publicdata.busyness.parse import (
        ShapeError,
        parse_forecast,
        parse_query,
    )

    fixtures = [
        (forecast(), lambda value: parse_forecast(encode(value))),
        (
            query(),
            lambda value: parse_query(
                encode(value), parse_forecast(encode(forecast()))
            ),
        ),
        (
            {"status": "Error", "venue_info": {}},
            lambda value: parse_forecast(encode(value)),
        ),
        (
            {"status": "Error", "venue_info": {"venue_id": "SYN-a"}},
            lambda value: parse_forecast(encode(value)),
        ),
        ([candidate()], validate_handoff),
    ]
    for value, accept in fixtures:
        for path in leaves(value):
            for hostile in ({"toString": None}, 7, None, []):
                try:
                    accept(replace_leaf(value, path, hostile))
                except ShapeError as error:
                    assert str(error).endswith("changed_shape")
                except ValueError as error:
                    assert str(error) == "handoff_schema"


@given(
    limit=st.integers(min_value=1),
    costs=st.lists(st.integers(min_value=1), max_size=40),
)
def test_busyness_budget_property_stops_at_first_unaffordable_request(limit, costs):
    from eii_custodian.publicdata.busyness.policy import CreditBudget

    budget = CreditBudget(limit)
    accepted = []
    for index, cost in enumerate(costs):
        reserved = budget.reserve(f"SYN-{index}", "forecast", cost)
        if reserved:
            accepted.append(cost)
            assert sum(accepted) <= limit
        else:
            assert sum(accepted) + cost > limit or budget.stopped
            assert not budget.reserve(f"SYN-cheaper-{index}", "forecast", 1)
    assert budget.used == sum(accepted)
    assert len(budget.sent) == len(accepted)


@example(name="Invented " + "x" * 10000)
@given(name=st.text().map(lambda value: "Invented " + value))
def test_busyness_handoff_identity_roundtrip(name):
    from eii_custodian.publicdata.busyness.handoff import validate_handoff

    row = {**candidate(), "venue_name": name}
    assert validate_handoff(json.loads(json.dumps([row]))) == [row]


@pytest.mark.parametrize(
    "answer", [[], {"status": "OK"}, {"status": "Error", "venue_info": {}}]
)
def test_busyness_malformed_or_not_found_never_handed_off(tmp_path, answer):
    if answer == {"status": "Error", "venue_info": {}}:
        cache, _, seen, _ = acquire(tmp_path, answer=answer)
        report = json.loads((cache / "busy_besttime/bootstrap-run.json").read_text())
        assert report["coverage"]["reasons"] == {"SYN-place-0": "not_found"}
        assert (
            json.loads((cache / "busy_besttime/identity-handoff.json").read_text())
            == []
        )
        assert len(seen) == 1
    else:
        with pytest.raises(ValueError, match=r"changed_shape$"):
            acquire(tmp_path, answer=answer)


def test_busyness_bootstrap_sends_only_pending(tmp_path):
    entry, reviews, cache, env = setup(tmp_path)
    build.build_busyness(
        replace(entry, url=build.FORECAST_URL),
        lambda req: pytest.fail("matched venue sent"),
        cache,
        lambda: STAMP,
        env,
        reviews,
        bootstrap=True,
    )
    assert json.loads((cache / "busy_besttime/identity-handoff.json").read_text()) == []


def test_busyness_bootstrap_registry_inventory_refused(tmp_path, monkeypatch, capsys):
    import commands.build_public as command

    monkeypatch.setattr(command, "load_registry", lambda: ())
    assert (
        command.run(
            tmp_path,
            {},
            ["--busyness-bootstrap"],
            transport=lambda req: pytest.fail("sent"),
        )
        == 1
    )
    assert "busyness_phase_failed" in capsys.readouterr().err


def test_busyness_confirmation_reports_no_provider_text(tmp_path, capsys):
    import commands.build_public as command

    assert (
        command.run(
            tmp_path,
            {},
            ["--busyness-confirm", "a" * 64, "lead-reviewer", "2026-11-16"],
            transport=lambda req: pytest.fail("sent"),
        )
        == 1
    )
    assert "busyness_phase_failed" in capsys.readouterr().err


def test_busyness_duplicate_json_property_refused(tmp_path):
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE, confirm_handoff

    cache, env, _, _ = acquire(tmp_path)
    path = cache / HANDOFF_FILE
    path.write_text(
        path.read_text().replace('"place_id":', '"place_id":"SYN-fake", "place_id":')
    )
    with pytest.raises(ValueError, match=r"^handoff_schema$"):
        confirm_handoff(
            cache,
            build.sha256_hex(path.read_bytes()),
            "lead-reviewer",
            "2026-11-16",
            env,
        )


def test_busyness_missing_place_cannot_confirm(tmp_path):
    from eii_custodian.publicdata.busyness.handoff import (
        HANDOFF_FILE,
        confirm_handoff,
        input_hashes,
    )

    cache, env, _, _ = acquire(tmp_path)
    (cache / "places_s2_t06/pub_place.jsonl").write_text("")
    report_path = cache / "busy_besttime/bootstrap-run.json"
    report = json.loads(report_path.read_text())
    report["inputs"] = input_hashes(cache)
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match=r"^handoff_name_mismatch$"):
        confirm_handoff(
            cache,
            build.sha256_hex((cache / HANDOFF_FILE).read_bytes()),
            "lead-reviewer",
            "2026-11-16",
            env,
        )


def test_busyness_confirmation_secret_role_never_replaces(tmp_path):
    from eii_custodian.publicdata.busyness.handoff import HANDOFF_FILE, confirm_handoff

    cache, env, _, _ = acquire(tmp_path)
    path = cache / "review" / review.CROSSWALK_FILE
    original = path.read_bytes()
    with pytest.raises(ValueError, match=r"secret_in_output$"):
        confirm_handoff(
            cache,
            build.sha256_hex((cache / HANDOFF_FILE).read_bytes()),
            env["BESTTIME_API_KEY_PRIVATE"],
            "2026-11-16",
            env,
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize("body", [b"[", b"\xff"])
def test_busyness_unreadable_handoff_document_closed(body):
    from eii_custodian.publicdata.busyness.handoff import _document

    with pytest.raises(ValueError, match=r"^handoff_schema$"):
        _document(body)


def test_busyness_bootstrap_transport_failure_no_retry(tmp_path):
    entry, reviews, cache, env = pending(tmp_path)
    sent = []

    def transport(request):
        sent.append(str(request))
        raise OSError("invented failure")

    with pytest.raises(ValueError, match=r"request_failed$"):
        build.build_busyness(
            entry, transport, cache, lambda: STAMP, env, reviews, bootstrap=True
        )
    assert len(sent) == 1
    assert not (cache / "busy_besttime/identity-handoff.json").exists()


@pytest.mark.parametrize("kind", ["no_forecast", "no_match", "address"])
def test_busyness_bootstrap_withheld_reasons(tmp_path, kind):
    entry, reviews, cache, env = pending(tmp_path)
    answer = {"status": "Error", "venue_info": {"venue_id": "SYN-venue-a"}}
    if kind == "no_match":
        path = cache / "review" / review.CROSSWALK_FILE
        path.write_text(
            path.read_text()
            .replace("SYN-place-0,,", "SYN-place-0,SYN-venue-a,")
            .replace(",pending", ",no_match")
        )
    if kind == "address":
        path = cache / "places_s2_t06/pub_place.jsonl"
        path.write_text(path.read_text().replace("2026-10-21.0", "invented-other"))
    seen = []

    def transport(request):
        seen.append(str(request))
        return Response(str(request), encode(answer), ())

    build.build_busyness(
        entry, transport, cache, lambda: STAMP, env, reviews, bootstrap=True
    )
    report = json.loads((cache / "busy_besttime/bootstrap-run.json").read_text())
    assert report["coverage"]["reasons"] == {
        "SYN-place-0": "venue_address_absent" if kind == "address" else kind
    }
    assert len(seen) == (1 if kind == "no_forecast" else 0)


def test_busyness_command_registry_error_is_closed(tmp_path, monkeypatch, capsys):
    import commands.build_public as command
    from eii_custodian.publicdata.fetch.registry import RegistryError

    def broken_registry():
        raise RegistryError("SYN-upstream-diagnostic")

    monkeypatch.setattr(command, "load_registry", broken_registry)
    assert (
        command.run(
            tmp_path,
            {},
            ["--busyness-bootstrap"],
            transport=lambda req: pytest.fail("sent"),
        )
        == 1
    )
    output = capsys.readouterr().err
    assert "busyness_phase_failed" in output
    assert "SYN-upstream-diagnostic" not in output


def test_busyness_unreadable_document_drops_exception_context():
    from eii_custodian.publicdata.busyness.handoff import _document

    with pytest.raises(ValueError, match=r"^handoff_schema$") as caught:
        _document(b'{"SYN-secret-marker":')
    assert caught.value.__context__ is None


def test_busyness_command_plain_never_selects_bootstrap(tmp_path, monkeypatch):
    from custodian.tests.method_pin_config_fixture import stage_tracked_configuration

    import commands.build_public as command
    from eii_custodian.publicdata.fetch.build import BuildOutcome

    stage_tracked_configuration(tmp_path)
    seen = []

    def plain(*args, **kwargs):
        seen.append(kwargs)
        return BuildOutcome((), None)

    monkeypatch.setattr(
        command, "_busyness_phase", lambda *args: pytest.fail("bootstrap selected")
    )
    monkeypatch.setattr(command, "run_build", plain)
    assert command.run(tmp_path, {}, (), transport=lambda req: pytest.fail("sent")) == 0
    assert seen and all("bootstrap" not in arguments for arguments in seen)
