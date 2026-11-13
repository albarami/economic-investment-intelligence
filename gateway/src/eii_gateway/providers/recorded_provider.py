"""Replay tiny hand-authored synthetic fixtures; no network or vendor imports."""

import json
from pathlib import Path

from ..memo import input_hash
from ..types import Request
from .base import Reply


class RecordedProvider:
    name = "recorded"
    model = "synthetic-recorded"

    def __init__(self, fixtures: Path) -> None:
        self.rows = json.loads(fixtures.read_text(encoding="utf-8"))

    def answer(
        self, request: Request, order: tuple[str, ...], token_limit: int
    ) -> Reply | None:
        for row in self.rows:
            if (
                row["case_id"] == request.case_id
                and row["input_sha256"] == input_hash(request)
                and row["order"] == list(order)
            ):
                return Reply(row["label"], row["scores"], self.model, row["tokens"])
        return None
