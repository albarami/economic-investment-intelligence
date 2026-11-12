"""Metadata guard tests for the uv workspace."""

from __future__ import annotations

import copy
import shutil
import tempfile
import tomllib
import unittest
from collections.abc import Callable
from pathlib import Path

import workspace_fields as fields
import workspace_guard as guard

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_EDGES: tuple[tuple[str, str], ...] = (
    ("core", "eii-custodian"),
    ("core", "eii-product"),
    ("custodian", "eii-product"),
    ("product", "eii-custodian"),
)

LOCK_EDGES: tuple[tuple[str, str], ...] = (
    ("eii-core", "eii-custodian"),
    ("eii-core", "eii-product"),
    ("eii-custodian", "eii-product"),
    ("eii-product", "eii-custodian"),
    ("eii-workspace", "eii-core"),
    ("eii-workspace", "eii-custodian"),
    ("eii-workspace", "eii-product"),
    ("eii-core", "eii-workspace"),
    ("eii-custodian", "eii-workspace"),
    ("eii-product", "eii-workspace"),
)

SPELLINGS: tuple[str, ...] = (
    "Eii_Custodian",
    "eii.custodian",
    "EII__CUSTODIAN",
    "eii-custodian[extra]>=0",
    'eii-custodian ; python_version >= "3.14"',
    "eii-custodian @ file:///x",
    " eii-custodian",
    "\teii-custodian",
    "eii-_custodian",
)

BAD_PATHS: tuple[str, ...] = (
    "/w/core",
    "C:\\w\\core",
    "d:/w/core",
    "\\\\host\\share\\core",
    "file:///w/core",
    "FILE:///w/core",
    "git+file:///w/core",
    " /w/core",
    "x=file:///w/core",
    "x file:///w/core",
)

PYPROJECTS: tuple[str, ...] = (
    "pyproject.toml",
    "core/pyproject.toml",
    "custodian/pyproject.toml",
    "product/pyproject.toml",
)

_PATH_ERR = "absolute path or file URI"


def _lock_path_lines(data: dict[str, object]) -> list[str]:
    prefix = "FAIL lock-paths"
    return [line for line in guard.check_lock_data(data) if line.startswith(prefix)]


ROUND_TRIP_SAMPLE: dict[str, object] = {
    "inline_tables": [{"a": 1}, {"b": 2}],
    "nested_inline": [[{"c": 3}]],
    "nested_value": {"outer": {"inner": 1}, "list": [1, {"x": True}]},
    "boolean": True,
    "integer": 7,
    "empty": {},
}


def make_fixture(tmp: Path) -> Path:
    """Copy the real workspace into a fresh folder under ``tmp``."""
    dest = tmp / f"fixture-{len(list(tmp.iterdir()))}"
    dest.mkdir()
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        src = REPO_ROOT / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    for member in fields.MEMBERS:
        shutil.copytree(
            REPO_ROOT / member,
            dest / member,
            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        )
    return dest


def mutated_lock(change: Callable[[dict[str, object]], None]) -> dict[str, object]:
    """Return a deep copy of the real lock after ``change``."""
    data = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    copy_data = copy.deepcopy(data)
    change(copy_data)
    return copy_data


def listing(root: Path) -> dict[str, bytes]:
    """Map relative paths under ``root`` to file bytes."""
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = path.read_bytes()
    return out


