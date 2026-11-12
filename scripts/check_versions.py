"""Fail when a manifest, lock or toolchain leaves the pin record.

Judged places (closed table; nothing else is claimed):

| Ecosystem | Place | Read as |
|---|---|---|
| Python | ``project.dependencies`` of the root and each member | list of requirement strings |
| Python | ``project.optional-dependencies.<group>`` | lists of requirement strings |
| Python | ``dependency-groups.<group>`` | lists; string items are requirements, table items (``{ include-group = ... }``) are skipped |
| npm | ``web/package.json`` ``dependencies``, ``devDependencies``, ``optionalDependencies``, ``peerDependencies`` | name to specifier |
| Python lock | every ``package`` entry of ``uv.lock`` with a name that is a component | name, version, source |
| npm lock | every key of ``packages`` in ``web/package-lock.json`` that contains ``node_modules/``; the name is the text after the last ``node_modules/`` | version |

Not judged, with the reason: names of the workspace members (``eii-workspace``, ``eii-core``, ``eii-custodian``, ``eii-product`` are the project's own packages, not pins); ``build-system.requires`` except the ``uv_build`` item of rule 8 (a build requirement, bound by S0-T02's decision); ``tool.uv.sources``, ``constraint-dependencies``, ``override-dependencies``, ``dev-dependencies`` and the other ``[tool.uv]`` keys (a version forced through them still appears in the lock, which rules 12 to 14 judge; a package named only there and absent from the record is not caught; S0-T02's guard owns the closed table of uv fields); ``overrides``, ``scripts``, ``engines.npm`` (unused; S0-T03 writes ``engines.node`` only) and every other ``package.json`` field except ``packageManager`` and ``devEngines``, which rule 7 refuses by presence (S0-T03's check judges ``overrides`` strings); ``lockfileVersion`` of the npm lock and ``revision`` of ``uv.lock``; which registry a lock names (rule 12 requires a registry source, not the index URL; the ``resolved`` and ``integrity`` fields of the npm lock are not read; a changed index setting still satisfies the check, OI-54); transitive packages that have no component (they are the lock's business; a component for one makes its versions binding); the upper bound of ``requires-python``; the contents of ``docs/``; a file that git ignores and does not track (by design, AGENTS.md rule 13: the candidate list never holds it); the files inside a nested git repository (git lists the folder, not its files); a tracked file that the work tree no longer holds (rule 17 skips it).
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

import versions_inputs
import versions_record
import versions_tools

RULE_ORDER = (
    "input",
    "record-row",
    "record-label",
    "record-cite",
    "record-duplicate",
    "version-file",
    "version-field",
    "build-backend",
    "manifest-form",
    "manifest-unrecorded",
    "manifest-version",
    "lock-source",
    "lock-entry",
    "lock-version",
    "state",
    "toolchain",
    "unscanned",
)
_JSON_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)
_FORM_RE = re.compile(
    r"[A-Za-z0-9._-]+(?:\[[^]]+\])?\s*==\s*\d+(?:\.\d+){1,3}",
    re.ASCII,
)
_NAME_RE = re.compile(r"[A-Za-z0-9._-]+", re.ASCII)
_NPM_RE = re.compile(r"\d+\.\d+\.\d+", re.ASCII)
Failure = tuple[str, str, str]


def run_checks(
    root: Path,
    *,
    interpreter: tuple[int, int, int] | None = None,
    environ: Mapping[str, str] | None = None,
    probe_timeout: float = versions_tools.PROBE_TIMEOUT,
) -> tuple[list[str], int]:
    """Return the failure lines, the summary and the number of record rows."""
    running = sys.version_info[:3] if interpreter is None else interpreter
    parent = os.environ if environ is None else environ
    components, failures, count = versions_record.load_record(root)
    if failures:
        return _render(failures, count)
    texts, docs, flags, members = _read_tree(root, failures)
    _version_files(components, texts, failures)
    _version_fields(components, docs, flags, failures)
    _build_backend(components, docs, failures)
    names = _workspace_names(docs)
    named = _manifests(components, docs, names, failures)
    _locks(components, docs, flags, named, failures)
    _state(components, docs, flags, named, failures)
    failures.extend(
        versions_tools.check_toolchain(components, running, parent, root, probe_timeout)
    )
    _unscanned(root, parent, flags, members, failures)
    return _render(failures, count)


def main(
    argv: Sequence[str],
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Run the check from ``argv`` and return the process status."""
    stdout = sys.stdout if out is None else out
    stderr = sys.stderr if err is None else err
    root, detail = _arguments(argv)
    if detail is not None or root is None:
        print(f"check_versions: usage error: {detail}", file=stderr)
        return 2
    try:
        lines, _count = run_checks(root, environ=environ)
    except Exception as exc:
        message = str(exc).splitlines()
        first = message[0] if message else ""
        print(
            f"FAIL internal-error: check_versions: {type(exc).__name__}: {first}",
            file=stdout,
        )
        return 1
    print("\n".join(lines), file=stdout)
    if lines and lines[-1].endswith(" OK"):
        return 0
    return 1


