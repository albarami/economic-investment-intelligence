"""C2: compare first answers with the one admitted overall interval."""

from typing import Any
from urllib.error import HTTPError

from eii_gateway.providers.base import Provider, Reply
from eii_gateway.types import Request

from .interval import Summary, inside_stated, interval
from .route import MODELS

PROTOCOL_DIFFERENCES = (
    "Option orders are hash-derived, not the original order.",
    "Activity labels are sent with the isic- prefix.",
    "The admitted run was made before the gateway existed.",
    "The adapter cuts the yes/no label at a weight of 0.5.",
)


class ObservedProvider:
    """Observe replies without changing the gateway's validation or acceptance."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.name = provider.name
        self.model = provider.model
        self.first: dict[str, str] = {}
        self.models: dict[str, list[str]] = {}
        self.calls_made = 0
        self.tokens_used = 0
        self.failure_status = "invalid response"

    def answer(
        self, request: Request, order: tuple[str, ...], token_limit: int
    ) -> Reply | None:
        self.calls_made += 1
        try:
            reply = self.provider.answer(request, order, token_limit)
        except HTTPError as exc:
            self.failure_status = str(exc.code)
            exc.close()
            raise
        except OSError as exc:
            self.failure_status = type(exc).__name__
            raise
        except (ValueError, KeyError, TypeError):
            self.failure_status = "invalid response"
            raise
        if reply is None:
            self.calls_made -= 1
        if reply is not None:
            if reply.model != self.model:
                self.failure_status = "model drift"
            self.models.setdefault(request.case_id, []).append(reply.model)
            # Validate the response shape independently of the pinned identity;
            # the gateway still validates that identity and enforces its cap.
            reply.validate(request, reply.model)
            self.tokens_used += reply.tokens
            self.first.setdefault(request.case_id, reply.label)
        return reply


def model_reply_counts(rows: list[dict[str, Any]], pinned: str) -> dict[str, int]:
    """Count the recorded identity of every reply, including either choice order."""
    models = [model for row in rows for model in row["response_models"]]
    return {
        "pinned": sum(model == pinned for model in models),
        "other_or_missing": sum(model != pinned for model in models),
    }


def answer_summary(rows: list[dict[str, Any]], pinned: str) -> Summary:
    """Only a first reply naming the configured model contributes an answer."""
    included = [
        row
        for row in rows
        if row["response_models"]
        and row["response_models"][0] == pinned
        and row["label"] is not None
    ]
    return interval(sum(row["correct"] for row in included), len(included))


def reproduction(
    provider: str, rows: list[dict[str, Any]], admitted: dict[str, Any]
) -> dict[str, Any]:
    """Return deterministic evidence; a replay never becomes a keyed measurement."""
    summary = answer_summary(rows, MODELS[provider])
    family_matches = all(
        model == MODELS["jev"] for row in rows for model in row["response_models"]
    )
    within = inside_stated(summary["rate"], admitted["ci95"])
    if provider != "jev":
        reason = "not_keyed"
    elif not family_matches:
        reason = "model_family_mismatch"
    elif summary["total"] != admitted["answered"]:
        reason = "incomplete_answers"
    elif not within:
        reason = "outside_stated_interval"
    else:
        reason = "reproduced"
    return {
        "overall": summary,
        "stated_ci95": admitted["ci95"],
        "inside_stated_interval": within,
        "admitted_measurement_reproduced": reason == "reproduced",
        "reproduction_reason": reason,
        "route_status": "requalify" if not family_matches else "match",
    }
