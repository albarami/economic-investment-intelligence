"""Domain-wide refusal and exact-query properties on invented inputs only."""

from urllib.parse import unquote_plus, urlsplit

import pytest
from custodian.tests.company_web_fixture import (
    manifest,
    offline_network,  # noqa: F401
)
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.company_web.contracts import Company, WebError, safe_text
from eii_custodian.publicdata.company_web.scope import Manifest
from eii_custodian.publicdata.company_web.search import request_url


@given(
    size=st.sampled_from((8, 11)),
    digit=st.sampled_from(("4", "٤", "۴", "\uff14", "⁴")),
    levels=st.integers(min_value=0, max_value=5),
    prefix=st.text(alphabet="abcdef _-", min_size=0, max_size=20),
)
@example(size=8, digit="⁴", levels=1, prefix="")
def test_identifier_refusal_survives_unicode_and_nested_encoding(
    size, digit, levels, prefix
):
    value = digit * size
    for _ in range(levels):
        value = "".join("%" + format(byte, "02X") for byte in value.encode())
    with pytest.raises(WebError):
        safe_text("address", "SYN " + prefix + "/" + value)


@given(st.text(alphabet="abcde فزورا", min_size=1, max_size=40))
def test_request_roundtrip_keeps_exact_typed_name_and_country(syllables):
    name = "SYN Zorvella " + syllables
    company = Company("syn-a", name, "register", {})
    plan = Manifest.from_data(manifest())
    url = request_url(company, plan)
    assert urlsplit(url).hostname == plan.data["provider"]["host"]
    query = urlsplit(url).query
    assert query.startswith("q=") and "&" not in query
    assert unquote_plus(query[2:]) == name + " Qatar"
    assert not plan.search_allowed(url, name + " Other")
