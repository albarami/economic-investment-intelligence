"""S2-P46: invented proof bytes, interrupted reads and offline population replay."""

import json
from dataclasses import replace
from time import perf_counter

import pytest
from custodian.tests.test_award_all_links import intake
from custodian.tests.test_s2_t29_awards import STAMP, profile, proof_row, row

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import AwardError
from eii_custodian.publicdata.fetch.award_links import check_all_awards
from eii_custodian.publicdata.fetch.page_records import PageError


def test_shape_refusal_keeps_going():
    calls = []

    def reader(url):
        calls.append(url)
        if url == row()["report_url"]:
            raise PageError("schema_missing")
        return proof_row()

    check = check_all_awards([row(), row(1)], profile(), reader)
    assert calls == [row()["report_url"], row(1)["report_url"]]
    assert check["results"][0]["reason"] == "schema_missing"
    assert check["results"][0]["result"] == "refused"
    assert check["incomplete"] is True


def test_fetch_once_and_replay(tmp_path, monkeypatch):
    entry, _declaration, proof = intake(tmp_path, monkeypatch, count=3)
    calls = []

    def send(url):
        calls.append(url)
        return proof(url)

    first = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    calls.clear()
    second = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert calls == []
    assert first.sidecar["award_links"] == second.sidecar["award_links"]
    replay = awards.replay_awards(entry, tmp_path, lambda: STAMP)
    assert replay["award_links"] == first.sidecar["award_links"]


def test_refusal_bytes_survive(tmp_path, monkeypatch):
    entry, _declaration, proof = intake(tmp_path, monkeypatch, count=3)
    calls = []

    def send(url):
        calls.append(url)
        return replace(proof(url), body=b"SYN wrong shape")

    with pytest.raises(AwardError, match=r"^award_proof_refused$"):
        awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert len(calls) == 3
    reports = list((tmp_path / entry.key / "proof_checks/index").glob("*.json"))
    assert len(reports) == 1
    replay = awards.replay_awards(entry, tmp_path, lambda: STAMP)
    assert [r["reason"] for r in replay["award_links"]["results"]] == [
        "schema_missing"
    ] * 3
    assert not (tmp_path / entry.key / "index").exists()


def test_interrupted_run_restarts_at_next_link(tmp_path, monkeypatch):
    entry, dec, proof = intake(tmp_path, monkeypatch, count=5)
    calls = []

    def interrupted(url):
        if len(calls) == 3:
            raise KeyboardInterrupt
        calls.append(url)
        return proof(url)

    with pytest.raises(KeyboardInterrupt):
        awards.fetch_awards(entry, interrupted, tmp_path, lambda: STAMP, lambda _: None)
    first = list(calls)
    calls.clear()

    def send(url):
        calls.append(url)
        return proof(url)

    result = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert first == sorted(dec["reviewed_urls"])[:3]
    assert calls == sorted(dec["reviewed_urls"])[3:]
    assert result.sidecar["award_links"]["checked_count"] == 5


@pytest.mark.parametrize("damage", ["body", "receipt"])
def test_only_invalid_link_is_refetched(tmp_path, monkeypatch, damage):
    from eii_custodian.publicdata.fetch.award_store import ProofStore
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    entry, dec, proof = intake(tmp_path, monkeypatch, count=3)
    awards.fetch_awards(entry, proof, tmp_path, lambda: STAMP, lambda _: None)
    url = sorted(dec["reviewed_urls"])[1]
    folder = ProofStore(tmp_path, entry, dec, STAMP).folder(url)
    state = json.loads((folder / "state.json").read_bytes())
    saved = read_snapshot(folder / state["archive"], state["identity"])
    if damage == "body":
        saved.path.write_bytes(b"SYN changed byte")
    else:
        saved.receipt_path.unlink()
    calls = []

    def send(address):
        calls.append(address)
        return proof(address)

    awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert calls == [url]
    assert (folder / state["archive"]).exists()
    assert (
        json.loads((folder / "state.json").read_bytes())["archive"] != state["archive"]
    )


