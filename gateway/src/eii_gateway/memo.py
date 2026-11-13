"""Canonical hashes and fixed hash-derived option orders (DAT-126)."""

import hashlib
import json
import unicodedata

from .types import Request

ADAPTER_VERSION = "offline-v1"


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n"))


def input_hash(request: Request) -> str:
    return digest(normalise(request.input_text))


def memo_key(request: Request, model: str) -> str:
    return digest(
        canonical(
            [
                request.decision_class,
                digest(request.rubric_text),
                [
                    normalise(request.input_text),
                    request.input_class,
                    request.language,
                    request.kind,
                    request.options,
                    request.route,
                    request.rubric_id,
                    request.case_id,
                ],
                model,
                ADAPTER_VERSION,
            ]
        )
    )


def option_orders(request: Request) -> tuple[tuple[str, ...], ...]:
    first = tuple(
        sorted(request.labels, key=lambda label: digest(input_hash(request) + label))
    )
    return (
        (first, tuple(reversed(first)))
        if request.kind == "choice"
        else (request.labels,)
    )
