"""Pin-record grammar, loading and series matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pack_anchors
import versions_inputs

EXACT_RE = re.compile(r"\d+(\.\d+){1,3}", re.ASCII)
SERIES_RE = re.compile(r"\d+(\.\d+)?\.x", re.ASCII)
FLOOR_RE = re.compile(r"\d+\.\d+\.\d+", re.ASCII)
LABEL_PACK = "pack, confirm at slice S1"
LABEL_ASSUMPTION = "ASSUMPTION"
NONE_RECORDED = "none recorded"
TOOLCHAINS = ("python", "uv", "node", "npm")
Failure = tuple[str, str, str]

_HEADER = ("schema", "confirm_at", "spike_result", "component")
_REQUIRED = ("name", "kind", "pin", "retreat", "state", "first_use")
_OPTIONAL = ("label", "cite", "floor", "source", "note")
_FIELD_ORDER = _REQUIRED + _OPTIONAL
_KINDS = frozenset({"toolchain", "python", "npm", "external"})
_STATES = frozenset({"installed", "recorded"})
_VERSIONED = frozenset({"toolchain", "python", "npm"})
_FIRST_USE_RE = re.compile(r"S\d{1,2}-T\d{2}|slice S\d{1,2}", re.ASCII)
_UV_PIN_RE = re.compile(r"\d+\.\d+\.\d+", re.ASCII)
_NODE_PIN_RE = re.compile(r"\d+\.x", re.ASCII)
_SEPARATORS = re.compile(r"[-_.]+")


@dataclass(frozen=True)
class Component:
    """One row of the pin record."""

    index: int
    name: str
    kind: str
    pin: str
    retreat: str
    label: str
    cite: str
    state: str
    first_use: str
    floor: str | None
    source: str | None


def normalise_python_name(name: str) -> str:
    """Fold a Python package name onto one spelling.

    Runs of ``-``, ``_`` and ``.`` become one hyphen, and hyphens at either
    end are removed, so a trailing separator still names the same component.
    """
    return _SEPARATORS.sub("-", name.lower()).strip("-")


def version_matches(entry: str, version: str) -> bool:
    """Return whether ``version`` is exactly ``entry`` or inside its series."""
    if EXACT_RE.fullmatch(version) is None:
        return False
    if EXACT_RE.fullmatch(entry) is not None:
        return entry == version
    if SERIES_RE.fullmatch(entry) is None:
        return False
    prefix = entry[: -len(".x")].split(".")
    parts = version.split(".")
    return len(parts) >= len(prefix) and parts[: len(prefix)] == prefix


def allowed_by(component: Component, version: str) -> bool:
    """Return whether ``version`` is the pin or the retreat."""
    return version_matches(component.pin, version) or version_matches(
        component.retreat, version
    )


def describe(component: Component) -> str:
    """Return ``component[<index>] <name>`` for a failure line."""
    if component.name:
        return f"component[{component.index}] {component.name}"
    return f"component[{component.index}]"


def load_record(root: Path) -> tuple[list[Component], list[Failure], int]:
    """Load ``pins.toml`` and return rows, record failures and the row count."""
    parsed, detail = versions_inputs.read_input(root, "pins.toml", "toml")
    if detail is not None or not isinstance(parsed, dict):
        reason = detail if detail is not None else "not valid TOML"
        return [], [("input", "pins.toml", reason)], 0
    return _assess(parsed, root)


def _show(text: str) -> str:
    return text.encode("unicode_escape").decode("ascii")


def _single(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and "\n" not in value
        and "\r" not in value
    )


def _assess(
    doc: dict[str, object], root: Path
) -> tuple[list[Component], list[Failure], int]:
    failures: list[Failure] = []
    for key in doc:
        if key not in _HEADER:
            failures.append(("record-row", "pins.toml", f"unknown key {key}"))
    schema = doc.get("schema", None)
    if type(schema) is not int or schema != 1:
        failures.append(("record-row", "pins.toml", "schema is not 1"))
    if doc.get("confirm_at") != "slice S1":
        failures.append(("record-row", "pins.toml", 'confirm_at is not "slice S1"'))
    spike = doc.get("spike_result", None)
    if not isinstance(spike, str) or spike.strip() == "":
        failures.append(("record-row", "pins.toml", "spike_result is missing or empty"))
    raw = doc.get("component", None)
    tables = raw if isinstance(raw, list) else []
    if (
        not isinstance(raw, list)
        or not raw
        or any(not isinstance(item, dict) for item in raw)
    ):
        failures.append(
            ("record-row", "pins.toml", "component is not a non-empty array of tables")
        )
        return [], failures, 0
    count = sum(1 for item in tables if isinstance(item, dict))
    components: list[Component] = []
    for index, item in enumerate(tables):
        if not isinstance(item, dict):
            continue
        component, row_failures = _row(index, item)
        components.append(component)
        for detail in row_failures:
            failures.append(("record-row", "pins.toml", detail))
    _retreats(components, failures)
    _toolchains(components, failures)
    _labels(components, doc_rows=tables, failures=failures)
    _cites(components, tables, root, failures)
    _duplicates(components, failures)
    return components, failures, count


def _row(index: int, item: dict[str, object]) -> tuple[Component, list[str]]:
    details: list[str] = []
    for key in item:
        if key not in _FIELD_ORDER:
            details.append(f"unknown field {key}")
    for key in _REQUIRED:
        if key not in item:
            details.append(f"{key} is missing")
    for key in _FIELD_ORDER:
        if key in item and not _single(item[key]):
            details.append(f"{key} is not a single-line non-empty string")
    name = item["name"] if _single(item.get("name")) else ""
    kind = item["kind"] if _single(item.get("kind")) else ""
    pin = item["pin"] if _single(item.get("pin")) else ""
    retreat = item["retreat"] if _single(item.get("retreat")) else ""
    label = item["label"] if isinstance(item.get("label"), str) else ""
    cite = item["cite"] if isinstance(item.get("cite"), str) else ""
    state = item["state"] if _single(item.get("state")) else ""
    first_use = item["first_use"] if _single(item.get("first_use")) else ""
    raw_floor = item.get("floor")
    raw_source = item.get("source")
    floor = raw_floor if isinstance(raw_floor, str) else None
    source = raw_source if isinstance(raw_source, str) else None
    component = Component(
        index,
        str(name),
        str(kind),
        str(pin),
        str(retreat),
        str(label),
        str(cite),
        str(state),
        str(first_use),
        floor if _single(raw_floor) else None,
        source if _single(raw_source) else None,
    )
    if "kind" not in item:
        return component, [_prefixed(component, detail) for detail in details]
    if not _single(item.get("kind")):
        return component, [_prefixed(component, detail) for detail in details]
    if kind not in _KINDS:
        details.append(f"unknown kind {kind}")
        return component, [_prefixed(component, detail) for detail in details]
    if "state" in item and _single(item.get("state")) and state not in _STATES:
        details.append(f"unknown state {state}")
    if (
        "first_use" in item
        and _single(item.get("first_use"))
        and _FIRST_USE_RE.fullmatch(str(first_use)) is None
    ):
        details.append(f"first_use {first_use} is not a task id or a slice")
    unknown_toolchain = kind == "toolchain" and name not in TOOLCHAINS
    if unknown_toolchain:
        details.append(f"no probe for toolchain {name}")
    elif kind in _VERSIONED and "pin" in item and _single(item.get("pin")):
        details.extend(_pin_details(str(kind), str(name), str(pin)))
    if "floor" in item and name != "node":
        details.append("floor is only for node")
    if name == "node" and (floor is None or FLOOR_RE.fullmatch(str(floor)) is None):
        if not ("floor" in item and not _single(item.get("floor"))):
            details.append("node needs a floor such as 22.12.0")
    if (
        kind == "toolchain"
        and not unknown_toolchain
        and _single(item.get("state"))
        and state != "installed"
    ):
        details.append("a toolchain row must be installed")
    if kind == "external" and _single(item.get("state")) and state != "recorded":
        details.append("an external row must be recorded")
    return component, [_prefixed(component, detail) for detail in details]


def _pin_details(kind: str, name: str, pin: str) -> list[str]:
    if kind == "toolchain" and name == "uv":
        if _UV_PIN_RE.fullmatch(pin) is None:
            return ["uv needs an exact three-part pin"]
        return []
    if kind == "toolchain" and name == "node":
        if _NODE_PIN_RE.fullmatch(pin) is None:
            return ["node needs a pin such as 22.x"]
        return []
    if EXACT_RE.fullmatch(pin) is None and SERIES_RE.fullmatch(pin) is None:
        return [f"pin {_show(pin)} is not an exact version or a series"]
    return []


def _prefixed(component: Component, detail: str) -> str:
    return f"{describe(component)}: {detail}"


def _retreats(components: list[Component], failures: list[Failure]) -> None:
    names: dict[str, set[str]] = {kind: set() for kind in _KINDS}
    for component in components:
        if component.kind in names and component.name:
            names[component.kind].add(component.name)
    for component in components:
        if component.kind not in _VERSIONED or not component.retreat:
            continue
        detail = _retreat_detail(component, names)
        if detail is not None:
            failures.append(("record-row", "pins.toml", _prefixed(component, detail)))


def _retreat_detail(component: Component, names: dict[str, set[str]]) -> str | None:
    retreat = component.retreat
    if (
        retreat == NONE_RECORDED
        or EXACT_RE.fullmatch(retreat)
        or SERIES_RE.fullmatch(retreat)
    ):
        return None
    if retreat.startswith("replace:") and retreat != "replace:":
        target = retreat[len("replace:") :]
        pool = names.get(component.kind, set())
        if component.kind == "python":
            found = normalise_python_name(target) in {
                normalise_python_name(item) for item in pool
            }
        else:
            found = target in pool
        if not found:
            return f"replace target {_show(target)} is not a component of the same kind"
        return None
    return f"retreat {_show(retreat)} is not none recorded, a version, a series or replace:<name>"


def _toolchains(components: list[Component], failures: list[Failure]) -> None:
    present = {
        component.name for component in components if component.kind == "toolchain"
    }
    for name in TOOLCHAINS:
        if name not in present:
            failures.append(("record-row", "pins.toml", f"toolchain {name} is missing"))


def _labels(
    components: list[Component],
    doc_rows: list[object],
    failures: list[Failure],
) -> None:
    for component, item in zip(components, doc_rows, strict=False):
        if not isinstance(item, dict):
            continue
        if "label" not in item:
            failures.append(
                ("record-label", "pins.toml", _prefixed(component, "label is missing"))
            )
        elif item.get("label") not in (LABEL_PACK, LABEL_ASSUMPTION):
            failures.append(
                (
                    "record-label",
                    "pins.toml",
                    _prefixed(
                        component,
                        f'label {item.get("label")!r} is not "{LABEL_PACK}" or "{LABEL_ASSUMPTION}"',
                    ),
                )
            )
        if item.get("label") == LABEL_ASSUMPTION and not _single(item.get("source")):
            failures.append(
                (
                    "record-label",
                    "pins.toml",
                    _prefixed(component, "ASSUMPTION needs a source"),
                )
            )


def _cites(
    components: list[Component],
    doc_rows: list[object],
    root: Path,
    failures: list[Failure],
) -> None:
    for component, item in zip(components, doc_rows, strict=False):
        if not isinstance(item, dict):
            continue
        if "cite" not in item:
            failures.append(
                ("record-cite", "pins.toml", _prefixed(component, "cite is missing"))
            )
            continue
        cite = item.get("cite")
        if not isinstance(cite, str):
            continue
        for problem in pack_anchors.check_cite(root, cite):
            failures.append(("record-cite", "pins.toml", _prefixed(component, problem)))


def _duplicates(components: list[Component], failures: list[Failure]) -> None:
    seen: dict[tuple[str, str], Component] = {}
    for component in components:
        if component.kind not in _KINDS or not component.name:
            continue
        if component.kind == "python":
            group, key = "python", normalise_python_name(component.name)
        elif component.kind == "npm":
            group, key = "npm", component.name
        else:
            group, key = "other", component.name
        previous = seen.get((group, key))
        if previous is None:
            seen[(group, key)] = component
            continue
        failures.append(
            (
                "record-duplicate",
                "pins.toml",
                _prefixed(component, f"same component as {describe(previous)}"),
            )
        )
