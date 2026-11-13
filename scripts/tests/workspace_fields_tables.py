"""Rule-test case tables for workspace metadata tests."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import workspace_fields as wf
import workspace_guard as guard

edit = wf.edit
put = wf.put
pop = wf.pop
adds = wf.adds
MEMBERS: tuple[str, ...] = wf.MEMBERS
NAMES: tuple[str, ...] = wf.NAMES


def write_toml(path: Path, data: dict[str, Any]) -> None:
    """Rewrite one TOML file through the guard's writer."""
    path.write_text(guard.dump_toml(data), encoding="utf-8")


def read_toml(path: Path) -> dict[str, Any]:
    """Load one TOML file via the shared test helper."""
    return wf.read_toml(path)


def _root_name_case(
    name: str,
    field: str,
) -> tuple[str, Callable[[Path], None], list[str]]:
    if field == "project.dependencies":
        plant = edit("pyproject.toml", adds(name))
    else:
        plant = edit("pyproject.toml", put("dependency-groups", {"dev": [name]}))
    norm = guard.normalise(name)
    line = f"FAIL root-clean: pyproject.toml: {field} names {norm}"
    return (f"root {field} {name}", plant, [line])


_ROOT_FIELDS = ("project.dependencies", "dependency-groups")
ROOT_NAMING_CASES = [_root_name_case(n, f) for n in NAMES for f in _ROOT_FIELDS]

ROOT_FLAG_CASES = [
    (
        "name other",
        edit("pyproject.toml", put("project.name", "other")),
        ["FAIL root-clean: pyproject.toml: name is other expected eii-workspace"],
    ),
    (
        "package true",
        edit("pyproject.toml", put("tool.uv.package", True)),
        ["FAIL root-clean: pyproject.toml: tool.uv.package is not false"],
    ),
    (
        "package removed",
        edit("pyproject.toml", pop("tool.uv.package")),
        ["FAIL root-clean: pyproject.toml: tool.uv.package is not false"],
    ),
    ("Eii_Workspace", edit("pyproject.toml", put("project.name", "Eii_Workspace")), []),
]

_WS = "eii-core is not taken from the workspace"


def _ws(member: str) -> list[str]:
    return [f"FAIL workspace-source: {member}/pyproject.toml: {_WS}"]


_CWS = {"eii-core": {"workspace": True}}
_CPATH = {"eii-core": {"path": "../core"}}
_MIX = {**_CWS, "Eii_Core": {"path": "../core"}}


SOURCE_CASES = [
    (
        "custodian removed",
        edit("custodian/pyproject.toml", pop("tool.uv.sources")),
        _ws("custodian"),
    ),
    (
        "product removed",
        edit("product/pyproject.toml", pop("tool.uv.sources")),
        _ws("product"),
    ),
    (
        "custodian string",
        edit("custodian/pyproject.toml", put("tool.uv.sources", "eii-core")),
        _ws("custodian"),
    ),
    (
        "product string",
        edit("product/pyproject.toml", put("tool.uv.sources", "eii-core")),
        _ws("product"),
    ),
    (
        "custodian path",
        edit("custodian/pyproject.toml", put("tool.uv.sources", _CPATH)),
        _ws("custodian"),
    ),
    (
        "product path",
        edit("product/pyproject.toml", put("tool.uv.sources", _CPATH)),
        _ws("product"),
    ),
    (
        "custodian Eii_Core",
        edit(
            "custodian/pyproject.toml",
            put("tool.uv.sources", {"Eii_Core": _CWS["eii-core"]}),
        ),
        [],
    ),
    (
        "product Eii_Core",
        edit(
            "product/pyproject.toml",
            put("tool.uv.sources", {"Eii_Core": _CWS["eii-core"]}),
        ),
        [],
    ),
    (
        "custodian mixed",
        edit("custodian/pyproject.toml", put("tool.uv.sources", _MIX)),
        _ws("custodian"),
    ),
    (
        "product mixed",
        edit("product/pyproject.toml", put("tool.uv.sources", _MIX)),
        _ws("product"),
    ),
]

_EXP = "core, custodian, gateway, product"


def _members(listed: str) -> list[str]:
    return [f"FAIL members: pyproject.toml: members are {listed} expected {_EXP}"]


MEMBER_LIST_CASES = [
    (
        "gateway",
        edit("pyproject.toml", put("tool.uv.workspace.members", [*MEMBERS, "extra"])),
        _members("core, custodian, extra, gateway, product"),
    ),
    (
        "drop product",
        edit("pyproject.toml", put("tool.uv.workspace.members", ["core", "custodian"])),
        _members("core, custodian"),
    ),
    (
        "dup core",
        edit(
            "pyproject.toml",
            put("tool.uv.workspace.members", ["core", "core", "custodian", "product"]),
        ),
        _members("core, core, custodian, product"),
    ),
    (
        "empty",
        edit("pyproject.toml", put("tool.uv.workspace.members", [])),
        _members("<none>"),
    ),
    (
        "members string",
        edit("pyproject.toml", put("tool.uv.workspace", {"members": "core"})),
        _members("<none>"),
    ),
    (
        "workspace string",
        edit("pyproject.toml", put("tool.uv.workspace", "members")),
        _members("<none>"),
    ),
    (
        "exclude",
        edit(
            "pyproject.toml",
            put("tool.uv.workspace", {"members": list(MEMBERS), "exclude": ["core"]}),
        ),
        ["FAIL members: pyproject.toml: exclude is not empty"],
    ),
    (
        "members and package",
        edit(
            "pyproject.toml",
            lambda d: (
                put("tool.uv.workspace.members", ["core", "custodian"])(d),
                put("tool.uv.package", True)(d),
                None,
            )[-1],
        ),
        _members("core, custodian"),
    ),
]


