"""Plants and case tables for workspace metadata tests."""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import workspace_guard as guard

EXPECTED_PYPROJECT_FIELDS, EXPECTED_PYPROJECT_PLANTS = 34, 44
EXPECTED_PACKAGE_LOCK_PLANTS, EXPECTED_WIDE_LOCK_PLANTS = 8, 14
COUNT_EVERY_PLACE, COUNT_LOCK_EDGES, COUNT_WIDE = 176, 80, 42
COUNT_PATHS, COUNT_SPELLINGS, COUNT_PYPROJECT_CASES = 20, 10, 9
MEMBERS: tuple[str, ...] = ("core", "custodian", "product")
NAMES: tuple[str, ...] = ("eii-core", "eii-custodian", "eii-product")
NOT_VALID = "not = [valid"
FILLER = "filler"
PIP_KEYS = (
    "config-settings-package",
    "dependency-metadata",
    "exclude-newer-package",
    "extra-build-dependencies",
    "extra-build-variables",
    "no-binary",
    "no-build-isolation-package",
    "no-emit-package",
    "no-sources-package",
    "only-binary",
    "reinstall-package",
    "upgrade-package",
)


def _nav(data: dict[str, Any], parts: list[str], make: bool) -> Any:
    cur: Any = data
    for part in parts[:-1]:
        nxt = cur.get(part) if isinstance(cur, dict) else None
        if not isinstance(nxt, dict):
            if not make:
                return None
            nxt = {}
            cur[part] = nxt
        cur = nxt
    return cur


def _put(data: dict[str, Any], dotted: str, value: object) -> None:
    parts = dotted.split(".")
    cur = _nav(data, parts, True)
    cur[parts[-1]] = value


def _pop(data: dict[str, Any], dotted: str) -> None:
    parts = dotted.split(".")
    cur = _nav(data, parts, False)
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _extend(data: dict[str, Any], parts: list[str], item: str) -> None:
    cur = _nav(data, parts, True)
    lst = cur.get(parts[-1])
    if not isinstance(lst, list):
        lst = []
        cur[parts[-1]] = lst
    lst.append(item)


def read_toml(path: Path) -> dict[str, Any]:
    """Parse one TOML file."""
    return tomllib.loads(path.read_text(encoding="utf-8"))


def edit(rel: str, change: Callable[[dict[str, Any]], None]) -> Callable[[Path], None]:
    """Return a fixture change that rewrites one TOML file."""

    def apply(root: Path) -> None:
        target = root / rel
        data = read_toml(target)
        change(data)
        target.write_text(guard.dump_toml(data), encoding="utf-8")

    return apply


def put(dotted: str, value: object) -> Callable[[dict[str, Any]], None]:
    """Return a change that sets a dotted path."""

    def change(data: dict[str, Any]) -> None:
        _put(data, dotted, value)

    return change


def pop(dotted: str) -> Callable[[dict[str, Any]], None]:
    """Return a change that removes a dotted path."""

    def change(data: dict[str, Any]) -> None:
        _pop(data, dotted)

    return change


def adds(name: str) -> Callable[[dict[str, Any]], None]:
    """Append a dependency name."""

    def change(data: dict[str, Any]) -> None:
        _extend(data, ["project", "dependencies"], name)

    return change


def _plant_list(parts: list[str]) -> Callable[[str, str, dict[str, Any]], None]:
    def plant(t: str, _f: str, data: dict[str, Any]) -> None:
        _extend(data, parts, t)

    return plant


def _plant_sources(t: str, _f: str, data: dict[str, Any]) -> None:
    cur = data.setdefault("tool", {}).setdefault("uv", {}).setdefault("sources", {})
    if isinstance(cur, dict):
        cur[t] = {"workspace": True}


def _plant_opt(t: str, _f: str, data: dict[str, Any]) -> None:
    _put(data, "project.optional-dependencies", {"x": [t]})


def _plant_dg(t: str, _f: str, data: dict[str, Any]) -> None:
    _put(data, "dependency-groups", {"g": [t]})


def _plant_scoped(
    t: str,
    f: str,
    data: dict[str, Any],
    mode: int,
    dotted: str,
) -> None:
    if mode == 0:
        _put(data, dotted, [t])
        return
    if mode == 1:
        row = [{"package": {"name": t}, "dependencies": [f]}]
    else:
        row = [{"package": {"name": f}, "dependencies": [t]}]
    _put(data, dotted, row)


