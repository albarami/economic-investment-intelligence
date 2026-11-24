"""Run-level plants in a disposable git repository, with offline stand-ins."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Match the offline eval tests under the runner's safe-path Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.question_lab import runner
from evals.question_lab.locks import BUDGET, digest, git_text, locked_budget

ROOT = Path(__file__).resolve().parents[2]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=INVENTED-maker",
            "-c",
            "user.email=INVENTED@invalid",
            *args,
        ],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    lab = root / "evals/question_lab"
    lab.mkdir(parents=True)
    # Only tracked lab sources and the explicitly hashed supporting inputs.
    for source in sorted((ROOT / "evals/question_lab").iterdir()):
        if source.suffix in {".json", ".py"}:
            shutil.copyfile(source, lab / source.name)
    (lab / "ledger.jsonl").write_text(
        json.dumps(
            {
                "run": "INVENTED-prior",
                "status": "incomplete",
                "exit": 1,
                "previous_sha256": digest(b""),
            }
        )
        + "\n"
    )
    for name in (
        "scripts/tests/public_release_fixture.py",
        "product/tests/public_opening_server.py",
        "product/tests/public_http_support.py",
        "web/src/brief/catalogue.generated.json",
        "web/src/brief/catalogue.ts",
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
    ):
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    (root / ".gitignore").write_text(".overnight/\nevals/question_lab/runs/\n")
    git(root, "init", "--quiet")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "test: invented fixture")
    return root


@pytest.fixture
def standins(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"plant": "control", "builder_calls": 0, "closed": 0}
    monkeypatch.setattr(sys, "path", list(sys.path))

    def close() -> None:
        state["closed"] += 1

    def build_fixture_app(work: Path, dist: Path) -> tuple[Any, Any, Any]:
        state["builder_calls"] += 1
        root = dist.parents[1]
        if state["plant"] == "budget":
            path = root / BUDGET
            path.write_bytes(path.read_bytes() + b"\n")
        elif state["plant"] == "input":
            path = root / "product/tests/public_http_support.py"
            path.write_bytes(path.read_bytes() + b"\n")
        elif state["plant"] == "provider":
            (work / "egress-attempts.txt").write_text("INVENTED-attempt")
        return (
            object(),
            SimpleNamespace(release_id="INVENTED-release", close=close),
            SimpleNamespace(close=close),
        )

    def execute_case(
        client: Any, release: str, case: Any, language: str
    ) -> dict[str, Any]:
        return {
            "question_id": case.identity,
            "language": language,
            "family": case.family,
            "scope": "standin_not_application_evidence",
            "status": "OK",
            "problems": ["accuracy:INVENTED"] if state["plant"] == "typed" else [],
            "judgements": {"accuracy": "passed:typed_api_only"},
        }

    def import_module(name: str) -> Any:
        if name == "product.tests.public_opening_server":
            return SimpleNamespace(build_fixture_app=build_fixture_app)
        assert name == "product.tests.public_http_support"
        return SimpleNamespace(Client=lambda app: object())

    monkeypatch.setattr(runner, "import_module", import_module)
    monkeypatch.setattr(runner, "execute_case", execute_case)
    monkeypatch.setattr(
        runner, "capture_answers", lambda *args: ([], ["browser:standin"])
    )
    monkeypatch.setattr(
        runner,
        "plant_results",
        lambda: [
            {
                "control_problems": ["INVENTED-dirty"]
                if state["plant"] == "plant"
                else [],
                "intended_diagnostic": "INVENTED-guard",
                "plant_problems": ["INVENTED-guard"],
            }
        ],
    )
    return state


def qualification(root: Path) -> tuple[Path, dict[str, Any]]:
    folders = list((root / "evals/question_lab/runs").iterdir())
    assert len(folders) == 1
    return folders[0], json.loads((folders[0] / "qualification.json").read_text())


def test_runner_control_binds_inputs_and_keeps_qualification_incomplete(
    repository: Path, standins: dict[str, Any]
) -> None:
    prior = (repository / "evals/question_lab/ledger.jsonl").read_bytes()
    assert runner.run_lab(repository, {}, 100, 17) == 1
    folder, report = qualification(repository)
    assert report["executions"] == 200
    assert report["typed_api_failures"] == 0
    assert "oracle:typed_case_failed" not in report["problems"]
    assert "plants:intended_guard_failed" not in report["problems"]
    assert standins["builder_calls"] == 1 and standins["closed"] == 2
    manifest = json.loads((folder / "manifest.json").read_text())
    name = "product/tests/public_http_support.py"
    assert manifest["input_sha256"][name] == digest((repository / name).read_bytes())
    assert manifest["commit"] == git(repository, "rev-parse", "HEAD")
    ledger = (repository / "evals/question_lab/ledger.jsonl").read_bytes()
    assert ledger.startswith(prior)
    assert len(ledger.splitlines()) == 2


@pytest.mark.parametrize(
    "plant,diagnostic",
    [
        ("budget", "budget:changed_during_run"),
        ("input", "inputs:changed_during_run"),
        ("provider", "provider_attempt"),
        ("typed", "oracle:typed_case_failed"),
        ("plant", "plants:intended_guard_failed"),
    ],
)
def test_runner_aggregates_planted_failures(
    repository: Path, standins: dict[str, Any], plant: str, diagnostic: str
) -> None:
    standins["plant"] = plant
    assert runner.run_lab(repository, {}, 100, 17) == 1
    assert diagnostic in qualification(repository)[1]["problems"]


def test_runner_refuses_edited_committed_ledger_before_output(
    repository: Path, standins: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = repository / "evals/question_lab/ledger.jsonl"
    ledger.write_bytes(
        ledger.read_bytes().replace(b"INVENTED-prior", b"INVENTED-edited")
    )
    assert runner.run_lab(repository, {}, 100, 17) == 1
    assert "ledger_changed" in capsys.readouterr().err
    assert not (repository / "evals/question_lab/runs").exists()
    assert standins["builder_calls"] == 0


def test_runner_refuses_linked_output_before_writing(
    repository: Path, standins: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    target = repository / "INVENTED-output"
    target.mkdir()
    (repository / "evals/question_lab/runs").symlink_to(
        target, target_is_directory=True
    )
    assert runner.run_lab(repository, {}, 100, 17) == 1
    assert "output_path" in capsys.readouterr().err
    assert list(target.iterdir()) == []
    assert standins["builder_calls"] == 0


def test_locked_budget_walks_committed_history(repository: Path) -> None:
    path = repository / BUDGET
    budget = json.loads(path.read_bytes())
    budget["limits_ms"]["map"]["p95"] = 400
    path.write_text(json.dumps(budget))
    git(repository, "add", BUDGET)
    git(repository, "commit", "--quiet", "-m", "test: stricter invented budget")
    assert "budget:loosened_after_run" not in locked_budget(repository)[1]
    budget["limits_ms"]["map"]["p95"] = 450
    path.write_text(json.dumps(budget))
    git(repository, "add", BUDGET)
    git(repository, "commit", "--quiet", "-m", "test: plant invented loosening")
    assert "budget:loosened_after_run" in locked_budget(repository)[1]


@pytest.mark.parametrize("limit", [None, 10, "INVENTED-invalid", []])
def test_malformed_budget_refuses_without_orphan_folder(
    repository: Path,
    standins: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    limit: Any,
) -> None:
    path = repository / BUDGET
    budget = json.loads(path.read_bytes())
    budget["limits_ms"]["map"] = limit
    path.write_text(json.dumps(budget))
    prior = (repository / "evals/question_lab/ledger.jsonl").read_bytes()
    assert runner.run_lab(repository, {}, 100, 17) == 1
    assert "budget:raised_or_invalid_limit" in capsys.readouterr().err
    assert not (repository / "evals/question_lab/runs").exists()
    assert (repository / "evals/question_lab/ledger.jsonl").read_bytes() == prior
    assert standins["builder_calls"] == 0


def test_git_unavailable_refuses_before_output(
    repository: Path,
    standins: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(runner, "git_text", lambda *args: None)
    assert runner.run_lab(repository, {}, 100, 17) == 1
    assert "git_unavailable" in capsys.readouterr().err
    assert not (repository / "evals/question_lab/runs").exists()
    assert standins["builder_calls"] == 0


def test_unknown_working_tree_status_never_silently_passes(
    repository: Path,
    standins: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_git = git_text
    monkeypatch.setattr(
        runner,
        "git_text",
        lambda root, *args: None if args[0] == "status" else real_git(root, *args),
    )
    assert runner.run_lab(repository, {}, 100, 17) == 1
    assert "head:working_tree_unknown" in qualification(repository)[1]["problems"]


def test_missing_git_executable_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("INVENTED-missing-git")

    monkeypatch.setattr(subprocess, "run", unavailable)
    assert git_text(tmp_path, "rev-parse", "HEAD") is None
