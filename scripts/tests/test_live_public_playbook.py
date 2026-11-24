"""Offline checks of the live companion's command contract."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from live_public_playbook import (
    RESOLVE_ROUTE_QUERIES,
    SELECTED_QUERIES,
    public_query_names,
)

_ROUTE_QUERY_NAMES = sorted(RESOLVE_ROUTE_QUERIES | set(SELECTED_QUERIES))


def _complete_record() -> dict[str, Any]:
    """One record whose per-engine lists cover every declared inventory."""
    import live_public_playbook as live

    required = sorted(
        set(live.public_query_names())
        | live.RESOLVE_ROUTE_QUERIES
        | set(live.SELECTED_QUERIES)
    )
    return dict(
        state="complete",
        release_id="ab" * 32,
        commit="cd" * 20,
        exits=[0, 3],
        queries={engine: list(required) for engine in ("postgres", "embedded")},
    )


def test_resolve_trace_inventory_rejects_each_omitted_query() -> None:
    import live_public_playbook as live

    assert callable(getattr(live, "require_resolve_coverage", None))
    required = live.RESOLVE_ROUTE_QUERIES
    valid = {"embedded": list(required), "postgres": list(required)}
    live.require_resolve_coverage(valid)
    for engine in valid:
        for missing in required:
            poisoned = {**valid, engine: [name for name in required if name != missing]}
            with pytest.raises(ValueError, match="resolve_query_coverage"):
                live.require_resolve_coverage(poisoned)
    with pytest.raises(ValueError, match="resolve_query_coverage"):
        live.require_resolve_coverage({"embedded": list(required)})
    with pytest.raises(ValueError, match="resolve_query_coverage"):
        live.require_resolve_coverage(
            {**valid, "embedded": [*required, "INVENTED-query"]}
        )


def test_live_playbook_companion_exit_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import live_public_playbook as live

    bundle = {"steps": ["INVENTED-a", "INVENTED-b"], "facts": []}
    brief = {"catalogue_version": "INVENTED"}

    def runner(environ: Mapping[str, str], diverge: bool) -> int:
        right = deepcopy(bundle)
        if diverge:
            right["steps"].reverse()
        return live.judge(bundle, right, brief, brief, diverge)

    assert live.main([], {}, runner=runner) == 0
    assert live.main(["--diverge"], {}, runner=runner) == 3
    assert live.main(["--invented"], {}, runner=runner) == 2
    assert live.judge(bundle, bundle, brief, brief, True) == 1
    altered = deepcopy(brief)
    altered["catalogue_version"] = "INVENTED-other"
    assert live.judge(bundle, bundle, brief, altered, False) == 1
    assert "PASS public-playbook" in capsys.readouterr().out


def test_live_playbook_proof_exception_refuses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import live_public_playbook as live

    assert live.main([], {}, runner=lambda environ, diverge: 0) == 0
    capsys.readouterr()

    def failed(environ: Mapping[str, str], diverge: bool) -> int:
        raise ValueError("invented_proof_failure")

    assert live.main([], {}, runner=failed) == 1
    assert capsys.readouterr().out == "FAIL public-playbook: operation_failed\n"


def test_public_route_inventory_and_standin_refusal() -> None:
    import live_public_playbook as live

    names = live.public_query_names()
    assert {
        "public_release_manifest",
        "public_lineage_for_table",
        "sector_facts_sources",
        "layer_fdi_gazetteer",
        "layer_company_points",
    } <= set(names)

    class SecondEngineStandIn:
        engine = "postgres"

    standin = SecondEngineStandIn()
    with pytest.raises(ValueError, match="actual_stores_required"):
        live.public_routes_proof(
            cast(Any, standin), cast(Any, object()), cast(Any, None), cast(Any, None)
        )


@pytest.mark.parametrize(
    "plant", ("pending", "missing", "wrong_commit", "missing_query")
)
def test_live_receipt_cannot_close_pending_evidence(plant: str) -> None:
    import live_public_playbook as live

    record = _complete_record()
    assert live.evidence_complete(record, "ab" * 32, "cd" * 20)
    if plant == "pending":
        record["state"] = "pending"
    if plant == "missing":
        del record["exits"]
    if plant == "wrong_commit":
        record["commit"] = "ef" * 20
    if plant == "missing_query":
        record["queries"]["postgres"].pop()
    assert not live.evidence_complete(record, "ab" * 32, "cd" * 20)


def test_live_record_of_public_queries_alone_is_incomplete() -> None:
    """The resolver and selected inventories are part of complete evidence."""
    import live_public_playbook as live

    record = _complete_record()
    record["queries"] = {
        engine: list(live.public_query_names()) for engine in ("postgres", "embedded")
    }
    assert not live.evidence_complete(record, "ab" * 32, "cd" * 20)


@pytest.mark.parametrize("omitted", _ROUTE_QUERY_NAMES)
def test_live_record_missing_a_route_query_is_incomplete(omitted: str) -> None:
    import live_public_playbook as live

    record = _complete_record()
    assert live.evidence_complete(record, "ab" * 32, "cd" * 20)
    for engine in ("postgres", "embedded"):
        changed = deepcopy(record)
        changed["queries"][engine].remove(omitted)
        assert not live.evidence_complete(changed, "ab" * 32, "cd" * 20)


@given(data=st.data())
def test_evidence_gate_covers_every_route_name(data: st.DataObject) -> None:
    """Any nonempty gap in either engine's recorded list stays incomplete."""
    import live_public_playbook as live

    record = _complete_record()
    required = sorted(record["queries"]["postgres"])
    engine = data.draw(st.sampled_from(("postgres", "embedded")))
    removed = data.draw(st.sets(st.sampled_from(required), min_size=1))
    changed = deepcopy(record)
    changed["queries"][engine] = [name for name in required if name not in removed]
    assert not live.evidence_complete(changed, "ab" * 32, "cd" * 20)
    extras = data.draw(
        st.sets(
            st.text(min_size=1).filter(lambda name: name not in set(required)),
            min_size=1,
        )
    )
    shuffled = data.draw(
        st.permutations([*required, *required[: len(required) // 2], *extras])
    )
    changed["queries"][engine] = shuffled
    assert live.evidence_complete(changed, "ab" * 32, "cd" * 20)


@pytest.mark.parametrize("removed", public_query_names())
def test_every_omitted_actual_query_trace_refuses(removed: str) -> None:
    from eii_product.store.parity import ParityCase, cover
    from eii_product.store.protocol import StoreRefusal
    from eii_product.tools.registry import (
        public_card_descriptors,
        public_layer_descriptors,
    )

    tools = (*public_layer_descriptors(), *public_card_descriptors(cast(Any, None)))
    names = public_query_names()
    with pytest.raises(StoreRefusal, match="query not executed"):
        cover(
            tools=tools,
            cases=tuple(ParityCase(t.key, ()) for t in tools),
            traces={
                "postgres": tuple(q for q in names if q != removed),
                "embedded": names,
            },
            identities={"postgres": "ab" * 32, "embedded": "ab" * 32},
            query_names=names,
        )


@pytest.mark.parametrize("omitted", ["polygon", "distance", "walk", "drive", "default"])
def test_selected_case_coverage_is_independent_of_queries(omitted: str) -> None:
    import live_public_playbook as live

    executed = {
        (engine, case)
        for engine in ("postgres", "embedded")
        for case in live.SELECTED_CASES
    }
    live.require_selected_cases(executed)
    executed.remove(("postgres", omitted))
    with pytest.raises(ValueError, match="selected_case_missing"):
        live.require_selected_cases(executed)


def test_absent_live_record_cannot_close_selected_gate() -> None:
    import live_public_playbook as live

    with pytest.raises(ValueError, match="live_selected_evidence_pending"):
        live.require_live_selected_record(None)
    with pytest.raises(ValueError, match="live_selected_evidence_pending"):
        live.require_live_selected_record({"kind": "control", "exit": 0})


def test_live_selected_record_requires_both_commands_and_scoped_queries() -> None:
    import live_public_playbook as live

    record = {
        "kind": "live",
        "normal_exit": 0,
        "diverge_exit": 3,
        "commit": "ab" * 20,
        "release_id": "cd" * 32,
        "cases": {
            engine: list(live.SELECTED_CASES) for engine in ("postgres", "embedded")
        },
        "queries": {
            engine: list(live.SELECTED_QUERIES) for engine in ("postgres", "embedded")
        },
    }
    live.require_live_selected_record(record)
    for field in (
        "kind",
        "normal_exit",
        "diverge_exit",
        "commit",
        "release_id",
        "cases",
        "queries",
    ):
        changed = {key: value for key, value in record.items() if key != field}
        with pytest.raises(ValueError, match="live_selected_evidence_pending"):
            live.require_live_selected_record(changed)
    for omitted in live.SELECTED_QUERIES:
        traces = {
            engine: list(live.SELECTED_QUERIES) for engine in ("postgres", "embedded")
        }
        live.require_selected_queries(traces)
        traces["postgres"].remove(omitted)
        with pytest.raises(ValueError, match="selected_query_missing"):
            live.require_selected_queries(traces)
