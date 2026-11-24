"""S3-T16: tests never call the imagery or photorealistic 3D provider.

The request log of ``pytest_no_provider`` refuses every name lookup outside
loopback and fails the test at teardown, even when product code swallows the
refusal. Each plant runs in its own pytest child with no key in its
environment; nothing here opens a connection.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from pytest_no_provider import loopback

ROOT = Path(__file__).resolve().parents[2]
REASON = "provider_request_refused"
AUDIT_REASON = "provider_audit_refused"

# Installed before pytest/provider imports; independent of the pytest predicate
# so a classification plant cannot disable this process-level safety boundary.
AUDIT_RUNNER = """
import ipaddress
import runpy
import sys

attempts = []

def audit(event, args):
    if event == "socket.getaddrinfo":
        host = args[0]
    elif event == "socket.connect":
        address = args[1]
        host = address[0] if isinstance(address, tuple) else address
    else:
        return
    try:
        local = host in (None, "localhost", b"localhost") or ipaddress.ip_address(
            host.decode("ascii") if isinstance(host, bytes) else host
        ).is_loopback
    except (ValueError, UnicodeError):
        local = False
    if not local:
        attempts.append(f"{event}: {host}")
        raise PermissionError(f"provider_audit_refused: {event}: {host}")

sys.addaudithook(audit)
try:
    if sys.argv[1] == "audit":
        runpy.run_path(sys.argv[2])["test_plant"]()
    else:
        import pytest
        raise SystemExit(pytest.main(sys.argv[2:]))
finally:
    if attempts:
        print("provider_audit_refused: " + ", ".join(attempts))
        raise SystemExit(1)
"""

IMAGERY_PLANT = """
from urllib.request import urlopen
import eii_product.imagery_provider.address as address

def test_plant():
    address.FIND_ADDRESS_CANDIDATES = "https://geocode.provider.invalid/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
    try:
        address.live_transport(urlopen)("SYN-street", "en", "")
    except Exception:
        pass
"""

SATELLITE_PLANT = """
from eii_product.photoreal_tiles.proxy import satellite_credit, tile_opener

def test_plant():
    assert satellite_credit(tile_opener, "https://imagery.provider.invalid/MapServer", "") == ""
"""

PHOTOREAL_PLANT = """
from eii_product.photoreal_tiles.proxy import fetch_tile, tile_opener

def test_plant():
    try:
        fetch_tile(tile_opener, "https://tiles.provider.invalid/v1", "3dtiles/root.json", "", satellite=False)
    except Exception:
        pass
"""

PLANTS = [
    (IMAGERY_PLANT, "geocode.provider.invalid"),
    (SATELLITE_PLANT, "imagery.provider.invalid"),
    (PHOTOREAL_PLANT, "tiles.provider.invalid"),
]

LOOPBACK_ONLY = """
import socket

def test_plant():
    socket.getaddrinfo("localhost", 0)
    socket.getaddrinfo("127.0.0.1", 0)
    socket.getaddrinfo("::1", 0)
"""


def run_plant(
    tmp_path: Path,
    body: str,
    *,
    audit_only: bool = False,
    confcutdir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    plant = tmp_path / "test_planted_request.py"
    plant.write_text(body, encoding="utf-8")
    env = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "TMPDIR", "LANG", "UV_OFFLINE")
        if name in os.environ
    }
    env["PYTHONPATH"] = os.pathsep.join(
        str(ROOT / path) for path in (".", "scripts", "core/src", "product/src")
    )
    args = (
        [str(plant)]
        if audit_only
        else [
            "-p",
            "conftest",
            "-p",
            "pytest_no_provider",
            "-q",
            "--rootdir",
            str(ROOT),
            "-c",
            str(ROOT / "pyproject.toml"),
            str(plant),
        ]
    )
    if confcutdir is not None:
        args.extend(["--confcutdir", str(confcutdir)])
    return subprocess.run(
        [
            sys.executable,
            "-c",
            AUDIT_RUNNER,
            "audit" if audit_only else "pytest",
            *args,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


@pytest.mark.parametrize(
    ("body", "host"),
    PLANTS,
    ids=["imagery-address", "imagery-tiles", "photoreal-tiles"],
)
def test_planted_provider_request_without_key_fails(
    tmp_path: Path, body: str, host: str
) -> None:
    done = run_plant(tmp_path, body)
    assert done.returncode == 1, done.stdout + done.stderr
    assert REASON in done.stdout
    assert host in done.stdout


def test_loopback_lookup_passes(tmp_path: Path) -> None:
    done = run_plant(tmp_path, LOOPBACK_ONLY)
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize(
    ("body", "host"),
    [*PLANTS, (LOOPBACK_ONLY, None)],
    ids=["imagery-address", "imagery-tiles", "photoreal-tiles", "loopback"],
)
def test_plants_without_ancestor_conftest(
    tmp_path: Path, body: str, host: str | None
) -> None:
    # Match an outside-root plant's discovery without requiring external scratch.
    plant_dir = tmp_path / "isolated-plant"
    plant_dir.mkdir()
    done = run_plant(plant_dir, body, confcutdir=plant_dir)
    assert done.returncode == (0 if host is None else 1), done.stdout + done.stderr
    if host is not None:
        assert f"{REASON}: {host}" in done.stdout


@pytest.mark.parametrize(
    ("body", "host"),
    PLANTS,
    ids=["imagery-address", "imagery-tiles", "photoreal-tiles"],
)
def test_provider_paths_fail_runtime_audit(
    tmp_path: Path, body: str, host: str
) -> None:
    done = run_plant(tmp_path, body, audit_only=True)
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"{AUDIT_REASON}: socket.getaddrinfo: {host}" in done.stdout


@pytest.mark.parametrize(
    ("body", "event", "host"),
    [
        (
            "import socket as s; s.getaddrinfo('x.invalid', 443)",
            "socket.getaddrinfo",
            "x.invalid",
        ),
        (
            "import socket as s; s.socket().connect(('192.0.2.1', 443))",
            "socket.connect",
            "192.0.2.1",
        ),
    ],
)
def test_runtime_audit_refuses_alias_and_direct_connect(
    tmp_path: Path, body: str, event: str, host: str
) -> None:
    done = run_plant(tmp_path, "def test_plant():\n    " + body, audit_only=True)
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"{AUDIT_REASON}: {event}: {host}" in done.stdout


def test_runtime_audit_allows_loopback(tmp_path: Path) -> None:
    done = run_plant(tmp_path, LOOPBACK_ONLY, audit_only=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_runtime_audit_allows_local_connect_events(tmp_path: Path) -> None:
    body = """import sys
