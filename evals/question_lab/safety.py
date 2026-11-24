"""Offline harness boundaries, independent of application provider settings."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch


def child_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """An allowlist, never inherited credentials or untrusted provider options."""
    kept = {
        key: environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "UV_CACHE_DIR")
        if key in environ
    }
    return {
        **kept,
        "EII_DECISION_PROVIDER": "none",
        "UV_OFFLINE": "1",
        "TZ": "UTC",
        "LANG": "C.UTF-8",
    }


@contextmanager
def loopback_only(attempts: list[str]) -> Iterator[None]:
    """Refuse even caught socket attempts. Numeric loopback needs no DNS."""
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_sendmsg = socket.socket.sendmsg

    def allowed(address: object) -> None:
        if not isinstance(address, tuple) or not address:
            attempts.append("non_loopback_attempt")
            raise PermissionError("non_loopback_attempt")
        try:
            valid = ipaddress.ip_address(str(address[0])).is_loopback
        except ValueError:
            valid = False
        if not valid:
            attempts.append("non_loopback_attempt")
            raise PermissionError("non_loopback_attempt")

    def connect(sock: socket.socket, address: object) -> None:
        allowed(address)
        original(sock, address)  # type: ignore[arg-type]

    def connect_ex(sock: socket.socket, address: object) -> int:
        allowed(address)
        return original_ex(sock, address)  # type: ignore[arg-type]

    def lookup(*_args: object, **_kwargs: object) -> object:
        attempts.append("dns_attempt")
        raise PermissionError("dns_attempt")

    def sendto(sock: socket.socket, data: bytes, *args: Any) -> int:
        allowed(args[-1] if args else None)
        return original_sendto(sock, data, *args)

    def sendmsg(sock: socket.socket, *args: Any) -> int:
        allowed(args[3] if len(args) == 4 else None)
        return original_sendmsg(sock, *args)

    with (
        patch.object(socket.socket, "connect", connect),
        patch.object(socket.socket, "connect_ex", connect_ex),
        patch.object(socket.socket, "sendto", sendto),
        patch.object(socket.socket, "sendmsg", sendmsg),
        patch.object(socket, "getaddrinfo", lookup),
        patch.object(socket, "gethostbyname", lookup),
        patch.object(socket, "gethostbyname_ex", lookup),
    ):
        yield
