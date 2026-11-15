"""Closed catalogues and the checks that refuse anything they do not hold."""

from eii_product.assistant.catalogue.brief import check_brief
from eii_product.assistant.catalogue.load import (
    catalogue_directory,
    catalogue_version,
    load_catalogue,
)
from eii_product.assistant.catalogue.schema import Catalogue, Refusal, ReturnedFact
from eii_product.assistant.catalogue.slots import match_slots

__all__ = [
    "Catalogue",
    "Refusal",
    "ReturnedFact",
    "catalogue_directory",
    "catalogue_version",
    "check_brief",
    "load_catalogue",
    "match_slots",
]
