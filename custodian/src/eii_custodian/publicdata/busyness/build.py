"""Build-only provider reader; publish a checked projection, never raw answers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.busyness.address import read_addresses
from eii_custodian.publicdata.busyness.parse import (
    FORECAST_URL,
    QUERY_URL,
    parse_forecast,
    parse_query,
)
from eii_custodian.publicdata.busyness.policy import (
    CreditBudget,
    names_match,
    reaches_minimum,
    run_limit,
)
from eii_custodian.publicdata.busyness.review import (
    CROSSWALK_FILE,
    REQUEST_FILE,
    VENUE_FILE,
    load_crosswalk,
    load_requests,
    load_venues,
)
from eii_custodian.publicdata.busyness.security import assert_clean
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import KeyedRequest, Transport
from eii_custodian.publicdata.places.read import SOURCE_RELEASE

REVIEW = Path(__file__).resolve().parents[4] / "publicdata/review"
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
FACT = {
    "provenance": "Public",
    "subject_type": "place_public",
    "evidence_status": "Observed",
    "unit": "relative_index",
    "label": "BestTime relative busyness",
    "caveat_key": "relative_busyness_not_people",
    "period_field": "retrieved_on",
    "update_field": "provider_updated_on",
    "missing_update_label": "update date not stated",
}
KEYS = ("BESTTIME_API_KEY_PRIVATE", "BESTTIME_API_KEY_PUBLIC")


class BuildInputError(ValueError):
    """Only schema names and reviewed place identifiers, never provider text."""


def _request(
    transport: Transport,
    endpoint: str,
    method: str,
    parameters: Mapping[str, str],
    environ: Mapping[str, str],
) -> tuple[bytes, str]:
    body: bytes | None = None
    try:
        response = transport(KeyedRequest(endpoint, method, parameters, environ))
        if response.hops or response.final_url != endpoint:
            raise ValueError
        body = response.body
        digest = response.body_sha256 or sha256_hex(body)
    except Exception:
        # Never retain provider/transport exception objects or their chains.
        pass
    if body is None:
        raise ValueError(f"busy_besttime {endpoint} request_failed") from None
    return body, digest


def _inputs(
    cache: Path, review: Path, venues: tuple[dict[str, str], ...]
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    if not venues:
        return {}, {}
    crosswalk = {
        row["place_id"]: row
        for row in load_crosswalk(cache / "review" / CROSSWALK_FILE)
    }
    places = {}
    for line in (cache / "places_s2_t06/pub_place.jsonl").read_text().splitlines():
        row = json.loads(line)
        places[row["place_id"]] = row
    for venue in venues:
        identifier = venue["place_id"]
        if identifier not in places:
            raise BuildInputError(f"pub_place missing {identifier}")
        if identifier not in crosswalk:
            raise BuildInputError(f"crosswalk missing {identifier}")
        for field in ("name",):
            if (
                not isinstance(places[identifier].get(field), str)
                or not places[identifier][field].strip()
            ):
                raise BuildInputError(f"pub_place {field} missing {identifier}")
    return places, crosswalk


def build_busyness(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Callable[[], str],
    environ: Mapping[str, str],
    review: Path = REVIEW,
) -> str:
    """Validate inputs before sending; stage every answer before publishing anything."""
    if not entry.terms_words.strip():
        raise ValueError("busy_besttime terms_words empty")
    if (
        entry.url != FORECAST_URL
        or entry.commit_allowed
        or entry.licence_basis != "provider_terms"
    ):
        raise ValueError("busy_besttime registry mismatch")
    venues = load_venues(review / VENUE_FILE)
    budget = CreditBudget(run_limit(environ) if venues else 1)
    forecast_cost, query_cost = 1, 1
    if venues:
        for variable in KEYS:
            if not environ.get(variable, "").strip():
                raise ValueError(f"{variable}: required")
        forecast_cost, query_cost = load_requests(review / REQUEST_FILE)
    places, crosswalk = _inputs(cache, review, venues)
    addresses = read_addresses(cache) if venues else {}
    asked = 0
    rows: list[dict[str, object]] = []
    answers: list[dict[str, object]] = []
    reasons: dict[str, str] = {}
    categories = {row["category_group"]: 0 for row in venues}
    retrieved = clock()
    for venue in venues:
        identifier = venue["place_id"]
        if (
            places[identifier].get("source_release") != SOURCE_RELEASE
            or identifier not in addresses
        ):
            reasons[identifier] = "venue_address_absent"
            continue
        if crosswalk[identifier]["match"] != "matched":
            reasons[identifier] = "no_match"
            continue
        if not budget.reserve(identifier, "forecast", forecast_cost):
            reasons[identifier] = "credit_limit"
            continue
        asked += 1
        body, answer_digest = _request(
            transport,
            FORECAST_URL,
            "POST",
            {
                "venue_name": places[identifier]["name"],
                "venue_address": addresses[identifier],
            },
            environ,
        )
        retrieved = clock()
        retrieved_on = (
            datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
            .astimezone(UTC)
            .date()
            .isoformat()
        )
        forecast = parse_forecast(body)
        answers.append(
            {
                "place_id": identifier,
                "url": FORECAST_URL,
                "sha256": answer_digest,
                "retrieved_utc": retrieved,
            }
        )
        if forecast.reason:
            reasons[identifier] = forecast.reason
            continue
        if forecast.venue_id != crosswalk[identifier]["venue_key"] or not names_match(
            places[identifier]["name"], forecast.name
        ):
            reasons[identifier] = "no_match"
            continue
        updated = None
        if budget.reserve(identifier, "query", query_cost):
            body, answer_digest = _request(
                transport, QUERY_URL, "GET", {"venue_id": forecast.venue_id}, environ
            )
            updated = parse_query(body, forecast)
            answers.append(
                {
                    "place_id": identifier,
                    "url": QUERY_URL,
                    "sha256": answer_digest,
                    "retrieved_utc": clock(),
                }
            )
        categories[venue["category_group"]] += 1
        for day, values in enumerate(forecast.days):
            for i, value in enumerate(values):
                rows.append(
                    {
                        "place_id": identifier,
                        "day_of_week": DAYS[day],
                        "hour": (6 + i) % 24,
                        "busyness_index": value,
                        "retrieved_on": retrieved_on,
                        "provider_updated_on": updated,
                        "source_id": "busy_besttime",
                    }
                )
    coverage = {
        "asked": asked,
        "not_asked": len(venues) - asked,
        "with_figure": sum(categories.values()),
        "without_figure": sum(reason == "no_forecast" for reason in reasons.values()),
        "not_found": sum(reason == "not_found" for reason in reasons.values()),
        "reasons": reasons,
        "categories": {
            group: {
                "matched_with_figure": count,
                "reaches_minimum": reaches_minimum(count),
            }
            for group, count in categories.items()
        },
    }
    body = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=FORECAST_URL,
        fetch_host="besttime.app",
        retrieved_utc=retrieved,
        publisher=entry.publisher,
        source_modified="",
        row_count=len(rows),
        terms_sha256="",
    )
    receipt["credits_used"] = budget.used
    manifest = {
        "table": "pub_venue_busyness",
        "table_sha256": digest,
        "method": "besttime_projection_v1",
        "answers": answers,
        "credits_used": budget.used,
        "coverage": coverage,
        "fact": FACT,
        "source": receipt,
    }
    directory = cache / "busy_besttime"
    payload = json.dumps(manifest, sort_keys=True)
    assert_clean(
        environ, {"body": body.decode(), "manifest": payload, "cache_name": digest}
    )
    commit_pair(directory, digest, "jsonl", body, receipt)
    partial = directory / ".manifest.json.partial"
    try:
        partial.write_text(payload + "\n")
        os.replace(partial, directory / "manifest.json")
    except OSError:
        partial.unlink(missing_ok=True)
        raise
    return sha256_hex(payload.encode())