def _layout(rel: str, detail: str) -> list[str]:
    return [f"FAIL package-layout: {rel}: {detail}"]


LAYOUT_CASES = [
    (
        "core layout",
        lambda root: (
            shutil.rmtree(root / "core/src", ignore_errors=True),
            (root / "core/eii_core").mkdir(parents=True, exist_ok=True),
            (root / "core/eii_core/__init__.py").write_text(
                '__version__ = "0.0.0"\n',
                encoding="utf-8",
            ),
        ),
        _layout("core/src/eii_core/__init__.py", "missing"),
    ),
    (
        "custodian init",
        lambda root: (root / "custodian/src/eii_custodian/__init__.py").unlink(),
        _layout("custodian/src/eii_custodian/__init__.py", "missing"),
    ),
    (
        "product bad name",
        edit("product/pyproject.toml", put("project.name", "eii-productx")),
        _layout("product/pyproject.toml", "name is eii-productx expected eii-product"),
    ),
    (
        "Eii_Product",
        edit("product/pyproject.toml", put("project.name", "Eii_Product")),
        [],
    ),
    (
        "core init dir",
        lambda root: (
            (root / "core/src/eii_core/__init__.py").unlink(missing_ok=True),
            (root / "core/src/eii_core/__init__.py").mkdir(parents=True),
        ),
        _layout("core/src/eii_core/__init__.py", "missing"),
    ),
    (
        "no project",
        edit("product/pyproject.toml", lambda d: d.pop("project", None)),
        _layout("product/pyproject.toml", "name is <none> expected eii-product"),
    ),
    (
        "core deleted",
        lambda root: (root / "core/pyproject.toml").unlink(),
        _layout("core/pyproject.toml", "missing or not valid TOML"),
    ),
]

_LOCK_EXP = "eii-core, eii-custodian, eii-gateway, eii-product, eii-workspace"


def _lock_members(listed: str) -> list[str]:
    return [f"FAIL lock: uv.lock: manifest.members are {listed} expected {_LOCK_EXP}"]


_TOML_INVALID = "FAIL members: pyproject.toml: missing or not valid TOML"


def _unlink_member_toml(member: str) -> Callable[[Path], None]:
    def plant(root: Path) -> None:
        (root / member / "pyproject.toml").unlink()

    return plant


def _bad_member_toml(member: str) -> Callable[[Path], None]:
    def plant(root: Path) -> None:
        (root / member / "pyproject.toml").write_text(wf.NOT_VALID, encoding="utf-8")

    return plant


def _unlink_root_toml(root: Path) -> None:
    (root / "pyproject.toml").unlink()


def _bad_root_toml(root: Path) -> None:
    (root / "pyproject.toml").write_text(wf.NOT_VALID, encoding="utf-8")


def _core_utf16_toml(root: Path) -> None:
    (root / "core" / "pyproject.toml").write_bytes(b"\xff\xfe")


def invalid_pyproject_cases() -> list[tuple[str, Callable[[Path], None], list[str]]]:
    """Build sub-cases for missing or unparsable workspace pyproject.toml files."""
    bad = "missing or not valid TOML"
    cases: list[tuple[str, Callable[[Path], None], list[str]]] = [
        ("root deleted", _unlink_root_toml, [_TOML_INVALID]),
        ("root bad", _bad_root_toml, [_TOML_INVALID]),
    ]
    for mdir in MEMBERS:
        line = f"FAIL package-layout: {mdir}/pyproject.toml: {bad}"
        cases.append((f"{mdir} deleted", _unlink_member_toml(mdir), [line]))
        cases.append((f"{mdir} bad", _bad_member_toml(mdir), [line]))
    cases.append(
        ("core utf16", _core_utf16_toml, _layout("core/pyproject.toml", bad)),
    )
    return cases


def plant_output_order_a(root: Path) -> None:
    """Plant multiple workspace violations to assert stable check order."""
    root_data = read_toml(root / "pyproject.toml")
    tool = root_data.setdefault("tool", {}).setdefault("uv", {})
    ws = tool.setdefault("workspace", {})
    ws["exclude"] = ["core"]
    root_data["project"]["name"] = "other"
    write_toml(root / "pyproject.toml", root_data)
    (root / "product/src/eii_product/__init__.py").unlink()
    cust = read_toml(root / "custodian/pyproject.toml")
    cust.get("tool", {}).pop("uv", None)
    write_toml(root / "custodian/pyproject.toml", cust)
    core = read_toml(root / "core/pyproject.toml")
    wf._extend(core, ["build-system", "requires"], "eii-product")
    write_toml(root / "core/pyproject.toml", core)
    lock = read_toml(root / "uv.lock")
    wf.drop_core_edge(lock, "eii-product")
    lock["requires-python"] = "/w/core"
    write_toml(root / "uv.lock", lock)


