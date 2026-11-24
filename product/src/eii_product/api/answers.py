"""BE-65/66 buffered answer events, retained in process for reconnection."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from eii_product.assistant.accounting import CHECKS, account, referenced
from eii_product.assistant.catalogue.brief import check_brief
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.models import Bundle
from eii_product.assistant.playbooks.registry import Definition
from eii_product.assistant.templates.status import plan_step
from eii_product.assistant.templates.writer import Draft, compose

Gate = Callable[[Draft, Bundle, Definition, Catalogue], Awaitable[dict[str, bool]]]


async def default_gate(
    draft: Draft, bundle: Bundle, definition: Definition, catalogue: Catalogue
) -> dict[str, bool]:
    return account(draft, bundle, definition, catalogue)


@dataclass(frozen=True)
class Event:
    id: int
    kind: str
    data: Any


class Answer:
    """A single producer survives reader disconnects; replay never reruns tools."""

    def __init__(
        self,
        answer_id: str,
        bundle: Bundle,
        definition: Definition,
        catalogue: Catalogue,
        *,
        gate: Gate = default_gate,
        candidate: Draft | None = None,
    ) -> None:
        self.answer_id = answer_id
        self.bundle = bundle
        self.definition = definition
        self.catalogue = catalogue
        self.gate = gate
        self.candidate = candidate
        self.history: list[Event] = []
        self.failures: list[dict[str, Any]] = []
        self.changed = asyncio.Condition()
        self.task: asyncio.Task[None] | None = None
        self.closed = False
        self.sent: set[str] = set()

    async def emit(self, kind: str, data: Any) -> None:
        async with self.changed:
            self.history.append(Event(len(self.history) + 1, kind, data))
            if kind in {"error", "done"}:
                self.closed = True
            self.changed.notify_all()

    async def events(self, after: int = 0) -> AsyncIterator[Event]:
        if after < 0 or after > len(self.history):
            raise ValueError("INVALID_ARGUMENT")
        if self.task is None:
            self.task = asyncio.create_task(self.produce())
        cursor = after
        while True:
            async with self.changed:
                while len(self.history) <= cursor and not self.closed:
                    await self.changed.wait()
                pending = self.history[cursor:]
                finished = self.closed
            for event in pending:
                cursor = event.id
                yield event
            if finished:
                return

    async def checked(self, draft: Draft) -> dict[str, bool]:
        facts = {
            key: evidence.returned() for key, evidence in self.bundle.facts.items()
        }
        # Catalogue validation always precedes the five checks, even for fallback.
        valid = check_brief(self.catalogue, draft.brief, facts) is None
        result = await self.gate(draft, self.bundle, self.definition, self.catalogue)
        if set(result) != set(CHECKS) or any(
            type(value) is not bool for value in result.values()
        ):
            raise ValueError("accounting_result_invalid")
        result["Nothing invented"] &= valid
        result["Sources"] &= referenced(draft.brief) <= self.sent
        return result

    def log_failure(self) -> None:
        row = dict(
            ts=datetime.now(UTC).isoformat(),
            level="error",
            event="accounting_failed",
            answer_id=self.answer_id,
            seat_key="",
            tool=None,
            engine=None,
            release_id=self.bundle.release_id,
            status="fallback",
            duration_ms=None,
            error_code="ACCOUNTING_FAILED",
            error_id=str(uuid4()),
        )
        self.failures.append(row)
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))

    async def produce(self) -> None:
        try:
            for step in self.bundle.steps:
                await self.emit("plan_step", plan_step(step))
            for directive in self.bundle.stage:
                from eii_product.tools.stage import stage

                stage(directive, self.catalogue)
                await self.emit("stage", directive)
            for card in self.bundle.cards:
                identities = card["fact_ids"]
                if not all(
                    identity in self.bundle.facts
                    and self.bundle.facts[identity].valid(self.bundle.release_id)
                    and self.bundle.facts[identity].fact.provenance == "public"
                    and self.bundle.facts[identity].fact.input_classes == ["public"]
                    for identity in identities
                ):
                    raise ValueError("lineage_incomplete")
                await self.emit(
                    "evidence",
                    {
                        **card,
                        "facts": [
                            self.bundle.facts[identity].wire()
                            for identity in identities
                        ],
                    },
                )
                self.sent.update(identities)
            draft = self.candidate or compose(
                self.bundle, self.definition, self.catalogue
            )
            checks = await self.checked(draft)
            if not all(checks.values()):
                self.log_failure()
                draft = compose(self.bundle, self.definition, self.catalogue)
                checks = await self.checked(draft)
                if not all(checks.values()):
                    raise ValueError("fallback_invalid")
            await self.emit(
                "receipt",
                {
                    "Checked before display": {
                        **checks,
                        "assumptions": draft.assumptions,
                        "caveat_keys": draft.caveat_keys,
                        "coverage_keys": draft.coverage_keys,
                    },
                    "egress": [],
                },
            )
            await self.emit(
                "status",
                {
                    "writer": "template",
                    "status": "OK",
                    "template_key": "template_writer",
                    "note_key": "template_writer",
                },
            )
            for value in draft.brief.values():
                for item in value if isinstance(value, list) else [value]:
                    await self.emit("narrative", item)
            await self.emit("done", {"answer_id": self.answer_id, "brief": draft.brief})
        except Exception:
            # Driver/validation exception text never enters a log or the wire.
            await self.emit(
                "error",
                {
                    "code": "ANSWER_FAILED",
                    "message_key": "answer_failed",
                    "error_id": str(uuid4()),
                },
            )
