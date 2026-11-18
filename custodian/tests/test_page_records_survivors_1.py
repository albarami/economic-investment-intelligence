"""Exact page-table, validation, cache-role and selection refusals; invented pages."""

import hashlib
import json
from dataclasses import replace

import pytest
import yaml
from custodian.tests import test_s2_t29_pages as pages

from eii_custodian.publicdata.additions.split_policy import (
    UseRequest,
    validate_split_use,
)
from eii_custodian.publicdata.fetch import page_records
from eii_custodian.publicdata.fetch.page_records import PageError
from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot

STAMP = pages.STAMP
HEAD = b'<table id="syn"><tr><th>syn_name</th><th>syn_count</th></tr>'


def exact(reason):
    return "^" + reason + "$"


def parse(body, entry=None, declaration=None):
    row = entry or pages.page_entry()
    return page_records.parse_body(
        body, row, declaration if declaration is not None else pages.review(row)
    )


def refuses(body, reason="schema_missing", entry=None, declaration=None):
    with pytest.raises(PageError, match=exact(reason)):
        parse(body, entry, declaration)


# Table parser ---------------------------------------------------------------


def test_character_references_are_converted_in_cells():
    body = HEAD + b"<tr><td>SYN&amp;item</td><td>7</td></tr></table>"
    assert parse(body) == [{"syn_name": "SYN&item", "syn_count": 7}]


def test_cell_text_split_by_comment_and_tag_joins_without_separator():
    body = HEAD + b"<tr><td>SYN<!-- c -->-item</td><td><b>7</b></td></tr></table>"
    assert parse(body) == [{"syn_name": "SYN-item", "syn_count": 7}]


def test_stray_cell_end_tag_is_ignored():
    body = HEAD + b"<tr><td>SYN</td></td><td>7</td></tr></table>"
    assert parse(body) == [{"syn_name": "SYN", "syn_count": 7}]


@pytest.mark.parametrize(
    "attrs", [b' colspan="1"', b' rowspan="1"', b' class="SYN"', b' colspan="1" id="x"']
)
def test_neutral_cell_attributes_are_accepted(attrs):
    body = HEAD + b"<tr><td" + attrs + b">SYN</td><td>7</td></tr></table>"
    assert parse(body) == [{"syn_name": "SYN", "syn_count": 7}]


@pytest.mark.parametrize(
    "body",
    [
        HEAD + b'<tr><td colspan="2">SYN</td><td>7</td></tr></table>',
        HEAD + b'<tr><td rowspan="2">SYN</td><td>7</td></tr></table>',
        HEAD + b'<tr><td colspan="2" class="SYN">SYN</td><td>7</td></tr></table>',
    ],
    ids=["colspan", "rowspan", "colspan-class"],
)
def test_spanning_cells_refused(body):
    refuses(body)


@pytest.mark.parametrize(
    "body",
    [
        # A second table with the reviewed identifier.
        HEAD + b'</table><table id="syn"><tr><td>SYN</td><td>7</td></tr></table>',
        # A nested table inside the reviewed one.
        HEAD + b'<tr><td><table id="x"></table></td></tr></table>',
        # A row opened inside an open row.
        HEAD + b"<tr><td>SYN</td><td>7</td><tr></tr></table>",
        # A cell opened outside any row.
        b'<table id="syn"><td>SYN</td></table>',
        # A cell opened inside an open cell, which would otherwise drop text.
        HEAD + b"<tr><td>SYN-a<td>SYN</td><td>7</td></tr></table>",
        # A row closed while its last cell is still open.
        HEAD + b"<tr><td>SYN</td><td>7</tr></table>",
        # A header row closed while an extra cell is still open.
        b'<table id="syn"><tr><th>syn_name</th><th>syn_count</th><th>SYN</tr></table>',
        # A final data row that is never closed.
        HEAD + b"<tr><td>SYN</td><td>7</td></table>",
        # The reviewed table is never closed.
        HEAD + b"<tr><td>SYN</td><td>7</td></tr>",
        # A data row shorter than the declared columns.
        HEAD + b"<tr><td>SYN</td></tr></table>",
        # Bytes that are not UTF-8.
        HEAD + b"<tr><td>\xff</td><td>7</td></tr></table>",
        # A typed cell that is not an integer.
        HEAD + b"<tr><td>SYN</td><td>SYN</td></tr></table>",
    ],
    ids=[
        "second-table",
        "nested-table",
        "nested-row",
        "cell-outside-row",
        "nested-cell",
        "row-closes-open-cell",
        "header-open-cell",
        "open-last-row",
        "open-table",
        "short-row",
        "not-utf8",
        "integer",
    ],
)
def test_malformed_tables_refused_with_exact_reason(body):
    refuses(body)


