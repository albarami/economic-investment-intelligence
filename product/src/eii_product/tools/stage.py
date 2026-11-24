"""BE-6.2 stage: validate with the existing catalogue, without a store read."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from eii_product.assistant.catalogue.brief import _stage
from eii_product.assistant.catalogue.schema import Catalogue, ReturnedFact


def stage(
    raw: Mapping[str, object],
    catalogue: Catalogue,
    facts: Mapping[str, ReturnedFact] | None = None,
) -> dict[str, Any]:
    """Return a checked wire directive unchanged; no fact is created."""
    directive = dict(raw)
    item = {
        "component": directive.get("directive"),
        "props": {key: value for key, value in directive.items() if key != "directive"},
    }
    if _stage(catalogue, [item], {} if facts is None else facts) is not None:
        raise ValueError("INVALID_ARGUMENT")
    return {
        "tool": "stage",
        "status": "OK",
        "facts": [],
        "payload": {"directive": deepcopy(directive)},
    }
