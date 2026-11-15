"""Mutation pass for the surviving mutants of the catalogue entry readers.

Every test here kills a group of survived mutants of
``product/src/eii_product/assistant/catalogue/entries.py`` from the lead's
campaign. Each expected refusal and value is a hand-written literal, reached
through the public ``load_catalogue`` reader of a copied catalogue folder.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from eii_product.assistant.catalogue.schema import FieldSpec

_SPEC = importlib.util.spec_from_file_location(
    "catalogue_entries_survivors_helpers",
    Path(__file__).with_name("test_catalogue_foundations.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FOUNDATIONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FOUNDATIONS)

_api = _FOUNDATIONS._api
_claim = _FOUNDATIONS._claim
_claims = _FOUNDATIONS._claims
_load = _FOUNDATIONS._load
_slot = _FOUNDATIONS._slot
SHIPPED = _FOUNDATIONS.SHIPPED


def _components() -> str:
    return (SHIPPED / "components.yaml").read_text(encoding="utf-8")


def _questions() -> str:
    return (SHIPPED / "questions.yaml").read_text(encoding="utf-8")


def _copy(tmp: Path, name: str, **files: str) -> tuple[Any, Any]:
    module = _api()
    folder = _FOUNDATIONS._copy(tmp, name, **files)
    return module, module.load_catalogue(folder)


def _props(body: str) -> str:
    """Put a planted props block in place of the shipped empty props list."""
    return _components().replace("    props: []\n", "    props:\n" + body, 1)


def test_claim_keeps_caveats_companions_and_fields(tmp_path: Path) -> None:
    """A loaded claim keeps its caveat keys, companions and rendered fields."""
    claim = _claim(slots=_slot(), caveats="[note_source]")
    claim = claim.replace("required_companions: []", "required_companions: [area_note]")
    module, loaded = _load(tmp_path, _claims(claim), name="claim-parts")
    assert not isinstance(loaded, module.Refusal)
    row = loaded.claims[0]
    assert row.required_caveat_keys == ("note_source",)
    assert row.required_companions == ("area_note",)
    assert row.fields == (
        ("template_en", "See {reading}."),
        ("template_ar", "انظر {reading}."),
    )


def test_the_english_template_must_hold_every_slot(tmp_path: Path) -> None:
    """The English template of a claim is refused when it drops its slot."""
    module, result = _load(
        tmp_path,
        _claims(
            _claim(
                slots=_slot(),
                en="The area is shown.",
                ar="انظر {reading}.",
            )
        ),
        name="en-missing-slot",
    )
    assert result == module.Refusal("TEMPLATE_SLOT", "claims[0].template_en")


def test_the_wider_personas_load(tmp_path: Path) -> None:
    """The international and start-up personas are accepted members."""
    wide = _questions().replace(
        "personas: [local]", "personas: [international, start_up]"
    )
    _module, loaded = _copy(tmp_path, "wide-personas", **{"questions.yaml": wide})
    expected = ("international", "start_up")
    assert loaded.questions[0].personas == expected
    assert loaded.questions[1].personas == expected
    assert loaded.questions[2].personas == expected


def test_disjoint_provenance_is_not_an_overlap(tmp_path: Path) -> None:
    """Two slots of one binding and disjoint provenance sit side by side."""
    slots = _slot(name="reading") + _slot(name="counting", provenance="synthetic")
    claim = _claim(
        slots=slots,
        en="See {reading} and {counting}.",
        ar="انظر {reading} و {counting}.",
    )
    module, loaded = _load(tmp_path, _claims(claim), name="disjoint-provenance")
    assert not isinstance(loaded, module.Refusal)
    row = loaded.claims[0]
    assert tuple(item.name for item in row.slots) == ("reading", "counting")
    assert row.slots[0].allowed_provenance == ("public",)
    assert row.slots[1].allowed_provenance == ("synthetic",)


def test_a_props_item_that_is_not_a_mapping_names_its_path(
    tmp_path: Path,
) -> None:
    """A props item that is a plain string is refused with its full path."""
    broken = _props("      - alpha\n")
    module, result = _copy(tmp_path, "props-not-mapping", **{"components.yaml": broken})
    assert result == module.Refusal("NOT_MAPPING", "components[0].props[0]")


def test_a_prop_name_must_match_the_key_shape(tmp_path: Path) -> None:
    """A prop name that is not a key shape is refused with its full path."""
    named = _props('      - name: "9bad"\n        kind: boolean\n')
    module, result = _copy(tmp_path, "prop-name-shape", **{"components.yaml": named})
    assert result == module.Refusal("CATALOGUE_VALUE", "components[0].props[0].name")


def test_a_prop_unknown_property_is_refused_with_its_path(
    tmp_path: Path,
) -> None:
    """An unknown prop key is refused with the key's own path."""
    extra = _props("      - name: flag\n        kind: boolean\n        extra: no\n")
    module, result = _copy(tmp_path, "prop-extra-key", **{"components.yaml": extra})
    assert result == module.Refusal("UNKNOWN_PROPERTY", "components[0].props[0].extra")


def test_an_enumeration_prop_without_values_is_missing(tmp_path: Path) -> None:
    """An enumeration prop without a values key is refused as missing."""
    bare = _props("      - name: tone\n        kind: enumeration\n")
    module, result = _copy(tmp_path, "prop-no-values", **{"components.yaml": bare})
    assert result == module.Refusal("MISSING_PROPERTY", "components[0].props[0].values")


def test_enumeration_values_that_are_not_a_list_name_the_path(
    tmp_path: Path,
) -> None:
    """Enumeration values that are a plain string are refused by full text."""
    plain = _props(
        "      - name: tone\n        kind: enumeration\n        values: plain\n"
    )
    module, result = _copy(tmp_path, "prop-values-plain", **{"components.yaml": plain})
    assert result == module.Refusal("CATALOGUE_VALUE", "components[0].props[0].values")


def test_enumeration_values_must_not_be_empty(tmp_path: Path) -> None:
    """An empty values list of an enumeration prop is refused by full text."""
    empty = _props(
        "      - name: tone\n        kind: enumeration\n        values: []\n"
    )
    module, result = _copy(tmp_path, "prop-values-empty", **{"components.yaml": empty})
    assert result == module.Refusal("CATALOGUE_VALUE", "components[0].props[0].values")


def test_an_enumeration_prop_holds_its_shaped_values(tmp_path: Path) -> None:
    """A valid enumeration prop keeps its name, kind and shaped values."""
    shaped = _props(
        "      - name: tone\n        kind: enumeration\n        values: [alpha, beta]\n"
    )
    _module, loaded = _copy(tmp_path, "prop-values", **{"components.yaml": shaped})
    assert loaded.components[0].props == (
        FieldSpec("tone", "enumeration", ("alpha", "beta")),
    )


def test_caveat_keys_must_be_a_list(tmp_path: Path) -> None:
    """Caveat keys handed as a plain string are refused with their path."""
    module, result = _load(
        tmp_path, _claims(_claim(caveats="note_source")), name="caveats-plain"
    )
    assert result == module.Refusal("CATALOGUE_VALUE", "claims[0].required_caveat_keys")
