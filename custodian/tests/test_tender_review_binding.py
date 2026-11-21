"""The committed tender review joins to a fresh, invented archive receipt."""

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from custodian.tests.singles_entries import tender_entry
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_tenders import archive_pages, terms_body_hash
from eii_custodian.publicdata.confirm_s2_t13 import (
    Confirmation,
    WeightConfirmation,
    completion_evidence,
    load_confirmation,
)
from eii_custodian.publicdata.fetch.receipts import archive_auxiliary, sha256_hex
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.singles.tenders import (
    LIST_PATHS,
    ListReading,
    _write_pages,
)

REVIEW = (
    Path(__file__).resolve().parents[1] / "publicdata/review/s2_t13_confirmation.yaml"
)


def _fresh(tmp_path):
    entry = tender_entry()
    confirmation = load_confirmation(REVIEW)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    pairs = [(name, language) for name, _ in LIST_PATHS for language in ("en", "ar")]
    pages = [(name, language, 1, b"<html>SYN-page</html>") for name, language in pairs]
    readings = [
        ListReading(name, language, 1, 1, stamp, stamp) for name, language in pairs
    ]
    _write_pages(tmp_path / entry.key, pages, readings)
    identity = archive_pages(
        tmp_path, entry, stamp, terms_sha256=confirmation.tender.terms_sha256
    )
    receipt = read_snapshot(tmp_path / entry.key, identity).sidecar
    return confirmation, entry, receipt


def test_committed_review_accepts_fresh_archive(tmp_path):
    confirmation, entry, receipt = _fresh(tmp_path)
    assert receipt["retrieved_utc"] != confirmation.tender.retrieved_utc
    assert receipt["sha256"] != confirmation.tender.page_sha256
    assert completion_evidence(confirmation, entry, receipt) == confirmation


def test_changed_terms_on_resume_gets_new_receipt(tmp_path):
    confirmation, entry, first = _fresh(tmp_path)
    identity = archive_pages(
        tmp_path,
        entry,
        first["retrieved_utc"],
        retrieved_utc=first["retrieved_utc"],
        terms_sha256="f" * 64,
    )
    second = read_snapshot(tmp_path / entry.key, identity).sidecar
    assert second["terms_sha256"] == "f" * 64
    assert second["sha256"] != first["sha256"]
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, second)


def test_split_whitespace_keeps_visible_text_but_changes_reviewed_raw_body(
    tmp_path, monkeypatch
):
    from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256

    confirmation, entry, first_receipt = _fresh(tmp_path)
    first_body = b"<html>Invented terms</html>"
    second_body = b"<html>Invented  terms</html>"
    assert terms_text_sha256(first_body) == terms_text_sha256(second_body)
    assert sha256_hex(first_body) != sha256_hex(second_body)
    receipts = []
    for body in (first_body, second_body):
        _, rows = _real_terms(tmp_path, monkeypatch, body)
        digest = terms_body_hash(tmp_path, entry, rows)
        identity = archive_pages(
            tmp_path,
            entry,
            first_receipt["retrieved_utc"],
            retrieved_utc=first_receipt["retrieved_utc"],
            terms_sha256=digest,
        )
        receipts.append(read_snapshot(tmp_path / entry.key, identity).sidecar)
    assert receipts[0]["terms_sha256"] == sha256_hex(first_body)
    assert receipts[1]["terms_sha256"] == sha256_hex(second_body)
    reviewed = replace(
        confirmation,
        tender=replace(confirmation.tender, terms_sha256=sha256_hex(first_body)),
    )
    assert completion_evidence(reviewed, entry, receipts[0]) == reviewed
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(reviewed, entry, receipts[1])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("terms_sha256", "0" * 64),
        ("terms_sha256", None),
        ("fetch_url", "https://monaqasat.mof.gov.qa/other"),
        ("source_id", "another_source"),
        ("key", "another_source"),
        ("sha256", "bad"),
        ("retrieved_utc", "not-a-date"),
    ],
)
def test_receipt_substitutions_refused(tmp_path, field, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    receipt[field] = value
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize("value", ["", "a" * 63, "a" * 65, "G" * 64, "a" * 63 + "!"])
def test_sha_boundaries_refused(tmp_path, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    receipt["sha256"] = value
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize(
    "value", [None, "", "2026-11-21T00:00:00", "2026-11-21T03:00:00+03:00"]
)
def test_missing_or_non_utc_retrieval_refused(tmp_path, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    receipt["retrieved_utc"] = value
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "https://other.invalid/tenders"),
        ("terms_url", "https://other.invalid/terms"),
        ("fetch_host", "other.invalid"),
        ("release_tables", ()),
        ("publisher", "other publisher"),
        ("licence_basis", "dataset"),
        ("decision_record", "other"),
        ("period_first", "different"),
        ("period_last", "different"),
        ("skip_reason", "unavailable"),
    ],
)
def test_registry_substitutions_refused(tmp_path, field, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, replace(entry, **{field: value}), receipt)


