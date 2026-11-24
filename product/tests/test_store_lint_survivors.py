"""Kill surviving mutants of the portable-SQL scanners.

Expectations are hand-worked from the scanner rules. Refusal text is compared
only through ``full_message``.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from product.tests.frames import raised_in

from eii_product.store.protocol import StoreRefusal


def _mod() -> Any:
    """Reload point so a mutated module object is what the assertions call."""
    return importlib.import_module("eii_product.store.lint")


def full_message(value: BaseException, expected: str) -> None:
    """Compare the whole refusal text with one hand-written literal."""
    assert str(value) == expected


def test_mask_blanks_a_line_comment_a_block_and_a_string() -> None:
    """Masking keeps code and replaces comments and quotes with spaces."""
    masked = _mod()._mask("x\n--zz\n'ab'")
    assert masked == "x\n    \n    "
    blocked = _mod()._mask("ab/*zz*/c")
    assert blocked == "ab    */c"
    quoted = _mod()._mask("'ab'")
    assert quoted == "    "
    escaped = _mod()._mask("'''x'")
    assert escaped == "     "
    plain = _mod()._mask("ab")
    assert plain == "ab"
    doubled = _mod()._mask("''")
    assert doubled == "  "


def test_lexical_refuses_markers_and_keeps_a_masked_comment() -> None:
    """Lexical refusals name the closed reason and skip a masked line comment."""
    mod = _mod()
    with pytest.raises(StoreRefusal) as percent:
        mod._lexical("SELECT 1 % 2")
    full_message(percent.value, "forbidden construct")
    assert raised_in(percent, "_lexical")
    with pytest.raises(StoreRefusal) as mark:
        mod._lexical("?")
    full_message(mark.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as cast:
        mod._lexical("a::b")
    full_message(cast.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as semi:
        mod._lexical("a;b")
    full_message(semi.value, "parse invalid")
    with pytest.raises(StoreRefusal) as bare:
        mod._lexical("AS INT")
    full_message(bare.value, "forbidden construct")
    mod._lexical("x\n-- AS INT\nSELECT 1")
    mod._lexical("'a;b'")
    with pytest.raises(StoreRefusal) as hidden:
        mod._lexical("x\n-- :label\nSELECT 1")
    full_message(hidden.value, "forbidden construct")
    assert raised_in(hidden, "_hidden")
    with pytest.raises(StoreRefusal) as open_comment:
        mod._lexical("/*")
    full_message(open_comment.value, "parse invalid")
    assert raised_in(open_comment, "_lexical")
    mod._lexical("/* c */ SELECT 1")
    with pytest.raises(StoreRefusal) as after_string:
        mod._lexical("'a' ?")
    full_message(after_string.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as after_quote:
        mod._lexical('"ab"?')
    full_message(after_quote.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as after_comment:
        mod._lexical("x\n--a\n?\nb")
    full_message(after_comment.value, "forbidden construct")
    mod._lexical("/*?*/")
    with pytest.raises(StoreRefusal) as after_block:
        mod._lexical("/**/?")
    full_message(after_block.value, "forbidden construct")
    mod._lexical("x\n--?")
    mod._lexical("x*/ /*?*/")
    with pytest.raises(StoreRefusal) as between_closers:
        mod._lexical("/*a*/?*/")
    full_message(between_closers.value, "forbidden construct")


def test_string_end_closes_on_the_matching_quote() -> None:
    """The end index is one past the closer. An open quote is parse invalid."""
    mod = _mod()
    assert mod._string_end("'ab'", 0) == 4
    assert mod._string_end("xx'ab'y", 2) == 6
    assert mod._string_end("''", 0) == 2
    assert mod._string_end("''a", 0) == 2
    assert mod._string_end("'''a'''", 0) == 7
    assert mod._string_end("'''a'", 0) == 5
    with pytest.raises(StoreRefusal) as open_quote:
        mod._string_end("'", 0)
    full_message(open_quote.value, "parse invalid")
    assert raised_in(open_quote, "_string_end")
    with pytest.raises(StoreRefusal) as escaped_open:
        mod._string_end("'''", 0)
    full_message(escaped_open.value, "parse invalid")


def test_skip_lexical_steps_over_comments_and_quotes() -> None:
    """Comments and quotes advance. Ordinary text and the end stay put."""
    mod = _mod()
    assert mod._skip_lexical("abc", 0) == 0
    assert mod._skip_lexical("abc", 3) == 3
    assert mod._skip_lexical("--ab\ncd", 0) == 4
    assert mod._skip_lexical("--ab", 0) == 4
    assert mod._skip_lexical("/*ab*/cd", 0) == 6
    assert mod._skip_lexical("'ab'c", 0) == 4
    assert mod._skip_lexical('"ab"c', 0) == 4
    with pytest.raises(StoreRefusal) as open_block:
        mod._skip_lexical("/*", 0)
    full_message(open_block.value, "parse invalid")
    assert raised_in(open_block, "_skip_lexical")


def test_skip_space_and_keyword_boundaries() -> None:
    """Space is skipped. A keyword needs a non-identifier on both sides."""
    mod = _mod()
    assert mod._skip_space("  ab", 0) == 2
    assert mod._skip_space("ab", 0) == 0
    assert mod._skip_space("ab", 2) == 2
    assert mod._keyword_at("CAST(", 0, "CAST") is True
    assert mod._keyword_at("CAST", 0, "CAST") is True
    assert mod._keyword_at("CASTX", 0, "CAST") is False
    assert mod._keyword_at("CAST_", 0, "CAST") is False
    assert mod._keyword_at("XCAST", 1, "CAST") is False
    assert mod._keyword_at(" cast", 1, "CAST") is True
    assert mod._keyword_at("CAST", 0, "AS") is False


def test_dotted_sees_a_dot_before_the_word() -> None:
    """A dot, with spaces ignored, qualifies the word."""
    mod = _mod()
    assert mod._dotted("ab. c", 4) is True
    assert mod._dotted(".unit", 1) is True
    assert mod._dotted("unit", 0) is False
    assert mod._dotted("p.unit", 2) is True


def test_gap_skips_space_and_reports_a_comment() -> None:
    """The cursor stops on the next code character and the comment flag is exact."""
    mod = _mod()
    assert mod._gap("ab", 0) == (0, False)
    assert mod._gap("  ab", 0) == (2, False)
    assert mod._gap(" /*c*/ab", 0) == (6, True)
    assert mod._gap(" --c\nab", 0) == (5, True)


def test_function_call_words_and_a_quoted_paren() -> None:
    """An unlisted word before a parenthesis is refused. A quoted name is too."""
    mod = _mod()
    mod._function_calls("SELECT p.unit_id FROM t AS p")
    mod._function_calls("COALESCE(p.label, 'SYN-a')")
    mod._function_calls("SUM(p.amount)")
    with pytest.raises(StoreRefusal) as quoted:
        mod._function_calls('"name"(p.unit_id)')
    full_message(quoted.value, "forbidden construct")
    assert raised_in(quoted, "_function_calls")
    with pytest.raises(StoreRefusal) as called:
        mod._function_calls("POWER(p.amount)")
    full_message(called.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as dotted:
        mod._function_calls("p.SUM(p.amount)")
    full_message(dotted.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as commented:
        mod._function_calls("SUM /*c*/ (p.amount)")
    full_message(commented.value, "forbidden construct")
    mod._function_calls("WHERE (p.unit_id = 1)")
    with pytest.raises(StoreRefusal) as underscore:
        mod._function_calls("_SUM(p.amount)")
    full_message(underscore.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as glued:
        mod._function_calls("FOO_SUM(p.amount)")
    full_message(glued.value, "forbidden construct")


def test_parameters_count_real_placeholders_only() -> None:
    """A placeholder in code is used. One in a comment, quote or word is not."""
    mod = _mod()
    assert _parameter_result(mod, ":label", ("label",)) == "accepted"
    assert _parameter_result(mod, "x:label", ()) == "accepted"
    assert _parameter_result(mod, ":label", ()) == "forbidden construct"
    assert _parameter_result(mod, "x\n-- c\n:label", ("label",)) == "accepted"
    assert _parameter_result(mod, "/* :hidden */:label", ("label",)) == "accepted"
    assert _parameter_result(mod, "':label'", ()) == "accepted"
    assert _parameter_result(mod, '":label"', ()) == "accepted"
    assert _parameter_result(mod, ":label Z", ("label",)) == "accepted"
    assert _parameter_result(mod, "::_label", ()) == "accepted"
    with pytest.raises(StoreRefusal) as open_block:
        mod._parameters(_parameter_spec("/*", ()))
    full_message(open_block.value, "parse invalid")
    assert raised_in(open_block, "_parameters")


def test_cast_word_scanner_accepts_one_of_the_four() -> None:
    """CAST type words are read from the text, including a nested cast."""
    mod = _mod()
    mod._cast_words("SELECT CAST(p.amount AS INTEGER) FROM t AS p")
    mod._cast_words("CAST(CAST(p.amount AS TEXT) AS BIGINT)")
    mod._cast_words("SELECT p.unit_id FROM t AS p")
    with pytest.raises(StoreRefusal) as bare:
        mod._cast_words("CAST p.amount")
    full_message(bare.value, "forbidden construct")
    assert raised_in(bare, "_one_cast")
    with pytest.raises(StoreRefusal) as kind:
        mod._cast_words("CAST(p.amount AS INT4)")
    full_message(kind.value, "forbidden construct")
    assert raised_in(kind, "_require_cast_word")
    with pytest.raises(StoreRefusal) as note:
        mod._cast_words("CAST(p.amount AS /*c*/ INTEGER)")
    full_message(note.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as trail:
        mod._cast_words("CAST(p.amount AS INTEGER EXTRA)")
    full_message(trail.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as missing:
        mod._cast_words("CAST(p.amount)")
    full_message(missing.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as open_paren:
        mod._cast_words("CAST(p.amount AS INTEGER")
    full_message(open_paren.value, "parse invalid")
    assert raised_in(open_paren, "_match_paren")


def test_last_as_match_paren_and_one_cast_indexes() -> None:
    """Indexes come from the cast scanner, not from the surrounding statement."""
    mod = _mod()
    assert mod._last_as("p.amount AS INTEGER") == 9
    assert mod._last_as("CAST(p.amount AS TEXT) AS BIGINT") == 23
    assert mod._last_as("p.amount") is None
    assert mod._match_paren("(ab)", 0) == 3
    assert mod._match_paren("x(a(b)c)y", 1) == 7
    assert mod._one_cast("CAST(p.amount AS TEXT) tail", 0) == 22
    assert mod._skip_space("\n\t x", 0) == 3


def test_require_cast_word_refuses_a_comment_between_as_and_the_type() -> None:
    """A comment where the type word should be is its own refusal."""
    mod = _mod()
    mod._require_cast_word("p.amount AS TEXT")
    with pytest.raises(StoreRefusal) as commented:
        mod._require_cast_word("p.amount AS -- note\nTEXT")
    full_message(commented.value, "forbidden construct")
    assert raised_in(commented, "_require_cast_word")
    with pytest.raises(StoreRefusal) as blocked:
        mod._require_cast_word("p.amount AS /*c*/ TEXT")
    full_message(blocked.value, "forbidden construct")


def _parameter_spec(text: str, names: tuple[str, ...]) -> Any:
    from eii_product.store.registry import ParamSpec, QuerySpec

    return QuerySpec(
        "syn_params",
        tuple(ParamSpec(name, "text") for name in names),
        (),
        (),
        text,
        "ab",
        (),
    )


def _parameter_result(mod: Any, text: str, names: tuple[str, ...]) -> str:
    try:
        mod._parameters(_parameter_spec(text, names))
    except StoreRefusal as caught:
        return str(caught)
    return "accepted"
