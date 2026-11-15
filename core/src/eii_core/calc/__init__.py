"""Deterministic calculations; no import-time I/O (MTH-01)."""

from .facts import compare_public_facts, least_real, order_changes
from .public_methods import (
    coverage_share,
    licence_churn,
    licence_density,
    location_quotient,
    reliability,
    supplier_metrics,
    wilson,
    zone_momentum,
)
from .public_series import decomposition
from .sector_economics import sector_norms

__all__ = [
    "compare_public_facts",
    "coverage_share",
    "decomposition",
    "least_real",
    "licence_churn",
    "licence_density",
    "location_quotient",
    "order_changes",
    "reliability",
    "sector_norms",
    "supplier_metrics",
    "wilson",
    "zone_momentum",
]
