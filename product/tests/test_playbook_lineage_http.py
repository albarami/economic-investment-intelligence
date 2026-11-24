"""S3-P09: site_check answer facts resolve over the mounted lineage route."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from product.tests.public_http_support import Client
from product.tests.public_opening_server import build_fixture_app

from eii_product.api.app import create_app
from eii_product.api.release import qualifiers
from eii_product.api.session_store import CapReached, SessionStore
from eii_product.assistant.playbooks.engine import execute
from eii_product.store.protocol import QueryResult

START = {"activity": "INVENTED-activity", "lang": "en"}
AREA = {"pin": {"lat": 1, "lon": 1}, "mode": "walk", "cutoff": 15}
FOREIGN = "ef" * 32
SEAT = "INVENTED-seat"


def frames(client: Any, started: Any) -> list[tuple[str, Any]]:
    text = client.get(started.json()["events_url"]).text
    return [
        (part.split("event: ")[1].split("\r\n")[0], json.loads(part.split("data: ")[1]))
        for part in text.split("\r\n\r\n")
        if "event: " in part
    ]


def answer_facts(client: Any) -> list[dict[str, Any]]:
    started = client.post("/api/playbooks/site_check", json={**START, **AREA})
    assert started.status_code == 202
    return answer_facts_of(client, started)


def answer_facts_of(client: Any, started: Any) -> list[dict[str, Any]]:
    return [
        fact
        for kind, data in frames(client, started)
        if kind == "evidence"
        for fact in data["facts"]
    ]


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    work = tmp_path_factory.mktemp("answer-lineage")
    app, store, ledger = build_fixture_app(work, work / "web")
    bundles: list[Any] = []

    def capture(*args: Any, **kwargs: Any) -> Any:
        bundles.append(execute(*args, **kwargs))
        return bundles[-1]

    client = Client(app)
    try:
        with patch("eii_product.api.playbooks.execute", side_effect=capture):
            facts = answer_facts(client)
        yield client, store, ledger, facts, bundles[0]
    finally:
        ledger.close()
        store.close()


@pytest.fixture
def fresh(tmp_path: Path) -> Iterator[Any]:
    app, store, ledger = build_fixture_app(tmp_path, tmp_path / "web")
    try:
        yield Client(app), store, ledger
    finally:
        ledger.close()
        store.close()


@contextmanager
def restored(mount: Any) -> Iterator[None]:
    before = dict(mount.answered)
    try:
        mount.answered.clear()
        yield
    finally:
        mount.answered.clear()
        mount.answered.update(before)


def lineage_code(client: Any, fact_id: str) -> tuple[int, str]:
    return code(client.get("/api/facts/" + fact_id + "/lineage"))


def test_site_check_fact_resolves_over_lineage(served):
    client, store, _, facts, bundle = served
    assert facts
    assert {f["fact_id"] for f in facts} == set(bundle.facts)
    for fact in facts:
        response = client.get("/api/facts/" + fact["fact_id"] + "/lineage")
        assert response.status_code == 200
        chain = response.json()
        assert set(chain) == {"fact_id", "release_id", "lineage", "sources", "binding"}
        assert chain["fact_id"] == fact["fact_id"]
        assert chain["release_id"] == store.release_id
        held = fact["source_chain"]
        assert chain["lineage"]["lineageId"] == fact["lineage_ref"]
        assert chain["lineage"]["tableName"] == held["lineage"][0]["table_name"]
        assert (
            chain["lineage"]["method"] + "@" + chain["lineage"]["methodVersion"]
            == held["lineage"][0]["transform"]
        )
        assert chain["lineage"]["sourceIds"] == sorted(
            {r["source_id"] for r in held["lineage"]}
        )
        assert [s["sha256"] for s in chain["sources"]] == [
            s["sha256"] for s in sorted(held["sources"], key=lambda s: s["source_id"])
        ]
        assert chain["binding"]["metricKey"] == (
            bundle.facts[fact["fact_id"]].metric_key
        )


def test_answer_binding_matches_card_entry_qualifiers(served):
    client, *_, bundle = served
    entries = [
        e
        for step in bundle.steps
        if step["tool"] == "population_age_sex"
        for e in step["payload"]["entries"]
        if e.get("fact_id")
    ]
    assert entries
    for entry in entries:
        chain = client.get("/api/facts/" + entry["fact_id"] + "/lineage").json()
        assert chain["binding"]["qualifiers"] == qualifiers(entry)
        assert chain["binding"]["qualifiers"]


def test_unknown_identifier_is_not_found(served):
    client, *_ = served
    assert code(client.get("/api/facts/f_" + "e" * 32 + "/lineage")) == (
        404,
        "NOT_FOUND",
    )


def test_answer_facts_resolve_only_for_the_session_that_admitted_them(fresh):
    app = fresh[0].app
    a, b = Client(app), Client(app)
    facts = answer_facts(a)
    assert facts and set(a.cookies) == {"eii_session"}
    for fact in facts:
        assert a.get("/api/facts/" + fact["fact_id"] + "/lineage").status_code == 200
    admitted = app.state.sessions.admit(None)
    b.cookies["eii_session"] = admitted.key
    for fact in facts:
        assert lineage_code(b, fact["fact_id"]) == (404, "NOT_FOUND")
    own = answer_facts(b)
    assert b.cookies["eii_session"] == admitted.key
    assert own
    for fact in own:
        assert b.get("/api/facts/" + fact["fact_id"] + "/lineage").status_code == 200


@pytest.mark.parametrize(
    "cookies", [{}, {"eii_session": "INVENTED-unadmitted-key"}], ids=["none", "unknown"]
)
def test_answer_facts_refuse_a_request_without_an_admitted_session(served, cookies):
    client, *_, bundle = served
    other = Client(client.app)
    other.cookies.update(cookies)
    for key in bundle.facts:
        assert lineage_code(other, key) == (404, "NOT_FOUND")


def test_answer_facts_refuse_a_seat_the_trusted_dependency_does_not_verify(served):
    from eii_product.api.area_context import trusted_seat

    client, *_, bundle = served
    client.app.dependency_overrides[trusted_seat] = lambda: "INVENTED-other-seat"
    try:
        for key in bundle.facts:
            assert lineage_code(client, key) == (404, "NOT_FOUND")
    finally:
        client.app.dependency_overrides.clear()
    for key in bundle.facts:
        assert client.get("/api/facts/" + key + "/lineage").status_code == 200


def test_session_cap_refuses_a_new_answer_before_admission(fresh):
    client, _, ledger = fresh
    app = client.app
    sessions = app.state.sessions
    kept = sessions.admit(None).key
    while not isinstance(sessions.admit(None), CapReached):
        pass
    count, rows = sessions.count, ledger.rows()
    assert code(client.post("/api/playbooks/site_check", json={**START, **AREA})) == (
        429,
        "RATE_LIMITED",
    )
    assert "eii_session" not in client.cookies
    assert (sessions.count, ledger.rows(), app.state.release_mount.answered) == (
        count,
        rows,
        {},
    )
    client.cookies["eii_session"] = kept
    assert answer_facts(client)
    assert set(app.state.release_mount.answered) == {kept}


def test_foreign_release_fact_is_refused_with_chain_refused(served):
    client, *_, bundle = served
    mount = client.app.state.release_mount
    key, evidence = next(iter(bundle.facts.items()))
    foreign = replace(
        evidence, fact=evidence.fact.model_copy(update={"release_id": FOREIGN})
    )
    with restored(mount):
        with pytest.raises(ValueError, match=r"^chain_refused$"):
            mount.prepare_answer(replace(bundle, facts={**bundle.facts, key: foreign}))
        assert mount.answered == {}


def test_foreign_release_answer_admits_nothing_and_rolls_back(fresh):
    client, _, ledger = fresh
    mount = client.app.state.release_mount

    def planted(*args: Any, **kwargs: Any) -> Any:
        bundle = execute(*args, **kwargs)
        key, evidence = next(iter(bundle.facts.items()))
        bundle.facts[key] = replace(
            evidence, fact=evidence.fact.model_copy(update={"release_id": FOREIGN})
        )
        return bundle

    rows = ledger.rows()
    with patch("eii_product.api.playbooks.execute", side_effect=planted):
        started = client.post("/api/playbooks/site_check", json={**START, **AREA})
    assert code(started) == (500, "INTERNAL")
    assert mount.answered == {}
    assert ledger.rows() == rows
    assert (client.cookies, client.app.state.sessions.count) == ({}, 0)


def test_incomplete_chain_is_refused(served, monkeypatch):
    client, store, *_, bundle = served
    mount = client.app.state.release_mount
    fetch = store.fetch

    def missing(query, params):
        result = fetch(query, params)
        if query.name == "sector_facts_lineage":
            return QueryResult(result.columns, ())
        return result

    monkeypatch.setattr(store, "fetch", missing)
    with restored(mount):
        with pytest.raises(ValueError, match=r"^chain_refused$"):
            mount.prepare_answer(bundle)
        assert mount.answered == {}


def test_unbound_metric_is_refused(served):
    client, *_, bundle = served
    mount = client.app.state.release_mount
    key, evidence = next(iter(bundle.facts.items()))
    with restored(mount):
        with pytest.raises(ValueError, match=r"^metric_unbound$"):
            mount.prepare_answer(
                replace(
                    bundle,
                    facts={**bundle.facts, key: replace(evidence, metric_key="")},
                )
            )
        assert mount.answered == {}


def test_failed_commit_admits_nothing(fresh):
    client, _, ledger = fresh
    app = client.app
    mount = app.state.release_mount
    sessions = app.state.sessions = SessionStore(3)
    held = Client(app)
    earlier = answer_facts(held)
    kept = held.cookies["eii_session"]
    transaction = ledger.transaction

    depth = [0]

    @contextmanager
    def failing() -> Iterator[None]:
        # Only the router's outer transaction fails, after its body completed;
        # the ledger's own nested writes use the real savepoints.
        depth[0] += 1
        try:
            with transaction():
                yield
                if depth[0] == 1:
                    raise RuntimeError("INVENTED-commit-failure")
        finally:
            depth[0] -= 1

    prepared = []
    real = mount.prepare_answer

    def spy(bundle: Any) -> Any:
        prepared.append(bundle)
        return real(bundle)

    rows, count = ledger.rows(), sessions.count
    with (
        patch.object(ledger, "transaction", failing),
        patch.object(mount, "prepare_answer", spy),
    ):
        started = client.post("/api/playbooks/site_check", json={**START, **AREA})
        again = held.post("/api/playbooks/site_check", json={**START, **AREA})
    assert code(started) == code(again) == (500, "INTERNAL")
    assert len(prepared) == 2 and all(bundle.facts for bundle in prepared)
    assert set(mount.answered) == {kept}
    assert set(mount.answered[kept]) == {f["fact_id"] for f in earlier}
    assert ledger.rows() == rows
    assert (sessions.count, dict(client.cookies)) == (count, {})
    assert dict(held.cookies) == {"eii_session": kept}
    for fact in earlier:
        assert held.get("/api/facts/" + fact["fact_id"] + "/lineage").status_code == 200
    # The failed newcomer's slot is free again: the store sits at its cap minus one.
    assert not isinstance(sessions.admit(None), CapReached)
    assert answer_facts(client)
    assert sessions.count == 3 and set(mount.answered) == {
        kept,
        client.cookies["eii_session"],
    }


def test_unmounted_store_still_answers_and_refuses_lineage(served, tmp_path):
    bundle = served[4]
    with patch(
        "product.tests.public_opening_server.create_app", wraps=create_app
    ) as built:
        _app, store, ledger = build_fixture_app(tmp_path, tmp_path / "web")
    try:
        # The same fixture inputs without a release folder: no verified mount.
        kwargs = {
            k: v
            for k, v in built.call_args.kwargs.items()
            if k not in ("release_dir", "web_dir", "startup_policy")
        }
        client = Client(create_app(*built.call_args.args, **kwargs))
        assert client.app.state.release_mount is None
        started = client.post("/api/playbooks/site_check", json={**START, **AREA})
        assert started.status_code == 202
        assert answer_facts_of(client, started)
        assert (client.cookies, client.app.state.sessions.count) == ({}, 0)
        for key in bundle.facts:
            assert code(client.get("/api/facts/" + key + "/lineage")) == (
                503,
                "STORE_UNAVAILABLE",
            )
    finally:
        ledger.close()
        store.close()


@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_admission_is_exact_and_all_or_nothing(served, data):
    client, *_, bundle = served
    mount = client.app.state.release_mount
    keys = data.draw(st.permutations(sorted(bundle.facts)))
    chosen = keys[: data.draw(st.integers(0, len(keys)))]
    plant = data.draw(st.none() | st.integers(0, max(len(chosen) - 1, 0)))
    facts = {k: bundle.facts[k] for k in chosen}
    if plant is not None and chosen:
        evidence = facts[chosen[plant]]
        facts[chosen[plant]] = replace(
            evidence, fact=evidence.fact.model_copy(update={"release_id": FOREIGN})
        )
    with restored(mount):
        if plant is not None and chosen:
            with pytest.raises(ValueError, match=r"^chain_refused$"):
                mount.prepare_answer(replace(bundle, facts=facts))
            assert mount.answered == {}
            return
        admit = mount.prepare_answer(replace(bundle, facts=facts))
        assert mount.answered == {}
        admit(SEAT)
        assert set(mount.answered) == {SEAT}
        assert set(mount.answered[SEAT]) == set(chosen)
        for key, (fact, binding) in mount.answered[SEAT].items():
            assert fact == bundle.facts[key].fact
            assert binding.metricKey == bundle.facts[key].metric_key


SEATS = ("INVENTED-seat-a", "INVENTED-seat-b", "INVENTED-seat-c")


@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_lookup_resolves_exactly_the_asking_sessions_answers(served, data):
    client, *_, bundle = served
    mount = client.app.state.release_mount
    keys = sorted(bundle.facts)
    # Repeated seats, empty answers and facts shared between seats are drawn.
    admissions = data.draw(
        st.lists(st.tuples(st.sampled_from(SEATS), st.sets(st.sampled_from(keys))))
    )
    asked = data.draw(st.none() | st.just("") | st.sampled_from(SEATS))
    held: dict[str, set[str]] = {}
    with restored(mount):
        assert mount.emitted == {}
        for seat, chosen in admissions:
            facts = {k: bundle.facts[k] for k in chosen}
            mount.prepare_answer(replace(bundle, facts=facts))(seat)
            held.setdefault(seat, set()).update(chosen)
        for key in keys:
            found = mount.find(key, asked)
            assert (found is not None) == (key in held.get(asked or "", set()))
            if found is not None:
                assert found[0] == bundle.facts[key].fact
