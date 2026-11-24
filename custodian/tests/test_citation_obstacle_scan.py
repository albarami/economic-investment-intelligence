"""S2-P75 rounds 2 to 4: a sign-in link word never refuses a citation page
(L-1615); an admitted bare sign-in wall still refuses the landmark excerpt
check as `excerpt_absent` (advisor condition of L-1617, decision 0093); a
citation page requires exactly status 200 and shares the one first-wins
tree of the form-secret strip (L-1619)."""

import html
import json
from dataclasses import replace

import pytest
from custodian.tests.fixtures.heights import invented
from custodian.tests.test_page_acquire_survivors_1 import refused, run
from custodian.tests.test_publicdata_heights import _cited_page, _landmark_document
from custodian.tests.test_s2_t29_live_shapes import declaration, embedded, entry
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.fc_register.acquire import obstacle
from eii_custodian.publicdata.fetch import page_acquire as acquire
from eii_custodian.publicdata.fetch.page_html import Tree
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.heights import landmarks
from eii_custodian.publicdata.heights.model import HeightError

NEUTRAL = b"<html><body><p>SYN landmark page</p></body></html>"
SIGNIN = (
    b'<html><body><a href="/syn-login">Sign in</a>'
    b"<p>SYN landmark page</p></body></html>"
)


def cited(tmp_path, dec, body, *, send=None):
    return run(tmp_path, dec, body, row=entry(dec, "landmark_syn"), send=send)


def test_citation_signin_link_alone_is_admitted(tmp_path):
    dec = declaration("citation_snapshot", {}, [])
    result = cited(tmp_path, dec, SIGNIN)
    assert json.loads(result.body)["rows"] == []


@pytest.mark.parametrize(
    "fragment",
    [
        b'<input type="password">',
        b'<input TYPE="PASSWORD">',
        b'<form><input type="Password" name="pw"></form>',
    ],
)
def test_citation_password_input_refuses_unavailable(tmp_path, fragment):
    dec = declaration("citation_snapshot", {}, [])
    refused("unavailable", lambda: cited(tmp_path, dec, NEUTRAL + fragment))


@pytest.mark.parametrize("marker", [b"robot check", b"ROBOT CHECK", b"paywall"])
def test_citation_refusal_body_word_refuses(tmp_path, marker):
    dec = declaration("citation_snapshot", {}, [])
    refused("unavailable", lambda: cited(tmp_path, dec, SIGNIN + marker))


def test_citation_text_input_and_signin_admitted(tmp_path):
    dec = declaration("citation_snapshot", {}, [])
    result = cited(tmp_path, dec, SIGNIN + b'<input type="text" name="q">')
    assert json.loads(result.body)["rows"] == []


def test_citation_password_in_script_or_comment_is_admitted(tmp_path):
    dec = declaration("citation_snapshot", {}, [])
    body = (
        NEUTRAL
        + b"<script>var s = \"<input type='password'>\";</script>"
        + b'<!-- <input type="password"> -->'
    )
    assert json.loads(cited(tmp_path, dec, body).body)["rows"] == []


def test_citation_http_fault_refuses_http_status(tmp_path):
    dec = declaration("citation_snapshot", {}, [])

    def send(url):
        raise TransportFault("http", url, status=403)

    refused("http_status", lambda: cited(tmp_path, dec, b"", send=send))


@pytest.mark.parametrize("status", [203, 206, None])
def test_citation_status_not_200_refuses_http_status(tmp_path, status):
    """Round 4 (L-1619): a citation page requires exactly status 200."""
    dec = declaration("citation_snapshot", {}, [])

    def send(u):
        return Response(u, SIGNIN, (), status=status)

    refused("http_status", lambda: cited(tmp_path, dec, b"", send=send))


def test_non_citation_status_206_is_unchanged(tmp_path):
    """Control: a successful non-200 on another kind keeps today's outcome."""
    dec, body, record = embedded()
    result = run(
        tmp_path,
        dec,
        body,
        send=lambda u: Response(u, body, (), status=206),
    )
    assert json.loads(result.body)["rows"] == [
        {
            "title": "SYN > event",
            "start": "2031-02-03",
            "end": "2031-02-04",
            "published_record": record,
        }
    ]