def test_number_cells_keep_their_decimal_text():
    row = replace(
        pages.page_entry(), columns=(("syn_name", "string"), ("syn_count", "number"))
    )
    body = HEAD + b"<tr><td>SYN</td><td>2.50</td></tr></table>"
    assert parse(body, row) == [{"syn_name": "SYN", "syn_count": "2.50"}]


def test_missing_table_id_matches_only_an_empty_id():
    declaration = pages.review()
    del declaration["table_id"]
    body = (
        b'<table id="None"></table><table id="XXXX"></table><table id="">'
        + HEAD.removeprefix(b'<table id="syn">')
        + b"<tr><td>SYN</td><td>7</td></tr></table>"
    )
    assert parse(body, declaration=declaration) == [{"syn_name": "SYN", "syn_count": 7}]


def test_declared_columns_must_equal_entry_columns():
    declaration = pages.review()
    declaration["columns"] = [["syn_name", "string"], ["syn_count", "number"]]
    refuses(HEAD + b"<tr><td>SYN</td><td>7</td></tr></table>", declaration=declaration)


def test_version_two_declared_columns_mismatch_reason():
    declaration = pages.review()
    declaration["version"] = 2
    declaration["columns"] = [["syn_name", "string"]]
    refuses(pages.BODY, declaration=declaration)


def test_school_forbidden_column_reason():
    row = replace(
        pages.page_entry(),
        source_id="schools_private_directory",
        columns=(("Capacity", "integer"),),
    )
    refuses(pages.BODY, "unsupported_source_claim", entry=row)


@pytest.mark.parametrize("bound", ["min", "max"])
def test_row_count_bounds_are_inclusive(bound):
    row = replace(
        pages.page_entry(),
        row_count_min=1 if bound == "min" else None,
        row_count_max=1 if bound == "max" else None,
    )
    assert len(parse(pages.BODY, row)) == 1


def test_row_count_reason():
    row = replace(pages.page_entry(), row_count_min=2)
    refuses(pages.BODY, "row_count", entry=row)


# Declaration, claim and use -------------------------------------------------


@pytest.mark.parametrize(
    "document",
    [{"sources": ["SYN"]}, ["SYN"], {"sources": {"SYN-other": {}}}],
    ids=["sources-list", "top-list", "row-missing"],
)
def test_declaration_shape_reason(tmp_path, document):
    path = tmp_path / "SYN-review.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(PageError, match=exact("schema_missing")):
        page_records.load_declaration("events_visit_qatar", path)


@pytest.mark.parametrize(
    "source,claim",
    [("events_qncc", "published_fields"), ("awards_owner_scrape", "awarded_value")],
)
def test_source_owned_claims_pass(source, claim):
    assert page_records.validate_claim(source, claim) is None


def test_refused_use_keeps_policy_reason():
    request = UseRequest(
        "syn_table",
        (("insurance_tables", ("nationality",)),),
        "public_display",
        "worker",
        "source",
        "public",
    )
    reason = "invented_geography"
    assert validate_split_use(request).reason == reason
    with pytest.raises(PageError) as caught:
        page_records.validate_use(request)
    assert str(caught.value) == reason


# Declaration and entry validation ------------------------------------------


def check(entry=None, **changes):
    row = entry or pages.page_entry()
    declaration = pages.review(row)
    declaration.update(changes)
    return page_records._validate(row, declaration)


