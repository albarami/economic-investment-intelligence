"""Parsers for bank credit, public tenders and district-cooling capacity."""

from eii_custodian.publicdata.singles.bank_credit import parse_bank_credit
from eii_custodian.publicdata.singles.dcool import parse_dcool
from eii_custodian.publicdata.singles.tenders import rows_from_pages

__all__ = ["parse_bank_credit", "parse_dcool", "rows_from_pages"]
