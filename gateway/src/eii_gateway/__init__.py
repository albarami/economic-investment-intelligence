"""Offline tooling interface. No configured adapter is imported here."""

from .facade import Gateway
from .types import Request

__all__ = ["Gateway", "Request"]
__version__ = "0.0.0"
