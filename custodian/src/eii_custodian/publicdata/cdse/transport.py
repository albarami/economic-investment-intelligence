"""Closed injected exchanges. No environment reader or socket.

Process JSON follows the official readings in README. Live endpoint admission
remains separate from documentation reading and requires the lead's review.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, quote_plus, urlsplit

if TYPE_CHECKING:
    from eii_custodian.publicdata.cdse.wire import ProcessSpec

REVIEWED_ENDPOINTS: Mapping[str, str] = {}
KINDS = frozenset({"token", "process"})
HASH = re.compile(r"[a-f0-9]{64}")


class CdseError(ValueError):
    """A sanitized refusal safe for the lead's report."""


@dataclass(frozen=True, repr=False)
class Credentials:
    client: str
    secret: str

    def __repr__(self) -> str:
        return "Credentials([redacted])"

    def __getstate__(self) -> object:
        raise TypeError("credentials are not serializable")


@dataclass(frozen=True, repr=False)
class Request:
    kind: str
    url: str
    body: dict[str, Any]
    headers: dict[str, str]

    def __repr__(self) -> str:
        return "Request([redacted])"


@dataclass(frozen=True, repr=False)
class Reply:
    status: int
    body: bytes
    redirect: str = ""


Sender = Callable[[Request], Reply]


def validate_request(request: Request) -> None:
    """Reject any URL, field or auth shape outside the reviewed closed schema."""
    if not REVIEWED_ENDPOINTS:
        raise CdseError("provider_contract_pending")
    if request.kind not in KINDS or request.url != REVIEWED_ENDPOINTS.get(request.kind):
        raise CdseError("request_refused")
    from eii_custodian.publicdata.fetch.allowlist import approve

    if not approve(request.url).ok:
        raise CdseError("request_host_refused")
    parts = urlsplit(request.url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.port not in (None, 443)
        or any(ord(c) <= 32 for c in request.url)
    ):
        raise CdseError("request_refused")
    if request.kind == "token":
        valid = (
            set(request.body) == {"grant_type", "client_id", "client_secret"}
            and request.body.get("grant_type") == "client_credentials"
            and bool(request.body.get("client_id"))
            and bool(request.body.get("client_secret"))
            and request.headers == {"Content-Type": "application/x-www-form-urlencoded"}
        )
    else:
        from eii_custodian.publicdata.cdse.wire import validate_process_body

        validate_process_body(request.body)
        valid = (
            set(request.headers) == {"Authorization", "Content-Type", "Accept"}
            and request.headers.get("Content-Type") == "application/json"
            and request.headers.get("Accept") == "application/x-tar"
            and request.headers.get("Authorization", "").startswith("Bearer ")
            and len(request.headers["Authorization"]) > len("Bearer ")
        )
    if not valid:
        raise CdseError("request_schema_refused")


@dataclass(repr=False)
class Session:
    """Enumerate every attempt before send. Any refusal permanently stops a run."""

    credentials: Credentials = field(repr=False)
    sender: Sender = field(repr=False)
    plan: tuple[str, ...]
    _position: int = field(default=0, init=False)
    _token: str = field(default="", init=False, repr=False)
    _stopped: bool = field(default=False, init=False)
    _issued_tokens: list[str] = field(default_factory=list, init=False, repr=False)

    def __repr__(self) -> str:
        return "Session([redacted])"

    def __getstate__(self) -> object:
        raise TypeError("session is not serializable")

    def redact(self, text: str) -> str:
        """Keep provider refusal text, removing raw and common encoded values."""
        values = (
            self.credentials.client,
            self.credentials.secret,
            *self._issued_tokens,
        )
        expanded = {
            variant
            for value in values
            if value
            for variant in (
                value,
                quote(value, safe=""),
                quote_plus(value),
                json.dumps(value)[1:-1],
            )
        }
        for value in sorted(expanded, key=len, reverse=True):
            text = text.replace(value, "[redacted]")
        return text

    def _send(self, kind: str, body: dict[str, Any]) -> bytes:
        if self._stopped:
            raise CdseError("run_stopped_fresh_budget_required")
        try:
            if self._position >= len(self.plan) or self.plan[self._position] != kind:
                raise CdseError("request_budget_exhausted")
            if kind not in KINDS:
                raise CdseError("request_schema_refused")
            if kind != "token" and not self._token:
                raise CdseError("authentication_required")
            headers = (
                {"Content-Type": "application/x-www-form-urlencoded"}
                if kind == "token"
                else {
                    "Authorization": "Bearer " + self._token,
                    "Content-Type": "application/json",
                    "Accept": "application/x-tar",
                }
            )
            request = Request(kind, REVIEWED_ENDPOINTS.get(kind, ""), body, headers)
            validate_request(request)
            self._position += 1  # Conservative: even a failed send consumes its slot.
            try:
                reply = self.sender(request)
            except Exception as exc:
                raise CdseError(self.redact(str(exc))) from None
            if reply.redirect or 300 <= reply.status < 400:
                raise CdseError("redirect_refused")
            if reply.status != 200:
                raise CdseError(
                    self.redact(reply.body.decode("utf-8", errors="replace"))
                )
            return reply.body
        except (CdseError, ValueError):
            self._stopped = True
            raise

    def token(self) -> None:
        """Keep the auth exchange only in memory; never return or store it."""
        body = self._send(
            "token",
            {
                "grant_type": "client_credentials",
                "client_id": self.credentials.client,
                "client_secret": self.credentials.secret,
            },
        )
        try:
            row = json.loads(body)
            if (
                not isinstance(row, dict)
                or set(row) - {"access_token", "token_type", "expires_in"}
                or not isinstance(row.get("access_token"), str)
                or not row["access_token"]
                or row.get("token_type") != "Bearer"
                or any(ord(c) <= 32 for c in row["access_token"])
            ):
                raise ValueError
            self._token = row["access_token"]
            self._issued_tokens.append(self._token)
        except (ValueError, TypeError):
            self._stopped = True
            raise CdseError("authentication_schema_refused") from None

    def _asset(self, kind: str, spec: ProcessSpec) -> bytes:
        from eii_custodian.publicdata.cdse.wire import ProcessSpec, process_body

        try:
            if not isinstance(spec, ProcessSpec):
                raise CdseError("request_schema_refused")
            body = self._send(kind, process_body(spec))
        except ValueError:
            self._stopped = True
            raise
        if self.redact(body.decode("utf-8", errors="replace")) != body.decode(
            "utf-8", errors="replace"
        ):
            self._stopped = True
            raise CdseError("response_contains_secret")
        return body

    def picture(self, spec: ProcessSpec) -> bytes:
        """Read one budgeted raster/metadata tar; no retries or refresh implicit."""
        return self._asset("process", spec)

    def metadata(self, spec: ProcessSpec) -> bytes:
        """Extra metadata-only endpoint remains pending; Process returns its dates."""
        self._stopped = True
        raise CdseError("metadata_endpoint_pending_use_process_userdata")