@pytest.mark.parametrize("plant", ["missing", "duplicate", "other_url", "no_body_hash"])
def test_run_terms_record_must_be_unique_and_bound(tmp_path, plant):
    entry = tender_entry()
    row = {
        "key": entry.key,
        "terms_url": entry.terms_url,
        "terms_fingerprint": "visible_text",
        "terms_body_sha256": "a" * 64,
    }
    rows = [row]
    if plant == "missing":
        rows = []
    elif plant == "duplicate":
        rows.append(row.copy())
    elif plant == "other_url":
        row["terms_url"] = "https://other.invalid/terms"
    else:
        del row["terms_body_sha256"]
    with pytest.raises(AssemblyError, match="assembly_tender_terms_incomplete"):
        terms_body_hash(tmp_path, entry, rows)


def _real_terms(tmp_path, monkeypatch, body=b"<html>Invented terms</html>"):
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.kinds import TermsPage
    from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256

    entry = tender_entry()
    monkeypatch.setattr(
        build,
        "read_terms_page",
        lambda *_: TermsPage(terms_text_sha256(body), None, body),
    )
    rows = []
    build._read_terms_apart(
        entry,
        lambda *_: None,
        lambda *_: None,
        lambda: "2026-11-21T00:00:00Z",
        [],
        rows,
        {},
        tmp_path,
        [],
    )
    return entry, rows


@pytest.mark.parametrize(
    "plant",
    [
        "missing",
        "duplicate",
        "row_url",
        "fingerprint",
        "digest",
        "source_id",
        "key",
        "fetch_url",
        "non_mapping",
    ],
)
def test_real_terms_snapshot_single_field_plants(tmp_path, monkeypatch, plant):
    import shutil

    entry, rows = _real_terms(tmp_path, monkeypatch)
    assert terms_body_hash(tmp_path, entry, rows) == rows[0]["terms_body_sha256"]
    if plant == "missing":
        rows.clear()
    elif plant == "duplicate":
        rows.append(rows[0].copy())
    elif plant == "row_url":
        rows[0]["terms_url"] = "https://other.invalid/terms"
    elif plant == "fingerprint":
        rows[0]["terms_fingerprint"] = "raw_bytes"
    elif plant == "digest":
        rows[0]["terms_body_sha256"] = "z" * 64
    elif plant == "non_mapping":
        rows.insert(0, "not-a-mapping")
    else:
        shutil.rmtree(tmp_path / entry.key / "terms")
        changed = (
            replace(entry, **{plant: "other.invalid"})
            if plant != "fetch_url"
            else entry
        )
        url = "https://other.invalid/terms" if plant == "fetch_url" else entry.terms_url
        archive_auxiliary(
            changed,
            tmp_path / entry.key,
            "terms",
            b"<html>Invented terms</html>",
            "2026-11-21T00:00:00Z",
            url,
        )
    with pytest.raises(AssemblyError, match="assembly_tender_terms_incomplete"):
        terms_body_hash(tmp_path, entry, rows)


