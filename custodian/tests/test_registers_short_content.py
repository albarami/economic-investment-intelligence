"""S2-REGSHORT: invented short card names against ordinary build metadata."""

import pytest
from custodian.tests.test_registers import capture, commerce, inputs
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.provenance import Frame
from eii_custodian.publicdata.registers.validate import scan_content


@pytest.mark.parametrize("name", ["e", "re", "pub", "-", "Q", "QZ", "a b"])
def test_register_short_name_builds(tmp_path, name):
    current = (
        capture(files=inputs(rows=[commerce(name_en=name)])),
        capture("fc_register"),
    )
    built = build(tmp_path, "public_only", Frame(frozenset()), current, ())
    assert name in {row["name_en"] for row in built.tables["pub_register_company"]}


@pytest.mark.parametrize(
    "name,control,plant",
    [
        ("e", "register", "x e-y"),
        ("re", "register", "x re.y"),
        ("pub", "pub_register_company", "pub x"),
        ("Q", "Qword", "x Q"),
        ("QZ", "QZword", "x QZ"),
        ("a b", "a x b", "x a b"),
        ("a b", "a_b", "a-b"),
        ("-", "x-y", "-"),
        ("Zelp", "safe", "preZelpsuffix"),
    ],
)
def test_register_content_plant(name, control, plant):
    content = frozenset({name})
    scan_content({"unlisted": control}, content)
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        scan_content({"unlisted": plant}, content)


@pytest.mark.parametrize(
    "wrap",
    [lambda x: x, lambda x: x.encode(), lambda x: {x: None}],
    ids=["str", "bytes", "key"],
)
def test_register_short_content_paths(wrap):
    scan_content(wrap("register"), frozenset({"e"}))
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        scan_content(wrap("x e"), frozenset({"e"}))


# An independent character-walk oracle, including Unicode and underscore.
def words(text):
    result = []
    current = ""
    for char in text:
        if char.isalnum() or char == "_":
            current += char
        elif current:
            result.append(current)
            current = ""
    if current:
        result.append(current)
    return result


def refuses(text, value):
    try:
        scan_content(value, frozenset({text}))
    except RegisterError as error:
        assert str(error) == "register_content_egress"
        return True
    return False


@settings(database=None)
@given(
    st.text(alphabet="aQéع٢_ -.", min_size=1, max_size=8).filter(
        lambda text: sum(char.isalnum() for char in text) <= 3
    ),
    st.text(alphabet="aQéع٢_ -.", max_size=30),
)
def test_register_short_content_relation(text, value):
    if not any(char.isalnum() for char in text):
        expected = text == value
    else:
        needle, haystack = words(text), words(value)
        expected = any(
            haystack[i : i + len(needle)] == needle
            for i in range(len(haystack) - len(needle) + 1)
        )
    assert refuses(text, value) == expected
    assert refuses(text, text)


@settings(database=None)
@given(
    st.text(alphabet="aQéع٢", min_size=4, max_size=12),
    st.text(alphabet="aQéع٢_ -.", max_size=30),
)
def test_register_long_content_relation(text, value):
    assert refuses(text, value) == (text in value)
    assert refuses(text, "prefix" + text + "suffix")
