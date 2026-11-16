"""Mutation pass for the surviving mutants of the stage-directive readers.

Every test here kills a group of survived mutants of
``product/src/eii_product/assistant/catalogue/directives.py`` from the lead's
campaign. Each expected refusal and value is a hand-written literal, reached
through the public ``load_catalogue`` reader of a copied catalogue folder.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from eii_product.assistant.catalogue.schema import Alternative, FieldSpec

_SPEC = importlib.util.spec_from_file_location(
    "catalogue_directives_survivors_helpers",
    Path(__file__).with_name("test_catalogue_foundations.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FOUNDATIONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FOUNDATIONS)

_api = _FOUNDATIONS._api
SHIPPED = _FOUNDATIONS.SHIPPED

_FLY_BODY = (
    "  fly:\n"
    "    fields:\n"
    "      - name: target\n"
    "        kind: target\n"
    "      - name: zoom\n"
    "        kind: enumeration\n"
    "        values: [country, city, district, street]\n"
)
_FLY_ONE_OF = (
    "  fly:\n"
    "    one_of:\n"
    "      - fields:\n"
    "          - name: target\n"
    "            kind: target\n"
    "          - name: zoom\n"
    "            kind: enumeration\n"
    "            values: [country, city, district, street]\n"
    "      - fields:\n"
    "          - name: zoom\n"
    "            kind: enumeration\n"
    "            values: [country, city]\n"
)
_HOUR_BODY = "  hour:\n    fields:\n      - name: hour_key\n        kind: identifier\n"
_PLACE_KEYS = "            kind: identifier_list\n            minimum: 1\n"


def _components() -> str:
    return (SHIPPED / "components.yaml").read_text(encoding="utf-8")


def _copy(tmp: Path, name: str, **files: str) -> tuple[Any, Any]:
    module = _api()
    folder = _FOUNDATIONS._copy(tmp, name, **files)
    return module, module.load_catalogue(folder)


def test_fly_one_of_holds_a_target_field(tmp_path: Path) -> None:
    """A one-of fly directive keeps a target field and its alternatives."""
    fly = _components().replace(_FLY_BODY, _FLY_ONE_OF, 1)
    _module, loaded = _copy(tmp_path, "fly-one-of", **{"components.yaml": fly})
    directive = loaded.find_directive("fly")
    assert directive.alternatives == (
        Alternative(
            (
                FieldSpec("target", "target"),
                FieldSpec(
                    "zoom", "enumeration", ("country", "city", "district", "street")
                ),
            )
        ),
        Alternative((FieldSpec("zoom", "enumeration", ("country", "city")),)),
    )


def test_a_directive_with_both_fields_and_one_of_is_missing(
    tmp_path: Path,
) -> None:
    """A directive holding both forms at once is refused as missing."""
    both = _HOUR_BODY + (
        "    one_of:\n"
        "      - fields:\n"
        "          - name: hour_key\n"
        "            kind: identifier\n"
    )
    extra = _components().replace(_HOUR_BODY, both, 1)
    module, result = _copy(tmp_path, "hour-both", **{"components.yaml": extra})
    assert result == module.Refusal("MISSING_PROPERTY", "stage_directives.hour.fields")


def test_an_identifier_field_keeps_empty_defaults() -> None:
    """An identifier field holds empty values and no bounds."""
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    directive = loaded.find_directive("hour")
    assert directive.alternatives == (
        Alternative((FieldSpec("hour_key", "identifier"),)),
    )


def test_an_identifier_list_maximum_is_allowed(tmp_path: Path) -> None:
    """An identifier list field keeps an optional maximum beside its minimum."""
    wider = _components().replace(
        _PLACE_KEYS,
        "            kind: identifier_list\n"
        "            minimum: 1\n"
        "            maximum: 3\n",
        1,
    )
    _module, loaded = _copy(
        tmp_path, "identifier-maximum", **{"components.yaml": wider}
    )
    directive = loaded.find_directive("highlight")
    assert directive.alternatives == (
        Alternative((FieldSpec("fact_id", "fact_id"),)),
        Alternative((FieldSpec("place_keys", "identifier_list", (), 1, 3, None),)),
        Alternative((FieldSpec("unit_ids", "identifier_list", (), 1, None, None),)),
    )


def test_an_identifier_list_minimum_is_required(tmp_path: Path) -> None:
    """An identifier list field without a minimum is refused as missing."""
    bare = _components().replace(
        _PLACE_KEYS,
        "            kind: identifier_list\n",
        1,
    )
    module, result = _copy(tmp_path, "identifier-minimum", **{"components.yaml": bare})
    assert result == module.Refusal(
        "MISSING_PROPERTY",
        "stage_directives.highlight.one_of[1].fields[0].minimum",
    )
