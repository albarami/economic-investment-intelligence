"""Real fresh processes prove the fixture machinery, never model determinism."""

import json
import os
import platform
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from evals.forecast_spike.adapters import ProcessOutput, determinism


def test_fixture_bytes_across_fresh_processes_and_worker_counts() -> None:
    root = Path(__file__).resolve().parents[2]
    samples = []
    measurements = []
    for workers in (1, 2):
        for _ in range(2):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "evals.forecast_spike.fixture",
                    "--workers",
                    str(workers),
                ],
                cwd=root,
                capture_output=True,
                check=False,
                timeout=30,
                env={**os.environ, "EII_DECISION_PROVIDER": "none"},
            )
            assert result.returncode == 0, result.stderr.decode()
            metadata = json.loads(result.stderr)
            assert metadata["device"] == "cpu" and metadata["threads"] == 1
            assert metadata["workers"] == workers and metadata["batch_seconds"] >= 0
            assert metadata["peak_memory_kib"] > 0
            payload = json.loads(result.stdout)
            assert payload["fixture_only"] is True
            assert payload["model_inference"] == "blocked"
            assert len(payload["family_summaries"]) == 24
            samples.append(ProcessOutput(metadata["process"], workers, result.stdout))
            measurements.append(
                {
                    "workers": workers,
                    "batch_seconds": format(metadata["batch_seconds"], ".6f"),
                    "largest_worker_peak_kib": metadata["peak_memory_kib"],
                    "fixture_only": True,
                }
            )
    assert determinism(tuple(samples), (1, 2)).status == "pass"
    print(
        json.dumps(
            {
                "fixture_measurements": measurements,
                "python": platform.python_version(),
                "machine": platform.machine(),
                "preregistration_file_sha256": payload["preregistration_file_sha256"],
                "registration_sha256": payload["registration_sha256"],
                "fixture_output_sha256": sha256(samples[0].output).hexdigest(),
                "family_summaries": payload["family_summaries"],
            },
            sort_keys=True,
        )
    )