def refused(reason, entry=None, **changes):
    with pytest.raises(PageError, match=exact(reason)):
        check(entry, **changes)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"commit_allowed": True}, "commit_refused"),
        ({"licence_basis": "SYN-basis"}, "receipt_missing"),
        ({"publisher": ""}, "receipt_missing"),
        (
            {"licence_basis": "owner_decision", "decision_record": "0099"},
            "receipt_missing",
        ),
        ({"row_count_min": 1}, "bounds_unconfirmed"),
        ({"row_count_max": 1}, "bounds_unconfirmed"),
        ({"key": "/SYN-key"}, "cache_path_refused"),
        ({"key": "SYN/../SYN-key"}, "cache_path_refused"),
    ],
)
def test_entry_refusals_exact(changes, reason):
    refused(reason, replace(pages.page_entry(), **changes))


def test_entry_pending_terms_fields_never_refuse():
    """Ruling L-1001: pending terms fields never refuse a page row."""
    row = replace(
        pages.page_entry(), terms_words="", terms_read_on="", licence_basis=""
    )
    assert check(row) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"licence_basis": "owner_decision", "decision_record": "0026"},
        {"licence_basis": "portal_terms"},
        {"licence_basis": "provider_terms"},
        {"licence_basis": "dataset"},
        {"licence_basis": "pending"},
        {"licence_basis": ""},
        {"period_last": "2024"},
        {"period_last": "2023"},
    ],
)
def test_entry_variants_pass(changes):
    assert check(replace(pages.page_entry(), **changes)) is None


def test_pending_terms_fields_still_fetch_and_record(tmp_path):
    """Ruling L-1001: a pending page row fetches, parses and records its pending values."""
    row = replace(
        pages.page_entry(), terms_words="", terms_read_on="", licence_basis=""
    )
    result = page_records.fetch_page(
        row,
        lambda url: pages.Response(url, pages.BODY, ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=pages.review(row),
    )
    payload = json.loads(result.body)
    assert payload["rows"] == [{"syn_name": "SYN-item", "syn_count": 7}]
    assert result.sidecar["terms_words"] == ""
    assert result.sidecar["terms_read_on"] == ""
    assert result.sidecar["licence_basis"] == ""


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"as_of": "SYN"}, "snapshot_date_missing"),
        ({"period": ""}, "snapshot_date_missing"),
        ({"reviewed_urls": (pages.URL,)}, "blocked_host"),
        ({"reviewed_urls": []}, "blocked_host"),
        ({"reviewed_urls": [pages.URL, "https://example.invalid/SYN"]}, "blocked_host"),
        ({"reviewed_urls": ["https://www.data.gov.qa/SYN-other"]}, "blocked_host"),
        ({"url": "https://www.data.gov.qa/SYN-other"}, "blocked_host"),
    ],
)
def test_declaration_refusals_exact(changes, reason):
    refused(reason, **changes)


def test_older_period_is_stale():
    refused("stale_period", replace(pages.page_entry(), period_last="2025"))


# Obstacle words ---------------------------------------------------------------


@pytest.mark.parametrize(
    "word",
    [b"Sign In", b"Sign-In", b"Paywall", b"Robot Check", b"Registration Required"],
)
def test_obstacle_words_refused_in_any_case(word):
    with pytest.raises(PageError, match=exact("unavailable")):
        page_records._obstacle(b"<p>SYN " + word + b"</p>")


def test_plain_page_has_no_obstacle():
    assert page_records._obstacle(pages.BODY) is None


# Failure records and parsed payloads ---------------------------------------


def test_failure_record_exact_bytes(tmp_path):
    row = pages.page_entry()
    page_records.record_failure(tmp_path, row, STAMP, "SYN-reason")
    expected = json.dumps(
        {
            "source_id": row.source_id,
            "attempted_utc": STAMP,
            "reason": "SYN-reason",
            "coverage": "NO_DATA",
        },
        sort_keys=True,
    ).encode()
    snapshot = read_snapshot(
        tmp_path / row.key / "failures", hashlib.sha256(expected).hexdigest()
    )
    assert snapshot.body == expected
    assert snapshot.sidecar["retrieved_utc"] == STAMP


def raw_snapshot(tmp_path, row, **sidecar):
    side = {
        "source_id": row.source_id,
        "key": row.key,
        "retrieved_utc": STAMP,
        "licence_basis": "owner_decision",
    }
    side.update(sidecar)
    return publish_snapshot(tmp_path / row.key / "raw", "html", pages.BODY, side)


