"""Boundary inputs that distinguish the remaining page-schema mutations."""

import pytest

from eii_custodian.publicdata.fetch.page_schema import period


def test_period_internal_z_separator_is_refused():
    with pytest.raises(ValueError, match=r"^snapshot_date_missing$"):
        period([{"date": "2031-02-03Z04:05:06"}], ["date"])
