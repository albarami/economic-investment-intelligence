"""Typed Comtrade fetch and cache assembly."""

from eii_custodian.publicdata.comtrade.assemble import Assembly, assemble
from eii_custodian.publicdata.comtrade.fetch import FetchResult, fetch_source

__all__ = ["Assembly", "FetchResult", "assemble", "fetch_source"]
