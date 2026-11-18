"""Invented certificate files for the tender chain tests; never a host certificate.

One disposable root, an intermediate it signs and a leaf the intermediate signs
are generated once per test process with the local ``openssl`` tool in a
temporary folder that is removed at once. Only their PEM text is kept.
"""

from __future__ import annotations

import subprocess
import tempfile
from functools import cache
from pathlib import Path


def _run(folder: Path, *args: str) -> None:
    subprocess.run(["openssl", *args], cwd=folder, check=True, capture_output=True)


def _key(folder: Path, name: str) -> None:
    _run(
        folder,
        "genpkey",
        "-algorithm",
        "EC",
        "-pkeyopt",
        "ec_paramgen_curve:prime256v1",
        "-out",
        name + ".key",
    )


def _signed(folder: Path, name: str, issuer: str, ca: bool, serial: str) -> None:
    _key(folder, name)
    _run(
        folder,
        "req",
        "-new",
        "-key",
        name + ".key",
        "-out",
        name + ".csr",
        "-subj",
        "/CN=SYN " + name,
    )
    (folder / (name + ".cnf")).write_text(
        "basicConstraints=critical,CA:"
        + ("TRUE" if ca else "FALSE")
        + "\nkeyUsage=critical,"
        + ("keyCertSign,cRLSign" if ca else "digitalSignature")
        + "\n",
        encoding="utf-8",
    )
    _run(
        folder,
        "x509",
        "-req",
        "-in",
        name + ".csr",
        "-CA",
        issuer + ".pem",
        "-CAkey",
        issuer + ".key",
        "-set_serial",
        serial,
        "-days",
        "2",
        "-extfile",
        name + ".cnf",
        "-out",
        name + ".pem",
    )


@cache
def invented_pems() -> dict[str, bytes]:
    """Return the PEM bytes of an invented root, intermediate and leaf."""
    with tempfile.TemporaryDirectory(prefix="SYN-chain-") as name:
        folder = Path(name)
        _key(folder, "root")
        _run(
            folder,
            "req",
            "-x509",
            "-key",
            "root.key",
            "-out",
            "root.pem",
            "-days",
            "2",
            "-subj",
            "/CN=SYN root",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        )
        _signed(folder, "intermediate", "root", ca=True, serial="2")
        _signed(folder, "leaf", "intermediate", ca=False, serial="3")
        return {
            part: (folder / (part + ".pem")).read_bytes()
            for part in ("root", "intermediate", "leaf")
        }


def intermediate_pem() -> bytes:
    """The invented issuing intermediate, a single PEM certificate."""
    return invented_pems()["intermediate"]
