"""S1-T08 offline harness. Provider evidence never decides an application gate."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Never, cast

from eii_gateway import Gateway, Request
from eii_gateway.memo import canonical, digest, memo_key, option_orders
from eii_gateway.records import RUNS, RecordStore
from eii_gateway.thresholds import THRESHOLD

# The direct project command starts with its own directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.typed_decisions.interval import interval, reserve
from evals.typed_decisions.reproduction import (
    PROTOCOL_DIFFERENCES,
    ObservedProvider,
    answer_summary,
    model_reply_counts,
    reproduction,
)
from evals.typed_decisions.route import MODELS, compare, configured, identity

FOLDER = Path(__file__).resolve().parent
CASES = FOLDER / "cases.json"
ADMITTED = FOLDER / "results_2026-11-11.json"
ARM = "jev-1.14.0 (typed-decision provider)"
CLASSES = {
    "A_match": ("spine_match", "public"),
    "A_choice": ("spine_match", "public"),
    "B_route": ("question_route", "team_question"),
    "C_qc": ("brief_second_reader", "synthetic"),
    "D_parity": ("string_parity", "project_text"),
}
Case = dict[str, Any]


class Refusal(ValueError):
    """Fixed reasons only; caller values never enter the diagnostic."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise Refusal("invalid arguments")


def encode_label(case: Case, label: str) -> str:
    return "isic-" + label if case["test"] == "A_choice" else label


def request_for(case: Case, cases: list[Case]) -> Request:
    """Only a complete row in the tooling-owned set can become a request."""
    if case not in cases or set(case) != {
        "id",
        "test",
        "lang",
        "state",
        "question_type",
        "instructions",
        "criteria",
        "expected",
        "kind",
        "note",
    }:
        raise Refusal("case outside qualification set")
    decision_class, input_class = CLASSES[case["test"]]
    criteria = [
        {"label": encode_label(case, row["label"]), "description": row["description"]}
        for row in case["criteria"]
    ]
    request = Request(
        decision_class=decision_class,
        input_class=input_class,
        kind={"noul": "yes_no", "choice": "choice"}[case["question_type"]],
        input_text=case["state"],
        language=case["lang"],
        rubric_id="requalification-v1-" + case["id"],
        rubric_text=canonical(
            {"instructions": case["instructions"], "criteria": criteria}
        ),
        route="offline-requalification-v1",
        options=tuple(row["label"] for row in criteria),
        case_id=case["id"],
    )
    if encode_label(case, case["expected"]) not in request.labels:
        raise Refusal("expected label outside options")
    return request


def token_cap(authorised: bool, raw: str | None, planned: int) -> int:
    """OI-18 refusals precede Gateway construction, adapter import and DNS."""
    if not authorised:
        raise Refusal("authorisation required")
    if not os.environ.get("JEV_PRO_API_KEY"):
        raise Refusal("key variable required")
    if (
        raw is None
        or not raw.isascii()
        or not raw.isdecimal()
        or len(raw.lstrip("0")) > 7
    ):
        raise Refusal("invalid token cap")
    cap = int(raw.lstrip("0") or "0")
    if not 1 <= cap <= 5_000_000:
        raise Refusal("invalid token cap")
    if planned > cap:
        raise Refusal("planned use exceeds cap")
    return cap


