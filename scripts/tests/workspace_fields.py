"""Plants and case tables for workspace metadata tests."""

from __future__ import annotations

import copy
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import workspace_guard as guard

EXPECTED_PYPROJECT_FIELDS = 34
EXPECTED_PYPROJECT_PLANTS = 44
EXPECTED_PACKAGE_LOCK_PLANTS = 8
EXPECTED_WIDE_LOCK_PLANTS = 14
COUNT_EVERY_PLACE = 176
COUNT_LOCK_EDGES = 80
COUNT_WIDE = 42
COUNT_PATHS = 20
COUNT_SPELLINGS = 10
COUNT_PYPROJECT_CASES = 8
MEMBERS = ("core", "custodian", "product")
NAMES = ("eii-core", "eii-custodian", "eii-product")
NOT_VALID = "not = [valid"
FILLER = "filler"
PIP_KEYS = (
    "config-settings-package", "dependency-metadata", "exclude-newer-package",
    "extra-build-dependencies", "extra-build-variables", "no-binary",
    "no-build-isolation-package", "no-emit-package", "no-sources-package",
    "only-binary", "reinstall-package", "upgrade-package",
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


def _plant_list(parts: list[str]) -> Callable[[dict[str, Any], str, str], None]:
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


def _plant_override(t: str, f: str, data: dict[str, Any], mode: int) -> None:
    if mode == 0:
        _put(data, "tool.uv.override-dependencies", [t])
    elif mode == 1:
        _put(data, "tool.uv.override-dependencies", [{"package": {"name": t}, "dependencies": [f]}])
    else:
        _put(data, "tool.uv.override-dependencies", [{"package": {"name": f}, "dependencies": [t]}])


def _plant_exclude(t: str, f: str, data: dict[str, Any], mode: int) -> None:
    if mode == 0:
        _put(data, "tool.uv.exclude-dependencies", [t])
    elif mode == 1:
        _put(data, "tool.uv.exclude-dependencies", [{"package": {"name": t}, "dependencies": [f]}])
    else:
        _put(data, "tool.uv.exclude-dependencies", [{"package": {"name": f}, "dependencies": [t]}])


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
    _put(data, "tool.uv.conflicts", [[{"package": t, "extra": "x"}, {"package": f, "extra": "y"}]])


def _plant_map(t: str, f: str, data: dict[str, Any], dotted: str) -> None:
    _put(data, dotted, {t: "2020-01-01T00:00:00Z" if dotted.endswith("exclude-newer-package") else {"k": "v"}})


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


PYPROJECT_PLANTS: list[tuple[str, Callable[[dict[str, Any], str, str], None]]] = []
for label, parts in (
    ("project.dependencies", ["project", "dependencies"]),
    ("build-system.requires", ["build-system", "requires"]),
    ("tool.uv.dev-dependencies", ["tool", "uv", "dev-dependencies"]),
    ("tool.uv.constraint-dependencies", ["tool", "uv", "constraint-dependencies"]),
    ("tool.uv.build-constraint-dependencies", ["tool", "uv", "build-constraint-dependencies"]),
    ("tool.uv.no-binary-package", ["tool", "uv", "no-binary-package"]),
    ("tool.uv.no-build-isolation-package", ["tool", "uv", "no-build-isolation-package"]),
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
for mode in range(3):
    PYPROJECT_PLANTS.append(
        (
            "tool.uv.override-dependencies",
            lambda t, f, d, m=mode: _plant_override(t, f, d, m),
        ),
    )
for mode in range(3):
    PYPROJECT_PLANTS.append(
        (
            "tool.uv.exclude-dependencies",
            lambda t, f, d, m=mode: _plant_exclude(t, f, d, m),
        ),
    )
for mode in range(2):
    PYPROJECT_PLANTS.append(
        (
            "tool.uv.dependency-metadata",
            lambda t, f, d, m=mode: _plant_depmeta(t, f, d, m),
        ),
    )
PYPROJECT_PLANTS += [
    ("tool.uv.conflicts", _plant_conflicts),
    (
        "tool.uv.config-settings-package",
        lambda t, f, d: _plant_map(t, f, d, "tool.uv.config-settings-package"),
    ),
    (
        "tool.uv.exclude-newer-package",
        lambda t, f, d: _plant_map(t, f, d, "tool.uv.exclude-newer-package"),
    ),
]
for mode in range(3):
    PYPROJECT_PLANTS.append(
        (
            "tool.uv.extra-build-dependencies",
            lambda t, f, d, m=mode: _plant_extra_build(t, f, d, m),
        ),
    )
PYPROJECT_PLANTS.append(
    (
        "tool.uv.extra-build-variables",
        lambda t, f, d: _plant_map(t, f, d, "tool.uv.extra-build-variables"),
    ),
)
for key in PIP_KEYS:
    if key in ("dependency-metadata",):
        for mode in range(2):
            dotted = f"tool.uv.pip.{key}"
            PYPROJECT_PLANTS.append(
                (
                    dotted,
                    lambda t, f, d, m=mode, dt=dotted: _plant_depmeta(t, f, d, m, dt),
                ),
            )
    elif key in (
        "extra-build-dependencies",
    ):
        for mode in range(3):
            dotted = f"tool.uv.pip.{key}"
            PYPROJECT_PLANTS.append(
                (
                    dotted,
                    lambda t, f, d, m=mode, dt=dotted: _plant_extra_build(t, f, d, m, dt),
                ),
            )
    elif key in ("config-settings-package", "exclude-newer-package", "extra-build-variables"):
        dotted = f"tool.uv.pip.{key}"
        PYPROJECT_PLANTS.append(
            (
                dotted,
                lambda t, f, d, dt=dotted: _plant_map(t, f, d, dt),
            ),
        )
    else:
        dotted = f"tool.uv.pip.{key}"
        PYPROJECT_PLANTS.append((dotted, _plant_list(_pip_path(key))))


def apply_pyproject_plant(
    data: dict[str, Any], label: str, target: str, filler: str = FILLER, rep: int = 0,
) -> None:
    """Merge one pyproject plant into a parsed member file."""
    matches = [fn for lab, fn in PYPROJECT_PLANTS if lab == label]
    matches[rep](target, filler, data)


def package_entry(lock: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the package table for ``name``."""
    for key in ("package", "distribution"):
        block = lock.get(key)
        if isinstance(block, list):
            for entry in block:
                if isinstance(entry, dict) and entry.get("name") == name:
                    return entry
    entry: dict[str, Any] = {"name": name, "version": "0.0.0", "source": {"editable": "x"}}
    pkg = lock.setdefault("package", [])
    if not isinstance(pkg, list):
        pkg = []
        lock["package"] = pkg
    pkg.append(entry)
    return entry


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


def apply_package_lock_plant(lock: dict[str, Any], rep: int, source: str, target: str) -> None:
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
    ("manifest.constraints", 0), ("manifest.overrides", 0), ("manifest.overrides", 1),
    ("manifest.overrides", 2), ("manifest.excludes", 0), ("manifest.excludes", 1),
    ("manifest.excludes", 2), ("manifest.build-constraints", 0),
    ("manifest.dependency-metadata", 0), ("manifest.dependency-metadata", 1),
    ("manifest.dependency-groups", 0), ("manifest.requirements", 0), ("conflicts", 0),
    ("options.exclude-newer-package", 0),
]


def apply_wide_lock_plant(
    lock: dict[str, Any], field: str, target: str, rep: int, filler: str = FILLER,
) -> None:
    """Apply one workspace-wide lock field plant."""
    man = lock.setdefault("manifest", {})
    if field == "manifest.constraints":
        man["constraints"] = [{"name": target}]
    elif field == "manifest.overrides":
        if rep == 0:
            man["overrides"] = [{"name": target}]
        elif rep == 1:
            man["overrides"] = [{"package": {"name": target}, "dependencies": [filler]}]
        else:
            man["overrides"] = [{"package": {"name": filler}, "dependencies": [target]}]
    elif field == "manifest.excludes":
        if rep == 0:
            man["excludes"] = [target]
        elif rep == 1:
            man["excludes"] = [{"package": {"name": target}, "dependencies": [filler]}]
        else:
            man["excludes"] = [{"package": {"name": filler}, "dependencies": [target]}]
    elif field == "manifest.build-constraints":
        man["build-constraints"] = [{"name": target}]
    elif field == "manifest.dependency-metadata":
        if rep == 0:
            man["dependency-metadata"] = [{"name": target}]
        else:
            man["dependency-metadata"] = [{"name": filler, "requires-dist": [target]}]
    elif field == "manifest.dependency-groups":
        man["dependency-groups"] = {"g": [{"name": target}]}
    elif field == "manifest.requirements":
        man["requirements"] = [{"name": target}]
    elif field == "conflicts":
        lock["conflicts"] = [[{"package": target, "extra": "x"}, {"package": filler, "extra": "y"}]]
    elif field == "options.exclude-newer-package":
        opts = lock.setdefault("options", {})
        opts.setdefault("exclude-newer-package", {})[target] = "2020-01-01T00:00:00Z"


def _root_name_case(name: str, field: str) -> tuple[str, Callable[[Path], None], list[str]]:
    if field == "project.dependencies":
        plant = edit("pyproject.toml", adds(name))
    else:
        plant = edit("pyproject.toml", put("dependency-groups", {"dev": [name]}))
    norm = guard.normalise(name)
    line = f"FAIL root-clean: pyproject.toml: {field} names {norm}"
    return (f"root {field} {name}", plant, [line])


ROOT_NAMING_CASES = [
    _root_name_case(n, f) for n in NAMES for f in ("project.dependencies", "dependency-groups")
]

ROOT_FLAG_CASES = [
    ("name other", edit("pyproject.toml", put("project.name", "other")),
     ["FAIL root-clean: pyproject.toml: name is other expected eii-workspace"]),
    ("package true", edit("pyproject.toml", put("tool.uv.package", True)),
     ["FAIL root-clean: pyproject.toml: tool.uv.package is not false"]),
    ("package removed", edit("pyproject.toml", pop("tool.uv.package")),
     ["FAIL root-clean: pyproject.toml: tool.uv.package is not false"]),
    ("Eii_Workspace", edit("pyproject.toml", put("project.name", "Eii_Workspace")), []),
]

SOURCE_CASES = [
    ("custodian removed", edit("custodian/pyproject.toml", pop("tool.uv.sources")),
     ["FAIL workspace-source: custodian/pyproject.toml: eii-core is not taken from the workspace"]),
    ("product removed", edit("product/pyproject.toml", pop("tool.uv.sources")),
     ["FAIL workspace-source: product/pyproject.toml: eii-core is not taken from the workspace"]),
    ("custodian string", edit("custodian/pyproject.toml", put("tool.uv.sources", "eii-core")),
     ["FAIL workspace-source: custodian/pyproject.toml: eii-core is not taken from the workspace"]),
    ("product string", edit("product/pyproject.toml", put("tool.uv.sources", "eii-core")),
     ["FAIL workspace-source: product/pyproject.toml: eii-core is not taken from the workspace"]),
    ("custodian path", edit("custodian/pyproject.toml", put("tool.uv.sources", {"eii-core": {"path": "../core"}})),
     ["FAIL workspace-source: custodian/pyproject.toml: eii-core is not taken from the workspace"]),
    ("product path", edit("product/pyproject.toml", put("tool.uv.sources", {"eii-core": {"path": "../core"}})),
     ["FAIL workspace-source: product/pyproject.toml: eii-core is not taken from the workspace"]),
    ("custodian Eii_Core", edit("custodian/pyproject.toml", put("tool.uv.sources", {"Eii_Core": {"workspace": True}})), []),
    ("product Eii_Core", edit("product/pyproject.toml", put("tool.uv.sources", {"Eii_Core": {"workspace": True}})), []),
    ("custodian mixed", edit("custodian/pyproject.toml", put("tool.uv.sources", {"eii-core": {"workspace": True}, "Eii_Core": {"path": "../core"}})),
     ["FAIL workspace-source: custodian/pyproject.toml: eii-core is not taken from the workspace"]),
    ("product mixed", edit("product/pyproject.toml", put("tool.uv.sources", {"eii-core": {"workspace": True}, "Eii_Core": {"path": "../core"}})),
     ["FAIL workspace-source: product/pyproject.toml: eii-core is not taken from the workspace"]),
]

MEMBER_LIST_CASES = [
    ("gateway", edit("pyproject.toml", put("tool.uv.workspace.members", ["core", "custodian", "product", "gateway"])),
     ["FAIL members: pyproject.toml: members are core, custodian, gateway, product expected core, custodian, product"]),
    ("drop product", edit("pyproject.toml", put("tool.uv.workspace.members", ["core", "custodian"])),
     ["FAIL members: pyproject.toml: members are core, custodian expected core, custodian, product"]),
    ("dup core", edit("pyproject.toml", put("tool.uv.workspace.members", ["core", "core", "custodian", "product"])),
     ["FAIL members: pyproject.toml: members are core, core, custodian, product expected core, custodian, product"]),
    ("empty", edit("pyproject.toml", put("tool.uv.workspace.members", [])),
     ["FAIL members: pyproject.toml: members are <none> expected core, custodian, product"]),
    ("members string", edit("pyproject.toml", put("tool.uv.workspace", {"members": "core"})),
     ["FAIL members: pyproject.toml: members are <none> expected core, custodian, product"]),
    ("workspace string", edit("pyproject.toml", put("tool.uv.workspace", "members")),
     ["FAIL members: pyproject.toml: members are <none> expected core, custodian, product"]),
    ("exclude", edit("pyproject.toml", put("tool.uv.workspace", {"members": ["core", "custodian", "product"], "exclude": ["core"]})),
     ["FAIL members: pyproject.toml: exclude is not empty"]),
]

LAYOUT_CASES = [
    ("core layout", lambda root: (shutil.rmtree(root / "core/src", ignore_errors=True), (root / "core/eii_core").mkdir(parents=True, exist_ok=True), (root / "core/eii_core/__init__.py").write_text('__version__ = "0.0.0"\n')),
     ["FAIL package-layout: core/src/eii_core/__init__.py: missing"]),
    ("custodian init", lambda root: (root / "custodian/src/eii_custodian/__init__.py").unlink(),
     ["FAIL package-layout: custodian/src/eii_custodian/__init__.py: missing"]),
    ("product bad name", edit("product/pyproject.toml", put("project.name", "eii-productx")),
     ["FAIL package-layout: product/pyproject.toml: name is eii-productx expected eii-product"]),
    ("Eii_Product", edit("product/pyproject.toml", put("project.name", "Eii_Product")), []),
    ("core init dir", lambda root: ((root / "core/src/eii_core/__init__.py").unlink(missing_ok=True), (root / "core/src/eii_core/__init__.py").mkdir(parents=True)),
     ["FAIL package-layout: core/src/eii_core/__init__.py: missing"]),
    ("no project", edit("product/pyproject.toml", lambda d: d.pop("project", None)),
     ["FAIL package-layout: product/pyproject.toml: name is <none> expected eii-product"]),
    ("core deleted", lambda root: (root / "core/pyproject.toml").unlink(),
     ["FAIL package-layout: core/pyproject.toml: missing or not valid TOML"]),
]

LOCK_MEMBER_CASES = [
    ("drop product", lambda lock: lock.setdefault("manifest", {}).update({"members": ["eii-core", "eii-custodian", "eii-workspace"]}),
     ["FAIL lock: uv.lock: manifest.members are eii-core, eii-custodian, eii-workspace expected eii-core, eii-custodian, eii-product, eii-workspace"]),
    ("add gateway", lambda lock: lock.setdefault("manifest", {}).update({"members": ["eii-core", "eii-custodian", "eii-gateway", "eii-product", "eii-workspace"]}),
     ["FAIL lock: uv.lock: manifest.members are eii-core, eii-custodian, eii-gateway, eii-product, eii-workspace expected eii-core, eii-custodian, eii-product, eii-workspace"]),
    ("members string", lambda lock: lock.setdefault("manifest", {}).update({"members": "eii-core"}),
     ["FAIL lock: uv.lock: manifest.members are <none> expected eii-core, eii-custodian, eii-product, eii-workspace"]),
    ("Eii_Product", lambda lock: lock.setdefault("manifest", {}).update({"members": ["eii-core", "eii-custodian", "Eii_Product", "eii-workspace"]}), []),
]

