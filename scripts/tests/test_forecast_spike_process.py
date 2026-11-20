"""Real CPU Auto models on invented histories; no Public acceptance evidence."""

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
            metadata = json.loads(result.stderr.splitlines()[-1])
            diagnostic_lines = result.stderr.splitlines()[:-1]
            assert metadata["device"] == "cpu" and metadata["threads"] == 1
            assert metadata["workers"] == workers and metadata["batch_seconds"] >= 0
            assert metadata["peak_memory_kib"] > 0
            payload = json.loads(result.stdout)
            assert payload["fixture_only"] is True
            assert payload["model_inference"] == "statsforecast_auto_models"
            assert payload["statistical_library"] == {
                "name": "statsforecast",
                "version": "2.1.1",
            }
            assert payload["challengers"] == {
                "chronos_2": "blocked",
                "timesfm_2_5": "blocked",
            }
            assert payload["adapter_kind"] == "statsforecast_prefix_callbacks"
            for summary in payload["family_summaries"]:
                if summary["evaluated"] != summary["expected"]:
                    assert summary["status"] == "blocked"
                    assert summary["reason"] == "missing_prediction_or_interval"
                    assert summary["score"] is None
                else:
                    assert summary["score"] is not None
            assert any(
                s["candidate"] == "auto_arima" and s["evaluated"] == s["expected"]
                for s in payload["family_summaries"]
            )
            assert any(
                s["candidate"] == "auto_ets" and s["status"] == "blocked"
                for s in payload["family_summaries"]
            )
            for result_run in payload["runs"]:
                by_key = {row["candidate"]: row for row in result_run["series"]}
                assert all(
                    any(
                        a["prediction"] != b["prediction"]
                        for a, b in zip(
                            by_key[key]["origins"],
                            by_key["seasonal_naive"]["origins"],
                            strict=True,
                        )
                    )
                    for key in ("auto_ets", "auto_theta", "auto_arima")
                )
            assert len(payload["family_summaries"]) == 24
            samples.append(ProcessOutput(metadata["process"], workers, result.stdout))
            measurements.append(
                {
                    "workers": workers,
                    "batch_seconds": format(metadata["batch_seconds"], ".6f"),
                    "largest_worker_peak_kib": metadata["peak_memory_kib"],
                    "fixture_only": True,
                    "library_warnings": sorted(
                        {
                            line.decode().split("RuntimeWarning: ", 1)[1]
                            for line in diagnostic_lines
                            if b"RuntimeWarning: " in line
                        }
                    ),
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
                "model_inference": payload["model_inference"],
                "adapter_kind": payload["adapter_kind"],
                "statistical_library": payload["statistical_library"],
                "lock_sha256": payload["lock_sha256"],
                "statistical_stage_verdicts": payload["statistical_stage_verdicts"],
                "fixture_only": True,
                "determinism": "pass",
                "threads": 1,
                "challengers": payload["challengers"],
                "family_summaries": payload["family_summaries"],
            },
            sort_keys=True,
        )
    )