def output_path(root: Path, output: str | None) -> Path:
    path = (
        Path(output)
        if output
        else root
        / "evals/typed_decisions"
        / ("results_" + datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%f") + ".json")
    )
    if path.name == ADMITTED.name or path.resolve() == ADMITTED.resolve():
        raise Refusal("admitted result is immutable")
    if not path.resolve().is_relative_to(root.resolve()):
        raise Refusal("output outside run root")
    if path.exists():
        raise Refusal("result already exists")
    return path


def committed_aggregate(result: dict[str, Any]) -> dict[str, Any]:
    """Omit run-record memo identifiers from public evidence without mutation."""
    return {
        **result,
        "gateway_accepted": {
            **result["gateway_accepted"],
            "cases": [
                {name: value for name, value in row.items() if name != "memo_key"}
                for row in result["gateway_accepted"]["cases"]
            ],
        },
    }


def run(args: argparse.Namespace, root: Path) -> int:
    case_bytes = CASES.read_bytes()
    cases: list[Case] = json.loads(case_bytes)
    requests = [request_for(case, cases) for case in cases]
    admitted = json.loads(ADMITTED.read_text())["arms"][ARM]
    planned_calls = sum(len(option_orders(request)) for request in requests)
    planned_tokens = reserve(planned_calls, admitted["tokens_mean_per_call"])
    cap = (
        token_cap(args.authorised, args.token_cap, planned_tokens)
        if args.provider == "jev"
        else 0
    )
    if args.provider == "jev" and not args.endpoint:
        raise Refusal("explicit endpoint required")
    if args.provider == "recorded" and not args.fixtures:
        raise Refusal("recorded fixture required")
    path = output_path(root, args.output)
    actual = identity(
        args.provider,
        MODELS[args.provider],
        canonical([r.rubric_text for r in requests]),
        case_bytes,
        THRESHOLD,
        args.endpoint if args.provider == "jev" else None,
    )
    state = compare(actual, configured(args.provider))
    if args.provider == "jev":
        requests = [
            replace(request, route="offline-requalification-" + digest(args.endpoint))
            for request in requests
        ]
        if (root / RUNS).exists():
            store = RecordStore(root)
            keys = {memo_key(request, MODELS["jev"]) for request in requests}
            if any(
                store.read(record)["memo_key"] in keys
                for record in store.folder.glob("*.json")
            ):
                raise Refusal("earlier records exist")
    print(
        canonical(
            {
                "identity": actual,
                "case_count": len(cases),
                "planned_calls": planned_calls,
                "planned_tokens": planned_tokens,
                "token_cap": cap,
            }
        )
    )
    previous = os.environ.get("EII_DECISION_PROVIDER")
    os.environ["EII_DECISION_PROVIDER"] = args.provider
    try:
        gateway = Gateway(
            root,
            fixtures=Path(args.fixtures) if args.fixtures else None,
            endpoint=args.endpoint,
            token_cap=cap,
        )
        observed = ObservedProvider(gateway._provider())
        gateway.provider = observed
        rows = []
        raw_rows = []
        for case, request in zip(cases, requests, strict=True):
            record = gateway.decide(request)
            if args.provider == "jev" and record["threshold_outcome"] in (
                "ERROR",
                "UNAVAILABLE",
            ):
                print(
                    f"STOPPED: provider failure at case {case['id']}; "
                    f"status {observed.failure_status}; "
                    f"calls made {observed.calls_made}; tokens used {observed.tokens_used}"
                )
                return 4
            actual["provider"] = cast(str, record["provider_used"])
            actual["model"] = cast(str, record["reported_model_id"])
            if compare(actual, configured(args.provider)) == "requalify":
                state = "requalify"
            accepted = record["threshold_outcome"] == "DECIDED"
            label = record["returned_label"]
            decoded = next(
                (
                    raw
                    for raw in (r["label"] for r in case["criteria"])
                    if encode_label(case, raw) == label
                ),
                label,
            )
            raw_label = observed.first.get(case["id"])
            raw_rows.append(
                dict(
                    id=case["id"],
                    test=case["test"],
                    label=next(
                        (
                            r["label"]
                            for r in case["criteria"]
                            if encode_label(case, r["label"]) == raw_label
                        ),
                        raw_label,
                    ),
                    correct=raw_label == encode_label(case, case["expected"]),
                    response_models=observed.models.get(case["id"], []),
                )
            )
            if any(
                model != MODELS[args.provider]
                for model in observed.models.get(case["id"], [])
            ):
                state = "requalify"
            rows.append(
                dict(
                    id=case["id"],
                    test=case["test"],
                    label=decoded,
                    accepted=accepted,
                    correct=accepted and decoded == case["expected"],
                    outcome=record["threshold_outcome"],
                    orders=record["option_order"],
                    memo_key=record["memo_key"],
                )
            )
    finally:
        if previous is None:
            os.environ.pop("EII_DECISION_PROVIDER", None)
        else:
            os.environ["EII_DECISION_PROVIDER"] = previous
    comparison = reproduction(args.provider, raw_rows, admitted)
    by_test = {}
    accepted_by_test = {}
    for name in CLASSES:
        group = [row for row in raw_rows if row["test"] == name]
        by_test[name] = {
            "current": answer_summary(group, MODELS[args.provider]),
            "admitted": admitted["by_test"][name],
        }
        accepted_group = [row for row in rows if row["test"] == name]
        accepted_by_test[name] = interval(
            sum(row["correct"] for row in accepted_group), len(accepted_group)
        )
    result = dict(
        identity=actual,
        route_status=state,
        model_replies=model_reply_counts(raw_rows, MODELS[args.provider]),
        raw_answers=dict(
            cases=raw_rows, overall=comparison["overall"], by_test=by_test
        ),
        gateway_accepted=dict(
            cases=rows,
            overall=interval(sum(row["correct"] for row in rows), len(rows)),
            by_test=accepted_by_test,
            outcomes=dict(Counter(row["outcome"] for row in rows)),
        ),
        stated_ci95=comparison["stated_ci95"],
        inside_stated_interval=comparison["inside_stated_interval"],
        admitted_measurement_reproduced=comparison["admitted_measurement_reproduced"],
        reproduction_reason=comparison["reproduction_reason"],
        protocol_differences=list(PROTOCOL_DIFFERENCES),
        evidence="live decision evidence"
        if args.provider == "jev"
        else "offline exercise; not a measurement",
    )
    if args.provider == "jev":
        result["calls_made"] = observed.calls_made
        result["tokens_used"] = observed.tokens_used
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(committed_aggregate(result)) + "\n")
    print(state)
    print(
        "DISABLED"
        if args.provider == "none"
        else "synthetic replay; not a measurement"
        if args.provider == "recorded"
        else "live run recorded; reproduction_reason="
        + comparison["reproduction_reason"]
    )
    return 2 if state == "requalify" else 0


def main(argv: list[str], *, root: Path | None = None) -> int:
    parser = Parser(description=__doc__)
    parser.add_argument("--provider", choices=tuple(MODELS), default="none")
    parser.add_argument("--fixtures")
    parser.add_argument("--output")
    parser.add_argument("--token-cap")
    parser.add_argument("--authorised", action="store_true")
    parser.add_argument("--endpoint")
    try:
        args = parser.parse_args(argv)
        if root is not None:
            return run(args, root)
        if args.provider == "jev":
            return run(args, FOLDER.parents[1])
        with tempfile.TemporaryDirectory() as folder:
            return run(args, Path(folder))
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
