"""Workspace metadata guard for the uv workspace (stdlib only, not a test module)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import workspace_toml

dump_toml = workspace_toml.dump_toml

ROOT_DIST = "eii-workspace"
MEMBER_ROWS: tuple[tuple[str, str, str], ...] = (
    ("core", "eii-core", "eii_core"),
    ("custodian", "eii-custodian", "eii_custodian"),
    ("product", "eii-product", "eii_product"),
)
MEMBER_DIRS: tuple[str, ...] = tuple(r[0] for r in MEMBER_ROWS)
MEMBER_NAMES: frozenset[str] = frozenset(r[1] for r in MEMBER_ROWS)
FORBIDDEN_BY_MEMBER: dict[str, frozenset[str]] = {
    "eii-core": frozenset({"eii-custodian", "eii-product"}),
    "eii-custodian": frozenset({"eii-product"}),
    "eii-product": frozenset({"eii-custodian"}),
}
ALLOWED_LOCK_EDGES: frozenset[tuple[str, str]] = frozenset(
    {("eii-custodian", "eii-core"), ("eii-product", "eii-core")},
)
WORKSPACE_PKGS: frozenset[str] = frozenset(
    {"eii-workspace", "eii-core", "eii-custodian", "eii-product"},
)
EXPECTED_MANIFEST_MEMBERS: tuple[str, ...] = (
    "eii-core",
    "eii-custodian",
    "eii-product",
    "eii-workspace",
)

PIPScan_KEYS: tuple[str, ...] = (
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

SCANNED_PYPROJECT_FIELDS: tuple[str, ...] = (
    "project.dependencies",
    "project.optional-dependencies",
    "dependency-groups",
    "build-system.requires",
    "tool.uv.sources",
    "tool.uv.dev-dependencies",
    "tool.uv.constraint-dependencies",
    "tool.uv.build-constraint-dependencies",
    "tool.uv.override-dependencies",
    "tool.uv.exclude-dependencies",
    "tool.uv.dependency-metadata",
    "tool.uv.conflicts",
    "tool.uv.config-settings-package",
    "tool.uv.exclude-newer-package",
    "tool.uv.extra-build-dependencies",
    "tool.uv.extra-build-variables",
    "tool.uv.no-binary-package",
    "tool.uv.no-build-isolation-package",
    "tool.uv.no-build-package",
    "tool.uv.no-sources-package",
    "tool.uv.reinstall-package",
    "tool.uv.upgrade-package",
    *tuple(f"tool.uv.pip.{k}" for k in PIPScan_KEYS),
)

WORKSPACE_WIDE_LOCK_FIELDS: tuple[str, ...] = (
    "manifest.constraints",
    "manifest.overrides",
    "manifest.excludes",
    "manifest.build-constraints",
    "manifest.dependency-metadata",
    "manifest.dependency-groups",
    "manifest.requirements",
    "conflicts",
    "options.exclude-newer-package",
)

NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
FILE_URI_RE = re.compile(r"(?:^|[+=\s])(file:)", re.IGNORECASE)


def normalise(name: str) -> str:
    """Lower-case a name and collapse ``-``, ``_`` and ``.`` runs to hyphens."""
    lowered = name.lower()
    return re.sub(r"[-_.]+", "-", lowered)


def requirement_name(text: str) -> str | None:
    """Return the leading PEP 508 name token, normalised, or ``None``."""
    match = NAME_RE.match(text)
    if not match:
        return None
    return normalise(match.group(1))


def names_in(value: object) -> set[str]:
    """Collect normalised distribution names from a parsed TOML value."""
    found: set[str] = set()
    if isinstance(value, str):
        parsed = requirement_name(value)
        if parsed is not None:
            found.add(parsed)
    elif isinstance(value, list):
        for item in value:
            found |= names_in(item)
    elif isinstance(value, dict):
        for key, child in value.items():
            found.add(normalise(str(key)))
            found |= names_in(child)
    return found


def _fail(rule: str, path: str, detail: str) -> str:
    return f"FAIL {rule}: {path}: {detail}"


def _dig(data: dict[str, Any], dotted: str) -> object | None:
    parts = dotted.split(".")
    cur: object = data
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _pyproject_field_lines(
    rule: str,
    rel_path: str,
    data: dict[str, Any],
    forbidden: frozenset[str],
) -> list[str]:
    lines: list[str] = []
    for field in SCANNED_PYPROJECT_FIELDS:
        value = _dig(data, field)
        if value is None:
            continue
        hits = sorted(names_in(value) & forbidden)
        for target in hits:
            lines.append(_fail(rule, rel_path, f"{field} names {target}"))
    return lines


def _rule_members(root: Path, data: dict[str, Any] | None) -> tuple[list[str], bool]:
    if data is None:
        return [_fail("members", "pyproject.toml", "missing or not valid TOML")], True
    workspace = _dig(data, "tool.uv.workspace")
    if not isinstance(workspace, dict):
        members_raw: object = None
    else:
        members_raw = workspace.get("members")
        exclude = workspace.get("exclude")
        if exclude:
            return [_fail("members", "pyproject.toml", "exclude is not empty")], False
    if not isinstance(members_raw, list) or not members_raw:
        listed = "<none>"
    else:
        listed = ", ".join(sorted(str(m) for m in members_raw))
    expected = ", ".join(MEMBER_DIRS)
    if listed != expected:
        detail = f"members are {listed} expected {expected}"
        return [_fail("members", "pyproject.toml", detail)], True
    return [], False


def _rule_root_clean(
    data: dict[str, Any] | None,
    members_invalid: bool,
) -> list[str]:
    if members_invalid or data is None:
        return []
    lines: list[str] = []
    name_val = _dig(data, "project.name")
    if not isinstance(name_val, str) or normalise(name_val) != normalise(ROOT_DIST):
        shown = name_val if isinstance(name_val, str) else "<none>"
        detail = f"name is {shown} expected {ROOT_DIST}"
        lines.append(_fail("root-clean", "pyproject.toml", detail))
    package_flag = _dig(data, "tool.uv.package")
    if package_flag is not False:
        detail = "tool.uv.package is not false"
        lines.append(_fail("root-clean", "pyproject.toml", detail))
    forbidden = MEMBER_NAMES
    lines.extend(
        _pyproject_field_lines("root-clean", "pyproject.toml", data, forbidden),
    )
    return lines


def _rule_package_layout(root: Path) -> list[str]:
    lines: list[str] = []
    for mdir, dist, module in MEMBER_ROWS:
        rel = f"{mdir}/pyproject.toml"
        pdata = workspace_toml.load_toml(root / rel)
        if pdata is None:
            lines.append(_fail("package-layout", rel, "missing or not valid TOML"))
            continue
        pname = _dig(pdata, "project.name")
        if not isinstance(pname, str) or normalise(pname) != dist:
            shown = pname if isinstance(pname, str) else "<none>"
            detail = f"name is {shown} expected {dist}"
            lines.append(_fail("package-layout", rel, detail))
        init_rel = f"{mdir}/src/{module}/__init__.py"
        if not (root / init_rel).is_file():
            lines.append(_fail("package-layout", init_rel, "missing"))
    return lines


def _rule_workspace_source(root: Path) -> list[str]:
    miss = "eii-core is not taken from the workspace"
    lines: list[str] = []
    for mdir, _dist, _module in MEMBER_ROWS:
        if mdir not in ("custodian", "product"):
            continue
        rel = f"{mdir}/pyproject.toml"
        pdata = workspace_toml.load_toml(root / rel)
        if pdata is None:
            continue
        sources = _dig(pdata, "tool.uv.sources")
        if not isinstance(sources, dict):
            lines.append(_fail("workspace-source", rel, miss))
            continue
        core_keys = [k for k in sources if normalise(str(k)) == "eii-core"]
        if not core_keys:
            lines.append(_fail("workspace-source", rel, miss))
            continue
        bad = any(sources[k] != {"workspace": True} for k in core_keys)
        if bad:
            lines.append(_fail("workspace-source", rel, miss))
    return lines


def _rule_dependency_edge(root: Path) -> list[str]:
    lines: list[str] = []
    for mdir, dist, _module in MEMBER_ROWS:
        rel = f"{mdir}/pyproject.toml"
        pdata = workspace_toml.load_toml(root / rel)
        if pdata is None:
            continue
        forbidden = FORBIDDEN_BY_MEMBER[dist]
        lines.extend(_pyproject_field_lines("dependency-edge", rel, pdata, forbidden))
    return lines


def _package_tables(data: dict[str, Any]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for key in ("package", "distribution"):
        block = data.get(key)
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict):
                    tables.append(item)
    return tables


def _pkg_name(entry: dict[str, Any]) -> str | None:
    name = entry.get("name")
    if not isinstance(name, str):
        return None
    return normalise(name)


def _edges_from_pkg(entry: dict[str, Any]) -> set[tuple[str, str]]:
    source = _pkg_name(entry)
    if source is None:
        return set()
    edges: set[tuple[str, str]] = set()

    def add_from_list(items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict):
                target = item.get("name")
                if isinstance(target, str):
                    edges.add((source, normalise(target)))

    add_from_list(entry.get("dependencies"))
    meta = entry.get("metadata")
    if isinstance(meta, dict):
        add_from_list(meta.get("requires-dist"))
        for key in ("requires-dev", "dependency-groups"):
            block = meta.get(key)
            if isinstance(block, dict):
                for group_list in block.values():
                    add_from_list(group_list)
    for key in ("optional-dependencies", "dev-dependencies", "dependency-groups"):
        block = entry.get(key)
        if isinstance(block, dict):
            for group_list in block.values():
                add_from_list(group_list)
    return edges


def _rule_lock(data: dict[str, Any] | None) -> list[str]:
    if data is None:
        return [_fail("lock", "uv.lock", "missing or not valid TOML")]
    lines: list[str] = []
    by_name: dict[str, dict[str, Any]] = {}
    for entry in _package_tables(data):
        name = _pkg_name(entry)
        if name is not None:
            by_name[name] = entry
    need = ("eii-core", "eii-custodian", "eii-product")
    missing = [n for n in need if n not in by_name]
    if missing:
        for name in missing:
            lines.append(_fail("lock", "uv.lock", f"package {name} is not listed"))
        return lines

    manifest = data.get("manifest")
    members_raw: object = None
    if isinstance(manifest, dict):
        members_raw = manifest.get("members")
    if not isinstance(members_raw, list) or not members_raw:
        listed = "<none>"
    else:
        listed = ", ".join(sorted(normalise(str(m)) for m in members_raw))
    expected = ", ".join(EXPECTED_MANIFEST_MEMBERS)
    if listed != expected:
        detail = f"manifest.members are {listed} expected {expected}"
        lines.append(_fail("lock", "uv.lock", detail))

    observed: set[tuple[str, str]] = set()
    for entry in _package_tables(data):
        name = _pkg_name(entry)
        if name is None or name not in WORKSPACE_PKGS:
            continue
        for src, tgt in _edges_from_pkg(entry):
            if src == tgt:
                continue
            if src in WORKSPACE_PKGS and tgt in WORKSPACE_PKGS:
                observed.add((src, tgt))

    for edge in sorted(observed - ALLOWED_LOCK_EDGES):
        a, b = edge
        lines.append(_fail("lock", "uv.lock", f"edge {a} -> {b} is not allowed"))
    for edge in sorted(ALLOWED_LOCK_EDGES - observed):
        a, b = edge
        lines.append(_fail("lock", "uv.lock", f"edge {a} -> {b} is missing"))

    for field in WORKSPACE_WIDE_LOCK_FIELDS:
        value = _dig(data, field)
        if value is None:
            continue
        hits = sorted(
            n
            for n in names_in(value)
            if n in {"eii-core", "eii-custodian", "eii-product"}
        )
        for target in hits:
            lines.append(_fail("lock", "uv.lock", f"{field} names {target}"))
    return lines


def _is_bad_path_string(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith("/"):
        return True
    if WIN_DRIVE_RE.match(stripped):
        return True
    if stripped.startswith("\\\\"):
        return True
    if FILE_URI_RE.search(stripped):
        return True
    return False


def _walk_lock_strings(
    value: object,
    prefix: str,
    out: list[tuple[str, str]],
) -> None:
    if isinstance(value, str):
        if _is_bad_path_string(value):
            out.append((prefix, value))
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            key = f"{prefix}[{index}]" if prefix else f"[{index}]"
            _walk_lock_strings(item, key, out)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            part = f"{prefix}.{key}" if prefix else str(key)
            _walk_lock_strings(child, part, out)


def _rule_lock_paths(data: dict[str, Any] | None) -> list[str]:
    if data is None:
        return []
    hits: list[tuple[str, str]] = []
    _walk_lock_strings(data, "", hits)
    return [
        _fail("lock-paths", "uv.lock", f"{path}: absolute path or file URI")
        for path, _value in hits
    ]


def check_lock_data(data: dict[str, Any] | None) -> list[str]:
    """Apply ``lock`` and ``lock-paths`` rules to parsed lock data."""
    lines = _rule_lock(data)
    lines.extend(_rule_lock_paths(data))
    return lines


def check_workspace(root: Path) -> list[str]:
    """Validate workspace metadata under ``root``; return ordered failure lines."""
    root_data = workspace_toml.load_toml(root / "pyproject.toml")
    member_lines, members_invalid = _rule_members(root, root_data)
    lines: list[str] = list(member_lines)
    lines.extend(_rule_root_clean(root_data, members_invalid))
    lines.extend(_rule_package_layout(root))

    lines.extend(_rule_workspace_source(root))
    lines.extend(_rule_dependency_edge(root))

    lock_data = workspace_toml.load_toml(root / "uv.lock")
    if lock_data is None:
        lines.append(_fail("lock", "uv.lock", "missing or not valid TOML"))
    else:
        lines.extend(_rule_lock(lock_data))
        lines.extend(_rule_lock_paths(lock_data))
    return lines