def plant_output_order_b(data: dict[str, Any]) -> None:
    """Mutate lock data to exercise lock-rule output ordering."""
    data.setdefault("package", []).reverse()
    man = data.setdefault("manifest", {})
    man["members"] = ["eii-core", "eii-custodian", "eii-product"]
    wf.add_dependency(data, "eii-custodian", "eii-product")
    wf.add_dependency(data, "eii-product", "eii-custodian")
    wf.drop_core_edge(data, "eii-custodian")
    wf.drop_core_edge(data, "eii-product")


def plant_registry_forbidden_edge(lock: dict[str, Any]) -> None:
    """Registry-sourced workspace row with a forbidden edge (judged by name)."""
    wf.add_dependency(lock, "eii-core", "eii-custodian")
    row = next(e for e in lock.get("package", []) if e.get("name") == "eii-core")
    row["source"] = {"registry": "https://pypi.org/simple"}


OUTPUT_ORDER_A = [
    "FAIL members: pyproject.toml: exclude is not empty",
    "FAIL root-clean: pyproject.toml: name is other expected eii-workspace",
    "FAIL package-layout: product/src/eii_product/__init__.py: missing",
    "FAIL workspace-source: custodian/pyproject.toml: "
    "eii-core is not taken from the workspace",
    "FAIL dependency-edge: core/pyproject.toml: "
    "build-system.requires names eii-product",
    "FAIL lock: uv.lock: edge eii-product -> eii-core is missing",
    "FAIL lock-paths: uv.lock: requires-python: absolute path or file URI",
]

OUTPUT_ORDER_B = [
    "FAIL lock: uv.lock: manifest.members are eii-core, eii-custodian, "
    "eii-product expected eii-core, eii-custodian, eii-gateway, eii-product, eii-workspace",
    "FAIL lock: uv.lock: edge eii-custodian -> eii-product is not allowed",
    "FAIL lock: uv.lock: edge eii-product -> eii-custodian is not allowed",
    "FAIL lock: uv.lock: edge eii-custodian -> eii-core is missing",
    "FAIL lock: uv.lock: edge eii-product -> eii-core is missing",
]

OUTPUT_ORDER_C = [
    "FAIL dependency-edge: core/pyproject.toml: "
    "project.dependencies names eii-custodian",
    "FAIL dependency-edge: core/pyproject.toml: project.dependencies names eii-product",
    "FAIL dependency-edge: core/pyproject.toml: "
    "build-system.requires names eii-custodian",
    "FAIL dependency-edge: custodian/pyproject.toml: "
    "project.dependencies names eii-product",
    "FAIL dependency-edge: product/pyproject.toml: "
    "project.dependencies names eii-custodian",
]


def plant_output_order_c(root: Path) -> None:
    """Plant forbidden dependency edges across member pyproject.toml files."""
    core = read_toml(root / "core/pyproject.toml")
    wf._extend(core, ["project", "dependencies"], "eii-product")
    wf._extend(core, ["project", "dependencies"], "eii-custodian")
    wf._extend(core, ["build-system", "requires"], "eii-custodian")
    write_toml(root / "core/pyproject.toml", core)
    cus = read_toml(root / "custodian/pyproject.toml")
    wf._extend(cus, ["project", "dependencies"], "eii-product")
    write_toml(root / "custodian/pyproject.toml", cus)
    prod = read_toml(root / "product/pyproject.toml")
    wf._extend(prod, ["project", "dependencies"], "eii-custodian")
    write_toml(root / "product/pyproject.toml", prod)


LOCK_MEMBER_CASES = [
    (
        "drop product",
        lambda lock: lock.setdefault("manifest", {}).update(
            {"members": ["eii-core", "eii-custodian", "eii-workspace"]},
        ),
        _lock_members("eii-core, eii-custodian, eii-workspace"),
    ),
    (
        "add gateway",
        lambda lock: lock.setdefault("manifest", {}).update(
            {
                "members": [
                    "eii-core",
                    "eii-custodian",
                    "eii-extra",
                    "eii-gateway",
                    "eii-product",
                    "eii-workspace",
                ],
            },
        ),
        _lock_members(
            "eii-core, eii-custodian, eii-extra, eii-gateway, eii-product, eii-workspace",
        ),
    ),
    (
        "members string",
        lambda lock: lock.setdefault("manifest", {}).update({"members": "eii-core"}),
        _lock_members("<none>"),
    ),
    (
        "Eii_Product",
        lambda lock: lock.setdefault("manifest", {}).update(
            {
                "members": [
                    "eii-core",
                    "eii-custodian",
                    "eii-gateway",
                    "Eii_Product",
                    "eii-workspace",
                ]
            },
        ),
        [],
    ),
]