def _arguments(argv: Sequence[str]) -> tuple[Path | None, str | None]:
    seen = False
    chosen: str | None = None
    index = 0
    while index < len(argv):
        word = argv[index]
        if word != "--root":
            return None, f'unknown argument "{word}"'
        if seen:
            return None, "--root given twice"
        if index + 1 >= len(argv):
            return None, "--root needs a value"
        seen = True
        chosen = argv[index + 1]
        index += 2
    root = Path(__file__).resolve().parent.parent if chosen is None else Path(chosen)
    if not root.is_dir():
        return None, "root is not a directory"
    return root, None


def _render(failures: list[Failure], count: int) -> tuple[list[str], int]:
    order = {name: index for index, name in enumerate(RULE_ORDER)}
    failures.sort(key=lambda item: order[item[0]])
    lines = [f"FAIL {rule}: {where}: {detail}" for rule, where, detail in failures]
    if failures:
        lines.append(f"checked {count} components: {len(failures)} failure(s)")
    else:
        lines.append(f"checked {count} components: OK")
    return lines, count


def _show(text: str) -> str:
    return text.encode("unicode_escape").decode("ascii")


def _prefix(pin: str) -> str:
    if pin.endswith(".x"):
        return pin[: -len(".x")]
    return pin


def _read_tree(
    root: Path, failures: list[Failure]
) -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bool], list[str]]:
    texts: dict[str, str] = {}
    docs: dict[str, dict[str, object]] = {}
    members_found: list[str] = []
    flags = {
        "root": False,
        "members": False,
        "member_failed": False,
        "lock": False,
        "web": False,
        "npm_lock": False,
    }
    for rel in (".python-version", ".nvmrc"):
        parsed, detail = versions_inputs.read_input(root, rel, "text")
        if detail is not None:
            failures.append(("input", rel, detail))
        elif isinstance(parsed, str):
            texts[rel] = parsed
    root_doc, root_detail = versions_inputs.read_input(root, "pyproject.toml", "toml")
    if root_detail is not None or not isinstance(root_doc, dict):
        failures.append(("input", "pyproject.toml", root_detail or "not valid TOML"))
    else:
        shapes = versions_inputs.shape_pyproject(root_doc)
        for detail in shapes:
            failures.append(("input", "pyproject.toml", detail))
        flags["root"] = not shapes
        members, members_detail = versions_inputs.members_of(root_doc)
        if members_detail is not None:
            failures.append(("input", "pyproject.toml", members_detail))
        elif members is not None:
            flags["members"] = True
            members_found = members
            if flags["root"]:
                docs["pyproject.toml"] = root_doc
            for member in members:
                rel = f"{member}/pyproject.toml"
                parsed, detail = versions_inputs.read_input(root, rel, "toml")
                if detail is not None or not isinstance(parsed, dict):
                    failures.append(("input", rel, detail or "not valid TOML"))
                    flags["member_failed"] = True
                    continue
                member_shapes = versions_inputs.shape_pyproject(parsed)
                if member_shapes:
                    for item in member_shapes:
                        failures.append(("input", rel, item))
                    flags["member_failed"] = True
                    continue
                docs[rel] = parsed
    _read_named(
        root,
        "uv.lock",
        "toml",
        versions_inputs.shape_uv_lock,
        "lock",
        docs,
        flags,
        failures,
    )
    _read_named(
        root,
        "web/package.json",
        "json",
        versions_inputs.shape_package_json,
        "web",
        docs,
        flags,
        failures,
    )
    _read_named(
        root,
        "web/package-lock.json",
        "json",
        versions_inputs.shape_package_lock,
        "npm_lock",
        docs,
        flags,
        failures,
    )
    return texts, docs, flags, members_found


