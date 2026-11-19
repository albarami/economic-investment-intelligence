"""Read only the optional CDSE pair from an injected environment mapping."""

from __future__ import annotations

from collections.abc import Mapping

from eii_custodian.publicdata.cdse.transport import Credentials


def cdse_credentials(environ: Mapping[str, str]) -> Credentials | None:
    """A missing or blank member omits the optional source; no setup file is read."""
    client = environ.get("CDSE_CLIENT_ID", "").strip()
    secret = environ.get("CDSE_CLIENT_SECRET", "").strip()
    return Credentials(client, secret) if client and secret else None