def _plant_depmeta(
    t: str,
    f: str,
    data: dict[str, Any],
    mode: int,
    dotted: str = "tool.uv.dependency-metadata",
) -> None:
    if mode == 0:
        _put(data, dotted, [{"name": t, "version": "0.0.0"}])
    else:
        _put(
            data,
            dotted,
            [{"name": f, "version": "0.0.0", "requires-dist": [t]}],
        )


def _plant_conflicts(t: str, f: str, data: dict[str, Any]) -> None:
    pair = [{"package": t, "extra": "x"}, {"package": f, "extra": "y"}]
    _put(data, "tool.uv.conflicts", [pair])


def _plant_map(t: str, f: str, data: dict[str, Any], dotted: str) -> None:
    if dotted.endswith("exclude-newer-package"):
        _put(data, dotted, {t: "2020-01-01T00:00:00Z"})
    else:
        _put(data, dotted, {t: {"k": "v"}})


def _plant_extra_build(
    t: str,
    f: str,
    data: dict[str, Any],
    mode: int,
    dotted: str = "tool.uv.extra-build-dependencies",
) -> None:
    if mode == 0:
        _put(data, dotted, {t: [f]})
    elif mode == 1:
        _put(data, dotted, {f: [t]})
    else:
        _put(data, dotted, {f: [{"requirement": t, "match-runtime": False}]})


def _pip_path(key: str) -> list[str]:
    return ["tool", "uv", "pip", key]


PYPROJECT_PLANTS: list[tuple[str, Callable[[str, str, dict[str, Any]], None]]] = []
for label, parts in (
    ("project.dependencies", ["project", "dependencies"]),
    ("build-system.requires", ["build-system", "requires"]),
    ("tool.uv.dev-dependencies", ["tool", "uv", "dev-dependencies"]),
    ("tool.uv.constraint-dependencies", ["tool", "uv", "constraint-dependencies"]),
    (
        "tool.uv.build-constraint-dependencies",
        ["tool", "uv", "build-constraint-dependencies"],
    ),
    ("tool.uv.no-binary-package", ["tool", "uv", "no-binary-package"]),
    (
        "tool.uv.no-build-isolation-package",
        ["tool", "uv", "no-build-isolation-package"],
    ),
    ("tool.uv.no-build-package", ["tool", "uv", "no-build-package"]),
    ("tool.uv.no-sources-package", ["tool", "uv", "no-sources-package"]),
    ("tool.uv.reinstall-package", ["tool", "uv", "reinstall-package"]),
    ("tool.uv.upgrade-package", ["tool", "uv", "upgrade-package"]),
):
    PYPROJECT_PLANTS.append((label, _plant_list(parts)))
PYPROJECT_PLANTS += [
    ("project.optional-dependencies", _plant_opt),
    ("dependency-groups", _plant_dg),
    ("tool.uv.sources", _plant_sources),
]


def _bind_mode_plant(
    mode: int,
    fn: Callable[[str, str, dict[str, Any], int], None],
) -> Callable[[str, str, dict[str, Any]], None]:
    def plant(t: str, f: str, d: dict[str, Any]) -> None:
        fn(t, f, d, mode)

    return plant


def _bind_map(dotted: str) -> Callable[[str, str, dict[str, Any]], None]:
    def plant(t: str, f: str, d: dict[str, Any]) -> None:
        _plant_map(t, f, d, dotted)

    return plant


def _bind_depmeta(
    mode: int,
    dotted: str,
) -> Callable[[str, str, dict[str, Any]], None]:
    def plant(t: str, f: str, d: dict[str, Any]) -> None:
        _plant_depmeta(t, f, d, mode, dotted)

    return plant


def _bind_extra_build(
    mode: int,
    dotted: str,
) -> Callable[[str, str, dict[str, Any]], None]:
    def plant(t: str, f: str, d: dict[str, Any]) -> None:
        _plant_extra_build(t, f, d, mode, dotted)

    return plant


def _mode_plants(
    label: str,
    fn: Callable[[str, str, dict[str, Any], int], None],
    modes: int,
) -> None:
    for mode in range(modes):
        PYPROJECT_PLANTS.append((label, _bind_mode_plant(mode, fn)))


def _plant_override_deps(t: str, f: str, d: dict[str, Any], m: int) -> None:
    _plant_scoped(t, f, d, m, "tool.uv.override-dependencies")


