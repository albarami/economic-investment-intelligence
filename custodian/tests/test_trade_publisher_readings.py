"""Publisher metadata review integrity; all mutations are INVENTED, no network."""

import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from eii_custodian.publicdata.fetch import allowlist
from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.registry import (
    load_registry,
    read_yaml,
    registry_path,
)

REVIEW = "review/trade_publisher_readings.yaml"
ROOT = Path(__file__).resolve().parents[2]
# Literal host set before P18 (d5ab3131); page readings grant no fetch permission.
PRE_P18 = frozenset(
    {
        "eservices.qfc.qa",
        "www.qfc.qa",
        "www.data.gov.qa",
        "www.data.qa",
        "services7.arcgis.com",
        "data.humdata.org",
        "s3.us-east-1.amazonaws.com",
        "www.geoboundaries.org",
        "github.com",
        "raw.githubusercontent.com",
        "stac.overturemaps.org",
        "overturemaps-us-west-2.s3.us-west-2.amazonaws.com",
        "download.openstreetmap.fr",
        "unstats.un.org",
        "data.worldpop.org",
        "web.archive.org",
        "fdiprojects.invest.qa",
        "www.invest.qa",
        "data.source.coop",
        "ladsweb.modaps.eosdis.nasa.gov",
        "archive-api.open-meteo.com",
        "services.gisqatar.org.qa",
        "monaqasat.mof.gov.qa",
        "ndownloader.figshare.com",
        "44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com",
        "download.geoservice.dlr.de",
        "besttime.app",
        "www.qcb.gov.qa",
        "visitqatar.com",
        "www.qncc.qa",
        "manateq.qa",
        "www.edu.gov.qa",
        "myschool.edu.gov.qa",
        "myschools.edu.gov.qa",
    }
)
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
def test_pub03_refuses_metadata_only_publisher_hosts(host):
    """A read page, including a data index, does not authorize its fetch host."""
    pages = [p for r in readings()["sources"].values() for p in r["pages"]]
    assert any(
        p["reading"] == "read" and urlsplit(p["url"]).hostname == host for p in pages
    )
    assert not approve("https://" + host + "/invented-metadata").ok
    assert not approve("https://" + host + ".invented.invalid/metadata").ok
    assert not approve("http://" + host + "/invented-metadata").ok
    assert not approve("https://" + host + "/metadata?key=invented").ok


P29_LEAD_READ_HOSTS = frozenset({"www.cepii.fr"})


def p18_fetch_hosts():
    """Configured fetch addresses and reviewed redirects, excluding reading-only URLs."""
    from eii_custodian.publicdata.atlas.config import load_config as atlas_config
    from eii_custodian.publicdata.baci.config import load_config as baci_config
    from eii_custodian.publicdata.benchmarks.config import load_policies
    from eii_custodian.publicdata.gravity.config import load_config as gravity_config

    hosts = set()
    for entry in load_registry():
        if entry.key not in SOURCES:
            continue
        if entry.url:
            hosts.add(urlsplit(entry.url).hostname)
        if entry.fetch_host:
            hosts.add(entry.fetch_host)
        policy = entry.comtrade_policy
        if policy is not None and policy.confirmed:
            hosts.update(template.host for template in policy.endpoint_templates)
            hosts.update(policy.allowed_redirect_hosts)
    for config in (baci_config(), gravity_config(), atlas_config()):
        if config.confirmed:
            hosts.update(urlsplit(url).hostname for url in config.reviewed_urls)
    for policy in load_policies().values():
        if policy.confirmed:
            hosts.add(urlsplit(policy.url).hostname)
            hosts.update(urlsplit(url).hostname for url in policy.reviewed_urls)
    return hosts


def check_p18_fetch_host_delta():
    read_hosts = {
        urlsplit(page["url"]).hostname
        for record in readings()["sources"].values()
        for page in record["pages"]
        if page["reading"] == "read"
    }
    # L-1270 narrows F3: a read host also needs a configured fetch purpose and
    # reviewed redirects. All P18 fetch policies/URLs remain unconfirmed/empty,
    # except the BACI row: S2-P29 fix 1 admits its host on the lead's
    # publisher-page reading (document 04, BACI pending identity and coverage
    # (S2-T24)), not on a P18 reading.
    fetch_hosts = p18_fetch_hosts()
    assert fetch_hosts == P29_LEAD_READ_HOSTS
    assert PRE_P18 <= allowlist.ALLOWED_HOSTS
    assert (
        allowlist.ALLOWED_HOSTS - PRE_P18
        == (read_hosts | P29_LEAD_READ_HOSTS) & fetch_hosts
    )


def test_pub03_fetch_host_delta_matches_readings_and_fetch_configuration():
    check_p18_fetch_host_delta()


def test_pub03_fetch_host_delta_rejects_planted_extra_host(monkeypatch):
    check_p18_fetch_host_delta()
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS | {"www.imf.org"}
    )
    with pytest.raises(AssertionError):
        check_p18_fetch_host_delta()


