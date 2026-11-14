"""Wire shape follows the public API reference read by the lead on 2026-11-13.

The caller supplies the address, kept out of the repository at the owner's
instruction. No test calls the service. Rubric form 1 is the only accepted form.
The yes/no label is yes at a weight of 0.5 or more, otherwise no.
The encoded-body byte cap is a guard, not a guarantee of token use; the gateway's
post-call cap check still holds. No retries or redirects; timeout is 30 seconds.
"""

import json
import math
import os
from typing import Any
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.request import Request as HTTPRequest

from ..types import Request
from .base import Reply


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


urlopen = build_opener(NoRedirect()).open


def question_for(request: Request, order: tuple[str, ...]) -> dict[str, Any]:
    """Accept only the closed rubric form, before any transport call."""
    if request.kind not in ("yes_no", "choice"):
        raise ValueError("unsupported question kind")
    try:
        rubric = json.loads(request.rubric_text)
    except ValueError:
        raise ValueError("invalid rubric form") from None
    if (
        not isinstance(rubric, dict)
        or set(rubric) != {"instructions", "criteria"}
        or not isinstance(rubric["instructions"], str)
        or not rubric["instructions"].strip()
        or not isinstance(rubric["criteria"], list)
    ):
        raise ValueError("invalid rubric form")
    criteria = rubric["criteria"]
    if any(
        not isinstance(row, dict)
        or set(row) != {"label", "description"}
        or not isinstance(row["label"], str)
        or not isinstance(row["description"], str)
        for row in criteria
    ):
        raise ValueError("invalid rubric criteria")
    question: dict[str, Any] = {
        "type": "noul" if request.kind == "yes_no" else "choice",
        "instructions": rubric["instructions"],
    }
    if request.kind == "yes_no":
        if criteria:
            raise ValueError("yes_no criteria must be empty")
    else:
        descriptions = {row["label"]: row["description"] for row in criteria}
        if (
            not 2 <= len(order) <= 255
            or len(set(order)) != len(order)
            or len(descriptions) != len(criteria)
            or set(descriptions) != set(order)
            or set(order) != set(request.labels)
        ):
            raise ValueError("criteria and order labels differ")
        question["criteria"] = {label: descriptions[label] for label in order}
    return question


def signal(value: Any) -> float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("invalid provider response")
    return float(value)


def parse_reply(result: Any, request: Request) -> Reply:
    """Return only typed evidence; diagnostics contain no response content."""
    try:
        model = result["model"]
        answer = result["answers"]["decision"]
        usage = result["usage"]
        counts = (usage["input_tokens"], usage["output_tokens"])
        if not isinstance(model, str) or any(
            type(count) is not int or count < 0 for count in counts
        ):
            raise ValueError("invalid provider response")
        if request.kind == "yes_no":
            if answer["type"] != "noul":
                raise ValueError("invalid provider response")
            weight = signal(answer["noul"])
            label = "yes" if weight >= 0.5 else "no"
            scores = {"yes": weight, "no": 1 - weight}
        else:
            if answer["type"] != "choice":
                raise ValueError("invalid provider response")
            label = answer["choice"]
            probabilities = answer["probabilities"]
            if (
                not isinstance(label, str)
                or label not in request.labels
                or not isinstance(probabilities, dict)
                or set(probabilities) != set(request.labels)
            ):
                raise ValueError("invalid provider response")
            confidence = answer["confidence"]
            if type(confidence) not in (int, float) or not math.isfinite(confidence):
                raise ValueError("invalid provider response")
            scores = {label: signal(value) for label, value in probabilities.items()}
        return Reply(label, scores, model, sum(counts))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("invalid provider response") from None


class JevProvider:
    name = "jev"
    model = "jev-1.14.0"

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def answer(
        self, request: Request, order: tuple[str, ...], token_limit: int
    ) -> Reply | None:
        question = question_for(request, order)
        key = os.environ.get("JEV_PRO_API_KEY")
        if not key or token_limit <= 0:
            return None
        payload = {
            "model": self.model,
            "state": request.input_text,
            "questions": {"decision": question},
        }
        body = json.dumps(payload).encode("utf-8")
        if token_limit < len(body):
            return None
        call = HTTPRequest(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "eii-typed-decision-tool",
            },
            method="POST",
        )
        with urlopen(call, timeout=30) as response:
            try:
                result = json.load(response)
            except ValueError:
                raise ValueError("invalid provider response") from None
        return parse_reply(result, request)
