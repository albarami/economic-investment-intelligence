"""Request log: a test never reaches a map provider (S3-T16, TST-248, TST-255).

Every name lookup outside loopback is refused and logged. The test fails at
teardown when the log is not empty, so product code that swallows the refusal
still cannot pass. The provider keys and service bases are removed for every
test; a test that needs them sets invented values itself.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator

import pytest

REASON = "provider_request_refused"
PROVIDER_SETTINGS = (
    "ESRI_API_KEY",
    "MAPTILE_API_KEY",
    "EII_IMAGERY_TILE_BASE",
    "EII_PHOTOREAL_TILE_BASE",
)


def loopback(host: object) -> bool:
    """True for no host, ``localhost`` or a loopback address literal."""
    if host is None:
        return True
    name = host.decode("ascii", "replace") if isinstance(host, bytes) else str(host)
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def provider_request_log(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    for name in PROVIDER_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    log: list[str] = []
    original = socket.getaddrinfo

    def guarded(host: object, *args: object, **kwargs: object) -> object:
        if not loopback(host):
            log.append(str(host))
            raise socket.gaierror(f"{REASON}: {host}")
        return original(host, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket, "getaddrinfo", guarded)
    yield log
    if log:
        pytest.fail(f"{REASON}: {', '.join(log)}", pytrace=False)