def test_parsed_payload_exact(tmp_path):
    row = pages.page_entry()
    raw = raw_snapshot(tmp_path, row)
    assert page_records.parse_page_snapshot(raw, row, pages.review(row)) == {
        "source_id": row.source_id,
        "rows": [{"syn_name": "SYN-item", "syn_count": 7}],
        "page_sha256": raw.sha256,
        "raw_identity": raw.sha256,
        "as_of": "2024-02-03",
        "source_period": "2024",
        "retrieved_utc": STAMP,
        "method": "page_records.parse_page_snapshot@v1",
        "provenance": "Public",
        "completeness": "unknown",
    }


def test_parsed_payload_other_source_reason(tmp_path):
    row = pages.page_entry()
    raw = raw_snapshot(tmp_path, row, source_id="SYN-other")
    with pytest.raises(PageError, match=exact("receipt_missing")):
        page_records.parse_page_snapshot(raw, row, pages.review(row))


# Cache roles -------------------------------------------------------------------


def test_cache_directory_returns_key_folder(tmp_path):
    row = pages.page_entry()
    assert page_records.cache_directory(tmp_path, row) == tmp_path / row.key


@pytest.mark.parametrize("key", ["/SYN-key", "SYN/../SYN-key"])
def test_cache_key_reason(tmp_path, key):
    with pytest.raises(PageError, match=exact("cache_path_refused")):
        page_records.cache_directory(tmp_path, replace(pages.page_entry(), key=key))


@pytest.mark.parametrize("role", ["raw", "proofs", "failures", "terms", "inputs"])
@pytest.mark.parametrize("inside", [True, False], ids=["inside", "outside"])
def test_each_cache_role_link_refused(tmp_path, role, inside):
    row = pages.page_entry()
    cache = tmp_path / "SYN-cache"
    target = (cache / "SYN-elsewhere") if inside else (tmp_path / "SYN-out")
    target.mkdir(parents=True)
    (cache / row.key).mkdir(parents=True)
    (cache / row.key / role).symlink_to(target, target_is_directory=True)
    with pytest.raises(PageError, match=exact("cache_path_refused")):
        page_records.cache_directory(cache, row)


def test_non_role_link_in_key_folder_is_not_a_role(tmp_path):
    row = pages.page_entry()
    cache = tmp_path / "SYN-cache"
    outside = tmp_path / "SYN-out"
    outside.mkdir()
    (cache / row.key).mkdir(parents=True)
    for name in ("XXXX", "SYN-other"):
        (cache / row.key / name).symlink_to(outside, target_is_directory=True)
    assert page_records.cache_directory(cache, row) == cache / row.key


# Selected snapshots ------------------------------------------------------------


def select(cache, row, identity):
    (cache / "snapshot_pins.json").write_text(
        json.dumps({row.key: identity}), encoding="utf-8"
    )


def v1_cache(tmp_path, *, page_sha256=None, as_of="2024-02-03"):
    row = pages.page_entry()
    raw = raw_snapshot(tmp_path, row)
    payload = {
        "raw_identity": raw.sha256,
        "page_sha256": raw.sha256 if page_sha256 is None else page_sha256,
        "as_of": as_of,
    }
    side = {"source_id": row.source_id, "key": row.key, "retrieved_utc": STAMP}
    parsed = publish_snapshot(
        tmp_path / row.key, "json", json.dumps(payload).encode(), side
    )
    select(tmp_path, row, parsed.sha256)
    return row, parsed


def test_selected_v1_payload_returned(tmp_path):
    row, parsed = v1_cache(tmp_path)
    assert page_records.selected_page(tmp_path, row).sha256 == parsed.sha256


@pytest.mark.parametrize(
    "changes", [{"page_sha256": "0" * 64}, {"as_of": ""}], ids=["hash", "date"]
)
def test_selected_v1_receipt_reason(tmp_path, changes):
    row, _ = v1_cache(tmp_path, **changes)
    with pytest.raises(PageError, match=exact("receipt_missing")):
        page_records.selected_page(tmp_path, row)


def test_selection_missing_reason(tmp_path):
    with pytest.raises(PageError, match=exact("snapshot_selection_invalid")):
        page_records.selected_page(tmp_path, pages.page_entry())


