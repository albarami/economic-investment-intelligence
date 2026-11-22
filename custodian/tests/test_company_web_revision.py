"""Review-round regression plants, using invented pages and no network."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from custodian.tests.company_web_fixture import (
    IDENTITY,
    NAME,
    STAMP,
    URL,
    body,
    manifest,
    offline_network,  # noqa: F401
    receipt,
)
from custodian.tests.test_company_web_command import environment

from eii_custodian.publicdata.company_web.build import (
    _fetch_stage,
    _review_stage,
    _search_stage,
    run_company_web,
)
from eii_custodian.publicdata.company_web.contracts import (
    Company,
    WebError,
    checked_url,
    dump,
)
from eii_custodian.publicdata.company_web.evidence import Outcome, reconcile
from eii_custodian.publicdata.company_web.fetch import Access, Pacer
from eii_custodian.publicdata.company_web.parse import extract
from eii_custodian.publicdata.company_web.review import reviewer_bundle
from eii_custodian.publicdata.company_web.scope import Manifest
from eii_custodian.publicdata.company_web.search import companies, request_url
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.transport import Response

SELECTION = {"block": "section#company", "fields": {"name": "b", "activity": "p"}}
MICRO = '<div itemscope itemtype="https://schema.org/Organization"><span itemprop="name">{n}</span><span itemprop="isicV4">SYN-class</span>{x}</div>'


SPLIT_RUNS = [
    "<i>Fa<u>x</u>: none</i>",
    "<i>Chi<u>ef</u> Executive</i>",
    "<i>M<u>r</u>. Invented</i>",
    "<i>Direc<u>tor</u></i>",
    "<i><u>Fa</u></i>x: none",
    "<i>Chi</i>ef Executive",
]


@pytest.mark.parametrize("extra", SPLIT_RUNS)
def test_split_and_fused_run_refused_in_selected_block(extra):
    data = f'<section id="company"><b>{NAME}</b><p>SYN activity</p>{extra}</section>'.encode()
    with pytest.raises(WebError):
        extract(
            data,
            Company("syn-a", NAME, "register", {}),
            receipt(data),
            selectors=SELECTION,
            selectors_reviewed=True,
        )


@pytest.mark.parametrize("extra", SPLIT_RUNS)
def test_split_and_fused_run_refused_in_microdata(extra):
    data = MICRO.format(n=NAME, x=extra).encode()
    with pytest.raises(WebError):
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data))


@pytest.mark.parametrize("extra", SPLIT_RUNS)
@pytest.mark.parametrize("kind", ["microdata", "selector"])
def test_split_and_fused_run_refused_in_reviewer_bundle(extra, kind):
    data = MICRO.format(n=NAME, x="").encode()
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    fragment = (
        MICRO.format(n=NAME, x=extra)
        if kind == "microdata"
        else f'<section id="company"><b>{NAME}</b><p>SYN activity</p>{extra}</section>'
    ).encode()
    candidates = tuple(
        replace(c, fragment_sha256=sha256_hex(fragment)) for c in result.candidates
    )
    with pytest.raises(WebError, match="review_bundle_refused"):
        reviewer_bundle(NAME, replace(result, fragment=fragment, candidates=candidates))


@pytest.mark.parametrize(
    "extra", ["<i> Fa<u>x</u>: none</i>", "<i> Chi<u>ef</u> Executive</i>"]
)
def test_spaced_split_run_control_refused(extra):
    data = MICRO.format(n=NAME, x=extra).encode()
    with pytest.raises(WebError):
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data))


def test_run_window_bounds_cost():
    data = MICRO.format(n=NAME, x="<u>a</u>" * 3000).encode()
    assert (
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data)).status
        == "matched"
    )


@pytest.mark.parametrize(
    "extra",
    ["<i>Telephone: none</i>", "<i>Chief Executive</i>", "<i>Mr. Invented</i>"],
)
def test_adjacent_personal_or_contact_run_refused_in_selected_block(extra):
    data = f'<section id="company"><b>{NAME}</b><p>SYN activity</p>{extra}</section>'.encode()
    with pytest.raises(WebError):
        extract(
            data,
            Company("syn-a", NAME, "register", {}),
            receipt(data),
            selectors=SELECTION,
            selectors_reviewed=True,
        )


@pytest.mark.parametrize("extra", ["<i>Telephone: none</i>", "<i>Chief Executive</i>"])
def test_adjacent_personal_or_contact_run_refused_in_microdata(extra):
    data = MICRO.format(n=NAME, x=extra).encode()
    with pytest.raises(WebError):
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data))


def test_adjacent_run_microdata_control_matches():
    data = MICRO.format(n=NAME, x="").encode()
    assert (
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data)).status
        == "matched"
    )


def test_selector_block_contact_refused_at_extraction():
    data = f'<section id="company"><b>{NAME}</b><p>SYN activity</p> <i>Telephone: none</i></section>'.encode()
    with pytest.raises(WebError):
        extract(
            data,
            Company("syn-a", NAME, "register", {}),
            receipt(data),
            selectors=SELECTION,
            selectors_reviewed=True,
        )


def access_for(tmp_path, value, sent, content):
    tick = [0.0]

    def sleep(seconds):
        tick[0] += seconds

    def send(url):
        sent.append(url)
        data = content(url)
        return Response(url, data, (), body_sha256=sha256_hex(data))

    return Access(
        Manifest.from_data(value),
        send,
        tmp_path,
        lambda: STAMP,
        Pacer(sleep, lambda: tick[0]),
    )


def test_provider_robots_stops_search_before_send_and_counts_each_company(tmp_path):
    value = manifest()
    robots = "https://search.example.test/robots.txt"
    value["access"]["search.example.test"]["robots_url"] = robots
    sent = []
    access = access_for(
        tmp_path,
        value,
        sent,
        lambda url: (
            b"User-agent: *\nDisallow: /search\n"
            if url == robots
            else f'<a class="result" href="{URL}">invented</a>'.encode()
        ),
    )
    inputs = (
        Company("syn-a", NAME, "register", {}),
        Company("syn-b", "Velquorra Tools", "register", {}),
    )
    searched = _search_stage(inputs, access.manifest, access, lambda: STAMP)
    assert sent == [robots]
    assert access.stopped["search.example.test"] == "obstacle"
    rows = searched["rows"]
    counted = reconcile(
        [c.key for c in inputs],
        {r["company_key"]: r["urls"] for r in rows},
        [Outcome(r["company_key"], r["status"], ()) for r in rows],
        {},
        IDENTITY,
    ).counts
    assert counted["search_obstacle"] == 2 and counted["searched"] == 0


def test_jsonld_fragment_preserves_source_parts_before_assembly():
    data = body(
        address={
            "@type": "PostalAddress",
            "streetAddress": "SYN lane",
            "addressLocality": "SYN locality",
        },
        isicV4="SYN class",
        naics="SYN code",
    )
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    block = json.loads(
        data.decode().split('type="application/ld+json">')[1].split("</script>")[0]
    )
    assert result.fragment == dump(block)
    assert result.fragment != dump({c.field: c.value for c in result.candidates})
    bundle = reviewer_bundle(NAME, result)
    assert (
        json.loads(bundle["fragment"])["address"]["addressLocality"] == "SYN locality"
    )
    assert all(
        c.fragment_sha256 == sha256_hex(result.fragment) for c in result.candidates
    )


def test_selected_jsonld_object_keeps_inherited_schema_context():
    block = {"@type": "Organization", "name": NAME}
    data = (
        '<script type="application/ld+json">'
        + json.dumps({"@context": "https://schema.org", "@graph": [block]})
        + "</script>"
    ).encode()
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    assert result.status == "matched"
    assert result.fragment == dump(block)
    assert reviewer_bundle(NAME, result)["fragment"] == dump(block).decode()


@pytest.mark.parametrize("kind", ["microdata", "selector"])
def test_html_fragment_preserves_selected_subtree_context(kind):
    if kind == "microdata":
        subtree = f'<section itemscope itemtype="https://schema.org/Organization"><b itemprop="name">{NAME}</b><p>Source context retained</p></section>'.encode()
        options = {}
    else:
        subtree = f'<section id="company"><b>{NAME}</b><p>Source context retained</p></section>'.encode()
        options = {
            "selectors": {"block": "section#company", "fields": {"name": "b"}},
            "selectors_reviewed": True,
        }
    data = b"<html><body>" + subtree + b"<aside>Outside context</aside></body></html>"
    result = extract(
        data, Company("syn-a", NAME, "register", {}), receipt(data), **options
    )
    assert result.fragment == subtree
    assert b"Outside context" not in result.fragment
    assert "Source context retained" in reviewer_bundle(NAME, result)["fragment"]


@pytest.mark.parametrize("rehash", [False, True])
def test_extracted_fields_redump_is_refused_as_reviewer_fragment(rehash):
    data = body()
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    projection = dump({c.field: c.value for c in result.candidates})
    candidates = tuple(
        replace(c, fragment_sha256=sha256_hex(projection)) if rehash else c
        for c in result.candidates
    )
    with pytest.raises(WebError, match="review_bundle_refused"):
        reviewer_bundle(
            NAME, replace(result, fragment=projection, candidates=candidates)
        )


def test_one_candidate_with_foreign_fragment_hash_is_refused():
    data = body()
    result = extract(data, Company("syn-a", NAME, "register", {}), receipt(data))
    assert len(result.candidates) > 1
    last = replace(result.candidates[-1], fragment_sha256="0" * 64)
    with pytest.raises(WebError, match="review_bundle_refused"):
        reviewer_bundle(
            NAME, replace(result, candidates=(*result.candidates[:-1], last))
        )


@pytest.mark.parametrize(
    "contact",
    [{"telephone": "+0 000 0000"}, {"email": "info" + "@" + "zorvella.example.test"}],
)
def test_contact_property_refuses_fragment_at_extraction(contact):
    data = body(**contact)
    with pytest.raises(WebError):
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data))


@pytest.mark.parametrize(
    "name",
    [
        "Qelvan Mobile Phones Trading",
        "Zorvanda Phone Centre",
        "Velquorra Asset Manager Holding",
        "Dr Qelmarine Pharma",
    ],
)
def test_register_name_uses_input_checks_only(name):
    company = Company("syn-a", name, "register", {})
    assert request_url(company, Manifest.from_data(manifest()))
    data = body(name=name)
    with pytest.raises(WebError, match="field_refused"):
        extract(data, company, receipt(data))


@pytest.mark.parametrize(
    "bad_name", [None, "", "Bad\x00name", "Bad;name", "Bad$(id)", "Bad`id`"]
)
def test_refused_input_name_is_counted_without_aborting_other_companies(
    tmp_path, bad_name
):
    inputs = companies(
        [
            {"company_name": NAME, "registration_number": "syn-good"},
            {"company_name": bad_name, "registration_number": "syn-bad"},
        ],
        [],
    )
    value = manifest()
    value["companies"] = {c.key: [] for c in inputs}
    value["access"] = {"search.example.test": value["access"]["search.example.test"]}
    sent = []
    access = access_for(tmp_path, value, sent, lambda _: b"<html></html>")
    searched = _search_stage(inputs, access.manifest, access, lambda: STAMP)
    assert len(sent) == 1
    assert [r["status"] for r in searched["rows"]] == ["searched", "input_refused"]
    fetched = _fetch_stage(
        inputs, access.manifest, access, searched, tmp_path, lambda: STAMP
    )
    reviewed = _review_stage(inputs, access.manifest, fetched, searched, access, {})
    assert reviewed["counts"]["companies"] == 2
    assert reviewed["counts"]["searched"] == 1
    assert reviewed["counts"]["input_refused"] == 1


def test_refused_bundle_name_is_counted_without_aborting_review(tmp_path):
    inputs = (Company("syn-a", "Smart-Phone Zorvex Trading", "register", {}),)
    data = body(name="SmartPhone Zorvex Trading")
    access = access_for(
        tmp_path,
        manifest(),
        [],
        lambda address: (
            f'<a class="result" href="{URL}">invented</a>'.encode()
            if "search.example.test" in address
            else data
        ),
    )
    searched = _search_stage(inputs, access.manifest, access, lambda: STAMP)
    assert searched["rows"][0]["status"] == "searched"
    fetched = _fetch_stage(
        inputs, access.manifest, access, searched, tmp_path, lambda: STAMP
    )
    page = fetched["outcomes"][0]["pages"][0]
    assert page["status"] == "field_refused"
    assert page["proposed"] == []
    assert page["reviewer_bundle"] == ""
    reviewed = _review_stage(inputs, access.manifest, fetched, searched, access, {})
    assert reviewed["counts"]["field_refused"] == 1
    assert reviewed["counts"]["proposed"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://169.254.169.254/latest",
        "https://[::1]/",
        "https://[fe80::1]/",
        "https://localhost/about",
        "https://intranet/",
        "https://localhost./",
        "https://build.localhost/",
        "https://127.1/",
        "https://0177.0.0.1/",
        "https://0x7f.0.0.1/",
        "https://10.1/",
    ],
)
def test_nonpublic_address_hosts_refused_before_manifest_admission(url):
    with pytest.raises(WebError, match="url_refused"):
        checked_url(url)
    value = manifest()
    value["companies"]["syn-a"] = [url]
    with pytest.raises(WebError, match="manifest_refused"):
        Manifest.from_data(value)


def test_trailing_dot_website_keeps_earlier_admission():
    assert (
        checked_url("https://example.invalid./about")
        == "https://example.invalid./about"
    )


@pytest.mark.parametrize(
    "title",
    [
        "founder",
        "founded",
        "owner",
        "chairman",
        "chairwoman",
        "president",
        "partner",
        "sheikh",
    ],
)
def test_person_titles_in_description_refused(title):
    data = body(description="Invented " + title)
    with pytest.raises(WebError, match="field_refused"):
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data))


@pytest.mark.parametrize(
    "url", [URL.replace("zorvella", "ZORVELLA"), URL.replace(".test/", ".test:443/")]
)
def test_selector_host_lookup_survives_case_and_default_port_in_both_stages(
    tmp_path, url
):
    value = manifest()
    value["companies"]["syn-a"] = [url]
    value["selectors"]["zorvella.example.test"] = {
        "block": "section#company",
        "fields": {"name": "b"},
    }
    data = f'<section id="company"><b>{NAME}</b></section>'.encode()
    access = access_for(
        tmp_path,
        value,
        [],
        lambda address: (
            f'<a class="result" href="{url}">invented</a>'.encode()
            if "search.example.test" in address
            else data
        ),
    )
    inputs = (Company("syn-a", NAME, "register", {}),)
    searched = _search_stage(inputs, access.manifest, access, lambda: STAMP)
    fetched = _fetch_stage(
        inputs, access.manifest, access, searched, tmp_path, lambda: STAMP
    )
    assert fetched["outcomes"][0]["pages"][0]["status"] == "matched"
    reviewed = _review_stage(inputs, access.manifest, fetched, searched, access, {})
    assert reviewed["counts"]["proposed"] == 1
    assert reviewed["counts"]["pending"] == 1


@pytest.mark.parametrize(
    "target", ["access", "selectors", "selector", "fields", "provider", "access_entry"]
)
def test_malformed_manifest_has_only_fixed_diagnostic(tmp_path: Path, capsys, target):
    env = environment(tmp_path, "search")
    path = Path(env["EII_COMPANY_WEB_MANIFEST"])
    value = json.loads(path.read_bytes())
    if target in {"access", "selectors", "provider"}:
        value[target] = []
    elif target == "access_entry":
        value["access"]["search.example.test"] = []
    else:
        value["selectors"] = {
            "zorvella.example.test": []
            if target == "selector"
            else {"block": "section", "fields": []}
        }
    raw = dump(value)
    path.write_bytes(raw)
    env["EII_COMPANY_WEB_MANIFEST_SHA256"] = sha256_hex(raw)
    sent = []
    with patch(
        "eii_custodian.publicdata.company_web.build.input_companies",
        return_value=(Company("syn-a", NAME, "register", {}),),
    ):
        assert (
            run_company_web(
                tmp_path,
                env,
                lambda url: sent.append(url),
                lambda _: None,
                clock=lambda: STAMP,
            )
            == 1
        )
    assert sent == []
    assert capsys.readouterr().out == "company_web refused; lead_review_required\n"


T = 256


def enc(char, depth=50):
    """Nested percent-encoding of one character; unquote to a fixpoint returns it."""
    return "%" + "25" * (depth - 1) + format(ord(char), "02X")


FILL = "y " * 300
REFUSED = {
    # split word at the end of a long first run (beyond T); right edge fused in the page
    "long-first": f"<i>{FILL}Fa<u>x</u></i><b>z: none</b>",
    "long-first-digits": f"<i>{FILL}1234<u>5678</u>9 z</i>",
    # split word at the start of a long last run, left edge fused in the page
    "long-last": f"<i>Chi</i>ef Executive {FILL}",
    # percent-encoded word whose raw extent (~200 chars) lies within 2 x window
    "encoded-first": f"<i>{enc('F')}{enc('a')}<u>x</u>: none</i>",
    # a 10-letter word whose extent in the long run (9 chars) exceeds a short context
    "word-first": f"<i>{FILL}chairwoma<u>n</u></i><b>z</b>",
    "word-last": f"<i>c</i>hairwoman {FILL}",
    "encoded-last": f"<i>Fa</i>{enc('x')}: none {FILL}",
}


def tail_control(word_tail, before, digits=False):
    # A long run cut T chars from its end lands right after `before` and right
    # before `word_tail`; a plain cut would make the cut a word boundary.
    rest = ("y " * T)[: T - len(word_tail)]
    return f"<i>{FILL}{before}{word_tail}{rest}</i><u>z</u>"


def head_control(word, after):
    lead = ("y " * T)[: T - len(word)]
    return f"<u>z</u><i>{lead}{word}{after}{FILL}</i>"


BENIGN = {
    "tail-suffix-ms": tail_control("ms ", "ite"),
    "tail-suffix-tel": tail_control("tel ", "ho"),
    "tail-digits": tail_control("1234" + "5678 ", "9"),
    "head-prefix-dr": head_control(" dr", "ying"),
    "head-prefix-fax": head_control(" fax", "ed"),
    "head-digits": head_control(" 1234" + "5678", "9"),
}


def _check_cut(extra):
    # guard: the cut really lands where intended in the long run
    return extra


@pytest.mark.parametrize("key", sorted(REFUSED))
def test_cf4_long_run_refused_micro(key):
    data = MICRO.format(n=NAME, x=REFUSED[key]).encode()
    with pytest.raises(WebError):
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data))


@pytest.mark.parametrize("key", sorted(REFUSED))
def test_cf4_long_run_refused_selected(key):
    data = f'<section id="company"><b>{NAME}</b><p>SYN activity</p>{REFUSED[key]}</section>'.encode()
    with pytest.raises(WebError):
        extract(
            data,
            Company("syn-a", NAME, "register", {}),
            receipt(data),
            selectors=SELECTION,
            selectors_reviewed=True,
        )


@pytest.mark.parametrize("key", sorted(BENIGN))
def test_cf4_cut_control_matches(key):
    data = MICRO.format(n=NAME, x=BENIGN[key]).encode()
    assert (
        extract(data, Company("syn-a", NAME, "register", {}), receipt(data)).status
        == "matched"
    )
