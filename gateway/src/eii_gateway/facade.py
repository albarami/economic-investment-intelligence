"""Offline evidence only: never a fact, gate result, tool argument or recommendation."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from .memo import digest, input_hash, memo_key, option_orders
from .policy import check_policy
from .providers.base import Provider, Reply
from .providers.none_provider import NoneProvider
from .providers.recorded_provider import RecordedProvider
from .records import RecordStore
from .schema import Record
from .settings import configured_provider
from .thresholds import THRESHOLD, outcome
from .types import CLASS_RULES, Outcome, Request


class Gateway:
    """One explicit offline run. A zero cap forbids configured-provider egress."""

    def __init__(
        self,
        root: Path,
        *,
        fixtures: Path | None = None,
        endpoint: str | None = None,
        token_cap: int = 0,
    ) -> None:
        if type(token_cap) is not int or token_cap < 0:
            raise ValueError("invalid token cap")
        self.root = root
        self.fixtures = fixtures
        self.endpoint = endpoint
        self.remaining = token_cap
        self.configured = configured_provider()
        self.provider: Provider | None = None

    def _provider(self) -> Provider:
        if self.provider is not None:
            return self.provider
        if self.configured == "none":
            self.provider = NoneProvider()
        elif self.configured == "recorded":
            if self.fixtures is None:
                raise ValueError("recorded provider requires fixtures")
            self.provider = RecordedProvider(self.fixtures)
        else:
            if self.endpoint is None:
                raise ValueError("configured provider requires an explicit endpoint")
            from .providers.jev_provider import JevProvider

            self.provider = JevProvider(self.endpoint)
        return self.provider

    def decide(self, request: Request) -> Record:
        check_policy(request.input_class, request.decision_class)
        provider = self._provider()
        store = RecordStore(self.root)
        key = memo_key(request, provider.model)
        previous = store.first(key)
        if previous is not None:
            replay = {
                **previous,
                "recorded_at": datetime.now(UTC).isoformat(),
                "latency_ms": 0.0,
            }
            store.write(replay)
            return replay
        start = perf_counter()
        orders = option_orders(request)
        result: Reply | None = None
        status: Outcome = "DISABLED" if provider.name == "none" else "UNAVAILABLE"
        try:
            replies: list[Reply] = []
            for order in orders:
                if provider.name == "jev" and self.remaining == 0:
                    break
                reply = provider.answer(request, order, self.remaining)
                if reply is None:
                    break
                reply.validate(request, provider.model)
                if reply.tokens > self.remaining:
                    raise ValueError("token cap exceeded")
                self.remaining -= reply.tokens
                replies.append(reply)
            if len(replies) == len(orders):
                result = replies[0]
                status = (
                    "DECIDED"
                    if all(
                        reply.label == result.label
                        and outcome(request.kind, reply.label, reply.scores)
                        == "DECIDED"
                        for reply in replies
                    )
                    else "BELOW_THRESHOLD"
                )
        except (OSError, ValueError, KeyError, TypeError):
            # No provider exception text or payload is persisted.
            status = "ERROR"
        record: Record = {
            "decision_class": request.decision_class,
            "kind": request.kind,
            "provider_configured": self.configured,
            "provider_used": provider.name,
            "reported_model_id": provider.model,
            "rubric_id": request.rubric_id,
            "rubric_sha256": digest(request.rubric_text),
            "input_class": request.input_class,
            "input_sha256": input_hash(request),
            "language": request.language,
            "route": request.route,
            "option_order": [list(order) for order in orders],
            "returned_label": result.label if result else None,
            "returned_scores": result.scores if result else {},
            "top_score": max(result.scores.values()) if result else None,
            "threshold_in_force": dict(THRESHOLD),
            "threshold_outcome": status,
            "memo_key": key,
            "latency_ms": (perf_counter() - start) * 1000,
            "fallback_applied": status != "DECIDED",
            "permitted_effect": CLASS_RULES[request.decision_class][1],
            "recorded_at": datetime.now(UTC).isoformat(),
            "human_disposition": None,
        }
        store.write(record)
        return record
