"""UNVERIFIED HTTP request shape; never imported or called by the default suite.

R1 / OI-01 / OI-18: no build key, live call or qualification. The explicit tooling
caller supplies the endpoint and token cap. This stdlib adapter is provisional;
S1-T08 must confirm its wire shape and route before any authorised live use.
"""

import json
import os
from urllib.request import Request as HTTPRequest
from urllib.request import urlopen

from ..types import Request
from .base import Reply


class JevProvider:
    name = "jev"
    model = "jev-1.14.0"

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def answer(
        self, request: Request, order: tuple[str, ...], token_limit: int
    ) -> Reply | None:
        key = os.environ.get("JEV_PRO_API_KEY")
        if not key or token_limit <= 0:
            return None
        payload = {
            "model": self.model,
            "state": request.input_text,
            "question_type": request.kind,
            "instructions": request.rubric_text,
            "criteria": list(order),
            "max_tokens": token_limit,
        }
        call = HTTPRequest(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(call, timeout=30) as response:
            result = json.load(response)
        return Reply(
            result["label"],
            result["scores"],
            result["model"],
            result["usage"]["total_tokens"],
        )
