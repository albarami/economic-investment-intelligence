"""Closed DAT-126 record shape, validated both on read and before write."""

import math
import re
from datetime import datetime
from typing import cast

from .policy import ALLOWED_INPUTS
from .types import CLASS_RULES, KINDS, OUTCOMES

TEXT_FIELDS = (
    "decision_class",
    "kind",
    "provider_configured",
    "provider_used",
    "reported_model_id",
    "rubric_id",
    "rubric_sha256",
    "input_class",
    "input_sha256",
    "language",
    "route",
    "threshold_outcome",
    "memo_key",
    "permitted_effect",
    "recorded_at",
)
FIELDS = frozenset(
    (
        *TEXT_FIELDS,
        "option_order",
        "returned_label",
        "returned_scores",
        "top_score",
        "threshold_in_force",
        "latency_ms",
        "fallback_applied",
        "human_disposition",
    )
)
Record = dict[str, object]


def number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(cast(float, value))


def validate_record(value: object) -> Record:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("record field set differs from DAT-126")
    record = cast(Record, value)
    if any(not isinstance(record[key], str) or not record[key] for key in TEXT_FIELDS):
        raise ValueError("invalid record text")
    decision_class = cast(str, record["decision_class"])
    if decision_class not in CLASS_RULES or record["kind"] not in KINDS:
        raise ValueError("unknown class or kind")
    if (
        record["input_class"] not in ALLOWED_INPUTS
        or record["threshold_outcome"] not in OUTCOMES
    ):
        raise ValueError("unknown input class or outcome")
    if record["permitted_effect"] != CLASS_RULES[decision_class][1]:
        raise ValueError("effect does not belong to class")
    for key in ("rubric_sha256", "input_sha256", "memo_key"):
        if re.fullmatch("[a-f0-9]{64}", cast(str, record[key])) is None:
            raise ValueError("invalid record hash")
    for key in ("provider_configured", "provider_used"):
        if record[key] not in ("none", "recorded", "jev"):
            raise ValueError("unknown provider")
    orders = record["option_order"]
    if not isinstance(orders, list) or len(orders) != (
        2 if record["kind"] == "choice" else 1
    ):
        raise ValueError("invalid option orders")
    for order in orders:
        if (
            not isinstance(order, list)
            or len(order) < 2
            or any(
                not isinstance(label, str) or not label or label.isnumeric()
                for label in order
            )
        ):
            raise ValueError("invalid option labels")
        if len(set(order)) != len(order):
            raise ValueError("duplicate option labels")
    if record["kind"] == "choice" and orders[1] != list(reversed(orders[0])):
        raise ValueError("choice orders must reverse")
    if record["kind"] == "yes_no" and orders != [["no", "yes"]]:
        raise ValueError("yes_no labels are fixed")
    scores = record["returned_scores"]
    if not isinstance(scores, dict):
        raise ValueError("invalid scores")
    if scores and (
        set(scores) != set(orders[0])
        or any(not number(x) or not 0 <= x <= 1 for x in scores.values())
    ):
        raise ValueError("invalid score signal")
    label, top = record["returned_label"], record["top_score"]
    if label is None:
        if (
            scores
            or top is not None
            or record["threshold_outcome"] in ("DECIDED", "BELOW_THRESHOLD")
        ):
            raise ValueError("missing result")
    elif (
        not isinstance(label, str)
        or label not in scores
        or not number(top)
        or top != max(scores.values())
    ):
        raise ValueError("invalid returned result")
    if record["threshold_in_force"] != {"high": 0.90, "low": 0.10}:
        raise ValueError("unknown threshold configuration")
    if not number(record["latency_ms"]) or cast(float, record["latency_ms"]) < 0:
        raise ValueError("invalid latency")
    if type(record["fallback_applied"]) is not bool or record["fallback_applied"] != (
        record["threshold_outcome"] != "DECIDED"
    ):
        raise ValueError("invalid fallback")
    disposition = record["human_disposition"]
    if disposition is not None and (
        not isinstance(disposition, str) or not disposition
    ):
        raise ValueError("invalid human disposition")
    stamp = datetime.fromisoformat(cast(str, record["recorded_at"]))
    offset = stamp.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("record timestamp must be UTC")
    return record
