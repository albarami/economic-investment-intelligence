"""Bounded, fail-closed manifest and output transport for the hosted pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

MODULE = "custodian/src/eii_custodian/publicdata/places_fsq/policy.py"
CAP = 128 * 1024
SHARDS = 4
VERSION = "3.8.1"
STATUSES = ("killed", "survived", "timeout", "not_covered", "infrastructure_failure")
IMPLEMENTATION = (
    "scripts/mutation.py",
    "scripts/mutation_pilot.py",
    ".github/workflows/mutation-pilot.yml",
)


class Refusal(ValueError):
    """A fixed refusal name, safe for evidence and logs."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: Any) -> str:
    result = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(result.encode()) > CAP:
        raise Refusal("payload-overflow")
    return result


def decode(value: str) -> Any:
    if not value:
        raise Refusal("missing-shard")
    if len(value.encode()) > CAP:
        raise Refusal("payload-overflow")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise Refusal("duplicate-property")
            result[key] = item
        return result

    try:
        return json.loads(value, object_pairs_hook=pairs)
    except json.JSONDecodeError as exc:
        raise Refusal("malformed-json") from exc


def status(code: Any) -> str:
    if type(code) is not int:
        return "infrastructure_failure"
    return {
        0: "survived",
        1: "killed",
        3: "killed",
        37: "killed",
        5: "not_covered",
        33: "not_covered",
        36: "timeout",
        -24: "timeout",
        24: "timeout",
        152: "timeout",
        255: "timeout",
    }.get(code, "infrastructure_failure")


def validate_inputs(module: str, ref: str, workflow_ref: str) -> None:
    if module != MODULE:
        raise Refusal("wrong-module")
    if re.fullmatch(r"[0-9a-f]{40}", ref) is None:
        raise Refusal("wrong-ref")
    if workflow_ref != "refs/heads/main":
        raise Refusal("workflow-ref")


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise Refusal("git-verification-failed")
    return result.stdout


def validate_ref(root: Path, module: str, ref: str, workflow_ref: str) -> None:
    validate_inputs(module, ref, workflow_ref)
    if git(root, "cat-file", "-t", ref).strip() != b"commit":
        raise Refusal("not-commit")
    git(root, "merge-base", "--is-ancestor", ref, "origin/main")
    for name in IMPLEMENTATION:
        if git(root, "show", ref + ":" + name) != (root / name).read_bytes():
            raise Refusal("unreviewed-implementation")


def manifest(context: dict[str, Any], mutants: list[dict[str, Any]]) -> dict[str, Any]:
    if (
        set(context) - {"commit", "module", "hashes", "synthetic"}
        or not {"commit", "module", "hashes"} <= context.keys()
    ):
        raise Refusal("context-schema")
    validate_inputs(context["module"], context["commit"], "refs/heads/main")
    allowed_hashes = {
        MODULE,
        "uv.lock",
        "scripts/mutation.py",
        "scripts/mutation_pilot.py",
        "scripts/mutation_explained.toml",
        "source",
    }
    if (
        not isinstance(context["hashes"], dict)
        or context["hashes"].keys() - allowed_hashes
    ):
        raise Refusal("context-hashes")
    if any(
        not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None
        for v in context["hashes"].values()
    ):
        raise Refusal("context-hashes")
    if "synthetic" in context and context["synthetic"] is not True:
        raise Refusal("context-synthetic")
    names = [r["name"] for r in mutants]
    if not names or len(names) != len(set(names)):
        raise Refusal("duplicate-or-empty-universe")
    for row in mutants:
        if (
            set(row) != {"name", "diff_sha256"}
            or re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.]*__mutmut_[0-9]+", row["name"])
            is None
        ):
            raise Refusal("invalid-mutant-name")
        if re.fullmatch(r"[0-9a-f]{64}", row["diff_sha256"]) is None:
            raise Refusal("diff-hash")
    result = dict(
        version=VERSION,
        context=context,
        mutants=sorted(mutants, key=lambda r: r["name"]),
    )
    result["sha256"] = digest(encode(result).encode())
    encode(result)
    return result


def verify_manifest(value: dict[str, Any]) -> None:
    if value != manifest(value["context"], value["mutants"]):
        raise Refusal("manifest-hash")


def assigned(value: dict[str, Any], index: int) -> list[dict[str, Any]]:
    if type(index) is not int or index not in range(SHARDS):
        raise Refusal("shard-index")
    return [r for n, r in enumerate(value["mutants"]) if n % SHARDS == index]


