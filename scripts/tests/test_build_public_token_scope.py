"""The production command keeps archive credentials out of page requests."""

from contextlib import nullcontext
from pathlib import Path
from string import ascii_letters, digits
from typing import Any
from unittest.mock import Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from commands import build_public
from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.build import BuildOutcome
from eii_custodian.publicdata.fetch.page_requests import active, page_requests
from eii_custodian.publicdata.fetch.transport import Response, TransportFault


@pytest.mark.parametrize(
    "url,archive,page_scoped",
    [
        ("https://monaqasat.mof.gov.qa/SYN-proof", False, True),
        ("https://ladsweb.modaps.eosdis.nasa.gov/SYN.h5", True, False),
        ("https://LADSWEB.MODAPS.EOSDIS.NASA.GOV/SYN.h5", True, False),
        ("https://urs.earthdata.nasa.gov/SYN", False, False),
        ("https://www.data.gov.qa/SYN", False, False),
    ],
)
@pytest.mark.parametrize("keyed", [False, True])
@pytest.mark.parametrize("reviewed", [False, True])
def test_command_routes_archive_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    keyed: bool,
    reviewed: bool,
    url: str,
    archive: bool,
    page_scoped: bool,
) -> None:
    calls = []

    def open_stub(address: str, token: str = "", **kwargs: Any) -> Response:
        calls.append((address, token, kwargs))
        if active() and token:
            raise TransportFault("blocked_host", "")
        return Response(address, b"SYN proof", ())

    def build_stub(
        entries: Any, transport: Any, *args: Any, **kwargs: Any
    ) -> BuildOutcome:
        with page_requests((url,), {}) if page_scoped else nullcontext():
            assert transport(url).body == b"SYN proof"
        return BuildOutcome((), None)

    monkeypatch.setattr(build_public, "load_registry", lambda: ())
    policy = Mock(reviewed_urls=(url,))
    monkeypatch.setattr(
        build_public, "load_policies", lambda: {"SYN": policy} if reviewed else {}
    )
    monkeypatch.setattr(build_public, "open_https", open_stub)
    monkeypatch.setattr(build_public, "run_build", build_stub)
    environ = {"EARTHDATA_API_KEY": "SYN-invented-archive-token"} if keyed else {}
    assert build_public.run(tmp_path, environ, []) == 0
    expected = {"reviewed_urls": (url,)} if reviewed else {}
    token = environ.get("EARTHDATA_API_KEY", "") if archive else ""
    assert calls == [(url, token, expected)]


@pytest.mark.parametrize(
    "url",
    [
        "",
        "SYN-relative/path",
        "https://ladsweb.modaps.eosdis.nasa.gov.example.test/SYN",
        "https://syn-ladsweb.modaps.eosdis.nasa.gov/SYN",
        "https://ladsweb.modaps.eosdis.nasa.gov" + "@" + "other.example.test/SYN",
        "https://other.example.test/ladsweb.modaps.eosdis.nasa.gov",
        "https://other.example.test/?host=ladsweb.modaps.eosdis.nasa.gov",
        "https://other.example.test/#ladsweb.modaps.eosdis.nasa.gov",
        "https://other.example.test/?host=other&host=ladsweb.modaps.eosdis.nasa.gov",
        "https://ladsweb.modaps.eosdis.nasa.g\u03bfv/SYN",
        "https://[::1]/SYN",
    ],
)
def test_other_authorities_withhold_archive_token(url: str) -> None:
    assert build_public._archive_token(url, "SYN-archive-token") == ""


def test_trailing_dot_archive_host_follows_the_allow_list_normalisation() -> None:
    """Join of S2-P43 with decision 0083: host_of drops one trailing dot, so the
    fully qualified archive host is the same authority for the allow-list, the
    transport's header rule and this token scope; one rule, not two."""
    url = "https://ladsweb.modaps.eosdis.nasa.gov./SYN"
    assert host_of(url) == "ladsweb.modaps.eosdis.nasa.gov"
    assert build_public._archive_token(url, "SYN-archive-token") == "SYN-archive-token"
    double = "https://ladsweb.modaps.eosdis.nasa.gov../SYN"
    assert build_public._archive_token(double, "SYN-archive-token") == ""


@given(
    target=st.one_of(
        st.tuples(
            st.sampled_from(
                ["ladsweb.modaps.eosdis.nasa.gov", "LADSWEB.MODAPS.EOSDIS.NASA.GOV"]
            ),
            st.just(True),
        ),
        st.tuples(
            st.text(ascii_letters + digits + "-", min_size=1, max_size=40).map(
                lambda label: label + ".example.test"
            ),
            st.just(False),
        ),
    ),
    tail=st.text(ascii_letters + digits + "/?=&@#.-_", max_size=80),
    token=st.one_of(st.just(""), st.text(ascii_letters).map(lambda s: "SYN-" + s)),
)
def test_archive_token_boundary_property(
    target: tuple[str, bool], tail: str, token: str
) -> None:
    host, authorized = target
    assert build_public._archive_token(f"https://{host}/{tail}", token) == (
        token if authorized else ""
    )


def test_real_page_transport_still_refuses_archive_token() -> None:
    from unittest.mock import patch

    from eii_custodian.publicdata.fetch.transport import open_https

    url = "https://www.data.gov.qa/SYN-page"
    with page_requests((url,), {}), patch("urllib.request.build_opener") as opened:
        with pytest.raises(TransportFault, match=r"^blocked_host") as refused:
            open_https(url, token="SYN-archive-token")
        assert refused.value.kind == "blocked_host"
        opened.assert_not_called()


def test_company_web_dispatch_has_no_archive_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = Mock()
    company = Mock(return_value=0)
    token_reader = Mock(side_effect=AssertionError("archive credential read"))
    monkeypatch.setattr(build_public, "open_https", opened)
    monkeypatch.setattr(build_public, "run_company_web", company)
    monkeypatch.setattr(build_public, "earthdata_token", token_reader)
    environ = {"EARTHDATA_API_KEY": "SYN-archive-token"}
    assert build_public.run(tmp_path, environ, ["--company-web"]) == 0
    assert company.call_args.args[2] is opened
    token_reader.assert_not_called()
