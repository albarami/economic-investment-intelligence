"""Complete default provider: no I/O, settings, key access or adapter imports."""

from ..types import Request
from .base import Reply


class NoneProvider:
    name = "none"
    model = "none"

    def answer(
        self, request: Request, order: tuple[str, ...], token_limit: int
    ) -> Reply | None:
        return None