def test_citation_page_shares_one_first_wins_tree(tmp_path, monkeypatch):
    """Round 4 (L-1619): password detection uses the strip parse's tree."""
    calls = []
    tree_class = acquire.Tree

    def counted(body, **kwargs):
        calls.append(kwargs.get("duplicate_attributes", "refuse"))
        return tree_class(body, **kwargs)

    monkeypatch.setattr(acquire, "Tree", counted)
    dec = declaration("citation_snapshot", {}, [])
    cited(tmp_path, dec, NEUTRAL)
    assert calls == ["first"]


def test_citation_unparseable_page_still_refuses(tmp_path):
    dec = declaration("citation_snapshot", {}, [])
    refused("schema_missing", lambda: cited(tmp_path, dec, b"<div>Sign in"))


def test_citation_duplicate_type_on_input_refuses(tmp_path):
    dec = declaration("citation_snapshot", {}, [])
    refused(
        "schema_missing",
        lambda: cited(tmp_path, dec, NEUTRAL + b'<input type="text" type="password">'),
    )


def test_non_citation_signin_still_refuses(tmp_path):
    dec, body, _ = embedded()
    refused(
        "unavailable",
        lambda: run(tmp_path, dec, body + b"Sign in"),
    )
    assert obstacle(b"<p>Sign in</p>") == "credentials"
    assert obstacle(b"<p>SIGN-IN</p>") == "credentials"


SIGNIN_WALL = (
    b'<html><body><a href="/syn-login">Sign in</a>'
    b"<button>Sign in with your account</button></body></html>"
)


def _wall_citation(tmp_path, monkeypatch, body):
    cache, row, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    digest = invented.store(cache, row, body, publisher=row.publisher)
    return cache, replace(
        rows[0], citation=replace(rows[0].citation, page_sha256=digest)
    )


def test_signin_wall_without_excerpt_refuses_excerpt_absent(tmp_path, monkeypatch):
    """Round 3 (L-1617): an admitted sign-in wall still misses the excerpt."""
    dec = declaration("citation_snapshot", {}, [])
    assert json.loads(cited(tmp_path, dec, SIGNIN_WALL).body)["rows"] == []
    cache, wall_row = _wall_citation(tmp_path, monkeypatch, SIGNIN_WALL)
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, (wall_row,))
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "excerpt_absent",
    )


def test_signin_wall_with_excerpt_is_not_refused(tmp_path, monkeypatch):
    """Control: the same wall plus the row's own excerpt text verifies."""
    dec = declaration("citation_snapshot", {}, [])
    assert json.loads(cited(tmp_path, dec, SIGNIN_WALL).body)["rows"] == []
    excerpt = _landmark_document()["entries"][0]["citation"]["height_excerpt"]
    body = SIGNIN_WALL.replace(b"</body>", ("<p>" + excerpt + "</p></body>").encode())
    cache, wall_row = _wall_citation(tmp_path, monkeypatch, body)
    assert landmarks.verify_landmark_receipts(cache, (wall_row,)) is None


PASSWORD_FRAGMENTS = [
    '<input type="password">',
    '<input TYPE="PASSWORD">',
    '<form><input type="Password" name="p"></form>',
]
REFUSAL_WORDS = ["robot check", "ROBOT CHECK", "paywall", "PayWall"]
SIGNIN_FRAGMENTS = [
    '<a href="/syn">Sign in</a>',
    "sign-in",
    "SIGN IN to continue",
]


@given(
    password=st.booleans(),
    refusal=st.booleans(),
    signin=st.booleans(),
    pad=st.text(alphabet="0123456789 \n", max_size=40),
    pfrag=st.sampled_from(PASSWORD_FRAGMENTS),
    rword=st.sampled_from(REFUSAL_WORDS),
    sfrag=st.sampled_from(SIGNIN_FRAGMENTS),
)
def test_citation_refuses_iff_password_or_refusal_word(
    password, refusal, signin, pad, pfrag, rword, sfrag
):
    parts = ["<div>", pad]
    if password:
        parts.append(pfrag)
    if refusal:
        parts.append("<span>" + rword + "</span>")
    if signin:
        parts.append(sfrag)
    parts.append("</div>")
    expected = "refusal_body" if refusal else "credentials" if password else None
    body = "".join(parts).encode()
    root = Tree(body, duplicate_attributes="first").root
    assert acquire._citation_obstacle(root) == expected


