"""Load the four catalogue files and refuse a key the schema does not hold."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from importlib.resources import files
from importlib.resources.abc import Traversable

import yaml

from eii_product.assistant.catalogue.directives import _directives
from eii_product.assistant.catalogue.entries import (
    _claims,
    _components,
    _fragments,
    _questions,
    _string_key_mapping,
)
from eii_product.assistant.catalogue.schema import (
    FILE_NAMES,
    FILE_VERSION,
    Catalogue,
    Component,
    Directive,
    Refusal,
)

_CORE_TAGS = frozenset(
    {
        "tag:yaml.org,2002:str",
        "tag:yaml.org,2002:int",
        "tag:yaml.org,2002:bool",
        "tag:yaml.org,2002:null",
        "tag:yaml.org,2002:seq",
        "tag:yaml.org,2002:map",
    }
)
_TOP = {
    "claims.yaml": frozenset({"version", "claims"}),
    "components.yaml": frozenset({"version", "components", "stage_directives"}),
    "fragments.yaml": frozenset({"version", "fragments"}),
    "questions.yaml": frozenset({"version", "questions"}),
}


def catalogue_directory() -> Traversable:
    """Resolve package data in both a source checkout and an installed wheel."""
    return files("eii_product.assistant.catalogue") / "assets"


def catalogue_version(folder: Traversable) -> str:
    """SHA-256 of the name-ordered file hashes, as canonical JSON."""
    pairs: list[dict[str, str]] = []
    for name in FILE_NAMES:
        digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        pairs.append({"name": name, "sha256": digest})
    payload = json.dumps(
        pairs, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_catalogue(folder: Traversable) -> Catalogue | Refusal:
    """Load one catalogue folder, or the first refusal."""
    documents: dict[str, dict[str, object]] = {}
    for name in FILE_NAMES:
        document = _read(folder / name, name)
        if isinstance(document, Refusal):
            return document
        documents[name] = document
    claims = _list(documents["claims.yaml"], "claims.yaml", "claims", _claims)
    if isinstance(claims, Refusal):
        return claims
    components = _component_file(documents["components.yaml"])
    if isinstance(components, Refusal):
        return components
    fragments = _list(
        documents["fragments.yaml"], "fragments.yaml", "fragments", _fragments
    )
    if isinstance(fragments, Refusal):
        return fragments
    questions = _list(
        documents["questions.yaml"], "questions.yaml", "questions", _questions
    )
    if isinstance(questions, Refusal):
        return questions
    return Catalogue(
        version=catalogue_version(folder),
        claims=claims,
        components=components[0],
        fragments=fragments,
        questions=questions,
        directives=components[1],
    )


def _read(path: Traversable, file_name: str) -> dict[str, object] | Refusal:
    text = path.read_text(encoding="utf-8")
    duplicate = _duplicate_key(text, file_name)
    if duplicate is not None:
        return duplicate
    try:
        loaded: object = yaml.safe_load(text)
    except yaml.YAMLError:
        return Refusal("NOT_MAPPING", file_name)
    return _string_key_mapping(loaded, file_name)


def _duplicate_key(text: str, file_name: str) -> Refusal | None:
    try:
        node: object = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return Refusal("NOT_MAPPING", file_name)
    if node is None:
        return None
    return _walk(node, file_name, set())


def _tag(node: object) -> str | None:
    tag = getattr(node, "tag", None)
    if isinstance(tag, str):
        return tag
    return None


def _walk(node: object, path: str, seen: set[int]) -> Refusal | None:
    if id(node) in seen:
        return Refusal("YAML_ALIAS", path)
    seen.add(id(node))
    if _tag(node) not in _CORE_TAGS:
        return Refusal("YAML_TAG", path)
    pairs = _mapping_pairs(node)
    if pairs is not None:
        seen_keys: set[str] = set()
        for key_node, value_node in pairs:
            if id(key_node) in seen:
                return Refusal("YAML_ALIAS", path)
            seen.add(id(key_node))
            key = _scalar(key_node)
            if key == "<<":
                return Refusal("YAML_MERGE", f"{path}.<<")
            if key is None:
                return Refusal("NOT_MAPPING", path)
            if _tag(key_node) not in _CORE_TAGS:
                return Refusal("YAML_TAG", f"{path}.{key}")
            if key in seen_keys:
                return Refusal("DUPLICATE_KEY", f"{path}.{key}")
            seen_keys.add(key)
            found = _walk(value_node, f"{path}.{key}", seen)
            if found is not None:
                return found
        return None
    items = _sequence_items(node)
    if items is None:
        return None
    for index, item in enumerate(items):
        found = _walk(item, f"{path}[{index}]", seen)
        if found is not None:
            return found
    return None


def _mapping_pairs(node: object) -> list[tuple[object, object]] | None:
    if type(node).__name__ != "MappingNode":
        return None
    raw = getattr(node, "value", None)
    if not isinstance(raw, list):
        return None
    pairs: list[tuple[object, object]] = []
    for item in raw:
        if not isinstance(item, tuple) or len(item) != 2:
            return None
        pairs.append((item[0], item[1]))
    return pairs


def _sequence_items(node: object) -> list[object] | None:
    if type(node).__name__ != "SequenceNode":
        return None
    raw = getattr(node, "value", None)
    if not isinstance(raw, list):
        return None
    return list(raw)


def _scalar(node: object) -> str | None:
    if type(node).__name__ != "ScalarNode":
        return None
    value = getattr(node, "value", None)
    if not isinstance(value, str):
        return None
    return value


def _list[Item](
    document: dict[str, object],
    file_name: str,
    list_name: str,
    builder: Callable[[object], tuple[Item, ...] | Refusal],
) -> tuple[Item, ...] | Refusal:
    refusal = _top(document, file_name)
    if refusal is not None:
        return refusal
    return builder(document[list_name])


def _component_file(
    document: dict[str, object],
) -> tuple[tuple[Component, ...], tuple[Directive, ...]] | Refusal:
    refusal = _top(document, "components.yaml")
    if refusal is not None:
        return refusal
    components = _components(document["components"])
    if isinstance(components, Refusal):
        return components
    directives = _directives(document["stage_directives"])
    if isinstance(directives, Refusal):
        return directives
    return components, directives


def _top(document: dict[str, object], file_name: str) -> Refusal | None:
    required = _TOP[file_name]
    unknown = [key for key in document if key not in required]
    if unknown:
        return Refusal("UNKNOWN_KEY", f"{file_name}.{unknown[0]}")
    missing = [key for key in sorted(required) if key not in document]
    if missing:
        return Refusal("MISSING_PROPERTY", f"{file_name}.{missing[0]}")
    version = document["version"]
    if type(version) is not int or version != FILE_VERSION:
        return Refusal("FILE_VERSION", f"{file_name}.version")
    return None