def _read_named(
    root: Path,
    rel: str,
    kind: str,
    shape: object,
    flag: str,
    docs: dict[str, dict[str, object]],
    flags: dict[str, bool],
    failures: list[Failure],
) -> None:
    parsed, detail = versions_inputs.read_input(root, rel, kind)
    if detail is not None or not isinstance(parsed, dict):
        failures.append(("input", rel, detail or "not valid TOML"))
        return
    if not callable(shape):
        return
    shapes = shape(parsed)
    if not isinstance(shapes, list):
        return
    if shapes:
        for item in shapes:
            if isinstance(item, str):
                failures.append(("input", rel, item))
        return
    docs[rel] = parsed
    flags[flag] = True


def _version_files(
    components: Sequence[versions_record.Component],
    texts: dict[str, str],
    failures: list[Failure],
) -> None:
    python = _toolchain(components, "python")
    node = _toolchain(components, "node")
    if python is not None and ".python-version" in texts:
        _hold(
            failures, ".python-version", texts[".python-version"], _prefix(python.pin)
        )
    if node is not None and ".nvmrc" in texts:
        _hold(failures, ".nvmrc", texts[".nvmrc"], _prefix(node.pin))


def _hold(failures: list[Failure], rel: str, text: str, prefix: str) -> None:
    if text != prefix and text != prefix + "\n":
        failures.append(("version-file", rel, f"holds {text!r} expected {prefix!r}"))


def _version_fields(
    components: Sequence[versions_record.Component],
    docs: dict[str, dict[str, object]],
    flags: dict[str, bool],
    failures: list[Failure],
) -> None:
    python = _toolchain(components, "python")
    uv = _toolchain(components, "uv")
    node = _toolchain(components, "node")
    if python is not None:
        expected = ">=" + _prefix(python.pin)
        for rel, doc in _python_docs(docs):
            _field(
                failures,
                rel,
                doc,
                ("project", "requires-python"),
                "project.requires-python",
                expected,
            )
    if uv is not None and flags["root"] and "pyproject.toml" in docs:
        _field(
            failures,
            "pyproject.toml",
            docs["pyproject.toml"],
            ("tool", "uv", "required-version"),
            "tool.uv.required-version",
            "==" + uv.pin,
        )
    if (
        node is not None
        and node.floor is not None
        and flags["web"]
        and "web/package.json" in docs
    ):
        major = int(node.pin.split(".", 1)[0])
        expected = f">={node.floor} <{major + 1}"
        web = docs["web/package.json"]
        if "packageManager" in web:
            failures.append(
                (
                    "version-field",
                    "web/package.json",
                    "packageManager is present expected absent",
                )
            )
        if "devEngines" in web:
            failures.append(
                (
                    "version-field",
                    "web/package.json",
                    "devEngines is present expected absent",
                )
            )
        _field(
            failures,
            "web/package.json",
            web,
            ("engines", "node"),
            "engines.node",
            expected,
        )


