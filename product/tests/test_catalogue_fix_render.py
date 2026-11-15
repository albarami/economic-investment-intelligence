"""Fix-pass plants for catalogue foundations. Each expected refusal is written here."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_SPEC = importlib.util.spec_from_file_location(
    "catalogue_foundations_helpers",
    Path(__file__).with_name("test_catalogue_foundations.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FOUNDATIONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FOUNDATIONS)

_api = _FOUNDATIONS._api
_brief = _FOUNDATIONS._brief
_claim = _FOUNDATIONS._claim
_claims = _FOUNDATIONS._claims
_fact = _FOUNDATIONS._fact
_load = _FOUNDATIONS._load
_slot = _FOUNDATIONS._slot
FACT_A = _FOUNDATIONS.FACT_A
FACT_B = _FOUNDATIONS.FACT_B
SHIPPED = _FOUNDATIONS.SHIPPED

_PROSE = "Open here now, revenue seven million"
_KEYCAP = "#\ufe0f\u20e3"


def _components() -> str:
    return (SHIPPED / "components.yaml").read_text(encoding="utf-8")


def _questions() -> str:
    return (SHIPPED / "questions.yaml").read_text(encoding="utf-8")


def _copy(tmp: Path, name: str, **files: str) -> Any:
    module = _api()
    folder = _FOUNDATIONS._copy(tmp, name, **files)
    return module, module.load_catalogue(folder)


def _words(en: str, ar: str | None = None) -> dict[str, str]:
    return {"en": en, "ar": ar if ar is not None else "المنطقة ظاهرة."}


def test_fix_n_numeral_symbols_and_character_references(tmp_path: Path) -> None:
    plants = (
        ("keycap", _KEYCAP, "claims[0].template_en"),
        ("enclosing", "\u20e3", "claims[0].template_en"),
        ("ten", "\U0001f51f", "claims[0].template_en"),
        ("input", "\U0001f522", "claims[0].template_en"),
        ("hundred", "\U0001f4af", "claims[0].template_ar"),
        ("eighteen", "\U0001f51e", "claims[0].template_en"),
    )
    for name, symbol, path in plants:
        if path.endswith("template_ar"):
            claim = _claim(**_words("The area is shown.", f"المنطقة {symbol}"))
        else:
            claim = _claim(**_words(f"The area is shown {symbol}."))
        module, result = _load(tmp_path, _claims(claim), name=name)
        assert result == module.Refusal("TEMPLATE_NUMERAL_SYMBOL", path)
    for name, text in (
        ("named", "See &half; there."),
        ("numeric", "See &#xBD; there."),
        ("no-semicolon", "See &frac12 there."),
    ):
        module, result = _load(tmp_path, _claims(_claim(**_words(text))), name=name)
        assert result == module.Refusal("TEMPLATE_CHARREF", "claims[0].template_en")
    module = _api()
    assert module.load_catalogue(SHIPPED).components[0].key == "foundation_note"
    from eii_product.assistant.catalogue.scan import NUMERAL_SYMBOLS

    assert NUMERAL_SYMBOLS == (
        "\u20e3",
        "\U0001f51f",
        "\U0001f522",
        "\U0001f4af",
        "\U0001f51e",
    )


def test_fix_o_highlight_fact_id() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    missing = _brief(loaded.version)
    missing["stage"] = [{"component": "highlight", "props": {"fact_id": FACT_A}}]
    assert module.check_brief(loaded, missing, {}) == module.Refusal(
        "UNKNOWN_FACT", "stage[0].props.fact_id"
    )
    fact = _fact(module)
    present = _brief(loaded.version)
    present["stage"] = [{"component": "highlight", "props": {"fact_id": fact.fact_id}}]
    assert module.check_brief(loaded, present, {fact.fact_id: fact}) is None


def test_fix_p_duplicate_question() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["next_questions"][1] = {
        "question_key": "foundation_ask_shape",
        "slots": {},
    }
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "QUESTION_DUPLICATE", "next_questions[1].question_key"
    )


def test_fix_q_yaml_tag_does_not_construct(tmp_path: Path) -> None:
    marker = tmp_path / "marker-open"
    quoted = str(marker)
    body = (
        "version: 1\n"
        'claims: !!python/object/apply:builtins.open ["' + quoted + '", w]\n'
    )
    module, result = _copy(tmp_path, "python-tag", **{"claims.yaml": body})
    assert result == module.Refusal("YAML_TAG", "claims.yaml.claims")
    assert not marker.exists()


def test_fix_r_directive_names_are_pinned(tmp_path: Path) -> None:
    extra = _components().replace(
        "  set_scenario_inputs:\n",
        "  zoom_to:\n    fields:\n      - name: target\n        kind: identifier\n"
        "  set_scenario_inputs:\n",
        1,
    )
    module, result = _copy(tmp_path, "extra-directive", **{"components.yaml": extra})
    assert result == module.Refusal(
        "UNKNOWN_DIRECTIVE", "components.yaml.stage_directives.zoom_to"
    )
    month = "  month:\n    fields:\n      - name: month_key\n        kind: identifier\n"
    removed = _components().replace(month, "", 1)
    module, result = _copy(tmp_path, "missing-month", **{"components.yaml": removed})
    assert result == module.Refusal(
        "MISSING_DIRECTIVE", "components.yaml.stage_directives.month"
    )
    from eii_product.assistant.catalogue.schema import STAGE_DIRECTIVES

    assert STAGE_DIRECTIVES == (
        "fly",
        "layer",
        "highlight",
        "rings",
        "dial",
        "hour",
        "day",
        "month",
        "split",
        "set_scenario_inputs",
    )


def test_fix_s_enumeration_values_match_key(tmp_path: Path) -> None:
    zoom = "        values: [country, city, district, street]\n"
    module, ten = _copy(
        tmp_path,
        "enum-ten",
        **{
            "components.yaml": _components().replace(
                zoom, '        values: ["10"]\n', 1
            )
        },
    )
    assert ten == module.Refusal(
        "KEY_SHAPE", "stage_directives.fly.fields[1].values[0]"
    )
    digit = _components().replace(
        "    props: []\n",
        "    props:\n      - name: title\n        kind: enumeration\n"
        '        values: ["\u0663"]\n',
        1,
    )
    module, arabic = _copy(tmp_path, "enum-digit", **{"components.yaml": digit})
    assert arabic == module.Refusal("KEY_SHAPE", "components[0].props[0].values[0]")


def test_fix_t_yaml_merge_and_alias(tmp_path: Path) -> None:
    merge = (
        "version: 1\n"
        "base: &base\n"
        '  template_en: "What the area shows"\n'
        "fragments:\n"
        "  - <<: *base\n"
        "    fragment_key: foundation_headline\n"
        "    kind: headline\n"
        '    template_ar: "ما تظهره المنطقة"\n'
    )
    module, merged = _copy(tmp_path, "merge", **{"fragments.yaml": merge})
    assert merged == module.Refusal("YAML_MERGE", "fragments.yaml.fragments[0].<<")
    alias = "version: &base 1\nclaims: []\nrepeat: *base\n"
    module, aliased = _copy(tmp_path, "alias", **{"claims.yaml": alias})
    assert aliased == module.Refusal("YAML_ALIAS", "claims.yaml.repeat")
    key_alias = "version: 1\nclaims: &name []\n*name: []\n"
    module, keyed = _copy(tmp_path, "key-alias", **{"claims.yaml": key_alias})
    assert keyed == module.Refusal("YAML_ALIAS", "claims.yaml")
    module, null_node = _copy(
        tmp_path, "null-node", **{"claims.yaml": "version: 1\nclaims:\n  - ~\n"}
    )
    assert null_node == module.Refusal("NOT_MAPPING", "claims[0]")


def test_fix_u_brief_key_path_is_a_string() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief[1] = "x"
    refusal = module.check_brief(loaded, brief, {})
    assert refusal == module.Refusal("UNKNOWN_PROPERTY", "1")
    assert isinstance(refusal.item_path, str)


def test_fix_v_coordinate_range() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)

    def fly(lat: object, lon: object) -> Any:
        brief = _brief(loaded.version)
        brief["stage"] = [
            {
                "component": "fly",
                "props": {"target": {"lat": lat, "lon": lon}, "zoom": "city"},
            }
        ]
        return module.check_brief(loaded, brief, {})

    assert fly(90.5, 0) == module.Refusal(
        "COORDINATE_RANGE", "stage[0].props.target.lat"
    )
    assert fly(999, 0) == module.Refusal(
        "COORDINATE_RANGE", "stage[0].props.target.lat"
    )
    assert fly(-90.5, 0) == module.Refusal(
        "COORDINATE_RANGE", "stage[0].props.target.lat"
    )
    assert fly(0, -180.5) == module.Refusal(
        "COORDINATE_RANGE", "stage[0].props.target.lon"
    )
    assert fly(0, 180.5) == module.Refusal(
        "COORDINATE_RANGE", "stage[0].props.target.lon"
    )
    assert fly(90, -180) is None
    assert fly(-90, 180) is None
