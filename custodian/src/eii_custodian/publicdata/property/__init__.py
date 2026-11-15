"""Kept deals and the quarterly aggregates of card C41 (PUB-107).

The package reads the Arabic label and the usage field of the two sales
bulletins through the reviewed ``property_use_map.csv``, keeps deals by the
rule of card C14 and writes only the aggregates of ``pub_property_quarter``:
identifiers stay inside the build as join keys and never reach a release row.
"""

from eii_custodian.publicdata.property.bulletin import (
    BULLETIN_FIELDS,
    SQ_M_PER_SQ_FT,
    BulletinDeals,
    Deal,
    parse_bulletin,
    quarter_of,
    refuse_release_identifiers,
)
from eii_custodian.publicdata.property.quarter import (
    forecast_window,
    quarter_aggregates,
    square_feet,
)
from eii_custodian.publicdata.property.use_map import (
    ANY_USAGE,
    LAND_MARKER,
    UNIT_TYPES,
    USE_MAP_COLUMNS,
    UseMapping,
    load_use_map,
    use_lookup,
)

__all__ = [
    "ANY_USAGE",
    "BULLETIN_FIELDS",
    "LAND_MARKER",
    "SQ_M_PER_SQ_FT",
    "UNIT_TYPES",
    "USE_MAP_COLUMNS",
    "BulletinDeals",
    "Deal",
    "UseMapping",
    "forecast_window",
    "load_use_map",
    "parse_bulletin",
    "quarter_aggregates",
    "quarter_of",
    "refuse_release_identifiers",
    "square_feet",
    "use_lookup",
]
