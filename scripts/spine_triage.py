"""Offline review ordering only; every mapping still needs PUB-35 sign-off."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Never

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eii_custodian.publicdata.review.activity import CODE_SYSTEM_VERSION, SpineError
from eii_custodian.publicdata.review.cache_fixture import CacheError
from eii_gateway import Gateway
from eii_gateway.memo import canonical, digest
from eii_gateway.types import Request
from spine_triage_io import (
    Context,
    Refusal,
    Result,
    Suggestion,
    contained,
    load_context,
    output_path,
    write_outputs,
)

RUBRIC_ID = "spine-triage-v1"
RUBRIC = (
    "Does the Arabic activity name fit the supplied ISIC class title? Answer yes or no."
)
LANGUAGE = "ar"
ROUTE = "offline-spine-triage-v1"
MODEL = "jev-1.14.0"


def requests(context: Context) -> dict[str, Request]:
    """Only recomputed eligible pairs; no prompt or input-class CLI seam."""
    classes = {row.code: row for row in context.inputs.classes}
    result = {}
    for row in context.inputs.spine.queue:
        if row.code_length != 7 or row.code[:4] not in classes:
            continue
        title = classes[row.code[:4]]
        result[row.code] = Request(
            decision_class="spine_match",
            kind="yes_no",
            input_class="public",
            input_text=canonical(
                {
                    "activity_name_ar": row.name_ar,
                    "class_code": title.code,
                    "class_title_en": title.label_en,
                    "class_title_ar": title.label_ar,
                    "code_system_version": CODE_SYSTEM_VERSION,
                }
            ),
            language=LANGUAGE,
            rubric_id=RUBRIC_ID,
            rubric_text=RUBRIC,
            route=ROUTE,
            case_id="spine-" + row.code,
        )
    return result


def keyed_cap(
    root: Path,
    authorised: bool,
    endpoint: str | None,
    raw_cap: str | None,
    qualification: Path | None,
) -> int:
    """Refuse before gateway setup; qualification must name this exact identity."""
    if not authorised or not endpoint or qualification is None:
        raise Refusal("qualification refused")
    evidence = json.loads(contained(root, qualification).read_text())
    identity = {
        "model": MODEL,
        "rubric_id": RUBRIC_ID,
        "rubric_sha256": digest(RUBRIC),
        "language": LANGUAGE,
        "route": ROUTE + "-" + digest(endpoint),
    }
    if evidence != {"qualified": True, **identity}:
        raise Refusal("qualification refused")
    if raw_cap is None or not raw_cap.isascii() or not raw_cap.isdecimal():
        raise Refusal("cap refused")
    if len(raw_cap) > 7 or not 1 <= int(raw_cap) <= 5_000_000:
        raise Refusal("cap refused")
    return int(raw_cap)


def triage(context: Context, gateway: Gateway) -> Result:
    """Stable partition of unsigned rows; keyed failure restores the whole baseline."""
    pairs = requests(context)
    suggestions = []
    failed = False
    calls = 0
    initial_tokens = gateway.remaining
    route = ROUTE
    if gateway.configured == "jev":
        route += "-" + digest(gateway.endpoint or "")
    for row in context.inputs.spine.queue:
        if row.code not in pairs:
            suggestions.append(Suggestion(row.code, "", "ineligible", ""))
            continue
        label, memo = "unresolved", ""
        if not failed:
            request = replace(pairs[row.code], route=route)
            calls += 1
            try:
                record = gateway.decide(request)
            except (OSError, ValueError, KeyError, TypeError):
                if gateway.configured != "jev":
                    raise Refusal("provider refused") from None
                failed = True
            else:
                memo = str(record["memo_key"])
                outcome = record["threshold_outcome"]
                if outcome == "DECIDED":
                    label = "match" if record["returned_label"] == "yes" else "mismatch"
                if gateway.configured == "jev" and outcome in ("ERROR", "UNAVAILABLE"):
                    failed = True
        suggestions.append(Suggestion(row.code, row.code[:4], label, memo))
    if failed:
        suggestions = [
            replace(item, suggestion="unresolved")
            if item.suggestion != "ineligible"
            else item
            for item in suggestions
        ]
    baseline = context.inputs.spine.queue
    if gateway.configured == "none" or failed:
        queue = baseline
    else:
        labels = {item.code: item.suggestion for item in suggestions}
        groups = {"mismatch": 0, "unresolved": 1, "ineligible": 1, "match": 2}
        queue = tuple(sorted(baseline, key=lambda row: groups[labels[row.code]]))
    return Result(
        queue,
        tuple(suggestions),
        failed,
        {
            "provider": gateway.configured,
            "rubric_id": RUBRIC_ID,
            "rubric_sha256": digest(RUBRIC),
            "language": LANGUAGE,
            "route": route,
            "calls": calls,
            "returned_tokens": initial_tokens - gateway.remaining,
            "model": {"none": "none", "recorded": "synthetic-recorded", "jev": MODEL}[
                gateway.configured
            ],
        },
    )


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise Refusal("arguments refused")


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Exit 0 unsigned output, 3 refusal, 4 complete keyed-failure fallback."""
    root = Path(__file__).resolve().parents[1] if root is None else root.resolve()
    parser = Parser(description=__doc__)
    for name in ("queue", "cache", "review", "membership"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--authorised", action="store_true")
    parser.add_argument("--endpoint")
    parser.add_argument("--token-cap")
    try:
        args = parser.parse_args(argv)
        provider = os.environ.get("EII_DECISION_PROVIDER", "none")
        if provider not in ("none", "recorded", "jev"):
            raise Refusal("provider refused")
        fixtures = None
        if provider == "recorded":
            if args.fixtures is None:
                raise Refusal("fixtures required")
            fixtures = contained(root, args.fixtures)
            if not isinstance(json.loads(fixtures.read_text()), list):
                raise Refusal("fixtures refused")
        cap = (
            keyed_cap(
                root, args.authorised, args.endpoint, args.token_cap, args.qualification
            )
            if provider == "jev"
            else 0
        )
        context = load_context(
            root, args.cache, args.review, args.queue, args.membership
        )
        output_path(context, args.run_id)
        gateway = Gateway(
            root,
            fixtures=fixtures,
            endpoint=args.endpoint if provider == "jev" else None,
            token_cap=cap,
        )
        result = triage(context, gateway)
        write_outputs(context, args.run_id, result)
    except (OSError, ValueError, TypeError, SpineError, CacheError):
        print("REFUSED spine triage input or authorisation")
        return 3
    print("FALLBACK unsigned queue" if result.fallback else "OK unsigned queue")
    return 4 if result.fallback else 0


if __name__ == "__main__":
    raise SystemExit(main())