def _plant_exclude_deps(t: str, f: str, d: dict[str, Any], m: int) -> None:
    _plant_scoped(t, f, d, m, "tool.uv.exclude-dependencies")


_mode_plants("tool.uv.override-dependencies", _plant_override_deps, 3)
_mode_plants("tool.uv.exclude-dependencies", _plant_exclude_deps, 3)
_mode_plants("tool.uv.dependency-metadata", _plant_depmeta, 2)
PYPROJECT_PLANTS += [
    ("tool.uv.conflicts", _plant_conflicts),
    ("tool.uv.config-settings-package", _bind_map("tool.uv.config-settings-package")),
    ("tool.uv.exclude-newer-package", _bind_map("tool.uv.exclude-newer-package")),
]
_mode_plants("tool.uv.extra-build-dependencies", _plant_extra_build, 3)
PYPROJECT_PLANTS.append(
    ("tool.uv.extra-build-variables", _bind_map("tool.uv.extra-build-variables")),
)
for key in PIP_KEYS:
    if key in ("dependency-metadata",):
        for mode in range(2):
            dotted = f"tool.uv.pip.{key}"
            PYPROJECT_PLANTS.append((dotted, _bind_depmeta(mode, dotted)))
    elif key in ("extra-build-dependencies",):
        for mode in range(3):
            dotted = f"tool.uv.pip.{key}"
            PYPROJECT_PLANTS.append((dotted, _bind_extra_build(mode, dotted)))
    elif key in (
        "config-settings-package",
        "exclude-newer-package",
        "extra-build-variables",
    ):
        dotted = f"tool.uv.pip.{key}"
        PYPROJECT_PLANTS.append((dotted, _bind_map(dotted)))
    else:
        dotted = f"tool.uv.pip.{key}"
        PYPROJECT_PLANTS.append((dotted, _plant_list(_pip_path(key))))


def apply_pyproject_plant(
    data: dict[str, Any],
    label: str,
    target: str,
    filler: str = FILLER,
    rep: int = 0,
) -> None:
    """Merge one pyproject plant into a parsed member file."""
    matches = [fn for lab, fn in PYPROJECT_PLANTS if lab == label]
    matches[rep](target, filler, data)