def test_plant():
    for host in ("localhost", "127.0.0.1", "::1", b"localhost"):
        sys.audit("socket.connect", None, (host, 443))
    sys.audit("invented.event", "x.invalid")
"""
    done = run_plant(tmp_path, body, audit_only=True)
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize("event", ["socket.getaddrinfo", "socket.connect"])
@pytest.mark.parametrize(
    "host",
    ["x.invalid", "0.0.0.0", "127.1", "localhost.", "x.localhost", b"x-\xff.invalid"],
)
def test_runtime_audit_records_swallowed_events(
    tmp_path: Path, event: str, host: str | bytes
) -> None:
    address = repr(host) if event == "socket.getaddrinfo" else f"None, ({host!r}, 443)"
    body = f"""import sys
def test_plant():
    try:
        sys.audit({event!r}, {address})
    except PermissionError as error:
        assert str(error).startswith({AUDIT_REASON!r})
"""
    done = run_plant(tmp_path, body, audit_only=True)
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"{AUDIT_REASON}: {event}: {host}" in done.stdout


# The oracle classifies address objects before host serialization; it does not
# repeat loopback's string parsing. Names are generated in an invented namespace.
@given(
    case=st.one_of(
        st.tuples(
            st.one_of(st.ip_addresses(), st.ip_addresses(v=4, network="127.0.0.0/8")),
            st.sampled_from(["", "%lo", "%1"]),
            st.booleans(),
        ).map(
            lambda value: (
                (str(value[0]) + value[1]).encode()
                if value[2]
                else str(value[0]) + value[1],
                value[0].is_loopback,
            )
        ),
        st.from_regex(r"[a-zA-Z][a-zA-Z0-9.-]{0,252}\.invalid", fullmatch=True).map(
            lambda name: (name, False)
        ),
        st.binary(max_size=255).map(lambda name: (b"x-" + name, False)),
        st.sampled_from(
            [
                (None, True),
                ("localhost", True),
                (b"localhost", True),
                ("", False),
                (b"", False),
            ]
        ),
    )
)
@example(case=(None, True))
@example(case=("localhost", True))
@example(case=(b"localhost", True))
@example(case=("127.0.0.1", True))
@example(case=("127.0.0.1%lo", True))
@example(case=("", False))
@example(case=(b"", False))
@example(case=("::1", True))
@example(case=("::1%lo", True))
@example(case=("0.0.0.0", False))
@example(
    case=("::ffff:127.0.0.1", ipaddress.ip_address("::ffff:127.0.0.1").is_loopback)
)
@example(case=("127.1", False))
@example(case=("localhost.", False))
@example(case=("LOCALHOST", False))
@example(case=("x.localhost", False))
@example(case=("localhost.provider.invalid", False))
def test_loopback_matches_ipaddress(case: tuple[str | bytes | None, bool]) -> None:
    host, expected = case
    assert loopback(host) is expected


def test_lookup_is_refused_in_process(provider_request_log: list[str]) -> None:
    with pytest.raises(socket.gaierror, match=REASON):
        socket.getaddrinfo("tiles.provider.invalid", 443)
    assert provider_request_log == ["tiles.provider.invalid"]
    provider_request_log.clear()


@pytest.mark.parametrize(
    "name",
    [
        "ESRI_API_KEY",
        "MAPTILE_API_KEY",
        "EII_IMAGERY_TILE_BASE",
        "EII_PHOTOREAL_TILE_BASE",
    ],
)
def test_provider_settings_are_absent(name: str) -> None:
    present = name in os.environ
    assert not present, name
