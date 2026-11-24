"""One closed offline lab command; fail closed on missing qualification evidence."""

from __future__ import annotations

import contextlib
import io
import json
import os
import platform
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from eii_core.reasons import reason
from evals.question_lab.api import execute_case
from evals.question_lab.capture import capture_answers
from evals.question_lab.cases import (
    coverage,
    execution_coverage,
    load_cases,
    select_cases,
)
from evals.question_lab.locks import BUDGET, digest, git_text, locked_budget
from evals.question_lab.packet import (
    ledger_problems,
    packet_problems,
    write_gallery,
    write_json,
    write_results,
)
from evals.question_lab.plants import plant_results
from evals.question_lab.safety import child_environment, loopback_only

JUDGEMENTS = ("accuracy", "smoothness", "value", "visual", "map")


def run_lab(root: Path, environ: Mapping[str, str], n: int, seed: int) -> int:
    try:
        cases = select_cases(load_cases(root), n, seed)
    except (ValueError, OSError, TypeError, KeyError) as error:
        print("FAIL question-lab: " + reason(error), file=sys.stderr)
        return 2
    lab = root / "evals/question_lab"
    ledger_path = lab / "ledger.jsonl"
    previous = ledger_path.read_bytes()
    committed_ledger = git_text(root, "show", "HEAD:evals/question_lab/ledger.jsonl")
    # git_text strips the trailing newline; reconstruct it for the prefix proof.
    committed_prefix = (committed_ledger + "\n").encode() if committed_ledger else b""
    if ledger_problems(previous, committed=committed_prefix):
        print("FAIL question-lab: ledger_changed", file=sys.stderr)
        return 1
    # Never use a linked output directory to cross the workspace boundary.
    if lab.is_symlink() or (lab / "runs").is_symlink():
        print("FAIL question-lab: output_path", file=sys.stderr)
        return 1
    commit = git_text(root, "rev-parse", "HEAD")
    if commit is None:
        print("FAIL question-lab: git_unavailable", file=sys.stderr)
        return 1
    try:
        raw, waiting = locked_budget(root)
    except (ValueError, TypeError, KeyError, OSError):
        print("FAIL question-lab: budget:invalid_input", file=sys.stderr)
        return 1
    if "budget:raised_or_invalid_limit" in waiting:
        print("FAIL question-lab: budget:raised_or_invalid_limit", file=sys.stderr)
        return 1
    inputs = [
        "evals/question_lab/cases.v1.json",
        BUDGET,
        "evals/question_lab/oracles.py",
        "scripts/tests/public_release_fixture.py",
        "product/tests/public_opening_server.py",
        "product/tests/public_http_support.py",
        "web/src/brief/catalogue.generated.json",
        "web/src/brief/catalogue.ts",
        "evals/question_lab/gallery_index.v1.json",
        "eii",
        "scripts/commands/table.py",
        "scripts/commands/main.py",
        "scripts/commands/question_lab.py",
        "web/playwright.question-lab.config.ts",
        "web/tests/question_lab/answers.spec.ts",
        "web/tests/question_lab/baselines.mjs",
        "web/tests/question_lab/parity.ts",
        "web/tests/question_lab/matrix.ts",
        "web/tests/question_lab/clock.ts",
        "evals/question_lab/guards.v1.json",
    ]
    inputs.extend(
        "evals/question_lab/" + name + ".py"
        for name in (
            "__init__",
            "api",
            "cases",
            "capture",
            "locks",
            "oracles",
            "packet",
            "runner",
            "safety",
            "timing",
            "plants",
        )
    )
    status = git_text(root, "status", "--porcelain", "--untracked-files=normal")
    if status is None:
        waiting.append("head:working_tree_unknown")
    elif status:
        waiting.append("head:working_tree_changed")
    input_identities = {name: digest((root / name).read_bytes()) for name in inputs}
    manifest = {
        "version": "question-lab.run.v1",
        "n": n,
        "seed": seed,
        "counting_unit": "distinct_question_identity_each_in_both_languages",
        "commit": commit,
        "started_at": datetime.now(UTC).isoformat(),
        "provider": "none",
        "network": "loopback_only",
        "python": platform.python_version(),
        "platform": sys.platform,
        "fixture": "S3-T10_invented_loaded_embedded_not_live_store_parity",
        "input_sha256": input_identities,
        "budget_sha256": digest(raw),
        "budget_problems": waiting,
        "measurement": "disabled_until_prior_ratification_and_commit",
    }
    # The exclusive-start manifest precedes app construction and all observations.
    folder = lab / "runs" / ("run-" + uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    with (folder / "manifest.json").open("x") as output:
        output.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    write_json(folder / "selection.json", [asdict(case) for case in cases])
    grid = coverage(cases)
    write_json(folder / "coverage.json", grid)
    rows = []
    attempts: list[str] = []
    tmp = root / ".overnight/tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    safe = child_environment(environ)
    safe["TMPDIR"] = str(tmp)
    sys.path.insert(0, str(root / "scripts/tests"))
    # Existing fixture modules import each other by their documented test path.
    try:
        with (
            tempfile.TemporaryDirectory(dir=tmp, prefix="question-lab-") as work,
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
            patch.dict(os.environ, safe, clear=True),
            loopback_only(attempts),
        ):
            builder = import_module(
                "product.tests.public_opening_server"
            ).build_fixture_app
            app, store, ledger = builder(Path(work), root / "web/dist")
            try:
                client_type = import_module("product.tests.public_http_support").Client
                for case in cases:
                    for language in ("en", "ar"):
                        try:
                            client = client_type(app)
                            row = execute_case(client, store.release_id, case, language)
                        except Exception as error:
                            row = {
                                "question_id": case.identity,
                                "language": language,
                                "family": case.family,
                                "scope": "typed_api_fixture",
                                "status": "FAILED",
                                "problems": ["execution:" + reason(error)],
                                "judgements": {
                                    key: "failed:execution" for key in JUDGEMENTS
                                },
                            }
                        rows.append(row)
            finally:
                ledger.close()
                store.close()
            if (Path(work) / "egress-attempts.txt").exists():
                attempts.append("provider_attempt")
    except Exception as error:
        waiting.append("fixture:" + reason(error))
    if attempts:
        waiting.extend(attempts)
    if (root / BUDGET).read_bytes() != raw:
        waiting.append("budget:changed_during_run")
    for name, identity in input_identities.items():
        if digest((root / name).read_bytes()) != identity:
            waiting.append("inputs:changed_during_run")
    write_results(folder, rows)
    probes = plant_results()
    write_json(folder / "guard_plants.json", probes)
    if any(
        row["control_problems"]
        or row["intended_diagnostic"] not in row["plant_problems"]
        for row in probes
    ):
        waiting.append("plants:intended_guard_failed")
    captures, capture_waiting = capture_answers(root, folder, environ, waiting)
    waiting.extend(capture_waiting)
    write_json(folder / "coverage.json", execution_coverage(cases, rows, captures))
    write_json(
        folder / "timings.json",
        {
            "scope": "native_measurements",
            "status": "waiting",
            "samples": [],
            "reason": "ratification_commit_and_declared_native_devices_required",
            "summaries": {"p50": None, "p95": None, "worst": None},
        },
    )
    waiting.extend(packet_problems(folder, [case.identity for case in cases]))
    waiting.extend(
        [
            "seal:separate_identity_not_provisioned",
            "pixel:approved_CI_baselines_required",
            "prerequisite:dated_opening_chip",
            "prerequisite:firms_chain",
            "native:stage_and_phone",
            "review:independent_maker",
            "review:native_arabic",
            "review:owner_gallery",
            "browser:full_question_matrix_waiting",
        ]
    )
    if any(row["problems"] for row in rows):
        waiting.append("oracle:typed_case_failed")
    write_json(
        folder / "qualification.json",
        {
            "status": "incomplete",
            "exit": 1,
            "problems": sorted(set(waiting)),
            "executions": len(rows),
            "distinct_questions": len({row["question_id"] for row in rows}),
            "typed_api_failures": sum(bool(row["problems"]) for row in rows),
            "not_qualification": "Functional fixture evidence cannot substitute for native, sealed, pixel or human evidence.",
        },
    )
    write_gallery(folder, captures)
    artifacts = {
        path.name: digest(path.read_bytes())
        for path in sorted(folder.iterdir())
        if path.is_file()
    }
    entry = {
        "run": folder.relative_to(root).as_posix(),
        "commit": commit,
        "seed": seed,
        "n": n,
        "status": "incomplete",
        "exit": 1,
        "budget_sha256": digest(raw),
        "previous_sha256": digest(previous),
        "artifacts": artifacts,
    }
    if ledger_path.read_bytes() != previous:
        print("FAIL question-lab: concurrent_ledger_change", file=sys.stderr)
        return 1
    with ledger_path.open("ab") as output:
        output.write(
            json.dumps(entry, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
    print(
        "FAIL question-lab: qualification_incomplete; "
        + folder.relative_to(root).as_posix()
    )
    return 1