@pytest.mark.parametrize("position", [0, 1])
def test_terms_row_order_does_not_change_unique_selection(
    tmp_path, monkeypatch, position
):
    entry, rows = _real_terms(tmp_path, monkeypatch)
    foreign = dict(rows[0], key="SYN-foreign")
    rows.insert(position, foreign)
    assert (
        terms_body_hash(tmp_path, entry, rows)
        == rows[1 - position]["terms_body_sha256"]
    )


@pytest.mark.parametrize("reused", [False, True])
def test_adapter_uses_this_run_terms_for_both_archive_paths(
    tmp_path, monkeypatch, reused
):
    from custodian.tests.test_production_adapters import context

    from eii_custodian.publicdata.fetch.build import BuildOutcome
    from eii_custodian.publicdata.review.cache_fixture import read_cached

    confirmation, entry, _ = _fresh(tmp_path)
    build = context(tmp_path, (entry,))
    reused_times = {entry.key: "2026-11-21T00:00:00Z"} if reused else {}
    for body, expected in (
        (b"<html>Invented terms</html>", True),
        (b"<html>Different invented terms</html>", False),
    ):
        _, rows = _real_terms(tmp_path, monkeypatch, body)
        build.fetcher = lambda rows=tuple(rows): BuildOutcome(
            (),
            None,
            terms=rows,
            reused_times=reused_times,
        )
        build.fetch_archive()
        stage = json.loads((tmp_path / "assembly/fetch_archive.json").read_text())
        digest = stage["tender_archives"][entry.key]
        receipt = read_cached(tmp_path, entry, digest=digest, extension="json").sidecar
        reviewed = replace(
            confirmation,
            tender=replace(
                confirmation.tender,
                terms_sha256=sha256_hex(b"<html>Invented terms</html>"),
            ),
        )
        if expected:
            assert completion_evidence(reviewed, entry, receipt) == reviewed
        else:
            with pytest.raises(ValueError, match="do not confirm tender"):
                completion_evidence(reviewed, entry, receipt)