def _field(
    failures: list[Failure],
    rel: str,
    doc: dict[str, object],
    path: tuple[str, ...],
    label: str,
    expected: str,
) -> None:
    current: object = doc
    for key in path:
        if not isinstance(current, dict) or key not in current:
            failures.append(("version-field", rel, f"{label} is missing"))
            return
        current = current[key]
    if current != expected:
        failures.append(
            ("version-field", rel, f"{label} is {current!r} expected {expected!r}")
        )


def _build_backend(
    components: Sequence[versions_record.Component],
    docs: dict[str, dict[str, object]],
    failures: list[Failure],
) -> None:
    uv = _toolchain(components, "uv")
    if uv is None:
        return
    major, minor, _micro = uv.pin.split(".")
    expected = [f"uv_build>={uv.pin},<{major}.{int(minor) + 1}"]
    for rel, doc in _python_docs(docs):
        if rel == "pyproject.toml":
            continue
        build = doc.get("build-system")
        requires = build.get("requires") if isinstance(build, dict) else None
        if not isinstance(build, dict) or "requires" not in build:
            failures.append(("build-backend", rel, "build-system.requires is missing"))
        elif requires != expected:
            failures.append(
                (
                    "build-backend",
                    rel,
                    f"build-system.requires is {requires!r} expected {expected!r}",
                )
            )


def _python_docs(
    docs: dict[str, dict[str, object]],
) -> list[tuple[str, dict[str, object]]]:
    found: list[tuple[str, dict[str, object]]] = []
    if "pyproject.toml" in docs:
        found.append(("pyproject.toml", docs["pyproject.toml"]))
    for rel, doc in docs.items():
        if rel not in {
            "pyproject.toml",
            "uv.lock",
            "web/package.json",
            "web/package-lock.json",
        }:
            found.append((rel, doc))
    return found


def _workspace_names(docs: dict[str, dict[str, object]]) -> set[str]:
    names: set[str] = set()
    for _rel, doc in _python_docs(docs):
        project = doc.get("project")
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            names.add(versions_record.normalise_python_name(str(project["name"])))
    return names


def _manifests(
    components: Sequence[versions_record.Component],
    docs: dict[str, dict[str, object]],
    workspace: set[str],
    failures: list[Failure],
) -> dict[str, list[str]]:
    named: dict[str, list[str]] = {"python": [], "npm": []}
    for rel, doc in _python_docs(docs):
        for field, requirement in _python_requirements(doc):
            head = _NAME_RE.match(requirement)
            if (
                head is not None
                and versions_record.normalise_python_name(head.group(0)) in workspace
            ):
                continue
            parsed = _parse_requirement(requirement)
            if parsed is None:
                failures.append(
                    (
                        "manifest-form",
                        rel,
                        f"{field}: {_show(requirement)}: not name==exact version",
                    )
                )
                continue
            name, version = parsed
            folded = versions_record.normalise_python_name(name)
            component = _kind(components, "python", folded)
            if component is None:
                failures.append(
                    (
                        "manifest-unrecorded",
                        rel,
                        f"{field}: {name}: no component in pins.toml",
                    )
                )
                continue
            if folded not in named["python"]:
                named["python"].append(folded)
            if not versions_record.allowed_by(component, version):
                failures.append(
                    (
                        "manifest-version",
                        rel,
                        f"{field}: {_show(requirement)}: neither pin {component.pin} "
                        f"nor retreat {component.retreat}",
                    )
                )
    web = docs.get("web/package.json")
    if isinstance(web, dict):
        for section in _JSON_SECTIONS:
            block = web.get(section)
            if not isinstance(block, dict):
                continue
            for name, spec in block.items():
                if not isinstance(name, str) or not isinstance(spec, str):
                    continue
                component = _kind(components, "npm", name)
                if component is None:
                    failures.append(
                        (
                            "manifest-unrecorded",
                            "web/package.json",
                            f"{section}.{_show(name)}: no component in pins.toml",
                        )
                    )
                    continue
                if name not in named["npm"]:
                    named["npm"].append(name)
                if _NPM_RE.fullmatch(spec) is None or not versions_record.allowed_by(
                    component, spec
                ):
                    failures.append(
                        (
                            "manifest-version",
                            "web/package.json",
                            f"{section}.{name}: {_show(spec)}: neither pin {component.pin} "
                            f"nor retreat {component.retreat}",
                        )
                    )
    return named


