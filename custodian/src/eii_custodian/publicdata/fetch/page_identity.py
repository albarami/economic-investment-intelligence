"""A request identity contains no delivered state or credentials."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .page_html import ShapeError


def digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


@dataclass(frozen=True)
class RequestIdentity:
    method: str
    url: str
    target: str | None
    argument: str | None
    ordinal: int
    preceding_sha256: str | None

    def data(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def load(cls, value: object) -> RequestIdentity:
        if not isinstance(value, dict) or set(value) != {
            "method",
            "url",
            "target",
            "argument",
            "ordinal",
            "preceding_sha256",
        }:
            raise ShapeError("capture_identity_mismatch")
        from ..fc_register.constants import TARGETS, URL

        if not isinstance(value["url"], str) or type(value["ordinal"]) is not int:
            raise ShapeError("capture_identity_mismatch")
        if value["ordinal"] == 1:
            if value["method"] != "GET" or any(
                value[k] is not None for k in ("target", "argument", "preceding_sha256")
            ):
                raise ShapeError("capture_identity_mismatch")
        elif (
            value["ordinal"] < 2
            or value["method"] != "POST"
            or value["url"] != URL
            or value["target"] not in TARGETS
            or value["argument"] != ""
            or not digest(value["preceding_sha256"])
        ):
            raise ShapeError("capture_identity_mismatch")
        return cls(**value)