@pytest.mark.parametrize(
    "plant",
    ["page", "terms", "registry_host", "registry_other_origin", "key", "receipt_host"],
)
def test_each_host_and_key_guard_has_a_single_field_plant(tmp_path, plant):
    confirmation, entry, receipt = _fresh(tmp_path)
    other = "https://other.invalid/"
    if plant == "page":
        confirmation = replace(
            confirmation, tender=replace(confirmation.tender, page=other)
        )
    elif plant == "terms":
        confirmation = replace(
            confirmation, tender=replace(confirmation.tender, terms_url=other)
        )
        entry = replace(entry, terms_url=other)
    elif plant == "registry_host":
        entry = replace(entry, fetch_host="other.invalid")
        receipt["fetch_host"] = "other.invalid"
    elif plant == "registry_other_origin":
        entry = replace(entry, url=other, fetch_host="other.invalid", terms_url=other)
        confirmation = replace(
            confirmation, tender=replace(confirmation.tender, terms_url=other)
        )
        receipt["fetch_url"] = other
        receipt["fetch_host"] = "other.invalid"
    elif plant == "key":
        entry = replace(entry, key="SYN-other-key")
        receipt["key"] = entry.key
    else:
        receipt["fetch_host"] = "other.invalid"
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("page", "http://invented.invalid/", id="page_scheme"),
        pytest.param("registry", "http://invented.invalid/x", id="registry_scheme"),
        pytest.param("registry", "https://invented.invalid:8443/x", id="registry_port"),
        pytest.param("page", "https://@invented.invalid/", id="page_userinfo"),
        pytest.param("registry", "https://@invented.invalid/x", id="registry_userinfo"),
        pytest.param("page", "https://invented.invalid/?a=1", id="page_query"),
        pytest.param(
            "page", "https://invented.invalid/?a=1&a=2", id="page_duplicate_query"
        ),
        pytest.param("registry", "https://invented.invalid/x?a=1", id="registry_query"),
        pytest.param("page", "https://invented.invalid/#f", id="page_fragment"),
        pytest.param(
            "registry", "https://invented.invalid/x#f", id="registry_fragment"
        ),
        pytest.param("page", "https://invented.invalid/a b", id="page_space"),
        pytest.param("page", "https://invented.invalid/a\tb", id="page_control"),
        pytest.param("registry", "https:///x", id="registry_empty_host"),
        pytest.param("page", "https://invented.invalid:8443/", id="page_port"),
        pytest.param(
            "page", "https://other.invalid\\@invented.invalid/", id="page_backslash"
        ),
        pytest.param(
            "page", "https://other.invalid\uff20invented.invalid/", id="page_nonascii"
        ),
        pytest.param(
            "terms_url", "https://invented.invalid:8443/terms", id="terms_port"
        ),
        pytest.param("terms_url", "http://invented.invalid/terms", id="terms_scheme"),
        pytest.param(
            "terms_url",
            "https://other.invalid\\@invented.invalid/terms",
            id="terms_backslash",
        ),
        pytest.param(
            "terms_url",
            "https://other.invalid\uff20invented.invalid/terms",
            id="terms_nonascii",
        ),
    ],
)
def test_reviewed_endpoint_must_be_same_safe_origin(field, value):
    from custodian.tests.test_s2_t13_confirmation import receipt as invented_receipt
    from custodian.tests.test_s2_t13_confirmation import registry_record, tender

    review = tender()
    entry = registry_record(review)
    receipt = invented_receipt(review, entry)
    if field == "registry":
        from eii_custodian.publicdata.fetch.allowlist import host_of

        entry = replace(entry, url=value, fetch_host=host_of(value))
        receipt["fetch_url"] = value
        receipt["fetch_host"] = entry.fetch_host
        if not entry.fetch_host:
            review = replace(review, page="https:///a", terms_url="https:///terms")
            entry = replace(entry, terms_url=review.terms_url)
    else:
        review = replace(review, **{field: value})
        if field == "terms_url":
            entry = replace(entry, terms_url=value)
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(Confirmation(review, WeightConfirmation()), entry, receipt)


@pytest.mark.parametrize(
    ("page", "registry"),
    [
        ("https://invented.invalid/a", "https://invented.invalid/x"),
        ("HTTPS://INVENTED.INVALID./a", "https://invented.invalid:443/x"),
        ("https://invented.invalid/a%20b", "https://invented.invalid/x"),
    ],
)
def test_reviewed_origin_valid_spelling_controls(page, registry):
    from eii_custodian.publicdata.confirm_s2_t13 import _same_reviewed_origin

    assert _same_reviewed_origin(page, registry)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com\uff20monaqasat.mof.gov.qa/",
        "https://evil.com\uff20monaqasat.mof.gov.qa/TermsOfUse",
    ],
)
def test_host_of_malformed_netloc_returns_empty(url):
    from eii_custodian.publicdata.fetch.allowlist import host_of

    assert host_of(url) == ""


@pytest.mark.parametrize("field", ["page", "terms_url", "fetch_host"])
def test_equivalent_hostname_forms_are_accepted(tmp_path, field):
    confirmation, entry, receipt = _fresh(tmp_path)
    if field == "fetch_host":
        entry = replace(entry, fetch_host=entry.fetch_host.upper())
        receipt["fetch_host"] = entry.fetch_host
    else:
        value = getattr(confirmation.tender, field).replace(
            "monaqasat.mof.gov.qa", "monaqasat.mof.gov.qa."
        )
        confirmation = replace(
            confirmation, tender=replace(confirmation.tender, **{field: value})
        )
        if field == "terms_url":
            entry = replace(entry, terms_url=value)
    assert completion_evidence(confirmation, entry, receipt) == confirmation


