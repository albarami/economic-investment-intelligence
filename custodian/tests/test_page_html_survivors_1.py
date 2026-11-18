"""Mutation-killing tests for page_html HTML tree, selector and table guards."""

from __future__ import annotations

import pytest

from eii_custodian.publicdata.fetch.page_html import ShapeError, Tree, table_rows


def _exact_shape_error(fn) -> None:
    with pytest.raises(ShapeError) as caught:
        fn()
    assert caught.value.args == ("schema_missing",)


def test_node_text_concatenates_mixed_children_without_separator() -> None:
    tree = Tree(b"<p>SYN-a<span>SYN-b</span>SYN-c</p>")
    assert tree.root.one("p").text() == "SYN-aSYN-bSYN-c"


@pytest.mark.parametrize(
    "selector",
    ["div > span", "DIV", '*[id="syn"]', "div:first-child", ""],
)
def test_node_matches_rejects_non_closed_selector_with_exact_reason(
    selector: str,
) -> None:
    node = Tree(b'<div id="syn">x</div>').root.one("div")
    _exact_shape_error(lambda: node.matches(selector))


def test_node_matches_class_and_attribute_edges() -> None:
    # Kills #410: lstrip("XX.XX") would strip leading X from class Xsyn.
    plain_syn = Tree(b'<div class="syn">x</div>').root.one("div")
    x_syn = Tree(b'<div class="Xsyn">x</div>').root.one("div")
    assert x_syn.matches("div.Xsyn") is True
    assert plain_syn.matches("div.Xsyn") is False

    # Kills #411: fallback "XXXX" on absent class attribute would match div.XXXX.
    unclassed = Tree(b"<div>x</div>").root.one("div")
    assert unclassed.matches("div.XXXX") is False
    assert unclassed.matches("div") is True

    # Kills #412: attr is not None short-circuit would accept mismatched attribute value.
    wrong_attr = Tree(b'<a tabindex="0">x</a>').root.one("a")
    right_attr = Tree(b'<a tabindex="-1">x</a>').root.one("a")
    assert wrong_attr.matches('a[tabindex="-1"]') is False
    assert unclassed.matches('div[data-syn="1"]') is False
    assert right_attr.matches('a[tabindex="-1"]') is True


@pytest.mark.parametrize(
    "markup",
    [b"<div></div>", b"<div><span>1</span><span>2</span></div>"],
)
def test_node_one_requires_single_match_with_exact_reason(markup: bytes) -> None:
    root = Tree(markup).root
    _exact_shape_error(lambda: root.one("span"))


def test_tree_init_charrefs_root_tag_and_error_reasons() -> None:
    # Kills #414, #415 (convert_charrefs=True) and #416, #417 (root tag == "root").
    tree = Tree(b"<p>SYN &amp; &#38; &#x26;</p>")
    assert tree.root.tag == "root"
    assert tree.root.one("p").text() == "SYN & & &"

    # Kills #419, #420, #421 (invalid UTF-8 exact ShapeError("schema_missing")).
    _exact_shape_error(lambda: Tree(b"\xff\xfe"))

    # Kills #422, #423, #424 (unclosed element exact ShapeError("schema_missing")).
    _exact_shape_error(lambda: Tree(b"<div><span>unclosed"))

    # Kills #425, #426, #427 (duplicate attribute exact ShapeError("schema_missing")).
    _exact_shape_error(lambda: Tree(b'<div id="a" id="b">x</div>'))


@pytest.mark.parametrize(
    "void_tag",
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ],
)
def test_tree_void_elements_stay_leaf_siblings(void_tag: str) -> None:
    # Kills #428..#453: removing any void tag leaves self.current open and fails Tree.__init__
    # or nests subsequent siblings inside the void tag.
    tree = Tree(f'<div><{void_tag} data-syn="1"><span>after</span></div>'.encode())
    div = tree.root.one("div")
    children = div.nodes()
    assert [child.tag for child in children] == [void_tag, "span"]
    assert children[0].attrs == {"data-syn": "1"}
    assert children[0].children == []
    assert children[1].text() == "after"


def test_tree_self_closing_startendtag_for_non_void_and_void_elements() -> None:
    # Kills #454..#460: non-void self-closing tag inside a non-root parent must
    # attach to parent with its attributes and restore self.current to parent (not root or None).
    tree = Tree(b'<div><span id="syn-self" /><i>tail</i></div>')
    div = tree.root.one("div")
    assert [child.tag for child in div.nodes()] == ["span", "i"]
    assert div.one("span#syn-self").children == []
    assert div.one("i").text() == "tail"
    assert [child.tag for child in tree.root.nodes()] == ["div"]

    # Also cover void self-closing tag where handle_starttag did not advance self.current.
    tree_void = Tree(b'<div><br class="syn-br"/><i>tail</i></div>')
    div_void = tree_void.root.one("div")
    assert [child.tag for child in div_void.nodes()] == ["br", "i"]
    assert div_void.one("br.syn-br").children == []


def test_tree_endtag_unmatched_and_omitted_ancestor_close() -> None:
    # Kills #461: unmatched closing tag walks to root and stops cleanly without None crash.
    unmatched = Tree(b"<div>x</span></div></p>")
    assert unmatched.root.one("div").text() == "x"

    # Kills #462: closing outer tag when inner non-void tag omitted its end tag walks parent chain.
    omitted = Tree(b"<div><p><span>nested</div><b>after</b>")
    assert [n.tag for n in omitted.root.nodes()] == ["div", "b"]
    assert omitted.root.one("div > p > span").text() == "nested"
    assert omitted.root.one("b").text() == "after"


@pytest.mark.parametrize(
    "markup",
    [
        # Kills #463..#465: missing thead > tr or multiple thead > tr
        b"<table><tbody><tr><td>a</td></tr></tbody></table>",
        b"<table><thead><tr><th>H</th></tr><tr><th>H</th></tr></thead><tbody></tbody></table>",
        # Kills #466: non-th in thead or mismatched header text
        b"<table><thead><tr><td>H</td></tr></thead><tbody><tr><td>a</td></tr></tbody></table>",
        b"<table><thead><tr><th>WRONG</th></tr></thead><tbody><tr><td>a</td></tr></tbody></table>",
        # Kills #467: wrong cell count or non-td in tbody > tr
        b"<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>a</td><td>b</td></tr></tbody></table>",
        b"<table><thead><tr><th>H</th></tr></thead><tbody><tr><th>a</th></tr></tbody></table>",
        # Kills #468..#470: nested table, colspan != "1", rowspan != "1" (in head or body)
        b"<table><thead><tr><th>H</th></tr></thead><tbody><tr><td><table></table></td></tr></tbody></table>",
        b'<table><thead><tr><th rowspan="2">H</th></tr></thead><tbody><tr><td>a</td></tr></tbody></table>',
        b'<table><thead><tr><th>H</th></tr></thead><tbody><tr><td rowspan="2">a</td></tr></tbody></table>',
        b'<table><thead><tr><th>H</th></tr></thead><tbody><tr><td colspan="2">a</td></tr></tbody></table>',
    ],
)
def test_table_rows_structural_refusals_have_exact_reason(markup: bytes) -> None:
    table = Tree(markup).root.nodes()[0]
    _exact_shape_error(lambda: table_rows(table, ["H"]))
