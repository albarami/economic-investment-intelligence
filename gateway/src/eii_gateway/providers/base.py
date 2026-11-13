"""Provider protocol returning bounded labels and private ranking signals."""

import math
from dataclasses import dataclass
from typing import Protocol

from ..types import Request


@dataclass(frozen=True)
class Reply:
    label: str
    scores: dict[str, float]
    model: str
    tokens: int

    def validate(self, request: Request, model: str) -> None:
        if self.model != model or self.label not in request.labels:
            raise ValueError("provider model or label differs from closed request")
        if set(self.scores) != set(request.labels):
            raise ValueError("provider score labels differ from request")
        if any(
            type(score) not in (int, float)
            or not math.isfinite(score)
            or not 0 <= score <= 1
            for score in self.scores.values()
        ):
            raise ValueError("invalid ranking signal")
        if type(self.tokens) is not int or self.tokens < 0:
            raise ValueError("invalid token usage")


class Provider(Protocol):
    name: str
    model: str

    def answer(
        self, request: Request, order: tuple[str, ...], token_limit: int
    ) -> Reply | None: ...