@given(
    scheme=st.sampled_from(["https", "http"]),
    host=st.sampled_from(["invented.invalid", "other.invalid"]),
    port=st.sampled_from(["", ":443", ":8443"]),
    path=st.text(alphabet="abcXYZ0123456789/-_", max_size=24),
)
def test_reviewed_page_origin_oracle(scheme, host, port, path):
    from custodian.tests.test_s2_t13_confirmation import receipt as invented_receipt
    from custodian.tests.test_s2_t13_confirmation import registry_record, tender

    from eii_custodian.publicdata.confirm_s2_t13 import tender_disposition

    review = tender()
    entry = registry_record(review)
    sidecar = invented_receipt(review, entry)
    page = f"{scheme}://{host}{port}/{path}"
    expected = scheme == "https" and host == entry.fetch_host and port in ("", ":443")
    assert (
        tender_disposition(replace(review, page=page), entry, sidecar).shown is expected
    )


_ORIGIN_CASE = st.tuples(
    st.sampled_from(["https", "HTTPS", "http"]),
    st.sampled_from(
        [
            "invented.invalid",
            "INVENTED.INVALID",
            "invented.invalid.",
            "other.invalid",
            "",
            "other.invalid\\@invented.invalid",
            "other.invalid\uff20invented.invalid",
        ]
    ),
    st.sampled_from(["", ":443", ":8443"]),
    st.sampled_from(["", "u@", ":p@"]),
    st.sampled_from(["/a", "/a b", "/a%20b"]),
    st.sampled_from(["", "?a=1"]),
    st.sampled_from(["", "#f"]),
)


@given(page=_ORIGIN_CASE, registry=_ORIGIN_CASE)
def test_reviewed_origin_component_oracle(page, registry):
    from eii_custodian.publicdata.confirm_s2_t13 import _same_reviewed_origin

    def url(case):
        scheme, host, port, userinfo, path, query, fragment = case
        return f"{scheme}://{userinfo}{host}{port}{path}{query}{fragment}"

    def valid(case):
        scheme, host, port, userinfo, path, query, fragment = case
        return (
            scheme.casefold() == "https"
            and host.casefold().removesuffix(".")
            in {"invented.invalid", "other.invalid"}
            and port in {"", ":443"}
            and not userinfo
            and path != "/a b"
            and not query
            and not fragment
        )

    expected = (
        valid(page)
        and valid(registry)
        and page[1].casefold().removesuffix(".")
        == registry[1].casefold().removesuffix(".")
    )
    assert _same_reviewed_origin(url(page), url(registry)) is expected


def test_missing_tender_terms_has_named_build_refusal(tmp_path, monkeypatch):
    from eii_custodian.publicdata.assembly_adapters import Production
    from eii_custodian.publicdata.fetch.build import run_build

    def refuse(_self):
        raise AssemblyError("assembly_tender_terms_incomplete")

    monkeypatch.setattr(Production, "run", refuse)
    outcome = run_build(
        (),
        lambda *_: pytest.fail("network called"),
        tmp_path,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
        seed=17,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "assembly_tender_terms_incomplete"


def test_terms_read_carries_its_raw_body_hash(tmp_path, monkeypatch):
    body = b"<html>Invented terms</html>"
    entry, terms = _real_terms(tmp_path, monkeypatch, body)
    assert terms_body_hash(tmp_path, entry, terms) == sha256_hex(body)
    terms[0]["terms_sha256"] = "0" * 64
    with pytest.raises(AssemblyError, match="assembly_tender_terms_incomplete"):
        terms_body_hash(tmp_path, entry, terms)


@given(
    value=st.text().filter(lambda value: re.fullmatch(r"[0-9a-f]{64}", value) is None)
)
def test_every_malformed_sha_is_refused(value):
    from custodian.tests.test_s2_t13_confirmation import (
        receipt as invented_receipt,
    )
    from custodian.tests.test_s2_t13_confirmation import registry_record, tender

    t = tender()
    entry = registry_record(t)
    receipt = invented_receipt(t, entry)
    receipt["sha256"] = value
    from eii_custodian.publicdata.confirm_s2_t13 import tender_disposition

    assert not tender_disposition(t, entry, receipt).shown
