"""Bounded, locked admission with no fixation, eviction or shared state."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Thread

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_core.shapes import canonical_ring
from eii_product.api.session_store import CapReached, SessionKey, SessionStore
from eii_product.config import ConfigError
from eii_product.tools.make_area import ShapeMiss


@pytest.mark.parametrize("cap", [0, -1, True, 1.5, "3", None])
def test_bad_cap(cap):
    with pytest.raises(ConfigError):
        SessionStore(cap)


def test_admission_cap_no_fixation_no_eviction_restart():
    store = SessionStore(3)
    held = [store.admit("INVENTED-client") for _ in range(3)]
    assert len({s.key for s in held}) == 3
    assert all(s.key != "INVENTED-client" and len(s.key) >= 43 for s in held)
    ring = canonical_ring(((1, 1), (1, 2), (2, 2), (1, 1)))
    identity = held[0].shapes.add(ring)
    assert isinstance(store.admit(None), CapReached)
    assert isinstance(store.admit("INVENTED-unknown"), CapReached)
    assert store.count == 3
    assert store.admit(held[0].key).shapes.find(identity).ring == ring
    assert isinstance(held[1].shapes.find(identity), ShapeMiss)
    assert isinstance(SessionStore(3).shapes(held[0].key).find(identity), ShapeMiss)
    assert isinstance(store.shapes(None).find(identity), ShapeMiss)
    assert store.count == 3


def test_race_for_last_slot():
    store = SessionStore(3)
    store.admit(None)
    store.admit(None)
    barrier = Barrier(2)

    def admit(_):
        barrier.wait()
        return store.admit(None)

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(admit, range(2)))
    assert sum(isinstance(item, CapReached) for item in result) == 1
    assert store.count == 3


def test_release_frees_only_a_new_allocation():
    store = SessionStore(2)
    kept = store.admit(None)
    again = store.admit(kept.key)
    assert again.created is False
    store.release(again)
    assert store.count == 1
    assert store.admit(kept.key).created is False
    fresh = store.admit(None)
    assert isinstance(store.admit(None), CapReached)
    store.release(fresh)
    assert store.count == 1
    assert store.shapes(fresh.key).seat is None
    store.release(fresh)
    assert store.count == 1
    assert not isinstance(store.admit(None), CapReached)


def test_release_of_a_foreign_store_key_removes_nothing():
    store, other = SessionStore(2), SessionStore(2)
    kept = store.admit(None)
    stranger = other.admit(None)
    store.release(SessionKey(kept.key, stranger.shapes, True))
    assert store.count == 1
    assert store.admit(kept.key).created is False


def race_for_last_slot_with_a_failed_commit(fail_first: bool) -> None:
    # Two requests at the cap minus one; the one whose commit fails releases.
    store = SessionStore(3)
    store.admit(None)
    store.admit(None)
    barrier, finished = Barrier(2), Event()
    seen: list[int] = []

    def failing(_):
        barrier.wait()
        try:
            found = store.admit(None)
            seen.append(store.count)
            if not isinstance(found, CapReached):
                store.release(found)
            return found
        finally:
            finished.set()

    def succeeding(_):
        barrier.wait()
        found = store.admit(None)
        seen.append(store.count)
        if isinstance(found, CapReached):  # a 429, retried by its client
            assert finished.wait(5)
            found = store.admit(None)
            seen.append(store.count)
        return found

    with ThreadPoolExecutor(2) as pool:
        if fail_first:
            lost, won = pool.submit(failing, 0), pool.submit(succeeding, 0)
        else:
            won, lost = pool.submit(succeeding, 0), pool.submit(failing, 0)
        assert not isinstance(won.result(), CapReached) and won.result().created
        lost.result()
    assert max(seen) <= 3
    assert store.count == 3
    assert store.admit(won.result().key).created is False


def test_concurrent_last_slot_with_a_failed_commit():
    for turn in range(200):
        race_for_last_slot_with_a_failed_commit(turn % 2 == 0)


def test_store_held_back_from_a_paused_failure_admits_after_release():
    store = SessionStore(3)
    store.admit(None)
    store.admit(None)
    holding, released = Event(), Event()

    def failing():
        found = store.admit(None)
        holding.set()
        released.wait()
        store.release(found)

    worker = Thread(target=failing)
    worker.start()
    holding.wait()
    assert isinstance(store.admit(None), CapReached)
    assert store.count == 3
    released.set()
    worker.join()
    assert store.count == 2
    assert store.admit(None).created is True
    assert store.count == 3


@settings(max_examples=200, deadline=None)
@given(
    steps=st.lists(
        st.tuples(st.sampled_from(["new", "old", "release"]), st.integers(0, 7))
    ),
    cap=st.integers(1, 4),
)
def test_admit_and_release_match_a_model(steps, cap):
    store = SessionStore(cap)
    handed: list[SessionKey] = []
    live: set[str] = set()
    for action, index in steps:
        if action == "new":
            found = store.admit(None)
            assert isinstance(found, CapReached) == (len(live) >= cap)
            if not isinstance(found, CapReached):
                assert found.created and found.key not in live
                live.add(found.key)
                handed.append(found)
        elif handed:
            chosen = handed[index % len(handed)]
            if action == "old":
                found = store.admit(chosen.key)
                if chosen.key in live:
                    assert found.created is False and found.shapes is chosen.shapes
                else:
                    assert isinstance(found, CapReached) == (len(live) >= cap)
                    if not isinstance(found, CapReached):
                        live.add(found.key)
                        handed.append(found)
            else:
                store.release(chosen)
                if chosen.created:
                    live.discard(chosen.key)
        assert store.count == len(live) <= cap
