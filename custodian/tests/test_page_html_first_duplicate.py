"""S2-P75: a snapshot page keeps the first value of a duplicate attribute."""

import pytest
from custodian.tests.test_s2_t29_live_shapes import classified, entry
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import page_acquire as acquire
from eii_custodian.publicdata.fetch.page_html import ShapeError, Tree
from eii_custodian.publicdata.fetch.page_records import PageError, parse_body


def refused(call) -> None:
    with pytest.raises(ShapeError) as error:
        call()
    assert error.value.args == ("schema_missing",)


def test_first_keeps_first_value_on_unprotected_tag() -> None:
    tree = Tree(
        b'<script id="syn-a" id="syn-b">x</script>', duplicate_attributes="first"
    )
    assert tree.root.one("script").attrs == {"id": "syn-a"}


@pytest.mark.parametrize("tag", ["input", "form", "meta", "base"])
def test_first_still_refuses_duplicate_on_protected_tag(tag: str) -> None:
    markup = f'<{tag} data-syn="a" data-syn="b"></{tag}>'.encode()
    refused(lambda: Tree(markup, duplicate_attributes="first"))


def test_unknown_duplicate_option_refuses() -> None:
    refused(lambda: Tree(b"<p>x</p>", duplicate_attributes="SYN-later"))


def test_snapshot_render_keeps_first_value() -> None:
    body = b'<div><script id="syn-a" id="syn-b">SYN</script></div>'
    assert acquire._html_without_form_secrets(body) == (
        b'<div><script id="syn-a">SYN</script></div>'
    )


@pytest.mark.parametrize("tag", ["input", "form", "meta", "base"])
def test_snapshot_duplicate_on_protected_tag_refuses(tag: str) -> None:
    markup = f'<div><{tag} data-syn="a" data-syn="b"></{tag}><i>tail</i></div>'
    refused(lambda: acquire._html_without_form_secrets(markup.encode()))


def test_form_secret_still_stripped_when_sibling_has_duplicate() -> None:
    body = (
        b'<script id="syn-a" id="syn-b">SYN</script>'
        b'<input name="__RequestVerificationToken" value="SYN-token">'
        b"<p>keep</p>"
    )
    assert acquire._html_without_form_secrets(body) == (
        b'<script id="syn-a">SYN</script><p>keep</p>'
    )


def test_table_parser_duplicate_still_refuses_by_default() -> None:
    dec, body = classified()
    body = body.replace(
        b'<div class="page-content">',
        b'<div class="page-content" id="syn-a" id="syn-b">',
        1,
    )
    with pytest.raises(PageError) as error:
        parse_body(body, entry(dec, "monaqasat_classified"), dec)
    assert error.value.args == ("schema_missing",)


@given(
    tag=st.sampled_from(
        [
            "a",
            "base",
            "div",
            "form",
            "img",
            "input",
            "meta",
            "p",
            "script",
            "span",
            "table",
        ]
    ),
    name=st.sampled_from(["class", "data-syn", "href", "id", "name"]),
)
@example(tag="script", name="id")
def test_first_duplicate_policy_over_closed_tag_space(tag: str, name: str) -> None:
    markup = f'<{tag} {name}="syn-a" {name}="syn-b"></{tag}>'.encode()
    if tag in {"base", "form", "input", "meta"}:
        refused(lambda: Tree(markup, duplicate_attributes="first"))
    else:
        node = Tree(markup, duplicate_attributes="first").root.one(tag)
        assert node.attrs == {name: "syn-a"}
