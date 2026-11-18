"""Exact school-query frame and context refusals; invented URLs, no connection."""

import ssl
from urllib.parse import urlencode

import pytest
from custodian.tests import test_certificate_pins_survivors_1 as pin_tests

from eii_custodian.publicdata.fetch import page_requests
from eii_custodian.publicdata.fetch.page_schema import SCHOOL_FIELDS
from eii_custodian.publicdata.fetch.transport import TransportFault

SCHOOL = (
    "https://myschools.edu.gov.qa/SYN/arcgis/rest/services"
    "/PrivateSchoolsView/FeatureServer/0/query"
)
OTHER = "https://www.data.gov.qa/SYN-page"

invented_certs = pin_tests.invented_certs
isolated_trust = pin_tests.isolated_trust


def test_default_context_trust_is_only_the_invented_root(invented_certs):
    context = ssl.create_default_context()
    assert context.get_ca_certs(binary_form=True) == [invented_certs["root"]]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname


def count_pairs():
    return [("where", "1=1"), ("returnCountOnly", "true"), ("f", "json")]


def page_pairs(**changes):
    values = {
        "where": "1=1",
        "outFields": ",".join(SCHOOL_FIELDS),
        "orderByFields": "objectid",
        "returnGeometry": "true",
        "resultOffset": "0",
        "resultRecordCount": "1000",
        "f": "json",
    }
    values.update(changes)
    return [(key, value) for key, value in values.items() if value is not None]


def url(pairs, base=SCHOOL):
    return base + "?" + urlencode(pairs)


def refused(target):
    with pytest.raises(TransportFault) as caught:
        page_requests.check_target(target)
    # The closed refusal carries no URL text and no other kind.
    assert caught.value.kind == "blocked_host"
    assert caught.value.url == ""
    assert str(caught.value) == "blocked_host "


@pytest.mark.parametrize(
    "pairs",
    [
        count_pairs(),
        page_pairs(),
        page_pairs(resultRecordCount="1"),
        page_pairs(resultOffset="25", resultRecordCount="500"),
    ],
    ids=["count", "page-1000", "page-1", "page-offset"],
)
def test_exact_school_queries_pass_without_frame(pairs):
    assert page_requests.check_target(url(pairs)) is None


def test_exact_school_query_passes_inside_its_frame():
    target = url(page_pairs())
    with page_requests.page_requests((target,), {}):
        assert page_requests.check_target(target) is None


def test_frame_refuses_unlisted_url_with_closed_fault():
    with page_requests.page_requests((OTHER,), {}):
        refused(OTHER + "-unlisted")


@pytest.mark.parametrize(
    "pairs",
    [
        [("where", "1=1"), ("f", "xml"), ("returnCountOnly", "true")],
        [("where", "2=2"), ("returnCountOnly", "true"), ("f", "json")],
        [("returnCountOnly", "true"), ("f", "json")],
        [
            ("where", "1=1"),
            ("where", "1=1"),
            ("returnCountOnly", "true"),
            ("f", "json"),
        ],
        [*count_pairs(), ("SYN", "")],
        [*count_pairs(), ("resultOffset", "0")],
        page_pairs(f="JSON"),
        page_pairs(returnGeometry="false"),
        page_pairs(orderByFields="name"),
        page_pairs(outFields="objectid"),
        page_pairs(resultOffset="SYN"),
        page_pairs(resultOffset="٣"),
        page_pairs(resultRecordCount="٣"),
        page_pairs(resultRecordCount="SYN"),
        page_pairs(resultRecordCount="0"),
        page_pairs(resultRecordCount="1001"),
        page_pairs(resultRecordCount="2000"),
        page_pairs(SYN="1"),
        page_pairs(SYN=""),
        page_pairs(resultOffset=None),
    ],
)
def test_school_query_refusals(pairs):
    refused(url(pairs))


def test_school_query_refused_inside_its_frame():
    target = url(page_pairs(returnGeometry="false"))
    with page_requests.page_requests((target,), {}):
        refused(target)


def test_school_rule_binds_host_and_exact_path_only():
    loose = page_pairs(returnGeometry="false")
    # The same loose query is outside the school rule on another reviewed host.
    other_host = SCHOOL.replace("myschools.edu.gov.qa", "www.edu.gov.qa")
    assert page_requests.check_target(url(loose, other_host)) is None
    # A different path on the school host is outside the rule as well.
    assert page_requests.check_target(url(loose, SCHOOL + "-SYN")) is None
    # The exact path on the school host is checked even when the case of the
    # whole URL host is upper case: the host compares in its parsed lower form.
    refused(url(loose, SCHOOL.replace("myschools.edu.gov.qa", "MYSCHOOLS.EDU.GOV.QA")))


def test_full_chain_context_keeps_default_flags_without_partial_chain():
    expected = ssl.create_default_context().verify_flags
    expected &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    context = page_requests.page_context("www.data.gov.qa")
    assert context.verify_flags == expected
    assert not context.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