def test_pub03_rejects_planted_read_only_host(monkeypatch):
    check_p18_fetch_host_delta()
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS | {"www.worldbank.org"}
    )
    with pytest.raises(AssertionError):
        check_p18_fetch_host_delta()


@pytest.mark.parametrize("source", SOURCES)
def test_page_reading_is_independent_of_fetch_permission(monkeypatch, source):
    monkeypatch.setattr(allowlist, "ALLOWED_HOSTS", PRE_P18)
    check_source(readings()["sources"][source])


def test_comtrade_partial_budgets_leave_acceptance_open():
    task = (ROOT / "TASKS.md").read_text().split("### S2-T23 —", 1)[1]
    task = task.split("### ", 1)[0]
    assert "[ ] free daily/per-call budgets recorded without keys" in task
    assert "tier binding, reset rule and quota scope remain unverified" in task
    assert "criterion 4 stays open" in task


def test_comtrade_partial_budgets_do_not_claim_api_tiers():
    record = readings()["sources"]["un_comtrade"]
    facts = record["facts"]
    assert (
        not {
            "keyed_records_per_call",
            "public_records_per_call",
            "daily_calls",
            "preview_scope",
        }
        & facts.keys()
    )
    assert {
        "registered_download_records_per_call",
        "registered_api_calls_per_day",
        "per_call_limit_tier_unstated",
        "per_call_scope_tier_unstated",
    } <= facts.keys()
    assert facts["registered_download_records_per_call"]["value"] == "100K"
    assert facts["registered_api_calls_per_day"]["value"] == "500"
    assert facts["per_call_limit_tier_unstated"]["value"] == "500"
    assert facts["per_call_scope_tier_unstated"]["value"] == (
        "one period and one product per call"
    )
    assert any("tier binding" in pending for pending in record["pending"])
    entry = next(e for e in load_registry() if e.key == "un_comtrade")
    assert entry.comtrade_policy.confirmed is False
    assert "records/keyed call" not in entry.basis_note
    assert (
        "tier binding, reset rule and quota scope remain unverified" in entry.basis_note
    )


@pytest.mark.parametrize("field", ["terms_words", "terms_read_on"])
def test_comtrade_registry_keeps_both_dated_terms_excerpts(field):
    """Bind the registry to the independent two-page record, including its date."""
    document = (ROOT / "docs/04_PUBLIC_DATA_PACK.md").read_text()
    section = document.split("### S2-T21 part B terms readings", 1)[1]
    row = next(
        line for line in section.splitlines() if line.startswith("| `un_comtrade` |")
    )
    cells = [cell.strip() for cell in row.split("|")]
    assert "terms_pages.tsv#comtrade-license" in cells[5]
    assert "terms_pages.tsv#comtrade-redistribution" in cells[5]
    entry = next(e for e in load_registry() if e.key == "un_comtrade")
    expected = {"terms_words": cells[2], "terms_read_on": cells[3]}
    assert getattr(entry, field) == expected[field]


def test_comtrade_terms_agree_with_deployment_record_and_current_summary():
    entry = next(e for e in load_registry() if e.key == "un_comtrade")
    document = (ROOT / "docs/04_PUBLIC_DATA_PACK.md").read_text()
    deployment = (ROOT / "docs/17_DEPLOYMENT_HARDENING.md").read_text()
    row = next(
        line for line in deployment.splitlines() if line.startswith("| UN Comtrade, ")
    )
    assert entry.terms_read_on in row
    for clause in (
        "is strictly prohibited without the prior written permission of the United Nations.",
        "Internal use, including the use of UN Comtrade data for the AI model",
    ):
        assert clause in entry.terms_words
        assert clause in row
    assert "no blanket permission or prohibition follows from one excerpt" in row
    summary = document.split("Current registry terms, read 2026-11-20", 1)[1]
    summary = summary.split("### ", 1)[0]
    assert "- `un_comtrade`," not in summary


@pytest.mark.parametrize(
    ("source", "token"), [("wb_wdi", "CC-BY-4.0"), ("unctad_fdi", "cc-by-igo")]
)
def test_benchmark_licence_ids_use_registry_tokens(source, token):
    entries = load_registry()
    entry = next(e for e in entries if e.key == source)
    assert entry.licence_id == token
    assert any(e.key not in SOURCES and e.licence_id == token for e in entries)


def test_partial_readings_do_not_activate_downloads():
    from eii_custodian.publicdata.atlas.config import load_config as atlas_config
    from eii_custodian.publicdata.baci.config import load_config as baci_config
    from eii_custodian.publicdata.benchmarks.config import load_policies
    from eii_custodian.publicdata.gravity.config import load_config as gravity_config

    assert not any(
        c.confirmed for c in (atlas_config(), baci_config(), gravity_config())
    )
    assert all(not policy.confirmed for policy in load_policies().values())