def _python_requirements(doc: dict[str, object]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    project = doc.get("project")
    if isinstance(project, dict):
        dependencies = project.get("dependencies")
        if isinstance(dependencies, list):
            for item in dependencies:
                if isinstance(item, str):
                    found.append(("project.dependencies", item))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group, items in optional.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str):
                            found.append(
                                (f"project.optional-dependencies.{group}", item)
                            )
    groups = doc.get("dependency-groups")
    if isinstance(groups, dict):
        for group, items in groups.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        found.append((f"dependency-groups.{group}", item))
    return found


def _parse_requirement(requirement: str) -> tuple[str, str] | None:
    if _FORM_RE.fullmatch(requirement) is None:
        return None
    name_part, version = re.split(r"\s*==\s*", requirement, maxsplit=1)
    return name_part.split("[", 1)[0], version


def _locks(
    components: Sequence[versions_record.Component],
    docs: dict[str, dict[str, object]],
    flags: dict[str, bool],
    named: dict[str, list[str]],
    failures: list[Failure],
) -> None:
    python_ready = (
        flags["root"]
        and flags["members"]
        and not flags["member_failed"]
        and flags["lock"]
    )
    if python_ready and "uv.lock" in docs:
        packages = docs["uv.lock"].get("package")
        entries = packages if isinstance(packages, list) else []
        locked: set[str] = set()
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            raw_name = str(item["name"])
            folded = versions_record.normalise_python_name(raw_name)
            component = _kind(components, "python", folded)
            source = item.get("source")
            registry = isinstance(source, dict) and "registry" in source
            version = item.get("version")
            if component is not None and isinstance(version, str) and not registry:
                failures.append(
                    (
                        "lock-source",
                        "uv.lock",
                        f"{_show(raw_name)} {_show(version)}: not locked from a registry",
                    )
                )
            if component is not None and registry:
                locked.add(folded)
            if component is None:
                continue
            if not isinstance(version, str):
                failures.append(
                    (
                        "lock-version",
                        "uv.lock",
                        f"{_show(raw_name)}: entry has no version",
                    )
                )
            elif not versions_record.allowed_by(component, version):
                failures.append(
                    (
                        "lock-version",
                        "uv.lock",
                        f"{_show(raw_name)} {_show(version)}: neither pin {component.pin} "
                        f"nor retreat {component.retreat}",
                    )
                )
        for folded in named["python"]:
            if folded not in locked:
                display = _display(components, "python", folded)
                failures.append(
                    (
                        "lock-entry",
                        "uv.lock",
                        f"{display}: named by a manifest, no package entry",
                    )
                )
    if flags["web"] and flags["npm_lock"] and "web/package-lock.json" in docs:
        packages = docs["web/package-lock.json"].get("packages")
        if isinstance(packages, dict):
            top = {name for name in named["npm"] if f"node_modules/{name}" in packages}
            for name in named["npm"]:
                if name not in top:
                    failures.append(
                        (
                            "lock-entry",
                            "web/package-lock.json",
                            f"{name}: named by web/package.json, no top-level entry",
                        )
                    )
            for key, value in packages.items():
                if (
                    not isinstance(key, str)
                    or "node_modules/" not in key
                    or not isinstance(value, dict)
                ):
                    continue
                name = key.rsplit("node_modules/", 1)[1]
                component = _kind(components, "npm", name)
                if component is None:
                    continue
                version = value.get("version")
                if not isinstance(version, str):
                    failures.append(
                        (
                            "lock-version",
                            "web/package-lock.json",
                            f"{_show(key)}: entry has no version",
                        )
                    )
                elif not versions_record.allowed_by(component, version):
                    failures.append(
                        (
                            "lock-version",
                            "web/package-lock.json",
                            f"{_show(key)}: {_show(version)}: neither pin {component.pin} "
                            f"nor retreat {component.retreat}",
                        )
                    )


