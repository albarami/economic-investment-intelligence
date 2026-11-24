"""Counterexamples to campaign seven's proposed lint equivalence proofs."""

from __future__ import annotations

import pytest
from product.tests.test_store_lint_survivors import full_message
from product.tests.test_store_lint_survivors_b import _mod, _parse, _spec

from eii_product.store.protocol import StoreRefusal


def test_sum_distinct_is_not_count_distinct() -> None:
    text = "SELECT SUM(DISTINCT p.amount) AS amount FROM control_rows AS p"
    with pytest.raises(StoreRefusal) as caught:
        _mod()._lint_one(_spec(text, returns=(("amount", "numeric"),), order=()))
    full_message(caught.value, "forbidden construct")


def test_count_accepts_coalesce_with_two_alternatives() -> None:
    text = (
        "SELECT COUNT(COALESCE(p.count_value, 1, 2)) AS unit_id FROM control_rows AS p"
    )
    _mod()._lint_one(_spec(text, returns=(("unit_id", "bigint"),), order=()))


def test_recursive_union_does_not_read_select_order() -> None:
    text = (
        "WITH RECURSIVE syn_picked AS (SELECT p.unit_id FROM control_rows AS p) "
        "SELECT syn_picked.unit_id FROM syn_picked "
        "UNION ALL SELECT q.unit_id FROM control_rows AS q "
        "ORDER BY syn_picked.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _mod()._order(_parse(text), _spec(text, name="graph_syn"))
    full_message(caught.value, "order unproved")


def test_nulls_check_ignores_empty_item_before_limit() -> None:
    # The helper accepts text directly; the full parser rejects this statement.
    assert (
        _mod()._nulls_explicit("ORDER BY p.unit_id ASC NULLS LAST, LIMIT 1", 1) is True
    )


def test_empty_parser_batch_is_refused_without_indexing() -> None:
    with pytest.raises(StoreRefusal) as caught:
        _mod()._lint_one(_spec("ELSE"))
    full_message(caught.value, "parse invalid")


def test_cte_trace_requires_select_even_for_a_select_subclass() -> None:
    import sqlglot

    class SynSelect(sqlglot.exp.Select):
        """An AST node with SELECT fields but a different expression kind."""

    tree = _parse(
        "WITH syn_picked AS (SELECT p.unit_id FROM control_rows AS p) "
        "SELECT syn_picked.unit_id FROM syn_picked"
    )
    cte = next(node for node in tree.walk() if type(node).__name__ == "CTE")
    cte.set("this", SynSelect(**cte.this.args))
    assert _mod()._trace_unrenamed({"syn_picked": cte}, "syn_picked", "unit_id") is None


def test_last_as_does_not_skip_an_opening_parenthesis() -> None:
    assert _mod()._last_as("AS(AS)") == 0