def report(
    value: dict[str, Any],
    index: int | None,
    records: list[dict[str, Any]],
    command_exit: int,
) -> dict[str, Any]:
    names = value["mutants"] if index is None else assigned(value, index)
    return dict(
        manifest_sha256=value["sha256"],
        shard_index=index,
        names=[r["name"] for r in names],
        records=records,
        command_exit=command_exit,
    )


def checked_records(
    value: dict[str, Any], payload: dict[str, Any], expected: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    required = {"manifest_sha256", "shard_index", "names", "records", "command_exit"}
    if not required <= payload.keys() or payload.keys() - required - {
        "timing",
        "budgets",
        "incidents",
    }:
        raise Refusal("report-schema")
    if payload.get("incidents"):
        raise Refusal("shard-incident")
    if payload["manifest_sha256"] != value["sha256"]:
        raise Refusal("manifest-hash")
    if payload["names"] != [r["name"] for r in expected]:
        raise Refusal("assigned-names")
    if type(payload["command_exit"]) is not int or payload["command_exit"] != 0:
        raise Refusal("command-failed")
    records: list[dict[str, Any]] = payload["records"]
    names = [r["name"] for r in records]
    if len(names) != len(set(names)):
        raise Refusal("duplicate-mutant")
    hashes = {r["name"]: r["diff_sha256"] for r in expected}
    if set(names) - hashes.keys():
        raise Refusal("foreign-mutant")
    if hashes.keys() - set(names):
        raise Refusal("missing-mutant")
    for row in records:
        if not {
            "name",
            "diff_sha256",
            "raw_exit",
            "status",
        } <= row.keys() or row.keys() - {
            "name",
            "diff_sha256",
            "raw_exit",
            "status",
            "mutation",
        }:
            raise Refusal("record-schema")
        if row["raw_exit"] is not None and type(row["raw_exit"]) is not int:
            raise Refusal("raw-exit-type")
        if row["diff_sha256"] != hashes[row["name"]]:
            raise Refusal("diff-hash")
        if row["status"] != status(row["raw_exit"]):
            raise Refusal("status-confusion")
        if (
            row["status"] in ("survived", "not_covered")
            and digest(row.get("mutation", "").encode()) != row["diff_sha256"]
        ):
            raise Refusal("survivor-diff-hash")
    return records


def summary(value: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return dict(
        manifest=value,
        records=sorted(records, key=lambda r: r["name"]),
        counts={s: sum(r["status"] == s for r in records) for s in STATUSES},
        survivors=[
            {k: r[k] for k in ("name", "diff_sha256")}
            for r in sorted(records, key=lambda r: r["name"])
            if r["status"] == "survived"
        ],
        incidents=[],
    )


def merge(value: dict[str, Any], parts: list[Any], states: list[str]) -> dict[str, Any]:
    verify_manifest(value)
    if len(parts) != SHARDS or any(not p for p in parts):
        raise Refusal("missing-shard")
    if states != ["success"] * SHARDS:
        raise Refusal("failed-shard")
    records = []
    for index, part in enumerate(parts):
        encode(part)
        if type(part["shard_index"]) is not int or part["shard_index"] != index:
            raise Refusal("shard-index")
        records.extend(checked_records(value, part, assigned(value, index)))
    return summary(value, records)


def compare(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    for value in (left, right):
        universe = value["manifest"]
        verify_manifest(universe)
        records = checked_records(
            universe, report(universe, None, value["records"], 0), universe["mutants"]
        )
        computed = summary(universe, records)
        if any(
            value[key] != computed[key] for key in ("counts", "survivors", "incidents")
        ):
            raise Refusal("summary-mismatch")
        if computed["counts"]["infrastructure_failure"]:
            raise Refusal("incomplete-campaign")
    if left["manifest"] != right["manifest"]:
        raise Refusal("comparison-manifest")
    differences = []
    for key in ("counts", "records", "incidents"):
        if left[key] != right[key]:
            differences.append(key)
    left_rows = {r["name"]: r for r in left["records"]}
    right_rows = {r["name"]: r for r in right["records"]}
    for name in sorted(left_rows.keys() | right_rows.keys()):
        if left_rows.get(name) != right_rows.get(name):
            differences.append(name)
    return differences


def read(path: Path) -> Any:
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise Refusal("symlink")
    with path.open("rb") as stream:
        data = stream.read(CAP + 1)
    if len(data) > CAP:
        raise Refusal("payload-overflow")
    return decode(data.decode())


def write(path: Path, value: Any) -> None:
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise Refusal("symlink")
    path.write_text(encode(value) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--module", required=True)
    validate.add_argument("--ref", required=True)
    validate.add_argument("--workflow-ref", required=True)
    transport = commands.add_parser("transport")
    transport.add_argument("path", type=Path)
    transport.add_argument(
        "--name",
        choices=["manifest", *[f"shard_{n}" for n in range(SHARDS)]],
        required=True,
    )
    commands.add_parser("receive")
    synthetic = commands.add_parser("synthetic")
    synthetic.add_argument("--shard-index", type=int, choices=range(SHARDS))
    merger = commands.add_parser("merge")
    merger.add_argument("--manifest", type=Path, default=Path("manifest.json"))
    merger.add_argument("--parts", nargs=4, type=Path)
    merger.add_argument("--output", type=Path, default=Path("merged.json"))
    comparator = commands.add_parser("compare")
    comparator.add_argument("local", type=Path)
    comparator.add_argument("hosted", type=Path)
    args = parser.parse_args()
    try:
        for key in ("path", "manifest", "output", "local", "hosted", "parts"):
            value = getattr(args, key, None)
            paths = (
                value
                if isinstance(value, list)
                else [value]
                if value is not None
                else []
            )
            for path in paths:
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or any(ord(c) < 32 or ord(c) == 127 for c in str(path))
                ):
                    raise Refusal("unsafe-evidence-path")
        if args.command == "validate":
            validate_ref(Path.cwd(), args.module, args.ref, args.workflow_ref)
        elif args.command == "transport":
            payload = encode(read(args.path))
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
                stream.write(args.name + "=" + payload + "\n")
        elif args.command == "synthetic":
            value = manifest(
                {"commit": "a" * 40, "module": MODULE, "hashes": {}, "synthetic": True},
                [
                    {"name": f"toy.x_value__mutmut_{n}", "diff_sha256": "b" * 64}
                    for n in range(8)
                ],
            )
            if args.shard_index is None:
                write(Path("manifest.json"), value)
            else:
                if read(Path("manifest.json")) != value:
                    raise Refusal("synthetic-manifest")
                rows = [
                    dict(r, raw_exit=1, status="killed")
                    for r in assigned(value, args.shard_index)
                ]
                write(Path("shard.json"), report(value, args.shard_index, rows, 0))
        elif args.command == "receive":
            value = decode(os.environ["MANIFEST"])
            verify_manifest(value)
            write(Path("manifest.json"), value)
        elif args.command == "merge":
            try:
                value = (
                    read(args.manifest)
                    if args.parts
                    else decode(os.environ.get("MANIFEST", ""))
                )
                parts = (
                    [read(p) for p in args.parts]
                    if args.parts
                    else [
                        decode(os.environ.get(f"SHARD_{n}", "")) for n in range(SHARDS)
                    ]
                )
                states = (
                    ["success"] * SHARDS
                    if args.parts
                    else [os.environ.get("SHARDS_STATE", "")] * SHARDS
                )
                if not args.parts and os.environ.get("DISCOVERY_STATE") != "success":
                    raise Refusal("failed-discovery")
                result = merge(value, parts, states)
                from mutation import judge

                code = max(
                    int(result["counts"]["infrastructure_failure"] > 0),
                    judge(
                        [
                            dict(
                                module=value["context"]["module"],
                                mutation=r["mutation"],
                            )
                            for r in result["records"]
                            if r["status"] in ("survived", "not_covered")
                        ],
                        Path("scripts/mutation_explained.toml"),
                    ),
                )
                write(args.output, result)
                print(encode(result["counts"]))
                return code
            except (
                Refusal,
                KeyError,
                TypeError,
                AttributeError,
                RecursionError,
                OSError,
                ValueError,
            ) as exc:
                reason = str(exc) if isinstance(exc, Refusal) else "malformed-evidence"
                write(
                    args.output,
                    dict(
                        counts={
                            s: int(s == "infrastructure_failure") for s in STATUSES
                        },
                        incidents=[reason],
                        records=[],
                    ),
                )
                raise Refusal(reason) from exc
        elif args.command == "compare":
            differences = compare(read(args.local), read(args.hosted))
            print(encode({"differences": differences}))
            return int(bool(differences))
        return 0
    except (
        Refusal,
        KeyError,
        TypeError,
        AttributeError,
        RecursionError,
        OSError,
        ValueError,
    ) as exc:
        reason = str(exc) if isinstance(exc, Refusal) else "malformed-evidence"
        print("mutation-pilot: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
