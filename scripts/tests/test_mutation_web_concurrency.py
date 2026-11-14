"""Exercise the generated command and Stryker budget through the real entry point."""

import json
import shlex
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import mutation_web


@pytest.mark.parametrize("processors", [1, 3, 7, 32, 64, None])
def test_mutation_workers_and_node_files_share_processor_budget(
    tmp_path: Path, processors: int | None
) -> None:
    root = tmp_path / "synthetic-runner"
    module = "web/spikes/performance/example.mjs"
    tests = [
        f"web/spikes/performance/tests/case {index}.node-test.mjs"
        for index in range(20)
    ]
    browser = "web/spikes/performance/tests/run.node-test.mjs"
    files = [module, *tests, browser]
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// synthetic runner fixture\n")
    (root / "web/node_modules").mkdir()
    ledger = root / "scripts/mutation_explained.toml"
    ledger.parent.mkdir()
    ledger.write_text("survivors = []\n")
    observed = []

    def run(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
        if arguments[0] == "git":
            return subprocess.CompletedProcess(arguments, 0, "\0".join(files).encode())
        assert arguments[0] == "node"
        config_path = Path(arguments[-1])
        config = json.loads(config_path.read_text())
        processors_available = processors or 1
        workers = config["concurrency"]
        assert 1 <= workers <= processors_available
        wrapper = shlex.split(config["commandRunner"]["command"])
        assert wrapper[:2] == ["node", "-e"]
        embedded = wrapper[2].split("status=spawnSync('sh',['-c',", 1)[1]
        command = json.loads(embedded.split("],{cwd:work", 1)[0])
        argv = shlex.split(command)
        assert argv[:2] == ["node", "--test"]
        flags = [arg for arg in argv if arg.startswith("--test-concurrency=")]
        assert len(flags) == 1, "Each mutant must bound Node's test-file concurrency"
        node_files = int(flags[0].split("=", 1)[1])
        assert workers == min(4, processors_available)
        assert node_files == max(1, processors_available // workers)
        assert workers * node_files <= processors_available
        assert argv[3:] == sorted(tests)
        assert browser not in argv
        observed.append((workers, node_files))
        report = config_path.parent / "reports/mutation.json"
        report.parent.mkdir()
        report.write_text(json.dumps({"files": {module: {"mutants": []}}}))
        return subprocess.CompletedProcess(arguments, 0, "", "")

    with (
        patch.object(mutation_web, "ROOT", root),
        patch("mutation_web.os.cpu_count", return_value=processors),
        patch("mutation_web.sys.argv", ["mutation_web.py", module]),
        patch("mutation_web.subprocess.run", side_effect=run),
    ):
        assert mutation_web.main() == 0
    assert len(observed) == 1