class WorkspaceMetadata(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def fresh(self) -> Path:
        return make_fixture(Path(self._tmp.name))

    def restore_members(self, root: Path) -> None:
        for member in fields.MEMBERS:
            src = REPO_ROOT / member / "pyproject.toml"
            shutil.copy2(src, root / member / "pyproject.toml")

    def check_cases(
        self,
        cases: list[tuple[str, Callable[..., None], list[str]]],
        on_lock: bool = False,
    ) -> int:
        count = 0
        for label, plant, expected in cases:
            with self.subTest(label=label):
                count += 1
                if on_lock:
                    data = mutated_lock(plant)  # type: ignore[arg-type]
                    actual = guard.check_lock_data(data)
                else:
                    root = self.fresh()
                    plant(root)  # type: ignore[misc]
                    actual = guard.check_workspace(root)
                self.assertEqual(actual, expected)
        return count

    def test_real_workspace_passes(self) -> None:
        self.assertEqual(guard.check_workspace(REPO_ROOT), [])

    def test_toml_writer_round_trips(self) -> None:
        for rel in PYPROJECTS:
            path = REPO_ROOT / rel
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(tomllib.loads(guard.dump_toml(data)), data)
        data = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
        self.assertEqual(tomllib.loads(guard.dump_toml(data)), data)
        self.assertEqual(
            tomllib.loads(guard.dump_toml(ROUND_TRIP_SAMPLE)),
            ROUND_TRIP_SAMPLE,
        )
        with self.assertRaises(TypeError):
            guard.dump_toml({"float": 0.5})

    def test_clean_fixture_passes(self) -> None:
        root = self.fresh()
        for rel in PYPROJECTS:
            path = root / rel
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            path.write_text(guard.dump_toml(data), encoding="utf-8")
        self.assertEqual(guard.check_workspace(root), [])

    def test_forbidden_edge_in_every_place(self) -> None:
        count = 0
        root = self.fresh()
        for mdir, target in FORBIDDEN_EDGES:
            for i, (label, _fn) in enumerate(fields.PYPROJECT_PLANTS):
                rep = sum(1 for j in range(i) if fields.PYPROJECT_PLANTS[j][0] == label)
                with self.subTest(member=mdir, field=label, rep=rep):
                    count += 1
                    self.restore_members(root)
                    path = root / mdir / "pyproject.toml"
                    data = tomllib.loads(path.read_text(encoding="utf-8"))
                    fields.apply_pyproject_plant(data, label, target, rep=rep)
                    path.write_text(guard.dump_toml(data), encoding="utf-8")
                    expected = [
                        f"FAIL dependency-edge: {mdir}/pyproject.toml: {label} names "
                        f"{guard.normalise(target)}",
                    ]
                    self.assertEqual(guard.check_workspace(root), expected)
        self.assertEqual(count, fields.COUNT_EVERY_PLACE)

    def test_forbidden_edge_spelling_variants(self) -> None:
        root = self.fresh()
        count = 0
        for spelling in SPELLINGS:
            with self.subTest(spelling=spelling):
                count += 1
                self.restore_members(root)
                data = fields.read_toml(root / "product/pyproject.toml")
                deps = data.setdefault("project", {}).setdefault("dependencies", [])
                if not isinstance(deps, list):
                    deps = []
                deps.append(spelling)
                data["project"]["dependencies"] = deps
                (root / "product/pyproject.toml").write_text(
                    guard.dump_toml(data),
                    encoding="utf-8",
                )
                expected = [
                    "FAIL dependency-edge: product/pyproject.toml: "
                    "project.dependencies names eii-custodian",
                ]
                self.assertEqual(guard.check_workspace(root), expected)
        with self.subTest(spelling="sources key"):
            count += 1
            self.restore_members(root)
            data = fields.read_toml(root / "product/pyproject.toml")
            uv = data.setdefault("tool", {}).setdefault("uv", {})
            src = uv.setdefault("sources", {})
            if isinstance(src, dict):
                src["Eii_Custodian"] = {"workspace": True}
            (root / "product/pyproject.toml").write_text(
                guard.dump_toml(data),
                encoding="utf-8",
            )
            expected = [
                "FAIL dependency-edge: product/pyproject.toml: "
                "tool.uv.sources names eii-custodian",
            ]
            self.assertEqual(guard.check_workspace(root), expected)
        self.assertEqual(count, fields.COUNT_SPELLINGS)

    def test_third_party_names_are_not_judged(self) -> None:
        root = self.fresh()
        for mdir in fields.MEMBERS:
            path = root / mdir / "pyproject.toml"
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            fields.adds("requests")(data)
            path.write_text(guard.dump_toml(data), encoding="utf-8")
        root_data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        fields._put(root_data, "dependency-groups", {"dev": ["requests"]})
        fields.write_toml(root / "pyproject.toml", root_data)
        self.assertEqual(guard.check_workspace(root), [])

    def test_root_naming_a_member_fails(self) -> None:
        n = self.check_cases(list(fields.ROOT_NAMING_CASES))
        self.assertEqual(n, 6)

    def test_root_name_and_package_flag_fail(self) -> None:
        n = self.check_cases(list(fields.ROOT_FLAG_CASES))
        self.assertEqual(n, 4)

    def test_missing_workspace_source_fails(self) -> None:
        n = self.check_cases(list(fields.SOURCE_CASES))
        self.assertEqual(n, 10)

    def test_member_list_wrong_fails(self) -> None:
        n = self.check_cases(list(fields.MEMBER_LIST_CASES))
        self.assertEqual(n, 8)

    def test_layout_fails(self) -> None:
        n = self.check_cases(list(fields.LAYOUT_CASES))
        self.assertEqual(n, 7)

    def test_missing_and_unparsable_pyproject_fail(self) -> None:
        n = self.check_cases(fields.invalid_pyproject_cases())  # type: ignore[arg-type]
        self.assertEqual(n, fields.COUNT_PYPROJECT_CASES)

    def test_forbidden_edge_in_lock(self) -> None:
        count = 0
        for source, target in LOCK_EDGES:
            for rep in range(len(fields.PACKAGE_LOCK_PLANTS)):
                with self.subTest(source=source, target=target, rep=rep):
                    count += 1
                    data = mutated_lock(
                        lambda lock, s=source, t=target, r=rep: (
                            fields.apply_package_lock_plant(lock, r, s, t)
                        ),
                    )
                    expected = [
                        f"FAIL lock: uv.lock: edge {source} -> {target} is not allowed",
                    ]
                    self.assertEqual(guard.check_lock_data(data), expected)
        self.assertEqual(count, fields.COUNT_LOCK_EDGES)

    def test_expected_edge_missing_in_lock(self) -> None:
        for name in ("eii-custodian", "eii-product"):
            with self.subTest(name=name):
                data = mutated_lock(lambda lock, n=name: fields.drop_core_edge(lock, n))
                expected = [f"FAIL lock: uv.lock: edge {name} -> eii-core is missing"]
                self.assertEqual(guard.check_lock_data(data), expected)

    def test_package_missing_in_lock(self) -> None:
        expected = ["FAIL lock: uv.lock: package eii-product is not listed"]
        n = 0
        data = mutated_lock(fields.drop_product)
        self.assertEqual(guard.check_lock_data(data), expected)
        n += 1
        data = mutated_lock(
            lambda lock: (
                fields.drop_product(lock),
                lock.setdefault("package", []).append("eii-product"),
            ),
        )
        self.assertEqual(guard.check_lock_data(data), expected)
        n += 1
        data = mutated_lock(
            lambda lock: next(
                e for e in lock.get("package", []) if e.get("name") == "eii-product"
            ).__setitem__("name", "Eii_Product"),
        )
        self.assertEqual(guard.check_lock_data(data), [])
        n += 1
        data = mutated_lock(
            lambda lock: lock.setdefault("package", []).append({"name": 1}),
        )
        self.assertEqual(guard.check_lock_data(data), [])
        n += 1
        self.assertEqual(n, 4)

    def test_lock_members_list_wrong_fails(self) -> None:
        n = self.check_cases(list(fields.LOCK_MEMBER_CASES), on_lock=True)
        self.assertEqual(n, 4)

    def test_member_name_in_workspace_wide_lock_field(self) -> None:
        count = 0
        for field, rep in fields.WIDE_LOCK_PLANTS:
            for target in fields.NAMES:
                with self.subTest(field=field, rep=rep, target=target):
                    count += 1
                    data = mutated_lock(
                        lambda lock, f=field, r=rep, t=target: (
                            fields.apply_wide_lock_plant(lock, f, t, r)
                        ),
                    )
                    expected = [f"FAIL lock: uv.lock: {field} names {target}"]
                    self.assertEqual(guard.check_lock_data(data), expected)
        self.assertEqual(count, fields.COUNT_WIDE)

    def test_absolute_path_in_lock_fails(self) -> None:
        count = 0
        base = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
        packages = base.get("package", [])
        idx = next(i for i, e in enumerate(packages) if e.get("name") == "eii-core")
        for value in BAD_PATHS:
            with self.subTest(where="source", value=value):
                count += 1
                def plant_src(lock: dict[str, object], v: str = value) -> None:
                    pkg = lock["package"]
                    row = next(e for e in pkg if e.get("name") == "eii-core")
                    row["source"] = {"editable": v}

                data = mutated_lock(plant_src)
                path_key = f"package[{idx}].source.editable"
                expected = [f"FAIL lock-paths: uv.lock: {path_key}: {_PATH_ERR}"]
                self.assertEqual(_lock_path_lines(data), expected)
            with self.subTest(where="requires-python", value=value):
                count += 1
                data = mutated_lock(
                    lambda lock, v=value: lock.__setitem__("requires-python", v),
                )
                expected = [f"FAIL lock-paths: uv.lock: requires-python: {_PATH_ERR}"]
                self.assertEqual(_lock_path_lines(data), expected)
        self.assertEqual(count, fields.COUNT_PATHS)

    def test_missing_and_unparsable_lock_fail(self) -> None:
        cases = [
            ("deleted", lambda r: (r / "uv.lock").unlink(), [
                "FAIL lock: uv.lock: missing or not valid TOML",
            ]),
            ("bad", lambda r: (r / "uv.lock").write_text(fields.NOT_VALID), [
                "FAIL lock: uv.lock: missing or not valid TOML",
            ]),
            ("utf16", lambda r: (r / "uv.lock").write_bytes(b"\\xff\\xfe"), [
                "FAIL lock: uv.lock: missing or not valid TOML",
            ]),
        ]
        n = self.check_cases(cases)  # type: ignore[arg-type]
        none_line = ["FAIL lock: uv.lock: missing or not valid TOML"]
        parsed_none = guard.check_lock_data(None)  # type: ignore[arg-type]
        self.assertEqual(parsed_none, none_line)
        self.assertEqual(n + 1, 4)

    def test_helper_changes_nothing(self) -> None:
        root = self.fresh()
        before = listing(root)
        guard.check_workspace(root)
        self.assertEqual(listing(root), before)

    def test_lock_ignores_self_and_third_party_edges(self) -> None:
        data = mutated_lock(
            lambda lock: (
                fields.add_dependency(lock, "eii-core", "eii-core"),
                fields.add_dependency(lock, "eii-custodian", "eii-custodian"),
            ),
        )
        self.assertEqual(
            [l for l in guard.check_lock_data(data) if "edge" in l],
            [],
        )
        data = mutated_lock(
            lambda lock: lock.setdefault("package", []).append({
                "name": "requests",
                "version": "0.0.0",
                "source": {"registry": "registry"},
                "dependencies": [{"name": "eii-core"}],
            }),
        )
        self.assertEqual(
            [l for l in guard.check_lock_data(data) if "edge" in l and "requests" in l],
            [],
        )
        data = mutated_lock(fields.plant_registry_forbidden_edge)
        fail_edge = "FAIL lock: uv.lock: edge"
        has_edge = [l for l in guard.check_lock_data(data) if l.startswith(fail_edge)]
        self.assertEqual(has_edge, [])

    def test_output_order(self) -> None:
        root = self.fresh()
        fields.plant_output_order_a(root)
        self.assertEqual(guard.check_workspace(root), fields.OUTPUT_ORDER_A)

        data = mutated_lock(fields.plant_output_order_b)
        self.assertEqual(guard.check_lock_data(data), fields.OUTPUT_ORDER_B)

        root = self.fresh()
        fields.plant_output_order_c(root)
        self.assertEqual(guard.check_workspace(root), fields.OUTPUT_ORDER_C)


if __name__ == "__main__":
    unittest.main()
