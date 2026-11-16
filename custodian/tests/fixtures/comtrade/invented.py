"""Invented Comtrade responses. No captured live body is stored here."""

from __future__ import annotations

import json
from hashlib import sha256
from urllib.parse import parse_qsl, urlsplit

from eii_custodian.publicdata.comtrade.policy import Policy, parse_policy, period_ends
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import AttemptResult, PreparedRequest

HOST = "invented.example"
REDIRECT_HOST = "invented-redirect.example"
PARTNER = "ZZA"
REVISION = "HS-INVENTED"
FLOW_IN = "flow-in"
FLOW_OUT = "flow-out"
CHAPTER = "ch-a"
YEAR = "2099"
MONTH = "2099-01"
MARKER = "invented-query-marker"


def evidence_sha256() -> str:
    """Return a hash of invented evidence text. It is not a retrieval of a page."""
    return sha256(b"invented-evidence").hexdigest()


def policy_document(**overrides: object) -> dict[str, object]:
    """Return one activated invented policy. Overrides replace top-level fields."""
    document: dict[str, object] = {
        "confirmed": True,
        "version": "invented-1",
        "verified_on": "2026-11-16",
        "evidence_url": f"https://{HOST}/evidence",
        "evidence_sha256": evidence_sha256(),
        "access_tier": "invented-free",
        "endpoint_templates": [
            {
                "api_class": "keyed",
                "family": "data",
                "host": HOST,
                "path": "/data/v1/get",
            },
            {
                "api_class": "public",
                "family": "data",
                "host": HOST,
                "path": "/public/v1/preview",
            },
        ],
        "allowed_redirect_hosts": [HOST, REDIRECT_HOST],
        "daily_calls": 20,
        "keyed_record_limit": 3,
        "public_record_limit": 2,
        "reset_rule": "calendar_day",
        "quota_scope": "keyed_slot",
        "daily_exhaustion_signal": "calls_reached",
        "reporter_key": "QAT",
        "mirror_partner_keys": [PARTNER],
        "frequencies": ["annual", "monthly"],
        "periods": [YEAR, MONTH],
        "flows": [FLOW_IN, FLOW_OUT],
        "chapters": [CHAPTER],
        "subdivision_fields": ["product"],
        "subdivision_values": {"product": ["ch-a-1", "ch-a-2"]},
        "response_schema": {
            "record_array": "data",
            "count_field": "count",
            "truncation_field": "truncated",
            "error_field": "error",
            "reporter_field": "reporterCode",
            "partner_field": "partnerCode",
            "partner2_field": "partner2Code",
            "period_field": "period",
            "flow_field": "flowCode",
            "product_field": "cmdCode",
            "value_field": "primaryValue",
            "quantity_field": "qty",
            "flag_field": "flag",
            "classification_field": "classificationCode",
            "revision_field": "classificationRevision",
            "aggregation_field": "aggregationLevel",
            "customs_field": "customsCode",
            "transport_field": "transportCode",
            "valuation_field": "valuationBasis",
        },
        "count_bounds": {"minimum": 1, "maximum": 64},
        "schema_reviewed": True,
        "classification_revision": REVISION,
        "measure_units": [
            {"measure": "trade_value", "unit": "XXX"},
            {"measure": "net_weight", "unit": "invented-mass"},
        ],
        "value_precision": 6,
        "value_scale": 2,
        "price_amount": "",
        "price_currency": "",
        "price_retrieved_on": "",
        "price_source": "",
        "price_unavailable_reason": "price_not_recorded",
    }
    document.update(overrides)
    if "expected_last_periods" not in overrides:
        periods = document["periods"]
        document["expected_last_periods"] = (
            list(periods) if isinstance(periods, list) else []
        )
    return document


def invented_policy(**overrides: object) -> Policy:
    """Parse an invented policy. The caller overrides only the field under test."""
    parsed = parse_policy(policy_document(**overrides))
    if not isinstance(parsed, Policy):
        raise AssertionError("policy")
    return parsed


def invented_entry(policy: Policy | None = None) -> Entry:
    """Return an activated in-memory row. The committed registry row stays unconfirmed."""
    chosen = policy if policy is not None else invented_policy()
    first, last = period_ends(chosen.periods)
    return Entry(
        key="un_comtrade",
        source_id="un_comtrade",
        slug="",
        kind="comtrade_api",
        title_en="Invented trade",
        publisher="Invented publisher",
        licence_id="",
        licence_basis="provider_terms",
        decision_record="",
        fetch_host=HOST,
        url=f"https://{HOST}/data/v1/get",
        terms_url="",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_comtrade_trade",),
        caveat_keys=("trade_coverage_gap", "trade_mirror_separate"),
        columns=(),
        row_count_min=chosen.count_bounds.minimum,
        row_count_max=chosen.count_bounds.maximum,
        period_first=first,
        period_last=last,
        period_field="period",
        reconciliation="open",
        skip_reason="",
        extension="json",
        landing_url=f"https://{HOST}/evidence",
        terms_words="terms to be read",
        terms_read_on="2026-11-16",
        comtrade_policy=chosen,
    )


def body_for(
    request: PreparedRequest, *, count: int = 1, truncated: bool = False
) -> bytes:
    """Build an invented body whose dimensions match the closed query."""
    query = dict(parse_qsl(urlsplit(request.url).query))
    product = query.get("product", query.get("chapter", CHAPTER))
    records = []
    for index in range(count):
        records.append(
            {
                "reporterCode": query.get("reporter", ""),
                "partnerCode": query.get("partner", ""),
                "partner2Code": None
                if index == 0
                else f"row-{chr(ord('b') + index - 1)}",
                "period": query.get("period", ""),
                "flowCode": query.get("flow", ""),
                "cmdCode": product,
                "primaryValue": "1.25",
                "qty": None,
                "flag": "",
                "classificationCode": "HS-INVENTED",
                "classificationRevision": query.get("revision", REVISION),
                "aggregationLevel": 2 + index,
                "customsCode": "customs-invented",
                "transportCode": "mode-invented",
                "valuationBasis": "value-invented",
                "error": None,
            }
        )
    payload = {"count": count, "truncated": truncated, "error": None, "data": records}
    return json.dumps(payload).encode("utf-8")


def ok_result(request: PreparedRequest, **kwargs: object) -> AttemptResult:
    """Return a successful invented result for one prepared request."""
    count = kwargs.get("count", 1)
    truncated = kwargs.get("truncated", False)
    if not isinstance(count, int) or not isinstance(truncated, bool):
        raise AssertionError("body")
    return AttemptResult("ok", body_for(request, count=count, truncated=truncated))
