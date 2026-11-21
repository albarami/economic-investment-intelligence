"""Scheme and host allow-list checked on every request and redirect."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit

# Hosts named by PUB-03. Hosts still to be fixed by a later fetcher are absent.
ALLOWED_HOSTS = frozenset(
    {
        "eservices.qfc.qa",
        "www.qfc.qa",
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
        "besttime.app",
        # S2-T29, L-892 and EVIDENCE-items-1-2, reviewed page/redirect hosts.
        "www.qcb.gov.qa",
        "visitqatar.com",
        "www.qncc.qa",
        "manateq.qa",
        "www.edu.gov.qa",
        "myschool.edu.gov.qa",
        "myschools.edu.gov.qa",
        # S2-P29: reviewed BACI page and HS17 archive, PUB-03 registry change.
        "www.cepii.fr",
    }
)

NAMED_PORTAL_HOSTS = frozenset({"www.data.gov.qa", "www.data.qa"})
NAMED_INVESTMENT_HOSTS = frozenset({"fdiprojects.invest.qa", "www.invest.qa"})
NAMED_PLACES_HOST = "data.source.coop"
NAMED_RADIANCE_HOST = "ladsweb.modaps.eosdis.nasa.gov"
NAMED_POPULATION_HOST = "data.worldpop.org"
NAMED_WEATHER_HOST = "archive-api.open-meteo.com"
CREDENTIAL_QUERY_NAMES = frozenset(
    {
        "access-token",
        "access_token",
        "api-key",
        "api_key",
        "apikey",
        "key",
        "ocp-apim-subscription-key",
        "subscription-key",
        "subscription_key",
        "token",
    }
)
QUERY_KEY_REFUSED = "query_key_refused"
URL_SECRET_REFUSED = "url_secret_refused"
CLOSED_QUERY_REFUSED = "closed_query_refused"


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
    if scheme != "https":
        return HostDecision(False, host, scheme, "scheme_refused")
    secret = _secret_reason(parts)
    if secret:
        return HostDecision(False, host, scheme, secret)
    if host in ALLOWED_HOSTS:
        return HostDecision(True, host, scheme, "")
    return HostDecision(False, host, scheme, "host_refused")


def canonical_https(
    host: str, path: str, selectors: tuple[tuple[str, str], ...]
) -> str:
    """Build an https URL from a host, a path and closed selectors.

    The host is a bare hostname. The path has no query and no fragment.
    Selector names and values are copied as given, in the given order.
    """
    if host == "" or "/" in host or "@" in host or ":" in host:
        raise ValueError("host")
    if not path.startswith("/") or "?" in path or "#" in path:
        raise ValueError("path")
    base = f"https://{host}{path}"
    if not selectors:
        return base
    return base + "?" + urlencode(selectors)


def approve_closed(
    url: str,
    *,
    hosts: frozenset[str],
    selectors: tuple[tuple[str, str], ...],
) -> HostDecision:
    """Approve a URL whose host is listed and whose query is exactly the selectors."""
    parts = urlsplit(url)
    scheme = parts.scheme.casefold()
    host = (parts.hostname or "").casefold()
    if scheme != "https":
        return HostDecision(False, host, scheme, "scheme_refused")
    secret = _secret_reason(parts)
    if secret:
        return HostDecision(False, host, scheme, secret)
    if host not in hosts:
        return HostDecision(False, host, scheme, "host_refused")
    observed = tuple(parse_qsl(parts.query, keep_blank_values=True))
    if observed != selectors:
        return HostDecision(False, host, scheme, CLOSED_QUERY_REFUSED)
    return HostDecision(True, host, scheme, "")


def _secret_reason(parts: SplitResult) -> str:
    """Return a key-free reason when the URL carries user-info, a fragment or a key."""
    if parts.username or parts.password or parts.fragment:
        return URL_SECRET_REFUSED
    names = {
        name.casefold()
        for name, _value in parse_qsl(parts.query, keep_blank_values=True)
    }
    if names & CREDENTIAL_QUERY_NAMES:
        return QUERY_KEY_REFUSED
    return ""


def secret_in_url(url: str, secret: str) -> bool:
    """Return whether a secret is in the user-info, path, query or fragment."""
    if secret == "":
        return False
    parts = urlsplit(url)
    if secret in (parts.username or "") or secret in (parts.password or ""):
        return True
    if secret in parts.path or secret in parts.fragment:
        return True
    for name, value in parse_qsl(parts.query, keep_blank_values=True):
        if secret in name or secret in value:
            return True
    return False


def host_of(url: str) -> str:
    """Return the lowercase host of a URL, or an empty string."""
    try:
        return (urlsplit(url).hostname or "").removesuffix(".").casefold()
    except ValueError:
        return ""


def reviewed_url(url: str) -> bool:
    """True for an allow-listed HTTPS URL with no query, fragment or credential."""
    try:
        parts = urlsplit(url)
        return (
            not any(ord(char) <= 32 for char in url)
            and parts.username is None
            and parts.password is None
            and not parts.query
            and not parts.fragment
            and parts.port in (None, 443)
            and approve(url).ok
        )
    except ValueError:
        return False
