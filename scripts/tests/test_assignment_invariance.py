"""PRV-124: a process boundary, an input audit, and every stored outline.

Only the named synthetic fixtures and standard-library temporary folders are
used. No service, vault, feed, external file or network is an input.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import h3
from eii_product.areas_spike.engine import scaled_actor
from eii_product.areas_spike.traffic import Traffic

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "custodian/tests/fixtures/assignment_spike"
RECORDED = ROOT / "product/tests/fixtures/areas_spike/assignment"

AUDIT = """import os
import pathlib
import sys
folder = pathlib.Path(os.environ["ASSIGNMENT_FIXTURE"])
committed = pathlib.Path(os.environ["ASSIGNMENT_COMMITTED"])
standins = {"protected_standin.json", "withheld_standin.json"}
allowed = {folder / name for name in ("hourly_flows.json", "hourly_roads.json", "parameters_v1.json")}
seen = set()
def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = pathlib.Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(committed) or path.name in standins:
            raise AssertionError("assignment input-list violation: " + path.name)
        if path.is_relative_to(folder):
            if path not in allowed:
                raise AssertionError("assignment input-list violation: " + path.name)
            seen.add(path.name)
sys.addaudithook(audit)
import atexit
@atexit.register
def record():
    pathlib.Path(os.environ["ASSIGNMENT_OPENED"]).write_text("\\n".join(sorted(seen)))
"""


class AssignmentInvarianceTests(unittest.TestCase):
    def test_assignment_standins_leave_rows_and_all_outlines_identical(self) -> None:
        with TemporaryDirectory(prefix="synthetic-assignment-") as temporary:
            folder = Path(temporary)
            inputs = folder / "inputs"
            inputs.mkdir()
            names = (
                "hourly_flows.json",
                "hourly_roads.json",
                "parameters_v1.json",
                "protected_standin.json",
                "withheld_standin.json",
            )
            for name in names:
                shutil.copyfile(FIXTURES / name, inputs / name)
            harness = folder / "harness"
            harness.mkdir()
            (harness / "sitecustomize.py").write_text(AUDIT)
            environment = {
                **os.environ,
                "PYTHONPATH": str(harness),
                "ASSIGNMENT_FIXTURE": str(inputs),
                "ASSIGNMENT_COMMITTED": str(FIXTURES),
            }
            frame = tuple(sorted(h3.grid_disk(h3.latlng_to_cell(0, 0, 9), 12)))
            outputs = []
            for run in range(2):
                if run:
                    for name in names[-2:]:
                        (inputs / name).write_text(
                            json.dumps(
                                {
                                    "note": "Changed invented stand-in, still withheld.",
                                    "value": "999",
                                }
                            )
                        )
                rows = folder / f"rows-{run}.json"
                opened = folder / f"opened-{run}.txt"
                environment["ASSIGNMENT_OPENED"] = str(opened)
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "eii_custodian.assignment_spike",
                        *(str(inputs / name) for name in names[:3]),
                        str(rows),
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    "assignment input-list run failed: " + result.stderr,
                )
                self.assertTrue(
                    opened.is_file(), "assignment opened-file record missing"
                )
                self.assertEqual(
                    opened.read_text().splitlines(),
                    sorted(names[:3]),
                    "assignment opened-file list",
                )
                traffic = Traffic.load(
                    rows, inputs / "hourly_roads.json", inputs / "parameters_v1.json"
                )
                scaled_actor.cache_clear()
                outlines = tuple(
                    json.dumps(
                        asdict(traffic.area("SYN-N-0-0", 3, hour, frame)),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                    for hour in range(24)
                )
                outputs.append((rows.read_bytes(), outlines))
            self.assertEqual(
                outputs[0],
                outputs[1],
                "assignment protected/withheld invariance: rows and every outline",
            )
            self.assertEqual(
                outputs[0][0], (RECORDED / "hourly_rows.json").read_bytes()
            )
            self.assertEqual(
                (inputs / "hourly_roads.json").read_bytes(),
                (RECORDED / "hourly_roads.json").read_bytes(),
            )
            self.assertEqual(
                (inputs / "parameters_v1.json").read_bytes(),
                (RECORDED / "hourly_parameters.json").read_bytes(),
            )

    def test_assignment_audit_refuses_committed_and_named_standins(self) -> None:
        with TemporaryDirectory(prefix="synthetic-audit-") as temporary:
            folder = Path(temporary)
            inputs = folder / "inputs"
            inputs.mkdir()
            harness = folder / "harness"
            harness.mkdir()
            (harness / "sitecustomize.py").write_text(AUDIT)
            outside = folder / "protected_standin.json"
            outside.write_text("{}")
            withheld = folder / "withheld_standin.json"
            withheld.write_text("{}")
            unlisted = inputs / "unlisted.json"
            unlisted.write_text("{}")
            for index, planted in enumerate(
                (
                    FIXTURES / "protected_standin.json",
                    FIXTURES / "hourly_roads.json",
                    outside,
                    withheld,
                    unlisted,
                )
            ):
                with self.subTest(planted=planted.name, index=index):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            "import pathlib, sys; pathlib.Path(sys.argv[1]).read_bytes()",
                            str(planted),
                        ],
                        env={
                            **os.environ,
                            "PYTHONPATH": str(harness),
                            "ASSIGNMENT_FIXTURE": str(inputs),
                            "ASSIGNMENT_COMMITTED": str(FIXTURES),
                            "ASSIGNMENT_OPENED": str(folder / f"opened-{index}.txt"),
                        },
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0, planted.name)
                    self.assertIn(
                        "assignment input-list violation: " + planted.name,
                        result.stderr,
                    )

    def test_assignment_worked_copies_match_fresh_calculation(self) -> None:
        from eii_custodian.assignment_spike.run import calculate

        result = calculate(
            FIXTURES / "worked_flows.json",
            FIXTURES / "worked_roads.json",
            FIXTURES / "worked_parameters.json",
        )
        self.assertEqual(
            result.to_bytes(), (RECORDED / "worked_rows.json").read_bytes()
        )
        for name in ("worked_roads.json", "worked_parameters.json"):
            self.assertEqual(
                (FIXTURES / name).read_bytes(), (RECORDED / name).read_bytes()
            )