def citation_reason(body):
    return acquire._citation_obstacle(acquire._form_secret_tree(body))


@pytest.mark.parametrize("marker", ["paywall", "robot check", "PaYwAlL", "ROBOT CHECK"])
@pytest.mark.parametrize(
    "hidden",
    [
        '<script>const syn = "{}";</script>',
        '<meta name="syn-analytics-{}">',
        '<div data-syn="{}">SYN page</div>',
        "<style>/* {} */</style>",
        "<noscript><div>{}</div></noscript>",
        "<template><div>{}</div></template>",
        "<head><title>{}</title></head>",
        "<!-- {} -->",
    ],
)
def test_citation_hidden_obstacle_words_are_admitted(tmp_path, marker, hidden):
    body = ("<html>" + hidden.format(marker) + "<body>SYN page</body></html>").encode()
    assert citation_reason(body) is None
    dec = declaration("citation_snapshot", {}, [])
    assert json.loads(cited(tmp_path, dec, body).body)["rows"] == []


@pytest.mark.parametrize(
    "fragment",
    [
        "<p>paywall</p>",
        "<div>robot check</div>",
        "<p>PaYwAlL</p>",
        "<div>RoBoT ChEcK</div>",
        "<p>pay&#119;all</p>",
        "<div>robot&#32;check</div>",
        "<p>pay<span>wall</span></p>",
        "<div>robot <span>check</span></div>",
        "<p>pay<!-- SYN -->wall</p>",
        "<p>pay<template>ignored</template>wall</p>",
    ],
)
def test_citation_visible_obstacle_reason_and_acquisition_refusal(tmp_path, fragment):
    body = ("<html><body>" + fragment + "</body></html>").encode()
    assert citation_reason(body) == "refusal_body"
    dec = declaration("citation_snapshot", {}, [])
    refused("unavailable", lambda: cited(tmp_path, dec, body))


def test_citation_password_reason_is_unchanged(tmp_path):
    body = NEUTRAL + b'<input type="password">'
    assert citation_reason(body) == "credentials"
    dec = declaration("citation_snapshot", {}, [])
    refused("unavailable", lambda: cited(tmp_path, dec, body))


@pytest.mark.parametrize("marker", ["paywall", "robot check"])
@pytest.mark.parametrize(
    "hidden", ['<script>"{}"</script>', '<div data-syn="{}">SYN</div>']
)
def test_non_citation_obstacle_still_raw_scans(tmp_path, marker, hidden):
    fragment = hidden.format(marker).encode()
    assert obstacle(fragment) == "refusal_body"
    dec, body, _ = embedded()
    refused("unavailable", lambda: run(tmp_path, dec, body + fragment))


GENERATED_PAGE_TEXT = st.recursive(
    st.one_of(
        st.text(max_size=40).map(html.escape),
        st.sampled_from(
            ["", "paywall", "ROBOT CHECK", '<input type="password">', "pay<b>wall</b>"]
        ),
    ),
    lambda child: st.tuples(
        st.sampled_from(["div", "p", "span", "template", "noscript", "head"]),
        st.lists(child, max_size=3),
    ).map(lambda pair: f"<{pair[0]}>" + "".join(pair[1]) + f"</{pair[0]}>"),
    max_leaves=12,
)


@given(
    fragment=GENERATED_PAGE_TEXT,
    marker=st.sampled_from(REFUSAL_WORDS),
    injection=st.sampled_from(["script", "attribute", "meta"]),
)
def test_citation_hidden_word_injection_preserves_outcome(fragment, marker, injection):
    baseline = "<html><head></head><body><div>" + fragment + "</div></body></html>"
    if injection == "script":
        injected = baseline.replace("</body>", f'<script>"{marker}"</script></body>')
    elif injection == "attribute":
        injected = baseline.replace("<div>", f'<div data-syn="{marker}">', 1)
    else:
        injected = baseline.replace("</head>", f'<meta name="syn-{marker}"></head>', 1)
    expected = citation_reason(baseline.encode())
    assert expected in {None, "refusal_body", "credentials"}
    assert citation_reason(injected.encode()) == expected
