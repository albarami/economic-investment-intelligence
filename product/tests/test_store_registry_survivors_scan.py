"""Kills surviving mutants of the registry scanners."""

from __future__ import annotations

from typing import Any

import pytest

from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import (
    _depth0_keywords,
    _dollar_open,
    _quoted_end,
    _refuse_dollar_quotes,
    _split_commas,
    _string_end,
    translate,
)


def refusal(caught: pytest.ExceptionInfo[StoreRefusal], text: str) -> None:
    """Compare the whole refusal text with one hand-written literal."""
    assert str(caught.value) == text


def as_any(value: object) -> Any:
    """Hand a value the parameter's annotation would reject."""
    return value


@pytest.mark.parametrize(
    ("sql", "engine", "expected"),
    [
        (":unit", "postgres", "%(unit)s"),
        (":unit", "embedded", "$unit"),
        ("a:unit", "postgres", "a:unit"),
        ("_:unit", "postgres", "_:unit"),
        ("(:unit)", "postgres", "(%(unit)s)"),
        ("a::text", "postgres", "a::text"),
        ("ab::c", "postgres", "ab::c"),
        ("::text", "postgres", "::text"),
        ("A\n-- c\n:unit\nB", "postgres", "A\n-- c\n%(unit)s\nB"),
        ("A\n-- c\n:unit", "embedded", "A\n-- c\n$unit"),
        ("X/*note*/:unit", "postgres", "X/*note*/%(unit)s"),
        ("X/**/:unit", "postgres", "X/**/%(unit)s"),
        ("X/*a*/:unit/*b*/Z", "postgres", "X/*a*/%(unit)s/*b*/Z"),
        ("X'a''b' :unit", "postgres", "X'a''b' %(unit)s"),
        ('X"a""b" :unit', "postgres", 'X"a""b" %(unit)s'),
        ("SELECT -- c", "postgres", "SELECT -- c"),
    ],
)
def test_translate_rewrites_only_real_placeholders(
    sql: str, engine: str, expected: str
) -> None:
    assert translate(sql, as_any(engine)) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "X-- :h\nY",
        "X/*:h*/Y",
        "X':h'Y",
        "$$",
        "$tag$a$tag$",
        "X$$Y",
    ],
)
def test_translate_refuses_hidden_and_dollar_text(sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        translate(sql, "postgres")
    refusal(caught, "forbidden construct")


@pytest.mark.parametrize("sql", ["SELECT /* c", "SELECT 'c", 'SELECT "c'])
def test_translate_refuses_an_unclosed_region(sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        translate(sql, "postgres")
    refusal(caught, "parse invalid")


def test_depth0_keywords_skip_shields_and_nested_selects() -> None:
    """Positions are counted from the start of each literal."""
    assert _depth0_keywords("SELECT a FROM t") == [("SELECT", 0), ("FROM", 9)]
    assert _depth0_keywords("SELECT 'FROM' a FROM t") == [("SELECT", 0), ("FROM", 16)]
    assert _depth0_keywords('SELECT "FROM" a FROM t') == [("SELECT", 0), ("FROM", 16)]
    assert _depth0_keywords("SELECT -- FROM\nFROM t") == [("SELECT", 0), ("FROM", 15)]
    assert _depth0_keywords("SELECT /* FROM */ a FROM t") == [
        ("SELECT", 0),
        ("FROM", 20),
    ]
    assert _depth0_keywords("SELECT () FROM t") == [("SELECT", 0), ("FROM", 10)]
    assert _depth0_keywords("SELECT ((SELECT a FROM b)) FROM t") == [
        ("SELECT", 0),
        ("FROM", 27),
    ]
    assert _depth0_keywords("A\n-- c\nSELECT") == [("SELECT", 7)]
    assert _depth0_keywords("SELECT -- c") == [("SELECT", 0)]
    assert _depth0_keywords("SELECT -- c\nFROM t\nFROM u") == [
        ("SELECT", 0),
        ("FROM", 12),
        ("FROM", 19),
    ]
    assert _depth0_keywords("SELECT /**/FROM t") == [("SELECT", 0), ("FROM", 11)]
    assert _depth0_keywords("SELECT /*a*/ FROM t /*b*/") == [
        ("SELECT", 0),
        ("FROM", 13),
    ]
    assert _depth0_keywords("/*c*/ SELECT a FROM t") == [
        ("SELECT", 6),
        ("FROM", 15),
    ]


def test_depth0_unclosed_block_is_parse_invalid() -> None:
    with pytest.raises(StoreRefusal) as caught:
        _depth0_keywords("SELECT /* c")
    refusal(caught, "parse invalid")


def test_split_commas_ignore_nested_and_shielded_commas() -> None:
    assert _split_commas("ab") == [(0, 2)]
    assert _split_commas("a,b") == [(0, 1), (2, 3)]
    assert _split_commas("a,,b") == [(0, 1), (2, 2), (3, 4)]
    assert _split_commas("(a,b)") == [(0, 5)]
    assert _split_commas("(a,b),c") == [(0, 5), (6, 7)]
    assert _split_commas("a,'b,c',d") == [(0, 1), (2, 7), (8, 9)]
    assert _split_commas('a,"b,c",d') == [(0, 1), (2, 7), (8, 9)]
    assert _split_commas("a,-- c\nb,d\ne") == [(0, 1), (2, 8), (9, 12)]
    assert _split_commas("a,-- b,c\nd") == [(0, 1), (2, 10)]
    assert _split_commas("a,-- b") == [(0, 1), (2, 6)]
    assert _split_commas("\n-- c\na,b") == [(0, 7), (8, 9)]
    assert _split_commas("a,/* c */b,d") == [(0, 1), (2, 10), (11, 12)]
    assert _split_commas("a,/*c*/,b") == [(0, 1), (2, 7), (8, 9)]
    assert _split_commas("a,/**/,x*/,b") == [(0, 1), (2, 6), (7, 10), (11, 12)]
    assert _split_commas("/*c*/,a") == [(0, 5), (6, 7)]
    assert _split_commas("a,/*c*/,/*d*/,e") == [(0, 1), (2, 7), (8, 13), (14, 15)]
    assert _split_commas("((a,b)),c") == [(0, 7), (8, 9)]


def test_split_unclosed_block_is_parse_invalid() -> None:
    with pytest.raises(StoreRefusal) as caught:
        _split_commas("a,/* c")
    refusal(caught, "parse invalid")


@pytest.mark.parametrize(
    ("sql", "index", "expected"),
    [
        ("$$", 0, True),
        ("$ab$", 0, True),
        ("$a$", 0, True),
        ("$_x$", 0, True),
        ("$a_b$", 0, True),
        ("$1$", 0, False),
        ("$a", 0, False),
        ("$ab", 0, False),
        ("$", 0, False),
        ("a", 0, False),
        ("$$", 2, False),
    ],
)
def test_dollar_open_accepts_only_a_closed_tag(
    sql: str, index: int, expected: bool
) -> None:
    assert _dollar_open(sql, index) is expected


def test_dollar_quotes_inside_shields_are_kept() -> None:
    _refuse_dollar_quotes("SELECT '$$' AS a")
    _refuse_dollar_quotes('SELECT "$$" AS a')
    _refuse_dollar_quotes("SELECT /* $$ */ 1")
    _refuse_dollar_quotes("SELECT -- $$\n1")
    _refuse_dollar_quotes("A\n-- c\nSELECT 1")


@pytest.mark.parametrize(
    "sql",
    [
        "$$",
        "$tag$",
        "X$$Y",
        "X$ab$Y",
        "X-- c\n$$",
        "X-- c\n$$\nY",
        "X/* c */$$",
        "X/*c*/$$/*d*/",
        "X'a'$$",
        'X"a"$$',
    ],
)
def test_dollar_quote_is_forbidden(sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        _refuse_dollar_quotes(sql)
    refusal(caught, "forbidden construct")


def test_dollar_scanner_refuses_an_unclosed_block() -> None:
    with pytest.raises(StoreRefusal) as caught:
        _refuse_dollar_quotes("SELECT /* c")
    refusal(caught, "parse invalid")


@pytest.mark.parametrize(
    ("sql", "start", "expected"),
    [
        ("''", 0, 2),
        ("'a'", 0, 3),
        ("'''ab'", 0, 6),
        ("''''", 0, 4),
        ("'a''b'", 0, 6),
        ("'a'''b'", 0, 5),
        ("'a''", 0, None),
        ("'ab", 0, None),
    ],
)
def test_string_end_stops_after_the_closer(
    sql: str, start: int, expected: int | None
) -> None:
    if expected is None:
        with pytest.raises(StoreRefusal) as caught:
            _string_end(sql, start)
        refusal(caught, "parse invalid")
        return
    assert _string_end(sql, start) == expected


@pytest.mark.parametrize(
    ("sql", "start", "expected"),
    [
        ('""', 0, 2),
        ('"a"', 0, 3),
        ('"""ab"', 0, 6),
        ('""""', 0, 4),
        ('"a""b"', 0, 6),
        ('"a"""b"', 0, 5),
        ('"a""', 0, None),
        ('"ab', 0, None),
    ],
)
def test_quoted_end_stops_after_the_closer(
    sql: str, start: int, expected: int | None
) -> None:
    if expected is None:
        with pytest.raises(StoreRefusal) as caught:
            _quoted_end(sql, start)
        refusal(caught, "parse invalid")
        return
    assert _quoted_end(sql, start) == expected
