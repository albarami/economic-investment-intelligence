"""Only the reviewed BACI page selector extends the generic URL policy."""

from dataclasses import replace

import pytest

from eii_custodian.publicdata.baci.config import BaciError, Config, safe_url
from eii_custodian.publicdata.baci.fetch import _entry_check, _metadata
from eii_custodian.publicdata.fetch.allowlist import ALLOWED_HOSTS, reviewed_url
from eii_custodian.publicdata.fetch.transport import Response

from .fixtures.baci.invented import configuration, entry

PAGE = "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37"
ARCHIVE = "https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS17_V202601.zip"


def real_shaped():
    raw = configuration()
    raw.update(page=PAGE, reviewed_urls=[PAGE, ARCHIVE])
    return raw


def test_reviewed_cepii_host_and_exact_page_configuration():
    assert "www.cepii.fr" in ALLOWED_HOSTS
    assert safe_url(PAGE)
    assert not reviewed_url(PAGE)  # Generic query refusal is unchanged.
    config = Config.from_mapping(real_shaped())
    source = replace(
        entry(),
        url=ARCHIVE,
        fetch_host="www.cepii.fr",
        landing_url=PAGE,
        terms_url=PAGE,
    )
    _entry_check(source, config)
    assert (
        _metadata(
            PAGE,
            lambda url: Response(url, b"invented page", ()),
            config,
            lambda _: None,
        )
        == b"invented page"
    )


@pytest.mark.parametrize(
    "url",
    [
        PAGE.replace("id=37", "id=38"),
        PAGE + "&extra=invented",
        PAGE + "&id=37",
        PAGE.replace("id=37", "id=%33%37"),
        PAGE.replace("bdd_modele_item.asp", "other.asp"),
        PAGE.replace("https://", "https://invented:@"),
        PAGE.replace("https:", "http:"),
        PAGE + "#invented",
    ],
)
def test_baci_page_selector_plants(url):
    assert not safe_url(url)
    raw = real_shaped()
    raw.update(page=url, reviewed_urls=[url, ARCHIVE])
    with pytest.raises(BaciError, match=r"^blocked_host$"):
        Config.from_mapping(raw)


def test_exact_page_still_requires_host_admission(monkeypatch):
    from eii_custodian.publicdata.fetch import allowlist

    monkeypatch.setattr(allowlist, "ALLOWED_HOSTS", ALLOWED_HOSTS - {"www.cepii.fr"})
    assert not safe_url(PAGE)


@pytest.mark.parametrize(
    "redirect",
    [
        "https://www.cepii.fr/unreviewed",
        "https://www.data.gov.qa/invented-unreviewed",
        "https://unreviewed.invalid/invented",
        PAGE.replace("id=37", "id=38"),
    ],
)
def test_unreviewed_metadata_redirect_never_passes(redirect):
    config = Config.from_mapping(real_shaped())
    with pytest.raises(BaciError, match=r"^blocked_host$"):
        _metadata(
            PAGE,
            lambda _: Response(redirect, b"invented", (PAGE,)),
            config,
            lambda _: None,
        )


def test_unreviewed_intermediate_redirect_never_passes():
    config = Config.from_mapping(real_shaped())
    with pytest.raises(BaciError, match=r"^blocked_host$"):
        _metadata(
            PAGE,
            lambda _: Response(PAGE, b"invented", ("https://www.cepii.fr/unreviewed",)),
            config,
            lambda _: None,
        )
