"""Lead-operated fc_register_paged_capture@v1: never persist a raw response.

The supplied visitor session is the producer's operational choice. It must use
verified TLS, the reviewed pin and no credentials. Only the producer sends POSTs;
consumers replay fragments without manufacturing delivered form state.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..fetch.certificate_pins import Capture, Pin, PinError, admit_capture, intake_file
from ..fetch.page_identity import RequestIdentity
from ..fetch.page_schema import validate
from ..fetch.receipts import sha256_hex
from ..fetch.snapshots import utc
from ..fetch.transport import Transport
from .acquire import pages
from .constants import PROJECTION, URL


def produce(
    cache: Path,
    visitor: Transport,
    pin: Pin,
    review: Mapping[str, Any],
    *,
    tool: str,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> None:
    """Validate the entire visitor chain and project in memory before any write."""
    validate(review)
    if review["hold"] is not None or review["max_bytes"] is None or not tool.strip():
        raise PinError("capture_evidence_missing")
    stamp = clock()
    utc(stamp)
    acquired = pages(
        visitor,
        cache,
        {pin.host: pin},
        review["shape"],
        review["max_bytes"],
        sleep,
        captures=False,
    )
    outputs: list[tuple[Path, bytes]] = []
    for response in acquired:
        identity = RequestIdentity.load(response.evidence["request_identity"])
        capture = Capture(
            response.body,
            URL,
            response.final_url,
            response.hops,
            tool,
            stamp,
            sha256_hex(response.body),
            pin,
            True,
            "visitor",
            identity,
            PROJECTION,
            response.body_sha256,
        )
        _, evidence = admit_capture(capture, URL, identity=identity)
        file = f"fragment-{identity.ordinal}.json"
        receipt = {
            k: v
            for k, v in evidence.items()
            if k not in {"redirect_urls", "upstream_evidence"}
        }
        receipt.update(file=file, hops=list(response.hops))
        outputs.extend(
            [
                (intake_file(cache, "fc_register", file), response.body),
                (
                    intake_file(
                        cache, "fc_register", f"capture-{identity.ordinal}.json"
                    ),
                    json.dumps(receipt, sort_keys=True).encode(),
                ),
            ]
        )
    if any(path.exists() for path, _ in outputs):
        raise PinError("capture_overwrite_refused")
    for path, body in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(body)