def v2_cache(
    tmp_path,
    *,
    payload=None,
    side=None,
    item=None,
    raw_side=None,
    link=False,
):
    row = pages.page_entry()
    raw_fields = {
        "source_id": row.source_id,
        "key": row.key,
        "retrieved_utc": STAMP,
        "licence_basis": "owner_decision",
    }
    raw_fields.update(raw_side or {})
    # A None value removes the key, for the absent-key plant.
    raw_fields = {k: v for k, v in raw_fields.items() if v is not None}
    folder = row.key + ("/SYN-real-input" if link else "/inputs/input-0")
    raw = publish_snapshot(tmp_path / folder, "html", b"SYN input", raw_fields)
    if link:
        (tmp_path / row.key / "inputs").mkdir()
        (tmp_path / row.key / "inputs" / "input-0").symlink_to(
            tmp_path / folder, target_is_directory=True
        )
    entry = {"key": "inputs/input-0", "identity": raw.sha256, "sha256": raw.sha256}
    entry.update(item or {})
    body = {
        "version": 2,
        "source_id": row.source_id,
        "method": "page_acquire.fetch@v2",
        "inputs": [entry],
        "as_of": "2024-02-03",
        "retrieved_utc": STAMP,
    }
    body.update(payload or {})
    sidecar = {
        "source_id": row.source_id,
        "key": row.key,
        "retrieved_utc": STAMP,
        "inputs": body["inputs"],
        "as_of": body["as_of"],
    }
    sidecar.update(side or {})
    parsed = publish_snapshot(
        tmp_path / row.key, "json", json.dumps(body).encode(), sidecar
    )
    select(tmp_path, row, parsed.sha256)
    return row, parsed


def test_selected_v2_payload_returned(tmp_path):
    row, parsed = v2_cache(tmp_path)
    assert page_records.selected_page(tmp_path, row).sha256 == parsed.sha256


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"payload": {"method": "SYN-method"}}, "receipt_missing"),
        ({"payload": {"source_id": "SYN-other"}}, "receipt_missing"),
        ({"payload": {"inputs": []}}, "receipt_missing"),
        ({"payload": {"as_of": "2024-02-04"}}, "snapshot_date_missing"),
        ({"payload": {"as_of": 2024}}, "snapshot_date_missing"),
        ({"payload": {"as_of": "2024-W05-6"}}, "snapshot_date_missing"),
        ({"side": {"inputs": []}}, "receipt_missing"),
        ({"side": {"as_of": "2024-02-04"}}, "receipt_missing"),
        ({"item": {"key": "inputs/input-1"}}, "receipt_missing"),
        ({"item": {"sha256": "0" * 64}}, "receipt_missing"),
        ({"raw_side": {"source_id": "SYN-other"}}, "receipt_missing"),
        ({"link": True}, "cache_path_refused"),
    ],
)
def test_selected_v2_refusals_exact(tmp_path, changes, reason):
    row, _ = v2_cache(tmp_path, **changes)
    with pytest.raises(PageError, match=exact(reason)):
        page_records.selected_page(tmp_path, row)


@pytest.mark.parametrize("basis", ["", "pending"])
def test_selected_v2_accepts_a_pending_basis(tmp_path, basis):
    """Ruling L-1001: a stored input receipt with a pending basis is still selected."""
    row, parsed = v2_cache(tmp_path, raw_side={"licence_basis": basis})
    assert page_records.selected_page(tmp_path, row).sha256 == parsed.sha256


def test_selected_v2_input_receipt_without_the_basis_key_refuses(tmp_path):
    """Ruling L-1016 (applying L-1001): a receipt the build itself wrote holds
    the licence_basis key; a receipt with the key absent is a defect, not a
    terms reading, and refuses receipt_missing."""
    row, _ = v2_cache(tmp_path, raw_side={"licence_basis": None})
    with pytest.raises(PageError, match=exact("receipt_missing")):
        page_records.selected_page(tmp_path, row)


def test_selected_v2_inputs_folder_link_out_refused(tmp_path):
    cache = tmp_path / "SYN-cache"
    cache.mkdir()
    row, _ = v2_cache(cache)
    inputs = cache / row.key / "inputs"
    moved = tmp_path / "SYN-moved-inputs"
    inputs.rename(moved)
    inputs.symlink_to(moved, target_is_directory=True)
    with pytest.raises(PageError, match=exact("cache_path_refused")):
        page_records.selected_page(cache, row)
