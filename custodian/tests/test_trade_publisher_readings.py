"""Publisher metadata review integrity; all mutations are INVENTED, no network."""

import re
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit

import pytest

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.registry import (
    load_registry,
    read_yaml,
    registry_path,
)

REVIEW = "review/trade_publisher_readings.yaml"
SOURCES = (
    "un_comtrade",
    "cepii_baci",
    "cepii_gravity",
    "atlas_complexity",
    "wb_wdi",
    "unctad_fdi",
    "imf_weo",
    "ilostat_qat",
)


def readings():
    return read_yaml(registry_path().parent / REVIEW)


def check_source(record):
    """Deciding predicate for the reviewed registry change, never a fetch gate."""
    assert set(record) == {"publisher", "pages", "facts", "pending", "activation"}
    assert record["publisher"]
    assert record["activation"] is False
    assert record["pending"]
    assert record["pages"]
    pages = {page["id"]: page for page in record["pages"]}
    assert len(pages) == len(record["pages"])
    for page in pages.values():
        assert set(page) == {
            "id",
            "url",
            "read_on",
            "status",
            "complete_body",
            "body_sha256",
            "reading",
            "sentences",
        }
        parts = urlsplit(page["url"])
        assert parts.scheme == "https" and parts.hostname
        assert not parts.username and not parts.password and not parts.fragment
        assert date.fromisoformat(page["read_on"]).isoformat() == page["read_on"]
        assert type(page["complete_body"]) is bool
        if page["complete_body"]:
            assert re.fullmatch(r"[a-f0-9]{64}", page["body_sha256"])
        else:
            assert page["body_sha256"] == ""
        if page["reading"] == "read":
            assert page["status"] == 200 and page["complete_body"]
            assert page["sentences"]
            assert approve(page["url"]).ok
        else:
            assert page["reading"] in {
                "http_error",
                "incomplete",
                "app_shell",
                "empty",
                "no_relevant_fact",
            }
            assert page["sentences"] == []
    for fact in record["facts"].values():
        assert set(fact) == {"confirmed", "value", "page", "sentence"}
        assert fact["confirmed"] is True
        assert fact["value"]
        page = pages[fact["page"]]
        assert page["reading"] == "read"
        assert fact["sentence"] in page["sentences"]


@pytest.mark.parametrize("source", SOURCES)
def test_registry_rows_resolve_to_independent_publisher_readings(source):
    review = readings()
    assert review["review_version"] == "trade-publisher-readings-v1"
    assert set(review["sources"]) == set(SOURCES)
    record = review["sources"][source]
    check_source(record)
    entry = next(item for item in load_registry() if item.key == source)
    assert entry.publisher == record["publisher"]
    assert REVIEW + "#" + source in entry.basis_note
    for page in record["pages"]:
        if page["reading"] == "read":
            assert page["body_sha256"] in entry.basis_note
            assert page["url"] in entry.basis_note
            assert all(sentence in entry.basis_note for sentence in page["sentences"])
    assert entry.skip_reason
    assert entry.commit_allowed is False


@pytest.mark.parametrize("plant", ["hash", "sentence", "failed_page", "activation"])
def test_review_rejects_unbacked_confirmation(plant):
    record = deepcopy(readings()["sources"]["un_comtrade"])
    fact = next(iter(record["facts"].values()))
    page = next(item for item in record["pages"] if item["id"] == fact["page"])
    check_source(record)
    if plant == "hash":
        page["body_sha256"] = "invented-not-a-body-hash"
    elif plant == "sentence":
        fact["sentence"] = "INVENTED statement absent from the publisher reading."
    elif plant == "failed_page":
        page.update(status=403, reading="http_error", sentences=[])
    else:
        record["activation"] = True
    with pytest.raises(AssertionError):
        check_source(record)


@pytest.mark.parametrize(
    "host",
    [
        "uncomtrade.org",
        "comtradeplus.un.org",
        "atlas.hks.harvard.edu",
        "intl-atlas-downloads.s3.amazonaws.com",
        "databank.worldbank.org",
        "datacatalog.worldbank.org",
        "www.worldbank.org",
        "unctadstat.unctad.org",
    ],
)
def test_pub03_admits_only_each_reviewed_publisher_host(host):
    """Each new host has a read page; an INVENTED lookalike stays refused."""
    pages = [p for r in readings()["sources"].values() for p in r["pages"]]
    assert any(
        p["reading"] == "read" and urlsplit(p["url"]).hostname == host for p in pages
    )
    assert approve("https://" + host + "/invented-metadata").ok
    assert not approve("https://" + host + ".invented.invalid/metadata").ok
    assert not approve("http://" + host + "/invented-metadata").ok
    assert not approve("https://" + host + "/metadata?key=invented").ok


def test_comtrade_free_budgets_are_publisher_facts_without_policy_activation():
    facts = readings()["sources"]["un_comtrade"]["facts"]
    assert facts["keyed_records_per_call"]["value"] == "100K"
    assert facts["daily_calls"]["value"] == "500"
    assert facts["public_records_per_call"]["value"] == "500"
    entry = next(e for e in load_registry() if e.key == "un_comtrade")
    assert entry.comtrade_policy.confirmed is False


def test_partial_readings_do_not_activate_downloads():
    from eii_custodian.publicdata.atlas.config import load_config as atlas_config
    from eii_custodian.publicdata.baci.config import load_config as baci_config
    from eii_custodian.publicdata.benchmarks.config import load_policies
    from eii_custodian.publicdata.gravity.config import load_config as gravity_config

    assert not any(
        c.confirmed for c in (atlas_config(), baci_config(), gravity_config())
    )
    assert all(not policy.confirmed for policy in load_policies().values())
