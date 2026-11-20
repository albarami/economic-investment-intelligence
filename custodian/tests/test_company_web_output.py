"""The unchanged repository scanner and the stricter URL-path field guard (F9)."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from custodian.tests.company_web_fixture import offline_network  # noqa: F401


@pytest.mark.parametrize("length", [8, 11])
def test_unchanged_check_docs_refuses_planted_bare_run_in_git_tree(
    tmp_path: Path, length: int, monkeypatch
) -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    scanner = scripts / "check_docs.py"
    original = (root / "scripts" / "check_docs.py").read_bytes()
    scanner.write_bytes(original)
    (scripts / "check_docs_place_exceptions.toml").write_text("exception = []\n")
    required = next(
        ast.literal_eval(node.value)
        for node in ast.parse(original).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "REQUIRED_FILES"
            for target in node.targets
        )
    )
    skeleton = "# Invented scanner fixture\n\n| | |\n|---|---|\n| Status | Fixture |\n| Date | 2026-11-20 |\n| Owner | Invented |\n| Purpose | Scanner control |\n"
    for name in required:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(skeleton)
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir()
    (decisions / "0001-invented.md").write_text(skeleton)
    monkeypatch.delenv("EII_FORBIDDEN_PATTERNS_FILE", raising=False)
    initialized = subprocess.run(
        ["git", "init", "-q", str(tmp_path)], capture_output=True
    )
    assert initialized.returncode == 0
    # The unchanged scanner passes the invented skeleton before and after the plant.
    control = subprocess.run(
        [sys.executable, str(scanner)], cwd=tmp_path, capture_output=True, text=True
    )
    assert control.returncode == 0, control.stdout
    (tmp_path / "planted.md").write_text("Invented field: " + "6" * length + "\n")
    # Untracked, non-ignored outputs are part of the real scanner's scan set.
    completed = subprocess.run(
        [sys.executable, str(scanner)], cwd=tmp_path, capture_output=True, text=True
    )
    assert completed.returncode == 1
    assert any(
        "planted.md:" in line and "identifier-shaped number" in line
        for line in completed.stdout.splitlines()
    )
    assert sum(line.startswith("FAIL ") for line in completed.stdout.splitlines()) == 1
    (tmp_path / "planted.md").write_text("Invented field: SYN safe\n")
    restored = subprocess.run(
        [sys.executable, str(scanner)], cwd=tmp_path, capture_output=True, text=True
    )
    assert restored.returncode == 0, restored.stdout
    assert (root / "scripts" / "check_docs.py").read_bytes() == original