def _state(
    components: Sequence[versions_record.Component],
    docs: dict[str, dict[str, object]],
    flags: dict[str, bool],
    named: dict[str, list[str]],
    failures: list[Failure],
) -> None:
    python_ready = (
        flags["root"]
        and flags["members"]
        and not flags["member_failed"]
        and flags["lock"]
    )
    locked_python: set[str] = set()
    if python_ready and "uv.lock" in docs:
        packages = docs["uv.lock"].get("package")
        if isinstance(packages, list):
            for item in packages:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    locked_python.add(
                        versions_record.normalise_python_name(str(item["name"]))
                    )
    if python_ready:
        for component in components:
            if component.kind != "python":
                continue
            folded = versions_record.normalise_python_name(component.name)
            _state_line(
                failures, component, folded in named["python"], folded in locked_python
            )
    if flags["web"] and flags["npm_lock"] and "web/package-lock.json" in docs:
        packages = docs["web/package-lock.json"].get("packages")
        locked_npm: set[str] = set()
        if isinstance(packages, dict):
            for key in packages:
                if isinstance(key, str) and "node_modules/" in key:
                    locked_npm.add(key.rsplit("node_modules/", 1)[1])
        for component in components:
            if component.kind != "npm":
                continue
            _state_line(
                failures,
                component,
                component.name in named["npm"],
                component.name in locked_npm,
            )


def _state_line(
    failures: list[Failure],
    component: versions_record.Component,
    named: bool,
    locked: bool,
) -> None:
    label = versions_record.describe(component)
    if component.state == "installed" and not named and not locked:
        failures.append(
            (
                "state",
                "pins.toml",
                f"{label}: installed but named by no manifest or lock",
            )
        )
    if component.state == "recorded" and named:
        failures.append(
            ("state", "pins.toml", f"{label}: recorded but a manifest names it")
        )


def _unscanned(
    root: Path,
    environ: Mapping[str, str],
    flags: dict[str, bool],
    members: Sequence[str],
    failures: list[Failure],
) -> None:
    candidates, detail = versions_inputs.list_candidates(root, environ)
    if detail is not None or candidates is None:
        failures.append(("input", "git", detail or "not found on PATH"))
        return
    if not flags["members"]:
        return
    judged = {
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".nvmrc",
        "web/package.json",
        "web/package-lock.json",
    }
    for member in members:
        judged.add(f"{member}/pyproject.toml")
    failures.extend(versions_inputs.find_unscanned(root, candidates, judged))


def _toolchain(
    components: Sequence[versions_record.Component], name: str
) -> versions_record.Component | None:
    for component in components:
        if component.kind == "toolchain" and component.name == name:
            return component
    return None


def _kind(
    components: Sequence[versions_record.Component], kind: str, name: str
) -> versions_record.Component | None:
    for component in components:
        if component.kind != kind:
            continue
        current = (
            component.name
            if kind == "npm"
            else versions_record.normalise_python_name(component.name)
        )
        if current == name:
            return component
    return None


def _display(
    components: Sequence[versions_record.Component], kind: str, folded: str
) -> str:
    for component in components:
        if (
            component.kind == kind
            and versions_record.normalise_python_name(component.name) == folded
        ):
            return component.name
    return folded


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