def package_entry(lock: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the package table for ``name``."""
    for key in ("package", "distribution"):
        block = lock.get(key)
        if isinstance(block, list):
            for row in block:
                if isinstance(row, dict) and row.get("name") == name:
                    return row
    created: dict[str, Any] = {
        "name": name,
        "version": "0.0.0",
        "source": {"editable": "x"},
    }
    pkg = lock.setdefault("package", [])
    if not isinstance(pkg, list):
        pkg = []
        lock["package"] = pkg
    pkg.append(created)
    return created


def drop_core_edge(lock: dict[str, Any], name: str) -> None:
    """Remove ``eii-core`` edges from one package entry."""
    entry = package_entry(lock, name)
    deps = entry.get("dependencies")
    if isinstance(deps, list):
        entry["dependencies"] = [d for d in deps if d.get("name") != "eii-core"]
    meta = entry.get("metadata")
    if isinstance(meta, dict):
        rd = meta.get("requires-dist")
        if isinstance(rd, list):
            meta["requires-dist"] = [d for d in rd if d.get("name") != "eii-core"]


def add_dependency(lock: dict[str, Any], name: str, target: str) -> None:
    """Append a dependency edge on a package entry."""
    entry = package_entry(lock, name)
    deps = entry.get("dependencies")
    if not isinstance(deps, list):
        deps = []
    deps.append({"name": target})
    entry["dependencies"] = deps


def drop_product(lock: dict[str, Any]) -> None:
    """Remove the ``eii-product`` package entry."""
    for key in ("package", "distribution"):
        block = lock.get(key)
        if isinstance(block, list):
            lock[key] = [e for e in block if e.get("name") != "eii-product"]


def _lock_rep(entry: dict[str, Any], t: str, mode: int) -> None:
    if mode == 0:
        deps = entry.setdefault("dependencies", [])
        deps.append({"name": t})
    elif mode == 1:
        entry["optional-dependencies"] = {"x": [{"name": t}]}
    elif mode == 2:
        entry["dev-dependencies"] = {"g": [{"name": t}]}
    elif mode == 3:
        entry["dependency-groups"] = {"g": [{"name": t}]}
    elif mode == 4:
        meta = entry.setdefault("metadata", {})
        rd = meta.setdefault("requires-dist", [])
        rd.append({"name": t})
    elif mode == 5:
        meta = entry.setdefault("metadata", {})
        meta["requires-dev"] = {"g": [{"name": t}]}
    elif mode == 6:
        meta = entry.setdefault("metadata", {})
        meta["dependency-groups"] = {"g": [{"name": t}]}


PACKAGE_LOCK_PLANTS = list(range(8))


def apply_package_lock_plant(
    lock: dict[str, Any],
    rep: int,
    source: str,
    target: str,
) -> None:
    """Apply one package-level lock plant."""
    entry = package_entry(lock, source)
    if rep == 7:
        src = copy.deepcopy(entry)
        pkg = lock.setdefault("package", [])
        lock["package"] = [e for e in pkg if e.get("name") != source]
        deps = src.setdefault("dependencies", [])
        deps.append({"name": target})
        lock["distribution"] = [src]
        return
    _lock_rep(entry, target, rep)


WIDE_LOCK_PLANTS: list[tuple[str, int]] = [
    ("manifest.constraints", 0),
    ("manifest.overrides", 0),
    ("manifest.overrides", 1),
    ("manifest.overrides", 2),
    ("manifest.excludes", 0),
    ("manifest.excludes", 1),
    ("manifest.excludes", 2),
    ("manifest.build-constraints", 0),
    ("manifest.dependency-metadata", 0),
    ("manifest.dependency-metadata", 1),
    ("manifest.dependency-groups", 0),
    ("manifest.requirements", 0),
    ("conflicts", 0),
    ("options.exclude-newer-package", 0),
]


def _manifest_triple(target: str, filler: str, rep: int) -> object:
    if rep == 0:
        return [{"name": target}]
    if rep == 1:
        row = {"package": {"name": target}, "dependencies": [filler]}
        return [row]
    row = {"package": {"name": filler}, "dependencies": [target]}
    return [row]


def apply_wide_lock_plant(
    lock: dict[str, Any],
    field: str,
    target: str,
    rep: int,
    filler: str = FILLER,
) -> None:
    man = lock.setdefault("manifest", {})
    if field == "manifest.constraints":
        man["constraints"] = [{"name": target}]
    elif field in ("manifest.overrides", "manifest.excludes"):
        key = field.split(".", 1)[1]
        if rep == 0 and field == "manifest.excludes":
            man[key] = [target]
        else:
            man[key] = _manifest_triple(target, filler, rep)
    elif field == "manifest.build-constraints":
        man["build-constraints"] = [{"name": target}]
    elif field == "manifest.dependency-metadata":
        if rep == 0:
            man["dependency-metadata"] = [{"name": target}]
        else:
            row = {"name": filler, "requires-dist": [target]}
            man["dependency-metadata"] = [row]
    elif field == "manifest.dependency-groups":
        man["dependency-groups"] = {"g": [{"name": target}]}
    elif field == "manifest.requirements":
        man["requirements"] = [{"name": target}]
    elif field == "conflicts":
        pair = [{"package": target, "extra": "x"}, {"package": filler, "extra": "y"}]
        lock["conflicts"] = [pair]
    elif field == "options.exclude-newer-package":
        opts = lock.setdefault("options", {})
        opts.setdefault("exclude-newer-package", {})[target] = "2020-01-01T00:00:00Z"


from workspace_fields_tables import (  # noqa: E402
    LAYOUT_CASES,
    LOCK_MEMBER_CASES,
    MEMBER_LIST_CASES,
    OUTPUT_ORDER_A,
    OUTPUT_ORDER_B,
    OUTPUT_ORDER_C,
    ROOT_FLAG_CASES,
    ROOT_NAMING_CASES,
    SOURCE_CASES,
    invalid_pyproject_cases,
    plant_output_order_a,
    plant_output_order_b,
    plant_output_order_c,
    plant_registry_forbidden_edge,
    write_toml,
)

__all__ = [
    "LAYOUT_CASES",
    "LOCK_MEMBER_CASES",
    "MEMBER_LIST_CASES",
    "OUTPUT_ORDER_A",
    "OUTPUT_ORDER_B",
    "OUTPUT_ORDER_C",
    "ROOT_FLAG_CASES",
    "ROOT_NAMING_CASES",
    "SOURCE_CASES",
    "invalid_pyproject_cases",
    "plant_output_order_a",
    "plant_output_order_b",
    "plant_output_order_c",
    "plant_registry_forbidden_edge",
    "write_toml",
]
