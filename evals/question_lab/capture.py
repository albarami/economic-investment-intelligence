"""Optional full built-app capture companion, gated before any subprocess."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evals.question_lab.packet import write_json
from evals.question_lab.safety import child_environment


def capture_prerequisites(root: Path, budget_problems: Sequence[str]) -> list[str]:
    problems = []
    if not (root / "data/tools/playwright").is_dir():
        problems.append("browser:assets_missing")
    manifest = root / "web/tests/question_lab/baselines/manifest.json"
    if not manifest.is_file():
        problems.append("pixel:approved_CI_baselines_required")
    else:
        try:
            raw = json.loads(manifest.read_text())
            if (
                raw.get("origin") != "CI"
                or raw.get("review") != "APPROVED"
                or not raw.get("entries")
            ):
                problems.append("pixel:approved_CI_baselines_required")
        except (OSError, ValueError, AttributeError):
            problems.append("pixel:approved_CI_baselines_required")
    return [*problems, *budget_problems]


def capture_answers(
    root: Path, folder: Path, environ: Mapping[str, str], budget_problems: Sequence[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    problems = capture_prerequisites(root, budget_problems)
    if problems:
        return [], problems
    env = child_environment(environ)
    env["EII_QUESTION_LAB_PACKET"] = folder.relative_to(root).as_posix()
    env["TMPDIR"] = str(root / ".overnight/tmp")
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(root / "data/tools/playwright")
    try:
        result = subprocess.run(
            [
                "node",
                "node_modules/playwright/cli.js",
                "test",
                "--config",
                "playwright.question-lab.config.ts",
            ],
            cwd=root / "web",
            env=env,
            capture_output=True,
            check=False,
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], ["browser:failed_or_timed_out"]
    # Do not persist arbitrary child diagnostics or absolute paths. The exit and
    # actual per-answer observations remain attributable to this exact run.
    write_json(
        folder / "browser_exit.json", {"exit": result.returncode, "provider": "none"}
    )
    rows = [
        json.loads(path.read_text())
        for path in sorted((folder / "captures").glob("*.json"))
    ]
    write_json(folder / "captures.json", rows)
    if result.returncode != 0:
        problems.append("browser:failed")
    return rows, problems
