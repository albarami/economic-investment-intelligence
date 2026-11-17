"""Scheme and host allow-list checked on every request and redirect."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

# Hosts named by PUB-03. Hosts still to be fixed by a later fetcher are absent.
ALLOWED_HOSTS = frozenset(
    {
        "www.data.gov.qa",
        "www.data.qa",
        "services7.arcgis.com",
        "data.humdata.org",
        "s3.us-east-1.amazonaws.com",
        "www.geoboundaries.org",
        "github.com",
        "raw.githubusercontent.com",
        "stac.overturemaps.org",
        "overturemaps-us-west-2.s3.us-west-2.amazonaws.com",
        "download.openstreetmap.fr",
        "unstats.un.org",
        "data.worldpop.org",
        "web.archive.org",
        "fdiprojects.invest.qa",
        "www.invest.qa",
        "data.source.coop",
        "ladsweb.modaps.eosdis.nasa.gov",
        "archive-api.open-meteo.com",
        "services.gisqatar.org.qa",
        "monaqasat.mof.gov.qa",
        "ndownloader.figshare.com",
        "44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com",
        "download.geoservice.dlr.de",
    }
)

NAMED_PORTAL_HOSTS = frozenset({"www.data.gov.qa", "www.data.qa"})
NAMED_INVESTMENT_HOSTS = frozenset({"fdiprojects.invest.qa", "www.invest.qa"})
NAMED_PLACES_HOST = "data.source.coop"
NAMED_RADIANCE_HOST = "ladsweb.modaps.eosdis.nasa.gov"
NAMED_POPULATION_HOST = "data.worldpop.org"
NAMED_WEATHER_HOST = "archive-api.open-meteo.com"


@dataclass(frozen=True)
class HostDecision:
    """Whether one URL may be requested."""

    ok: bool
    host: str
    scheme: str
    reason: str


def approve(url: str) -> HostDecision:
    """Approve HTTPS to an allow-listed host. Any other scheme or host is refused."""
    parts = urlsplit(url)
    scheme = parts.scheme.casefold()
    host = (parts.hostname or "").casefold()
    if scheme == "https" and host in ALLOWED_HOSTS:
        return HostDecision(True, host, scheme, "")
    if scheme != "https":
        return HostDecision(False, host, scheme, "scheme_refused")
    return HostDecision(False, host, scheme, "host_refused")


def host_of(url: str) -> str:
    """Return the lowercase host of a URL, or an empty string."""
    return (urlsplit(url).hostname or "").casefold()
