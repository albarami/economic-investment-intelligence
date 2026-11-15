"""Read the stage-directive schemas stored with the components."""

from __future__ import annotations

from eii_product.assistant.catalogue.entries import (
    _count,
    _key_values,
    _plain_strings,
    _string_key_mapping,
)
from eii_product.assistant.catalogue.schema import (
    DIRECTIVE_KINDS,
    KEY,
    STAGE_DIRECTIVES,
    Alternative,
    Directive,
    FieldSpec,
    Refusal,
)


def _directives(value: object) -> tuple[Directive, ...] | Refusal:
    table = _string_key_mapping(value, "components.yaml.stage_directives")
    if isinstance(table, Refusal):
        return table
    for name in table:
        if KEY.fullmatch(name) is None:
            return Refusal("UNKNOWN_KEY", f"components.yaml.stage_directives.{name}")
        if name not in STAGE_DIRECTIVES:
            return Refusal(
                "UNKNOWN_DIRECTIVE", f"components.yaml.stage_directives.{name}"
            )
    for name in STAGE_DIRECTIVES:
        if name not in table:
            return Refusal(
                "MISSING_DIRECTIVE", f"components.yaml.stage_directives.{name}"
            )
    directives: list[Directive] = []
    for name, body in table.items():
        directive = _directive(name, body)
        if isinstance(directive, Refusal):
            return directive
        directives.append(directive)
    return tuple(directives)


def _directive(name: str, body: object) -> Directive | Refusal:
    row = _string_key_mapping(body, f"stage_directives.{name}")
    if isinstance(row, Refusal):
        return row
    if set(row) == {"fields"}:
        fields = _field_list(row["fields"], name, f"stage_directives.{name}.fields")
        if isinstance(fields, Refusal):
            return fields
        return Directive(name, (Alternative(fields),))
    if set(row) == {"one_of"}:
        alternatives = _one_of(row["one_of"], name, f"stage_directives.{name}.one_of")
        if isinstance(alternatives, Refusal):
            return alternatives
        return Directive(name, alternatives)
    unknown = [key for key in row if key not in {"fields", "one_of"}]
    if unknown:
        return Refusal("UNKNOWN_PROPERTY", f"stage_directives.{name}.{unknown[0]}")
    return Refusal("MISSING_PROPERTY", f"stage_directives.{name}.fields")


def _one_of(
    value: object, directive: str, path: str
) -> tuple[Alternative, ...] | Refusal:
    if not isinstance(value, list) or not value:
        return Refusal("CATALOGUE_VALUE", path)
    alternatives: list[Alternative] = []
    for index, item in enumerate(value):
        row = _string_key_mapping(item, f"{path}[{index}]")
        if isinstance(row, Refusal):
            return row
        if set(row) != {"fields"}:
            return Refusal("UNKNOWN_PROPERTY", f"{path}[{index}]")
        fields = _field_list(row["fields"], directive, f"{path}[{index}].fields")
        if isinstance(fields, Refusal):
            return fields
        alternatives.append(Alternative(fields))
    return tuple(alternatives)


def _field_list(
    value: object, directive: str, path: str
) -> tuple[FieldSpec, ...] | Refusal:
    if not isinstance(value, list) or not value:
        return Refusal("CATALOGUE_VALUE", path)
    fields: list[FieldSpec] = []
    for index, item in enumerate(value):
        field = _field_spec(item, directive, f"{path}[{index}]")
        if isinstance(field, Refusal):
            return field
        fields.append(field)
    return tuple(fields)


def _field_spec(value: object, directive: str, path: str) -> FieldSpec | Refusal:
    row = _string_key_mapping(value, path)
    if isinstance(row, Refusal):
        return row
    kind = row.get("kind")
    name = row.get("name")
    if not isinstance(kind, str) or kind not in DIRECTIVE_KINDS:
        return Refusal("CATALOGUE_VALUE", f"{path}.kind")
    if kind == "target" and directive != "fly":
        return Refusal("CATALOGUE_VALUE", f"{path}.kind")
    if not isinstance(name, str) or KEY.fullmatch(name) is None:
        return Refusal("CATALOGUE_VALUE", f"{path}.name")
    allowed, required = _field_keys(kind)
    unknown = [key for key in row if key not in allowed]
    if unknown:
        return Refusal("UNKNOWN_PROPERTY", f"{path}.{unknown[0]}")
    missing = [key for key in sorted(required) if key not in row]
    if missing:
        return Refusal("MISSING_PROPERTY", f"{path}.{missing[0]}")
    values: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    const: bool | None = None
    if "values" in row:
        parsed = _plain_strings(row["values"], f"{path}.values")
        if isinstance(parsed, Refusal):
            return parsed
        if not parsed:
            return Refusal("CATALOGUE_VALUE", f"{path}.values")
        shaped = _key_values(parsed, f"{path}.values")
        if isinstance(shaped, Refusal):
            return shaped
        values = shaped
    if "minimum" in row:
        counted = _count(row["minimum"], f"{path}.minimum")
        if isinstance(counted, Refusal):
            return counted
        minimum = counted
    if "maximum" in row:
        counted = _count(row["maximum"], f"{path}.maximum")
        if isinstance(counted, Refusal):
            return counted
        if minimum is not None and counted < minimum:
            return Refusal("CATALOGUE_VALUE", f"{path}.maximum")
        maximum = counted
    if "const" in row:
        if type(row["const"]) is not bool:
            return Refusal("CATALOGUE_VALUE", f"{path}.const")
        const = row["const"]
    return FieldSpec(name, kind, values, minimum, maximum, const)


def _field_keys(kind: str) -> tuple[frozenset[str], frozenset[str]]:
    base = frozenset({"name", "kind"})
    if kind == "enumeration":
        fields = base | frozenset({"values"})
        return fields, fields
    if kind == "boolean":
        return base | frozenset({"const"}), base
    if kind == "area_ids":
        fields = base | frozenset({"minimum", "maximum"})
        return fields, fields
    if kind == "identifier_list":
        return base | frozenset({"minimum", "maximum"}), base | frozenset({"minimum"})
    return base, base