@pytest.mark.parametrize(
    "reason", ["schema_missing", "snapshot_date_missing", "unavailable", "row_count"]
)
def test_closed_shape_classes(reason):
    def reader(_):
        raise PageError(reason)

    result = check_all_awards([row()], profile(), reader)
    assert result["results"] == [
        {"report_url": row()["report_url"], "result": "refused", "reason": reason}
    ]


@pytest.mark.parametrize("reason", ["blocked_host", "SYN unknown"])
def test_unknown_and_host_errors_stop(reason):
    def reader(_):
        raise PageError(reason)

    with pytest.raises(PageError, match=f"^{reason}$"):
        check_all_awards([row(), row(1)], profile(), reader)


def test_replay_missing_has_no_transport(tmp_path, monkeypatch):
    entry, _dec, _proof = intake(tmp_path, monkeypatch, count=1)
    with pytest.raises(AwardError, match=r"^proof_store_missing$"):
        awards.replay_awards(entry, tmp_path, lambda: STAMP)


def population(tmp_path, monkeypatch, count):
    from custodian.tests.test_awards_survivors_1 import csv_body
    from custodian.tests.test_s2_t29_live_awards import report

    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.transport import Response

    entry, _dec, _proof = intake(tmp_path, monkeypatch, count=count)
    dec, body = report()
    dec.update(
        max_bytes=4194304,
        url=entry.url,
        reviewed_urls=[row(i)["report_url"] for i in range(count)],
        profile=dict(
            profile(),
            proof_columns={
                "company": "SYN company",
                "registration": "SYN registration",
                "value": "SYN amount",
            },
        ),
    )
    folder = tmp_path / "intake" / entry.key
    intake_body = csv_body(
        [
            dict(row(i), syn_company="SYN first", syn_value="1007.00 QAR")
            for i in range(count)
        ]
    )
    (folder / "syn.csv").write_bytes(intake_body)
    manifest = json.loads((folder / "intake.json").read_bytes())
    manifest["sha256"] = sha256_hex(intake_body)
    (folder / "intake.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(awards, "load_declaration", lambda _: dec)
    return entry, dec, lambda url: Response(url, body, ())


def test_replay_nine_thousand_real_shape_under_one_minute(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import award_checks

    entry, _dec, proof = population(tmp_path, monkeypatch, 9000)
    _dec["max_readers"] = 4
    calls = []

    def send(url):
        calls.append(url)
        return proof(url)

    live = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert len(calls) == 9000
    calls.clear()
    start = perf_counter()
    replay = awards.replay_awards(entry, tmp_path, lambda: STAMP)
    elapsed = perf_counter() - start
    print(f"S2-P46 replay links=9000 seconds={elapsed:.6f}")
    assert elapsed <= 60
    assert replay["award_links"] == live.sidecar["award_links"]
    monkeypatch.setattr(
        award_checks, "comparison_reason", lambda *args: "proof_mismatch"
    )
    start = perf_counter()
    changed = awards.replay_awards(entry, tmp_path, lambda: STAMP)
    elapsed = perf_counter() - start
    print(f"S2-P46 changed comparison links=9000 seconds={elapsed:.6f}")
    assert elapsed <= 60
    assert changed["award_links"]["mismatched"] == 9000
    assert {r["reason"] for r in changed["award_links"]["results"]} == {
        "proof_mismatch"
    }
    assert calls == []


def test_pool_order_and_contexts(monkeypatch):
    from contextvars import ContextVar
    from threading import Barrier

    from eii_custodian.publicdata.fetch import award_pool
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool

    monkeypatch.setattr(
        award_pool, "as_completed", lambda pending: reversed(list(pending))
    )
    parent = ContextVar("SYN context", default="SYN missing")
    parent.set("SYN parent")
    barrier = Barrier(4)
    records = [row(i) for i in range(4)]

    def concurrent(url):
        assert parent.get() == "SYN parent"
        parent.set(url)
        barrier.wait(timeout=5)
        assert parent.get() == url
        return proof_row()

    parallel = check_all_awards(records, profile(), concurrent, pool=ReaderPool(4))
    serial = check_all_awards(records, profile(), lambda _: proof_row())
    assert (
        json.dumps(parallel, sort_keys=True).encode()
        == json.dumps(serial, sort_keys=True).encode()
    )
    assert parent.get() == "SYN parent"


@pytest.mark.parametrize(
    "kind,status", [("unreachable", None), ("http", 429), ("http", 503), ("http", 500)]
)
def test_transport_refusal_reduces_remaining_run(tmp_path, monkeypatch, kind, status):
    from threading import Barrier, Lock, get_ident

    from eii_custodian.publicdata.fetch.transport import TransportFault

    entry, dec, proof = population(tmp_path, monkeypatch, 12)
    dec["max_readers"] = 4
    barrier = Barrier(4)
    lock = Lock()
    urls = sorted(dec["reviewed_urls"])
    calls = []
    active = 0
    peak_tail = 0

    def send(url):
        nonlocal active, peak_tail
        with lock:
            calls.append((url, get_ident()))
            active += 1
            if url not in urls[:4]:
                peak_tail = max(peak_tail, active)
        try:
            if url in urls[:4] and sum(u == url for u, _ in calls) == 1:
                barrier.wait(timeout=5)
            if url == urls[0]:
                raise TransportFault(kind, url, status)
            return proof(url)
        finally:
            with lock:
                active -= 1

    snapshot = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert peak_tail == 1
    assert {ident for url, ident in calls if url not in urls[:4]} == {get_ident()}
    assert snapshot.sidecar["award_readers"] == {
        "max_readers": 4,
        "fallback": True,
        "fallback_reason": "unreachable" if kind == "unreachable" else "http_status",
    }
    assert snapshot.sidecar["award_links"]["results"][0]["reason"] == (
        "unreachable" if kind == "unreachable" else "http_status"
    )


@pytest.mark.parametrize("value", [0, 5, True, 1.0, "4", None])
def test_invalid_pool_width(value):
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool

    with pytest.raises(AwardError, match=r"^award_readers_invalid$"):
        ReaderPool(value)


def test_pool_width_domain():
    from hypothesis import given
    from hypothesis import strategies as st

    from eii_custodian.publicdata.fetch.award_pool import reader_count

    @given(st.one_of(st.integers(), st.booleans(), st.text(), st.none(), st.floats()))
    def oracle(value):
        if type(value) is int and value in {1, 2, 3, 4}:
            assert reader_count(value) == value
        else:
            with pytest.raises(AwardError, match=r"^award_readers_invalid$"):
                reader_count(value)

    oracle()


@pytest.mark.parametrize(
    "plant",
    [
        "state_missing",
        "state_json",
        "state_keys",
        "identity_type",
        "body",
        "receipt",
        "proof_url",
        "transport",
        "source_id",
        "key",
        "upstream_sha256",
        "upstream_type",
    ],
)
def test_store_invalidates_exact_link_with_named_replay_refusal(
    tmp_path, monkeypatch, plant
):
    from eii_custodian.publicdata.fetch.award_store import ProofStore
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    store = ProofStore(tmp_path, entry, dec, STAMP)
    url = dec["url"]
    store.save(url, proof(url))
    folder = store.folder(url)
    state_path = folder / "state.json"
    state = json.loads(state_path.read_bytes())
    directory = folder / state["archive"]
    saved = read_snapshot(directory, state["identity"])
    if plant == "state_missing":
        state_path.unlink()
    elif plant == "state_json":
        state_path.write_bytes(b"SYN bad json")
    elif plant == "state_keys":
        state_path.write_text("{}")
    elif plant == "identity_type":
        state["identity"] = []
        state_path.write_text(json.dumps(state))
    elif plant == "body":
        saved.path.write_bytes(b"SYN changed")
    elif plant == "receipt":
        saved.receipt_path.unlink()
    else:
        side = dict(saved.sidecar)
        key = "upstream_sha256" if plant == "upstream_type" else plant
        side[key] = None if plant == "upstream_type" else "SYN changed"
        replacement = publish_snapshot(folder / ("a" * 32), "html", saved.body, side)
        state_path.write_text(
            json.dumps({"archive": "a" * 32, "identity": replacement.sha256})
        )
    with pytest.raises(AwardError, match=r"^proof_store_missing$"):
        store.body(url, replay=True)


@pytest.mark.parametrize(
    "plant", ["folder", "state", "archive_name", "archive", "body"]
)
def test_store_paths_refuse_before_network(tmp_path, monkeypatch, plant):
    from eii_custodian.publicdata.fetch.award_store import ProofStore
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError, read_snapshot

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    store = ProofStore(tmp_path, entry, dec, STAMP)
    url = dec["url"]
    store.save(url, proof(url))
    folder = store.folder(url)
    state_path = folder / "state.json"
    state = json.loads(state_path.read_bytes())
    directory = folder / state["archive"]
    saved = read_snapshot(directory, state["identity"])
    if plant == "archive_name":
        state["archive"] = "../SYN escape"
        state_path.write_text(json.dumps(state))
    else:
        path = {
            "folder": folder,
            "state": state_path,
            "archive": directory,
            "body": saved.path,
        }[plant]
        moved = path.with_name(path.name + "-SYN-original")
        path.rename(moved)
        path.symlink_to(moved.name, target_is_directory=plant in {"folder", "archive"})
    with pytest.raises(SnapshotError, match=r"^snapshot_path_invalid$"):
        store.body(url, replay=False)


def test_store_write_failure_stops_instead_of_fetch_failed(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import award_store
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    store = award_store.ProofStore(tmp_path, entry, dec, STAMP)

    def broken(*args, **kwargs):
        raise OSError("SYN secret diagnostic")

    monkeypatch.setattr(award_store, "NamedTemporaryFile", broken)
    with pytest.raises(SnapshotError, match=r"^snapshot_write_failed$"):
        store.save(dec["url"], proof(dec["url"]))


@pytest.mark.parametrize(
    "reason", ["snapshot_conflict", "snapshot_path_invalid", "snapshot_date_missing"]
)
def test_store_never_downgrades_other_archive_refusals(tmp_path, monkeypatch, reason):
    from eii_custodian.publicdata.fetch import award_store
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    store = award_store.ProofStore(tmp_path, entry, dec, STAMP)
    store.save(dec["url"], proof(dec["url"]))

    def broken(*args):
        raise SnapshotError(reason)

    monkeypatch.setattr(award_store, "read_snapshot", broken)
    with pytest.raises(SnapshotError, match=f"^{reason}$"):
        store.load(dec["url"])


def test_transient_429_also_reduces_run(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.transport import TransportFault

    entry, dec, proof = population(tmp_path, monkeypatch, 6)
    dec["max_readers"] = 4
    called = set()

    def send(url):
        if url == sorted(dec["reviewed_urls"])[0] and url not in called:
            called.add(url)
            raise TransportFault("http", url, 429)
        return proof(url)

    snapshot = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert snapshot.sidecar["award_readers"]["fallback_reason"] == "http_status"
    assert snapshot.sidecar["award_links"]["matched"] == 6


def test_shape_parser_change_uses_stored_population(tmp_path, monkeypatch):
    entry, _dec, proof = population(tmp_path, monkeypatch, 4)
    awards.fetch_awards(entry, proof, tmp_path, lambda: STAMP, lambda _: None)

    def refused(*args):
        raise PageError("schema_missing")

    monkeypatch.setattr(awards, "parse_body", refused)
    outcome = awards.replay_awards(entry, tmp_path, lambda: STAMP)
    assert [r["reason"] for r in outcome["award_links"]["results"]] == [
        "schema_missing"
    ] * 4


def test_publish_refused_prechecked_result_is_blocked(tmp_path):
    from custodian.tests.test_awards_survivors_1 import award_entry, batch

    def refused(_):
        raise PageError("schema_missing")

    links = check_all_awards([row()], profile(), refused)
    with pytest.raises(AwardError, match=r"^award_proof_refused$"):
        awards._publish_awards(
            award_entry(),
            tmp_path,
            batch(),
            profile(),
            STAMP,
            73,
            lambda _: proof_row(),
            [],
            links=links,
        )


def test_legacy_archive_identity_refusal(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_store import verify_legacy_proofs
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError, publish_snapshot

    entry, _dec, _proof = intake(tmp_path, monkeypatch, count=1)
    publish_snapshot(
        tmp_path / entry.key / "proofs",
        "html",
        b"SYN legacy",
        {"source_id": "SYN wrong", "key": entry.key, "retrieved_utc": STAMP},
    )
    with pytest.raises(SnapshotError, match=r"^snapshot_conflict$"):
        verify_legacy_proofs(tmp_path, entry)


def test_shape_refusal_prevents_staging(tmp_path, monkeypatch):
    entry, _dec, proof = intake(tmp_path, monkeypatch, count=1)

    def forbidden(*args):
        pytest.fail("refused proof entered publication stage")

    monkeypatch.setattr(awards, "staged_source", forbidden)
    with pytest.raises(AwardError, match=r"^award_proof_refused$"):
        awards.fetch_awards(
            entry,
            lambda url: replace(proof(url), body=b"SYN wrong shape"),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
        )


def test_proof_reader_exact_url_refusal(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool
    from eii_custodian.publicdata.fetch.award_store import ProofStore

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    store = ProofStore(tmp_path, entry, dec, STAMP)

    def forbidden(*args, **kwargs):
        pytest.fail("off-frame URL reached the proof store")

    monkeypatch.setattr(store, "body", forbidden)
    read = awards._proof_reader(
        entry,
        dec,
        store,
        frozenset({dec["url"]}),
        None,
        ReaderPool(),
        proof,
        lambda _: None,
    )
    with pytest.raises(AwardError, match=r"^blocked_host$"):
        read(row(99)["report_url"])


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("pin", "certificate_chain_incomplete"),
        ("size", "metadata_bytes"),
        ("blocked", "blocked_host"),
        ("failure", "proof_fetch_failed"),
        ("hop", "blocked_host"),
    ],
)
def test_proof_response_refusal_branches(tmp_path, monkeypatch, plant, reason):
    from eii_custodian.publicdata.fetch.award_links import ProofFetchError
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool
    from eii_custodian.publicdata.fetch.certificate_pins import PinError
    from eii_custodian.publicdata.fetch.transport import TransportFault

    _entry, dec, proof = population(tmp_path, monkeypatch, 1)
    dec["max_bytes"] = len(proof(dec["url"]).body) - (plant == "size")

    def send(url):
        if plant == "pin":
            raise PinError("certificate_chain_incomplete")
        if plant == "blocked":
            raise TransportFault("blocked_host", url)
        if plant == "failure":
            raise TransportFault("http", url, 500)
        response = proof(url)
        return (
            replace(response, final_url=row(99)["report_url"])
            if plant == "hop"
            else response
        )

    expected = (
        PinError
        if plant == "pin"
        else ProofFetchError
        if plant == "failure"
        else AwardError
    )
    with pytest.raises(expected, match=f"^{reason}$"):
        awards._proof_response(
            dec["url"],
            send,
            lambda _: None,
            dec,
            frozenset(dec["reviewed_urls"]),
            None,
            ReaderPool(),
        )


def test_empty_parsed_proof_refuses_in_reader(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool
    from eii_custodian.publicdata.fetch.award_store import ProofStore

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    monkeypatch.setattr(awards, "parse_body", lambda *args: [])
    read = awards._proof_reader(
        entry,
        dec,
        ProofStore(tmp_path, entry, dec, STAMP),
        frozenset({dec["url"]}),
        None,
        ReaderPool(),
        proof,
        lambda _: None,
    )
    with pytest.raises(AwardError, match=r"^schema_missing$"):
        read(dec["url"])


def test_context_entry_provenance_refuses(tmp_path, monkeypatch):
    entry, _dec, _proof = intake(tmp_path, monkeypatch, count=1)
    with pytest.raises(AwardError, match=r"^receipt_missing$"):
        awards._awards_context(replace(entry, publisher=""), tmp_path, lambda: STAMP)


def test_oserror_reduces_pool():
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool

    pool = ReaderPool(4)

    def failed(_):
        raise OSError("SYN confidential diagnostic")

    result = check_all_awards([row()], profile(), failed, pool=pool)
    assert result["results"][0]["reason"] == "unreachable"
    assert pool.receipt()["fallback_reason"] == "unreachable"


def test_response_oserror_reduces_pool(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool

    _entry, dec, _proof = population(tmp_path, monkeypatch, 1)
    pool = ReaderPool(4)

    def failed(_):
        raise ConnectionRefusedError

    with pytest.raises(ConnectionRefusedError):
        awards._proof_response(
            dec["url"],
            failed,
            lambda _: None,
            dec,
            frozenset(dec["reviewed_urls"]),
            None,
            pool,
        )
    assert pool.receipt()["fallback_reason"] == "unreachable"


def test_result_partition_and_parallel_property():
    from fractions import Fraction

    from hypothesis import example, given
    from hypothesis import strategies as st

    from eii_custodian.publicdata.fetch.award_links import ProofFetchError
    from eii_custodian.publicdata.fetch.award_pool import ReaderPool

    @given(st.lists(st.integers(min_value=0, max_value=15), max_size=40))
    @example([])
    @example([0])
    @example([0, 0, 0])
    @example([3, 2, 1, 0, 3])
    def oracle(indices):
        records = [
            dict(row(i), report_url=" " + row(i)["report_url"] + " ") for i in indices
        ]
        records += [dict(row(), report_url=" ")]

        def reader(url):
            index = int(url.rsplit("/", 1)[1])
            if index % 4 == 2:
                raise PageError("schema_missing")
            if index % 4 == 3:
                raise ProofFetchError("http_status")
            return dict(proof_row(), syn_value="13.50" if index % 4 == 1 else "12.50")

        first = check_all_awards(records, profile(), reader)
        parallel = check_all_awards(
            list(reversed(records)), profile(), reader, pool=ReaderPool(4)
        )
        assert parallel == first
        report = awards._proof_report(first)
        unique = set(indices)
        expected = {
            remainder: sum(i % 4 == remainder for i in unique) for remainder in range(4)
        }
        assert report["refused_count"] == expected[2]
        assert report["refusals_by_class"]["schema_missing"] == expected[2]
        assert first["matched"] == expected[0]
        assert first["mismatched"] == expected[1]
        assert first["failed_fetches"] == expected[3]
        assert sum(expected.values()) == first["checked_count"]
        if unique:
            assert Fraction(first["match_rate"]).limit_denominator(
                len(unique)
            ) == Fraction(expected[0], len(unique))
        else:
            assert first["match_rate"] is None

    oracle()


def test_full_sample_with_shape_refusal_is_incomplete():
    from eii_custodian.publicdata.fetch.award_checks import check_awards

    def refused(_):
        raise PageError("schema_missing")

    check = check_awards([row(i) for i in range(30)], profile(), 73, refused)
    assert check["status"] == "award_check_incomplete"
    assert {item["reason"] for item in check["results"]} == {"schema_missing"}


@pytest.mark.parametrize("proof", [[], [None], [42]])
def test_candidate_schema_refused(proof):
    check = check_all_awards([row()], profile(), lambda _: proof)
    assert check["results"][0]["reason"] == "schema_missing"
    assert check["results"][0]["result"] == "refused"


def test_each_proof_uses_its_retrieval_clock(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_store import ProofStore
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    retrieved = "2024-02-04T01:00:00Z"
    store = ProofStore(tmp_path, entry, dec, STAMP, lambda: retrieved)
    store.save(dec["url"], proof(dec["url"]))
    folder = store.folder(dec["url"])
    state = json.loads((folder / "state.json").read_bytes())
    snapshot = read_snapshot(folder / state["archive"], state["identity"])
    assert snapshot.sidecar["retrieved_utc"] == retrieved
    assert snapshot.path.parent.name == "2024-02-04"


def test_four_real_proof_readers_have_scopes_and_identical_output(
    tmp_path, monkeypatch
):
    from threading import Barrier

    from eii_custodian.publicdata.fetch.certificate_pins import current_pin
    from eii_custodian.publicdata.fetch.page_requests import active, check_target
    from eii_custodian.publicdata.fetch.transport import _METADATA_LIMIT

    parallel_entry, parallel_dec, parallel_proof = population(
        tmp_path / "parallel", monkeypatch, 4
    )
    parallel_dec["max_readers"] = 4
    barrier = Barrier(4)

    def send(url):
        assert active()
        assert _METADATA_LIMIT.get() == parallel_dec["max_bytes"]
        assert current_pin() is None
        check_target(url)
        barrier.wait(timeout=5)
        return parallel_proof(url)

    parallel = awards.fetch_awards(
        parallel_entry, send, tmp_path / "parallel", lambda: STAMP, lambda _: None
    )
    serial_entry, serial_dec, serial_proof = population(
        tmp_path / "serial", monkeypatch, 4
    )
    serial_dec["max_readers"] = 1
    serial = awards.fetch_awards(
        serial_entry, serial_proof, tmp_path / "serial", lambda: STAMP, lambda _: None
    )
    assert parallel.body == serial.body
    assert json.dumps(parallel.sidecar["award_links"], sort_keys=True) == json.dumps(
        serial.sidecar["award_links"], sort_keys=True
    )
    assert not active()


def test_form_secrets_removed_before_storage_with_upstream_hash(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_store import ProofStore
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    entry, dec, proof = population(tmp_path, monkeypatch, 1)
    response = proof(dec["url"])
    response = replace(
        response,
        body=response.body
        + b'<input name="__RequestVerificationToken" value="SYN discarded token">',
    )
    store = ProofStore(tmp_path, entry, dec, STAMP)
    sanitized = store.save(dec["url"], response)
    assert b"SYN discarded token" not in sanitized
    folder = store.folder(dec["url"])
    state = json.loads((folder / "state.json").read_bytes())
    snapshot = read_snapshot(folder / state["archive"], state["identity"])
    assert snapshot.sidecar["upstream_sha256"] == sha256_hex(response.body)
    assert snapshot.sha256 == sha256_hex(sanitized)
    assert snapshot.sha256 != snapshot.sidecar["upstream_sha256"]


def test_changed_transport_version_refetches_only_its_namespace(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import award_store

    entry, dec, proof = intake(tmp_path, monkeypatch, count=3)
    store = award_store.ProofStore(tmp_path, entry, dec, STAMP)
    original_folder = store.folder(dec["url"])
    awards.fetch_awards(entry, proof, tmp_path, lambda: STAMP, lambda _: None)
    monkeypatch.setattr(award_store, "TRANSPORT_VERSION", "awards.https_proof@SYN-next")
    assert store.folder(dec["url"]) != original_folder
    with pytest.raises(AwardError, match=r"^proof_store_missing$"):
        awards.replay_awards(entry, tmp_path, lambda: STAMP)


@pytest.mark.parametrize("role", ["proof_checks", "proofs/index", "proof_store"])
def test_existing_source_symlink_stops_before_acquisition(tmp_path, monkeypatch, role):
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    entry, _dec, _proof = intake(tmp_path, monkeypatch, count=1)
    target = tmp_path / "SYN other source"
    target.mkdir()
    link = tmp_path / entry.key / role
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)

    def forbidden(_):
        pytest.fail("untrusted source directory reached transport")

    with pytest.raises(SnapshotError, match=r"^snapshot_path_invalid$"):
        awards.fetch_awards(entry, forbidden, tmp_path, lambda: STAMP, lambda _: None)


def test_duplicate_state_key_refuses_replay(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.award_store import ProofStore

    entry, dec, proof = intake(tmp_path, monkeypatch, count=1)
    store = ProofStore(tmp_path, entry, dec, STAMP)
    store.save(dec["url"], proof(dec["url"]))
    path = store.folder(dec["url"]) / "state.json"
    state = json.loads(path.read_bytes())
    path.write_text(
        '{"archive": '
        + json.dumps(state["archive"])
        + ', "identity": '
        + json.dumps(state["identity"])
        + ', "identity": '
        + json.dumps(state["identity"])
        + "}"
    )
    with pytest.raises(AwardError, match=r"^proof_store_missing$"):
        store.body(dec["url"], replay=True)


@pytest.mark.parametrize(
    "body",
    [
        b"\xff",
        b"<div>SYN unclosed",
        b'<input name="__RequestVerificationToken" value="SYN discard" value="SYN duplicate">',
    ],
)
def test_unarchivable_representation_is_hard_refusal(tmp_path, monkeypatch, body):
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    entry, _dec, proof = population(tmp_path, monkeypatch, 1)
    with pytest.raises(SnapshotError, match=r"^proof_representation_refused$"):
        awards.fetch_awards(
            entry,
            lambda url: replace(proof(url), body=body),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
        )
    assert not list((tmp_path / entry.key / "proof_store").rglob("state.json"))
